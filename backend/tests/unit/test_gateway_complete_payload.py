from __future__ import annotations

import json

import pytest

import app.gateway.service as gateway_service
from app.core.schemas import TruthCheckRequest


class _DummyGatewayGraphApp:
    async def astream(self, state, config=None):  # type: ignore[no-untyped-def]
        final_verdict = {
            "label": "TRUE",
            "confidence": 0.82,
            "summary": "요약",
            "headline": "헤드라인",
            "explanation": "설명",
            "citations": [],
        }
        yield {
            "stage09_judge": {
                "final_verdict": final_verdict,
                "stage_outputs": {"stage09_judge": {"final_verdict": final_verdict}},
                "stage_logs": [],
            }
        }


@pytest.mark.asyncio
async def test_gateway_stream_complete_payload_uses_result_dual_shape(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(gateway_service, "build_langgraph", lambda: _DummyGatewayGraphApp())

    req = TruthCheckRequest(input_type="text", input_payload="테스트")
    chunks: list[str] = []
    async for chunk in gateway_service.run_pipeline_stream(req):
        chunks.append(chunk)

    complete = json.loads(chunks[-1])
    assert complete["event"] == "complete"
    assert complete["data"]["schema_version"] == "v2"
    assert complete["data"]["result"]["schema_version"] == "v2"
    assert complete["data"]["result"]["label"] == "TRUE"
    assert complete["data"]["label"] == "TRUE"
