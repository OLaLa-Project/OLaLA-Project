"""
Stage 9 - Judge (LLM 기반 최종 판정 + 사용자 친화적 결과 생성)

Stage6/7의 상반된 결과를 직접 비교하고,
별도 retrieval 근거를 함께 검토해 TRUE/FALSE 판결을 내립니다.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

from app.core.settings import settings
from app.db.session import SessionLocal
from app.services.rag_usecase import retrieve_wiki_context
from app.stages._shared.guardrails import parse_judge_json_with_retry, validate_judge_output
from app.stages._shared.orchestrator_runtime import (
    CircuitBreaker,
    CircuitBreakerConfig,
    OrchestratorError,
    OrchestratorRuntime,
    RetryConfig,
    RetryPolicy,
)

logger = logging.getLogger(__name__)

PROMPT_FILE = Path(__file__).parent / "prompt_judge.txt"


@dataclass
class LLMConfig:
    """Stage9 LLM 호출 설정."""

    base_url: str = "https://api.openai.com/v1"
    api_key: str = ""
    model: str = "gpt-4.1"
    timeout_seconds: int = 60
    max_tokens: int = 1024
    temperature: float = 0.2

    @classmethod
    def from_env(cls) -> "LLMConfig":
        return cls(
            base_url=settings.judge_base_url,
            api_key=settings.judge_api_key,
            model=settings.judge_model,
            timeout_seconds=settings.judge_timeout_seconds,
            max_tokens=settings.judge_max_tokens,
            temperature=settings.judge_temperature,
        )


@lru_cache(maxsize=1)
def load_system_prompt() -> str:
    return PROMPT_FILE.read_text(encoding="utf-8")


_llm_runtime: Optional[OrchestratorRuntime] = None
_llm_config: Optional[LLMConfig] = None


def _get_llm_config() -> LLMConfig:
    global _llm_config
    if _llm_config is None:
        _llm_config = LLMConfig.from_env()
    return _llm_config


def _get_llm_runtime() -> OrchestratorRuntime:
    global _llm_runtime
    if _llm_runtime is None:
        circuit_config = CircuitBreakerConfig(
            failure_threshold=3,
            timeout_seconds=60,
            success_threshold=2,
        )
        retry_config = RetryConfig(
            max_retries=2,
            base_delay=1.0,
            max_delay=10.0,
        )
        retry_policy = RetryPolicy(retry_config)
        retry_policy.add_retryable_exception(requests.exceptions.Timeout)
        retry_policy.add_retryable_exception(requests.exceptions.ConnectionError)
        _llm_runtime = OrchestratorRuntime(
            name="llm",
            circuit_breaker=CircuitBreaker(name="llm", config=circuit_config),
            retry_policy=retry_policy,
        )
    return _llm_runtime


def _call_llm(system_prompt: str, user_prompt: str, **kwargs) -> str:
    config = _get_llm_config()
    from app.stages._shared.slm_client import SLMClient, SLMConfig

    slm_config = SLMConfig(
        base_url=config.base_url,
        api_key=config.api_key or "ollama",
        model=config.model,
        timeout=config.timeout_seconds,
        max_tokens=config.max_tokens,
        temperature=kwargs.get("temperature", config.temperature),
        stream_enabled=settings.slm_stream_enabled,
        stream_connect_timeout_seconds=settings.slm_stream_connect_timeout_seconds,
        stream_read_timeout_seconds=settings.slm_stream_read_timeout_seconds,
        stream_hard_timeout_seconds=settings.slm_stream_hard_timeout_seconds,
    )

    client = SLMClient(slm_config)
    return client.chat_completion(system_prompt, user_prompt, temperature=slm_config.temperature)


def _normalize_mode(value: Any) -> str:
    raw = str(value or "fact").strip().lower()
    if raw in {"fact", "rumor", "mixed"}:
        return raw
    if "rumor" in raw and "fact" in raw:
        return "mixed"
    if "rumor" in raw:
        return "rumor"
    return "fact"


def _required_intents() -> set[str]:
    raw = str(settings.stage6_rumor_required_intents_csv or "").strip()
    if not raw:
        return {"official_statement", "fact_check"}
    intents = {token.strip().lower() for token in raw.split(",") if token.strip()}
    return intents or {"official_statement", "fact_check"}


def _judge_wiki_retrieval_policy(claim_mode: str) -> tuple[bool, int]:
    mode = _normalize_mode(claim_mode)
    if mode in {"rumor", "mixed"}:
        enabled = bool(settings.stage9_wiki_retrieval_enabled_rumor)
        top_k = max(0, int(settings.stage9_wiki_retrieval_top_k_rumor))
        return enabled and top_k > 0, top_k
    top_k = max(0, int(settings.stage9_wiki_retrieval_top_k_fact))
    return top_k > 0, top_k


def _retrieve_judge_evidence(claim_text: str, search_mode: str, claim_mode: str) -> List[Dict[str, Any]]:
    if not (claim_text or "").strip():
        return []

    enabled, top_k = _judge_wiki_retrieval_policy(claim_mode)
    if not enabled:
        return []

    try:
        with SessionLocal() as db:
            pack = retrieve_wiki_context(
                db=db,
                question=claim_text,
                top_k=top_k,
                page_limit=max(1, top_k),
                window=2,
                embed_missing=False,
                search_mode=search_mode or "auto",
            )
    except Exception as e:
        logger.warning("Judge retrieval 실패: %s", e)
        return []

    sources: list[dict[str, Any]] = []
    for i, src in enumerate(pack.get("sources", []), start=1):
        evid_id = f"judge_wiki_{i}"
        sources.append(
            {
                "evid_id": evid_id,
                "source_type": "WIKIPEDIA",
                "title": src.get("title", ""),
                "url": f"wiki://page/{src.get('page_id')}" if src.get("page_id") else "",
                "snippet": src.get("snippet", ""),
                "intent": "entity_profile",
                "claim_id": "",
                "mode": _normalize_mode(claim_mode),
                "pre_score": None,
                "source_domain": "wiki",
            }
        )

    return sources


def _build_evidence_index(evidence_index: Dict[str, Any], retrieval_sources: List[Dict[str, Any]]) -> Dict[str, Any]:
    merged = dict(evidence_index or {})
    for source in retrieval_sources:
        evid_id = source.get("evid_id")
        if evid_id and evid_id not in merged:
            merged[evid_id] = {
                "evid_id": evid_id,
                "title": source.get("title", ""),
                "url": source.get("url", ""),
                "snippet": source.get("snippet", ""),
                "source_type": source.get("source_type", "WIKIPEDIA"),
                "intent": source.get("intent", ""),
                "claim_id": source.get("claim_id", ""),
                "mode": source.get("mode", "fact"),
                "pre_score": source.get("pre_score"),
                "source_domain": source.get("source_domain", "wiki"),
            }
    return merged


def _build_citation_index(
    support_pack: Dict[str, Any],
    skeptic_pack: Dict[str, Any],
    retrieval_sources: List[Dict[str, Any]],
) -> Dict[str, Dict[str, Any]]:
    index: Dict[str, Dict[str, Any]] = {}

    for citation in (support_pack.get("citations", []) or []) + (skeptic_pack.get("citations", []) or []):
        evid_id = citation.get("evid_id")
        if not evid_id:
            continue
        index[evid_id] = {
            "evid_id": evid_id,
            "title": citation.get("title", ""),
            "url": citation.get("url", ""),
            "quote": citation.get("quote", ""),
        }

    for source in retrieval_sources:
        evid_id = source.get("evid_id")
        if not evid_id:
            continue
        index.setdefault(
            evid_id,
            {
                "evid_id": evid_id,
                "title": source.get("title", ""),
                "url": source.get("url", ""),
                "quote": source.get("snippet", ""),
            },
        )

    return index


def _truncate_text(value: Any, max_chars: int) -> str:
    text = str(value or "").strip()
    if max_chars <= 0:
        return ""
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rstrip() + "..."


def _compact_citations_for_prompt(
    citations: Any,
    *,
    citation_limit: int,
    text_limit: int,
) -> List[Dict[str, Any]]:
    if not isinstance(citations, list):
        return []
    compact: list[dict[str, Any]] = []
    for item in citations:
        if not isinstance(item, dict):
            continue
        compact.append(
            {
                "evid_id": str(item.get("evid_id") or "").strip(),
                "title": _truncate_text(item.get("title", ""), text_limit),
                "url": _truncate_text(item.get("url", ""), text_limit),
                "quote": _truncate_text(item.get("quote", ""), text_limit),
            }
        )
        if len(compact) >= citation_limit:
            break
    return compact


def _compact_pack_for_prompt(
    pack: Dict[str, Any],
    *,
    citation_limit: int,
    text_limit: int,
) -> Dict[str, Any]:
    reasoning = pack.get("reasoning_bullets") if isinstance(pack.get("reasoning_bullets"), list) else []
    weak_points = pack.get("weak_points") if isinstance(pack.get("weak_points"), list) else []
    analysis_meta = pack.get("analysis_meta") if isinstance(pack.get("analysis_meta"), dict) else {}
    confidence_raw = pack.get("confidence", 0.0)
    try:
        confidence = float(confidence_raw)
    except (TypeError, ValueError):
        confidence = 0.0
    citation_count_raw = analysis_meta.get("citation_count", 0)
    try:
        citation_count = int(citation_count_raw)
    except (TypeError, ValueError):
        citation_count = 0

    compact_meta = {
        "mode": str(analysis_meta.get("mode") or "").strip(),
        "citation_count": citation_count,
        "has_required_intent": bool(analysis_meta.get("has_required_intent")),
        "claim_coverage_ids": [
            str(item).strip()
            for item in (analysis_meta.get("claim_coverage_ids") or [])
            if str(item).strip()
        ][:3],
    }
    intent_counts = analysis_meta.get("intent_counts")
    if isinstance(intent_counts, dict) and intent_counts:
        compact_meta["intent_counts"] = {
            str(key): int(value)
            for key, value in intent_counts.items()
            if isinstance(key, str) and isinstance(value, (int, float))
        }

    citation_ids: list[str] = []
    raw_citations = pack.get("citations")
    if isinstance(raw_citations, list):
        for citation in raw_citations:
            if not isinstance(citation, dict):
                continue
            evid_id = str(citation.get("evid_id") or "").strip()
            if not evid_id:
                continue
            citation_ids.append(evid_id)
            if len(citation_ids) >= citation_limit:
                break

    return {
        "stance": str(pack.get("stance") or "UNVERIFIED").strip().upper(),
        "confidence": confidence,
        "reasoning_bullets": [_truncate_text(item, text_limit) for item in reasoning][:2],
        "weak_points": [_truncate_text(item, text_limit) for item in weak_points][:2],
        "citation_ids": citation_ids,
        "has_citations": bool(citation_ids),
        "analysis_meta": compact_meta,
    }


def _compact_judge_prep_meta_for_prompt(judge_prep_meta: Dict[str, Any]) -> Dict[str, Any]:
    claim_profile = judge_prep_meta.get("claim_profile") if isinstance(judge_prep_meta.get("claim_profile"), dict) else {}
    score_diag = judge_prep_meta.get("score_diagnostics") if isinstance(judge_prep_meta.get("score_diagnostics"), dict) else {}
    topk_diag = judge_prep_meta.get("topk_diagnostics") if isinstance(judge_prep_meta.get("topk_diagnostics"), dict) else {}
    merge_stats = judge_prep_meta.get("stage03_merge_stats") if isinstance(judge_prep_meta.get("stage03_merge_stats"), dict) else {}

    return {
        "support_citation_count": int(judge_prep_meta.get("support_citation_count") or 0),
        "skeptic_citation_count": int(judge_prep_meta.get("skeptic_citation_count") or 0),
        "claim_profile": {
            "claim_mode": str(claim_profile.get("claim_mode") or "").strip(),
            "verification_priority": str(claim_profile.get("verification_priority") or "").strip(),
            "risk_markers": claim_profile.get("risk_markers", []) if isinstance(claim_profile.get("risk_markers"), list) else [],
        },
        "score_diagnostics": {
            "threshold": score_diag.get("threshold"),
            "threshold_pass_count": score_diag.get("threshold_pass_count"),
            "total_scored": score_diag.get("total_scored"),
        },
        "topk_diagnostics": {
            "selected_k": topk_diag.get("selected_k"),
            "target_k": topk_diag.get("target_k"),
            "support_selected_k": topk_diag.get("support_selected_k"),
            "skeptic_selected_k": topk_diag.get("skeptic_selected_k"),
            "support_avg_trust": topk_diag.get("support_avg_trust"),
            "skeptic_avg_trust": topk_diag.get("skeptic_avg_trust"),
            "domain_diversity": topk_diag.get("domain_diversity"),
        },
        "stage03_merge_stats": {
            "after_cap": merge_stats.get("after_cap"),
            "source_mix": merge_stats.get("source_mix"),
            "low_quality_filtered": merge_stats.get("low_quality_filtered"),
        },
    }


def _evidence_rank_score(evidence: Dict[str, Any]) -> tuple[float, float]:
    pre_score_raw = evidence.get("pre_score")
    if pre_score_raw is None and isinstance(evidence.get("metadata"), dict):
        pre_score_raw = evidence["metadata"].get("pre_score")
    trust_raw = evidence.get("credibility_score")
    if trust_raw is None and isinstance(evidence.get("metadata"), dict):
        trust_raw = evidence["metadata"].get("credibility_score")
    try:
        pre_score = float(pre_score_raw)
    except (TypeError, ValueError):
        pre_score = 0.0
    try:
        trust = float(trust_raw)
    except (TypeError, ValueError):
        trust = 0.5
    return pre_score, trust


def _select_prompt_evidence_ids(
    evidence_index: Dict[str, Any],
    support_pack: Dict[str, Any],
    skeptic_pack: Dict[str, Any],
    retrieval_sources: List[Dict[str, Any]],
    *,
    max_items: int,
) -> List[str]:
    if max_items <= 0 or not isinstance(evidence_index, dict):
        return []

    selected: list[str] = []
    seen: set[str] = set()

    def _add(evid_id: Any) -> None:
        key = str(evid_id or "").strip()
        if not key or key in seen:
            return
        if key not in evidence_index:
            return
        seen.add(key)
        selected.append(key)

    for pack in (support_pack, skeptic_pack):
        citations = pack.get("citations") if isinstance(pack.get("citations"), list) else []
        for citation in citations:
            if isinstance(citation, dict):
                _add(citation.get("evid_id"))
            if len(selected) >= max_items:
                return selected[:max_items]

    for source in retrieval_sources:
        if isinstance(source, dict):
            _add(source.get("evid_id"))
        if len(selected) >= max_items:
            return selected[:max_items]

    remainder = [
        (str(evid_id), evidence)
        for evid_id, evidence in evidence_index.items()
        if isinstance(evidence, dict) and str(evid_id) not in seen
    ]
    remainder.sort(key=lambda item: _evidence_rank_score(item[1]), reverse=True)
    for evid_id, _ in remainder:
        selected.append(evid_id)
        if len(selected) >= max_items:
            break
    return selected[:max_items]


def _compact_evidence_for_prompt(
    evidence_index: Dict[str, Any],
    support_pack: Dict[str, Any],
    skeptic_pack: Dict[str, Any],
    retrieval_sources: List[Dict[str, Any]],
    *,
    max_items: int,
    snippet_max_chars: int,
) -> Dict[str, Any]:
    selected_ids = _select_prompt_evidence_ids(
        evidence_index,
        support_pack,
        skeptic_pack,
        retrieval_sources,
        max_items=max_items,
    )
    compact: dict[str, Any] = {}
    for evid_id in selected_ids:
        evidence = evidence_index.get(evid_id, {})
        if not isinstance(evidence, dict):
            continue
        metadata = evidence.get("metadata") if isinstance(evidence.get("metadata"), dict) else {}
        query_stance = str(
            evidence.get("query_stance")
            or metadata.get("stance")
            or "neutral"
        ).strip().lower()
        compact[evid_id] = {
            "evid_id": evid_id,
            "source_type": str(evidence.get("source_type") or ""),
            "title": _truncate_text(evidence.get("title", ""), snippet_max_chars),
            "url": _truncate_text(evidence.get("url", ""), snippet_max_chars),
            "snippet": _truncate_text(evidence.get("snippet", ""), snippet_max_chars),
            "intent": str(evidence.get("intent") or "").strip().lower(),
            "claim_id": str(evidence.get("claim_id") or "").strip(),
            "mode": str(evidence.get("mode") or "").strip().lower(),
            "query_stance": query_stance if query_stance in {"support", "skeptic", "neutral"} else "neutral",
            "pre_score": evidence.get("pre_score"),
            "credibility_score": evidence.get("credibility_score"),
            "source_tier": evidence.get("source_tier"),
            "source_domain": evidence.get("source_domain"),
        }
    return compact


def _compact_retrieval_for_prompt(
    retrieval_sources: List[Dict[str, Any]],
    *,
    max_items: int,
    snippet_max_chars: int,
) -> List[Dict[str, Any]]:
    compact: list[dict[str, Any]] = []
    if max_items <= 0:
        return compact
    for source in retrieval_sources:
        if not isinstance(source, dict):
            continue
        compact.append(
            {
                "evid_id": str(source.get("evid_id") or "").strip(),
                "source_type": str(source.get("source_type") or "WIKIPEDIA"),
                "title": _truncate_text(source.get("title", ""), snippet_max_chars),
                "url": _truncate_text(source.get("url", ""), snippet_max_chars),
                "snippet": _truncate_text(source.get("snippet", ""), snippet_max_chars),
            }
        )
        if len(compact) >= max_items:
            break
    return compact


def _build_judge_user_prompt(
    claim_text: str,
    support_pack: Dict[str, Any],
    skeptic_pack: Dict[str, Any],
    evidence_index: Dict[str, Any],
    retrieval_sources: List[Dict[str, Any]],
    language: str,
    claim_profile: Dict[str, Any],
    judge_prep_meta: Dict[str, Any],
) -> str:
    citation_limit = max(1, int(settings.stage9_prompt_pack_citation_limit))
    text_limit = max(80, int(settings.stage9_prompt_pack_text_max_chars))

    compact_support = _compact_pack_for_prompt(
        support_pack,
        citation_limit=citation_limit,
        text_limit=text_limit,
    )
    compact_skeptic = _compact_pack_for_prompt(
        skeptic_pack,
        citation_limit=citation_limit,
        text_limit=text_limit,
    )
    compact_prep_meta = _compact_judge_prep_meta_for_prompt(judge_prep_meta)

    support_str = json.dumps(compact_support, ensure_ascii=False, indent=2)
    skeptic_str = json.dumps(compact_skeptic, ensure_ascii=False, indent=2)
    claim_profile_str = json.dumps(claim_profile, ensure_ascii=False, indent=2)
    prep_meta_str = json.dumps(compact_prep_meta, ensure_ascii=False, indent=2)

    return f"""## 검증 대상 주장
{claim_text}

