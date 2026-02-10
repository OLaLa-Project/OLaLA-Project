from __future__ import annotations

from app.services.response_mapper import (
    build_complete_event_data,
    build_truth_response,
    response_contract_metrics,
)


def test_build_truth_response_maps_stage09_fields() -> None:
    state = {
        "include_full_outputs": True,
        "stage_logs": [{"stage": "stage09_judge"}],
        "stage_outputs": {"stage09_judge": {"ok": True}},
        "stage_full_outputs": {"stage09_judge": {"raw": "x"}},
        "checkpoint_thread_id": "thread-1",
        "checkpoint_resumed": True,
        "checkpoint_expired": False,
        "judge_retrieval": [{"evid_id": "judge_wiki_1"}],
        "stage09_diagnostics": {"selected_evidence_count": 2},
        "user_result": {"headline": "사용자 헤드라인"},
        "final_verdict": {
            "label": "FALSE",
            "confidence": 0.7,
            "summary": "요약",
            "rationale": ["근거1"],
            "citations": [
                {
                    "source_type": "NEWS",
                    "title": "기사",
                    "url": "https://example.com/a",
                    "quote": "인용문",
                    "relevance": 0.9,
                }
            ],
            "risk_flags": ["LOW_CONFIDENCE"],
            "model_info": {"provider": "openai", "model": "gpt-4.1", "version": "v1"},
            "latency_ms": 123,
            "cost_usd": 0.05,
            "created_at": "2026-02-10T00:00:00+00:00",
            "headline": "헤드라인",
            "explanation": "설명",
            "verdict_korean": "거짓입니다",
            "confidence_percent": 70,
            "evaluation": {"reason": "근거 충돌"},
            "evidence_summary": [{"point": "핵심 포인트"}],
        },
    }

    response = build_truth_response(state, "trace-1", include_debug=True)

    assert response.analysis_id == "trace-1"
    assert response.schema_version == "v2"
    assert response.label == "FALSE"
    assert response.headline == "헤드라인"
    assert response.explanation == "설명"
    assert response.verdict_korean == "거짓입니다"
    assert response.confidence_percent == 70
    assert response.evaluation == {"reason": "근거 충돌"}
    assert response.evidence_summary == [{"point": "핵심 포인트"}]
    assert response.user_result == {"headline": "사용자 헤드라인"}
    assert response.judge_retrieval == [{"evid_id": "judge_wiki_1"}]
    assert response.stage09_diagnostics == {"selected_evidence_count": 2}
    assert response.checkpoint_thread_id == "thread-1"
    assert response.checkpoint_resumed is True
    assert response.checkpoint_expired is False
    assert response.citations[0].source_type == "NEWS"


def test_build_complete_event_data_keeps_dual_shape() -> None:
    response = build_truth_response(
        {
            "final_verdict": {
                "label": "TRUE",
                "confidence": 0.9,
                "summary": "ok",
                "citations": [],
                "headline": "헤드",
                "explanation": "설명",
            }
        },
        "trace-2",
        include_debug=False,
    )

    event_data = build_complete_event_data(response, "trace-2")

    assert event_data["trace_id"] == "trace-2"
    assert event_data["schema_version"] == "v2"
    assert event_data["result"]["label"] == "TRUE"
    assert event_data["result"]["schema_version"] == "v2"
    assert event_data["label"] == "TRUE"
    assert event_data["analysis_id"] == "trace-2"


def test_response_contract_metrics_reports_missing_fields() -> None:
    response = build_truth_response(
        {
            "final_verdict": {
                "label": "UNVERIFIED",
                "confidence": 0.0,
                "summary": "",
                "citations": [],
            }
        },
        "trace-3",
        include_debug=False,
    )

    metrics = response_contract_metrics(response)
    assert metrics["schema_version"] == "v2"
    assert "headline" in metrics["missing_critical_fields"]
    assert "explanation" in metrics["missing_critical_fields"]
    assert "citations" in metrics["missing_critical_fields"]


def test_build_truth_response_omits_debug_fields_when_disabled() -> None:
    response = build_truth_response(
        {
            "judge_retrieval": [{"evid_id": "judge-1"}],
            "stage09_diagnostics": {"x": 1},
            "final_verdict": {
                "label": "TRUE",
                "confidence": 0.8,
                "summary": "요약",
                "citations": [],
            },
        },
        "trace-4",
        include_debug=False,
    )

    assert response.judge_retrieval == []
    assert response.stage09_diagnostics is None
