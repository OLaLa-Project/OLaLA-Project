from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from app.core.schemas import Citation, ModelInfo, TruthCheckResponse

_ALLOWED_LABELS = {"TRUE", "FALSE", "MIXED", "UNVERIFIED", "REFUSED"}


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _as_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    return {}


def _as_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    return []


def _as_str(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return str(value)


def _as_non_empty_str(value: Any) -> str | None:
    text = _as_str(value).strip()
    return text or None


def _as_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        try:
            return int(float(value.strip()))
        except ValueError:
            return None
    return None


def _as_float(value: Any, *, default: float = 0.0) -> float:
    if isinstance(value, bool):
        return float(int(value))
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except ValueError:
            return default
    return default


def _normalize_confidence(value: Any) -> float:
    confidence = _as_float(value, default=0.0)
    if confidence > 1.0:
        confidence = confidence / 100.0
    return max(0.0, min(1.0, confidence))


def _normalize_label(value: Any) -> Literal["TRUE", "FALSE", "MIXED", "UNVERIFIED", "REFUSED"]:
    label = _as_str(value, "UNVERIFIED").strip().upper()
    if label in _ALLOWED_LABELS:
        return label  # type: ignore[return-value]
    return "UNVERIFIED"


def _string_list(value: Any) -> list[str]:
    out: list[str] = []
    for item in _as_list(value):
        text = _as_str(item).strip()
        if text:
            out.append(text)
    return out


def _dict_list(value: Any) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for item in _as_list(value):
        if isinstance(item, dict):
            out.append(dict(item))
    return out


def _map_source_type(raw: Any) -> Literal["KB_DOC", "WEB_URL", "NEWS", "WIKIPEDIA"]:
    token = _as_str(raw).strip().upper()
    if token == "NEWS":
        return "NEWS"
    if token in {"WIKIPEDIA", "KB_DOC", "KNOWLEDGE_BASE"}:
        return "WIKIPEDIA"
    return "WEB_URL"


def _normalize_citations(value: Any) -> list[Citation]:
    citations: list[Citation] = []
    for raw in _as_list(value):
        if not isinstance(raw, dict):
            continue
        quote = _as_str(raw.get("quote") or raw.get("snippet") or raw.get("content"), "").strip()
        citations.append(
            Citation(
                source_type=_map_source_type(raw.get("source_type")),
                title=_as_str(raw.get("title"), ""),
                url=_as_non_empty_str(raw.get("url")),
                quote=quote[:500] if quote else None,
                relevance=_as_float(raw.get("relevance", raw.get("score")), default=0.0),
                evid_id=_as_non_empty_str(raw.get("evid_id")),
            )
        )
    return citations


def _confidence_percent_from_fields(final_verdict: dict[str, Any], confidence: float) -> int | None:
    if not final_verdict:
        return None
    raw = _as_int(final_verdict.get("confidence_percent"))
    if raw is not None:
        return max(0, min(100, raw))
    if "confidence" not in final_verdict:
        return None
    return int(max(0.0, min(1.0, confidence)) * 100)


def _build_user_result_fallback(
    state: dict[str, Any],
    final_verdict: dict[str, Any],
    confidence_percent: int | None,
) -> dict[str, Any]:
    label = _normalize_label(final_verdict.get("label"))
    verdict_korean = _as_str(final_verdict.get("verdict_korean"), "확인이 어렵습니다")
    headline = _as_str(final_verdict.get("headline") or final_verdict.get("summary"), "")
    explanation = _as_str(final_verdict.get("explanation"), "")
    evidence_summary = _dict_list(final_verdict.get("evidence_summary"))
    cautions = _string_list(final_verdict.get("limitations"))
    next_steps = _string_list(final_verdict.get("recommended_next_steps"))
    recommendation = next_steps[0] if next_steps else ""
    evidence: list[dict[str, Any]] = []
    for item in evidence_summary:
        evidence.append(
            {
                "text": _as_str(item.get("point"), "").strip(),
                "source": {
                    "title": _as_str(item.get("source_title"), ""),
                    "url": _as_str(item.get("source_url"), ""),
                },
            }
        )

    return {
        "claim": _as_str(state.get("claim_text"), ""),
        "verdict": {
            "label": label,
            "korean": verdict_korean,
            "confidence_percent": confidence_percent or 0,
        },
        "headline": headline,
        "explanation": explanation,
        "evidence": evidence,
        "cautions": cautions,
        "recommendation": recommendation,
        "generated_at": _iso_now(),
    }


def build_truth_response(
    state: dict[str, Any],
    trace_id: str,
    *,
    include_debug: bool = False,
) -> TruthCheckResponse:
    final_verdict = _as_dict(state.get("final_verdict"))
    include_full_outputs = bool(state.get("include_full_outputs", False))

    if final_verdict:
        label = _normalize_label(final_verdict.get("label"))
        confidence = _normalize_confidence(final_verdict.get("confidence"))
        summary = _as_str(final_verdict.get("summary"), "")
        rationale = _string_list(final_verdict.get("rationale"))
        counter_evidence = _dict_list(final_verdict.get("counter_evidence"))
        limitations = _string_list(final_verdict.get("limitations"))
        recommended_next_steps = _string_list(final_verdict.get("recommended_next_steps"))
        risk_flags = _string_list(final_verdict.get("risk_flags", state.get("risk_flags")))
        model_meta = _as_dict(final_verdict.get("model_info"))
        latency_ms = max(0, _as_int(final_verdict.get("latency_ms")) or 0)
        cost_usd = max(0.0, _as_float(final_verdict.get("cost_usd"), default=0.0))
        created_at = _as_non_empty_str(final_verdict.get("created_at")) or _iso_now()
        citation_source = final_verdict.get("citations")
    else:
        label = "UNVERIFIED"
        confidence = 0.0
        summary = "충분한 증거를 찾지 못했습니다."
        rationale = []
        counter_evidence = []
        limitations = []
        recommended_next_steps = []
        risk_flags = _string_list(state.get("risk_flags"))
        model_meta = {"provider": "local", "model": "pipeline", "version": "v0.1"}
        latency_ms = 0
        cost_usd = 0.0
        created_at = _iso_now()
        citation_source = state.get("citations")

    confidence_percent = _confidence_percent_from_fields(final_verdict, confidence)
    user_result = _as_dict(state.get("user_result"))
    if not user_result and final_verdict:
        user_result = _build_user_result_fallback(state, final_verdict, confidence_percent)

    response = TruthCheckResponse(
        analysis_id=trace_id,
        label=label,
        confidence=confidence,
        summary=summary,
        rationale=rationale,
        citations=_normalize_citations(citation_source),
        counter_evidence=counter_evidence,
        limitations=limitations,
        recommended_next_steps=recommended_next_steps,
        risk_flags=risk_flags,
        stage_logs=_dict_list(state.get("stage_logs")) if include_full_outputs else [],
        stage_outputs=_as_dict(state.get("stage_outputs")) if include_full_outputs else {},
        stage_full_outputs=_as_dict(state.get("stage_full_outputs")) if include_full_outputs else {},
        model_info=ModelInfo(
            provider=_as_str(model_meta.get("provider"), "local"),
            model=_as_str(model_meta.get("model"), "slm"),
            version=_as_str(model_meta.get("version"), "v1.0"),
        ),
        latency_ms=latency_ms,
        cost_usd=cost_usd,
        created_at=created_at,
        checkpoint_thread_id=_as_non_empty_str(state.get("checkpoint_thread_id")),
        checkpoint_resumed=bool(state["checkpoint_resumed"]) if "checkpoint_resumed" in state else None,
        checkpoint_expired=bool(state["checkpoint_expired"]) if "checkpoint_expired" in state else None,
        schema_version="v2",
        headline=_as_non_empty_str(final_verdict.get("headline") or final_verdict.get("summary")),
        explanation=_as_non_empty_str(final_verdict.get("explanation")),
        verdict_korean=_as_non_empty_str(final_verdict.get("verdict_korean")),
        confidence_percent=confidence_percent,
        evaluation=_as_dict(final_verdict.get("evaluation")) or None,
        evidence_summary=_dict_list(final_verdict.get("evidence_summary")),
        user_result=user_result or None,
        judge_retrieval=_dict_list(state.get("judge_retrieval")) if include_debug else [],
        stage09_diagnostics=(
            _as_dict(state.get("stage09_diagnostics")) or None
        ) if include_debug else None,
    )
    return response


def build_complete_event_data(response: TruthCheckResponse, trace_id: str) -> dict[str, Any]:
    result = response.model_dump()
    data = {
        "result": result,
        "trace_id": trace_id,
        "schema_version": result.get("schema_version", "v2"),
    }
    # Legacy compatibility: keep flat keys for old clients.
    data.update(result)
    return data


def response_contract_metrics(response: TruthCheckResponse) -> dict[str, Any]:
    missing_critical_fields: list[str] = []
    if not (response.headline or "").strip():
        missing_critical_fields.append("headline")
    if not (response.explanation or "").strip():
        missing_critical_fields.append("explanation")
    if response.confidence_percent is None:
        missing_critical_fields.append("confidence_percent")
    if not response.citations:
        missing_critical_fields.append("citations")

    fields_populated_count = 4 - len(missing_critical_fields)
    return {
        "schema_version": response.schema_version,
        "fields_populated_count": fields_populated_count,
        "missing_critical_fields": missing_critical_fields,
    }
