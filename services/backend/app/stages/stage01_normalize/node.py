import re
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Literal
from urllib.parse import urlparse, urlunparse
from functools import lru_cache

from app.stages._shared.slm_client import call_slm1, SLMError
from app.services.url_prefetcher import prefetch_url

logger = logging.getLogger(__name__)

# 프롬프트 파일 경로
PROMPT_FILE = Path(__file__).parent / "prompt_normalize.txt"

# 설정
DEFAULT_LANGUAGE = "ko"
MAX_CONTENT_LENGTH = None


@lru_cache(maxsize=1)
def load_system_prompt() -> str:
    """시스템 프롬프트 로드 (캐싱)."""
    return PROMPT_FILE.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# URL 처리
# ---------------------------------------------------------------------------

def extract_url_from_text(text: str) -> str:
    """텍스트에서 첫 번째 URL 추출."""
    match = re.search(r'https?://[^\s<>"\')\]]+', text)
    return match.group(0) if match else ""


def normalize_url(url: str) -> Dict[str, Any]:
    """URL 파싱 및 정규화."""
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
        logger.warning(f"URL 파싱 실패: {e}")
        return {"normalized_url": url, "is_valid": False, "domain": ""}


# ---------------------------------------------------------------------------
# 텍스트 분석 유틸리티
# ---------------------------------------------------------------------------

def extract_entities(text: str) -> List[str]:
    """간이 엔티티 추출 (고유명사 후보)."""
    if not text:
        return []
    words = text.split()
    entities = []
    for w in words:
        w_clean = w.strip(".,!?\"'()[]")
        if len(w_clean) <= 1:
            continue
        # 영문 대문자 시작 또는 한글
        if w_clean[0].isupper() or ('\uAC00' <= w_clean[0] <= '\uD7A3'):
            entities.append(w_clean)
    return list(set(entities))[:10]


# ---------------------------------------------------------------------------
# LLM 기반 주장 정규화
# ---------------------------------------------------------------------------

from app.stages._shared.guardrails import parse_json_safe
from app.orchestrator.schemas.normalization import NormalizedClaim

_META_CLAIM_MARKERS = (
    "소문",
    "루머",
    "의혹",
    "논란",
    "가능성",
    "추정",
    "추측",
    "풍문",
    "카더라",
    "낚시",
    "가짜뉴스",
    "허위",
)


def _select_primary_claim(normalize_claims: Any) -> str:
    """
    Stage1이 추출한 claims(기사 문장 그대로)를 기반으로,
    downstream(증거 검색/판정)이 실제로 검증할 "원자적 주장" 1개를 고른다.

    기존 claim_text는 2~3문장 내러티브 요약이라,
    'OOO 사망설이 퍼지고 있다' 같은 메타 서술이 TRUE로 판정되는 오탐을 유발할 수 있다.
    """
    if not isinstance(normalize_claims, list):
        return ""

    best_text = ""
    best_score = -10_000

    for item in normalize_claims:
        if not isinstance(item, dict):
            continue
        text = item.get("주장") or item.get("claim") or item.get("text") or ""
        if not isinstance(text, str):
            continue
        text = text.strip()
        if len(text) < 6:
            continue

        claim_type = (item.get("claim_type") or "").strip()

        score = len(text)
        if any(ch.isdigit() for ch in text):
            score += 30
        if claim_type in {"사건", "통계", "정책", "인용"}:
            score += 10
        if claim_type == "논리":
            score -= 10

        # 메타/전달/루머 서술은 검증 대상 주장으로 부적합한 경우가 많아 페널티.
        lowered = text.lower()
        if any(marker in lowered for marker in _META_CLAIM_MARKERS):
            score -= 25

        if score > best_score:
            best_score = score
            best_text = text

    return best_text

def split_sentences(text: str) -> List[str]:
    if not text:
        return []
    # 간단한 문장 분리 (한글/영문 혼합 대응)
    raw = re.split(r'(?<=[.!?。！？])\s+|\n+', text.strip())
    sentences = []
    for s in raw:
        s_clean = s.strip()
        if s_clean:
            sentences.append(s_clean)
    return sentences

