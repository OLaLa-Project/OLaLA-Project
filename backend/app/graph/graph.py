import asyncio
import logging
import re
import time
from collections.abc import Awaitable, Callable
from functools import lru_cache
from typing import Any, cast

from app.core.settings import settings
from app.orchestrator.schemas.common import SearchQueryType
from app.orchestrator.stage_manager import get_async as get_async_stage
from app.orchestrator.stage_manager import run as run_stage
from app.graph.checkpoint import get_graph_checkpointer
from app.graph.stage_logger import attach_stage_log, log_stage_event
from app.graph.state import (
    GraphState,
    RegistryStageName,
    STAGE_ORDER,
    SearchQuery,
    StageName,
    normalize_stage_name,
)
StageFn = Callable[[GraphState], GraphState]
AsyncStageFn = Callable[[GraphState], Awaitable[GraphState]]


def _resolve_wiki_search_mode(state: GraphState) -> str:
    """Decide wiki search_mode dynamically based on embeddings readiness."""
    if bool(settings.stage3_wiki_strict_vector_only):
        return "vector"
    explicit = str(state.get("search_mode", "")).strip().lower()
    if explicit in {"lexical", "fts", "vector"}:
        return explicit

    embeddings_ready = settings.wiki_embeddings_ready
    if explicit == "auto":
        return "auto" if embeddings_ready else "lexical"
    return "auto" if embeddings_ready else "lexical"


_KEYWORD_STOPWORDS = {
    "그리고",
    "또한",
    "대한",
    "관련",
    "통한",
    "위한",
    "이번",
    "해당",
    "with",
    "from",
    "that",
    "this",
    "and",
    "the",
}
_GENERIC_WEB_TOKENS = {
    "기사",
    "보도",
    "내용",
    "관련",
    "검증",
    "정보",
    "사이트",
    "문서",
    "페이지",
    "news",
    "article",
    "web",
    "search",
}


def _extract_keyword_tokens(text: str, *, max_terms: int = 8) -> list[str]:
    if not text:
        return []
    tokens = re.findall(r"[A-Za-z0-9가-힣]{2,}", text)
    selected: list[str] = []
    seen: set[str] = set()
    for token in tokens:
        key = token.lower()
        if key in _KEYWORD_STOPWORDS or key in seen:
            continue
        seen.add(key)
        selected.append(token)
        if len(selected) >= max_terms:
            break
    return selected


def _to_keyword_text(text: str, *, max_terms: int = 8, max_chars: int = 50) -> tuple[str, list[str]]:
    tokens = _extract_keyword_tokens(text, max_terms=max_terms)
    if not tokens:
        fallback = re.sub(r"\s+", " ", str(text or "").strip())
        if not fallback:
            return "", []
        return fallback[:max_chars].strip(), [fallback[:max_chars].strip()]
    keyword_text = " ".join(tokens).strip()
    if len(keyword_text) > max_chars:
        keyword_text = keyword_text[:max_chars].strip()
    return keyword_text, tokens


def _extract_anchor_tokens(entity_map: Any, *, max_terms: int = 6) -> list[str]:
    if not isinstance(entity_map, dict):
        return []
    extracted = entity_map.get("extracted")
    if not isinstance(extracted, list):
        return []
    anchors: list[str] = []
    seen: set[str] = set()
    for item in extracted:
        tokens = _extract_keyword_tokens(str(item or ""), max_terms=2)
        for token in tokens:
            key = token.lower()
            if key in seen:
                continue
            seen.add(key)
            anchors.append(token)
            if len(anchors) >= max_terms:
                return anchors
    return anchors


