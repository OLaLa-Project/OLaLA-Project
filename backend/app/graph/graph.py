import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List

from app.core.schemas import TruthCheckRequest, TruthCheckResponse, Citation, ModelInfo
from app.graph.state import GraphState
from app.graph.stage_logger import attach_stage_log, log_stage_event, prepare_stage_output
from app.stages.stage01_normalize.node import run as stage01_normalize
from app.stages.stage02_querygen.node import run as stage02_querygen
from app.stages.stage03_collect.node import run as stage03_collect
from app.stages.stage04_score.node import run as stage04_score
from app.stages.stage05_topk.node import run as stage05_topk

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
    graph.add_node("stage01_normalize", _with_log("stage01_normalize", stage01_normalize))
    graph.add_node("stage02_querygen", _with_log("stage02_querygen", stage02_querygen))
    graph.add_node("adapter_queries", _with_log("adapter_queries", _build_queries))
    graph.add_node("stage03_collect", _with_log("stage03_collect", stage03_collect))
    graph.add_node("stage04_score", _with_log("stage04_score", stage04_score))
    graph.add_node("stage05_topk", _with_log("stage05_topk", stage05_topk))

    graph.set_entry_point("stage01_normalize")
    graph.add_edge("stage01_normalize", "stage02_querygen")
    graph.add_edge("stage02_querygen", "adapter_queries")
    graph.add_edge("adapter_queries", "stage03_collect")
    graph.add_edge("stage03_collect", "stage04_score")
    graph.add_edge("stage04_score", "stage05_topk")
    graph.add_edge("stage05_topk", END)
    return graph.compile()


STAGE_SEQUENCE = [
    ("stage01_normalize", stage01_normalize),
    ("stage02_querygen", stage02_querygen),
    ("adapter_queries", _build_queries),
    ("stage03_collect", stage03_collect),
    ("stage04_score", stage04_score),
    ("stage05_topk", stage05_topk),
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

    # stage-by-stage execution (range controllable)
    out = run_stage_sequence(state, req.start_stage, req.end_stage)
    def _map_source_type(raw: str) -> str:
        raw = (raw or "").upper()
        if raw in {"NEWS"}:
            return "NEWS"
        if raw in {"WIKIPEDIA", "KB_DOC", "KNOWLEDGE_BASE"}:
            return "WIKIPEDIA"
        return "WEB_URL"

    citations = [
        Citation(
            source_type=_map_source_type(c.get("source_type")),
            title=c.get("title", ""),
            url=c.get("url", ""),
            quote=(c.get("content") or "")[:500],
            relevance=c.get("score"),
        )
        for c in out.get("citations", [])
    ]

    label = "UNVERIFIED"
    summary = "Stage5 완료. 증거 요약 필요."

    return TruthCheckResponse(
        analysis_id=state["trace_id"],
        label=label,
        confidence=0.0,
        summary=summary,
        rationale=[],
        citations=citations,
        counter_evidence=[],
        limitations=[],
        recommended_next_steps=[],
        risk_flags=out.get("risk_flags", []),
        stage_logs=out.get("stage_logs", []),
        stage_outputs=out.get("stage_outputs", {}),
        stage_full_outputs=out.get("stage_full_outputs", {}),
        model_info=ModelInfo(provider="local", model="pipeline", version="v0.1"),
        latency_ms=0,
        cost_usd=0.0,
        created_at=datetime.now(timezone.utc).isoformat(),
    )
