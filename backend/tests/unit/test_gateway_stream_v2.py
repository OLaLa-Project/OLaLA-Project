from __future__ import annotations

import asyncio
import json

import pytest

import app.gateway.service as gateway_service
from app.core.schemas import TruthCheckRequest


async def _collect_events(req: TruthCheckRequest, interval: float) -> list[dict]:
    events: list[dict] = []
    async for chunk in gateway_service.run_pipeline_stream_v2(
        req,
        heartbeat_interval_seconds=interval,
    ):
        events.append(json.loads(chunk))
    return events


@pytest.mark.asyncio
async def test_stream_v2_emits_open_heartbeat_and_complete(monkeypatch: pytest.MonkeyPatch):
    async def _fake_stream(_req: TruthCheckRequest):
        await asyncio.sleep(0.25)
        yield json.dumps(
            {
                "event": "stage_complete",
                "stage": "stage01_normalize",
                "data": {"claim_text": "x"},
            }
        ) + "\n"
        await asyncio.sleep(0.25)
        yield json.dumps(
            {
                "event": "complete",
                "data": {"label": "TRUE", "confidence": 0.9},
            }
        ) + "\n"

    monkeypatch.setattr(gateway_service, "run_pipeline_stream", _fake_stream)

    req = TruthCheckRequest(input_type="text", input_payload="테스트")
    events = await _collect_events(req, 0.2)

    assert events[0]["event"] == "stream_open"
    assert any(event["event"] == "heartbeat" for event in events)
    assert any(event["event"] == "stage_complete" for event in events)
    assert events[-1]["event"] == "complete"
    assert all("trace_id" in event for event in events)
    assert all("ts" in event for event in events)


@pytest.mark.asyncio
async def test_stream_v2_emits_error_when_upstream_has_no_terminal_event(
    monkeypatch: pytest.MonkeyPatch,
):
    async def _fake_stream(_req: TruthCheckRequest):
        yield json.dumps(
            {
                "event": "stage_complete",
                "stage": "stage03_web",
                "data": {"web_candidates": []},
            }
        ) + "\n"

    monkeypatch.setattr(gateway_service, "run_pipeline_stream", _fake_stream)

    req = TruthCheckRequest(input_type="text", input_payload="테스트")
    events = await _collect_events(req, 0.2)

    assert events[0]["event"] == "stream_open"
    assert events[1]["event"] == "stage_complete"
    assert events[-1]["event"] == "error"
    assert events[-1]["data"]["code"] == "STREAM_TERMINATED"