def _rewrite_keyword_query(
    text: str,
    *,
    anchor_tokens: list[str],
    max_terms: int = 8,
    max_chars: int = 50,
) -> tuple[str, list[str], list[str], list[str], list[str]]:
    raw_tokens = re.findall(r"[A-Za-z0-9가-힣]{2,}", str(text or ""))
    cleaned_tokens: list[str] = []
    dropped_tokens: list[str] = []
    seen: set[str] = set()
    for token in raw_tokens:
        key = token.lower()
        if key in seen:
            continue
        seen.add(key)
        if key in _KEYWORD_STOPWORDS or key in _GENERIC_WEB_TOKENS:
            dropped_tokens.append(token)
            continue
        cleaned_tokens.append(token)

    if not cleaned_tokens:
        fallback = _extract_keyword_tokens(text, max_terms=max_terms)
        cleaned_tokens = fallback[:max_terms]

    selected = cleaned_tokens[:max_terms]
    quality_flags: list[str] = ["keyword_rewrite"]
    anchor_used: list[str] = []

    if anchor_tokens:
        selected_lower = " ".join(selected).lower()
        for anchor in anchor_tokens:
            if anchor.lower() in selected_lower:
                anchor_used.append(anchor)
                break
        if not anchor_used:
            selected = [anchor_tokens[0], *selected]
            selected = selected[:max_terms]
            anchor_used = [anchor_tokens[0]]
            quality_flags.append("anchor_enforced")

    if dropped_tokens:
        quality_flags.append("generic_tokens_dropped")

    keyword_text = " ".join(selected).strip()
    if len(keyword_text) > max_chars:
        keyword_text = keyword_text[:max_chars].strip()
        quality_flags.append("length_clipped")

    return keyword_text, selected, dropped_tokens, quality_flags, anchor_used


def _merge_flag_lists(*values: Any) -> list[str]:
    merged: list[str] = []
    for value in values:
        if not isinstance(value, list):
            continue
        for item in value:
            text = str(item or "").strip()
            if not text or text in merged:
                continue
            merged.append(text)
    return merged


def _normalized_key(text: str) -> str:
    compact = re.sub(r"\s+", " ", str(text or "").strip().lower())
    return re.sub(r"[^0-9a-zA-Z가-힣]", "", compact)


