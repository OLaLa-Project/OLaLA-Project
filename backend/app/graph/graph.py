import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List

from app.core.schemas import TruthCheckRequest, TruthCheckResponse, Citation, ModelInfo
from app.graph.state import GraphState
from app.graph.stage_logger import attach_stage_log, log_stage_event, prepare_stage_output
from app.gateway.stage_manager import run as run_stage

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
    graph.add_node("stage03_wiki", _async_node_wrapper("stage03_wiki"))
    graph.add_node("stage03_web", _async_node_wrapper("stage03_web"))
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
    "stage01_normalize": ["claim_text", "canonical_evidence", "entity_map"],
    "stage02_querygen": [
        "query_variants",
        "keyword_bundles",
        "search_constraints",
        "querygen_claims",
        "querygen_prompt_used",
    ],
    "adapter_queries": ["search_queries"],
    "stage03_wiki": ["wiki_candidates"],
    "stage03_web": ["web_candidates"],
    "stage03_merge": ["evidence_candidates"],
    "stage04_score": ["scored_evidence"],
    "stage05_topk": ["citations", "evidence_topk", "risk_flags"],
    "stage06_verify_support": ["verdict_support"],
    "stage07_verify_skeptic": ["verdict_skeptic"],
    "stage08_aggregate": ["draft_verdict", "quality_score"],
    "stage09_judge": ["final_verdict", "user_result", "risk_flags"],
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


def run_pipeline(req: TruthCheckRequest) -> TruthCheckResponse:
    # Manual sequence execution to match debug_pipeline.py logic exactly
    state: Dict[str, Any] = {
        "trace_id": str(uuid.uuid4()),
        "input_type": req.input_type,
        "input_payload": req.input_payload,
        "user_request": req.user_request or "",
        "language": req.language or "ko",
        "search_mode": "auto",
        "stage_logs": [],
        "stage_outputs": {},
        "stage_full_outputs": {},
    }
    if req.include_full_outputs:
        state["include_full_outputs"] = True
    if isinstance(req.stage_state, dict):
        state.update(req.stage_state)
    if req.normalize_mode:
        state["normalize_mode"] = req.normalize_mode
    if req.querygen_prompt:
        state["querygen_prompt"] = req.querygen_prompt

    # Execute manual sequence
    out = run_stage_sequence(state, req.start_stage, req.end_stage)
    return _build_response(out, state["trace_id"])


def _run_pipeline_legacy(req: TruthCheckRequest) -> TruthCheckResponse:
    return run_pipeline(req)


async def run_pipeline_stream(req: TruthCheckRequest):
    import json
    
    app = build_langgraph()
    if app is None:
        yield json.dumps({"event": "error", "data": "LangGraph not initialized"}) + "\n"
        return

    # Normal initialization
    state: Dict[str, Any] = {
        "trace_id": str(uuid.uuid4()),
        "input_type": req.input_type,
        "input_payload": req.input_payload,
        "user_request": req.user_request or "",
        "language": req.language or "ko",
        "search_mode": "auto",
        "stage_logs": [],
        "stage_outputs": {},
        "stage_full_outputs": {},
    }
    if req.include_full_outputs:
        state["include_full_outputs"] = True
    if isinstance(req.stage_state, dict):
        state.update(req.stage_state)
    if req.normalize_mode:
        state["normalize_mode"] = req.normalize_mode
    if req.querygen_prompt:
        state["querygen_prompt"] = req.querygen_prompt

    import logging
    logger = logging.getLogger(__name__)

    # Custom serializer for Pydantic models
    def pydantic_encoder(obj):
        if hasattr(obj, "model_dump"):
            return obj.model_dump()
        if hasattr(obj, "__dict__"):
            return obj.__dict__
        return str(obj)

    final_state = state.copy()
    
    # Execute Graph Stream (Async-safe now due to wrappers)
    try:
        async for output in app.astream(state):
            # output is typically {node_name: {key: val, ...}}
            for node_name, node_state in output.items():
                logger.info(f"Stream yielded node: {node_name}")
                
                # Update our accumulated state
                final_state.update(node_state)
                
                # Get stage data via standard keys or stage_outputs
                stage_data = node_state.get("stage_outputs", {}).get(node_name, {})
                
                # Fallback: if empty, check if keys exist directly in node_state
                if not stage_data and node_name in STAGE_OUTPUT_KEYS:
                     keys = STAGE_OUTPUT_KEYS[node_name]
                     subset = {k: node_state.get(k) for k in keys if k in node_state}
                     if subset:
                         stage_data = subset
                
                # Yield event
                try:
                    payload = json.dumps({
                        "event": "stage_complete",
                        "stage": node_name,
                        "data": stage_data
                    }, default=pydantic_encoder)
                    yield payload + "\n"
                except Exception as e:
                    logger.error(f"Serialization failed for {node_name}: {e}")
                    yield json.dumps({
                        "event": "error",
                        "stage": node_name, 
                        "data": f"Serialization error: {str(e)}"
                    }) + "\n"

    except Exception as e:
        logger.error(f"Stream execution failed: {e}")
        yield json.dumps({"event": "error", "data": str(e)}) + "\n"

    # Final complete event
    final_response = _build_response(final_state, state["trace_id"])
    yield json.dumps({
        "event": "complete",
        "data": final_response.model_dump()
    }, default=pydantic_encoder) + "\n"


