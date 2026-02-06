# REFACTORING STEP 10 - Terminology & Documentation Sync

**작업 일시:** 2026-02-06  
**연계 문서:** `docs/REFACTORING_STEP_09_GATEWAY_RENAMING.md`

## 1. 배경/목표
- Step 09 이후 남아 있던 `Gateway` 용어 잔존을 코드/문서 관점에서 최소화
- 리네이밍 완료 후 레퍼런스 문서의 경로(`backend/app/gateway/...`)를 현재 구조(`backend/app/orchestrator/...`)로 정합화
- 테스트 파일명도 네이밍 규칙에 맞춰 정리

## 2. 변경 파일 목록
- 코드 네이밍 정리:
  - `backend/app/stages/_shared/orchestrator_runtime.py` (신규 경로, 기존 `gateway_runtime.py` 대체)
  - `backend/app/stages/stage09_judge/node.py`
  - `backend/app/orchestrator/database/gateway.py`
  - `backend/app/orchestrator/stage_manager.py`
  - `backend/app/orchestrator/schemas/__init__.py`
  - `backend/app/orchestrator/schemas/transform.py`
  - `backend/app/stages/stage05_topk/node.py`
  - `backend/app/services/wiki_usecase.py`
  - `backend/app/stages/stage06_verify_support/node copy.py`
  - `backend/app/stages/stage07_verify_skeptic/node copy.py`
- 테스트 파일 리네이밍:
  - `backend/tests/unit/test_gateway_service_state_init.py` → `backend/tests/unit/test_orchestrator_service_state_init.py`
- 문서 경로 정합성 반영:
  - `docs/REFACTORING_STEP_02_ERROR_HANDLING_AND_STATE_INIT.md`
  - `docs/REFACTORING_STEP_03_CONFIG_CENTRALIZATION.md`
  - `docs/REFACTORING_STEP_04_TYPE_SAFETY.md`
  - `docs/REFACTORING_STEP_05_CHECKPOINTING.md`
  - `docs/REFACTORING_STEP_06_EXTERNAL_API_RATE_LIMITING.md`
  - `docs/REFACTORING_STEP_07_OBSERVABILITY.md`
  - `docs/REFACTORING_STEP_08_STAGE_ASYNC_UNIFICATION.md`
  - `docs/REFACTORING_STEP_09_GATEWAY_RENAMING.md`

## 3. 핵심 변경 내용
### 3.1 Runtime/예외 용어 통일
- `GatewayRuntime` 계열을 `OrchestratorRuntime` 계열로 치환
- Stage9 Judge 경로의 import/type/exception 처리 로직을 새 이름으로 동기화

### 3.2 DB 접근 클래스 명확화
- `DatabaseGateway`를 `DatabaseOrchestrator`로 변경
- 인스턴스 이름도 `db_orchestrator`로 통일

### 3.3 문서 레퍼런스 업데이트
- 기존 Step 02~08 문서의 코드 경로를 현재 리포지토리 구조에 맞게 업데이트
- 테스트 파일명 변경 반영(`test_orchestrator_service_state_init.py`)

## 4. 검증 방법 및 결과
1. 타입 검사
   - 명령: `cd backend && mypy --config-file mypy.ini app`
   - 결과: `Success: no issues found in 74 source files`

2. 테스트
   - 명령: `pytest backend/tests -q`
   - 결과: `27 passed, 1 warning`

## 5. 리스크/후속 작업
- 남은 리스크:
  - 현재 작업 디렉토리는 Git 메타데이터가 없어 rename diff(`R100`)를 로컬에서 확인할 수 없음.
- 후속 작업:
1. 원격 GitHub 리포지토리(PR/Push)에서 rename 인식 상태 확인
2. 필요 시 `backend/app/orchestrator/database/gemini_gateway_rag_restore.md`의 역사적 용어를 별도 정리

