# 레포 사용 방법 (팀원 안내)

## 1) 레포 구조 요약
- `frontend/` : Flutter 앱 UI
- `backend/` : FastAPI + Stage 파이프라인
- `mlops/` : 학습/평가/모델 설정
- `shared/` : 공통 스키마
- `docs/` : 문서
- `legacy/` : 과거 초안 (수정 금지)

## 2) 팀별 작업 위치
### 팀 A (Evidence Pipeline)
- Stage 1~5
- 작업 경로: `backend/app/stages/stage01_normalize` ~ `stage05_topk`

### 팀 B (Verification)
- Stage 6~8
- 작업 경로: `backend/app/stages/stage06_verify_support` ~ `stage08_aggregate`

### 공통/플랫폼
- Stage 9~10 + 스키마/그래프
- 작업 경로:
  - `backend/app/stages/stage09_judge`, `stage10_policy`
  - `backend/app/graph/`
  - `shared/`

### 프론트엔드
- 작업 경로: `frontend/lib/`

## 3) 절대 건드리지 말 것
- `legacy/` 폴더 (과거 코드 보관용)
- `shared/` 스키마는 변경 시 반드시 공유/합의

## 4) 로컬 실행 (백엔드)
```bash
docker compose up -d
# health check
curl http://localhost:8000/health
```

## 5) API 확인
- `/health`
- `/truth/check`

## 6) 프론트 실행
```bash
cd frontend
flutter pub get
flutter run
```

## 7) 공통 계약 스키마
- `docs/CONTRACT.md`
- 프론트는 이 스키마만 믿고 렌더링
- 백엔드는 이 스키마로 응답
