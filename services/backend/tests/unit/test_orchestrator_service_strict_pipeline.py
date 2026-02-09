from __future__ import annotations

import pytest

from app.core.schemas import TruthCheckRequest
import app.orchestrator.service as orchestrator_service


def _raise_runtime_error(*_args, **_kwargs):
    raise RuntimeError("boom")


def test_run_pipeline_returns_fallback_when_strict_pipeline_disabled(monkeypatch: pytest.MonkeyPatch):
    req = TruthCheckRequest(input_type="text", input_payload="테스트 입력")

    monkeypatch.setattr(orchestrator_service, "_invoke_langgraph_sync", lambda _state: None)
    monkeypatch.setattr(
        orchestrator_service,
        "_resolve_checkpoint_context",
        lambda _req, trace_id: (trace_id, False, False),
    )
    monkeypatch.setattr(orchestrator_service, "run_stage_sequence", _raise_runtime_error)
    monkeypatch.setattr(orchestrator_service.settings, "strict_pipeline", False)

    out = orchestrator_service.run_pipeline(req)

    assert out.analysis_id
    assert "PIPELINE_CRASH" in out.risk_flags


def test_run_pipeline_raises_when_strict_pipeline_enabled(monkeypatch: pytest.MonkeyPatch):
    req = TruthCheckRequest(input_type="text", input_payload="테스트 입력")

    monkeypatch.setattr(orchestrator_service, "_invoke_langgraph_sync", lambda _state: None)
    monkeypatch.setattr(
        orchestrator_service,
        "_resolve_checkpoint_context",
        lambda _req, trace_id: (trace_id, False, False),
    )
    monkeypatch.setattr(orchestrator_service, "run_stage_sequence", _raise_runtime_error)
    monkeypatch.setattr(orchestrator_service.settings, "strict_pipeline", True)

    with pytest.raises(RuntimeError, match="boom"):
        orchestrator_service.run_pipeline(req)
