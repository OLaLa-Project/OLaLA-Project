"""
Stage 1 - Normalize (LLM-Enhanced)

?ъ슜???낅젰(?띿뒪??URL)???뺢퇋?뷀븯??寃利?媛?ν븳 ?⑥씪 二쇱옣(claim)?쇰줈 蹂?섑빀?덈떎.

Input state keys:
    - trace_id: str
    - input_type: "url" | "text" | "image"
    - input_payload: str
    - user_request: Optional[str]
    - language: "ko" | "en" (default: "ko")

Output state keys:
    - claim_text: str (?뺢퇋?붾맂 二쇱옣 臾몄옣)
    - language: str
    - canonical_evidence: dict (URL, 蹂몃Ц, ?쒕ぉ ??
    - entity_map: dict (異붿텧???뷀떚??
"""

import re
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional
from urllib.parse import urlparse, urlunparse
from functools import lru_cache

from app.stages._shared.slm_client import call_slm1, SLMError

logger = logging.getLogger(__name__)

# ?꾨＼?꾪듃 ?뚯씪 寃쎈줈
PROMPT_FILE = Path(__file__).parent / "prompt_normalize.txt"

# ?ㅼ젙
DEFAULT_LANGUAGE = "ko"
MAX_CONTENT_LENGTH = 1000


@lru_cache(maxsize=1)
def load_system_prompt() -> str:
    """?쒖뒪???꾨＼?꾪듃 濡쒕뱶 (罹먯떛)."""
    return PROMPT_FILE.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# URL 泥섎━
# ---------------------------------------------------------------------------

def extract_url_from_text(text: str) -> str:
    """?띿뒪?몄뿉??泥?踰덉㎏ URL 異붿텧."""
    match = re.search(r'https?://[^\s<>"\')\]]+', text)
    return match.group(0) if match else ""


def normalize_url(url: str) -> Dict[str, Any]:
    """URL ?뚯떛 諛??뺢퇋??"""
    if not url or not url.strip():
        return {"normalized_url": "", "is_valid": False, "domain": ""}
    try:
        clean = url.strip()
        if not clean.startswith(("http://", "https://", "ftp://")):
            clean = "https://" + clean
        parsed = urlparse(clean)
        normalized = urlunparse(parsed._replace(fragment=""))
        return {
            "normalized_url": normalized,
            "is_valid": bool(parsed.netloc),
            "domain": parsed.netloc,
        }
    except Exception as e:
        logger.warning(f"URL ?뚯떛 ?ㅽ뙣: {e}")
        return {"normalized_url": url, "is_valid": False, "domain": ""}


def fetch_url_content(url: str) -> Dict[str, str]:
    """
    URL?먯꽌 湲곗궗 蹂몃Ц怨??쒕ぉ 異붿텧 (trafilatura ?ъ슜).
    trafilatura媛 ?놁쑝硫?鍮?寃곌낵 諛섑솚.
    """
    try:
        import trafilatura
    except ImportError:
        logger.warning("trafilatura 誘몄꽕移?- URL 肄섑뀗痢?異붿텧 遺덇?")
        return {"text": "", "title": ""}

    try:
        downloaded = trafilatura.fetch_url(url)
        if not downloaded:
            return {"text": "", "title": ""}

        result = trafilatura.bare_extraction(
            downloaded, include_comments=False, include_tables=False
        )
        if result:
            return {
                "text": getattr(result, "text", "") or (result.get("text", "") if isinstance(result, dict) else ""),
                "title": getattr(result, "title", "") or (result.get("title", "") if isinstance(result, dict) else ""),
            }
    except Exception as e:
        logger.warning(f"URL 肄섑뀗痢?異붿텧 ?ㅽ뙣 ({url}): {e}")

    return {"text": "", "title": ""}


# ---------------------------------------------------------------------------
# ?띿뒪??遺꾩꽍 ?좏떥由ы떚
# ---------------------------------------------------------------------------

