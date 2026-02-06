# Backend (FastAPI)

## 역할
LangGraph 파이프라인을 실행하고 `/truth/check` API를 제공합니다.
PostgreSQL에 결과를 저장합니다.

## 주요 경로
- API: `backend/app/api/`
- 그래프/스테이지: `backend/app/stages/`
- 공통 스키마: `backend/app/core/schemas.py`
- DB: `backend/app/db/`

## Stage 작업 위치
- Stage1~5: `backend/app/stages/stage01_normalize` ~ `stage05_topk`
- Stage6~8: `backend/app/stages/stage06_verify_support` ~ `stage08_aggregate`
- Stage9: `backend/app/stages/stage09_judge` (Final Verdict & Quality Gate)

## 실행 방법
```bash
pip install -r backend/requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8080
```

## 환경변수 설정
- 템플릿: `backend/.env.example`
- 중앙 설정 모듈: `backend/app/core/settings.py`
- 기본적으로 `.env` 또는 `backend/.env`를 읽습니다.

## 테스트 방법
```bash
pip install -r backend/requirements-dev.txt
pytest backend/tests -q
```

## 타입 체크 (Step 04)
```bash
cd backend
mypy --config-file mypy.ini app
```

## Postgres 적용
- `docker-compose.yml`에 DB 포함
- 서버 시작 시 `analysis_results` 테이블 자동 생성
- 저장 로직: `backend/app/db/repo.py`

## 주의사항
- 스키마 변경은 `shared/` 및 `docs/CONTRACT.md`와 반드시 동기화하세요.
