"""
Stage 1: Normalize Node
담당: Team A (이윤호, 성세빈)

사용자 입력 텍스트를 정규화합니다.
"""

import re
from typing import Any


def normalize_node(state: dict[str, Any]) -> dict[str, Any]:
    """
    입력 텍스트를 정규화하는 노드

    Args:
        state: {"request_id": str, "raw_claim": str}

    Returns:
        {"request_id": str, "normalized_claim": str, "language": str, "metadata": dict}
    """
    raw_claim = state.get("raw_claim", "")

    # TODO: 정규화 로직 구현
    # 1. 특수문자 처리
    # 2. 공백 정리
    # 3. 언어 감지

    normalized = raw_claim.strip()
    normalized = re.sub(r'\s+', ' ', normalized)

    return {
        "request_id": state.get("request_id"),
        "normalized_claim": normalized,
        "language": "ko",  # TODO: 언어 감지 구현
        "metadata": {}
    }
