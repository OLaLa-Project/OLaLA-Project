"""
Stage 8 - Prepare Judge Packs (판정용 정제 패키지 생성)

Stage 6 (Supportive)와 Stage 7 (Skeptic)의 결과를
Stage 9 Judge가 직접 비교/판정할 수 있도록 정제합니다.

Input state keys:
    - trace_id: str
    - verdict_support: DraftVerdict dict (from Stage 6)
    - verdict_skeptic: DraftVerdict dict (from Stage 7)
    - evidence_topk: list[dict] (원본 증거)

Output state keys:
    - support_pack: dict (Stage6 결과 정제본)
    - skeptic_pack: dict (Stage7 결과 정제본)
    - evidence_index: dict (evid_id -> evidence payload)
    - judge_prep_meta: dict (정제 메타)
"""

import logging

logger = logging.getLogger(__name__)


def _build_evidence_index(evidence_topk: list[dict]) -> dict:
    """evidence_topk를 evid_id 키로 인덱싱."""
    index: dict[str, dict] = {}
    for i, ev in enumerate(evidence_topk or [], start=1):
        evid_id = ev.get("evid_id") or f"ev_{i}"
        # Stage9에서 원문 비교가 필요하므로 snippet/content를 그대로 유지한다.
        index[evid_id] = {
            "evid_id": evid_id,
            "title": ev.get("title", ""),
            "url": ev.get("url", ""),
            "snippet": ev.get("snippet") or ev.get("content", ""),
            "source_type": ev.get("source_type", "WEB_URL"),
        }
    return index


def _normalize_verdict(verdict: dict) -> dict:
    """판정 결과를 Stage9 입력용으로 정규화."""
    verdict = verdict or {}
    return {
        "stance": verdict.get("stance", "UNVERIFIED"),
        "confidence": verdict.get("confidence", 0.0),
        "reasoning_bullets": verdict.get("reasoning_bullets", []) or [],
        "citations": verdict.get("citations", []) or [],
        "weak_points": verdict.get("weak_points", []) or [],
        "followup_queries": verdict.get("followup_queries", []) or [],
    }


def run(state: dict) -> dict:
    """
    Stage 8 실행: Stage9 판결을 위한 정제 패키지 생성.

    기존 병합/판결/quality_score 계산은 제거하고,
    Stage9이 직접 판결하도록 입력 구조만 정제한다.
    """
    trace_id = state.get("trace_id", "unknown")
    logger.info(f"[{trace_id}] Stage8 시작: 판정용 정제 패키지 생성")

    support_verdict = _normalize_verdict(state.get("verdict_support", {}))
    skeptic_verdict = _normalize_verdict(state.get("verdict_skeptic", {}))
    evidence_topk = state.get("evidence_topk", [])

    evidence_index = _build_evidence_index(evidence_topk)

    # Stage9 입력용 패키지. 기존 병합 로직을 제거하고 원본 결과만 전달한다.
    state["support_pack"] = support_verdict
    state["skeptic_pack"] = skeptic_verdict
    state["evidence_index"] = evidence_index
    state["judge_prep_meta"] = {
        "support_citation_count": len(support_verdict.get("citations", [])),
        "skeptic_citation_count": len(skeptic_verdict.get("citations", [])),
        "support_has_citations": bool(support_verdict.get("citations")),
        "skeptic_has_citations": bool(skeptic_verdict.get("citations")),
    }

    logger.info(
        f"[{trace_id}] Stage8 완료: support_cits={state['judge_prep_meta']['support_citation_count']}, "
        f"skeptic_cits={state['judge_prep_meta']['skeptic_citation_count']}, "
        f"evidence_index={len(evidence_index)}"
    )

    return state
