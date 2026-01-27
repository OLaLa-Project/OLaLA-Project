"""
Stage 8 - Aggregate Verdict (판정 병합)

Stage 6 (Supportive)와 Stage 7 (Skeptic)의 결과를 병합하여
최종 draft_verdict를 생성합니다.

Input state keys:
    - trace_id: str
    - verdict_support: DraftVerdict dict (from Stage 6)
    - verdict_skeptic: DraftVerdict dict (from Stage 7)
    - evidence_topk: list[dict] (원본 증거)

Output state keys:
    - draft_verdict: DraftVerdict dict (병합된 최종 결과)
    - quality_score: int (0~100, 결과 품질 점수)
"""

import logging
from typing import Optional

from app.stages._shared.guardrails import (
    validate_stance,
    validate_confidence,
    enforce_unverified_if_no_citations,
)

logger = logging.getLogger(__name__)

# 유효한 stance 값들
VALID_STANCES = {"TRUE", "FALSE", "MIXED", "UNVERIFIED"}


def merge_citations(support_cits: list, skeptic_cits: list) -> list:
    """
    두 verdict의 citations를 병합 (중복 제거).
    """
    seen_evid_ids = set()
    merged = []

    for cit in support_cits + skeptic_cits:
        evid_id = cit.get("evid_id", "")
        if evid_id and evid_id not in seen_evid_ids:
            seen_evid_ids.add(evid_id)
            merged.append(cit)

    return merged


def merge_reasoning_bullets(
    support_bullets: list,
    skeptic_bullets: list,
    final_stance: str,
) -> list:
    """
    두 verdict의 reasoning_bullets를 병합.
    """
    bullets = []

    # 지지 관점 근거
    for bullet in support_bullets:
        if bullet and not bullet.startswith("[시스템"):
            bullets.append(f"[지지] {bullet}")

    # 회의적 관점 근거
    for bullet in skeptic_bullets:
        if bullet and not bullet.startswith("[시스템"):
            bullets.append(f"[반박] {bullet}")

    # 최종 판정 설명 추가
    if final_stance == "MIXED":
        bullets.insert(0, "[종합] 지지와 반박 증거가 모두 존재하여 MIXED로 판정")
    elif final_stance == "UNVERIFIED":
        bullets.insert(0, "[종합] 충분한 근거가 없어 UNVERIFIED로 판정")

    return bullets


def merge_weak_points(support_wp: list, skeptic_wp: list) -> list:
    """weak_points 병합."""
    merged = []
    for wp in support_wp + skeptic_wp:
        if wp and wp not in merged:
            merged.append(wp)
    return merged


def merge_followup_queries(support_fq: list, skeptic_fq: list) -> list:
    """followup_queries 병합."""
    merged = []
    for fq in support_fq + skeptic_fq:
        if fq and fq not in merged:
            merged.append(fq)
    return merged[:5]  # 최대 5개


def determine_final_stance(
    support_stance: str,
    skeptic_stance: str,
    has_citations: bool,
) -> str:
    """
    최종 stance 결정 (MVP 병합 규칙).

    규칙:
    1. A/B 모두 UNVERIFIED → UNVERIFIED
    2. A/B 합의 (TRUE/TRUE 또는 FALSE/FALSE) + citations 존재 → 그 stance
    3. A/B 불합의 (TRUE vs FALSE) → MIXED 또는 UNVERIFIED (근거 부족이면)
    """
    # 둘 다 UNVERIFIED
    if support_stance == "UNVERIFIED" and skeptic_stance == "UNVERIFIED":
        return "UNVERIFIED"

    # citations 없으면 UNVERIFIED
    if not has_citations:
        return "UNVERIFIED"

    # 합의된 경우
    if support_stance == skeptic_stance:
        return support_stance

    # 한쪽만 UNVERIFIED인 경우 - 다른 쪽 따라감
    if support_stance == "UNVERIFIED":
        return skeptic_stance
    if skeptic_stance == "UNVERIFIED":
        return support_stance

    # TRUE vs FALSE 불합의 → MIXED
    if {support_stance, skeptic_stance} == {"TRUE", "FALSE"}:
        return "MIXED"

    # 그 외 불합의 (MIXED 포함) → MIXED
    return "MIXED"


def calculate_final_confidence(
    support_conf: float,
    skeptic_conf: float,
    final_stance: str,
    support_stance: str,
    skeptic_stance: str,
) -> float:
    """
    최종 confidence 계산.

    - 합의: 두 confidence의 평균
    - 불합의: 낮은 쪽으로 조정
    - UNVERIFIED: 0.0
    """
    if final_stance == "UNVERIFIED":
        return 0.0

    # 합의된 경우
    if support_stance == skeptic_stance:
        return (support_conf + skeptic_conf) / 2

    # 불합의 시 페널티
    avg = (support_conf + skeptic_conf) / 2
    return max(0.0, avg * 0.7)  # 30% 페널티


