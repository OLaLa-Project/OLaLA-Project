import re
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Literal
from urllib.parse import urlparse, urlunparse
from functools import lru_cache
from difflib import SequenceMatcher

from app.stages._shared.slm_client import call_slm1, SLMError
from app.services.url_prefetcher import prefetch_url

logger = logging.getLogger(__name__)

# 프롬프트 파일 경로
PROMPT_FILE = Path(__file__).parent / "prompt_normalize.txt"

# 설정
DEFAULT_LANGUAGE = "ko"
MAX_CONTENT_LENGTH = None
_VALID_CLAIM_TYPES = {"사건", "논리", "통계", "인용", "정책"}
_VALID_CLAIM_MODES = {"fact", "rumor", "mixed"}
_VALID_VERIFICATION_PRIORITIES = {"high", "normal"}
_RISK_MARKER_PATTERNS = [
    "설",
    "카더라",
    "익명 제보",
    "라고 알려졌다",
    "확인되지 않았다",
    "미확인",
    "단독 주장",
]


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


def _normalize_original_intent(value: Any) -> Literal["verification", "exploration"]:
    raw = str(value or "").strip().lower()
    if raw == "exploration":
        return "exploration"
    if raw == "verification":
        return "verification"
    # LLM이 "verification | exploration"처럼 스키마 문구를 그대로 반환하는 경우 방어
    if "exploration" in raw and "verification" not in raw:
        return "exploration"
    return "verification"


def _normalize_claim_type(value: Any) -> Optional[str]:
    if not isinstance(value, str):
        return None
    for token in re.split(r"[|,/]", value):
        claim_type = token.strip()
        if claim_type in _VALID_CLAIM_TYPES:
            return claim_type
    return None


def _normalize_for_similarity(text: str) -> str:
    source = re.sub(r"\s+", " ", str(text or "").strip().lower())
    return re.sub(r"[^0-9a-zA-Z가-힣]", "", source)


def _claim_similarity(left: str, right: str) -> float:
    left_norm = _normalize_for_similarity(left)
    right_norm = _normalize_for_similarity(right)
    if not left_norm or not right_norm:
        return 0.0
    return SequenceMatcher(None, left_norm, right_norm).ratio()


def _pick_farthest_sentence(existing_claims: List[Dict[str, Any]], article_sentences: List[str]) -> str:
    if not existing_claims or not article_sentences:
        return ""

    existing_texts = [str(item.get("주장") or "").strip() for item in existing_claims if str(item.get("주장") or "").strip()]
    if not existing_texts:
        return ""

    best_sentence = ""
    best_distance = -1.0
    for sentence in article_sentences:
        candidate = str(sentence or "").strip()
        if len(candidate) < 8:
            continue
        max_similarity = max((_claim_similarity(candidate, text) for text in existing_texts), default=0.0)
        distance = 1.0 - max_similarity
        if distance > best_distance:
            best_distance = distance
            best_sentence = candidate
    return best_sentence


