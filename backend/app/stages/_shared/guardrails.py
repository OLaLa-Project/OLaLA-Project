"""
Guardrails for SLM2 stages.

주요 기능:
1. JSON 파싱 실패 시 1회 재요청
2. citations.quote substring 검증
3. citations==0이면 UNVERIFIED 강제
"""

import json
import re
import logging
from difflib import SequenceMatcher
from typing import Any, Callable, Optional, cast

from app.core.settings import settings

logger = logging.getLogger(__name__)

# MVP 설정
MAX_JSON_RETRY = 1
VALID_STANCES = {"TRUE", "FALSE", "MIXED", "UNVERIFIED"}


def extract_json_from_text(text: str) -> str:
    """
    텍스트에서 JSON 블록 추출.

    마크다운 코드블록(```json ... ```) 또는 { } 블록을 찾음.
    """
    # 마크다운 코드블록에서 추출
    code_block_match = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", text)
    if code_block_match:
        return code_block_match.group(1)

    # 순수 JSON 블록 추출 (첫 번째 { 부터 마지막 } 까지)
    first_brace = text.find("{")
    last_brace = text.rfind("}")
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        return text[first_brace : last_brace + 1]

    return text


def normalize_json_text(text: str) -> str:
    """
    JSON 파싱을 돕기 위한 최소 정규화.
    - 코드블록/잡문 제거는 extract_json_from_text에서 처리됨
    - 유효하지 않은 escape를 이스케이프 처리(문자 손실 방지)
    - 제어문자 제거 (탭/개행/캐리지리턴 제외)
    """
    # 제어문자 제거 (JSON에 허용되지 않는 범위)
    cleaned = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F]", "", text)

    # 유효하지 않은 escape: \" \\ \/ \b \f \n \r \t \uXXXX 외는 \\로 치환
    cleaned = re.sub(r"\\(?![\"\\/bfnrtu])", r"\\\\", cleaned)

    # 끝에 남은 단일 백슬래시 처리
    if cleaned.endswith("\\"):
        cleaned = cleaned[:-1] + "\\\\"

    return cleaned


def _extract_json_array_body(text: str, key: str) -> str:
    key_pattern = re.compile(rf'"{re.escape(key)}"\s*:', re.IGNORECASE)
    key_match = key_pattern.search(text)
    if not key_match:
        return ""

    start = text.find("[", key_match.end())
    if start < 0:
        return ""

    depth = 0
    in_string = False
    escaped = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            continue

        if ch == '"':
            in_string = True
            continue
        if ch == "[":
            depth += 1
            continue
        if ch == "]":
            depth -= 1
            if depth == 0:
                return text[start + 1 : i]

    # 배열 닫힘이 없으면 남은 텍스트를 반환(부분 복구 용도)
    return text[start + 1 :]


def _extract_json_object_body(text: str, key: str) -> str:
    key_pattern = re.compile(rf'"{re.escape(key)}"\s*:', re.IGNORECASE)
    key_match = key_pattern.search(text)
    if not key_match:
        return ""

    start = text.find("{", key_match.end())
    if start < 0:
        return ""

    depth = 0
    in_string = False
    escaped = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            continue

        if ch == '"':
            in_string = True
            continue
        if ch == "{":
            depth += 1
            continue
        if ch == "}":
            depth -= 1
            if depth == 0:
                return text[start + 1 : i]

    return text[start + 1 :]


def _extract_json_string_field(text: str, key: str) -> str:
    pattern = re.compile(rf'"{re.escape(key)}"\s*:\s*"((?:\\.|[^"\\])*)"', re.IGNORECASE)
    match = pattern.search(text)
    if not match:
        return ""
    token = match.group(1)
    try:
        return cast(str, json.loads(f'"{token}"'))
    except json.JSONDecodeError:
        return token.replace('\\"', '"').replace("\\n", "\n")


def _extract_json_number_field(text: str, key: str) -> Optional[float]:
    pattern = re.compile(rf'"{re.escape(key)}"\s*:\s*(-?\d+(?:\.\d+)?)', re.IGNORECASE)
    match = pattern.search(text)
    if not match:
        return None
    try:
        return float(match.group(1))
    except ValueError:
        return None


