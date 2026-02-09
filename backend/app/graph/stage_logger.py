import json
import os
import time
import hashlib
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from app.core.observability import record_stage_result
from app.core.settings import settings

_LOG_DIR = settings.log_dir
_PIPELINE_DIR = os.path.join(_LOG_DIR, "pipeline")
_ARTIFACTS_DIR = os.path.join(_LOG_DIR, "pipeline_artifacts")
_ARTIFACTS_BY_DATE_DIR = os.path.join(_ARTIFACTS_DIR, "by_date")
_ARTIFACT_INDEX_PATH = os.path.join(_ARTIFACTS_DIR, "artifact_index.jsonl")
_ARTIFACT_LATEST_PATH = os.path.join(_ARTIFACTS_DIR, "latest_artifact.json")
_TRACE_RUN_DIR_CACHE: Dict[str, str] = {}


def _ensure_dir() -> None:
    os.makedirs(_PIPELINE_DIR, exist_ok=True)
    os.makedirs(_ARTIFACTS_DIR, exist_ok=True)
    os.makedirs(_ARTIFACTS_BY_DATE_DIR, exist_ok=True)


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
        if key in {
            "evidence_candidates",
            "scored_evidence",
            "citations",
            "evidence_topk",
            "evidence_topk_support",
            "evidence_topk_skeptic",
        }:
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


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _sha256_text(value: str) -> str:
    if not value:
        return ""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _resolve_artifact_dt(artifact: Dict[str, Any]) -> datetime:
    ts = artifact.get("timestamp")
    if isinstance(ts, str) and ts.strip():
        normalized = ts.replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(normalized)
            if parsed.tzinfo is None:
                return parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)
        except ValueError:
            pass
    return datetime.now(timezone.utc)


def _artifact_sort_key(dt_utc: datetime) -> str:
    return dt_utc.strftime("%Y%m%dT%H%M%S.%fZ")


def _find_existing_trace_dir(trace_id: str) -> Optional[str]:
    suffix = f"__{trace_id}"
    try:
        candidates = []
        for entry in os.listdir(_ARTIFACTS_DIR):
            path = os.path.join(_ARTIFACTS_DIR, entry)
            if not os.path.isdir(path):
                continue
            if entry == trace_id or entry.endswith(suffix):
                candidates.append(entry)
        if not candidates:
            return None
        candidates.sort()
        timestamped = [name for name in candidates if name.endswith(suffix)]
        selected = timestamped[-1] if timestamped else candidates[-1]
        return os.path.join(_ARTIFACTS_DIR, selected)
    except OSError:
        return None


def _resolve_trace_dir(trace_id: str, artifact_dt: datetime) -> str:
    cached = _TRACE_RUN_DIR_CACHE.get(trace_id)
    if cached:
        return cached

    existing = _find_existing_trace_dir(trace_id)
    if existing:
        _TRACE_RUN_DIR_CACHE[trace_id] = existing
        return existing

    run_dir_name = f"{_artifact_sort_key(artifact_dt)}__{trace_id}"
    run_dir = os.path.join(_ARTIFACTS_DIR, run_dir_name)
    _TRACE_RUN_DIR_CACHE[trace_id] = run_dir
    return run_dir


def _pick_first(stage_output: Dict[str, Any], predicate) -> str:
    for key, value in stage_output.items():
        if predicate(key) and isinstance(value, str) and value.strip():
            return value
    return ""


def _extract_llm_io(stage_output: Dict[str, Any]) -> Dict[str, Any]:
    prompt_user = _pick_first(stage_output, lambda k: isinstance(k, str) and k.startswith("prompt_") and k.endswith("_user"))
    prompt_system = _pick_first(stage_output, lambda k: isinstance(k, str) and k.startswith("prompt_") and k.endswith("_system"))
    slm_raw = _pick_first(stage_output, lambda k: isinstance(k, str) and k.startswith("slm_raw_"))
    if not prompt_user and isinstance(stage_output.get("querygen_prompt_used"), str):
        prompt_user = stage_output.get("querygen_prompt_used", "")
    return {
        "prompt_user": prompt_user,
        "prompt_system": prompt_system,
        "slm_raw": slm_raw,
        "prompt_user_sha256": _sha256_text(prompt_user),
        "prompt_system_sha256": _sha256_text(prompt_system),
        "slm_raw_sha256": _sha256_text(slm_raw),
        "has_llm_io": bool(prompt_user or prompt_system or slm_raw),
    }


def _strip_llm_fields(stage_output: Dict[str, Any]) -> Dict[str, Any]:
    return {
        key: value
        for key, value in stage_output.items()
        if not (isinstance(key, str) and key.startswith(("prompt_", "slm_raw_")))
    }


def _extract_guardrail_hints(stage_output: Dict[str, Any]) -> Dict[str, Any]:
    hints: Dict[str, Any] = {}
    diagnostics: Dict[str, Any] = {}

    for key, value in stage_output.items():
        if not (isinstance(key, str) and key.endswith("_diagnostics") and isinstance(value, dict)):
            continue
        diagnostics[key] = value

    for key in ("stage06_diagnostics", "stage07_diagnostics"):
        diag = diagnostics.get(key, {})
        if not isinstance(diag, dict):
            continue
        for field in (
            "parse_ok",
            "parse_retry_used",
            "raw_len",
            "citation_input_count",
            "citation_valid_count",
            "partial_recovered",
        ):
            if field in diag:
                hints[f"{key}.{field}"] = diag.get(field)

    stage09_diag = diagnostics.get("stage09_diagnostics", {})
    if isinstance(stage09_diag, dict):
        for field in (
            "schema_mismatch",
            "fail_closed",
            "fallback_applied",
            "fallback_reason",
            "recovered_selected_count",
            "selected_evidence_count",
            "final_confidence_percent",
        ):
            if field in stage09_diag:
                hints[f"stage09_diagnostics.{field}"] = stage09_diag.get(field)

    risk_flags = stage_output.get("risk_flags")
    if not isinstance(risk_flags, list):
        final_verdict = stage_output.get("final_verdict")
        if isinstance(final_verdict, dict):
            risk_flags = final_verdict.get("risk_flags")
    if isinstance(risk_flags, list):
        hints["risk_flags"] = [flag for flag in risk_flags if isinstance(flag, str)]

    return hints


