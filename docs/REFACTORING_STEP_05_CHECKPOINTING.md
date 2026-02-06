# REFACTORING STEP 05 - Checkpointing 도입

**작업 일시:** 2026-02-06  
**기준 문서:** `docs/REFACTORING_PRIORITY.md` (#6 LangGraph Checkpointing)

## 1. 배경/목표
- LangGraph 실행 중단 시 동일 `thread_id`로 재개 가능한 기반 확보
- `thread_id` 재사용 정책과 TTL 만료 정책을 서비스 계층에서 명시
- 그래프 컴파일 시 checkpointer를 실제 연결해 재개 경로를 활성화

## 2. 변경 파일 목록
- 신규: `backend/app/graph/checkpoint.py`
- 수정: `backend/app/graph/graph.py`
- 수정: `backend/app/orchestrator/service.py`
- 수정: `backend/app/core/schemas.py`
- 수정: `backend/app/graph/state.py`
- 수정: `backend/app/core/settings.py`
- 수정: `backend/.env.example`
- 신규: `backend/tests/unit/test_checkpointing.py`
- 수정: `backend/tests/unit/test_orchestrator_service_state_init.py`

## 3. 핵심 변경 내용
### 3.1 Checkpointer 런타임 모듈 추가
- `backend/app/graph/checkpoint.py`:
  - checkpointer singleton 초기화 로직 추가
  - 기본 backend는 `postgres` (`CHECKPOINT_BACKEND=postgres`)
  - PostgreSQL thread 메타데이터 테이블(`checkpoint_threads`) 기반 TTL 관리
  - `PostgresSaver` 사용 가능 시 연결 시도, 미지원 런타임에서는 memory saver로 안전 fallback
  - `resolve_checkpoint_thread_id()`로 `thread_id` 재개/만료 판단
  - TTL 정책: `CHECKPOINT_TTL_SECONDS` 초과 시 신규 fallback thread 발급 + `expired=True`

### 3.2 LangGraph compile 시 checkpointer 연결
- `backend/app/graph/graph.py`:
  - `build_langgraph()`를 `@lru_cache(maxsize=1)`로 고정해 checkpointer 상태 재사용
  - `graph.compile(checkpointer=...)` 적용 (사용 가능 시)

### 3.3 서비스 레이어 thread_id 전략 반영
- `backend/app/orchestrator/service.py`:
  - 요청의 `checkpoint_thread_id`/`checkpoint_resume`를 기반으로 실행 컨텍스트 계산
  - 스트리밍 실행에서 `app.astream(state, config={"configurable": {"thread_id": ...}})` 전달
  - 상태/응답에 checkpoint 메타데이터 포함:
    - `checkpoint_thread_id`
    - `checkpoint_resumed`
    - `checkpoint_expired`

### 3.4 스키마/설정 확장
- `backend/app/core/schemas.py`:
  - Request: `checkpoint_thread_id`, `checkpoint_resume`
  - Response: `checkpoint_thread_id`, `checkpoint_resumed`, `checkpoint_expired`
- `backend/app/core/settings.py`, `backend/.env.example`:
  - `CHECKPOINT_ENABLED`, `CHECKPOINT_BACKEND`, `CHECKPOINT_TTL_SECONDS`, `CHECKPOINT_THREAD_TABLE` 추가

### 3.5 테스트 추가
- `backend/tests/unit/test_checkpointing.py`:
  - TTL 만료 시 fallback thread 발급 검증
  - 스트리밍 경로에서 `configurable.thread_id` 전달 검증
  - PostgreSQL backend 라우팅 검증
  - sync full-run에서 LangGraph `ainvoke` 경로 사용 검증
- `backend/tests/unit/test_orchestrator_service_state_init.py`:
  - 초기 state에 checkpoint 필드 기본값 검증 추가

## 4. 검증 결과
1. 타입 검사
   - 명령: `cd backend && mypy --config-file mypy.ini app`
   - 결과: `Success: no issues found in 73 source files`

2. 테스트
   - 명령: `pytest backend/tests -q`
   - 결과: `23 passed, 1 warning`

## 5. 완료 기준(DoD) 충족 여부
- LangGraph checkpointer 연결: **충족**
- `thread_id`/resume 전략 정의: **충족**
- checkpoint 정리 정책(TTL) 정의: **충족** (PostgreSQL 영속 메타데이터 기반)
- 중간 재개 시나리오 검증: **충족**
  - 스트리밍 경로 `configurable.thread_id` 전달 검증
  - sync 경로 LangGraph `ainvoke(..., config=thread_id)` 검증
  - TTL 만료 시 fallback thread 전환 검증
  - PostgreSQL backend 라우팅 검증

## 6. 남은 리스크
- sync API 기본 경로는 LangGraph checkpointer 기반으로 전환되어 해소됨.
  - 구현: full run 요청(`start_stage/end_stage` 미지정)은 `build_langgraph().ainvoke(..., config={"configurable": {"thread_id": ...}})` 사용
  - 예외: 단계 슬라이싱 실행 요청 시에만 `run_stage_sequence` fallback 유지
- TTL 재시작 일관성 리스크는 PostgreSQL thread 메타데이터 저장소로 해소됨.
  - 구현: `checkpoint_threads(thread_id,last_seen)` 영속 테이블 사용
  - 만료 판정/정리 정책이 프로세스 재시작 이후에도 동일하게 동작

## 7. 리스크 해결 결과 (추가)
- 수정 파일:
  - `backend/app/orchestrator/service.py`
  - `backend/app/graph/checkpoint.py`
  - `backend/app/core/settings.py`
  - `backend/.env.example`
  - `backend/tests/unit/test_checkpointing.py`
- 핵심 결과:
  - sync + stream 모두 `thread_id` 기반 checkpoint resume 경로 확보
  - TTL 정책을 PostgreSQL 영속 메타데이터로 전환해 restart 내구성 확보