def _extract_json_string_list(text: str, key: str, max_items: int = 2) -> list[str]:
    body = _extract_json_array_body(text, key)
    if not body:
        return []
    items = []
    for token in re.findall(r'"((?:\\.|[^"\\])*)"', body):
        try:
            value = cast(str, json.loads(f'"{token}"')).strip()
        except json.JSONDecodeError:
            value = token.strip()
        if not value:
            continue
        items.append(value)
        if len(items) >= max_items:
            break
    return items


def recover_partial_draft_verdict(text: str) -> dict[str, Any]:
    """
    잘린/불완전 JSON에서 DraftVerdict 핵심 필드를 최대한 복구.

    Stage6/7에서 parse_json_safe 실패 후 보조 경로로 사용한다.
    """
    source = (text or "").strip()
    if not source:
        return {}

    recovered: dict[str, Any] = {}

    stance = _extract_json_string_field(source, "stance").upper().strip()
    if stance in VALID_STANCES:
        recovered["stance"] = stance

    confidence = _extract_json_number_field(source, "confidence")
    if confidence is not None:
        recovered["confidence"] = confidence

    reasoning = _extract_json_string_list(source, "reasoning_bullets", max_items=2)
    if reasoning:
        recovered["reasoning_bullets"] = reasoning

    citation_obj = _extract_json_object_body(source, "citations")
    citations: list[dict[str, Any]] = []
    if citation_obj:
        evid_id = _extract_json_string_field(citation_obj, "evid_id")
        url = _extract_json_string_field(citation_obj, "url")
        quote = _extract_json_string_field(citation_obj, "quote")
        title = _extract_json_string_field(citation_obj, "title")
        if evid_id or url or quote or title:
            citation: dict[str, Any] = {}
            if evid_id:
                citation["evid_id"] = evid_id
            if url:
                citation["url"] = url
            if quote:
                citation["quote"] = quote
            if title:
                citation["title"] = title
            citations.append(citation)
    if citations:
        recovered["citations"] = citations

    weak_points = _extract_json_string_list(source, "weak_points", max_items=2)
    if weak_points:
        recovered["weak_points"] = weak_points
    followups = _extract_json_string_list(source, "followup_queries", max_items=2)
    if followups:
        recovered["followup_queries"] = followups

    if recovered:
        recovered["_partial_recovered"] = True
    return recovered


def enrich_partial_citations_from_evidence(
    raw: dict[str, Any],
    evidence_topk: list[dict[str, Any]],
    *,
    min_quote_length: int = 10,
    quote_max_chars: int = 140,
) -> dict[str, Any]:
    """
    partial 복구 결과에서 비어있는 citation 필드를 evidence_topk로 최소 보완.
    """
    if not isinstance(raw, dict):
        return raw
    citations = raw.get("citations")
    if not isinstance(citations, list) or not citations:
        return raw

    evidence_map: dict[str, dict[str, Any]] = {}
    for ev in evidence_topk:
        evid_id = str(ev.get("evid_id") or "").strip()
        if not evid_id:
            continue
        evidence_map[evid_id] = ev

    if not evidence_map:
        return raw

    updated_citations: list[dict[str, Any]] = []
    changed = False

    for citation in citations:
        if not isinstance(citation, dict):
            continue
        item = dict(citation)
        evid_id = str(item.get("evid_id") or "").strip()
        if not evid_id or evid_id not in evidence_map:
            updated_citations.append(item)
            continue

        evidence = evidence_map[evid_id]
        snippet = str(evidence.get("snippet") or evidence.get("content") or "")
        if not item.get("url"):
            url = str(evidence.get("url") or "").strip()
            if url:
                item["url"] = url
                changed = True
        if not item.get("title"):
            title = str(evidence.get("title") or "").strip()
            if title:
                item["title"] = title
                changed = True
        quote = str(item.get("quote") or "")
        if len(quote.strip()) < min_quote_length and snippet.strip():
            item["quote"] = snippet.strip()[:quote_max_chars]
            changed = True

        updated_citations.append(item)

    if changed:
        updated = dict(raw)
        updated["citations"] = updated_citations
        return updated
    return raw


