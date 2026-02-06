# REFACTORING STEP 06 - External API Rate Limiting

**작업 일시:** 2026-02-06  
**기준 문서:** `docs/REFACTORING_PRIORITY.md` (#7 External API Rate Limiting)

## 1. 배경/목표
- Stage03의 Naver/DDG 외부 호출에 과호출 방지 장치 도입
- 429/5xx 및 타임아웃 상황에서 재시도(backoff) 표준화
- timeout/retry/backoff 정책을 설정값으로 중앙화

## 2. 변경 파일 목록
- 수정: `backend/app/stages/stage03_collect/node.py`
- 수정: `backend/app/core/settings.py`
- 수정: `backend/.env.example`
- 신규: `backend/tests/unit/test_stage03_rate_limit.py`

## 3. 핵심 변경 내용
### 3.1 Rate Limiter 도입
- `run_web_async()`에서 provider별 세마포어 적용
  - Naver: `NAVER_MAX_CONCURRENCY`
  - DDG: `DDG_MAX_CONCURRENCY`
- 각 검색 함수 호출에 limiter를 주입해 burst 시 동시 호출량 상한을 강제

### 3.2 Retry + Backoff 표준화
- 공통 정책 함수 추가:
  - `_api_retry_attempts()`
  - `_api_backoff_seconds()`
  - `_backoff_delay(attempt)`
  - `_is_retryable_status(status_code)`
- Naver:
  - 429/5xx 상태코드에서 exponential backoff 후 재시도
  - `requests.Timeout`, `requests.RequestException` 재시도 처리
- DDG:
  - rate-limit/timeout성 오류 문자열(429/rate/timeout) 감지 시 재시도
  - 실패 시 기존과 동일하게 안전하게 빈 결과 반환

### 3.3 Timeout 표준화
- Naver 요청 timeout을 설정 기반으로 통일
- DDG 동기 호출(`to_thread`)을 `asyncio.wait_for`로 감싸 timeout 강제

### 3.4 설정 중앙화
- `backend/app/core/settings.py`에 외부 API 내성 설정 추가:
  - `external_api_timeout_seconds`
  - `external_api_retry_attempts`
  - `external_api_backoff_seconds`
  - `naver_max_concurrency`
  - `ddg_max_concurrency`
- `backend/.env.example`에 대응 변수 추가

## 4. 테스트/검증
1. 타입 검사
   - 명령: `cd backend && mypy --config-file mypy.ini app`
   - 결과: `Success: no issues found in 73 source files`

2. 테스트
   - 명령: `pytest backend/tests -q`
   - 결과: `23 passed, 1 warning`

3. 신규 단위 테스트
   - `test_search_naver_retries_after_429`
   - `test_search_ddg_retries_after_rate_limit_error`

## 5. 완료 기준(DoD) 충족 여부
- limiter + retry 정책 도입: **충족**
- timeout/retry/backoff 표준화: **충족**
- burst 요청 과호출 방지: **충족(세마포어 기반 상한 제어)**

## 6. 남은 리스크
- 현재 limiter는 프로세스 인스턴스 단위 세마포어이므로, 멀티 인스턴스 분산 환경의 글로벌 쿼터 제어는 별도 인프라(공유 rate limiter)로 확장 필요.
- DDG 오류 분류는 라이브러리 예외 타입이 버전별로 달라 메시지 기반 판정을 일부 포함함.

## 7. 추가 작업 - Checkpoint 저장소 PostgreSQL 통일 (요청 반영)
### 7.1 배경
- 기존 구현에 SQLite 기반 checkpoint 메타데이터(`checkpoint_threads`) 경로가 포함되어 있었고, 운영 DB(PostgreSQL)와 저장소가 분리되는 문제가 있었음.
- 팀 운영 정책(단일 DB 일관성)에 맞춰 checkpoint 메타데이터 저장소를 PostgreSQL로 통일.

### 7.2 구현 상세
- 수정: `backend/app/graph/checkpoint.py`
  - SQLite 파일 접근 로직 제거
  - PostgreSQL 테이블 기반 thread TTL 관리로 전환:
    - 테이블: `checkpoint_threads` (환경변수 `CHECKPOINT_THREAD_TABLE`로 변경 가능)
    - 컬럼: `thread_id`(PK), `last_seen`(TIMESTAMPTZ)
  - `resolve_checkpoint_thread_id()`에서 `CHECKPOINT_BACKEND=postgres`일 때
    - 만료 row 정리
    - upsert(last_seen 갱신)
    - TTL 초과 시 fallback thread 발급
  - PostgreSQL 접근 실패 시 메모리 기반 정책으로 안전 fallback(서비스 중단 방지)

- 수정: `backend/app/core/settings.py`
  - `CHECKPOINT_BACKEND` 기본값을 `postgres`로 변경
  - `CHECKPOINT_THREAD_TABLE` 설정 추가
  - 허용 backend를 `postgres|memory|none`으로 정규화

- 수정: `backend/.env.example`
  - `CHECKPOINT_BACKEND=postgres`
  - `CHECKPOINT_THREAD_TABLE=checkpoint_threads`

- 수정: `backend/app/orchestrator/service.py`
  - sync full-run 경로에서 LangGraph `ainvoke(..., config={"configurable":{"thread_id":...}})` 사용 유지
  - stream 경로와 함께 동일 `thread_id` 전략 적용

### 7.3 LangGraph saver 가용성 메모
- 현재 런타임 점검 결과 `langgraph.checkpoint.postgres` 모듈이 기본 설치에 포함되지 않아 `PostgresSaver`는 미가용.
- 따라서 checkpointer 객체는 런타임에서 memory saver fallback을 사용하며,
  thread TTL/재개 판정 메타데이터는 PostgreSQL 단일 저장소로 유지됨.
- 추후 `PostgresSaver` 패키지/버전을 표준화하면 checkpoint payload까지 PostgreSQL로 완전 일원화 가능.

### 7.4 검증
- 타입 검사: `Success: no issues found in 73 source files`
- 테스트: `23 passed, 1 warning`
- 추가 확인 테스트:
  - `test_resolve_checkpoint_thread_id_uses_postgres_backend`
  - `test_run_pipeline_uses_langgraph_in_full_mode`
