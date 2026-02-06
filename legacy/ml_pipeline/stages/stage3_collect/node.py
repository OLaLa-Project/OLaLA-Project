"""
Stage 3: Collect Node
담당: Team A (이윤호, 성세빈)
"""

from typing import Any


def collect_node(state: dict[str, Any]) -> dict[str, Any]:
    """
    Wikipedia에서 증거 수집 (RAG)

    입력: queries
    출력: evidences
    """
    queries = state.get("queries", [])

    # TODO: Wikipedia API + Hybrid Search (BM25 + Vector)
    evidences = []

    return {
        **state,
        "evidences": evidences,
    }
