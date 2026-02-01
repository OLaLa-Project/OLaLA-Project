"""
Stage 6 - Supportive Verification (吏吏 愿??寃利?

二쇱옣??吏吏?섎뒗 愿?먯뿉??利앷굅瑜?遺꾩꽍?⑸땲??
SLM???몄텧?섏뿬 DraftVerdict瑜??앹꽦?⑸땲??

Input state keys:
    - trace_id: str
    - claim_text: str
    - language: "ko" | "en" (default: "ko")
    - evidence_topk: list[dict] (evid_id, title, url, snippet, source_type)

Output state keys:
    - verdict_support: DraftVerdict dict
"""

import logging
from pathlib import Path
from functools import lru_cache

from app.stages._shared.slm_client import call_slm2, SLMError
from app.stages._shared.guardrails import (
    parse_json_with_retry,
    build_draft_verdict,
    JSONParseError,
)

logger = logging.getLogger(__name__)

# ?꾨＼?꾪듃 ?뚯씪 寃쎈줈
PROMPT_FILE = Path(__file__).parent / "prompt_supportive.txt"

# MVP ?ㅼ젙
MAX_SNIPPET_LENGTH = 500
DEFAULT_LANGUAGE = "ko"


@lru_cache(maxsize=1)
def load_system_prompt() -> str:
    """?쒖뒪???꾨＼?꾪듃 濡쒕뱶 (罹먯떛)."""
    return PROMPT_FILE.read_text(encoding="utf-8")


def truncate_snippet(snippet: str, max_length: int = MAX_SNIPPET_LENGTH) -> str:
    """snippet??理쒕? 湲몄씠濡??먮Ⅴ湲?"""
    if len(snippet) <= max_length:
        return snippet
    return snippet[:max_length] + "..."


def format_evidence_for_prompt(evidence_topk: list[dict]) -> str:
    """利앷굅 由ъ뒪?몃? ?꾨＼?꾪듃???띿뒪?몃줈 ?щ㎎."""
    if not evidence_topk:
        return "(利앷굅 ?놁쓬)"

    lines = []
    for i, ev in enumerate(evidence_topk, 1):
        evid_id = ev.get("evid_id", f"ev_{i}")
        title = ev.get("title", "?쒕ぉ ?놁쓬")
        url = ev.get("url", "")
        # snippet ?곗꽑, ?놁쑝硫?content ?ъ슜 (?섏쐞 ?명솚??
        text_content = ev.get("snippet") or ev.get("content", "")
        snippet = truncate_snippet(text_content)
        source_type = ev.get("source_type", "WEB_URL")

        lines.append(f"[{evid_id}] ({source_type}) {title}")
        if url:
            lines.append(f"    URL: {url}")
        lines.append(f"    ?댁슜: {snippet}")
        lines.append("")

    return "\n".join(lines)


def build_user_prompt(claim_text: str, evidence_topk: list[dict], language: str) -> str:
    """?ъ슜???꾨＼?꾪듃 ?앹꽦."""
    evidence_text = format_evidence_for_prompt(evidence_topk)

    return f"""## 寃利앺븷 二쇱옣
{claim_text}

## ?섏쭛??利앷굅
{evidence_text}

## ?붿껌
??利앷굅瑜?諛뷀깢?쇰줈 二쇱옣??**吏吏?섎뒗 愿??*?먯꽌 遺꾩꽍?섍퀬, 吏?뺣맂 JSON ?뺤떇?쇰줈 寃곌낵瑜?異쒕젰?섏꽭??
?몄뼱: {language}
"""


def create_fallback_verdict(reason: str) -> dict:
    """SLM ?몄텧 ?ㅽ뙣 ??fallback verdict ?앹꽦."""
    return {
        "stance": "UNVERIFIED",
        "confidence": 0.0,
        "reasoning_bullets": [f"[?쒖뒪???ㅻ쪟] {reason}"],
        "citations": [],
        "weak_points": ["SLM ?몄텧 ?ㅽ뙣濡?遺꾩꽍 遺덇?"],
        "followup_queries": [],
    }


def run(state: dict) -> dict:
    """
    Stage 6 ?ㅽ뻾: 吏吏 愿??寃利?

    Args:
        state: ?뚯씠?꾨씪???곹깭 dict

    Returns:
        verdict_support媛 異붽???state
    """
    trace_id = state.get("trace_id", "unknown")
    claim_text = state.get("claim_text", "")
    language = state.get("language", DEFAULT_LANGUAGE)
    evidence_topk = state.get("evidence_topk", [])

    logger.info(f"[{trace_id}] Stage6 ?쒖옉: claim={claim_text[:50]}...")

    # 利앷굅媛 ?놁쑝硫?諛붾줈 UNVERIFIED
    if not evidence_topk:
        logger.warning(f"[{trace_id}] 利앷굅 ?놁쓬, UNVERIFIED 諛섑솚")
        state["verdict_support"] = create_fallback_verdict("利앷굅媛 ?쒓났?섏? ?딆쓬")
        return state

    # ?꾨＼?꾪듃 以鍮?
    system_prompt = load_system_prompt()
    user_prompt = build_user_prompt(claim_text, evidence_topk, language)

    # SLM ?몄텧 ?⑥닔
    def call_fn():
        return call_slm2(system_prompt, user_prompt)

    def retry_call_fn(retry_prompt: str):
        combined_prompt = f"{system_prompt}\n\n{retry_prompt}"
        return call_slm2(combined_prompt, user_prompt)

    try:
        # JSON ?뚯떛 with ?ъ떆??
        raw_verdict = parse_json_with_retry(call_fn, retry_call_fn=retry_call_fn)

        # ?뺢퇋??諛?寃利?
        verdict = build_draft_verdict(raw_verdict, evidence_topk)

        logger.info(
            f"[{trace_id}] Stage6 ?꾨즺: stance={verdict['stance']}, "
            f"confidence={verdict['confidence']:.2f}, "
            f"citations={len(verdict['citations'])}"
        )

    except JSONParseError as e:
        logger.error(f"[{trace_id}] JSON ?뚯떛 理쒖쥌 ?ㅽ뙣: {e}")
        verdict = create_fallback_verdict(f"JSON ?뚯떛 ?ㅽ뙣: {e}")

    except SLMError as e:
        logger.error(f"[{trace_id}] SLM ?몄텧 ?ㅽ뙣: {e}")
        verdict = create_fallback_verdict(f"SLM ?몄텧 ?ㅽ뙣: {e}")

    except Exception as e:
        logger.exception(f"[{trace_id}] ?덉긽移?紐삵븳 ?ㅻ쪟: {e}")
        verdict = create_fallback_verdict(f"?대? ?ㅻ쪟: {e}")

    state["verdict_support"] = verdict
    return state