## claim_profile
{claim_profile_str}

## Stage8 (집계) 요약
{prep_meta_str}

## Stage6 (지지) 결과
{support_str}

## Stage7 (회의) 결과
{skeptic_str}

## 요청
위 정보를 바탕으로 최종 판결을 TRUE 또는 FALSE 중 하나로 결정하고,
지정된 JSON 형식으로 결과를 출력하세요.
언어: {language}
"""


def _build_evidence_summary(selected_ids: List[str], evidence_index: Dict[str, Any]) -> List[Dict[str, Any]]:
    summary: list[dict[str, Any]] = []
    for evid_id in selected_ids[:3]:
        evidence = evidence_index.get(evid_id, {})
        summary.append(
            {
                "point": (evidence.get("snippet", "") or "")[:100],
                "source_title": evidence.get("title", ""),
                "source_url": evidence.get("url", ""),
            }
        )
    return summary


def _sorted_evidence_ids(evidence_index: Dict[str, Any]) -> List[str]:
    ranked: list[tuple[float, str]] = []
    for evid_id, evidence in (evidence_index or {}).items():
        if not isinstance(evidence, dict):
            continue
        score_raw = evidence.get("pre_score")
        if score_raw is None and isinstance(evidence.get("metadata"), dict):
            score_raw = evidence["metadata"].get("pre_score")
        try:
            score = float(score_raw)
        except (TypeError, ValueError):
            score = 0.0
        ranked.append((score, str(evid_id)))
    ranked.sort(key=lambda item: item[0], reverse=True)
    return [evid_id for _, evid_id in ranked]


def _recover_selected_ids_from_evidence(
    evidence_index: Dict[str, Any],
    claim_mode: str,
    select_k: int,
) -> List[str]:
    if not isinstance(evidence_index, dict) or not evidence_index:
        return []

    ranked_ids = _sorted_evidence_ids(evidence_index)
    if not ranked_ids:
        return []

    mode = _normalize_mode(claim_mode)
    required_intents = _required_intents()
    selected: list[str] = []

    for evid_id in ranked_ids:
        if len(selected) >= select_k:
            break
        evidence = evidence_index.get(evid_id, {})
        intent = str((evidence or {}).get("intent") or "").strip().lower()
        if mode in {"rumor", "mixed"} and intent not in required_intents:
            continue
        selected.append(evid_id)

    if selected:
        return selected[:select_k]

    for evid_id in ranked_ids:
        if len(selected) >= select_k:
            break
        selected.append(evid_id)
    return selected[:select_k]


def _is_placeholder_evidence_id(evid_id: str) -> bool:
    token = str(evid_id or "").strip().lower()
    if not token:
        return True
    if "xxxxx" in token:
        return True
    if token.startswith("ev_x"):
        return True
    return False


def _extract_verified_citation_ids(pack: Dict[str, Any], evidence_index: Dict[str, Any]) -> List[str]:
    verified: list[str] = []
    seen: set[str] = set()
    citations = pack.get("citations") if isinstance(pack.get("citations"), list) else []
    for citation in citations:
        if not isinstance(citation, dict):
            continue
        evid_id = str(citation.get("evid_id") or "").strip()
        if (
            not evid_id
            or evid_id in seen
            or _is_placeholder_evidence_id(evid_id)
            or evid_id not in evidence_index
        ):
            continue
        seen.add(evid_id)
        verified.append(evid_id)
    return verified


def _has_label_explanation_contradiction(label: str, explanation: str) -> bool:
    text = str(explanation or "").strip().lower()
    if not text:
        return False

    true_negative_markers = (
        "사실이 아닙니다",
        "거짓",
        "허위",
        "검증되지",
        "확인되지",
        "근거가 부족",
        "근거가 없습니다",
        "판단하기 어렵",
    )
    false_positive_markers = (
        "사실입니다",
        "사실로 확인",
        "사실로 판단",
        "맞습니다",
        "참입니다",
    )

    if label == "TRUE" and any(marker in text for marker in true_negative_markers):
        return True
    if label == "FALSE" and any(marker in text for marker in false_positive_markers):
        return True
    return False


def _compute_selected_trust(selected_ids: List[str], evidence_index: Dict[str, Any]) -> float:
    if not selected_ids:
        return 0.0
    selected_trust_values: list[float] = []
    for evid_id in selected_ids:
        evidence = evidence_index.get(evid_id, {})
        if not isinstance(evidence, dict):
            continue
        raw = evidence.get("credibility_score")
        if raw is None and isinstance(evidence.get("metadata"), dict):
            raw = evidence["metadata"].get("credibility_score")
        try:
            trust = float(raw)
        except (TypeError, ValueError):
            trust = 0.5
        selected_trust_values.append(max(0.0, min(1.0, trust)))
    if not selected_trust_values:
        return 0.0
    return sum(selected_trust_values) / len(selected_trust_values)


def _compute_evidence_based_caps(
    selected_ids: List[str],
    evidence_index: Dict[str, Any],
    has_required_intent: bool,
) -> tuple[int, float, float]:
    if not selected_ids:
        return (
            int(settings.stage9_no_evidence_confidence_cap),
            max(0.0, min(1.0, float(settings.stage9_no_evidence_grounding_cap))),
            0.0,
        )

    avg_selected_trust = _compute_selected_trust(selected_ids, evidence_index)
    coverage_factor = min(1.0, len(selected_ids) / 3.0)
    intent_factor = 1.0 if has_required_intent else 0.65

    evidence_conf_cap = int(
        max(
            0.0,
            min(
                100.0,
                round(100.0 * (0.45 * avg_selected_trust + 0.35 * coverage_factor + 0.20 * intent_factor)),
            ),
        )
    )
    evidence_grounding_cap = max(
        0.0,
        min(
            1.0,
            round(0.60 * avg_selected_trust + 0.30 * coverage_factor + 0.10 * intent_factor, 4),
        ),
    )
    return evidence_conf_cap, evidence_grounding_cap, avg_selected_trust


def _create_no_verified_citation_judge_result() -> Dict[str, Any]:
    confidence_cap = int(max(0, min(100, int(settings.stage9_no_evidence_confidence_cap))))
    grounding_cap = max(0.0, min(1.0, float(settings.stage9_no_evidence_grounding_cap)))
    return {
        "evaluation": {
            "hallucination_count": 0,
            "grounding_score": grounding_cap,
            "is_consistent": True,
            "policy_violations": [],
        },
        "verdict_label": "UNVERIFIED",
        "verdict_korean": "검증불가입니다",
        "confidence_percent": confidence_cap,
        "headline": "검증된 인용 근거가 부족해 판단을 보류합니다",
        "explanation": "Stage6/7에서 검증된 인용 근거가 없어 최종 판정을 보류했습니다.",
        "evidence_summary": [],
        "cautions": ["검증 가능한 인용 근거가 없어 단정 판정을 제공할 수 없습니다."],
        "recommendation": "공식 자료나 1차 출처 인용을 추가해 다시 검증해 주세요.",
        "risk_flags": ["NO_VERIFIED_CITATIONS"],
        "selected_evidence_ids": [],
    }


def _postprocess_judge_result(
    parsed: Dict[str, Any],
    support_pack: Dict[str, Any],
    skeptic_pack: Dict[str, Any],
    evidence_index: Dict[str, Any],
    claim_mode: str,
) -> Dict[str, Any]:
    verdict_korean_map = {
        "TRUE": "사실입니다",
        "FALSE": "거짓입니다",
        "UNVERIFIED": "검증불가입니다",
    }

    label = (parsed.get("verdict_label") or "").upper().strip()
    verified_support_ids = _extract_verified_citation_ids(support_pack, evidence_index)
    verified_skeptic_ids = _extract_verified_citation_ids(skeptic_pack, evidence_index)
    no_verified_citations = not verified_support_ids and not verified_skeptic_ids
    label_from_fallback = False

    if label not in {"TRUE", "FALSE"}:
        label = "FALSE"
        label_from_fallback = True

    confidence_percent = parsed.get("confidence_percent")
    if not isinstance(confidence_percent, (int, float)):
        fallback_conf = support_pack.get("confidence", 0.0) if label == "TRUE" else skeptic_pack.get("confidence", 0.0)
        confidence_percent = int(max(0.0, min(1.0, float(fallback_conf))) * 100)
    confidence_percent = int(max(0, min(100, int(confidence_percent))))

    evaluation = parsed.get("evaluation", {}) if isinstance(parsed.get("evaluation"), dict) else {}
    try:
        grounding_score = float(evaluation.get("grounding_score", 1.0))
    except (TypeError, ValueError):
        grounding_score = 1.0
    grounding_score = max(0.0, min(1.0, grounding_score))

    def _confidence_from_pack() -> int:
        pack = support_pack if label == "TRUE" else skeptic_pack
        raw = pack.get("confidence", 0.0) if isinstance(pack, dict) else 0.0
        try:
            val = float(raw)
        except (TypeError, ValueError):
            return 0
        if val <= 1.0:
            return int(max(0.0, min(1.0, val)) * 100)
        return int(max(0.0, min(100.0, val)))

    selected_ids_raw = parsed.get("selected_evidence_ids") if isinstance(parsed.get("selected_evidence_ids"), list) else []
    selected_ids_raw = [str(eid).strip() for eid in selected_ids_raw if str(eid).strip()]

    selected_ids: list[str] = []
    seen_selected: set[str] = set()
    invalid_selected_count = 0
    placeholder_selected_count = 0
    for eid in selected_ids_raw:
        if _is_placeholder_evidence_id(eid):
            placeholder_selected_count += 1
            invalid_selected_count += 1
            continue
        if eid not in evidence_index:
            invalid_selected_count += 1
            continue
        if eid in seen_selected:
            continue
        seen_selected.add(eid)
        selected_ids.append(eid)

    evidence_mismatch = invalid_selected_count > 0
    schema_mismatch = bool("JUDGE_SCHEMA_MISMATCH" in [str(flag).strip() for flag in (parsed.get("risk_flags") or []) if isinstance(flag, str)])
    fallback_applied = False
    fallback_reason = ""
    recovered_selected_count = 0

    if not selected_ids:
        preferred_ids = verified_support_ids if label == "TRUE" else verified_skeptic_ids
        other_ids = verified_skeptic_ids if label == "TRUE" else verified_support_ids
        fallback_ids = preferred_ids + [eid for eid in other_ids if eid not in preferred_ids]
        selected_ids = fallback_ids[: max(1, int(settings.stage9_schema_fallback_select_k))]
        if not selected_ids and not no_verified_citations:
            evidence_mismatch = True

    if not selected_ids and schema_mismatch and not no_verified_citations:
        recovered = _recover_selected_ids_from_evidence(
            evidence_index,
            claim_mode,
            max(1, int(settings.stage9_schema_fallback_select_k)),
        )
        if recovered:
            selected_ids = recovered
            recovered_selected_count = len(recovered)
            fallback_applied = True
            fallback_reason = "schema_mismatch_recovered_ids"
            evidence_mismatch = False
            if confidence_percent <= 0:
                confidence_percent = 35 if label == "TRUE" else 30

    if schema_mismatch and confidence_percent <= 0 and not no_verified_citations:
        pack_conf = _confidence_from_pack()
        if pack_conf > 0:
            confidence_percent = pack_conf
            if not fallback_applied:
                fallback_applied = True
                fallback_reason = "schema_mismatch_confidence_from_pack"

    risk_flags = [str(flag) for flag in (parsed.get("risk_flags") or []) if isinstance(flag, str)]
    if label_from_fallback and "JUDGE_SCHEMA_MISMATCH" not in risk_flags:
        risk_flags.append("JUDGE_SCHEMA_MISMATCH")
    if placeholder_selected_count > 0 and "JUDGE_PLACEHOLDER_EVIDENCE_ID" not in risk_flags:
        risk_flags.append("JUDGE_PLACEHOLDER_EVIDENCE_ID")

    if evidence_mismatch and "JUDGE_EVIDENCE_MISMATCH" not in risk_flags:
        risk_flags.append("JUDGE_EVIDENCE_MISMATCH")

    if len(selected_ids) < 2 and "LOW_EVIDENCE" not in risk_flags:
        risk_flags.append("LOW_EVIDENCE")
    if evaluation.get("hallucination_count", 0) >= 2 and "HALLUCINATION_DETECTED" not in risk_flags:
        risk_flags.append("HALLUCINATION_DETECTED")
    if evaluation.get("policy_violations") and "POLICY_RISK" not in risk_flags:
        risk_flags.append("POLICY_RISK")

    mode = _normalize_mode(claim_mode)
    required_intents = _required_intents()
    confidence_capped = False
    has_required_intent = any(
        str((evidence_index.get(eid, {}) or {}).get("intent") or "").strip().lower() in required_intents
        for eid in selected_ids
    )

    evidence_confidence_cap, evidence_grounding_cap, avg_selected_trust = _compute_evidence_based_caps(
        selected_ids,
        evidence_index,
        has_required_intent,
    )
    confidence_percent = min(confidence_percent, evidence_confidence_cap)
    grounding_score = min(grounding_score, evidence_grounding_cap)

    if no_verified_citations:
        label = "UNVERIFIED"
        confidence_percent = min(confidence_percent, int(settings.stage9_no_evidence_confidence_cap))
        grounding_score = min(grounding_score, float(settings.stage9_no_evidence_grounding_cap))
        if "NO_VERIFIED_CITATIONS" not in risk_flags:
            risk_flags.append("NO_VERIFIED_CITATIONS")

    if mode in {"rumor", "mixed"} and not has_required_intent:
        capped = int(settings.stage9_rumor_confidence_cap)
        if confidence_percent > capped:
            confidence_percent = capped
            confidence_capped = True
        if "RUMOR_UNCONFIRMED" not in risk_flags:
            risk_flags.append("RUMOR_UNCONFIRMED")

    min_trust = float(settings.stage9_min_evidence_trust)
    if selected_ids and avg_selected_trust < min_trust:
        label = "UNVERIFIED"
        confidence_percent = min(confidence_percent, int(settings.stage9_unverified_confidence_cap))
        grounding_score = min(grounding_score, float(settings.stage9_no_evidence_grounding_cap))
        if "LOW_TRUST_EVIDENCE" not in risk_flags:
            risk_flags.append("LOW_TRUST_EVIDENCE")

    explanation = str(parsed.get("explanation", "") or "").strip()
    if _has_label_explanation_contradiction(label, explanation):
        label = "UNVERIFIED"
        confidence_percent = min(confidence_percent, int(settings.stage9_unverified_confidence_cap))
        grounding_score = min(grounding_score, float(settings.stage9_self_contradiction_grounding_cap))
        if "JUDGE_SELF_CONTRADICTION" not in risk_flags:
            risk_flags.append("JUDGE_SELF_CONTRADICTION")

    fail_closed = False
    fail_closed_on_no_evidence = bool(settings.stage9_fail_closed_only_when_no_evidence)
    should_fail_close = (
        False
        if no_verified_citations
        else (not selected_ids if fail_closed_on_no_evidence else (evidence_mismatch or not selected_ids or confidence_percent <= 0))
    )
    if should_fail_close:
        fail_closed = True
        label = "FALSE"
        confidence_percent = min(confidence_percent, int(settings.stage9_fail_closed_confidence_cap))
        grounding_score = min(grounding_score, float(settings.stage9_fail_closed_grounding_cap))
        if "JUDGE_FAIL_CLOSED" not in risk_flags:
            risk_flags.append("JUDGE_FAIL_CLOSED")
    elif "JUDGE_FAIL_CLOSED" in risk_flags:
        risk_flags = [flag for flag in risk_flags if flag != "JUDGE_FAIL_CLOSED"]

    confidence_percent = int(max(0, min(100, int(confidence_percent))))
    grounding_score = max(0.0, min(1.0, float(grounding_score)))
    if confidence_percent < 50 and "LOW_CONFIDENCE" not in risk_flags:
        risk_flags.append("LOW_CONFIDENCE")

    evidence_summary = _build_evidence_summary(selected_ids, evidence_index)

    return {
        "evaluation": {
            "hallucination_count": evaluation.get("hallucination_count", 0),
            "grounding_score": grounding_score,
            "is_consistent": evaluation.get("is_consistent", True),
            "policy_violations": evaluation.get("policy_violations", []),
        },
        "verdict_label": label,
        "verdict_korean": verdict_korean_map.get(label, "확인이 어렵습니다"),
        "confidence_percent": confidence_percent,
        "headline": f"이 주장은 {confidence_percent}% 확률로 {verdict_korean_map.get(label, '확인이 어렵습니다')}",
        "explanation": explanation,
        "evidence_summary": evidence_summary,
        "cautions": parsed.get("cautions", []),
        "recommendation": parsed.get("recommendation", ""),
        "risk_flags": risk_flags,
        "selected_evidence_ids": selected_ids,
        "_meta": {
            "invalid_selected_count": invalid_selected_count,
            "placeholder_selected_count": placeholder_selected_count,
            "evidence_mismatch": evidence_mismatch,
            "no_verified_citations": no_verified_citations,
            "has_required_intent": has_required_intent,
            "retrieval_mode": mode,
            "confidence_capped": confidence_capped,
            "fail_closed": fail_closed,
            "schema_mismatch": schema_mismatch,
            "fallback_applied": fallback_applied,
            "fallback_reason": fallback_reason,
            "recovered_selected_count": recovered_selected_count,
            "evidence_confidence_cap": evidence_confidence_cap,
            "evidence_grounding_cap": evidence_grounding_cap,
            "avg_selected_evidence_trust": round(avg_selected_trust, 4),
            "grounding_score": grounding_score,
        },
    }


def _format_citations(
    selected_ids: List[str],
    evidence_index: Dict[str, Any],
    citation_index: Dict[str, Dict[str, Any]],
) -> List[Dict[str, Any]]:
    formatted = []
    for evid_id in selected_ids:
        evidence = evidence_index.get(evid_id, {})
        citation = citation_index.get(evid_id, {})
        formatted.append(
            {
                "source_type": evidence.get("source_type", "NEWS"),
                "title": citation.get("title") or evidence.get("title", ""),
                "url": citation.get("url") or evidence.get("url", ""),
                "doc_id": None,
                "doc_version_id": None,
                "locator": {},
                "quote": citation.get("quote") or evidence.get("snippet", ""),
                "relevance": 0.0,
            }
        )
    return formatted


def _build_final_verdict(
    judge_result: Dict[str, Any],
    evidence_index: Dict[str, Any],
    citation_index: Dict[str, Dict[str, Any]],
    trace_id: str,
) -> Dict[str, Any]:
    selected_ids = judge_result.get("selected_evidence_ids", [])
    formatted_citations = _format_citations(selected_ids, evidence_index, citation_index)

    llm_config = _get_llm_config()

    return {
        "analysis_id": trace_id,
        "label": judge_result.get("verdict_label", "FALSE"),
        "confidence": judge_result.get("confidence_percent", 0) / 100.0,
        "summary": judge_result.get("headline", ""),
        "rationale": [evidence.get("point", "") for evidence in judge_result.get("evidence_summary", [])],
        "citations": formatted_citations,
        "counter_evidence": [],
        "limitations": judge_result.get("cautions", []),
        "recommended_next_steps": [judge_result.get("recommendation", "")] if judge_result.get("recommendation") else [],
        "risk_flags": judge_result.get("risk_flags", []),
        "model_info": {
            "provider": "openai",
            "model": llm_config.model,
            "version": "v1.0",
        },
        "latency_ms": 0,
        "cost_usd": 0.0,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "evaluation": judge_result.get("evaluation", {}),
        "verdict_korean": judge_result.get("verdict_korean", "확인이 어렵습니다"),
        "confidence_percent": judge_result.get("confidence_percent", 0),
        "headline": judge_result.get("headline", ""),
        "explanation": judge_result.get("explanation", ""),
        "evidence_summary": judge_result.get("evidence_summary", []),
    }


def _build_user_result(judge_result: Dict[str, Any], claim_text: str) -> Dict[str, Any]:
    verdict_label = judge_result.get("verdict_label", "FALSE")
    confidence_percent = judge_result.get("confidence_percent", 0)

    verdict_style = {
        "TRUE": {"icon": "✅", "color": "green", "badge": "사실"},
        "FALSE": {"icon": "❌", "color": "red", "badge": "거짓"},
        "UNVERIFIED": {"icon": "⚪", "color": "gray", "badge": "판단보류"},
    }
    style = verdict_style.get(verdict_label, verdict_style["UNVERIFIED"])

    evidence_list = []
    for evidence in judge_result.get("evidence_summary", []):
        evidence_list.append(
            {
                "text": evidence.get("point", ""),
                "source": {
                    "title": evidence.get("source_title", ""),
                    "url": evidence.get("source_url", ""),
                },
            }
        )

    return {
        "claim": claim_text,
        "verdict": {
            "label": verdict_label,
            "korean": judge_result.get("verdict_korean", "확인이 어렵습니다"),
            "confidence_percent": confidence_percent,
            "icon": style["icon"],
            "color": style["color"],
            "badge": style["badge"],
        },
        "headline": judge_result.get("headline", ""),
        "explanation": judge_result.get("explanation", ""),
        "evidence": evidence_list,
        "cautions": judge_result.get("cautions", []),
        "recommendation": judge_result.get("recommendation", ""),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def _determine_risk_flags(judge_result: Dict[str, Any]) -> List[str]:
    flags = list(judge_result.get("risk_flags", []))

    if judge_result.get("confidence_percent", 0) < 50 and "LOW_CONFIDENCE" not in flags:
        flags.append("LOW_CONFIDENCE")

    evaluation = judge_result.get("evaluation", {})
    if evaluation.get("hallucination_count", 0) >= 2 and "HALLUCINATION_DETECTED" not in flags:
        flags.append("HALLUCINATION_DETECTED")

    if evaluation.get("policy_violations") and "POLICY_RISK" not in flags:
        flags.append("POLICY_RISK")

    if len(judge_result.get("selected_evidence_ids", [])) < 2 and "LOW_EVIDENCE" not in flags:
        flags.append("LOW_EVIDENCE")

    return flags


def _merge_risk_flags(*flag_lists: Any) -> List[str]:
    merged: List[str] = []
    seen = set()
    for flags in flag_lists:
        if not isinstance(flags, list):
            continue
        for flag in flags:
            if not isinstance(flag, str):
                continue
            normalized = flag.strip()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            merged.append(normalized)
    return merged


def _apply_rule_based_judge(
    claim_text: str,
    support_pack: Dict[str, Any],
    skeptic_pack: Dict[str, Any],
    evidence_index: Dict[str, Any],
    claim_mode: str,
) -> Dict[str, Any]:
    support_cits = support_pack.get("citations", []) or []
    skeptic_cits = skeptic_pack.get("citations", []) or []

    label = "TRUE" if len(support_cits) > len(skeptic_cits) else "FALSE"
    confidence_percent = 30 if (support_cits or skeptic_cits) else 0

    selected_ids = [
        c.get("evid_id")
        for c in (support_cits if label == "TRUE" else skeptic_cits)
        if c.get("evid_id") in evidence_index
    ]

    risk_flags = ["LLM_JUDGE_FAILED"]
    mode = _normalize_mode(claim_mode)
    if mode in {"rumor", "mixed"}:
        required_intents = _required_intents()
        has_required_intent = any(
            str((evidence_index.get(eid, {}) or {}).get("intent") or "").strip().lower() in required_intents
            for eid in selected_ids
        )
        if not has_required_intent:
            risk_flags.append("RUMOR_UNCONFIRMED")
            confidence_percent = min(confidence_percent, int(settings.stage9_rumor_confidence_cap))

    judge_result = {
        "evaluation": {
            "hallucination_count": -1,
            "grounding_score": -1.0,
            "is_consistent": None,
            "policy_violations": [],
        },
        "verdict_label": label,
        "verdict_korean": "사실입니다" if label == "TRUE" else "거짓입니다",
        "confidence_percent": confidence_percent,
        "headline": f"이 주장은 {confidence_percent}% 확률로 {'사실입니다' if label == 'TRUE' else '거짓입니다'}",
        "explanation": "LLM 판정 실패로 규칙 기반 판단을 적용했습니다.",
        "evidence_summary": _build_evidence_summary(selected_ids, evidence_index),
        "cautions": ["자동 판정 결과이므로 참고용으로만 활용해 주세요"],
        "recommendation": "추가 검증을 위해 공식 출처를 직접 확인해 보시기 바랍니다.",
        "risk_flags": risk_flags,
        "selected_evidence_ids": selected_ids,
    }

    return {
        "final_verdict": _build_final_verdict(judge_result, evidence_index, {}, ""),
        "user_result": _build_user_result(judge_result, claim_text),
        "judge_result": judge_result,
    }


def _create_fallback_result(error_msg: str) -> Dict[str, Any]:
    judge_result = {
        "verdict_label": "FALSE",
        "verdict_korean": "거짓입니다",
        "confidence_percent": 0,
        "headline": "이 주장은 현재 확인이 어렵습니다",
        "explanation": f"시스템 오류로 인해 검증을 완료할 수 없습니다. ({error_msg[:50]})",
        "evidence_summary": [],
        "cautions": ["자동 분석 결과이므로 참고용으로만 활용해 주세요"],
        "recommendation": "추가 검증을 위해 공식 출처를 직접 확인해 보시기 바랍니다.",
        "risk_flags": ["QUALITY_GATE_FAILED"],
        "selected_evidence_ids": [],
    }

    final_verdict = _build_final_verdict(judge_result, {}, {}, "")
    user_result = _build_user_result(judge_result, "")

    return {
        "final_verdict": final_verdict,
        "user_result": user_result,
        "judge_result": judge_result,
    }


def run(state: dict) -> dict:
    """Stage 9 실행: TRUE/FALSE 최종 판정 + 사용자 친화 결과 생성."""
    trace_id = state.get("trace_id", "unknown")
    claim_text = state.get("claim_text", "")
    language = state.get("language", "ko")

    support_pack = state.get("support_pack", {})
    skeptic_pack = state.get("skeptic_pack", {})
    evidence_index = state.get("evidence_index", {})
    claim_profile = (state.get("judge_prep_meta", {}) or {}).get("claim_profile", {}) if isinstance(state.get("judge_prep_meta"), dict) else {}
    claim_mode = _normalize_mode(claim_profile.get("claim_mode") if isinstance(claim_profile, dict) else state.get("claim_mode"))

    logger.info(
        "[%s] Stage9 시작: support_cits=%d, skeptic_cits=%d, mode=%s",
        trace_id,
        len(support_pack.get("citations", [])),
        len(skeptic_pack.get("citations", [])),
        claim_mode,
    )

    if not support_pack and not skeptic_pack:
        logger.warning("[%s] support/skeptic pack 없음, fallback 적용", trace_id)
        fallback = _create_fallback_result("검증 데이터가 없습니다")
        fallback_judge_result = fallback.get("judge_result", {})
        merged_flags = _merge_risk_flags(state.get("risk_flags", []), _determine_risk_flags(fallback_judge_result))
        final_verdict = dict(fallback["final_verdict"])
        final_verdict["risk_flags"] = merged_flags
        state["final_verdict"] = final_verdict
        state["user_result"] = fallback["user_result"]
        state["risk_flags"] = merged_flags
        state["stage09_diagnostics"] = {
            "mode": claim_mode,
            "retrieval_enabled": False,
            "retrieval_top_k": 0,
            "retrieval_count": 0,
            "invalid_selected_count": 0,
            "placeholder_selected_count": 0,
            "confidence_capped": False,
            "has_required_intent": False,
            "fail_closed": False,
            "schema_mismatch": False,
            "fallback_applied": False,
            "fallback_reason": "missing_support_skeptic_pack",
            "recovered_selected_count": 0,
            "final_confidence_percent": 0,
            "selected_evidence_count": 0,
            "avg_selected_evidence_trust": 0.0,
            "no_verified_citations": False,
            "grounding_score": 0.0,
        }
        return state

    judge_prep_meta = state.get("judge_prep_meta", {}) if isinstance(state.get("judge_prep_meta"), dict) else {}
    support_citation_count = int(
        judge_prep_meta.get(
            "support_citation_count",
            len(support_pack.get("citations", []) if isinstance(support_pack.get("citations"), list) else []),
        )
        or 0
    )
    skeptic_citation_count = int(
        judge_prep_meta.get(
            "skeptic_citation_count",
            len(skeptic_pack.get("citations", []) if isinstance(skeptic_pack.get("citations"), list) else []),
        )
        or 0
    )
    if support_citation_count + skeptic_citation_count <= 0:
        logger.warning("[%s] Stage8 집계상 검증된 인용 0건: Judge 호출 스킵", trace_id)
        judge_result = _create_no_verified_citation_judge_result()
        final_verdict = _build_final_verdict(judge_result, evidence_index, {}, trace_id)
        user_result = _build_user_result(judge_result, claim_text)

        existing_flags = state.get("risk_flags", [])
        new_flags = _determine_risk_flags(judge_result)
        merged_flags = _merge_risk_flags(existing_flags, new_flags, ["NO_VERIFIED_CITATIONS"])
        final_verdict["risk_flags"] = merged_flags

        state["final_verdict"] = final_verdict
        state["user_result"] = user_result
        state["risk_flags"] = merged_flags
        state["stage09_diagnostics"] = {
            "mode": claim_mode,
            "retrieval_enabled": False,
            "retrieval_top_k": 0,
            "retrieval_count": 0,
            "invalid_selected_count": 0,
            "placeholder_selected_count": 0,
            "confidence_capped": False,
            "has_required_intent": False,
            "fail_closed": False,
            "schema_mismatch": False,
            "fallback_applied": True,
            "fallback_reason": "no_verified_citations_skip_judge",
            "recovered_selected_count": 0,
            "final_confidence_percent": int(judge_result.get("confidence_percent", 0) or 0),
            "selected_evidence_count": 0,
            "avg_selected_evidence_trust": 0.0,
            "no_verified_citations": True,
            "grounding_score": float((judge_result.get("evaluation") or {}).get("grounding_score", 0.0) or 0.0),
        }
        return state

    try:
        retrieval_sources = _retrieve_judge_evidence(claim_text, state.get("search_mode", "auto"), claim_mode)
        state["judge_retrieval"] = retrieval_sources

        merged_evidence_index = _build_evidence_index(evidence_index, retrieval_sources)
        citation_index = _build_citation_index(support_pack, skeptic_pack, retrieval_sources)

        system_prompt = load_system_prompt()
        user_prompt = _build_judge_user_prompt(
            claim_text=claim_text,
            support_pack=support_pack,
            skeptic_pack=skeptic_pack,
            evidence_index=merged_evidence_index,
            retrieval_sources=retrieval_sources,
            language=language,
            claim_profile=claim_profile if isinstance(claim_profile, dict) else {},
            judge_prep_meta=state.get("judge_prep_meta", {}) if isinstance(state.get("judge_prep_meta"), dict) else {},
        )
        state["prompt_judge_user"] = user_prompt
        state["prompt_judge_system"] = system_prompt

        runtime = _get_llm_runtime()
        last_response: str = ""

        def operation():
            def call_fn():
                nonlocal last_response
                last_response = _call_llm(system_prompt, user_prompt)
                return last_response

            def retry_call_fn(retry_prompt: str):
                combined_prompt = f"{system_prompt}\n\n{retry_prompt}"
                nonlocal last_response
                last_response = _call_llm(combined_prompt, user_prompt)
                return last_response

            parsed = parse_judge_json_with_retry(call_fn, max_retries=1, retry_call_fn=retry_call_fn)
            state["slm_raw_judge"] = last_response
            parsed = validate_judge_output(parsed)
            return _postprocess_judge_result(parsed, support_pack, skeptic_pack, merged_evidence_index, claim_mode)

        judge_result = runtime.execute(operation, "judge_verdict")

        meta = judge_result.get("_meta") if isinstance(judge_result.get("_meta"), dict) else {}
        if "_meta" in judge_result:
            judge_result = dict(judge_result)
            judge_result.pop("_meta", None)

        final_verdict = _build_final_verdict(
            judge_result=judge_result,
            evidence_index=merged_evidence_index,
            citation_index=citation_index,
            trace_id=trace_id,
        )
        user_result = _build_user_result(judge_result, claim_text)

        existing_flags = state.get("risk_flags", [])
        new_flags = _determine_risk_flags(judge_result)
        merged_flags = _merge_risk_flags(existing_flags, new_flags)
        final_verdict["risk_flags"] = merged_flags

        state["final_verdict"] = final_verdict
        state["user_result"] = user_result
        state["risk_flags"] = merged_flags

        enabled, retrieval_top_k = _judge_wiki_retrieval_policy(claim_mode)
        confidence_capped = bool(meta.get("confidence_capped", False))
        state["stage09_diagnostics"] = {
            "mode": claim_mode,
            "retrieval_enabled": enabled,
            "retrieval_top_k": retrieval_top_k,
            "retrieval_count": len(retrieval_sources),
            "invalid_selected_count": int(meta.get("invalid_selected_count", 0) or 0),
            "placeholder_selected_count": int(meta.get("placeholder_selected_count", 0) or 0),
            "confidence_capped": confidence_capped,
            "has_required_intent": bool(meta.get("has_required_intent", False)),
            "fail_closed": bool(meta.get("fail_closed", False)),
            "schema_mismatch": bool(meta.get("schema_mismatch", False)),
            "fallback_applied": bool(meta.get("fallback_applied", False)),
            "fallback_reason": str(meta.get("fallback_reason", "") or ""),
            "recovered_selected_count": int(meta.get("recovered_selected_count", 0) or 0),
            "final_confidence_percent": int(judge_result.get("confidence_percent", 0) or 0),
            "selected_evidence_count": len(judge_result.get("selected_evidence_ids", []) or []),
            "avg_selected_evidence_trust": float(meta.get("avg_selected_evidence_trust", 0.0) or 0.0),
            "no_verified_citations": bool(meta.get("no_verified_citations", False)),
            "grounding_score": float(meta.get("grounding_score", 0.0) or 0.0),
        }

        evaluation = judge_result.get("evaluation", {})
        logger.info(
            "[%s] Stage9 완료: label=%s, confidence=%s%%, hallucination=%s, grounding=%s",
            trace_id,
            judge_result.get("verdict_label"),
            judge_result.get("confidence_percent"),
            evaluation.get("hallucination_count", "N/A"),
            evaluation.get("grounding_score", "N/A"),
        )

    except OrchestratorError as e:
        logger.error("[%s] LLM Judge 실패: %s", trace_id, e)
        fallback = _apply_rule_based_judge(claim_text, support_pack, skeptic_pack, evidence_index, claim_mode)
        fallback_judge_result = fallback.get("judge_result", {})
        merged_flags = _merge_risk_flags(state.get("risk_flags", []), _determine_risk_flags(fallback_judge_result), ["LLM_JUDGE_FAILED"])
        final_verdict = dict(fallback["final_verdict"])
        final_verdict["risk_flags"] = merged_flags
        state["final_verdict"] = final_verdict
        state["user_result"] = fallback["user_result"]
        state["risk_flags"] = merged_flags
        state["stage09_diagnostics"] = {
            "mode": claim_mode,
            "retrieval_enabled": False,
            "retrieval_top_k": 0,
            "retrieval_count": 0,
            "invalid_selected_count": 0,
            "placeholder_selected_count": 0,
            "confidence_capped": claim_mode in {"rumor", "mixed"},
            "has_required_intent": False,
            "fail_closed": False,
            "schema_mismatch": False,
            "fallback_applied": True,
            "fallback_reason": "orchestrator_error_rule_based_judge",
            "recovered_selected_count": len((fallback.get("judge_result") or {}).get("selected_evidence_ids", []) or []),
            "final_confidence_percent": int((fallback.get("judge_result") or {}).get("confidence_percent", 0)),
            "selected_evidence_count": len((fallback.get("judge_result") or {}).get("selected_evidence_ids", []) or []),
            "avg_selected_evidence_trust": 0.0,
            "no_verified_citations": False,
            "grounding_score": float(((fallback.get("judge_result") or {}).get("evaluation") or {}).get("grounding_score", 0.0) or 0.0),
        }

    except Exception as e:
        logger.exception("[%s] Stage9 예상치 못한 오류: %s", trace_id, e)
        fallback = _create_fallback_result(str(e))
        fallback_judge_result = fallback.get("judge_result", {})
        merged_flags = _merge_risk_flags(state.get("risk_flags", []), _determine_risk_flags(fallback_judge_result), ["QUALITY_GATE_FAILED"])
        final_verdict = dict(fallback["final_verdict"])
        final_verdict["risk_flags"] = merged_flags
        state["final_verdict"] = final_verdict
        state["user_result"] = fallback["user_result"]
        state["risk_flags"] = merged_flags
        state["stage09_diagnostics"] = {
            "mode": claim_mode,
            "retrieval_enabled": False,
            "retrieval_top_k": 0,
            "retrieval_count": 0,
            "invalid_selected_count": 0,
            "placeholder_selected_count": 0,
            "confidence_capped": False,
            "has_required_intent": False,
            "fail_closed": False,
            "schema_mismatch": False,
            "fallback_applied": True,
            "fallback_reason": "unexpected_exception",
            "recovered_selected_count": 0,
            "final_confidence_percent": 0,
            "selected_evidence_count": 0,
            "avg_selected_evidence_trust": 0.0,
            "no_verified_citations": False,
            "grounding_score": 0.0,
        }

    return state