def build_normalize_user_prompt(
    user_input: str,
    article_title: str,
    article_content: str,
) -> str:
    sentences = split_sentences(article_content)
    sentences_block = "\n".join([f"- {s}" for s in sentences]) if sentences else "- (문장 없음)"
    return f"""[사용자 입력]: {user_input}
[기사 제목]: {article_title}
[SENTENCES]
{sentences_block}

위 내용을 바탕으로 JSON 포맷의 출력을 생성하세요."""


def normalize_claim_with_llm(
    user_input: str,
    article_title: str,
    article_content: str,
) -> tuple[NormalizedClaim, str, Optional[dict]]:
    """
    SLM을 사용해 사용자 입력 + 기사 내용으로부터 정규화된 주장 및 의도를 추출.
    """
    system_prompt = load_system_prompt()
    user_prompt = build_normalize_user_prompt(
        user_input=user_input,
        article_title=article_title,
        article_content=article_content,
    )

    try:
        response = call_slm1(system_prompt, user_prompt)
        parsed = parse_json_safe(response)
        
        if parsed:
            # Pydantic validation
            try:
                if parsed.get("original_intent") not in {"verification", "exploration"}:
                    parsed["original_intent"] = "verification"
                return NormalizedClaim(**parsed), response, parsed
            except Exception as e:
                logger.warning(f"NormalizedClaim 파싱 실패: {e}, raw={parsed}")
                # Fallback to loose dictionary if schema mismatch, or fix fields
                intent_raw = parsed.get("original_intent")
                intent: Literal["verification", "exploration"] = (
                    "exploration" if intent_raw == "exploration" else "verification"
                )
                return NormalizedClaim(
                    claim_text=parsed.get("claim_text") or article_title or user_input,
                    original_intent=intent,
                    key_entities=parsed.get("key_entities", [])
                ), response, parsed
    except SLMError as e:
        logger.warning(f"LLM 정규화 실패: {e}")

    # Fallback
    fallback_text = article_title or re.sub(r'\s+', ' ', user_input).strip() or "확인할 수 없는 주장"
    return NormalizedClaim(
        claim_text=fallback_text,
        original_intent="verification", # Default assumption
        key_entities=extract_entities(fallback_text) # Regex fallback
    ), "", None


# ---------------------------------------------------------------------------
# 기본 정규화 (LLM 불필요한 경우)
# ---------------------------------------------------------------------------

def normalize_text_basic(text: str) -> str:
    """기본 텍스트 정규화 (공백, 줄바꿈 정리)."""
    normalized = text.strip()
    normalized = re.sub(r'\s+', ' ', normalized)
    return normalized


# ---------------------------------------------------------------------------
# 메인 실행
# ---------------------------------------------------------------------------

