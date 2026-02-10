import uuid
import json
import logging
import asyncio
import time
from typing import Dict, Any, List
from datetime import datetime, timezone

from app.core.schemas import TruthCheckRequest, TruthCheckResponse
from app.graph.checkpoint import resolve_checkpoint_thread_id
from app.graph.graph import build_langgraph, STAGE_SEQUENCE, STAGE_OUTPUT_KEYS, run_stage_sequence
from app.services.response_mapper import (
    build_complete_event_data,
    build_truth_response,
    response_contract_metrics,
)

logger = logging.getLogger(__name__)


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()

UI_STEP_TITLES: Dict[int, str] = {
    1: "주장/콘텐츠 추출",
    2: "관련 근거 수집",
    3: "근거 기반 판단 제공",
}

STAGE_TO_UI_STEP: Dict[str, int] = {
    "stage01_normalize": 1,
    "stage02_querygen": 1,
    "adapter_queries": 1,
    "stage03_wiki": 2,
    "stage03_web": 2,
    "stage03_merge": 2,
    "stage04_score": 2,
    "stage05_topk": 2,
    "stage06_verify_support": 3,
    "stage07_verify_skeptic": 3,
    "stage08_aggregate": 3,
    "stage09_judge": 3,
}

STEP_LAST_STAGE: Dict[int, str] = {
    1: "stage02_querygen",
    2: "stage05_topk",
    3: "stage09_judge",
}

def _stage_seq_name(item: Any) -> str:
    if isinstance(item, (list, tuple)) and item:
        return str(item[0])
    return str(item)


STAGE_ORDER: Dict[str, int] = {
    _stage_seq_name(item): idx + 1 for idx, item in enumerate(STAGE_SEQUENCE)
}


def _log_response_contract(trace_id: str, response: TruthCheckResponse) -> None:
    metrics = response_contract_metrics(response)
    logger.info(
        "[%s] response_contract schema_version=%s fields_populated_count=%s missing_critical_fields=%s",
        trace_id,
        metrics["schema_version"],
        metrics["fields_populated_count"],
        metrics["missing_critical_fields"],
    )

def _build_error_payload(error_msg: str, stage: str = "unknown") -> str:
    """Flutter UI에서 인식할 수 있는 규격화된 에러 JSON 생성."""
    error_code = "PIPELINE_ERROR"
    if "timeout" in error_msg.lower(): error_code = "TIMEOUT"
    elif "json" in error_msg.lower(): error_code = "PARSING_ERROR"
    
    ui_step = STAGE_TO_UI_STEP.get(stage)
    return json.dumps({
        "event": "error",
        "data": {
            "code": error_code,
            "stage": stage,
            "ui_step": ui_step,
            "message": error_msg,
            "display_message": "분석 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요."
        }
    }) + "\n"

def run_pipeline(req: TruthCheckRequest) -> TruthCheckResponse:
    """동기식 파이프라인 실행."""
    state: Dict[str, Any] = {
        "trace_id": str(uuid.uuid4()),
        "input_type": req.input_type,
        "input_payload": req.input_payload,
        "user_request": req.user_request or "",
        "language": req.language or "ko",
        "search_mode": "auto",
        "stage_logs": [],
        "stage_outputs": {},
        "stage_full_outputs": {},
        "include_full_outputs": req.include_full_outputs
    }
    
    # 추가 상태 설정
    if isinstance(req.stage_state, dict):
        state.update(req.stage_state)
    if req.normalize_mode:
        state["normalize_mode"] = req.normalize_mode

    try:
        out = run_stage_sequence(state, req.start_stage, req.end_stage)
        response = build_truth_response(
            out,
            state["trace_id"],
            include_debug=bool(req.include_full_outputs),
        )
        _log_response_contract(state["trace_id"], response)
        return response
    except Exception as e:
        logger.error(f"Sync pipeline failed: {e}")
        response = build_truth_response(
            {"risk_flags": ["PIPELINE_CRASH"], "final_verdict": {"summary": f"오류 발생: {str(e)}"}},
            state["trace_id"],
            include_debug=bool(req.include_full_outputs),
        )
        _log_response_contract(state["trace_id"], response)
        return response

