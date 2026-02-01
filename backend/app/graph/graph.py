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


def _run_stage(stage_name: str):
    def _runner(state: Dict[str, Any]) -> Dict[str, Any]:
        return run_stage(stage_name, state)
    return _runner


def _with_log(stage_name: str, fn):
    def _runner(state: Dict[str, Any]) -> Dict[str, Any]:
        started_at = None
        try:
            start_log = log_stage_event(state, stage_name, "start")
            from time import time as _time
            started_at = _time()
            out = fn(state)
            end_log = attach_stage_log(state, stage_name, out, started_at=started_at)
            merged = dict(end_log)
            merged["stage_logs"] = start_log["stage_logs"] + end_log["stage_logs"]
            allowed = STAGE_OUTPUT_KEYS.get(stage_name, [])
            stage_payload = {k: out.get(k) for k in allowed if k in out}
            merged["stage_outputs"] = {stage_name: prepare_stage_output(stage_payload)}
            if state.get("include_full_outputs"):
                merged["stage_full_outputs"] = {stage_name: stage_payload}
            return merged
        except Exception as exc:
            err_entry = log_stage_event(state, stage_name, "error")
            err_entry["stage_logs"][0]["error"] = str(exc)
            raise
    return _runner


def build_langgraph() -> Any:
    if StateGraph is None:
        return None

    graph = StateGraph(GraphState)
    graph.add_node("stage01_normalize", _with_log("stage01_normalize", _run_stage("stage01_normalize")))
    graph.add_node("stage02_querygen", _with_log("stage02_querygen", _run_stage("stage02_querygen")))
    graph.add_node("adapter_queries", _with_log("adapter_queries", _build_queries))
    graph.add_node("stage03_collect", _with_log("stage03_collect", _run_stage("stage03_collect")))
    graph.add_node("stage04_score", _with_log("stage04_score", _run_stage("stage04_score")))
    graph.add_node("stage05_topk", _with_log("stage05_topk", _run_stage("stage05_topk")))
    graph.add_node("stage06_verify_support", _with_log("stage06_verify_support", _run_stage("stage06_verify_support")))
    graph.add_node("stage07_verify_skeptic", _with_log("stage07_verify_skeptic", _run_stage("stage07_verify_skeptic")))
    graph.add_node("stage08_aggregate", _with_log("stage08_aggregate", _run_stage("stage08_aggregate")))
    graph.add_node("stage09_judge", _with_log("stage09_judge", _run_stage("stage09_judge")))

    graph.set_entry_point("stage01_normalize")
    graph.add_edge("stage01_normalize", "stage02_querygen")
    graph.add_edge("stage02_querygen", "adapter_queries")
    graph.add_edge("adapter_queries", "stage03_collect")
    graph.add_edge("stage03_collect", "stage04_score")
    graph.add_edge("stage04_score", "stage05_topk")
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
    ("stage03_collect", _run_stage("stage03_collect")),
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
    "stage03_collect": ["evidence_candidates"],
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

    # stage-by-stage execution (always full pipeline)
    out = run_stage_sequence(state, None, None)
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
        analysis_id=state["trace_id"],
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
            version=model_meta.get("version", "v1.0"),
        ),
        latency_ms=latency_ms,
        cost_usd=cost_usd,
        created_at=created_at,
    )
