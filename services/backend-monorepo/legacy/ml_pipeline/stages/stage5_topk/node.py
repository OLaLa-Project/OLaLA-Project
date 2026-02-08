"""
Stage 5: TopK Node
담당: Team A (이윤호, 성세빈)
"""

from typing import Any

TOP_K = 5  # 상위 K개 선택


def topk_node(state: dict[str, Any]) -> dict[str, Any]:
    """
    상위 K개 증거 선택

    입력: scored_evidences
    출력: top_evidences
    """
    scored_evidences = state.get("scored_evidences", [])

    # 점수 기준 정렬 후 상위 K개 선택
    sorted_evidences = sorted(
        scored_evidences,
        key=lambda x: x.get("score", 0),
        reverse=True
    )
    top_evidences = sorted_evidences[:TOP_K]

    return {
        **state,
        "top_evidences": top_evidences,
    }
