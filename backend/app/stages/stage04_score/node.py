"""Stage 4 - Score Evidence (Precision-first rerank)."""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any

from app.core.settings import settings
from app.services.wiki_retriever import calculate_hybrid_score, extract_keywords

logger = logging.getLogger(__name__)

_WIKI_TYPES = {"KNOWLEDGE_BASE", "KB_DOC", "WIKIPEDIA"}
_SOURCE_PRIOR = {
    "WIKIPEDIA": 0.72,
    "KNOWLEDGE_BASE": 0.72,
    "KB_DOC": 0.72,
    "NEWS": 0.64,
    "WEB_URL": 0.52,
    "WEB": 0.52,
}
_INTENT_BONUS = {
    "official_statement": 0.10,
    "fact_check": 0.10,
    "origin_trace": 0.06,
    "entity_profile": 0.03,
}


def _normalize_mode(value: Any) -> str:
    raw = str(value or "fact").strip().lower()
    if raw in {"fact", "rumor", "mixed"}:
        return raw
    if "rumor" in raw and "fact" in raw:
        return "mixed"
    if "rumor" in raw:
        return "rumor"
    return "fact"


def _clean_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _keyword_overlap(text: str, keywords: list[str]) -> float:
    if not text or not keywords:
        return 0.0
    source = text.lower()
    hits = sum(1 for keyword in keywords if keyword.lower() in source)
    return hits / max(1, len(keywords))


def _parse_datetime_maybe(value: Any):
    if not value:
        return None
    if isinstance(value, datetime):
        dt = value
    else:
        text = str(value).strip()
        if not text:
            return None
        try:
            dt = parsedate_to_datetime(text)
        except Exception:
            try:
                dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
            except Exception:
                return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _freshness_bonus(metadata: dict[str, Any]) -> float:
    dt = _parse_datetime_maybe(metadata.get("pub_date"))
    if dt is None:
        return 0.0
    age_days = (datetime.now(timezone.utc) - dt).total_seconds() / 86400.0
    if age_days < 0:
        age_days = 0.0
    if age_days <= 3:
        return 0.08
    if age_days <= 14:
        return 0.05
    if age_days <= 60:
        return 0.02
    return 0.0


def _credibility_values(metadata: dict[str, Any]) -> tuple[float, float, float, str]:
    source_trust = metadata.get("source_trust_score")
    html_signal = metadata.get("html_signal_score")
    credibility = metadata.get("credibility_score")
    source_tier = str(metadata.get("source_tier") or "unknown").strip().lower() or "unknown"

    try:
        source_trust_score = float(source_trust)
    except (TypeError, ValueError):
        source_trust_score = 0.55
    try:
        html_signal_score = float(html_signal)
    except (TypeError, ValueError):
        html_signal_score = 0.5
    try:
        credibility_score = float(credibility)
    except (TypeError, ValueError):
        credibility_score = (0.65 * source_trust_score) + (0.35 * html_signal_score)

    return (
        max(0.0, min(1.0, source_trust_score)),
        max(0.0, min(1.0, html_signal_score)),
        max(0.0, min(1.0, credibility_score)),
        source_tier,
    )


def _score_wiki_candidate(
    candidate: dict[str, Any],
    metadata: dict[str, Any],
    keywords: list[str],
    rumor_mode: bool,
) -> tuple[float, dict[str, Any]]:
    hit_for_score = {
        "title": candidate.get("title", "") or "",
        "content": candidate.get("content", "") or "",
        "dist": metadata.get("dist"),
        "lex_score": metadata.get("lex_score") or 0.0,
    }

    base = float(calculate_hybrid_score(hit=hit_for_score, keywords=keywords))
    intent = str(metadata.get("intent") or "").strip().lower()

    rumor_adjustment = 0.0
    if rumor_mode and intent in {"official_statement", "fact_check"}:
        rumor_adjustment += 0.05
    elif rumor_mode and intent == "origin_trace":
        rumor_adjustment += 0.02
    elif rumor_mode:
        rumor_adjustment -= 0.03

    source_trust_score, html_signal_score, _, source_tier = _credibility_values(metadata)
    weight = float(settings.stage4_credibility_adjust_weight_wiki)
    multiplier = 1.15 if rumor_mode else 1.0
    credibility_adjustment = weight * (source_trust_score - 0.5) * multiplier

    score = max(0.0, min(base + rumor_adjustment + credibility_adjustment, 1.0))
    return round(score, 4), {
        "hybrid_base": round(base, 4),
        "rumor_adjustment": round(rumor_adjustment, 4),
        "source_tier": source_tier,
        "source_trust_score": round(source_trust_score, 4),
        "html_signal_score": round(html_signal_score, 4),
        "credibility_adjustment": round(credibility_adjustment, 4),
    }


