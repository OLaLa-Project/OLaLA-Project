import json
import os
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from app.core.observability import record_stage_result
from app.core.settings import settings

_LOG_DIR = settings.log_dir
_PIPELINE_DIR = os.path.join(_LOG_DIR, "pipeline")


def _ensure_dir() -> None:
    os.makedirs(_PIPELINE_DIR, exist_ok=True)


def _summarize(value: Any) -> Any:
    if isinstance(value, str):
        return value[:200]
    if isinstance(value, list):
        return {"type": "list", "len": len(value)}
    if isinstance(value, dict):
        keys = list(value.keys())
        return {"type": "dict", "keys": keys[:20]}
    return value


def _summarize_output(output: Dict[str, Any]) -> Dict[str, Any]:
    summary: Dict[str, Any] = {}
    for key, value in output.items():
        if key in _IGNORE_STAGE_OUTPUT_KEYS:
            continue
        if key in {"evidence_candidates", "scored_evidence", "citations", "evidence_topk"}:
            summary[key] = len(value) if isinstance(value, list) else 0
        else:
            summary[key] = _summarize(value)
    return summary


def _trim_list(items: list, limit: int = 3) -> Dict[str, Any]:
    return {
        "len": len(items),
        "sample": items[:limit],
    }


_IGNORE_STAGE_OUTPUT_KEYS = {
    "trace_id",
    "input_type",
    "input_payload",
    "user_request",
    "language",
    "search_mode",
    "stage_logs",
    "stage_outputs",
    "querygen_prompt",
    "querygen_prompt_used",
    "querygen_claims",
}


def prepare_stage_output(output: Dict[str, Any]) -> Dict[str, Any]:
    trimmed: Dict[str, Any] = {}
    for key, value in output.items():
        if key in _IGNORE_STAGE_OUTPUT_KEYS:
            continue
        if isinstance(value, list):
            trimmed[key] = _trim_list(value, limit=3)
        elif isinstance(value, dict):
            trimmed[key] = value
        else:
            trimmed[key] = value
    return trimmed


def _write_log(entry: Dict[str, Any]) -> None:
    try:
        log_dir = entry.get("log_dir")
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)
            stage = entry.get("stage", "stage")
            path = os.path.join(log_dir, f"{stage}.json")
        else:
            _ensure_dir()
            trace_id = entry.get("trace_id", "unknown")
            stage = entry.get("stage", "stage")
            path = os.path.join(_PIPELINE_DIR, f"{trace_id}_{stage}.json")

        with open(path, "w", encoding="utf-8") as f:
            json.dump(entry, f, ensure_ascii=False, indent=2)
    except Exception:
        # best-effort logging only
        return


def _make_entry(
    state: Dict[str, Any],
    stage: str,
    event: str,
    output: Optional[Dict[str, Any]] = None,
    error: Optional[str] = None,
    duration_ms: Optional[int] = None,
) -> Dict[str, Any]:
    entry: Dict[str, Any] = {
        "trace_id": state.get("trace_id"),
        "stage": stage,
        "event": event,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "input_keys": list(state.keys()),
    }
    if "log_dir" in state:
        entry["log_dir"] = state["log_dir"]
    if output is not None:
        entry["output_summary"] = _summarize_output(output)
        if state.get("include_full_outputs"):
            entry["output"] = output
    if error:
        entry["error"] = error
    if duration_ms is not None:
        entry["duration_ms"] = duration_ms
    return entry


def log_stage_event(state: Dict[str, Any], stage: str, event: str) -> Dict[str, Any]:
    entry = _make_entry(state, stage, event)
    _write_log(entry)
    return {"stage_logs": [entry]}


def attach_stage_log(
    state: Dict[str, Any],
    stage: str,
    output: Dict[str, Any],
    started_at: Optional[float] = None,
) -> Dict[str, Any]:
    duration_ms = None
    if started_at is not None:
        duration_ms = int((time.time() - started_at) * 1000)
    entry = _make_entry(state, stage, "end", output=output, duration_ms=duration_ms)
    _write_log(entry)
    record_stage_result(
        stage,
        trace_id=str(state.get("trace_id", "unknown")),
        duration_ms=duration_ms,
        ok=True,
    )

    out = dict(output)
    out["stage_logs"] = [entry]
    return out
