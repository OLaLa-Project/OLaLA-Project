"""
Stage 6: Verify Support Node
담당: Team B (김현섭, 윤수민)
"""

from typing import Any


def verify_support_node(state: dict[str, Any]) -> dict[str, Any]:
    """
    지지 관점에서 검증 (병렬 실행)

    입력: top_evidences, normalized_claim
    출력: support_result
    """
    evidences = state.get("top_evidences", [])
    claim = state.get("normalized_claim", "")

    # TODO: SLM2를 활용한 지지 관점 검증
    # "이 증거들이 주장을 지지하는지 분석하세요"

    support_result = {
        "stance": "support",  # support / refute / neutral
        "confidence": 0.5,
        "reasoning": "",  # TODO: 판단 근거
    }

    return {
        **state,
        "support_result": support_result,
    }
