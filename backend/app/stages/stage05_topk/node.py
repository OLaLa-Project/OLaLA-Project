"""Stage 5 - Adaptive Top-K Selection & Formatting."""

from __future__ import annotations

import asyncio
import hashlib
import logging
from typing import Any
from urllib.parse import urlsplit

from app.core.async_utils import run_async_in_sync
from app.core.settings import settings
from app.services.web_rag_service import WebRAGService

logger = logging.getLogger(__name__)

SNIPPET_MAX_LENGTH = 500
_RUMOR_REQUIRED_INTENTS = {"official_statement", "fact_check"}


def _normalize_mode(value: Any) -> str:
    raw = str(value or "fact").strip().lower()
    if raw in {"fact", "rumor", "mixed"}:
        return raw
    if "rumor" in raw and "fact" in raw:
        return "mixed"
    if "rumor" in raw:
        return "rumor"
    return "fact"


def _generate_evid_id(url: str, title: str) -> str:
    """URL과 제목으로 고유 evid_id 생성."""
    key = f"{url}:{title}"
    return f"ev_{hashlib.md5(key.encode()).hexdigest()[:8]}"


def _create_snippet(content: str, max_length: int = SNIPPET_MAX_LENGTH) -> str:
    """content에서 snippet 생성."""
    content = (content or "").strip()
    if len(content) <= max_length:
        return content
    return content[:max_length] + "..."


def _domain_key(url: str) -> str:
    parsed = urlsplit(str(url or "").strip())
    netloc = (parsed.netloc or "").lower()
    if netloc.startswith("www."):
        netloc = netloc[4:]
    if not netloc and str(url).startswith("wiki://"):
        return "wiki"
    return netloc or "unknown"


def _candidate_meta(item: dict[str, Any]) -> dict[str, Any]:
    return item.get("metadata") if isinstance(item.get("metadata"), dict) else {}


def _candidate_claim_id(item: dict[str, Any]) -> str:
    meta = _candidate_meta(item)
    return str(meta.get("claim_id") or "").strip()


def _candidate_intent(item: dict[str, Any]) -> str:
    meta = _candidate_meta(item)
    return str(meta.get("intent") or "").strip().lower()


def _candidate_stance(item: dict[str, Any]) -> str:
    meta = _candidate_meta(item)
    stance = str(meta.get("stance") or "").strip().lower()
    if stance in {"support", "skeptic", "neutral"}:
        return stance
    return "neutral"


def _candidate_credibility(item: dict[str, Any]) -> float:
    meta = _candidate_meta(item)
    raw = meta.get("credibility_score")
    try:
        score = float(raw)
    except (TypeError, ValueError):
        return 0.5
    return max(0.0, min(1.0, score))


def _within_domain_cap(item: dict[str, Any], domain_counts: dict[str, int], cap: int) -> bool:
    if cap <= 0:
        return True
    domain = _domain_key(item.get("url", ""))
    return domain_counts.get(domain, 0) < cap


def _mark_selected(
    item: dict[str, Any],
    *,
    selected: list[dict[str, Any]],
    selected_ids: set[int],
    domain_counts: dict[str, int],
    covered_claims: set[str],
) -> None:
    selected.append(item)
    selected_ids.add(id(item))
    domain = _domain_key(item.get("url", ""))
    domain_counts[domain] = domain_counts.get(domain, 0) + 1
    claim_id = _candidate_claim_id(item)
    if claim_id:
        covered_claims.add(claim_id)


