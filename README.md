# OLaLA MVP

OLaLA는 멀티 에이전트 기반 가짜뉴스 판독 MVP입니다. 이 레포는 **프론트(Flutter) / 백엔드(FastAPI) / MLOps**를 한 곳에 모은 **모노레포**입니다.

## 빠른 시작 (로컬)

```bash
# 1. 환경변수 설정
cp .env.example .env

# 2. 전체 서비스 실행 (api + db + ollama)
docker compose up -d --build

# 3. Ollama 모델 다운로드 (최초 1회)
docker exec -it olala-project-ollama-1 ollama pull llama3.2

# 4. 헬스체크
curl http://localhost:8000/health
```

## SLM2 테스트 (Stage 6-8)

```bash
# 케이스 1 실행
docker compose run --rm slm2-test --case 1

# 전체 케이스 실행
docker compose run --rm slm2-test --all

# 로컬 환경에서 mock 테스트 (SLM 서버 불필요)
cd backend && python -m tests.test_slm2_stages
```

## Ollama 모델 설정

`.env` 파일에서 모델을 변경할 수 있습니다:

```bash
# .env
SLM_MODEL=llama3.2          # 기본값 (3B 파라미터, 가벼움)
# SLM_MODEL=llama3.1:8b     # 더 높은 품질
# SLM_MODEL=gemma2:2b       # 경량 대안
```

모델 변경 후 pull 필요:
```bash
docker exec -it olala-project-ollama-1 ollama pull <모델명>
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
