# STEP-17 LLM Config Source of Truth

- Date: 2026-02-09
- Status: Completed
- Scope: Judge API 키 주입 경로 명확화 + Docker compose 설정 우선순위 정리

## 목표
백엔드 런타임 설정을 `.env.beta` 단일 기준으로 고정하고, Stage9 외부 LLM API 키 입력 경로를 명확히 한다.

## 수행 작업
1. `.env.beta` 단일 소스화
- 파일: `infra/docker/docker-compose.beta.yml`
- 변경: `backend.environment` 블록 제거
- 이유: `environment` 기본값이 `env_file` 값을 덮어써 실제 설정 불일치를 만들던 문제 제거

2. Judge API 키 입력 경로 문서화
- 파일: `.env.example`, `README.md`
- 명시 항목:
  - `JUDGE_BASE_URL`
  - `JUDGE_API_KEY`
  - `JUDGE_MODEL`
- OpenAI/Perplexity 예시 추가

3. Strict 모드 설정값 추가
- 파일: `.env.example`, `services/backend/app/core/settings.py`
- 추가: `STRICT_PIPELINE=false` (기본), 런타임 토글 가능하도록 반영

## 기존 대비 변경 사항
- 기존:
  - `.env.beta`를 수정해도 compose 기본값에 의해 일부 값이 덮여 실제 반영이 불명확
  - Judge API 키 입력 위치가 문서상 불명확
- 변경:
  - `.env.beta`가 backend 설정의 단일 기준이 됨
  - Stage9 외부 LLM 키 입력 위치를 문서/예시로 명확화

## 검증 결과
1. 런타임 환경 확인
- 실행: `docker exec olala-backend env | rg '^(SLM1_|SLM2_|JUDGE_)'`
- 결과: SLM/JUDGE 변수들이 컨테이너에 반영됨

2. 스모크 결과
- 실행: `bash scripts/smoke_mobile_bridge.sh`
- 결과: endpoint는 응답하지만 `LLM_JUDGE_FAILED` 감지 (모델 미설치 이슈로 단계18에서 대응)

## 남은 리스크
1. `JUDGE_API_KEY` 관리 리스크
- 키를 `.env.beta`에 평문 저장하면 유출 위험이 큼
- 외부에 노출된 키는 반드시 폐기(rotate) 필요

2. 모델/키 조합 불일치
- Judge를 ollama로 사용할지 외부 LLM으로 사용할지 운영 정책 고정 필요

## 다음 단계
- STEP-18: 실패 조기 감지(preflight)와 파이프라인 fail-fast 강화
