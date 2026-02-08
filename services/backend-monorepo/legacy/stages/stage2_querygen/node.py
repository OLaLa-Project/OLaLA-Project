"""
Stage 2: QueryGen Node
담당: Team A (이윤호, 성세빈)

검색 쿼리를 생성합니다.
"""

from typing import Any


def querygen_node(state: dict[str, Any]) -> dict[str, Any]:
    """
    Wikipedia 검색용 쿼리를 생성하는 노드

    Args:
        state: {"request_id": str, "normalized_claim": str, "language": str}

    Returns:
        {"request_id": str, "queries": list[dict]}
    """
    normalized_claim = state.get("normalized_claim", "")

    # TODO: 쿼리 생성 로직 구현
    # 1. 키워드 추출
    # 2. 엔티티 추출
    # 3. SLM1으로 쿼리 확장

    queries = [
        {"query": normalized_claim, "type": "full_text"}
    ]

    return {
        "request_id": state.get("request_id"),
        "queries": queries
    }
