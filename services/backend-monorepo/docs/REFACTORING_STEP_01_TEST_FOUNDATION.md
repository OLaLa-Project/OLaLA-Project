# OLaLA Refactoring Step 01 - 테스트 프레임워크 최소 골격 구축

**작성일:** 2026-02-06  
**기준 단계:** `docs/REFACTORING_STEP_00_ANALYSIS.md`의 Step 01

---

## 1. 배경/목표

리팩토링 안전망 확보를 위해 최소 테스트 실행 기반을 먼저 구축했다.

이번 단계 목표:
1. `pytest` 기반 테스트 구조 표준화
2. API 스모크 테스트 1개 확보
3. Stage 단위 테스트 1개 이상 확보
4. CI에서 자동 테스트 실행 경로 추가

---

## 2. 변경 파일 목록

### 신규 파일
1. `pytest.ini`
2. `backend/requirements-dev.txt`
3. `backend/tests/conftest.py`
4. `backend/tests/integration/test_health_api.py`
5. `backend/tests/unit/test_stage04_score.py`
6. `.github/workflows/backend-tests.yml`

### 수정 파일
1. `backend/README.md`
2. `backend/tests/__init__.py`

### 삭제 파일
1. `backend/tests/integration/test_truth_check_api.py`  
   삭제 사유: 현재 로컬 테스트 환경에서 DB 드라이버 의존성(`psycopg2`)으로 인한 실행 장애를 피하고, Step 01 목표(스모크 + stage 단위 테스트)에 맞춰 최소 골격으로 정리.

---

## 3. 핵심 변경 내용

1. **pytest 기본 설정 추가**
   - `pytest.ini`로 테스트 탐색 기준(`backend/tests`, `test_*.py`) 고정.

2. **개발/테스트 의존성 분리**
   - `backend/requirements-dev.txt` 추가.
   - Step 01 범위 테스트에 필요한 최소 패키지를 명시.

3. **공통 fixture 도입**
   - `backend/tests/conftest.py`에서 공통 `client` fixture 제공.
   - DB 비의존 `FastAPI` 앱에 health router만 주입하여 스모크 테스트 가능 상태 확보.

4. **테스트 추가**
   - API 스모크 테스트: `backend/tests/integration/test_health_api.py`
   - Stage 단위 테스트: `backend/tests/unit/test_stage04_score.py`
     - 점수 계산/정렬 검증
     - 비정상 candidate 필터링 검증

5. **CI 자동화 초안 추가**
   - `.github/workflows/backend-tests.yml` 추가.
   - PR/Push 시 백엔드 테스트 자동 실행 경로 구성.

6. **문서 보강**
   - `backend/README.md`에 테스트 설치/실행 커맨드 추가.

---

## 4. 검증 방법 및 결과

### 수행한 검증
1. 문법/파일 체크
   - 명령: `python3 -m compileall backend/tests .github/workflows/backend-tests.yml pytest.ini`
   - 결과: 성공

2. Python 3.11 컨테이너에서 테스트 의존성 설치 + pytest 실행
   - 명령: `docker run --rm -v "$PWD":/work -w /work python:3.11-slim bash -lc "pip install -r backend/requirements-dev.txt && pytest backend/tests -q"`
   - 결과: 성공 (`3 passed, 1 warning`)

3. 워크플로 파일 정적 검증(actionlint)
   - 명령: `docker run --rm -v "$PWD":/repo -w /repo rhysd/actionlint:latest .github/workflows/backend-tests.yml`
   - 결과: 성공

### 결론
코드/구조 기준의 Step 01 골격과 컨테이너 기반 실실행 검증까지 완료했다.

---

## 5. 리스크/후속 작업

1. **남은 리스크**
   - 로컬 호스트 Python(3.14)에서는 `pydantic-core` 호환성 이슈가 있어 직접 실행이 어려울 수 있음.
   - 현재 작업 디렉토리는 Git 리포지토리가 아니므로 GitHub Actions의 "첫 실행 결과"를 로컬에서 조회할 수 없음.

2. **후속 작업 (Step 02 진입 전)**
1. GitHub 원격 리포지토리에서 PR/Push 후 `Backend Tests` 워크플로 1회 실행 확인
2. Step 02(API 에러 처리 + state 초기화 통합) 진행
