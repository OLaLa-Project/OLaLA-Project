# REFACTORING STEP 03 - Config 중앙화

**작업 일시:** 2026-02-06  
**기준 문서:** `docs/REFACTORING_PRIORITY.md` (#4 Config 중앙화)

## 1. 목표
- 분산된 `os.getenv`/`os.environ` 호출을 중앙 Settings 계층으로 통합
- 핵심 모듈(DB/LLM/외부 API/앱 설정)에서 설정 값을 단일 진입점으로 관리
- `.env.example` 템플릿 제공

## 2. 주요 변경 사항
### 2.1 중앙 Settings 모듈 추가
- 신규: `backend/app/core/settings.py`
  - `pydantic-settings` 기반 `Settings` 클래스 도입
  - `.env`, `backend/.env` 자동 로드
  - 타입 변환/기본값 중앙화
  - 파생 프로퍼티 제공:
    - `cors_origins_list`
    - `database_url_resolved`

### 2.2 의존성 추가
- 수정: `backend/requirements.txt`
  - `pydantic-settings==2.2.1` 추가

### 2.3 핵심 모듈 설정 참조 통합
- 수정: `backend/app/main.py`
  - CORS 설정을 `settings.cors_origins_list`로 통합

- 수정: `backend/app/api/rag.py`
- 수정: `backend/app/api/dashboard.py`
- 수정: `backend/app/stages/stage03_collect/node.py`
- 수정: `backend/app/orchestrator/embedding/client.py`
  - `OLLAMA_URL`, `OLLAMA_TIMEOUT`, NAVER 키, 임베딩 모델을 `settings`에서 조회

- 수정: `backend/app/orchestrator/database/connection.py`
  - `DatabaseConfig.from_env()` 제거
  - `DatabaseConfig.from_settings()`로 교체
  - DB URL/풀 설정을 중앙화

- 수정: `backend/app/graph/graph.py`
- 수정: `backend/app/services/wiki_usecase.py`
  - `WIKI_EMBEDDINGS_READY` 판단 로직을 `settings.wiki_embeddings_ready`로 통합

- 수정: `backend/app/stages/_shared/slm_client.py`
- 수정: `backend/app/stages/stage09_judge/node.py`
  - SLM/Judge LLM 설정 로딩을 중앙 Settings 기반으로 변경

- 수정: `backend/app/graph/stage_logger.py`
- 수정: `backend/app/stages/stage02_querygen/node.py`
- 수정: `backend/app/orchestrator/database/models/rag.py`
- 수정: `backend/app/orchestrator/database/models/wiki_page.py`
- 수정: `backend/embed_chunks.py`
  - `LOG_DIR`, `YOUTUBE_QUERY_MAX_LEN`, `EMBED_DIM`도 Settings 기반으로 통합
  - 배치 임베딩 스크립트의 OLLAMA/DB timeout 관련 설정도 Settings 기반으로 통합

### 2.4 환경변수 템플릿 추가
- 신규: `backend/.env.example`
  - App/Ollama/Naver/DB/SLM/Judge 필수·주요 변수 샘플 정리

### 2.5 설정 테스트 추가
- 신규: `backend/tests/unit/test_settings.py`
  - CORS 파싱/기본값
  - DB URL 해석 우선순위
  - bool 파싱(`WIKI_EMBEDDINGS_READY`) 검증

## 3. 검증 결과
1. 문법/임포트 검증
   - 명령: `python3 -m compileall backend/app backend/embed_chunks.py backend/tests`
   - 결과: 성공

2. 통합 테스트
   - 명령:  
     `/bin/zsh -lc "docker run --rm -v \"$PWD\":/work -w /work python:3.11-slim bash -lc \"apt-get update >/dev/null && apt-get install -y --no-install-recommends gcc python3-dev >/dev/null && pip install -r backend/requirements-dev.txt && pytest backend/tests -q\""`
   - 결과: `12 passed, 1 warning`

3. 환경변수 직접 호출 제거 점검
   - 명령: `rg -n "os\\.getenv|os\\.environ\\.get|getenv\\(" backend -S`
   - 결과: 매치 없음

## 4. 요청하신 후속 작업 상태
1. 원격 GitHub 리포지토리의 `Backend Tests` 실제 실행 로그 확인  
   - 현재 작업 디렉토리에 `.git` 메타데이터가 없고, 로컬에 `gh` CLI도 없어 run id/실로그 조회는 수행 불가.

2. Step 03(Config 중앙화) 진행  
   - 완료 (본 문서 기준)

## 5. 남은 리스크
- `settings`는 프로세스 시작 시 로드되는 단일 객체이므로, 환경변수 변경 시 프로세스 재시작이 필요.
- 원격 CI 첫 실행 결과(run id) 확인은 Git 메타데이터가 있는 클론 또는 리포지토리 식별자(`owner/repo`)가 필요.
