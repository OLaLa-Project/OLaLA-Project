"""
Stage 9: Judge Node
담당: Common (이은지, 성세빈)
"""

from typing import Any, Literal

Label = Literal["TRUE", "FALSE", "MIXED", "UNVERIFIED", "REFUSED"]


def judge_node(state: dict[str, Any]) -> dict[str, Any]:
    """
    최종 판정

    입력: aggregated_result, top_evidences
    출력: judgment
    """
    aggregated = state.get("aggregated_result", {})
    evidences = state.get("top_evidences", [])

    # TODO: LLM을 활용한 최종 판정
    # 증거가 없으면 UNVERIFIED

    if not evidences:
        label: Label = "UNVERIFIED"
        confidence = 0.0
        summary = "검증할 증거를 찾지 못했습니다."
    else:
        # TODO: 실제 판정 로직
        label = "UNVERIFIED"
        confidence = aggregated.get("combined_confidence", 0.0)
        summary = "판정 로직 구현 필요"

    judgment = {
        "label": label,
        "confidence": confidence,
        "summary": summary,
    }

    return {
        **state,
        "judgment": judgment,
    }