def _build_queries(state: GraphState) -> GraphState:
    variants = state.get("query_variants") or []
    search_queries: list[SearchQuery] = []
    default_mode = str(state.get("claim_mode", "fact") or "fact").strip().lower() or "fact"
    constraints = state.get("search_constraints")
    constraints_meta = constraints if isinstance(constraints, dict) and constraints else {}
    web_cap = max(1, int(settings.stage3_web_query_cap_per_claim))
    anchor_tokens = _extract_anchor_tokens(state.get("entity_map"))

    parsed_variants: list[dict[str, Any]] = []
    for idx, variant in enumerate(variants, start=1):
        if isinstance(variant, dict):
            text = str(variant.get("text", "")).strip()
            qtype: Any = variant.get("type", "direct")
            base_meta = variant.get("meta") if isinstance(variant.get("meta"), dict) else {}
        elif isinstance(variant, str):
            text = variant.strip()
            qtype = "direct"
            base_meta = {}
        else:
            continue

        if not text:
            continue

        if isinstance(qtype, SearchQueryType):
            qtype_str = qtype.value
        else:
            qtype_str = str(qtype).strip().lower()
        final_type = (
            qtype_str
            if qtype_str in {"wiki", "news", "web", "verification", "direct"}
            else SearchQueryType.DIRECT.value
        )
        parsed_variants.append(
            {
                "index": idx,
                "type": final_type,
                "text": text,
                "meta": dict(base_meta) if isinstance(base_meta, dict) else {},
            }
        )

    wiki_variant = next((item for item in parsed_variants if item["type"] == "wiki"), None)
    if wiki_variant:
        wiki_text = re.sub(r"\s+", " ", str(wiki_variant["text"] or "").strip())
        wiki_quality_flags: list[str] = []
        wiki_anchor_used: list[str] = []
        if anchor_tokens:
            text_lower = wiki_text.lower()
            for anchor in anchor_tokens:
                if anchor.lower() in text_lower:
                    wiki_anchor_used = [anchor]
                    break
            if not wiki_anchor_used:
                wiki_text = f"{anchor_tokens[0]} {wiki_text}".strip()
                wiki_anchor_used = [anchor_tokens[0]]
                wiki_quality_flags.append("anchor_enforced")
        wiki_tokens = _extract_keyword_tokens(wiki_text, max_terms=12)
        wiki_meta = dict(wiki_variant["meta"])
        wiki_meta.setdefault("mode", default_mode)
        wiki_meta["query_strategy"] = "wiki_vector_single"
        wiki_meta["original_text"] = str(wiki_variant["text"] or "").strip()
        wiki_meta["keyword_tokens"] = wiki_tokens
        wiki_meta["anchor_tokens"] = wiki_anchor_used
        wiki_meta["dropped_tokens"] = list(wiki_meta.get("dropped_tokens") or [])
        wiki_meta["quality_flags"] = _merge_flag_lists(wiki_meta.get("quality_flags"), wiki_quality_flags)
        if constraints_meta:
            wiki_meta.setdefault("search_constraints", constraints_meta)
        search_queries.append(
            {
                "type": "wiki",
                "text": wiki_text,
                "search_mode": cast(Any, "vector"),
                "meta": wiki_meta,
            }
        )

    grouped_by_claim: dict[str, list[dict[str, Any]]] = {}
    claim_order: list[str] = []
    for item in parsed_variants:
        if item["type"] == "wiki":
            continue
        meta = dict(item["meta"])
        claim_id = str(meta.get("claim_id") or "").strip() or "__global__"
        mode = str(meta.get("mode") or default_mode).strip().lower() or default_mode
        intent = str(meta.get("intent") or "").strip().lower()
        keyword_text, keyword_tokens, dropped_tokens, quality_flags, anchor_used = _rewrite_keyword_query(
            str(item["text"] or ""),
            anchor_tokens=anchor_tokens,
            max_terms=8,
            max_chars=max(20, int(settings.stage3_web_query_max_chars)),
        )
        if not keyword_text:
            continue
        if claim_id not in grouped_by_claim:
            grouped_by_claim[claim_id] = []
            claim_order.append(claim_id)
        grouped_by_claim[claim_id].append(
            {
                "index": int(item["index"]),
                "qtype": str(item["type"]),
                "claim_id": claim_id,
                "mode": mode,
                "intent": intent,
                "original_text": str(item["text"] or ""),
                "keyword_text": keyword_text,
                "keyword_tokens": keyword_tokens,
                "dropped_tokens": dropped_tokens,
                "quality_flags": quality_flags,
                "anchor_tokens": anchor_used,
                "meta": meta,
            }
        )

    selected_non_wiki: list[dict[str, Any]] = []
    qtype_priority = {"news": 0, "verification": 1, "web": 2, "direct": 3}
    for claim_id in claim_order:
        candidates = grouped_by_claim.get(claim_id, [])
        if not candidates:
            continue
        local_selected: list[dict[str, Any]] = []
        used: set[int] = set()
        group_mode = str(candidates[0].get("mode") or default_mode).strip().lower() or default_mode
        required_intents = ["official_statement", "fact_check"]
        if group_mode in {"rumor", "mixed"}:
            required_intents.append("origin_trace")

        for required_intent in required_intents:
            if len(local_selected) >= web_cap:
                break
            for idx, candidate in enumerate(candidates):
                if idx in used:
                    continue
                if str(candidate.get("intent") or "") != required_intent:
                    continue
                used.add(idx)
                local_selected.append(candidate)
                break

        ranked = sorted(
            enumerate(candidates),
            key=lambda pair: (qtype_priority.get(str(pair[1].get("qtype") or ""), 9), int(pair[1].get("index") or 0)),
        )
        for idx, candidate in ranked:
            if len(local_selected) >= web_cap:
                break
            if idx in used:
                continue
            used.add(idx)
            local_selected.append(candidate)

        selected_non_wiki.extend(local_selected)

    seen_non_wiki: set[tuple[str, str, str]] = set()
    for candidate in sorted(selected_non_wiki, key=lambda item: int(item.get("index") or 0)):
        qtype = str(candidate.get("qtype") or "direct")
        keyword_text = str(candidate.get("keyword_text") or "").strip()
        claim_id = str(candidate.get("claim_id") or "__global__")
        norm_text = _normalized_key(keyword_text)
        if not keyword_text or not norm_text:
            continue
        key = (qtype, norm_text, claim_id)
        if key in seen_non_wiki:
            continue
        seen_non_wiki.add(key)

        meta = dict(candidate.get("meta") or {})
        meta.setdefault("mode", default_mode)
        meta["query_strategy"] = "keyword_focus"
        meta["original_text"] = str(candidate.get("original_text") or keyword_text)
        meta["keyword_tokens"] = list(candidate.get("keyword_tokens") or [])
        meta["anchor_tokens"] = list(candidate.get("anchor_tokens") or [])
        meta["dropped_tokens"] = list(candidate.get("dropped_tokens") or [])
        meta["quality_flags"] = _merge_flag_lists(meta.get("quality_flags"), candidate.get("quality_flags"))
        if constraints_meta:
            meta.setdefault("search_constraints", constraints_meta)
        search_queries.append(
            {
                "type": cast(Any, qtype),
                "text": keyword_text,
                "meta": meta,
            }
        )

    claim_text = state.get("claim_text")
    if not search_queries and isinstance(claim_text, str) and claim_text.strip():
        fallback_text, fallback_tokens, fallback_dropped, fallback_flags, fallback_anchor = _rewrite_keyword_query(
            claim_text,
            anchor_tokens=anchor_tokens,
            max_terms=8,
            max_chars=max(20, int(settings.stage3_web_query_max_chars)),
        )
        fallback_meta: dict[str, Any] = {
            "mode": default_mode,
            "query_strategy": "keyword_focus",
            "original_text": claim_text,
            "keyword_tokens": fallback_tokens,
            "anchor_tokens": fallback_anchor,
            "dropped_tokens": fallback_dropped,
            "quality_flags": fallback_flags,
        }
        if constraints_meta:
            fallback_meta["search_constraints"] = constraints_meta
        search_queries = [
            {
                "type": "direct",
                "text": fallback_text or claim_text.strip(),
                "meta": fallback_meta,
            }
        ]

    return {"search_queries": search_queries}


