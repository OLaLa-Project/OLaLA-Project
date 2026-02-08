# STEP-03 Beta Stack and Wiki DB

- Date: 2026-02-07
- Status: Completed
- Scope: WSL(Ubuntu) Docker 기반 베타 스택 안정화 + wiki DB(CSV) 적재 검증

## 목표
WSL 환경에서 `backend + wiki-db`를 안정적으로 기동하고, `wiki_db_dump_file`의 CSV를 Docker DB로 적재해 실제 서비스에서 사용할 수 있는 베타 런타임을 확보한다.

## 수행 작업
1. 베타 스택 기동 실패 원인 분석
- 증상: `wiki-db` 컨테이너가 `unhealthy`로 반복 재시작
- 원인: Windows 경로 바인드 마운트(`.runtime/pgdata`)에서 PostgreSQL 초기화 시 `chmod` 권한 실패

2. Docker 볼륨 전략 수정 (WSL 안정화)
- 파일: `infra/docker/docker-compose.beta.yml`
- 변경:
  - `wiki-db` 데이터 경로를 바인드 마운트 -> Docker named volume(`wiki-db-data`)로 전환
  - `ollama` 데이터 경로를 바인드 마운트 -> Docker named volume(`ollama-data`)로 전환
  - `wiki_db_dump_file`는 읽기 전용(`/import:ro`)으로 유지
- 기대 효과:
  - Windows/WSL 파일 권한 이슈 제거
  - 재기동/업데이트 시 DB 안정성 향상

3. 백엔드 부팅 재시작 루프 원인 수정
- 증상: `olala-backend`가 반복 재시작
- 원인: DB 초기화 시 `VECTOR(768)` 타입 생성 전에 `pgvector` 확장이 없어 테이블 생성 실패
- 파일: `services/backend/app/db/init_db.py`
- 변경:
  - `Base.metadata.create_all()` 이전에 `CREATE EXTENSION IF NOT EXISTS vector` 실행

4. 베타 스택 재기동 및 헬스 검증
- 실행: `bash scripts/run_beta.sh`
- 검증: `bash scripts/check_stack.sh`
- 결과:
  - `olala-wiki-db`: `Up (healthy)`
  - `olala-backend`: `Up`
  - `GET /health`: `{"status":"healthy"}`

5. wiki DB 적재 자동화 검증
- 실행: `bash scripts/import_wiki_db.sh`
- 수행:
  - 스키마/인덱스 보장
  - 기존 데이터 truncate
  - CSV `COPY` 적재
- 결과:
  - `wiki_pages`: `1,599,603`
  - `wiki_chunks`: `1,002,975`
  - 스크립트 최종 상태: `[ok] wiki DB import 완료`

## 기존 대비 변경 사항
- 기존:
  - DB 저장소가 Windows 바인드 마운트 기반이라 WSL 권한 충돌 발생
  - 백엔드가 `vector` 확장 미생성 상태에서 부팅되어 재시작 루프
- 변경:
  - Docker named volume 기반으로 스토리지 안정화
  - DB 초기화 순서 보강(확장 생성 -> 테이블 생성)
- 효과:
  - 베타 런타임 기동 안정성 확보
  - wiki 데이터셋 적재 자동화 경로 실동작 확인

## 검증 결과
1. 컨테이너 상태
- `olala-wiki-db` healthy 확인
- `olala-backend` running 확인

2. 애플리케이션 헬스
- `/health` 응답 정상(`status=healthy`)

3. 데이터 적재
- 대용량 CSV `COPY` 성공
- row count 검증 완료

## 남은 리스크
1. 대용량 적재 시간
- 전체 import가 환경 리소스에 따라 지연될 수 있음
- 베타 운영 시 초기 적재 시간/재적재 절차 문서화 필요

2. 백업/복구 운영정책 미정
- named volume은 안정적이지만 운영 백업 정책이 별도 필요

3. 앱-API E2E 미완료
- 서버/DB는 정상이나 Flutter 실기기 E2E(로그인/이슈/채팅/검증 플로우)는 다음 단계에서 확인 필요

## 다음 단계
- STEP-04: Flutter beta/prod 환경 분리(`dart-define`) + 실기기 Android 베타 빌드(APK/AAB) + 릴리스 경로 결정(GitHub pre-release vs Firebase 무료 경로)
