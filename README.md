# OLaLA MVP

OLaLA는 멀티 에이전트 기반 가짜뉴스 판독 MVP입니다. 이 레포는 **프론트(Flutter) / 백엔드(FastAPI) / MLOps**를 한 곳에 모은 **모노레포**입니다.

## 사전 준비 — 호스트 Ollama

SLM은 Docker 컨테이너가 아닌 **호스트 머신**에서 실행 중인 Ollama를 사용합니다.

```bash
# Ollama 설치: https://ollama.com
ollama pull qwen2.5:3b        # 모델 다운로드
ollama list                   # qwen2.5:3b 확인
```

## 빠른 시작

```bash
cp .env.example .env                   # 환경변수 (.env.example 기본값 그대로 사용 가능)
docker compose up -d --build           # api + db 실행 (Ollama 컨테이너 없음)
curl http://localhost:8000/health      # 헬스체크
```

## SLM2 테스트 (Stage 6-8)

```bash
# 기본 실행 (케이스 #1)
docker compose --profile test run --rm slm2-test

# 특정 케이스 지정
docker compose --profile test run --rm -e CASE=2 slm2-test

# 전체 케이스 실행
docker compose --profile test run --rm -e ALL=1 slm2-test

# 로컬 mock 테스트 (Ollama 불필요)
cd backend && python -m tests.test_slm2_stages
```

## 모델 변경

`.env`의 `SLM_MODEL`을 수정한 뒤 호스트에서 해당 모델을 pull 합니다.

```bash
# .env
SLM_MODEL=qwen2.5:3b       # 기본값
# SLM_MODEL=gemma3:4b       # 대안 1
# SLM_MODEL=llama3.2:3b     # 대안 2

# 호스트에서 pull
ollama pull <모델명>
```

## 디렉토리 구조
- `frontend/`  Flutter 모바일 앱
- `backend/`   FastAPI + Stage 파이프라인
- `mlops/`     학습/평가/모델 설정
- `shared/`    공통 스키마
- `docs/`      팀 가이드/계약/문서
- `legacy/`    과거 초안(수정 금지)

## 팀별 작업 위치
- 팀 A (Stage 1~5): `backend/app/stages/stage01_normalize` ~ `stage05_topk`
- 팀 B (Stage 6~8): `backend/app/stages/stage06_verify_support` ~ `stage08_aggregate`
- 공통 (Stage 9~10 + 스키마): `backend/app/stages/stage09_judge`, `stage10_policy`, `shared/`

## 브랜치 정책 (2개만 사용)
- `main`: 최종 데모/발표용 (직접 작업 금지)
- `sub`: 팀 작업 통합 브랜치 (모든 작업은 sub에 반영)

작업 방법은 `docs/HOW_TO_GIT.md`를 참고하세요.