def _select_adaptive_topk(
    candidates: list[dict[str, Any]],
    *,
    target_k: int,
    domain_cap: int,
    rumor_mode: bool,
) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    selected_ids: set[int] = set()
    domain_counts: dict[str, int] = {}
    covered_claims: set[str] = set()

    ranked = sorted(candidates, key=lambda item: float(item.get("score") or 0.0), reverse=True)

    # 1) rumor/mixed 모드에서 official_statement/fact_check intent 최소 1개 우선 확보
    if rumor_mode:
        for candidate in ranked:
            if _candidate_intent(candidate) not in _RUMOR_REQUIRED_INTENTS:
                continue
            if not _within_domain_cap(candidate, domain_counts, domain_cap):
                continue
            _mark_selected(
                candidate,
                selected=selected,
                selected_ids=selected_ids,
                domain_counts=domain_counts,
                covered_claims=covered_claims,
            )
            break

    # 2) claim_id 커버리지 최소 1개(가능한 경우)
    claim_order: list[str] = []
    seen_claims: set[str] = set()
    for candidate in ranked:
        claim_id = _candidate_claim_id(candidate)
        if not claim_id or claim_id in seen_claims:
            continue
        seen_claims.add(claim_id)
        claim_order.append(claim_id)

    for claim_id in claim_order:
        if len(selected) >= target_k:
            break
        if claim_id in covered_claims:
            continue
        for candidate in ranked:
            if id(candidate) in selected_ids:
                continue
            if _candidate_claim_id(candidate) != claim_id:
                continue
            if not _within_domain_cap(candidate, domain_counts, domain_cap):
                continue
            _mark_selected(
                candidate,
                selected=selected,
                selected_ids=selected_ids,
                domain_counts=domain_counts,
                covered_claims=covered_claims,
            )
            break

    # 3) 남은 슬롯은 점수 순으로 채움 (도메인 cap 유지)
    for candidate in ranked:
        if len(selected) >= target_k:
            break
        if id(candidate) in selected_ids:
            continue
        if not _within_domain_cap(candidate, domain_counts, domain_cap):
            continue
        _mark_selected(
            candidate,
            selected=selected,
            selected_ids=selected_ids,
            domain_counts=domain_counts,
            covered_claims=covered_claims,
        )

    # 4) cap 때문에 target 미달이면 cap 완화해 점수순 보충
    if len(selected) < target_k:
        for candidate in ranked:
            if len(selected) >= target_k:
                break
            if id(candidate) in selected_ids:
                continue
            _mark_selected(
                candidate,
                selected=selected,
                selected_ids=selected_ids,
                domain_counts=domain_counts,
                covered_claims=covered_claims,
            )

    selected.sort(key=lambda item: float(item.get("score") or 0.0), reverse=True)
    return selected[:target_k]


