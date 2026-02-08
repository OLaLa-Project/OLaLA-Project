from __future__ import annotations

import time
from collections import deque
from threading import Lock
from typing import Any

_LOCK = Lock()
_MAX_STAGE_SAMPLES = 500
_MAX_TRACE_EVENTS = 200

_stage_durations: dict[str, list[int]] = {}
_stage_errors: dict[str, int] = {}
_external_api_stats: dict[str, dict[str, int]] = {}
_trace_events: deque[dict[str, Any]] = deque(maxlen=_MAX_TRACE_EVENTS)


def _percentile(values: list[int], percentile: float) -> int:
    if not values:
        return 0
    if len(values) == 1:
        return values[0]
    rank = int(round((percentile / 100.0) * (len(values) - 1)))
    rank = max(0, min(rank, len(values) - 1))
    return values[rank]


def record_stage_result(
    stage: str,
    *,
    trace_id: str | None = None,
    duration_ms: int | None = None,
    ok: bool = True,
) -> None:
    stage_name = (stage or "").strip() or "unknown_stage"
    event = {
        "trace_id": trace_id or "unknown",
        "stage": stage_name,
        "ok": bool(ok),
        "duration_ms": duration_ms if duration_ms is not None else None,
        "timestamp": int(time.time()),
    }
    with _LOCK:
        if duration_ms is not None and duration_ms >= 0:
            durations = _stage_durations.setdefault(stage_name, [])
            durations.append(int(duration_ms))
            if len(durations) > _MAX_STAGE_SAMPLES:
                del durations[0 : len(durations) - _MAX_STAGE_SAMPLES]
        if not ok:
            _stage_errors[stage_name] = _stage_errors.get(stage_name, 0) + 1
        _trace_events.append(event)


def record_external_api_result(provider: str, *, ok: bool) -> None:
    provider_name = (provider or "").strip().lower() or "unknown"
    with _LOCK:
        stats = _external_api_stats.setdefault(
            provider_name,
            {"requests": 0, "success": 0, "failure": 0},
        )
        stats["requests"] += 1
        if ok:
            stats["success"] += 1
        else:
            stats["failure"] += 1


def snapshot_observability() -> dict[str, Any]:
    with _LOCK:
        stage_latency: dict[str, dict[str, int]] = {}
        for stage, durations in _stage_durations.items():
            if not durations:
                continue
            ordered = sorted(durations)
            stage_latency[stage] = {
                "count": len(ordered),
                "avg_ms": int(sum(ordered) / len(ordered)),
                "p50_ms": _percentile(ordered, 50),
                "p95_ms": _percentile(ordered, 95),
            }

        external_api: dict[str, dict[str, float | int]] = {}
        for provider, stats in _external_api_stats.items():
            requests_total = stats.get("requests", 0)
            success = stats.get("success", 0)
            failure = stats.get("failure", 0)
            success_ratio = (float(success) / float(requests_total)) if requests_total else 0.0
            external_api[provider] = {
                "requests": requests_total,
                "success": success,
                "failure": failure,
                "success_ratio": round(success_ratio, 4),
            }

        return {
            "stage_latency": stage_latency,
            "stage_errors": dict(_stage_errors),
            "external_api": external_api,
            "recent_traces": list(_trace_events)[-20:],
        }


def reset_observability_for_test() -> None:
    with _LOCK:
        _stage_durations.clear()
        _stage_errors.clear()
        _external_api_stats.clear()
        _trace_events.clear()
