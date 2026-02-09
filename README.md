# OLaLA Production (Beta)

이 디렉토리는 다음 3개 소스를 통합한 베타 프로덕션 워크스페이스입니다.
- `apps/flutter` <- `올랄라 프로젝트/olala_frontend`
- `services/backend` <- `올랄라 프로젝트/OLaLA-Project-backend/backend`
- `data/wiki_db_dump_file` <- `올랄라 프로젝트/wiki_db_dump_file`

## 통합 구조
- `apps/flutter`: Flutter 앱
- `services/backend`: FastAPI 백엔드
- `infra/docker`: Docker Compose (WSL 실행 기준)
- `scripts`: 실행/적재/검증 스크립트
- `docs`: 통합 계약/단계 문서

## 빠른 시작 (WSL)
1. `.env.beta` 파일 생성: `cp .env.example .env.beta`
2. 스택 기동: `bash scripts/run_beta.sh`
3. 위키 DB 적재: `bash scripts/import_wiki_db.sh`
4. 상태 확인: `bash scripts/check_stack.sh`
   - LLM 모델/키 사전점검: `bash scripts/check_llm_stack.sh`
5. Flutter 실행: `bash scripts/flutter_run_env.sh dev`

## Flutter 환경 분리
- 환경 파일: `apps/flutter/config/env/{dev,beta,prod}.json`
- 실행:
  - `bash scripts/flutter_run_env.sh dev`
  - `bash scripts/flutter_run_env.sh beta`
  - `bash scripts/flutter_run_env.sh prod`
- Android release 빌드:
  - `bash scripts/flutter_build_android_env.sh beta apk`
  - `bash scripts/flutter_build_android_env.sh beta aab`
- 베타 릴리스 준비:
  - `bash scripts/prepare_beta_release_bundle.sh <tag>`
  - `bash scripts/github_prerelease_beta.sh <tag> <owner/repo>`
  - `FIREBASE_APP_ID=<app_id> bash scripts/firebase_distribute_beta.sh <tag>`

## 주의
- WSL 성능을 위해 `/mnt/c` 대신 WSL 리눅스 경로에서 Docker를 실행하는 것을 권장합니다.
- Android 에뮬레이터는 `10.0.2.2`, 실기기는 동일 네트워크의 호스트 IP를 사용하세요.
- Stage9 외부 LLM 사용 시 `.env.beta`에 `JUDGE_BASE_URL`, `JUDGE_API_KEY`, `JUDGE_MODEL`을 설정하세요.
- 장애를 HTTP 5xx로 즉시 노출하려면 `.env.beta`에 `STRICT_PIPELINE=true`를 설정하세요.
- Ollama를 CPU로 사용할 때는 `.env.beta`에 `SLM1_TIMEOUT_SECONDS`, `SLM2_TIMEOUT_SECONDS`, `JUDGE_TIMEOUT_SECONDS`를 180 이상으로, `SLM1_MAX_TOKENS`, `SLM2_MAX_TOKENS`, `JUDGE_MAX_TOKENS`를 384 내외로 설정하세요.