async def run_pipeline_stream(req: TruthCheckRequest):
    """비동기 스트리밍 파이프라인 실행 (Flutter SSE 대응)."""
    app = build_langgraph()
    if app is None:
        yield _build_error_payload("LangGraph not initialized", "system")
        return

    trace_id = str(uuid.uuid4())
    requested_thread_id = req.checkpoint_thread_id if req.checkpoint_resume else None
    checkpoint_thread_id, checkpoint_resumed, checkpoint_expired = resolve_checkpoint_thread_id(
        requested_thread_id,
        trace_id,
    )
    state: Dict[str, Any] = {
        "trace_id": trace_id,
        "checkpoint_thread_id": checkpoint_thread_id,
        "checkpoint_resumed": checkpoint_resumed,
        "checkpoint_expired": checkpoint_expired,
        "input_type": req.input_type,
        "input_payload": req.input_payload,
        "user_request": req.user_request or "",
        "language": req.language or "ko",
        "search_mode": "auto",
        "stream_mode": True,
        "stream_fast_normalize": True,
        "stream_fast_querygen": True,
        "stage_logs": [],
        "stage_outputs": {},
        "stage_full_outputs": {},
        "include_full_outputs": req.include_full_outputs
    }
    
    if isinstance(req.stage_state, dict):
        state.update(req.stage_state)

    stream_logger = logging.getLogger("uvicorn.error")

    def pydantic_encoder(obj):
        if hasattr(obj, "model_dump"): return obj.model_dump()
        return str(obj)

    final_state = state.copy()
    current_stage = "initializing"
    stream_config: Dict[str, Dict[str, str]] = {
        "configurable": {"thread_id": checkpoint_thread_id}
    }
    
    buffered_stage02: Dict[str, Any] | None = None
    emitted_stage02 = False
    started_steps: set[int] = set()
    completed_steps: set[int] = set()

    # Stream 연결 직후 즉시 1단계 시작 이벤트를 보낸다.
    # (URL prefetch 지연 시에도 프론트가 "멈춤"으로 보이지 않도록)
    initial_step = STAGE_TO_UI_STEP.get("stage01_normalize")
    if initial_step is not None:
        started_steps.add(initial_step)
        yield json.dumps({
            "event": "step_started",
            "ui_step": initial_step,
            "ui_step_title": UI_STEP_TITLES.get(initial_step),
            "stage": "stage01_normalize",
            "stage_order": STAGE_ORDER.get("stage01_normalize"),
        }, default=pydantic_encoder) + "\n"

    def _build_stage_events(stage_label: str, stage_payload: Dict[str, Any]) -> List[Dict[str, Any]]:
        events: List[Dict[str, Any]] = []
        ui_step = STAGE_TO_UI_STEP.get(stage_label)
        ui_step_title = UI_STEP_TITLES.get(ui_step) if ui_step is not None else None

        if ui_step is not None and ui_step not in started_steps:
            started_steps.add(ui_step)
            events.append({
                "event": "step_started",
                "ui_step": ui_step,
                "ui_step_title": ui_step_title,
                "stage": stage_label,
                "stage_order": STAGE_ORDER.get(stage_label),
            })

        stage_event: Dict[str, Any] = {
            "event": "stage_complete",
            "stage": stage_label,
            "data": stage_payload,
            "stage_order": STAGE_ORDER.get(stage_label),
            "stage_total": len(STAGE_SEQUENCE),
        }
        if ui_step is not None:
            stage_event["ui_step"] = ui_step
            stage_event["ui_step_title"] = ui_step_title
        events.append(stage_event)

        if (
            ui_step is not None
            and ui_step not in completed_steps
            and STEP_LAST_STAGE.get(ui_step) == stage_label
        ):
            completed_steps.add(ui_step)
            events.append({
                "event": "step_completed",
                "ui_step": ui_step,
                "ui_step_title": ui_step_title,
                "stage": stage_label,
                "stage_order": STAGE_ORDER.get(stage_label),
            })
        return events

    try:
        async for output in app.astream(state, config=stream_config):
            for node_name, node_state in output.items():
                current_stage = node_name
                stream_logger.info(f"Stream yielded node: {node_name}")
                
                final_state.update(node_state)
                
                # 정해진 출력 키에 따라 클라이언트에 보낼 데이터 필터링
                stage_data = node_state.get("stage_outputs", {}).get(node_name, {})
                if not stage_data and node_name in STAGE_OUTPUT_KEYS:
                     keys = STAGE_OUTPUT_KEYS[node_name]
                     stage_data = {k: node_state.get(k) for k in keys if k in node_state}
                
                # 디버그 모드가 아니면 프롬프트 등 무거운 데이터 제외
                if not req.include_full_outputs:
                    stage_data = {k: v for k, v in stage_data.items() if not (isinstance(k, str) and k.startswith(("prompt_", "slm_raw_")))}
                    # Deep cleanup of canonical_evidence in stage_data
                    if "canonical_evidence" in stage_data:
                        ce = stage_data["canonical_evidence"]
                        if isinstance(ce, dict):
                            ce.pop("fetched_content", None)

                # Stage02는 adapter 이후 search_queries를 포함해 전송
                if node_name == "stage02_querygen":
                    buffered_stage02 = stage_data
                    continue

                if node_name == "adapter_queries":
                    merged = dict(buffered_stage02 or {})
                    if "search_queries" in node_state:
                        merged["search_queries"] = node_state.get("search_queries")
                    stage_label = "stage02_querygen"
                    stage_payload = merged
                    emitted_stage02 = True
                else:
                    stage_label = node_name
                    stage_payload = stage_data

                for event_payload in _build_stage_events(stage_label, stage_payload):
                    yield json.dumps(event_payload, default=pydantic_encoder) + "\n"

    except Exception as e:
        stream_logger.error(f"[{trace_id}] Stream failed at {current_stage}: {e}")
        yield _build_error_payload(str(e), current_stage)
        return

    # Adapter가 실행되지 않은 경우(예외적) stage02 버퍼 flush
    if buffered_stage02 and not emitted_stage02:
        for event_payload in _build_stage_events("stage02_querygen", buffered_stage02):
            yield json.dumps(event_payload, default=pydantic_encoder) + "\n"

    # 최종 결과 전송
    final_response = build_truth_response(
        final_state,
        trace_id,
        include_debug=bool(req.include_full_outputs),
    )
    _log_response_contract(trace_id, final_response)
    yield json.dumps({
        "event": "complete",
        "data": build_complete_event_data(final_response, trace_id),
    }, default=pydantic_encoder) + "\n"


