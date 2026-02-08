"""
Stage 1: Normalize Node
담당: Team A (이윤호, 성세빈)
"""

import re
from typing import Any


def normalize_node(state: dict[str, Any]) -> dict[str, Any]:
    """
    입력 텍스트를 정규화

    입력: raw_claim
    출력: normalized_claim, language
    """
    raw_claim = state.get("raw_claim", "")

    # TODO: 정규화 로직 구현
    normalized = raw_claim.strip()
    normalized = re.sub(r'\s+', ' ', normalized)

    return {
        **state,
        "normalized_claim": normalized,
        "language": "ko",  # TODO: 언어 감지
    }
