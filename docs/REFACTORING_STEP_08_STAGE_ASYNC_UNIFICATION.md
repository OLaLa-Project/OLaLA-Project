# REFACTORING STEP 08 - Stage Async 통일

**작업 일시:** 2026-02-06  
**기준 문서:** `docs/REFACTORING_STEP_00_ANALYSIS.md` (Step 08 - Stage Async 통일)

## 1. 배경/목표
- sync/async 혼합 경로에서 발생 가능한 이벤트 루프 충돌 지점 제거
- I/O 중심 stage를 async-native 경로로 우선 전환
- Graph 실행 시 async stage를 직접 await 하도록 경로 단순화

## 2. 변경 파일 목록
- 신규: `backend/app/core/async_utils.py`
- 수정: `backend/app/stages/stage03_collect/node.py`
- 수정: `backend/app/stages/stage05_topk/node.py`
- 수정: `backend/app/orchestrator/stage_manager.py`
- 수정: `backend/app/graph/graph.py`
- 수정: `backend/app/orchestrator/service.py`
- 신규: `backend/tests/unit/test_async_utils.py`
- 신규: `backend/tests/unit/test_stage_manager_async_registry.py`

## 3. 핵심 변경 내용
### 3.1 공통 async 실행 유틸 도입
- `run_async_in_sync()` 추가:
  - 일반 sync 컨텍스트: `asyncio.run(...)`
  - 이미 실행 중인 이벤트 루프 컨텍스트: 백그라운드 스레드에서 별도 루프 실행
- 목적:
  - `RuntimeError: asyncio.run() cannot be called from a running event loop` 계열 충돌 방지

### 3.2 Stage sync wrapper 정리
- `stage03_collect.run_wiki/run_web`:
  - 직접 `asyncio.run/new_event_loop` 관리 코드 제거
  - `run_async_in_sync()` 사용으로 통일
- `stage05_topk.run`:
  - 동일 방식으로 sync wrapper 단순화

### 3.3 Stage Manager async registry 추가
- `ASYNC_STAGE_REGISTRY` 및 `get_async(stage_name)` 추가
- async-native stage를 명시적으로 등록:
  - `stage03_wiki`
  - `stage03_web`
  - `stage05_topk`

### 3.4 Graph 실행 경로 개선
- `_async_node_wrapper()`가 stage별 async 함수 존재 시 직접 await 실행
- async 함수가 없는 stage만 기존처럼 `to_thread`로 sync 함수 실행
- 결과:
  - I/O stage의 불필요한 sync wrapper 경유 감소
  - Graph 경로의 async 일관성 향상

### 3.5 Service 동기 진입점 충돌 완화
- `_invoke_langgraph_sync()`에서 직접 이벤트 루프 생성/관리 코드를 제거
- `run_async_in_sync(app.ainvoke, ...)` 사용으로 루프 충돌 처리 일원화

## 4. 검증 결과
1. 타입 검사
   - 명령: `cd backend && mypy --config-file mypy.ini app`
   - 결과: `Success: no issues found in 74 source files`

2. 테스트
   - 명령: `pytest backend/tests -q`
   - 결과: `27 passed, 1 warning`

3. 신규 테스트
   - `backend/tests/unit/test_async_utils.py`
     - running loop 유무 2가지 상황에서 `run_async_in_sync` 동작 검증
   - `backend/tests/unit/test_stage_manager_async_registry.py`
     - async registry 노출 stage/비노출 stage 검증

## 5. 완료 기준(DoD) 충족 여부
- I/O 중심 stage async 전환: **부분 충족**
  - `stage03_wiki`, `stage03_web`, `stage05_topk`를 async-native 경로로 우선 통합
- 이벤트 루프 충돌 지점 제거: **충족**
  - stage/service sync wrapper의 직접 루프 제어 코드 제거
- 기존 기능 회귀 없이 async 경로 안정 동작: **충족**
  - mypy + 전체 테스트 통과

## 6. 남은 리스크
- Stage01/02/06/07/09는 내부적으로 sync 로직/외부 I/O가 남아 있어 완전 async end-to-end 통일은 후속 단계 필요.
- DB 계층은 SQLAlchemy sync 세션 기반이므로, full async DB 전환은 별도 범위(마이그레이션)로 분리 권장.