def _sanitize_claims(raw_claims: Any, article_sentences: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    if not isinstance(raw_claims, list):
        return []

    cleaned: List[Dict[str, Any]] = []
    for item in raw_claims:
        if not isinstance(item, dict):
            continue
        text = item.get("주장") or item.get("claim") or item.get("text") or ""
        text = str(text).strip()
        if not text:
            continue

        is_duplicate = False
        for existing in cleaned:
            existing_text = str(existing.get("주장") or "").strip()
            if _claim_similarity(text, existing_text) >= 0.90:
                is_duplicate = True
                break
        if is_duplicate:
            continue

        claim_id = f"C{len(cleaned) + 1}"
        claim: Dict[str, Any] = {
            "claim_id": claim_id,
            "주장": text,
        }
        claim_type = _normalize_claim_type(item.get("claim_type"))
        if claim_type:
            claim["claim_type"] = claim_type
        cleaned.append(claim)
        if len(cleaned) >= 2:
            break

    if len(cleaned) == 1 and isinstance(article_sentences, list):
        supplement = _pick_farthest_sentence(cleaned, article_sentences)
        if supplement and _claim_similarity(supplement, str(cleaned[0].get("주장") or "")) < 0.85:
            cleaned.append(
                {
                    "claim_id": "C2",
                    "주장": supplement,
                    "claim_type": "논리",
                }
            )

    for idx, claim in enumerate(cleaned, start=1):
        claim["claim_id"] = f"C{idx}"

    return cleaned


def _extract_risk_markers(text: str) -> List[str]:
    source = str(text or "")
    if not source:
        return []
    markers: List[str] = []
    for pattern in _RISK_MARKER_PATTERNS:
        if pattern in source and pattern not in markers:
            markers.append(pattern)
    return markers


def _sanitize_risk_markers(value: Any) -> List[str]:
    if isinstance(value, str):
        raw = [token.strip() for token in re.split(r"[,\n|/]", value) if token.strip()]
    elif isinstance(value, list):
        raw = [str(token).strip() for token in value if isinstance(token, str) and token.strip()]
    else:
        return []

    seen: set[str] = set()
    cleaned: List[str] = []
    for token in raw:
        if token not in seen:
            seen.add(token)
            cleaned.append(token)
    return cleaned[:10]


def _normalize_claim_mode(value: Any, context_text: str = "") -> Literal["fact", "rumor", "mixed"]:
    raw = str(value or "").strip().lower()
    if raw in _VALID_CLAIM_MODES:
        return raw  # type: ignore[return-value]

    tokens = [token.strip() for token in re.split(r"[|,/]", raw) if token.strip()]
    token_set = set(tokens)
    if {"fact", "rumor"}.issubset(token_set) or {"fact", "mixed"}.issubset(token_set):
        return "mixed"
    if "rumor" in token_set:
        return "rumor"
    if "mixed" in token_set:
        return "mixed"
    if "fact" in token_set:
        return "fact"

    inferred = _extract_risk_markers(context_text)
    if inferred:
        return "rumor"
    return "fact"


def _normalize_verification_priority(value: Any, claim_mode: str) -> Literal["high", "normal"]:
    raw = str(value or "").strip().lower()
    if raw in _VALID_VERIFICATION_PRIORITIES:
        priority = raw
    else:
        priority = "high" if claim_mode in {"rumor", "mixed"} else "normal"
    if claim_mode in {"rumor", "mixed"}:
        return "high"
    return "normal" if priority != "high" else "high"

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
                parsed["original_intent"] = _normalize_original_intent(parsed.get("original_intent"))
                return NormalizedClaim(**parsed), response, parsed
            except Exception as e:
                logger.warning(f"NormalizedClaim 파싱 실패: {e}, raw={parsed}")
                # Fallback to loose dictionary if schema mismatch, or fix fields
                intent = _normalize_original_intent(parsed.get("original_intent"))
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
    state["claim_mode"] = "fact"
    state["risk_markers"] = []
    state["verification_priority"] = "normal"

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
        state["normalize_claims"] = []
        parsed: Optional[dict[str, Any]] = None
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
            if parsed:
                state["normalize_claims"] = _sanitize_claims(
                    parsed.get("claims"),
                    split_sentences(fetched["text"]),
                )
        
        claim_text = normalized_obj.claim_text
        logger.info(f"[{trace_id}] 정규화된 주장: {claim_text[:150]} (의도: {normalized_obj.original_intent})")

        # ── 4. 부가 정보 추출 ──
        # Use LLM extracted entities if available
        entities = normalized_obj.key_entities or []

        # ── 5. State 업데이트 ──
        raw_claim_mode = parsed.get("claim_mode") if isinstance(parsed, dict) else None
        risk_markers = _sanitize_risk_markers(parsed.get("risk_markers")) if isinstance(parsed, dict) else []
        if not risk_markers:
            risk_markers = _extract_risk_markers(
                " ".join(
                    [
                        snippet or "",
                        fetched["title"] or "",
                        fetched["text"][:1200] if fetched["text"] else "",
                        claim_text or "",
                    ]
                )
            )
        claim_mode = _normalize_claim_mode(raw_claim_mode, context_text=" ".join([claim_text, *risk_markers]))
        if claim_mode == "fact" and risk_markers:
            claim_mode = "mixed"
        verification_priority = _normalize_verification_priority(
            parsed.get("verification_priority") if isinstance(parsed, dict) else None,
            claim_mode,
        )

        state["claim_text"] = claim_text
        state["original_intent"] = normalized_obj.original_intent # New State Field
        state["claim_mode"] = claim_mode
        state["risk_markers"] = risk_markers
        state["verification_priority"] = verification_priority
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
            f"lang={state['language']}, entities={len(entities)}, "
            f"claim_mode={claim_mode}, verification_priority={verification_priority}"
        )

    except Exception as e:
        logger.exception(f"[{trace_id}] Stage1 오류: {e}")
        # 에러 시에도 파이프라인이 계속 진행될 수 있도록 기본값 설정
        state["claim_text"] = normalize_text_basic(input_payload) or "확인할 수 없는 주장"
        state["language"] = language or DEFAULT_LANGUAGE
        state["canonical_evidence"] = {}
        state["entity_map"] = {"extracted": [], "count": 0}
        state["normalize_claims"] = []
        state["claim_mode"] = "fact"
        state["risk_markers"] = []
        state["verification_priority"] = "normal"

    return state
