# STEP-22 Stage9 External Judge (Perplexity)

- Date: 2026-02-09
- Status: Completed
- Scope: Stage9 Judge를 외부 LLM(Perplexity)로 전환하고, API 키 주입 경로를 확정한다.

## 목표/범위
- Stage9 Judge가 로컬 Ollama가 아니라 외부 Judge(Perplexity)로 호출되도록 설정을 전환한다.
- 외부 provider인데 키가 비어있을 때 잘못된 기본값("ollama")이 주입되는 케이스를 방지한다.

## 수행 작업
1. 베타 런타임 설정 전환
- 파일: `.env.beta`
- 변경:
  - `JUDGE_BASE_URL=https://api.perplexity.ai`
  - `JUDGE_MODEL=sonar`
  - `JUDGE_API_KEY=` (사용자 주입 대기)

2. 외부 Judge 키 미주입 시 fail-fast
- 파일: `services/backend/app/stages/stage09_judge/node.py`
- 변경:
  - 외부 provider인데 `JUDGE_API_KEY`가 비어있으면 `OrchestratorValidationError`로 즉시 실패 처리
  - 로컬(ollama/localhost/11434)일 때만 api_key 기본값을 "ollama"로 허용

## 변경 사항(기존 대비)
- 기존:
  - 외부 Judge인데 키가 비어도 Stage9가 "ollama"를 기본값으로 넣어 잘못된 Authorization으로 호출할 수 있었음
- 변경:
  - 외부 Judge는 키 미주입 시 즉시 실패(원인 명확화)

## 검증 결과
1. 설정 반영
- 실행: `docker compose -f infra/docker/docker-compose.beta.yml up -d --force-recreate backend`
- 결과: `.env.beta` 변경(키 포함)이 백엔드 컨테이너에 반영됨

2. 스택 사전 점검
- 실행: `bash scripts/check_stack.sh`
- 결과: `JUDGE_API_KEY is set for external judge provider` 확인 및 통과

3. 기능 스모크(E2E)
- 실행: `TRUTH_TIMEOUT_SECONDS=300 bash scripts/smoke_mobile_bridge.sh`
- 결과: 통과
  - `model_info.provider=perplexity`, `model_info.model=sonar` 확인
  - `risk_flags`에 `LLM_JUDGE_FAILED/PIPELINE_CRASH/QUALITY_GATE_FAILED/PERSISTENCE_FAILED` 미검출

## 남은 리스크
- Perplexity 모델명(`sonar`)은 계정/플랜/시점에 따라 변경될 수 있어 404/400 가능
- 외부 호출은 네트워크/레이트리밋에 민감(타임아웃/재시도 정책 지속 점검 필요)

## 다음 단계
- API 키 주입 후:
  - `docker compose -f infra/docker/docker-compose.beta.yml up -d --force-recreate backend`
  - `bash scripts/check_stack.sh`
  - `TRUTH_TIMEOUT_SECONDS=300 bash scripts/smoke_mobile_bridge.sh`
