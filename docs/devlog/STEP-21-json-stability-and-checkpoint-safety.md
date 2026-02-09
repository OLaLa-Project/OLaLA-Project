# STEP-21 JSON Stability and Checkpoint Safety

- Date: 2026-02-09
- Status: Completed
- Scope: Stage6/7/9 JSON 파싱 안정화, 체크포인트 런타임 크래시 제거, 설정/의존성 정리

## 목표/범위
- Stage6/7/9에서 모델 출력(JSON)이 잘려 파이프라인이 흔들리거나 `LLM_JUDGE_FAILED`가 발생하는 리스크를 줄인다.
- 체크포인트(Postgres) 적용 시 `PIPELINE_CRASH`가 발생하는 문제를 제거하고, 안전한 fallback 동작을 보장한다.
- Judge API 키 주입 경로를 운영 친화적으로 정리한다.

## 수행 작업
1. Judge API 키 환경변수 alias 추가
- 파일: `services/backend/app/core/settings.py`
- 변경: `judge_api_key`가 아래 env를 모두 수용하도록 확장
  - `JUDGE_API_KEY` (기본)
  - `OPENAI_API_KEY` (호환)
  - `PPLX_API_KEY`, `PERPLEXITY_API_KEY` (Perplexity 호환)

2. 의존성 보강
- 파일: `services/backend/requirements.txt`
- 변경:
  - `ddgs` 추가(duckduckgo-search rename 경고 제거 목적)
  - `langgraph-checkpoint-postgres`, `psycopg[binary]` 추가(향후 Postgres 체크포인터 재도입 기반)

3. 체크포인트 런타임 크래시(PIPELINE_CRASH) 제거
- 파일: `services/backend/app/graph/checkpoint.py`
- 원인:
  - async 그래프(ainvoke/astream)에서 sync PostgresSaver 사용 시 `aget_tuple` 미구현으로 NotImplementedError 발생 가능
- 조치:
  - Postgres checkpointer는 일시 비활성화하고 memory checkpointer로 강제 fallback
  - 로그로 명시적으로 경고 출력

4. JSON 출력 안정화(잘림/파싱 실패 대응)
- 파일:
  - `services/backend/app/core/settings.py`
  - `.env.example`
  - `.env.beta` (로컬 베타 실행용)
  - `services/backend/app/stages/stage06_verify_support/prompt_supportive.txt`
  - `services/backend/app/stages/stage07_verify_skeptic/prompt_skeptical.txt`
  - `services/backend/app/stages/stage09_judge/prompt_judge.txt`
- 변경:
  - `SLM1_MAX_TOKENS`, `SLM2_MAX_TOKENS`, `JUDGE_MAX_TOKENS` 기본값 상향
  - Stage6/7/9 프롬프트에 출력 길이/리스트 개수 제한 규칙 추가
  - `.env.beta`의 `*_BASE_URL`을 `.../v1`로 정리(불필요한 404 시도 제거)

5. 파이프라인 실패 로그 품질 개선
- 파일: `services/backend/app/orchestrator/service.py`
- 변경: `str(e)`가 빈 경우를 대비해 `logger.exception(..., %r)`로 스택트레이스/표현식 로그 보존

## 변경 사항(기존 대비)
- 기존:
  - Stage6/7/9 JSON이 잘려 파싱 실패 -> `LLM_JUDGE_FAILED` 발생
  - Postgres checkpointer 적용 시 `PIPELINE_CRASH` 발생 가능
  - Judge 키는 `JUDGE_API_KEY`만 허용(운영/CI 주입 시 혼선 가능)
- 변경:
  - max_tokens 상향 + 출력 제한으로 JSON 파싱 실패 빈도 감소
  - 체크포인터로 인한 파이프라인 크래시 제거(메모리 fallback 고정)
  - Perplexity/OpenAI 키 alias로 설정 주입 실수 감소

## 검증 결과
- `bash scripts/check_stack.sh` 통과
- `TRUTH_TIMEOUT_SECONDS=300 bash scripts/smoke_mobile_bridge.sh` 통과
  - `risk_flags`에 `LLM_JUDGE_FAILED/PIPELINE_CRASH/QUALITY_GATE_FAILED/PERSISTENCE_FAILED` 미검출

## 남은 리스크
- Postgres 체크포인팅 미활성:
  - 현재는 안정성을 위해 memory checkpointer로 고정
  - 운영에서 재시작/스케일아웃 시 체크포인트 복구가 필요하면 AsyncPostgresSaver 기반으로 재설계 필요
- max_tokens 상향:
  - 추론 지연/비용이 증가할 수 있음(특히 외부 LLM 사용 시)
- 외부 검색 크리덴셜:
  - `NAVER_CLIENT_ID/SECRET` 미설정이면 뉴스 검색 품질이 제한될 수 있음

## 다음 단계
- Stage9 외부 Judge(Perplexity/OpenAI) 운영 정책 확정 및 키 로테이션/마스킹/주입 파이프라인 정비
- checkpoint 설계를 "요청 처리 모델(스레드/이벤트루프)"에 맞춰 AsyncPostgresSaver로 재도입(필요 시)