def _extract_stage_payload(stage_name: str, output: dict[str, Any]) -> dict[str, Any]:
    keys = STAGE_OUTPUT_KEYS.get(cast(StageName, stage_name), [])
    if not keys:
        return {}
    return {key: output.get(key) for key in keys if key in output}


def _with_log(stage_name: str, fn: StageFn) -> StageFn:
    def wrapper(state: GraphState) -> GraphState:
        raw_state = cast(dict[str, Any], state)
        log_stage_event(raw_state, stage_name, "start")
        start = time.time()
        out = fn(state)
        raw_out = cast(dict[str, Any], out)
        stage_payload = _extract_stage_payload(stage_name, raw_out)
        return cast(
            GraphState,
            attach_stage_log(raw_state, stage_name, raw_out, stage_output=stage_payload, started_at=start),
        )

    return wrapper


def _run_stage(stage_name: RegistryStageName) -> StageFn:
    def runner(state: GraphState) -> GraphState:
        return cast(GraphState, run_stage(stage_name, state))

    return runner


def _async_node_wrapper(stage_name: RegistryStageName) -> AsyncStageFn:
    """Use async-native stage when available, otherwise offload sync stage."""

    async def async_runner(state: GraphState) -> GraphState:
        async_fn = get_async_stage(stage_name)
        if async_fn is not None:
            logger = logging.getLogger("uvicorn.error")
            raw_state = cast(dict[str, Any], state)
            log_stage_event(raw_state, stage_name, "start")
            logger.info("[%s] %s start", state.get("trace_id", "unknown"), stage_name)
            start = time.time()
            out = await async_fn(state)
            raw_out = cast(dict[str, Any], out)
            stage_payload = _extract_stage_payload(stage_name, raw_out)
            logger.info("[%s] %s end", state.get("trace_id", "unknown"), stage_name)
            return cast(
                GraphState,
                attach_stage_log(raw_state, stage_name, raw_out, stage_output=stage_payload, started_at=start),
            )

        fn = _with_log(stage_name, _run_stage(stage_name))
        return await asyncio.to_thread(fn, state)

    return async_runner