def detect_language(text: str) -> str:
    """?쒓뎅???곸뼱 媛꾩씠 媛먯?."""
    if not text:
        return DEFAULT_LANGUAGE
    korean = len(re.findall(r'[媛-??', text))
    english = len(re.findall(r'[a-zA-Z]', text))
    return "ko" if korean >= english else "en"


def extract_temporal_info(text: str, timestamp: Optional[str] = None) -> Dict[str, Any]:
    """?띿뒪?몄뿉???좎쭨/?쒓컙 ?⑦꽩 異붿텧."""
    patterns = [
        r'\d{4}??s*\d{1,2}??s*\d{1,2}??,
        r'\d{4}??s*\d{1,2}??,
        r'\d{4}-\d{2}-\d{2}',
        r'\d{4}\.\d{2}\.\d{2}',
    ]
    dates = []
    for p in patterns:
        dates.extend(re.findall(p, text or ""))

    return {
        "extracted_dates": list(set(dates)),
        "timestamp": timestamp or datetime.now(timezone.utc).isoformat(),
    }


def extract_entities(text: str) -> List[str]:
    """媛꾩씠 ?뷀떚??異붿텧 (怨좎쑀紐낆궗 ?꾨낫)."""
    if not text:
        return []
    words = text.split()
    entities = []
    for w in words:
        w_clean = w.strip(".,!?\"'()[]")
        if len(w_clean) <= 1:
            continue
        # ?곷Ц ?臾몄옄 ?쒖옉 ?먮뒗 ?쒓?
        if w_clean[0].isupper() or ('\uAC00' <= w_clean[0] <= '\uD7A3'):
            entities.append(w_clean)
    return list(set(entities))[:10]


# ---------------------------------------------------------------------------
# LLM 湲곕컲 二쇱옣 ?뺢퇋??
# ---------------------------------------------------------------------------

def normalize_claim_with_llm(
    user_input: str,
    article_title: str,
    article_content: str,
) -> str:
    """
    SLM???ъ슜???ъ슜???낅젰 + 湲곗궗 ?댁슜?쇰줈遺???듭떖 二쇱옣 1臾몄옣??異붿텧.
    ?ㅽ뙣 ??fallback ?꾨왂 ?곸슜.
    """
    system_prompt = load_system_prompt()
    content_snippet = article_content[:MAX_CONTENT_LENGTH] if article_content else ""

    user_prompt = f"""[?ъ슜???낅젰]: {user_input}
[湲곗궗 ?쒕ぉ]: {article_title}
[湲곗궗 蹂몃Ц(?쇰?)]: {content_snippet}

???댁슜??諛뷀깢?쇰줈 '寃利앺빐?????듭떖 二쇱옣' ??臾몄옣???묒꽦?섎씪."""

    try:
        response = call_slm1(system_prompt, user_prompt)
        claim = response.strip().strip('"').strip("'")
        if claim:
            return claim
    except SLMError as e:
        logger.warning(f"LLM ?뺢퇋???ㅽ뙣: {e}")

    # Fallback: 湲곗궗 ?쒕ぉ > ?ъ슜???낅젰 > 湲곕낯媛?
    if article_title:
        return article_title
    if user_input:
        # 湲곕낯 ?뺢퇋?? 怨듬갚 ?뺣━
        return re.sub(r'\s+', ' ', user_input).strip()
    return "?뺤씤?????녿뒗 二쇱옣"


# ---------------------------------------------------------------------------
# 湲곕낯 ?뺢퇋??(LLM 遺덊븘?뷀븳 寃쎌슦)
# ---------------------------------------------------------------------------

def normalize_text_basic(text: str) -> str:
    """湲곕낯 ?띿뒪???뺢퇋??(怨듬갚, 以꾨컮轅??뺣━)."""
    normalized = text.strip()
    normalized = re.sub(r'\s+', ' ', normalized)
    return normalized


# ---------------------------------------------------------------------------
# 硫붿씤 ?ㅽ뻾
# ---------------------------------------------------------------------------