def calculate_quality_score(
    verdict: dict,
    support_verdict: dict,
    skeptic_verdict: dict,
) -> int:
    """
    결과 품질 점수 계산 (0~100).

    구성:
    - 형식 점수 (40점): JSON 파싱 성공, 필수 필드 존재
    - 근거 점수 (40점): citations 수, reasoning_bullets 수
    - 합의 점수 (20점): A/B 판정 일치 여부
    """
    score = 0

    # 1. 형식 점수 (40점)
    format_score = 0
    required_fields = ["stance", "confidence", "reasoning_bullets", "citations"]
    for field in required_fields:
        if field in verdict:
            format_score += 10
    score += format_score

    # 2. 근거 점수 (40점)
    evidence_score = 0
    citations_count = len(verdict.get("citations", []))
    reasoning_count = len(verdict.get("reasoning_bullets", []))

    # citations: 최대 20점 (1개당 4점, 최대 5개)
    evidence_score += min(20, citations_count * 4)

    # reasoning: 최대 20점 (1개당 4점, 최대 5개)
    evidence_score += min(20, reasoning_count * 4)
    score += evidence_score

    # 3. 합의 점수 (20점)
    support_stance = support_verdict.get("stance", "UNVERIFIED")
    skeptic_stance = skeptic_verdict.get("stance", "UNVERIFIED")

    if support_stance == skeptic_stance and support_stance != "UNVERIFIED":
        score += 20  # 완전 합의
    elif support_stance != "UNVERIFIED" and skeptic_stance != "UNVERIFIED":
        score += 10  # 둘 다 판정은 했음

    return min(100, max(0, score))


def create_fallback_verdict(reason: str) -> dict:
    """오류 시 fallback verdict 생성."""
    return {
        "stance": "UNVERIFIED",
        "confidence": 0.0,
        "reasoning_bullets": [f"[시스템 오류] {reason}"],
        "citations": [],
        "weak_points": ["병합 처리 중 오류 발생"],
        "followup_queries": [],
    }


def run(state: dict) -> dict:
    """
    Stage 8 실행: 판정 병합.

    Args:
        state: 파이프라인 상태 dict

    Returns:
        draft_verdict와 quality_score가 추가된 state
    """
    trace_id = state.get("trace_id", "unknown")

    logger.info(f"[{trace_id}] Stage8 시작: 판정 병합")

    # 입력 verdict 가져오기
    support_verdict = state.get("verdict_support", {})
    skeptic_verdict = state.get("verdict_skeptic", {})

    # 입력 검증
    if not support_verdict and not skeptic_verdict:
        logger.error(f"[{trace_id}] 입력 verdict 없음")
        state["draft_verdict"] = create_fallback_verdict("입력 verdict 없음")
        state["quality_score"] = 0
        return state

    try:
        # 개별 verdict 정보 추출
        support_stance = validate_stance(support_verdict.get("stance", "UNVERIFIED"))
        skeptic_stance = validate_stance(skeptic_verdict.get("stance", "UNVERIFIED"))
        support_conf = validate_confidence(support_verdict.get("confidence", 0.0))
        skeptic_conf = validate_confidence(skeptic_verdict.get("confidence", 0.0))

        # Citations 병합
        merged_citations = merge_citations(
            support_verdict.get("citations", []),
            skeptic_verdict.get("citations", []),
        )
        has_citations = len(merged_citations) > 0

        # 최종 stance 결정
        final_stance = determine_final_stance(
            support_stance, skeptic_stance, has_citations
        )

        # 최종 confidence 계산
        final_confidence = calculate_final_confidence(
            support_conf, skeptic_conf, final_stance, support_stance, skeptic_stance
        )

        # Reasoning bullets 병합
        merged_reasoning = merge_reasoning_bullets(
            support_verdict.get("reasoning_bullets", []),
            skeptic_verdict.get("reasoning_bullets", []),
            final_stance,
        )

        # 기타 필드 병합
        merged_weak_points = merge_weak_points(
            support_verdict.get("weak_points", []),
            skeptic_verdict.get("weak_points", []),
        )
        merged_followup = merge_followup_queries(
            support_verdict.get("followup_queries", []),
            skeptic_verdict.get("followup_queries", []),
        )

        # 최종 verdict 조립
        draft_verdict = {
            "stance": final_stance,
            "confidence": final_confidence,
            "reasoning_bullets": merged_reasoning,
            "citations": merged_citations,
            "weak_points": merged_weak_points,
            "followup_queries": merged_followup,
        }

        # citations=0이면 UNVERIFIED 강제 (최종 guardrail)
        draft_verdict = enforce_unverified_if_no_citations(draft_verdict)

        # 품질 점수 계산
        quality_score = calculate_quality_score(
            draft_verdict, support_verdict, skeptic_verdict
        )

        logger.info(
            f"[{trace_id}] Stage8 완료: "
            f"support={support_stance}, skeptic={skeptic_stance} → "
            f"final={draft_verdict['stance']}, "
            f"confidence={draft_verdict['confidence']:.2f}, "
            f"citations={len(merged_citations)}, "
            f"quality={quality_score}"
        )

    except Exception as e:
        logger.exception(f"[{trace_id}] 병합 중 오류: {e}")
        draft_verdict = create_fallback_verdict(f"병합 오류: {e}")
        quality_score = 0

    state["draft_verdict"] = draft_verdict
    state["quality_score"] = quality_score
    return state
