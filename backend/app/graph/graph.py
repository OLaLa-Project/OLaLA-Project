import uuid
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List

from app.core.schemas import TruthCheckRequest, TruthCheckResponse, Citation, ModelInfo
from app.graph.state import GraphState
from app.graph.stage_logger import attach_stage_log, log_stage_event, prepare_stage_output
from app.gateway.stage_manager import run as run_stage
from app.stages.stage03_collect.node import run_wiki_async, run_web_async

try:
    from langgraph.graph import StateGraph, END  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    StateGraph = None
    END = None


def _build_queries(state: Dict[str, Any]) -> Dict[str, Any]:
    variants = state.get("query_variants", [])
    search_queries: List[str] = []
    for v in variants:
        text = (v.get("text") or "").strip()
        if not text:
            continue
        search_queries.append(text)
    if not search_queries and state.get("claim_text"):
        search_queries = [state["claim_text"]]
    return {"search_queries": search_queries}


import time

def _with_log(stage_name: str, fn):
    def wrapper(state: Dict[str, Any]) -> Dict[str, Any]:
        log_stage_event(state, stage_name, "start")
        start = time.time()
        try:
            out = fn(state)
        except Exception as e:
            # log error? logic handled inside fn usually, but catching here just in case
            raise e
        return attach_stage_log(state, stage_name, out, started_at=start)
    return wrapper


def _run_stage(stage_name: str):
    def _runner(state: Dict[str, Any]) -> Dict[str, Any]:
        # If we are in an async context (like app.astream), running a sync function 
        # that calls asyncio.run() (like stage03) will fail.
        # However, _runner itself is called by LangGraph. 
        # If LangGraph calls this in a threadpool, we are fine.
        # But if LangGraph runs it specifically, we might need protection.
        # Since we can't easily await inside this sync _runner, we rely on LangGraph's config 
        # or we accept that _runner is blocking. 
        # The issue "Cannot run event loop" happens when _runner calls asyncio.run() 
        # WHILE inside a running loop.
        
        # We'll handle this in the graph definition by wrapping with asyncio.to_thread 
        # IF we make the node async. 
        # BETTER: Make the node wrapper async compatible.
        return run_stage(stage_name, state)
    return _runner

# Wrapper to make sync stage functions safe for LangGraph async execution
import asyncio
import functools

def _async_node_wrapper(stage_name: str):
    """Wraps a sync stage function to run in a thread, avoiding asyncio.run() conflicts."""
    async def _async_runner(state: Dict[str, Any]) -> Dict[str, Any]:
        fn = _with_log(stage_name, _run_stage(stage_name))
        return await asyncio.to_thread(fn, state)
    return _async_runner


def _async_stage_wrapper(stage_name: str, async_fn):
    async def _runner(state: Dict[str, Any]) -> Dict[str, Any]:
        logger = logging.getLogger("uvicorn.error")
        log_stage_event(state, stage_name, "start")
        logger.info(f"[{state.get('trace_id', 'unknown')}] {stage_name} start")
        start = time.time()
        out = await async_fn(state)
        logger.info(f"[{state.get('trace_id', 'unknown')}] {stage_name} end")
        return attach_stage_log(state, stage_name, out, started_at=start)
    return _runner

def _async_adapter_wrapper():
    async def _runner(state: Dict[str, Any]) -> Dict[str, Any]:
         # Adapter is simple sync
         fn = _with_log("adapter_queries", _build_queries)
         return await asyncio.to_thread(fn, state)
    return _runner


