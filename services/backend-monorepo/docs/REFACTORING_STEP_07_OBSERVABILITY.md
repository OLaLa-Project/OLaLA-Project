# REFACTORING STEP 07 - Observability 기본 세트

**작업 일시:** 2026-02-06  
**기준 문서:** `docs/REFACTORING_STEP_00_ANALYSIS.md` (Step 07 - Observability 기본 세트)

## 1. 배경/목표
- Stage별 지연시간과 실패 건수를 운영 관점에서 빠르게 확인할 수 있는 최소 메트릭 도입
- 외부 API(Naver/DDG) 성공률을 누적 지표로 관리
- trace_id와 stage 이벤트를 함께 남겨 실패 요청 역추적 가능성 확보

## 2. 변경 파일 목록
- 신규: `backend/app/core/observability.py`
- 수정: `backend/app/graph/stage_logger.py`
- 수정: `backend/app/stages/stage03_collect/node.py`
- 수정: `backend/app/orchestrator/service.py`
- 수정: `backend/app/api/dashboard.py`
- 신규: `backend/tests/unit/test_observability.py`

## 3. 핵심 변경 내용
### 3.1 관측 메트릭 모듈 추가
- `backend/app/core/observability.py`
  - Stage 메트릭:
    - `record_stage_result(stage, trace_id, duration_ms, ok)`
    - stage별 `count`, `avg_ms`, `p50_ms`, `p95_ms`
    - stage 실패 카운트(`stage_errors`)
  - 외부 API 메트릭:
    - `record_external_api_result(provider, ok)`
    - provider별 `requests`, `success`, `failure`, `success_ratio`
  - Trace 이벤트:
    - 최근 이벤트(최대 200개) 보관, 응답에는 최근 20개 노출
  - 테스트 유틸:
    - `reset_observability_for_test()`

### 3.2 Stage latency/error 자동 수집
- `backend/app/graph/stage_logger.py`
  - stage 완료 시 duration 기반 메트릭 자동 기록
- `backend/app/orchestrator/service.py`
  - sync/stream 실패 시 stage error 메트릭 기록

### 3.3 External API success ratio 수집
- `backend/app/stages/stage03_collect/node.py`
  - Naver/DDG 최종 성공/실패 지점에서 메트릭 기록
  - Step06의 retry/backoff 로직과 결합하여 실제 최종 결과 기준 success/failure 집계

### 3.4 운영 조회 엔드포인트 통합
- `backend/app/api/dashboard.py`
  - 기존 `/api/metrics` 응답에 `pipeline` 필드 추가
  - 시스템/프로세스 통계와 파이프라인 메트릭을 한 응답에서 조회 가능

## 4. 검증 결과
1. 타입 검사
   - 명령: `cd backend && mypy --config-file mypy.ini app`
   - 결과: `Success: no issues found in 73 source files`

2. 테스트
   - 명령: `pytest backend/tests -q`
   - 결과: `23 passed, 1 warning`

3. 신규 테스트
   - `backend/tests/unit/test_observability.py`
     - stage latency/error 집계 검증
     - external API success ratio 집계 검증

## 5. 완료 기준(DoD) 충족 여부
- stage latency 확인 가능: **충족**
- stage error count 확인 가능: **충족**
- external API success ratio 확인 가능: **충족**
- trace_id 기반 최근 이벤트 확인 가능: **충족**

## 6. 남은 리스크
- 현재 메트릭 저장소는 프로세스 메모리 기반이므로 멀티 인스턴스 합산 지표는 별도 백엔드(Prometheus/OTel 등) 연계가 필요.
- p95 계산은 최근 샘플(기본 500개) 기반이며 장기 보존/정확한 히스토그램은 추후 확장 과제.