def _async_adapter_wrapper() -> AsyncStageFn:
    async def runner(state: GraphState) -> GraphState:
        fn = _with_log("adapter_queries", _build_queries)
        return await asyncio.to_thread(fn, state)

    return runner


@lru_cache(maxsize=1)
def build_langgraph() -> Any:
    try:
        import langgraph.graph as langgraph_graph
    except Exception:  # pragma: no cover - optional dependency
        return None

    graph = langgraph_graph.StateGraph(GraphState)

    graph.add_node("stage01_normalize", _async_node_wrapper("stage01_normalize"))
    graph.add_node("stage02_querygen", _async_node_wrapper("stage02_querygen"))
    graph.add_node("adapter_queries", _async_adapter_wrapper())

    graph.add_node("stage03_wiki", _async_node_wrapper("stage03_wiki"))
    graph.add_node("stage03_web", _async_node_wrapper("stage03_web"))
    graph.add_node("stage03_merge", _async_node_wrapper("stage03_merge"))

    graph.add_node("stage04_score", _async_node_wrapper("stage04_score"))
    graph.add_node("stage05_topk", _async_node_wrapper("stage05_topk"))
    graph.add_node("stage06_verify_support", _async_node_wrapper("stage06_verify_support"))
    graph.add_node("stage07_verify_skeptic", _async_node_wrapper("stage07_verify_skeptic"))
    graph.add_node("stage08_aggregate", _async_node_wrapper("stage08_aggregate"))
    graph.add_node("stage09_judge", _async_node_wrapper("stage09_judge"))

    graph.set_entry_point("stage01_normalize")
    graph.add_edge("stage01_normalize", "stage02_querygen")
    graph.add_edge("stage02_querygen", "adapter_queries")
    graph.add_edge("adapter_queries", "stage03_wiki")
    graph.add_edge("adapter_queries", "stage03_web")
    graph.add_edge("stage03_wiki", "stage03_merge")
    graph.add_edge("stage03_web", "stage03_merge")
    graph.add_edge("stage03_merge", "stage04_score")
    graph.add_edge("stage04_score", "stage05_topk")
    graph.add_edge("stage05_topk", "stage06_verify_support")
    graph.add_edge("stage06_verify_support", "stage07_verify_skeptic")
    graph.add_edge("stage07_verify_skeptic", "stage08_aggregate")
    graph.add_edge("stage08_aggregate", "stage09_judge")
    graph.add_edge("stage09_judge", langgraph_graph.END)

    checkpointer = get_graph_checkpointer()
    if checkpointer is not None:
        return graph.compile(checkpointer=checkpointer)
    return graph.compile()


STAGE_SEQUENCE: list[tuple[StageName, StageFn]] = [
    ("stage01_normalize", _run_stage("stage01_normalize")),
    ("stage02_querygen", _run_stage("stage02_querygen")),
    ("adapter_queries", _build_queries),
    ("stage03_wiki", _run_stage("stage03_wiki")),
    ("stage03_web", _run_stage("stage03_web")),
    ("stage03_merge", _run_stage("stage03_merge")),
    ("stage04_score", _run_stage("stage04_score")),
    ("stage05_topk", _run_stage("stage05_topk")),
    ("stage06_verify_support", _run_stage("stage06_verify_support")),
    ("stage07_verify_skeptic", _run_stage("stage07_verify_skeptic")),
    ("stage08_aggregate", _run_stage("stage08_aggregate")),
    ("stage09_judge", _run_stage("stage09_judge")),
]

