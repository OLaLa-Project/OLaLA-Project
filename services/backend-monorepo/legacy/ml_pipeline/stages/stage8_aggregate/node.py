"""
Stage 8: Aggregate Node
담당: Team B (김현섭, 윤수민)
"""

from typing import Any


def aggregate_node(state: dict[str, Any]) -> dict[str, Any]:
    """
    지지/회의 결과 통합

    입력: support_result, skeptic_result
    출력: aggregated_result
    """
    support = state.get("support_result", {})
    skeptic = state.get("skeptic_result", {})

    # TODO: 두 관점 통합 로직
    # 1. 일치하면 -> 높은 신뢰도
    # 2. 충돌하면 -> MIXED 또는 추가 분석

    aggregated_result = {
        "support_stance": support.get("stance"),
        "skeptic_stance": skeptic.get("stance"),
        "combined_confidence": (
            support.get("confidence", 0) + skeptic.get("confidence", 0)
        ) / 2,
        "conflict": support.get("stance") != skeptic.get("stance"),
    }

    return {
        **state,
        "aggregated_result": aggregated_result,
    }
