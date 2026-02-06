from __future__ import annotations

from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.api.truth_check as truth_check_api
from app.core.schemas import ModelInfo, TruthCheckResponse


def _build_test_app() -> TestClient:
    app = FastAPI()
    app.include_router(truth_check_api.router)

    def _fake_get_db():
        yield object()

    app.dependency_overrides[truth_check_api.get_db] = _fake_get_db
    return TestClient(app)


def _fake_truth_check_response() -> TruthCheckResponse:
    return TruthCheckResponse(
        analysis_id="analysis-test-id",
        label="UNVERIFIED",
        confidence=0.0,
        summary="테스트 요약",
        rationale=[],
        citations=[],
        counter_evidence=[],
        limitations=[],
        recommended_next_steps=[],
        risk_flags=[],
        stage_logs=[],
        stage_outputs={},
        stage_full_outputs={},
        model_info=ModelInfo(provider="test", model="test", version="v0"),
        latency_ms=0,
        cost_usd=0.0,
        created_at=datetime.now(timezone.utc).isoformat(),
    )


def test_truth_check_returns_structured_error_when_pipeline_fails(monkeypatch):
    def _raise_pipeline(req):
        raise RuntimeError("pipeline boom")

    monkeypatch.setattr(truth_check_api, "run_pipeline", _raise_pipeline)

    with _build_test_app() as client:
        response = client.post(
            "/truth/check",
            json={
                "input_type": "text",
                "input_payload": "테스트 주장",
            },
        )

    assert response.status_code == 500
    detail = response.json().get("detail", {})
    assert detail.get("code") == "PIPELINE_EXECUTION_FAILED"


def test_truth_check_returns_result_when_persistence_fails(monkeypatch):
    monkeypatch.setattr(truth_check_api, "run_pipeline", lambda req: _fake_truth_check_response())

    def _raise_persistence(self, analysis_data):
        raise RuntimeError("db commit failed")

    monkeypatch.setattr(truth_check_api.AnalysisRepository, "save_analysis", _raise_persistence)

    with _build_test_app() as client:
        response = client.post(
            "/truth/check",
            json={
                "input_type": "text",
                "input_payload": "테스트 주장",
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert "PERSISTENCE_FAILED" in payload.get("risk_flags", [])