def _build_stage_ai_artifact(
    state: Dict[str, Any],
    stage: str,
    stage_output: Dict[str, Any],
    duration_ms: Optional[int],
) -> Dict[str, Any]:
    llm = _extract_llm_io(stage_output)
    stage_json = _strip_llm_fields(stage_output)
    stage_json_dump = _canonical_json(stage_json)
    guardrail_hints = _extract_guardrail_hints(stage_output)

    return {
        "schema_version": "truthcheck.stage_artifact.v1",
        "trace_id": state.get("trace_id"),
        "stage": stage,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "duration_ms": duration_ms,
        "llm": llm,
        "stage_json": stage_json,
        "guardrail_hints": guardrail_hints,
        "comparison_hints": {
            "stage_json_keys": sorted(stage_json.keys()),
            "stage_json_sha256": _sha256_text(stage_json_dump),
            "stage_json_key_count": len(stage_json),
            "llm_present": llm["has_llm_io"],
        },
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
        _ensure_dir()
        trace_id = entry.get("trace_id", "unknown")
        stage = entry.get("stage", "stage")
        path = os.path.join(_PIPELINE_DIR, f"{trace_id}_{stage}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(entry, f, ensure_ascii=False, indent=2, default=str)
    except Exception:
        # best-effort logging only
        return


def _write_stage_artifact(artifact: Dict[str, Any]) -> Dict[str, str]:
    try:
        _ensure_dir()
        trace_id = str(artifact.get("trace_id") or "unknown")
        stage = str(artifact.get("stage") or "stage")
        artifact_dt = _resolve_artifact_dt(artifact)
        trace_dir = _resolve_trace_dir(trace_id, artifact_dt)
        os.makedirs(trace_dir, exist_ok=True)
        date_key = artifact_dt.strftime("%Y-%m-%d")
        sort_key = _artifact_sort_key(artifact_dt)
        dated_dir = os.path.join(_ARTIFACTS_BY_DATE_DIR, date_key)
        os.makedirs(dated_dir, exist_ok=True)

        stage_path = os.path.join(trace_dir, f"{stage}.json")
        with open(stage_path, "w", encoding="utf-8") as f:
            json.dump(artifact, f, ensure_ascii=False, indent=2, default=str)

        dated_filename = f"{sort_key}__{trace_id}__{stage}.json"
        dated_path = os.path.join(dated_dir, dated_filename)
        with open(dated_path, "w", encoding="utf-8") as f:
            json.dump(artifact, f, ensure_ascii=False, indent=2, default=str)

        jsonl_path = os.path.join(trace_dir, "stage_artifacts.jsonl")
        with open(jsonl_path, "a", encoding="utf-8") as f:
            f.write(_canonical_json(artifact))
            f.write("\n")

        index_entry = {
            "timestamp": artifact.get("timestamp"),
            "sort_key": sort_key,
            "date": date_key,
            "trace_id": trace_id,
            "run_dir": os.path.basename(trace_dir),
            "stage": stage,
            "artifact_path": stage_path,
            "artifact_path_dated": dated_path,
        }
        with open(_ARTIFACT_INDEX_PATH, "a", encoding="utf-8") as f:
            f.write(_canonical_json(index_entry))
            f.write("\n")
        with open(_ARTIFACT_LATEST_PATH, "w", encoding="utf-8") as f:
            json.dump(index_entry, f, ensure_ascii=False, indent=2, default=str)

        return {
            "artifact_path": stage_path,
            "artifact_path_dated": dated_path,
            "artifact_index_path": _ARTIFACT_INDEX_PATH,
            "artifact_latest_path": _ARTIFACT_LATEST_PATH,
        }
    except Exception:
        return {}


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
    if output is not None:
        entry["output_summary"] = _summarize_output(output)
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
    stage_output: Optional[Dict[str, Any]] = None,
    started_at: Optional[float] = None,
) -> Dict[str, Any]:
    duration_ms = None
    if started_at is not None:
        duration_ms = int((time.time() - started_at) * 1000)
    stage_payload = stage_output if isinstance(stage_output, dict) else prepare_stage_output(output)
    artifact = _build_stage_ai_artifact(state, stage, stage_payload, duration_ms)
    artifact_paths = _write_stage_artifact(artifact)

    entry = _make_entry(state, stage, "end", output=stage_payload, duration_ms=duration_ms)
    if artifact_paths:
        entry.update(artifact_paths)
    _write_log(entry)
    record_stage_result(
        stage,
        trace_id=str(state.get("trace_id", "unknown")),
        duration_ms=duration_ms,
        ok=True,
    )

    out = dict(output)
    out["stage_logs"] = [entry]
    out["stage_outputs"] = {stage: stage_payload}
    out["stage_full_outputs"] = {stage: artifact}
    return out
