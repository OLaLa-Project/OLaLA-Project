from __future__ import annotations

import json

import pytest

import app.orchestrator.service as orchestrator_service
import app.graph.checkpoint as checkpoint_runtime
from app.core.schemas import TruthCheckRequest


@pytest.fixture(autouse=True)
def _reset_checkpoint_runtime(monkeypatch: pytest.MonkeyPatch):
    checkpoint_runtime.reset_checkpoint_runtime_for_test()
    monkeypatch.setattr(checkpoint_runtime.settings, "checkpoint_enabled", True)
    monkeypatch.setattr(checkpoint_runtime.settings, "checkpoint_backend", "memory")
    monkeypatch.setattr(checkpoint_runtime.settings, "checkpoint_ttl_seconds", 10)
    monkeypatch.setattr(checkpoint_runtime.settings, "checkpoint_thread_table", "checkpoint_threads_test")
    yield
    checkpoint_runtime.reset_checkpoint_runtime_for_test()


def test_resolve_checkpoint_thread_id_expires_old_thread(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(checkpoint_runtime.time, "time", lambda: 1000.0)
    thread_id, resumed, expired = checkpoint_runtime.resolve_checkpoint_thread_id(
        "thread-A",
        "fallback-A",
    )

    assert thread_id == "thread-A"
    assert resumed is True
    assert expired is False

    monkeypatch.setattr(checkpoint_runtime.time, "time", lambda: 1015.0)
    new_thread_id, resumed2, expired2 = checkpoint_runtime.resolve_checkpoint_thread_id(
        "thread-A",
        "fallback-B",
    )

    assert new_thread_id == "fallback-B"
    assert resumed2 is False
    assert expired2 is True


def test_resolve_checkpoint_thread_id_uses_postgres_backend(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(checkpoint_runtime.settings, "checkpoint_backend", "postgres")
    called: dict[str, object] = {}

    def _fake_resolver(req_id: str | None, fallback: str, now: float):  # type: ignore[no-untyped-def]
        called["req_id"] = req_id
        called["fallback"] = fallback
        called["now"] = now
        return ("pg-thread", True, False)

    monkeypatch.setattr(checkpoint_runtime, "_resolve_thread_id_with_postgres", _fake_resolver)
    thread_id, resumed, expired = checkpoint_runtime.resolve_checkpoint_thread_id(
        "persist-thread",
        "fallback-1",
    )

    assert thread_id == "pg-thread"
    assert resumed is True
    assert expired is False
    assert called["req_id"] == "persist-thread"


class _DummyGraphApp:
    def __init__(self):
        self.stream_configs: list[dict[str, dict[str, str]] | None] = []

    async def astream(self, state, config=None):  # type: ignore[no-untyped-def]
        self.stream_configs.append(config)
        yield {
            "stage01_normalize": {
                "stage_outputs": {"stage01_normalize": {"claim_text": state.get("input_payload", "")}},
                "stage_logs": [],
            }
        }

    async def ainvoke(self, state, config=None):  # type: ignore[no-untyped-def]
        self.stream_configs.append(config)
        return {
            "final_verdict": {"summary": "ok"},
            "stage_logs": [],
            "stage_outputs": {},
            "stage_full_outputs": {},
        }


@pytest.mark.asyncio
async def test_run_pipeline_stream_passes_checkpoint_thread_id(monkeypatch: pytest.MonkeyPatch):
    dummy_app = _DummyGraphApp()
    monkeypatch.setattr(orchestrator_service, "build_langgraph", lambda: dummy_app)

    req = TruthCheckRequest(
        input_type="text",
        input_payload="테스트 주장",
        checkpoint_thread_id="resume-thread-1",
        checkpoint_resume=True,
    )

    outputs: list[str] = []
    async for chunk in orchestrator_service.run_pipeline_stream(req):
        outputs.append(chunk)

    assert dummy_app.stream_configs
    assert dummy_app.stream_configs[0] == {"configurable": {"thread_id": "resume-thread-1"}}

    complete_event = json.loads(outputs[-1])
    assert complete_event["event"] == "complete"
    assert complete_event["data"]["checkpoint_thread_id"] == "resume-thread-1"
    assert complete_event["data"]["checkpoint_resumed"] is True
    assert complete_event["data"]["result"]["checkpoint_thread_id"] == "resume-thread-1"
    assert complete_event["data"]["result"]["schema_version"] == "v2"


def test_run_pipeline_uses_langgraph_in_full_mode(monkeypatch: pytest.MonkeyPatch):
    dummy_app = _DummyGraphApp()
    monkeypatch.setattr(orchestrator_service, "build_langgraph", lambda: dummy_app)
    monkeypatch.setattr(orchestrator_service, "run_stage_sequence", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("should not fallback")))

    req = TruthCheckRequest(
        input_type="text",
        input_payload="동기 체크",
        checkpoint_thread_id="sync-thread-1",
        checkpoint_resume=True,
    )
    result = orchestrator_service.run_pipeline(req)

    assert result.checkpoint_thread_id == "sync-thread-1"
    assert dummy_app.stream_configs
    assert dummy_app.stream_configs[0] == {"configurable": {"thread_id": "sync-thread-1"}}