async def run_pipeline_stream_v2(
    req: TruthCheckRequest,
    *,
    heartbeat_interval_seconds: float = 2.0,
):
    """
    Streaming v2 wrapper.
    - Emits `stream_open` immediately.
    - Emits periodic `heartbeat` while waiting for upstream stage events.
    - Preserves v1 payloads (`stage_complete`, `step_*`, `complete`, `error`).
    """
    interval = max(0.2, float(heartbeat_interval_seconds))
    trace_id = str(uuid.uuid4())
    stream_logger = logging.getLogger("uvicorn.error")

    queue: asyncio.Queue[Dict[str, Any]] = asyncio.Queue()
    producer_done = asyncio.Event()
    current_stage = "initializing"
    last_activity_monotonic = time.monotonic()
    saw_terminal_event = False

    async def _producer() -> None:
        nonlocal current_stage
        nonlocal last_activity_monotonic
        try:
            async for chunk in run_pipeline_stream(req):
                try:
                    payload = json.loads(chunk)
                    if not isinstance(payload, dict):
                        continue
                except Exception:
                    await queue.put(
                        {
                            "event": "error",
                            "trace_id": trace_id,
                            "ts": _iso_now(),
                            "data": {
                                "code": "STREAM_PARSE_ERROR",
                                "stage": current_stage,
                                "message": "Malformed upstream stream payload",
                            },
                        }
                    )
                    continue

                payload.setdefault("trace_id", trace_id)
                payload.setdefault("ts", _iso_now())

                event_name = str(payload.get("event", "")).lower()
                stage = payload.get("stage")
                if isinstance(stage, str) and stage:
                    current_stage = stage

                if event_name in {"step_started", "step_completed", "stage_complete", "complete", "error"}:
                    last_activity_monotonic = time.monotonic()

                await queue.put(payload)
        except Exception as exc:
            stream_logger.exception("Stream v2 producer failed")
            await queue.put(
                {
                    "event": "error",
                    "trace_id": trace_id,
                    "ts": _iso_now(),
                    "data": {
                        "code": "PIPELINE_ERROR",
                        "stage": current_stage,
                        "message": str(exc),
                        "display_message": "분석 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.",
                    },
                }
            )
        finally:
            producer_done.set()

    producer_task = asyncio.create_task(_producer())

    try:
        yield json.dumps(
            {
                "event": "stream_open",
                "trace_id": trace_id,
                "ts": _iso_now(),
            }
        ) + "\n"

        while True:
            if producer_done.is_set() and queue.empty():
                break

            try:
                payload = await asyncio.wait_for(queue.get(), timeout=interval)
                event_name = str(payload.get("event", "")).lower()
                if event_name in {"complete", "error"}:
                    saw_terminal_event = True
                yield json.dumps(payload) + "\n"
            except asyncio.TimeoutError:
                idle_ms = int((time.monotonic() - last_activity_monotonic) * 1000)
                yield json.dumps(
                    {
                        "event": "heartbeat",
                        "trace_id": trace_id,
                        "current_stage": current_stage,
                        "idle_ms": idle_ms,
                        "ts": _iso_now(),
                    }
                ) + "\n"
        if not saw_terminal_event:
            yield json.dumps(
                {
                    "event": "error",
                    "trace_id": trace_id,
                    "ts": _iso_now(),
                    "data": {
                        "code": "STREAM_TERMINATED",
                        "stage": current_stage,
                        "message": "Stream ended before terminal event",
                        "display_message": "분석 스트림이 비정상 종료되었습니다.",
                    },
                }
            ) + "\n"
    finally:
        if not producer_task.done():
            producer_task.cancel()
            try:
                await producer_task
            except asyncio.CancelledError:
                pass
