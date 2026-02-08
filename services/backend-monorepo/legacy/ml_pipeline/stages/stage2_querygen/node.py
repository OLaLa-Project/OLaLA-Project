"""
Stage 2: QueryGen Node
담당: Team A (이윤호, 성세빈)
"""

from typing import Any


def querygen_node(state: dict[str, Any]) -> dict[str, Any]:
    """
    Wikipedia 검색용 쿼리 생성

    입력: normalized_claim
    출력: queries
    """
    normalized_claim = state.get("normalized_claim", "")

    # TODO: SLM1을 활용한 쿼리 생성
    queries = [
        {"query": normalized_claim, "type": "full_text"}
    ]

    return {
        **state,
        "queries": queries,
    }