def run(state: dict) -> dict:
    """
    Stage 1 실행: 입력 정규화.

    TruthCheckRequest 기반 state를 받아
    claim_text, language, canonical_evidence, entity_map을 설정합니다.
    """
    trace_id = state.get("trace_id", "unknown")
    input_type = state.get("input_type", "text")
    input_payload = state.get("input_payload", "")
    user_request = state.get("user_request", "")
    language = state.get("language", DEFAULT_LANGUAGE)

    logger.info(f"[{trace_id}] Stage1 시작: type={input_type}, payload={input_payload[:80]}...")

    try:
        # ── 1. 입력 분류 및 URL 추출 ──
        raw_text = input_payload
        url = ""

        if input_type == "url":
            url = input_payload
        else:
            # 텍스트에서 URL 자동 추출
            url = extract_url_from_text(raw_text)

        # user_request가 있으면 사용자의 원래 의도
        snippet = user_request or raw_text

        # ── 2. URL 처리 ──
        url_info = normalize_url(url)
        fetched = {"text": "", "title": ""}
        source_type = ""

        if url_info["is_valid"]:
            allow_youtube = input_type == "url"
            prefetched = prefetch_url(url_info["normalized_url"], allow_youtube=allow_youtube)
            fetched = {
                "text": prefetched.get("text", ""),
                "title": prefetched.get("title", ""),
            }
            source_type = prefetched.get("source_type", "")
            logger.info(
                f"[{trace_id}] URL 콘텐츠: {len(fetched['text'])} chars, "
                f"제목: {fetched['title'][:100]}"
            )
            
            # 2-1. Snippet 보정: 입력이 단순 URL인 경우, snippet을 기사 제목으로 대체
            # (UI나 다운스트림에서 snippet이 URL로 보이는 문제 해결)
            if not user_request and fetched["title"]:
                snippet = fetched["title"]
                logger.info(f"[{trace_id}] Snippet을 URL에서 제목으로 대체: {snippet[:50]}...")

        # ── 3. 주장 정규화 ──
        normalize_mode = (state.get("normalize_mode") or "llm").lower()
        if normalize_mode == "basic":
            normalized_obj = NormalizedClaim(
                claim_text=normalize_text_basic(snippet) or normalize_text_basic(fetched["title"]) or "확인할 수 없는 주장",
                original_intent="verification",
                key_entities=extract_entities(snippet)
            )
            logger.info(f"[{trace_id}] 기본 정규화 사용")
        else:
            system_prompt = load_system_prompt()
            user_prompt = build_normalize_user_prompt(
                user_input=snippet,
                article_title=fetched["title"],
                article_content=fetched["text"],
            )
            state["prompt_normalize_system"] = system_prompt
            state["prompt_normalize_user"] = user_prompt
            normalized_obj, slm_raw, parsed = normalize_claim_with_llm(
                user_input=snippet,
                article_title=fetched["title"],
                article_content=fetched["text"],
            )
            state["slm_raw_normalize"] = slm_raw
            if parsed and isinstance(parsed.get("claims"), list):
                state["normalize_claims"] = parsed.get("claims")
        
        claim_text = normalized_obj.claim_text
        logger.info(f"[{trace_id}] 정규화된 주장: {claim_text[:150]} (의도: {normalized_obj.original_intent})")

        # ── 4. 부가 정보 추출 ──
        # Use LLM extracted entities if available
        entities = normalized_obj.key_entities or []

        # ── 5. State 업데이트 ──
        state["claim_text"] = claim_text
        # URL/기사 입력일 때는 "내러티브 요약"이 아니라 "기사 문장 그대로의 주장"을 1개 선택해 검증한다.
        # (요약 내러티브는 사실 여부 판정 대상이 아니라 주제 설명에 가까운 경우가 많음)
        if url_info.get("is_valid") and state.get("normalize_claims"):
            primary = _select_primary_claim(state.get("normalize_claims"))
            if primary:
                state["claim_text_narrative"] = claim_text
                state["claim_text"] = primary
                logger.info(f"[{trace_id}] 검증 대상 claim_text를 primary claim으로 설정: {primary[:150]}")
        state["original_intent"] = normalized_obj.original_intent # New State Field
        state["language"] = language or DEFAULT_LANGUAGE

        state["canonical_evidence"] = {
            "snippet": snippet,
            "fetched_content": fetched["text"],
            "article_title": fetched["title"],
            "source_url": url_info["normalized_url"],
            "url_valid": url_info["is_valid"],
            "domain": url_info["domain"],
            "source_type": source_type,
        }

        state["entity_map"] = {
            "extracted": entities,
            "count": len(entities),
        }

        logger.info(
            f"[{trace_id}] Stage1 완료: claim={claim_text[:150]}..., "
            f"lang={state['language']}, entities={len(entities)}"
        )

    except Exception as e:
        logger.exception(f"[{trace_id}] Stage1 오류: {e}")
        # 에러 시에도 파이프라인이 계속 진행될 수 있도록 기본값 설정
        state["claim_text"] = normalize_text_basic(input_payload) or "확인할 수 없는 주장"
        state["language"] = language or DEFAULT_LANGUAGE
        state["canonical_evidence"] = {}
        state["entity_map"] = {"extracted": [], "count": 0}

    return state
