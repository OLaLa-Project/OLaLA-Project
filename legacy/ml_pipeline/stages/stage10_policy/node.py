"""
Stage 10: Policy Guard Node
담당: Common (이은지, 성세빈)
"""

from typing import Any

# 정책 필터링 키워드 (예시)
BLOCKED_TOPICS = [
    "정치적 선동",
    "혐오 발언",
    # TODO: 정책에 따라 추가
]


def policy_node(state: dict[str, Any]) -> dict[str, Any]:
    """
    정책 필터링

    입력: judgment, normalized_claim
    출력: final_result
    """
    judgment = state.get("judgment", {})
    claim = state.get("normalized_claim", "")

    # TODO: 정책 필터링 로직
    # 1. 금지 주제 검사
    # 2. 민감 정보 마스킹
    # 3. 응답 포맷 정리

    is_blocked = False  # TODO: 실제 필터링

    if is_blocked:
        final_result = {
            "label": "REFUSED",
            "confidence": 1.0,
            "summary": "정책상 처리할 수 없는 요청입니다.",
            "evidences": [],
        }
    else:
        final_result = {
            "label": judgment.get("label", "UNVERIFIED"),
            "confidence": judgment.get("confidence", 0.0),
            "summary": judgment.get("summary", ""),
            "evidences": state.get("top_evidences", []),
        }

    return {
        **state,
        "final_result": final_result,
    }
