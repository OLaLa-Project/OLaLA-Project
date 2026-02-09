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
    explicit = str(state.get("search_mode", "")).strip().lower()
    if explicit in {"lexical", "fts", "vector"}:
        return explicit

    embeddings_ready = settings.wiki_embeddings_ready
    if explicit == "auto":
        return "auto" if embeddings_ready else "lexical"
    return "auto" if embeddings_ready else "lexical"


def _normalize_wiki_query(text: str) -> list[str]:
    if not text:
        return []
    parts = re.split(r"\s*[,&]\s*", text)
    terms: list[str] = []
    for part in parts:
        if not part or not part.strip():
            continue
        token = part.strip()
        if token:
            terms.append(token)
    return terms if terms else [text.strip()]


def _normalize_bundle_terms(items: Any) -> list[str]:
    if not isinstance(items, list):
        return []
    cleaned: list[str] = []
    for raw in items:
        if not isinstance(raw, str):
            continue
        token = raw.strip()
        if len(token) < 2:
            continue
        cleaned.append(token)

    seen: set[str] = set()
    uniq: list[str] = []
    for token in cleaned:
        if token not in seen:
            seen.add(token)
            uniq.append(token)
    return uniq


def _build_queries(state: GraphState) -> GraphState:
    variants = state.get("query_variants") or []
    search_queries: list[SearchQuery] = []
    seen: set[tuple[str, str, str, str]] = set()
    default_mode = str(state.get("claim_mode", "fact") or "fact").strip().lower() or "fact"

    keyword_bundles = state.get("keyword_bundles") or {}
    bundle_terms = _normalize_bundle_terms(keyword_bundles.get("primary"))[:2]
    constraints = state.get("search_constraints")
    constraints_meta = constraints if isinstance(constraints, dict) and constraints else {}

    for variant in variants:
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

        if final_type == "wiki":
            wiki_mode = _resolve_wiki_search_mode(state)
            normalized_terms = _normalize_wiki_query(text)[:2]
            claim_id = str(base_meta.get("claim_id", "")).strip() if isinstance(base_meta, dict) else ""
            for term in normalized_terms:
                key = (final_type, term, wiki_mode, claim_id)
                if not term or key in seen:
                    continue
                seen.add(key)
                meta: dict[str, Any] = {}
                if isinstance(base_meta, dict) and base_meta:
                    meta.update(base_meta)
                meta.setdefault("original", text)
                meta.setdefault("mode", default_mode)
                if constraints_meta:
                    meta.setdefault("search_constraints", constraints_meta)
                search_queries.append(
                    {
                        "type": "wiki",
                        "text": term,
                        "search_mode": cast(Any, wiki_mode),
                        "meta": meta,
                    }
                )
        else:
            claim_id = str(base_meta.get("claim_id", "")).strip() if isinstance(base_meta, dict) else ""
            key = (final_type, text, "", claim_id)
            if key in seen:
                continue
            seen.add(key)
            query: SearchQuery = {"type": cast(Any, final_type), "text": text}
            meta: dict[str, Any] = {}
            if isinstance(base_meta, dict) and base_meta:
                meta.update(base_meta)
            meta.setdefault("mode", default_mode)
            if constraints_meta:
                meta.setdefault("search_constraints", constraints_meta)
            if meta:
                query["meta"] = meta
            search_queries.append(query)

    if bundle_terms:
        wiki_mode = _resolve_wiki_search_mode(state)
        for term in bundle_terms:
            key = ("wiki", term, wiki_mode, "bundle")
            if not term or key in seen:
                continue
            seen.add(key)
            meta: dict[str, Any] = {
                "original": term,
                "source": "keyword_bundles",
                "intent": "entity_profile",
                "mode": default_mode,
            }
            if constraints_meta:
                meta["search_constraints"] = constraints_meta
            search_queries.append(
                {
                    "type": "wiki",
                    "text": term,
                    "search_mode": cast(Any, wiki_mode),
                    "meta": meta,
                }
            )

    claim_text = state.get("claim_text")
    if not search_queries and isinstance(claim_text, str) and claim_text.strip():
        search_queries = [{"type": "direct", "text": claim_text}]

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
    "stage03_wiki": ["wiki_candidates"],
    "stage03_web": ["web_candidates"],
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