def _merge_candidates(*groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    seen: set[int] = set()
    for group in groups:
        for item in group:
            marker = id(item)
            if marker in seen:
                continue
            seen.add(marker)
            merged.append(item)
    merged.sort(key=lambda item: float(item.get("score") or 0.0), reverse=True)
    return merged


def _compose_balanced_selection(
    support_selection: list[dict[str, Any]],
    skeptic_selection: list[dict[str, Any]],
    *,
    fallback_selection: list[dict[str, Any]],
    target_k: int,
) -> list[dict[str, Any]]:
    ordered: list[dict[str, Any]] = []
    seen: set[int] = set()
    support_ranked = sorted(support_selection, key=lambda item: float(item.get("score") or 0.0), reverse=True)
    skeptic_ranked = sorted(skeptic_selection, key=lambda item: float(item.get("score") or 0.0), reverse=True)
    support_idx = 0
    skeptic_idx = 0

    while len(ordered) < target_k and (support_idx < len(support_ranked) or skeptic_idx < len(skeptic_ranked)):
        if support_idx < len(support_ranked):
            candidate = support_ranked[support_idx]
            support_idx += 1
            if id(candidate) not in seen:
                seen.add(id(candidate))
                ordered.append(candidate)
                if len(ordered) >= target_k:
                    break
        if skeptic_idx < len(skeptic_ranked):
            candidate = skeptic_ranked[skeptic_idx]
            skeptic_idx += 1
            if id(candidate) not in seen:
                seen.add(id(candidate))
                ordered.append(candidate)

    for candidate in sorted(fallback_selection, key=lambda item: float(item.get("score") or 0.0), reverse=True):
        if len(ordered) >= target_k:
            break
        if id(candidate) in seen:
            continue
        seen.add(id(candidate))
        ordered.append(candidate)

    return ordered[:target_k]


def _derive_risk_flags(
    base_flags: list[str],
    *,
    selected: list[dict[str, Any]],
    support_selection: list[dict[str, Any]],
    skeptic_selection: list[dict[str, Any]],
    thresholded_count: int,
    target_k: int,
    rumor_mode: bool,
) -> list[str]:
    flags: list[str] = []
    for flag in base_flags:
        if isinstance(flag, str) and flag not in flags:
            flags.append(flag)

    if not selected or thresholded_count == 0 or len(selected) < max(2, min(target_k, 4)):
        if "LOW_EVIDENCE" not in flags:
            flags.append("LOW_EVIDENCE")

    if rumor_mode:
        has_required_intent = any(_candidate_intent(item) in _RUMOR_REQUIRED_INTENTS for item in selected)
        if not has_required_intent and "RUMOR_UNCONFIRMED" not in flags:
            flags.append("RUMOR_UNCONFIRMED")
        if not skeptic_selection and "NO_SKEPTIC_EVIDENCE" not in flags:
            flags.append("NO_SKEPTIC_EVIDENCE")
        support_count = len(support_selection)
        skeptic_count = len(skeptic_selection)
        if (
            support_count == 0
            or skeptic_count == 0
            or abs(support_count - skeptic_count) >= max(2, int(target_k / 2))
        ) and "UNBALANCED_STANCE_EVIDENCE" not in flags:
            flags.append("UNBALANCED_STANCE_EVIDENCE")

    domains = {_domain_key(item.get("url", "")) for item in selected if item.get("url")}
    if len(selected) >= 2 and len(domains) <= 1 and "LOW_SOURCE_DIVERSITY" not in flags:
        flags.append("LOW_SOURCE_DIVERSITY")

    return flags


def _clamp_threshold(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _resolve_base_threshold(claim_mode: str) -> float:
    if claim_mode == "fact":
        return _clamp_threshold(settings.stage5_threshold_standard)
    if claim_mode == "mixed":
        return _clamp_threshold(settings.stage5_threshold_mixed)
    return _clamp_threshold(settings.stage5_threshold_rumor)


def _resolve_threshold_floor(claim_mode: str, base_threshold: float) -> float:
    if claim_mode == "mixed":
        floor = _clamp_threshold(settings.stage5_threshold_backoff_min_mixed)
    elif claim_mode == "rumor":
        floor = _clamp_threshold(settings.stage5_threshold_backoff_min_rumor)
    else:
        floor = base_threshold
    return min(base_threshold, floor)


def _filter_thresholded(scored: list[dict[str, Any]], threshold: float) -> list[dict[str, Any]]:
    return [
        item
        for item in scored
        if isinstance(item, dict) and float(item.get("score") or 0.0) >= threshold
    ]


def _apply_threshold_backoff(
    scored: list[dict[str, Any]],
    *,
    claim_mode: str,
    base_threshold: float,
    threshold_floor: float,
    threshold_target_min: int,
) -> tuple[list[dict[str, Any]], float, int]:
    threshold = base_threshold
    thresholded = _filter_thresholded(scored, threshold)
    backoff_steps = 0

    if claim_mode not in {"rumor", "mixed"}:
        return thresholded, threshold, backoff_steps

    step = max(0.0, float(settings.stage5_threshold_backoff_step))
    if step <= 0.0:
        return thresholded, threshold, backoff_steps

    while len(thresholded) < threshold_target_min and threshold > (threshold_floor + 1e-9):
        next_threshold = max(threshold_floor, threshold - step)
        if next_threshold >= threshold:
            break
        threshold = next_threshold
        thresholded = _filter_thresholded(scored, threshold)
        backoff_steps += 1
        if threshold <= (threshold_floor + 1e-9):
            break

    return thresholded, threshold, backoff_steps


def _apply_threshold_failopen(
    scored: list[dict[str, Any]],
    thresholded: list[dict[str, Any]],
    *,
    claim_mode: str,
    target_k: int,
) -> tuple[list[dict[str, Any]], bool, int]:
    if claim_mode not in {"rumor", "mixed"}:
        return thresholded, False, 0
    if not bool(settings.stage5_failopen_enabled):
        return thresholded, False, 0

    min_items = max(1, min(target_k, int(settings.stage5_failopen_min_items)))
    if len(thresholded) >= min_items:
        return thresholded, False, 0

    min_score = _clamp_threshold(settings.stage5_failopen_min_score)
    rescue_pool = [
        item
        for item in scored
        if isinstance(item, dict) and float(item.get("score") or 0.0) >= min_score
    ]
    rescue_pool.sort(key=lambda item: float(item.get("score") or 0.0), reverse=True)
    need = max(0, min_items - len(thresholded))
    rescued = rescue_pool[:need]
    if not rescued:
        return thresholded, False, 0
    return _merge_candidates(thresholded, rescued), True, len(rescued)


async def run_async(state: dict) -> dict:
    """Stage 5 Main (Async)."""
    scored = state.get("scored_evidence", [])
    claim_text = state.get("claim_text", "")
    claim_mode = _normalize_mode(state.get("claim_mode"))
    rumor_mode = claim_mode in {"rumor", "mixed"}

    target_k = int(settings.stage5_topk_rumor if rumor_mode else settings.stage5_topk_standard)
    support_target_k = max(1, int(settings.stage5_topk_support))
    skeptic_target_k = max(1, int(settings.stage5_topk_skeptic))
    domain_cap = max(0, int(settings.stage5_domain_cap))
    soft_split_enabled = bool(settings.stage5_soft_split_enabled)
    shared_trust_min = float(settings.stage5_shared_trust_min)
    base_threshold = _resolve_base_threshold(claim_mode)
    threshold_floor = _resolve_threshold_floor(claim_mode, base_threshold)
    threshold_target_min = max(1, min(target_k, int(settings.stage5_threshold_backoff_target_min)))
    thresholded, threshold, threshold_backoff_steps = _apply_threshold_backoff(
        scored,
        claim_mode=claim_mode,
        base_threshold=base_threshold,
        threshold_floor=threshold_floor,
        threshold_target_min=threshold_target_min,
    )
    thresholded, threshold_failopen_used, threshold_failopen_added = _apply_threshold_failopen(
        scored,
        thresholded,
        claim_mode=claim_mode,
        target_k=target_k,
    )

    logger.info(
        "Stage 5 Start. candidates=%d mode=%s base_threshold=%.2f threshold=%.2f target_k=%d domain_cap=%d",
        len(scored),
        claim_mode,
        base_threshold,
        threshold,
        target_k,
        domain_cap,
    )

    support_pool = [item for item in thresholded if _candidate_stance(item) == "support"]
    skeptic_pool = [item for item in thresholded if _candidate_stance(item) == "skeptic"]
    neutral_pool = [item for item in thresholded if _candidate_stance(item) == "neutral"]
    shared_pool = [item for item in neutral_pool if _candidate_credibility(item) >= shared_trust_min]

    final_selection = _select_adaptive_topk(
        thresholded,
        target_k=target_k,
        domain_cap=domain_cap,
        rumor_mode=rumor_mode,
    )

    if soft_split_enabled:
        support_selection = _select_adaptive_topk(
            _merge_candidates(support_pool, shared_pool),
            target_k=support_target_k,
            domain_cap=domain_cap,
            rumor_mode=rumor_mode,
        )
        skeptic_selection = _select_adaptive_topk(
            _merge_candidates(skeptic_pool, shared_pool),
            target_k=skeptic_target_k,
            domain_cap=domain_cap,
            rumor_mode=rumor_mode,
        )
        if not support_selection:
            support_selection = list(final_selection[:support_target_k])
    else:
        support_selection = list(final_selection)
        skeptic_selection = list(final_selection)

    skeptic_rescued_count = 0
    if soft_split_enabled and rumor_mode and bool(settings.stage5_skeptic_rescue_enabled) and not skeptic_selection:
        rescue_min_score = _clamp_threshold(settings.stage5_skeptic_rescue_min_score)
        rescue_max_items = max(1, int(settings.stage5_skeptic_rescue_max_items))
        skeptic_rescue_pool = [
            item
            for item in scored
            if isinstance(item, dict)
            and _candidate_stance(item) == "skeptic"
            and float(item.get("score") or 0.0) >= rescue_min_score
        ]
        skeptic_selection = _select_adaptive_topk(
            skeptic_rescue_pool,
            target_k=min(skeptic_target_k, rescue_max_items),
            domain_cap=domain_cap,
            rumor_mode=False,
        )
        skeptic_rescued_count = len(skeptic_selection)

    if soft_split_enabled and rumor_mode:
        final_selection = _compose_balanced_selection(
            support_selection,
            skeptic_selection,
            fallback_selection=final_selection,
            target_k=target_k,
        )

    citation_index: dict[str, dict[str, Any]] = {}
    enrichment_tasks = []
    all_selected = _merge_candidates(final_selection, support_selection, skeptic_selection)

    for item in all_selected:
        url = str(item.get("url") or "")
        title = str(item.get("title") or "")
        content = str(item.get("content") or "")
        source_type = str(item.get("source_type") or "WEB")
        metadata = _candidate_meta(item)
        evid_id = _generate_evid_id(url, title)
        if evid_id in citation_index:
            continue

        citation = {
            "evid_id": evid_id,
            "source_type": source_type,
            "title": title,
            "url": url,
            "content": content,
            "snippet": _create_snippet(content),
            "score": float(item.get("score") or 0.0),
            "relevance": float(item.get("score") or 0.0),
            "metadata": metadata,
        }

        if source_type in {"WEB_URL", "NEWS", "WEB"} and url:
            enrichment_tasks.append(WebRAGService.enrich_citation(citation, claim_text))

        citation_index[evid_id] = citation

    if enrichment_tasks:
        logger.info("Stage 5: Enriching %d citations with Web RAG...", len(enrichment_tasks))
        await asyncio.gather(*enrichment_tasks)

    for citation in citation_index.values():
        citation["snippet"] = _create_snippet(str(citation.get("snippet") or ""))

    def _selection_to_citations(selection: list[dict[str, Any]]) -> list[dict[str, Any]]:
        ordered: list[dict[str, Any]] = []
        seen: set[str] = set()
        for item in selection:
            evid_id = _generate_evid_id(str(item.get("url") or ""), str(item.get("title") or ""))
            if evid_id in seen:
                continue
            citation = citation_index.get(evid_id)
            if citation is None:
                continue
            seen.add(evid_id)
            ordered.append(citation)
        return ordered

    citations = _selection_to_citations(final_selection)
    support_citations = _selection_to_citations(support_selection)
    skeptic_citations = _selection_to_citations(skeptic_selection)

    risk_flags = _derive_risk_flags(
        state.get("risk_flags", []) if isinstance(state.get("risk_flags"), list) else [],
        selected=final_selection,
        support_selection=support_selection,
        skeptic_selection=skeptic_selection,
        thresholded_count=len(thresholded),
        target_k=target_k,
        rumor_mode=rumor_mode,
    )
    if skeptic_rescued_count > 0 and "SKEPTIC_RESCUE_USED" not in risk_flags:
        risk_flags.append("SKEPTIC_RESCUE_USED")
    if threshold_failopen_used and "THRESHOLD_FAILOPEN_USED" not in risk_flags:
        risk_flags.append("THRESHOLD_FAILOPEN_USED")

    def _avg_trust(items: list[dict[str, Any]]) -> float:
        if not items:
            return 0.0
        total = sum(_candidate_credibility(item) for item in items)
        return round(total / len(items), 4)

    diagnostics = {
        "claim_mode": claim_mode,
        "threshold": round(threshold, 4),
        "base_threshold": round(base_threshold, 4),
        "threshold_floor": round(threshold_floor, 4),
        "threshold_target_min": threshold_target_min,
        "threshold_backoff_steps": threshold_backoff_steps,
        "threshold_backoff_applied": bool(threshold_backoff_steps > 0),
        "threshold_failopen_used": threshold_failopen_used,
        "threshold_failopen_added": threshold_failopen_added,
        "thresholded_count": len(thresholded),
        "selected_k": len(citations),
        "target_k": target_k,
        "domain_diversity": len({_domain_key(c.get("url", "")) for c in citations if c.get("url")}),
        "soft_split_enabled": soft_split_enabled,
        "support_pool_size": len(support_pool),
        "skeptic_pool_size": len(skeptic_pool),
        "neutral_pool_size": len(neutral_pool),
        "shared_pool_size": len(shared_pool),
        "support_selected_k": len(support_citations),
        "skeptic_selected_k": len(skeptic_citations),
        "support_target_k": support_target_k,
        "skeptic_target_k": skeptic_target_k,
        "support_avg_trust": _avg_trust(support_selection),
        "skeptic_avg_trust": _avg_trust(skeptic_selection),
        "skeptic_rescued_count": skeptic_rescued_count,
        "balanced_selection_used": bool(soft_split_enabled and rumor_mode),
    }

    logger.info("Stage 5 Complete. selected=%d flags=%s", len(citations), risk_flags)

    return {
        "citations": citations,
        "evidence_topk": citations,
        "evidence_topk_support": support_citations,
        "evidence_topk_skeptic": skeptic_citations,
        "scored_evidence": None,
        "risk_flags": risk_flags,
        "topk_diagnostics": diagnostics,
    }


def run(state: dict) -> dict:
    """Sync wrapper for Stage 5."""
    return run_async_in_sync(run_async, state)
