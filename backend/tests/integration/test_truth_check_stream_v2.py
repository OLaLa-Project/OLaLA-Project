from __future__ import annotations

import json

from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.api.truth_check as truth_check_api
from app.core.schemas import TruthCheckRequest


def _build_test_app() -> TestClient:
    app = FastAPI()
    app.include_router(truth_check_api.router)

    def _fake_get_db():
        yield object()

    app.dependency_overrides[truth_check_api.get_db] = _fake_get_db
    return TestClient(app)


def test_truth_check_stream_v2_returns_ndjson_with_stream_headers(monkeypatch):
    async def _fake_stream(_req: TruthCheckRequest):
        yield json.dumps({"event": "stream_open", "trace_id": "trace-1", "ts": "2026-02-06T10:00:00Z"}) + "\n"
        yield json.dumps({"event": "heartbeat", "trace_id": "trace-1", "current_stage": "stage06_verify_support"}) + "\n"
        yield json.dumps({"event": "complete", "trace_id": "trace-1", "data": {"label": "TRUE", "confidence": 0.9}}) + "\n"

    monkeypatch.setattr(truth_check_api, "run_pipeline_stream_v2", _fake_stream)

    with _build_test_app() as client:
        with client.stream(
            "POST",
            "/api/truth/check/stream-v2",
            json={
                "input_type": "text",
                "input_payload": "테스트 주장",
            },
        ) as response:
            assert response.status_code == 200
            assert response.headers.get("cache-control") == "no-cache"
            assert response.headers.get("x-accel-buffering") == "no"
            assert response.headers.get("content-type", "").startswith("application/x-ndjson")
            lines = [line for line in response.iter_lines() if line]

    payloads = [json.loads(line) for line in lines]
    assert [payload["event"] for payload in payloads] == ["stream_open", "heartbeat", "complete"]
