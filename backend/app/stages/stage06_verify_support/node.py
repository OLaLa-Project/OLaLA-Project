"""
Stage 6 - Supportive Verification (지지 관점 검증)

주장을 지지하는 관점에서 증거를 분석합니다.
LLM Gateway를 통해 검증을 수행합니다.

Input state keys:
    - trace_id: str
    - claim_text: str
    - language: "ko" | "en" (default: "ko")
    - evidence_topk: list[dict] (evid_id, title, url, snippet, source_type)

Output state keys:
    - verdict_support: DraftVerdict dict
"""

import logging
from typing import List

from app.gateway import GatewayError
from app.gateway.llm.llm_gateway import get_llm_gateway
from app.core.schemas import Citation

logger = logging.getLogger(__name__)

DEFAULT_LANGUAGE = "ko"


def _convert_to_citations(evidence_topk: List[dict]) -> List[Citation]:
    """evidence_topk를 Citation 객체 리스트로 변환 (Gateway용)."""
    citations = []
    for ev in evidence_topk:
        citations.append(
            Citation(
                source_type=ev.get("source_type", "WEB"),
                title=ev.get("title", ""),
                url=ev.get("url", ""),
                quote=ev.get("snippet") or ev.get("content", ""),
                relevance=ev.get("score", 0.0),
                evid_id=ev.get("evid_id"),
            )
        )
    return citations


def create_fallback_verdict(reason: str) -> dict:
    """Gateway 호출 실패 시 fallback verdict 생성."""
    return {
        "stance": "UNVERIFIED",
        "confidence": 0.0,
        "reasoning_bullets": [f"[시스템 오류] {reason}"],
        "citations": [],
        "weak_points": ["SLM 호출 실패로 분석 불가"],
        "followup_queries": [],
    }


def run(state: dict) -> dict:
    """
    Stage 6 실행: 지지 관점 검증.

    Args:
        state: 파이프라인 상태 dict

    Returns:
        verdict_support가 추가된 state
    """
    trace_id = state.get("trace_id", "unknown")
    claim_text = state.get("claim_text", "")
    language = state.get("language", DEFAULT_LANGUAGE)
    evidence_topk = state.get("evidence_topk", [])

    logger.info(f"[{trace_id}] Stage6 시작: claim={claim_text[:50]}...")

    # 증거가 없으면 바로 UNVERIFIED
    if not evidence_topk:
        logger.warning(f"[{trace_id}] 증거 없음, UNVERIFIED 반환")
        state["verdict_support"] = create_fallback_verdict("증거가 제공되지 않음")
        return state

    try:
        # Gateway 인스턴스 획득
        gateway = get_llm_gateway()
        
        # 증거 변환
        citations = _convert_to_citations(evidence_topk)
        
        # Gateway 호출 (perspective="supportive")
        verdict_obj = gateway.verify_claim(
            claim_text=claim_text,
            citations=citations,
            perspective="supportive",
            language=language,
        )
        
        # 객체를 dict로 변환 (State 저장용)
        # DraftVerdict 객체는 as_dict() 메서드나 dataclasses.asdict() 등을 지원해야 함.
        # 여기서는 Gateway가 반환하는 객체가 Pydantic 모델이나 Dataclass라고 가정.
        # 하지만 llm_gateway.py를 보면 `verify_claim`은 `DraftVerdict` 객체를 반환.
        # schemas.py를 확인해야 하지만, 보통 dict 호환되거나 변환 필요.
        # 일단 안전하게 dict로 변환 시도.
        if hasattr(verdict_obj, "dict"):
            verdict = verdict_obj.dict()
        elif hasattr(verdict_obj, "as_dict"):
            verdict = verdict_obj.as_dict()
        else:
            # dataclass or pydantic model default
            from dataclasses import asdict, is_dataclass
            if is_dataclass(verdict_obj):
                verdict = asdict(verdict_obj)
            else:
                # 최악의 경우 dict(verdict_obj) 시도 (Pydantic v2 등)
                verdict = dict(verdict_obj)

        logger.info(
            f"[{trace_id}] Stage6 완료: stance={verdict.get('stance')}, "
            f"confidence={verdict.get('confidence', 0.0):.2f}, "
            f"citations={len(verdict.get('citations', []))}"
        )

    except GatewayError as e:
        logger.error(f"[{trace_id}] Gateway 호출 실패: {e}")
        verdict = create_fallback_verdict(f"Gateway 오류: {e}")

    except Exception as e:
        logger.exception(f"[{trace_id}] 예상치 못한 오류: {e}")
        verdict = create_fallback_verdict(f"내부 오류: {e}")

    state["verdict_support"] = verdict
    return state