def _score_news_web_candidate(
    candidate: dict[str, Any],
    metadata: dict[str, Any],
    keywords: list[str],
    rumor_mode: bool,
) -> tuple[float, dict[str, Any]]:
    source_type = str(candidate.get("source_type") or "WEB_URL").upper()
    source_prior = _SOURCE_PRIOR.get(source_type, 0.5)

    title = _clean_text(candidate.get("title"))
    content = _clean_text(candidate.get("content"))

    title_overlap = _keyword_overlap(title, keywords)
    lexical_overlap = _keyword_overlap(content, keywords)

    intent = str(metadata.get("intent") or "").strip().lower()
    intent_bonus = _INTENT_BONUS.get(intent, 0.0)
    freshness_bonus = _freshness_bonus(metadata)

    rumor_penalty = 0.0
    if rumor_mode and source_type == "WEB_URL" and intent not in {"official_statement", "fact_check"}:
        rumor_penalty = 0.12

    relevance_base = (
        source_prior
        + (0.26 * lexical_overlap)
        + (0.24 * title_overlap)
        + intent_bonus
        + freshness_bonus
        - rumor_penalty
    )
    source_trust_score, html_signal_score, credibility_score, source_tier = _credibility_values(metadata)
    weight = float(settings.stage4_credibility_adjust_weight_news_web)
    multiplier = 1.15 if rumor_mode else 1.0
    credibility_adjustment = weight * (credibility_score - 0.5) * multiplier

    score = max(0.0, min(relevance_base + credibility_adjustment, 1.0))

    return round(score, 4), {
        "source_prior": round(source_prior, 4),
        "lexical_overlap": round(lexical_overlap, 4),
        "title_overlap": round(title_overlap, 4),
        "intent_bonus": round(intent_bonus, 4),
        "freshness_bonus": round(freshness_bonus, 4),
        "rumor_penalty": round(rumor_penalty, 4),
        "relevance_base": round(relevance_base, 4),
        "source_tier": source_tier,
        "source_trust_score": round(source_trust_score, 4),
        "html_signal_score": round(html_signal_score, 4),
        "credibility_adjustment": round(credibility_adjustment, 4),
    }


def run(state: dict) -> dict:
    """
    Stage 4 Main:
    1. Get evidence_candidates
    2. Score by source-aware precision heuristic
    3. Attach score_breakdown for tuning
    4. Sort descending
    """
    candidates = state.get("evidence_candidates", [])
    claim_text = state.get("claim_text", "")
    claim_mode = _normalize_mode(state.get("claim_mode"))
    rumor_mode = claim_mode in {"rumor", "mixed"}

    keywords = extract_keywords(claim_text)

    scored_evidence: list[dict[str, Any]] = []

    logger.info(
        "Stage 4 Start. Scoring %d candidates against claim='%s' mode=%s",
        len(candidates),
        claim_text,
        claim_mode,
    )

    for candidate in candidates:
        if not isinstance(candidate, dict):
            logger.warning("Stage 4: skipping non-dict candidate: %r", candidate)
            continue

        metadata = candidate.get("metadata") if isinstance(candidate.get("metadata"), dict) else {}
        source_type = str(candidate.get("source_type") or "").upper()

        if source_type in _WIKI_TYPES:
            score, breakdown = _score_wiki_candidate(candidate, metadata, keywords, rumor_mode)
        else:
            score, breakdown = _score_news_web_candidate(candidate, metadata, keywords, rumor_mode)

        scored_item = dict(candidate)
        scored_metadata = dict(metadata)
        scored_metadata["score_breakdown"] = breakdown
        scored_item["metadata"] = scored_metadata
        scored_item["score"] = score
        scored_evidence.append(scored_item)

    scored_evidence.sort(key=lambda item: float(item.get("score") or 0.0), reverse=True)

    threshold = settings.stage5_threshold_rumor if rumor_mode else settings.stage5_threshold_standard
    threshold_pass = sum(1 for item in scored_evidence if float(item.get("score") or 0.0) >= threshold)
    pass_rate = threshold_pass / len(scored_evidence) if scored_evidence else 0.0

    diagnostics = {
        "claim_mode": claim_mode,
        "threshold": round(float(threshold), 4),
        "threshold_pass_count": threshold_pass,
        "threshold_pass_rate": round(pass_rate, 4),
        "total_scored": len(scored_evidence),
    }

    logger.info("Stage 4 Complete. pass_rate=%.3f (%d/%d)", pass_rate, threshold_pass, len(scored_evidence))

    return {
        "scored_evidence": scored_evidence,
        "score_diagnostics": diagnostics,
        "evidence_candidates": None,
    }