def build_langgraph() -> Any:
    if StateGraph is None:
        return None

    graph = StateGraph(GraphState)
    
    # 1. Linear Setup Nodes
    graph.add_node("stage01_normalize", _async_node_wrapper("stage01_normalize"))
    graph.add_node("stage02_querygen", _async_node_wrapper("stage02_querygen"))
    graph.add_node("adapter_queries", _async_adapter_wrapper())
    
    # 2. Split Stage 3 (Granular Visibility matched to Goold Logic)
    graph.add_node("stage03_wiki", _async_stage_wrapper("stage03_wiki", run_wiki_async))
    graph.add_node("stage03_web", _async_stage_wrapper("stage03_web", run_web_async))
    graph.add_node("stage03_merge", _async_node_wrapper("stage03_merge"))
    
    # 3. Intermediate Processing
    graph.add_node("stage04_score", _async_node_wrapper("stage04_score"))
    graph.add_node("stage05_topk", _async_node_wrapper("stage05_topk"))
    
    # 4. Sequential Verification Nodes (As requested)
    graph.add_node("stage06_verify_support", _async_node_wrapper("stage06_verify_support"))
    graph.add_node("stage07_verify_skeptic", _async_node_wrapper("stage07_verify_skeptic"))
    
    # 5. Convergence & Finalize
    graph.add_node("stage08_aggregate", _async_node_wrapper("stage08_aggregate"))
    graph.add_node("stage09_judge", _async_node_wrapper("stage09_judge"))

    # --- EDGES ---
    graph.set_entry_point("stage01_normalize")
    graph.add_edge("stage01_normalize", "stage02_querygen")
    graph.add_edge("stage02_querygen", "adapter_queries")
    
    # Stage 3 Parallelism (Wiki || Web)
    # Fan-Out
    graph.add_edge("adapter_queries", "stage03_wiki")
    graph.add_edge("adapter_queries", "stage03_web")
    
    # Fan-In
    graph.add_edge("stage03_wiki", "stage03_merge")
    graph.add_edge("stage03_web", "stage03_merge")
    
    graph.add_edge("stage03_merge", "stage04_score")
    
    graph.add_edge("stage04_score", "stage05_topk")
    
    # Sequential Verification (Strict)
    graph.add_edge("stage05_topk", "stage06_verify_support")
    graph.add_edge("stage06_verify_support", "stage07_verify_skeptic")
    graph.add_edge("stage07_verify_skeptic", "stage08_aggregate")
    
    graph.add_edge("stage08_aggregate", "stage09_judge")
    graph.add_edge("stage09_judge", END)
    
    return graph.compile()


STAGE_SEQUENCE = [
    ("stage01_normalize", _run_stage("stage01_normalize")),
    ("stage02_querygen", _run_stage("stage02_querygen")),
    ("adapter_queries", _build_queries),
    # Parallel simulation order for legacy list
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

STAGE_OUTPUT_KEYS: Dict[str, List[str]] = {
    "stage01_normalize": [
        "claim_text",
        "canonical_evidence",
        "entity_map",
        "prompt_normalize_user",
        "prompt_normalize_system",
        "slm_raw_normalize",
        "transcript",
    ],
    "stage02_querygen": [
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
    "stage03_merge": ["evidence_candidates"],
    "stage04_score": ["scored_evidence"],
    "stage05_topk": ["citations", "evidence_topk", "risk_flags"],
    "stage06_verify_support": ["verdict_support", "prompt_support_user", "prompt_support_system", "slm_raw_support"],
    "stage07_verify_skeptic": ["verdict_skeptic", "prompt_skeptic_user", "prompt_skeptic_system", "slm_raw_skeptic"],
    "stage08_aggregate": ["draft_verdict", "quality_score"],
    "stage09_judge": [
        "final_verdict",
        "user_result",
        "risk_flags",
        "prompt_judge_user",
        "prompt_judge_system",
        "slm_raw_judge",
    ],
}


def run_stage_sequence(state: Dict[str, Any], start_stage: str | None, end_stage: str | None) -> Dict[str, Any]:
    name_list = [name for name, _ in STAGE_SEQUENCE]
    if start_stage not in name_list:
        start_stage = name_list[0]
    if end_stage not in name_list:
        end_stage = name_list[-1]
    start_idx = name_list.index(start_stage)
    end_idx = name_list.index(end_stage)
    if end_idx < start_idx:
        end_idx = start_idx

    for name, fn in STAGE_SEQUENCE[start_idx : end_idx + 1]:
        print(f"DEBUG: Executing stage {name}")
        # Log before execution (optional, but consistent with wrapper)
        # Using _with_log logic inside loop for simplicity or wrapper
        out = _with_log(name, fn)(state)
        
        # merge outputs into state
        for key, value in out.items():
            if key == "stage_logs":
                state["stage_logs"] = state.get("stage_logs", []) + value
            elif key == "stage_outputs":
                merged = dict(state.get("stage_outputs") or {})
                merged.update(value)
                state["stage_outputs"] = merged
            elif key == "stage_full_outputs":
                merged = dict(state.get("stage_full_outputs") or {})
                merged.update(value)
                state["stage_full_outputs"] = merged
            else:
                state[key] = value
    return state


# Logic migrated to app.gateway.service
# run_pipeline, run_pipeline_stream, and _build_response removed from here.

