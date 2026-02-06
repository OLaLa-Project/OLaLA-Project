from __future__ import annotations

from app.core.observability import (
    record_external_api_result,
    record_stage_result,
    reset_observability_for_test,
    snapshot_observability,
)


def test_observability_collects_stage_latency_and_errors():
    reset_observability_for_test()
    record_stage_result("stage01_normalize", trace_id="t1", duration_ms=120, ok=True)
    record_stage_result("stage01_normalize", trace_id="t2", duration_ms=80, ok=True)
    record_stage_result("stage02_querygen", trace_id="t3", duration_ms=None, ok=False)

    snap = snapshot_observability()
    stage_latency = snap["stage_latency"]
    stage_errors = snap["stage_errors"]

    assert "stage01_normalize" in stage_latency
    assert stage_latency["stage01_normalize"]["count"] == 2
    assert stage_latency["stage01_normalize"]["avg_ms"] == 100
    assert stage_errors["stage02_querygen"] == 1


def test_observability_collects_external_api_success_ratio():
    reset_observability_for_test()
    record_external_api_result("naver", ok=True)
    record_external_api_result("naver", ok=False)
    record_external_api_result("ddg", ok=True)

    snap = snapshot_observability()
    ext = snap["external_api"]

    assert ext["naver"]["requests"] == 2
    assert ext["naver"]["success"] == 1
    assert ext["naver"]["failure"] == 1
    assert ext["naver"]["success_ratio"] == 0.5
    assert ext["ddg"]["success_ratio"] == 1.0
