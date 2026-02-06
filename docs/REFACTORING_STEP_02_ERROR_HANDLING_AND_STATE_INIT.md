# OLaLA Refactoring Step 02 - API 에러 처리 + State 초기화 통합

**작성일:** 2026-02-06  
**기준 단계:** `docs/REFACTORING_STEP_00_ANALYSIS.md`의 Step 02

---

## 1. 배경/목표

Step 02 목표는 다음 두 가지였다.

1. `/truth/check` API의 예외 처리 품질 향상
2. `service.py`의 중복된 state 초기화 경로 통합

핵심 의도:
1. 파이프라인 실행 오류와 DB 저장 오류를 구분 처리
2. 스트리밍/동기 실행에서 동일한 초기 state 계약 유지

---

## 2. 변경 파일 목록

### 신규 파일
1. `backend/app/core/errors.py`
2. `backend/tests/integration/test_truth_check_error_handling.py`
3. `backend/tests/unit/test_orchestrator_service_state_init.py`
4. `docs/REFACTORING_STEP_02_ERROR_HANDLING_AND_STATE_INIT.md`

### 수정 파일
1. `backend/app/api/truth_check.py`
2. `backend/app/orchestrator/service.py`
3. `backend/requirements-dev.txt`
4. `docs/REFACTORING_STEP_01_TEST_FOUNDATION.md`

---

## 3. 핵심 변경 내용

### 3-1. API 에러 처리 표준화

`backend/app/core/errors.py`에 API 에러 스펙을 도입했다.

1. `PIPELINE_EXECUTION_FAILED`
2. `PIPELINE_STREAM_INIT_FAILED`
3. `to_http_exception()` 변환 함수

`backend/app/api/truth_check.py` 변경:
1. `run_pipeline` 예외를 500 구조화 에러로 변환
2. `AnalysisRepository.save_analysis()` 실패 시 요청 자체는 성공(200) 유지
3. 저장 실패 시 `risk_flags`에 `PERSISTENCE_FAILED` 추가
4. stream 초기화 예외를 구조화 에러로 변환

### 3-2. 실행 경로(state 초기화) 통합

`backend/app/orchestrator/service.py` 변경:
1. `_init_state(req, trace_id=None)` 함수 추가
2. `run_pipeline()`와 `run_pipeline_stream()`이 동일 초기화 함수 사용
3. `stage_state`, `normalize_mode`, `include_full_outputs` 적용 로직 단일화

효과:
1. 동기/스트리밍 경로 간 초기 state 불일치 위험 감소
2. state 필드 추가/수정 시 변경 지점 1곳으로 축소

### 3-3. 테스트 범위 확장

신규 테스트 추가:
1. 파이프라인 예외 시 구조화 에러 응답 검증
2. DB 저장 실패 시 200 응답 + `PERSISTENCE_FAILED` 검증
3. `_init_state` 기본값/override 동작 검증

---

## 4. 검증 방법 및 결과

### 4-1. Step 02 코드 컴파일 검증
1. 명령:
   - `python3 -m compileall backend/app/api/truth_check.py backend/app/orchestrator/service.py backend/app/core/errors.py backend/tests/integration/test_truth_check_error_handling.py backend/tests/unit/test_orchestrator_service_state_init.py`
2. 결과: 성공

### 4-2. Python 3.11 컨테이너 기준 테스트 실행
1. 명령:
   - `docker run --rm -v "$PWD":/work -w /work python:3.11-slim bash -lc "apt-get update >/dev/null && apt-get install -y --no-install-recommends gcc python3-dev >/dev/null && pip install -r backend/requirements-dev.txt && pytest backend/tests -q"`
2. 결과:
   - `7 passed, 1 warning`

### 4-3. CI 워크플로 유효성 점검
1. 명령:
   - `docker run --rm -v "$PWD":/repo -w /repo rhysd/actionlint:latest .github/workflows/backend-tests.yml`
2. 결과: 성공

---

## 5. 리스크/후속 작업

1. **남은 리스크**
   - 현재 작업 디렉토리는 Git 메타데이터가 없어 GitHub Actions의 실제 "첫 실행 결과(run id)" 조회는 불가.

2. **후속 작업**
1. 원격 GitHub 리포지토리에서 PR/Push 후 `Backend Tests` 워크플로 실제 실행 로그 확인
2. Step 03(Config 중앙화) 진행