def _build_response(out: Dict[str, Any], trace_id: str) -> TruthCheckResponse:
    """Build TruthCheckResponse from pipeline output state."""
    def _map_source_type(raw: str) -> str:
        raw = (raw or "").upper()
        if raw in {"NEWS"}:
            return "NEWS"
        if raw in {"WIKIPEDIA", "KB_DOC", "KNOWLEDGE_BASE"}:
            return "WIKIPEDIA"
        return "WEB_URL"

    final_verdict = out.get("final_verdict") if isinstance(out.get("final_verdict"), dict) else None
    if final_verdict:
        label = final_verdict.get("label", "UNVERIFIED")
        confidence = final_verdict.get("confidence", 0.0)
        summary = final_verdict.get("summary", "")
        rationale = final_verdict.get("rationale", [])
        counter_evidence = final_verdict.get("counter_evidence", [])
        limitations = final_verdict.get("limitations", [])
        recommended_next_steps = final_verdict.get("recommended_next_steps", [])
        risk_flags = final_verdict.get("risk_flags", out.get("risk_flags", []))
        model_meta = final_verdict.get("model_info", {"provider": "openai", "model": "gpt-4.1", "version": "v1.0"})
        latency_ms = final_verdict.get("latency_ms", 0)
        cost_usd = final_verdict.get("cost_usd", 0.0)
        created_at = final_verdict.get("created_at", datetime.now(timezone.utc).isoformat())
        citation_source = final_verdict.get("citations", [])
    else:
        label = "UNVERIFIED"
        confidence = 0.0
        summary = "Stage5 완료. 증거 요약 필요."
        rationale = []
        counter_evidence = []
        limitations = []
        recommended_next_steps = []
        risk_flags = out.get("risk_flags", [])
        model_meta = {"provider": "local", "model": "pipeline", "version": "v0.1"}
        latency_ms = 0
        cost_usd = 0.0
        created_at = datetime.now(timezone.utc).isoformat()
        citation_source = out.get("citations", [])

    citations = [
        Citation(
            source_type=_map_source_type(c.get("source_type")),
            title=c.get("title", ""),
            url=c.get("url", ""),
            quote=(c.get("quote") or c.get("content") or "")[:500],
            relevance=c.get("relevance", c.get("score")),
        )
        for c in citation_source
    ]

    return TruthCheckResponse(
        analysis_id=trace_id,
        label=label,
        confidence=confidence,
        summary=summary,
        rationale=rationale,
        citations=citations,
        counter_evidence=counter_evidence,
        limitations=limitations,
        recommended_next_steps=recommended_next_steps,
        risk_flags=risk_flags,
        stage_logs=out.get("stage_logs", []),
        stage_outputs=out.get("stage_outputs", {}),
        stage_full_outputs=out.get("stage_full_outputs", {}),
        model_info=ModelInfo(
            provider=model_meta.get("provider", "openai"),
            model=model_meta.get("model", "gpt-4.1"),
            version=model_meta.get("version", "v1. 0"),
        ),
        latency_ms=latency_ms,
        cost_usd=cost_usd,
        created_at=created_at,
    )

