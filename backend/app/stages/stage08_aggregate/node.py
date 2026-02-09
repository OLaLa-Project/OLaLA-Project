"""
Stage 8 - Prepare Judge Packs (판정용 정제 패키지 생성)

Stage 6 (Supportive)와 Stage 7 (Skeptic)의 결과를
Stage 9 Judge가 직접 비교/판정할 수 있도록 정제합니다.
"""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urlsplit

from app.core.settings import settings

logger = logging.getLogger(__name__)


def _required_intents() -> set[str]:
    raw = str(settings.stage6_rumor_required_intents_csv or "").strip()
    if not raw:
        return {"official_statement", "fact_check"}
    intents = {token.strip().lower() for token in raw.split(",") if token.strip()}
    return intents or {"official_statement", "fact_check"}


def _source_domain(url: str) -> str:
    netloc = (urlsplit(str(url or "").strip()).netloc or "").lower()
    if netloc.startswith("www."):
        netloc = netloc[4:]
    if not netloc and str(url or "").startswith("wiki://"):
        return "wiki"
    return netloc or "unknown"


def _build_evidence_index(evidence_topk: list[dict]) -> dict:
    """evidence_topk를 evid_id 키로 인덱싱하고 메타를 보존."""
    index: dict[str, dict[str, Any]] = {}
    for i, evidence in enumerate(evidence_topk or [], start=1):
        evid_id = str(evidence.get("evid_id") or f"ev_{i}")
        metadata = evidence.get("metadata") if isinstance(evidence.get("metadata"), dict) else {}

        candidate = {
            "evid_id": evid_id,
            "title": evidence.get("title", ""),
            "url": evidence.get("url", ""),
            "snippet": evidence.get("snippet") or evidence.get("content", ""),
            "source_type": evidence.get("source_type", "WEB_URL"),
            "intent": str(metadata.get("intent") or "").strip().lower(),
            "claim_id": str(metadata.get("claim_id") or "").strip(),
            "mode": str(metadata.get("mode") or "").strip().lower(),
            "query_stance": str(metadata.get("stance") or "neutral").strip().lower() or "neutral",
            "pre_score": metadata.get("pre_score"),
            "credibility_score": metadata.get("credibility_score"),
            "source_trust_score": metadata.get("source_trust_score"),
            "html_signal_score": metadata.get("html_signal_score"),
            "source_tier": metadata.get("source_tier"),
            "source_domain": _source_domain(evidence.get("url", "")),
            "metadata": metadata,
        }
        existing = index.get(evid_id)
        if isinstance(existing, dict):
            prev_score = existing.get("pre_score")
            next_score = candidate.get("pre_score")
            try:
                prev = float(prev_score)
            except (TypeError, ValueError):
                prev = -1.0
            try:
                nxt = float(next_score)
            except (TypeError, ValueError):
                nxt = -1.0
            if prev >= nxt:
                continue
        index[evid_id] = candidate
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


def _analysis_meta(
    verdict: dict,
    evidence_index: dict[str, dict[str, Any]],
    claim_mode: str,
) -> dict[str, Any]:
    citations = verdict.get("citations") if isinstance(verdict.get("citations"), list) else []
    intent_counts: dict[str, int] = {}
    claim_coverage: set[str] = set()
    has_required_intent_from_citations = False
    required_intents = _required_intents()
    has_required_intent_from_topk = any(
        str((item or {}).get("intent") or "").strip().lower() in required_intents
        for item in (evidence_index or {}).values()
        if isinstance(item, dict)
    )

    for citation in citations:
        if not isinstance(citation, dict):
            continue
        evid_id = str(citation.get("evid_id") or "").strip()
        if not evid_id:
            continue
        evidence = evidence_index.get(evid_id, {})
        intent = str(evidence.get("intent") or "").strip().lower()
        claim_id = str(evidence.get("claim_id") or "").strip()

        if intent:
            intent_counts[intent] = intent_counts.get(intent, 0) + 1
            if intent in required_intents:
                has_required_intent_from_citations = True
        if claim_id:
            claim_coverage.add(claim_id)

    return {
        "mode": claim_mode,
        "intent_counts": intent_counts,
        "claim_coverage_ids": sorted(claim_coverage),
        "citation_count": len(citations),
        "has_required_intent": has_required_intent_from_citations,
        "has_required_intent_from_topk": has_required_intent_from_topk,
        "has_required_intent_from_citations": has_required_intent_from_citations,
    }


def run(state: dict) -> dict:
    """Stage 8 실행: Stage9 판결을 위한 정제 패키지 생성."""
    trace_id = state.get("trace_id", "unknown")
    logger.info("[%s] Stage8 시작: 판정용 정제 패키지 생성", trace_id)

    claim_mode = str(state.get("claim_mode") or "fact").strip().lower() or "fact"
    support_verdict = _normalize_verdict(state.get("verdict_support", {}))
    skeptic_verdict = _normalize_verdict(state.get("verdict_skeptic", {}))
    evidence_topk = state.get("evidence_topk", [])
    evidence_topk_support = state.get("evidence_topk_support", [])
    evidence_topk_skeptic = state.get("evidence_topk_skeptic", [])
    merged_evidence: list[dict[str, Any]] = []
    for pool in (evidence_topk_support, evidence_topk_skeptic, evidence_topk):
        if isinstance(pool, list):
            for item in pool:
                if isinstance(item, dict):
                    merged_evidence.append(item)

    evidence_index = _build_evidence_index(merged_evidence)

    support_meta = _analysis_meta(support_verdict, evidence_index, claim_mode)
    skeptic_meta = _analysis_meta(skeptic_verdict, evidence_index, claim_mode)

    state["support_pack"] = {
        **support_verdict,
        "analysis_meta": support_meta,
    }
    state["skeptic_pack"] = {
        **skeptic_verdict,
        "analysis_meta": skeptic_meta,
    }
    state["evidence_index"] = evidence_index

    state["judge_prep_meta"] = {
        "support_citation_count": len(support_verdict.get("citations", [])),
        "skeptic_citation_count": len(skeptic_verdict.get("citations", [])),
        "support_has_citations": bool(support_verdict.get("citations")),
        "skeptic_has_citations": bool(skeptic_verdict.get("citations")),
        "claim_profile": {
            "claim_mode": claim_mode,
            "risk_markers": state.get("risk_markers", []),
            "verification_priority": state.get("verification_priority", "normal"),
        },
        "stage03_merge_stats": state.get("stage03_merge_stats", {}),
        "score_diagnostics": state.get("score_diagnostics", {}),
        "topk_diagnostics": state.get("topk_diagnostics", {}),
        "support_pool_count": len(evidence_topk_support) if isinstance(evidence_topk_support, list) else 0,
        "skeptic_pool_count": len(evidence_topk_skeptic) if isinstance(evidence_topk_skeptic, list) else 0,
    }

    logger.info(
        "[%s] Stage8 완료: support_cits=%d, skeptic_cits=%d, evidence_index=%d",
        trace_id,
        state["judge_prep_meta"]["support_citation_count"],
        state["judge_prep_meta"]["skeptic_citation_count"],
        len(evidence_index),
    )

    return state