def run(state: dict) -> dict:
    """
    Stage 1 ?ㅽ뻾: ?낅젰 ?뺢퇋??

    TruthCheckRequest 湲곕컲 state瑜?諛쏆븘
    claim_text, language, canonical_evidence, entity_map???ㅼ젙?⑸땲??
    """
    trace_id = state.get("trace_id", "unknown")
    input_type = state.get("input_type", "text")
    input_payload = state.get("input_payload", "")
    user_request = state.get("user_request", "")
    language = state.get("language", DEFAULT_LANGUAGE)

    logger.info(f"[{trace_id}] Stage1 ?쒖옉: type={input_type}, payload={input_payload[:80]}...")

    try:
        # ?? 1. ?낅젰 遺꾨쪟 諛?URL 異붿텧 ??
        raw_text = input_payload
        url = ""

        if input_type == "url":
            url = input_payload
        else:
            # ?띿뒪?몄뿉??URL ?먮룞 異붿텧
            url = extract_url_from_text(raw_text)

        # user_request媛 ?덉쑝硫??ъ슜?먯쓽 ?먮옒 ?섎룄
        snippet = user_request or raw_text

        # ?? 2. URL 泥섎━ ??
        url_info = normalize_url(url)
        fetched = {"text": "", "title": ""}

        if url_info["is_valid"]:
            fetched = fetch_url_content(url_info["normalized_url"])
            logger.info(
                f"[{trace_id}] URL 肄섑뀗痢? {len(fetched['text'])} chars, "
                f"?쒕ぉ: {fetched['title'][:50]}"
            )

        # ?? 3. 二쇱옣 ?뺢퇋????
        normalize_mode = (state.get("normalize_mode") or "llm").lower()
        if normalize_mode == "basic":
            claim_text = normalize_text_basic(snippet) or normalize_text_basic(fetched["title"]) or "?뺤씤?????녿뒗 二쇱옣"
            logger.info(f"[{trace_id}] 湲곕낯 ?뺢퇋???ъ슜")
        else:
            claim_text = normalize_claim_with_llm(
                user_input=snippet,
                article_title=fetched["title"],
                article_content=fetched["text"],
            )
        logger.info(f"[{trace_id}] ?뺢퇋?붾맂 二쇱옣: {claim_text[:80]}")

        # ?? 4. 遺媛 ?뺣낫 異붿텧 ??
        target_text = snippet if snippet else fetched["text"]
        detected_lang = detect_language(claim_text)
        temporal = extract_temporal_info(target_text)
        entities = extract_entities(claim_text)

        # ?? 5. State ?낅뜲?댄듃 ??
        state["claim_text"] = claim_text
        state["language"] = language or detected_lang

        state["canonical_evidence"] = {
            "snippet": snippet,
            "fetched_content": fetched["text"],
            "article_title": fetched["title"],
            "source_url": url_info["normalized_url"],
            "url_valid": url_info["is_valid"],
            "domain": url_info["domain"],
            "temporal_context": temporal,
            "detected_language": detected_lang,
        }

        state["entity_map"] = {
            "extracted": entities,
            "count": len(entities),
        }

        logger.info(
            f"[{trace_id}] Stage1 ?꾨즺: claim={claim_text[:50]}..., "
            f"lang={state['language']}, entities={len(entities)}"
        )

    except Exception as e:
        logger.exception(f"[{trace_id}] Stage1 ?ㅻ쪟: {e}")
        # ?먮윭 ?쒖뿉???뚯씠?꾨씪?몄씠 怨꾩냽 吏꾪뻾?????덈룄濡?湲곕낯媛??ㅼ젙
        state["claim_text"] = normalize_text_basic(input_payload) or "?뺤씤?????녿뒗 二쇱옣"
        state["language"] = language or DEFAULT_LANGUAGE
        state["canonical_evidence"] = {}
        state["entity_map"] = {"extracted": [], "count": 0}

    return state