def parse_json_safe(text: str) -> Optional[dict[str, Any]]:
    """
    안전한 JSON 파싱. 실패 시 None 반환.
    """
    try:
        extracted = extract_json_from_text(text)
        parsed = json.loads(extracted)
        return parsed if isinstance(parsed, dict) else None
    except (json.JSONDecodeError, TypeError) as e:
        logger.warning(f"JSON 파싱 실패: {e}")
        # 1차 정규화 후 재시도
        try:
            normalized = normalize_json_text(extracted)
            parsed = json.loads(normalized)
            return parsed if isinstance(parsed, dict) else None
        except (json.JSONDecodeError, TypeError) as e2:
            logger.warning(f"JSON 정규화 후 파싱 실패: {e2}")
            return None


def parse_json_with_retry(
    call_fn: Callable[[], str],
    retry_system_prompt: str = "이전 응답이 올바른 JSON 형식이 아닙니다. 반드시 유효한 JSON만 출력하세요. 다른 설명 없이 JSON만 출력하세요.",
    retry_call_fn: Optional[Callable[[str], str]] = None,
    meta: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """
    JSON 파싱 (최대 1회 재시도).

    Args:
        call_fn: SLM 호출 함수 (인자 없음, 문자열 반환)
        retry_system_prompt: 재시도용 시스템 프롬프트
        retry_call_fn: 재시도 호출 함수
        meta: 파싱 진단 정보 기록용 dict

    Returns:
        파싱된 dict, 파싱 실패 시 빈 dict 반환
    """
    parse_meta = meta if isinstance(meta, dict) else {}

    response = call_fn()
    parse_meta["parse_retry_used"] = False
    parse_meta["raw_len"] = len(response or "")

    result = parse_json_safe(response)
    if result is not None:
        parse_meta["parse_ok"] = True
        return result

    should_retry = bool(settings.stage67_json_retry_enabled) and callable(retry_call_fn)
    if should_retry:
        parse_meta["parse_retry_used"] = True
        retry_response = retry_call_fn(retry_system_prompt)
        parse_meta["retry_raw_len"] = len(retry_response or "")
        retry_result = parse_json_safe(retry_response)
        if retry_result is not None:
            parse_meta["parse_ok"] = True
            return retry_result

    parse_meta["parse_ok"] = False
    logger.warning("JSON 파싱 실패, 빈 dict 반환: %s", (response or "")[:200])
    return {}


class JSONParseError(Exception):
    """JSON 파싱 실패 에러."""
    pass


def validate_citations(
    citations: list[dict],
    evidence_topk: list[dict],
    min_quote_length: int = 10,
) -> list[dict]:
    """
    citations의 quote가 evidence_topk의 snippet/content에 실제 포함되는지 검증.

    Args:
        citations: 모델이 생성한 citation 리스트
        evidence_topk: 원본 증거 리스트 (각 항목에 evid_id, snippet 또는 content 포함)
        min_quote_length: 최소 quote 길이 (너무 짧은 quote 제외)

    Returns:
        검증 통과한 citation 리스트만 반환
    """
    if not citations:
        return []

    # evidence_topk를 evid_id로 인덱싱
    # snippet과 content 모두 지원 (하위 호환성)
    evidence_map: dict[str, str] = {}
    for ev in evidence_topk:
        evid_id = ev.get("evid_id", "")
        # snippet 우선, 없으면 content 사용
        text_content = ev.get("snippet") or ev.get("content", "")
        if evid_id and text_content:
            evidence_map[evid_id] = text_content

    # evidence_map이 비어있으면 검증 불가능
    if not evidence_map:
        logger.warning("evidence_topk에서 evid_id/snippet을 찾을 수 없음")
        return []

    validated = []
    for cit in citations:
        evid_id = cit.get("evid_id", "")
        quote = cit.get("quote", "")

        # 기본 검증
        if not evid_id or not quote:
            logger.debug(f"Citation 누락 필드: evid_id={evid_id}, quote={bool(quote)}")
            continue

        if len(quote) < min_quote_length:
            logger.debug(f"Quote 너무 짧음: {len(quote)} chars")
            continue

        # evid_id가 evidence_topk에 존재하는지
        if evid_id not in evidence_map:
            logger.debug(f"evid_id 불일치: {evid_id}")
            continue

        # quote가 snippet/content의 substring인지 검증
        source_text = evidence_map[evid_id]
        # 공백/줄바꿈 정규화 후 비교
        normalized_quote = normalize_whitespace(quote)
        normalized_source = normalize_whitespace(source_text)

        if normalized_quote in normalized_source:
            validated.append(cit)
            logger.debug(f"Citation 검증 통과: evid_id={evid_id}")
        elif _soft_match_quote(normalized_quote, normalized_source):
            validated.append(cit)
            logger.info("Citation 소프트 매치 통과: evid_id=%s", evid_id)
        else:
            logger.warning(f"Quote 검증 실패: evid_id={evid_id}, quote='{quote[:50]}...'")

    logger.info(f"Citation 검증: {len(validated)}/{len(citations)} 통과")
    return validated


def recover_citations_by_evid_id(
    citations: list[dict],
    evidence_topk: list[dict],
    quote_max_chars: int = 160,
) -> list[dict]:
    """
    quote 검증이 모두 실패한 경우, evid_id 매칭 기반으로 최소 citation을 복구.

    2B 모델의 의역/문장절단으로 quote substring 검증이 실패할 때
    evid_id가 유효하면 원문 snippet 일부를 quote로 대체해 완전 UNVERIFIED 연쇄를 줄인다.
    """
    if not citations or not evidence_topk:
        return []

    evidence_map: dict[str, dict[str, Any]] = {}
    for ev in evidence_topk:
        evid_id = str(ev.get("evid_id") or "").strip()
        if evid_id:
            evidence_map[evid_id] = ev

    recovered: list[dict] = []
    for cit in citations:
        if not isinstance(cit, dict):
            continue
        evid_id = str(cit.get("evid_id") or "").strip()
        if not evid_id or evid_id not in evidence_map:
            continue

        evidence = evidence_map[evid_id]
        source_text = str(evidence.get("snippet") or evidence.get("content") or "").strip()
        if not source_text:
            continue

        recovered.append(
            {
                "evid_id": evid_id,
                "url": str(cit.get("url") or evidence.get("url") or ""),
                "title": str(cit.get("title") or evidence.get("title") or ""),
                "quote": source_text[:max(40, int(quote_max_chars))],
            }
        )

    if recovered:
        logger.warning(
            "Citation evid_id 기반 복구 적용: %d/%d",
            len(recovered),
            len(citations),
        )
    return recovered


def normalize_whitespace(text: str) -> str:
    """공백/줄바꿈 정규화."""
    return " ".join(text.split()).lower()


def _normalize_soft(text: str) -> str:
    normalized = normalize_whitespace(text)
    return re.sub(r"[^0-9a-zA-Z가-힣]", "", normalized)


def _soft_match_quote(normalized_quote: str, normalized_source: str) -> bool:
    if not settings.stage67_citation_soft_match_enabled:
        return False

    quote_soft = _normalize_soft(normalized_quote)
    source_soft = _normalize_soft(normalized_source)
    if not quote_soft or not source_soft:
        return False

    if quote_soft in source_soft:
        return True

    threshold = float(settings.stage67_citation_soft_match_threshold)
    if threshold <= 0:
        return False

    # 문장 단위로 유사도를 측정해 과도한 오탐을 줄인다.
    source_sentences = [seg for seg in re.split(r"[.!?。！？\n]+", normalized_source) if seg.strip()]
    for sentence in source_sentences:
        candidate = _normalize_soft(sentence)
        if not candidate:
            continue
        ratio = SequenceMatcher(None, quote_soft, candidate).ratio()
        if ratio >= threshold:
            return True

    return False


def enforce_unverified_if_no_citations(verdict: dict) -> dict:
    """
    citations가 비어있으면 stance를 UNVERIFIED로 강제.

    Args:
        verdict: DraftVerdict dict

    Returns:
        수정된 verdict (in-place 수정도 됨)
    """
    citations = verdict.get("citations", [])
    current_stance = verdict.get("stance", "UNVERIFIED")

    if not citations and current_stance != "UNVERIFIED":
        logger.warning(
            f"citations=0, stance 강제 변경: {current_stance} -> UNVERIFIED"
        )
        verdict["stance"] = "UNVERIFIED"
        verdict["confidence"] = 0.0
        if "reasoning_bullets" not in verdict:
            verdict["reasoning_bullets"] = []
        verdict["reasoning_bullets"].insert(
            0, "[시스템] 검증된 인용이 없어 UNVERIFIED로 처리됨"
        )

    return verdict


def validate_stance(stance: str) -> str:
    """stance 값 검증 및 정규화."""
    normalized = stance.upper().strip() if stance else "UNVERIFIED"
    if normalized not in VALID_STANCES:
        logger.warning(f"잘못된 stance '{stance}' -> UNVERIFIED로 변경")
        return "UNVERIFIED"
    return normalized


def validate_confidence(confidence: Any) -> float:
    """confidence 값 검증 (0.0 ~ 1.0)."""
    try:
        val = float(confidence)
        return max(0.0, min(1.0, val))
    except (TypeError, ValueError):
        return 0.0


def build_draft_verdict(
    raw: dict,
    evidence_topk: list[dict],
) -> dict:
    """
    모델 출력을 정규화된 DraftVerdict로 변환.

    Args:
        raw: 모델이 생성한 raw dict
        evidence_topk: 원본 증거 리스트

    Returns:
        정규화된 DraftVerdict dict
    """
    # 기본 구조
    verdict = {
        "stance": validate_stance(raw.get("stance", "UNVERIFIED")),
        "confidence": validate_confidence(raw.get("confidence", 0.0)),
        "reasoning_bullets": raw.get("reasoning_bullets", []) or [],
        "citations": [],
        "weak_points": raw.get("weak_points", []) or [],
        "followup_queries": raw.get("followup_queries", []) or [],
    }

    # citations 검증
    raw_citations = raw.get("citations", []) or []
    validated_citations = validate_citations(raw_citations, evidence_topk)
    if not validated_citations and raw_citations:
        validated_citations = recover_citations_by_evid_id(raw_citations, evidence_topk)
    verdict["citations"] = validated_citations

    # citations=0이면 UNVERIFIED 강제
    verdict = enforce_unverified_if_no_citations(verdict)

    return verdict


# ---------------------------------------------------------------------------
# Judge 전용 파서/검증 (Stage 9)
# ---------------------------------------------------------------------------

def parse_judge_json(text: str) -> dict[str, Any]:
    """
    Judge 응답 JSON 파싱 (Stage 9 전용).

    - LLMGateway._parse_json과 동일한 추출 규칙 사용
    - 파싱 실패 시 빈 dict 반환
    """
    try:
        extracted = extract_json_from_text(text)
        parsed = json.loads(extracted)
        if not isinstance(parsed, dict):
            logger.warning("Judge JSON 루트가 dict가 아님, 빈 dict 반환")
            return {}
        return cast(dict[str, Any], parsed)
    except (json.JSONDecodeError, TypeError) as e:
        logger.warning("Judge JSON 파싱 실패: %s", e)
        return {}


def parse_judge_json_with_retry(
    call_fn: Callable[[], str],
    max_retries: int = 0,
    retry_system_prompt: str = "이전 응답이 올바른 JSON 형식이 아닙니다. 반드시 유효한 JSON만 출력하세요. 다른 설명 없이 JSON만 출력하세요.",
    retry_call_fn: Optional[Callable[[str], str]] = None,
) -> dict[str, Any]:
    """
    Judge JSON 파싱 + 선택적 재시도.

    Args:
        call_fn: SLM 호출 함수
        max_retries: 재시도 횟수
        retry_system_prompt: 재시도용 시스템 프롬프트
        retry_call_fn: 재시도 호출 함수

    Returns:
        파싱된 dict, 파싱 실패 시 빈 dict 반환
    """
    response = call_fn()
    parsed = parse_judge_json(response)
    if parsed:
        return parsed

    if not callable(retry_call_fn):
        return {}

    retries = max(0, int(max_retries))
    for _ in range(retries):
        retry_response = retry_call_fn(retry_system_prompt)
        parsed = parse_judge_json(retry_response)
        if parsed:
            return parsed

    return {}


def validate_judge_output(result: dict[str, Any]) -> dict[str, Any]:
    """
    Judge 출력 검증 (Stage 9 전용).

    비표준 키(result/reason 등)를 표준 스키마로 정규화하고
    필수 정보가 부족하면 보수적 기본값(FALSE, confidence=0)을 적용합니다.
    """
    if not isinstance(result, dict):
        logger.warning("Judge output이 dict가 아님, 빈 dict로 처리")
        result = {}

    def _string_list(value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        cleaned: list[str] = []
        for item in value:
            if not isinstance(item, str):
                continue
            token = item.strip()
            if token:
                cleaned.append(token)
        return cleaned

    def _normalize_label(value: Any) -> str:
        raw = str(value or "").strip().upper()
        if raw in {"TRUE", "FALSE"}:
            return raw
        if raw in {"UNVERIFIED", "MIXED"}:
            return "FALSE"
        if raw in {"FACT", "SUPPORTED", "CONFIRMED", "REAL"}:
            return "TRUE"
        if raw in {"FAKE", "REFUTED", "NOT_TRUE"}:
            return "FALSE"
        return ""

    def _to_int(value: Any, default: int = 0) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    def _to_float(value: Any, default: float = 0.0) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    schema_mismatch = False

    raw_label = (
        result.get("verdict_label")
        or result.get("label")
        or result.get("result")
        or result.get("verdict")
    )
    label = _normalize_label(raw_label)
    if not label:
        schema_mismatch = True
        label = "FALSE"

    raw_confidence = result.get("confidence_percent")
    if isinstance(raw_confidence, (int, float)):
        confidence_percent = int(max(0, min(100, int(raw_confidence))))
    elif isinstance(result.get("confidence"), (int, float)):
        confidence_val = float(result.get("confidence"))
        if confidence_val <= 1.0:
            confidence_percent = int(max(0.0, min(1.0, confidence_val)) * 100)
        else:
            confidence_percent = int(max(0.0, min(100.0, confidence_val)))
    else:
        schema_mismatch = True
        confidence_percent = 0

    explanation = str(
        result.get("explanation")
        or result.get("reason")
        or result.get("rationale")
        or ""
    ).strip()
    if not explanation:
        schema_mismatch = True
        explanation = "모델 출력이 스키마와 달라 보수적으로 판정했습니다."

    headline = str(result.get("headline") or "").strip()
    if not headline:
        schema_mismatch = True
        headline = f"이 주장은 {confidence_percent}% 확률로 {'사실' if label == 'TRUE' else '거짓'}로 판단됩니다"

    raw_evaluation = result.get("evaluation")
    if isinstance(raw_evaluation, dict):
        evaluation = {
            "hallucination_count": _to_int(raw_evaluation.get("hallucination_count", 0), 0),
            "grounding_score": _to_float(raw_evaluation.get("grounding_score", 1.0), 1.0),
            "is_consistent": bool(raw_evaluation.get("is_consistent", True)),
            "policy_violations": _string_list(raw_evaluation.get("policy_violations")),
        }
    else:
        schema_mismatch = True
        evaluation = {
            "hallucination_count": 0,
            "grounding_score": 1.0,
            "is_consistent": True,
            "policy_violations": [],
        }

    selected_ids_raw = (
        result.get("selected_evidence_ids")
        or result.get("selected_ids")
        or result.get("evidence_ids")
        or []
    )
    selected_evidence_ids = _string_list(selected_ids_raw)
    if "selected_evidence_ids" not in result and selected_evidence_ids:
        schema_mismatch = True

    evidence_summary = result.get("evidence_summary") if isinstance(result.get("evidence_summary"), list) else []
    cautions = _string_list(result.get("cautions") or result.get("warnings"))
    recommendation = str(result.get("recommendation") or "").strip()
    risk_flags = _string_list(result.get("risk_flags"))

    if schema_mismatch and "JUDGE_SCHEMA_MISMATCH" not in risk_flags:
        risk_flags.append("JUDGE_SCHEMA_MISMATCH")

    return {
        "evaluation": evaluation,
        "verdict_label": label,
        "confidence_percent": confidence_percent,
        "headline": headline,
        "explanation": explanation,
        "selected_evidence_ids": selected_evidence_ids,
        "evidence_summary": evidence_summary,
        "cautions": cautions,
        "recommendation": recommendation,
        "risk_flags": risk_flags,
    }
