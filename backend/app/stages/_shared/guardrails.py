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
from typing import Any, Callable, Optional

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


def parse_json_safe(text: str) -> Optional[dict]:
    """
    안전한 JSON 파싱. 실패 시 None 반환.
    """
    try:
        extracted = extract_json_from_text(text)
        return json.loads(extracted)
    except (json.JSONDecodeError, TypeError) as e:
        logger.warning(f"JSON 파싱 실패: {e}")
        return None


def parse_json_with_retry(
    call_fn: Callable[[], str],
    retry_system_prompt: str = "이전 응답이 올바른 JSON 형식이 아닙니다. 반드시 유효한 JSON만 출력하세요. 다른 설명 없이 JSON만 출력하세요.",
    retry_call_fn: Optional[Callable[[str], str]] = None,
) -> dict:
    """
    JSON 파싱 with 1회 재시도.

    Args:
        call_fn: 첫 번째 SLM 호출 함수 (인자 없음, 문자열 반환)
        retry_system_prompt: 재시도 시 사용할 시스템 프롬프트
        retry_call_fn: 재시도 호출 함수 (시스템 프롬프트를 인자로 받음)
                       None이면 call_fn을 다시 호출

    Returns:
        파싱된 dict

    Raises:
        JSONParseError: 재시도 후에도 파싱 실패
    """
    # 첫 번째 시도
    response = call_fn()
    result = parse_json_safe(response)

    if result is not None:
        return result

    # 재시도
    logger.info("JSON 파싱 실패, 1회 재시도")
    if retry_call_fn:
        response = retry_call_fn(retry_system_prompt)
    else:
        response = call_fn()

    result = parse_json_safe(response)
    if result is not None:
        return result

    raise JSONParseError(f"JSON 파싱 실패 (재시도 후에도 실패): {response[:200]}...")


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
        else:
            logger.warning(f"Quote 검증 실패: evid_id={evid_id}, quote='{quote[:50]}...'")

    logger.info(f"Citation 검증: {len(validated)}/{len(citations)} 통과")
    return validated


def normalize_whitespace(text: str) -> str:
    """공백/줄바꿈 정규화."""
    return " ".join(text.split()).lower()


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
    verdict["citations"] = validate_citations(raw_citations, evidence_topk)

    # citations=0이면 UNVERIFIED 강제
    verdict = enforce_unverified_if_no_citations(verdict)

    return verdict


# ---------------------------------------------------------------------------
# Judge 전용 파서/검증 (Stage 9)
# ---------------------------------------------------------------------------

def parse_judge_json(text: str) -> dict:
    """
    Judge 응답 JSON 파싱 (Stage 9 전용).

    - LLMGateway._parse_json과 동일한 추출 규칙 사용
    - 파싱 실패 시 JSONParseError 발생
    """
    try:
        extracted = extract_json_from_text(text)
        return json.loads(extracted)
    except (json.JSONDecodeError, TypeError) as e:
        raise JSONParseError(f"Judge JSON 파싱 실패: {e}")


def parse_judge_json_with_retry(
    call_fn: Callable[[], str],
    max_retries: int = 0,
    retry_system_prompt: str = "이전 응답이 올바른 JSON 형식이 아닙니다. 반드시 유효한 JSON만 출력하세요. 다른 설명 없이 JSON만 출력하세요.",
    retry_call_fn: Optional[Callable[[str], str]] = None,
) -> dict:
    """
    Judge JSON 파싱 with (옵션) 재시도.

    기본값 max_retries=0으로 LLMGateway.judge_verdict의 기본 동작(파싱 실패 시 즉시 실패)을 유지합니다.
    """
    attempt = 0
    response = call_fn()
    try:
        return parse_judge_json(response)
    except JSONParseError as e:
        last_error = e

    while attempt < max_retries:
        attempt += 1
        logger.info("Judge JSON 파싱 실패, 재시도")
        if retry_call_fn:
            response = retry_call_fn(retry_system_prompt)
        else:
            response = call_fn()
        try:
            return parse_judge_json(response)
        except JSONParseError as e:
            last_error = e

    raise last_error


def validate_judge_output(result: dict) -> dict:
    """
    Judge 출력 검증 (Stage 9 전용).

    현재는 LLMGateway의 후처리 로직에 위임되며,
    출력 내용을 변경하지 않습니다.
    """
    return result
