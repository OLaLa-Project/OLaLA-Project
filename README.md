# OLaLA MVP

OLaLA는 멀티 에이전트 기반 가짜뉴스 판독 MVP입니다. 이 레포는 **프론트(Flutter) / 백엔드(FastAPI) / MLOps**를 한 곳에 모은 **모노레포**입니다.

## 빠른 시작 (로컬)
1) `.env.example` → `.env` 복사 후 값 입력
2) 실행: `docker compose up -d`
3) 백엔드 헬스체크: `http://localhost:8000/health`
4) 웹 대시보드: `http://localhost:5173`

## 디렉토리 구조
- `frontend/`  Flutter 모바일 앱
- `web/`       React 웹 대시보드
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
