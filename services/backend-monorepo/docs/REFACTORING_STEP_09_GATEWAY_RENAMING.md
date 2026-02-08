# REFACTORING STEP 09 - Gateway 리네이밍

**작업 일시:** 2026-02-06  
**기준 문서:** `docs/REFACTORING_STEP_00_ANALYSIS.md` (Step 09 - Gateway 리네이밍)

## 1. 배경/목표
- `gateway`라는 이름이 API Gateway 개념과 내부 오케스트레이션 레이어를 혼동시키는 문제를 해소
- 모듈 책임에 맞게 패키지 네이밍을 `orchestrator`로 통일
- 리네이밍 이후 import 깨짐 없이 기존 기능을 동일 동작으로 유지

## 2. 변경 파일 목록
- 디렉토리 이동: `backend/app/gateway` → `backend/app/orchestrator`
- import 경로 갱신:
  - `backend/app/api/truth_check.py`
  - `backend/app/api/wiki.py`
  - `backend/app/graph/graph.py`
  - `backend/app/db/session.py`
  - `backend/app/db/models/__init__.py`
  - `backend/app/services/wiki_usecase.py`
  - `backend/app/services/web_rag_service.py`
  - `backend/app/stages/stage01_normalize/node.py`
  - `backend/app/stages/stage02_querygen/node.py`
  - `backend/app/debug_db.py`
  - `backend/tests/unit/test_checkpointing.py`
  - `backend/tests/unit/test_orchestrator_service_state_init.py`
  - `backend/tests/unit/test_stage_manager_async_registry.py`
  - `backend/mypy.ini`
- 기타 정합성 수정:
  - `backend/app/orchestrator/__init__.py`
  - `backend/app/orchestrator/database/gemini_gateway_rag_restore.md`

## 3. 핵심 변경 내용
### 3.1 패키지 네이밍 통일
- 기존 `app.gateway.*` 참조를 전부 `app.orchestrator.*`로 교체
- 서비스 진입점(`run_pipeline`, `run_pipeline_stream`)과 stage registry import 경로를 새 패키지 기준으로 정렬

### 3.2 DB/스키마/임베딩 경로 정리
- DB 모델, 저장소(repo), 스키마, 임베딩 클라이언트 import를 새 경로로 통일
- 기존 비즈니스 로직 동작은 변경하지 않고 모듈 경로만 재배선

### 3.3 타입/테스트 설정 동기화
- `mypy.ini` 대상 모듈 경로를 `app.orchestrator.service`, `app.orchestrator.stage_manager`로 갱신
- 단위 테스트 import 및 alias 명칭을 orchestrator 기준으로 정리

## 4. 검증 방법 및 결과
1. 타입 검사
   - 명령: `cd backend && mypy --config-file mypy.ini app`
   - 결과: `Success: no issues found in 74 source files`

2. 테스트
   - 명령: `pytest backend/tests -q`
   - 결과: `27 passed, 1 warning`
   - warning: `starlette/formparsers.py`의 `python_multipart` 관련 기존 경고 1건(기존과 동일)

## 5. 리스크/후속 작업
- 해결 완료:
  - `DatabaseGateway` → `DatabaseOrchestrator`로 클래스명 변경
  - `gateway_runtime.py` → `orchestrator_runtime.py`로 모듈명 변경
  - Stage9 runtime 타입/예외명 일괄 변경:
    - `GatewayRuntime` → `OrchestratorRuntime`
    - `GatewayError` → `OrchestratorError`
    - `GatewayValidationError` → `OrchestratorValidationError`
- 추가 변경 파일:
  - `backend/app/orchestrator/database/gateway.py`
  - `backend/app/stages/_shared/orchestrator_runtime.py`
  - `backend/app/stages/stage09_judge/node.py`
  - `backend/app/stages/stage06_verify_support/node copy.py`
  - `backend/app/stages/stage07_verify_skeptic/node copy.py`
  - `backend/app/orchestrator/stage_manager.py`
  - `backend/app/orchestrator/schemas/__init__.py`
  - `backend/app/orchestrator/schemas/transform.py`
  - `backend/app/stages/stage05_topk/node.py`
  - `backend/app/services/wiki_usecase.py`
- 재검증 결과:
1. `mypy --config-file backend/mypy.ini backend/app` 통과 (`74 source files`)
2. `pytest backend/tests -q` 통과 (`27 passed, 1 warning`)

- 남은 리스크:
  - 현재 작업 디렉토리는 Git 메타데이터가 없어 `git mv` 기반 rename 이력(R100) 확인은 불가.
  - 로컬 확인 결과: `git rev-parse --is-inside-work-tree` → `fatal: not a git repository`

- 후속 작업:
1. 원격 Git 리포지토리(PR/Push)에서 rename diff(`R100`) 인식 여부 확인
2. 필요 시 `backend/app/orchestrator/database/gemini_gateway_rag_restore.md`의 레거시 용어(`Gateway`)를 문서 관점으로 추가 정리
