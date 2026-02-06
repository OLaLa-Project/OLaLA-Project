from app.core.schemas import TruthCheckRequest
from app.orchestrator.service import _init_state


def test_init_state_sets_default_fields():
    req = TruthCheckRequest(
        input_type="text",
        input_payload="테스트 입력",
    )

    state = _init_state(req, trace_id="trace-123")

    assert state["trace_id"] == "trace-123"
    assert state["checkpoint_thread_id"] == "trace-123"
    assert state["checkpoint_resumed"] is False
    assert state["checkpoint_expired"] is False
    assert state["input_type"] == "text"
    assert state["input_payload"] == "테스트 입력"
    assert state["language"] == "ko"
    assert state["search_mode"] == "auto"
    assert state["stage_logs"] == []
    assert state["stage_outputs"] == {}
    assert state["stage_full_outputs"] == {}
    assert state["include_full_outputs"] is False


def test_init_state_applies_stage_state_and_normalize_mode():
    req = TruthCheckRequest(
        input_type="text",
        input_payload="테스트 입력",
        normalize_mode="basic",
        include_full_outputs=True,
        stage_state={"search_mode": "vector", "custom_flag": "on"},
    )

    state = _init_state(req, trace_id="trace-456")

    assert state["trace_id"] == "trace-456"
    assert state["checkpoint_thread_id"] == "trace-456"
    assert state["checkpoint_resumed"] is False
    assert state["checkpoint_expired"] is False
    assert state["search_mode"] == "vector"
    assert state["custom_flag"] == "on"
    assert state["normalize_mode"] == "basic"
    assert state["include_full_outputs"] is True
