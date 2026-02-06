"""
Stage 4: Score Node
담당: Team A (이윤호, 성세빈)
"""

from typing import Any


def score_node(state: dict[str, Any]) -> dict[str, Any]:
    """
    증거 관련성 점수화

    입력: evidences, normalized_claim
    출력: scored_evidences
    """
    evidences = state.get("evidences", [])
    claim = state.get("normalized_claim", "")

    # TODO: 관련성 점수 계산
    scored_evidences = [
        {**ev, "score": 0.5}  # TODO: 실제 점수 계산
        for ev in evidences
    ]

    return {
        **state,
        "scored_evidences": scored_evidences,
    }
