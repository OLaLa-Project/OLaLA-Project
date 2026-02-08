# STEP-01 Integration Foundation

- Date: 2026-02-07
- Status: Completed
- Scope: 통합 프로덕션 루트 생성 + 원본 소스 이관 + 기본 실행 골격 구축

## 목표
기존 원본 디렉토리(프론트/백엔드/위키DB 덤프)를 손상 없이 유지하면서, 프로덕션 작업 전용 통합 워크스페이스를 바탕화면에 생성한다.

## 수행 작업
1. 통합 루트 생성
- 경로: `C:\Users\alber\Desktop\OLaLA-Production-v2`

2. 통합 폴더 구조 생성
- `apps/`, `services/`, `data/`, `infra/docker/`, `docs/`, `scripts/`

3. 원본 소스 이관(복사)
- `올랄라 프로젝트/olala_frontend` -> `apps/flutter`
- `올랄라 프로젝트/OLaLA-Project-backend` -> `services/backend-monorepo`
- `올랄라 프로젝트/wiki_db_dump_file` -> `data/wiki_db_dump_file`

4. Flutter 빌드 산출물 정리
- 제거: `.dart_tool`, `build`, `.idea`, `ios/Pods`, `.DS_Store`

5. 실행 대상 백엔드 분리
- `services/backend` 디렉토리에 `backend-monorepo/backend`를 별도 복사

## 기존 대비 변경 사항
- 기존: 원본 프로젝트 디렉토리 내부에서 혼합 작업
- 변경: 통합 프로덕션 전용 루트에서 작업
- 장점:
  - 원본 보존
  - 배포/운영 파일을 단일 루트에서 관리 가능
  - 단계별 산출물 추적 용이

## 산출물
- 루트 문서: `README.md`
- 환경 예시: `.env.example`
- 베타 compose: `infra/docker/docker-compose.beta.yml`
- 실행 스크립트:
  - `scripts/run_beta.sh`
  - `scripts/check_stack.sh`
  - `scripts/import_wiki_db.sh`
- 단계 문서:
  - `docs/STEP_BY_STEP.md`
  - `docs/NEXT_ACTIONS.md`
  - `docs/API_CONTRACT_V1.md`

## 검증 결과
- 통합 루트 및 주요 하위 디렉토리 생성 확인
- 이관 대상 디렉토리 존재 확인
- 위키 덤프 데이터(대용량) 복사 완료 확인

## 남은 리스크
1. 경로 리스크
- 현재 통합 루트가 Windows 파일시스템(`/mnt/c`) 상에 있어 WSL Docker I/O 성능 저하 가능성 존재

2. 실행 검증 미완료
- 베타 스택 기동/헬스체크, 위키 DB 적재는 아직 실행 전

3. 보안/운영 하드닝 미완료
- 내부 운영 API 분리, 비밀값 관리, 릴리스 정책은 후속 단계 필요

## 다음 단계
- STEP-02: Flutter-Backend 연결 안정화(API/WS 브리지 + 검증 API 연결)