STAGE_OUTPUT_KEYS: dict[StageName, list[str]] = {
    "stage01_normalize": [
        "claim_text",
        "original_intent",
        "claim_mode",
        "risk_markers",
        "verification_priority",
        "normalize_claims",
        "canonical_evidence",
        "entity_map",
        "prompt_normalize_user",
        "prompt_normalize_system",
        "slm_raw_normalize",
    ],
    "stage02_querygen": [
        "query_core_fact",
        "query_variants",
        "keyword_bundles",
        "search_constraints",
        "querygen_claims",
        "querygen_prompt_used",
        "prompt_querygen_user",
        "prompt_querygen_system",
        "slm_raw_querygen",
    ],
    "adapter_queries": ["search_queries"],
    "stage03_wiki": ["wiki_candidates", "stage03_wiki_diagnostics"],
    "stage03_web": ["web_candidates", "stage03_web_diagnostics"],
    "stage03_merge": ["evidence_candidates", "stage03_merge_stats"],
    "stage04_score": ["scored_evidence", "score_diagnostics"],
    "stage05_topk": [
        "citations",
        "evidence_topk",
        "evidence_topk_support",
        "evidence_topk_skeptic",
        "risk_flags",
        "topk_diagnostics",
    ],
    "stage06_verify_support": [
        "verdict_support",
        "stage06_diagnostics",
        "prompt_support_user",
        "prompt_support_system",
        "slm_raw_support",
    ],
    "stage07_verify_skeptic": [
        "verdict_skeptic",
        "stage07_diagnostics",
        "prompt_skeptic_user",
        "prompt_skeptic_system",
        "slm_raw_skeptic",
    ],
    "stage08_aggregate": ["support_pack", "skeptic_pack", "evidence_index", "judge_prep_meta"],
    "stage09_judge": [
        "final_verdict",
        "user_result",
        "risk_flags",
        "judge_retrieval",
        "stage09_diagnostics",
        "prompt_judge_user",
        "prompt_judge_system",
        "slm_raw_judge",
    ],
}


def run_stage_sequence(state: GraphState, start_stage: str | None, end_stage: str | None) -> GraphState:
    resolved_start = normalize_stage_name(start_stage, for_end=False) or STAGE_ORDER[0]
    resolved_end = normalize_stage_name(end_stage, for_end=True) or STAGE_ORDER[-1]

    start_idx = STAGE_ORDER.index(resolved_start)
    end_idx = STAGE_ORDER.index(resolved_end)
    if end_idx < start_idx:
        end_idx = start_idx

    state_dict = cast(dict[str, Any], state)
    for name, fn in STAGE_SEQUENCE[start_idx : end_idx + 1]:
        out = _with_log(name, fn)(state)
        for key, value in out.items():
            if key == "stage_logs":
                existing_logs = list(state_dict.get("stage_logs") or [])
                incoming_logs = value if isinstance(value, list) else []
                state_dict["stage_logs"] = existing_logs + incoming_logs
            elif key == "stage_outputs":
                merged_outputs = dict(state_dict.get("stage_outputs") or {})
                if isinstance(value, dict):
                    merged_outputs.update(value)
                state_dict["stage_outputs"] = merged_outputs
            elif key == "stage_full_outputs":
                merged_full = dict(state_dict.get("stage_full_outputs") or {})
                if isinstance(value, dict):
                    merged_full.update(value)
                state_dict["stage_full_outputs"] = merged_full
            else:
                state_dict[key] = value
    return state
