"""
Stage 7: Verify Skeptic Node
담당: Team B (김현섭, 윤수민)
"""

from typing import Any


def verify_skeptic_node(state: dict[str, Any]) -> dict[str, Any]:
    """
    회의 관점에서 검증 (병렬 실행)

    입력: top_evidences, normalized_claim
    출력: skeptic_result
    """
    evidences = state.get("top_evidences", [])
    claim = state.get("normalized_claim", "")

    # TODO: SLM2를 활용한 회의 관점 검증
    # "이 증거들이 주장을 반박하는지 분석하세요"

    skeptic_result = {
        "stance": "refute",  # support / refute / neutral
        "confidence": 0.5,
        "reasoning": "",  # TODO: 판단 근거
    }

    return {
        **state,
        "skeptic_result": skeptic_result,
    }
