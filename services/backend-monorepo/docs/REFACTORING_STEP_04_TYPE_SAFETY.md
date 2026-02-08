# REFACTORING STEP 04 - Type Safety 강화

**작업 일시:** 2026-02-06  
**기준 문서:** `docs/REFACTORING_PRIORITY.md` (#2 Type Safety 강화)

## 1. 목표
- Stage/Graph/Service 경계의 타입 계약을 명시적으로 강화
- Stage 이름/상태 키 오타를 정적 검사에서 더 빨리 탐지
- 최소 mypy 규칙을 도입해 핵심 모듈 타입 체크를 CI에 포함

## 2. 주요 변경 사항
### 2.1 GraphState 및 Stage 타입 계약 강화
- 수정: `backend/app/graph/state.py`
  - `StageName`, `PublicStageName`, `RegistryStageName` Literal 타입 추가
  - `SearchQuery` TypedDict 추가
  - `STAGE_ORDER` 상수 및 `normalize_stage_name()` 추가
  - `GraphState`에 누락되어 있던 핵심 필드 명시:
    - `normalize_mode`, `include_full_outputs`, `stage_full_outputs`, `querygen_prompt_used`, `querygen_claims` 등

### 2.2 핵심 실행 경로 시그니처 정리
- 수정: `backend/app/graph/graph.py`
  - `StageFn`/`AsyncStageFn` 타입 alias 도입
  - `STAGE_SEQUENCE`, `STAGE_OUTPUT_KEYS`를 stage literal 기반으로 타입 명시
  - `run_stage_sequence()`에서 start/end stage 정규화 적용
    - `stage03_collect` alias 처리:
      - start 기준 -> `stage03_wiki`
      - end 기준 -> `stage03_merge`

- 수정: `backend/app/orchestrator/stage_manager.py`
  - registry 키 타입을 `RegistryStageName`으로 제한

- 수정: `backend/app/orchestrator/service.py`
  - `_init_state()` 반환 타입을 `GraphState`로 명시
  - stream 시그니처를 `AsyncGenerator[str, None]`로 명시
  - `Citation.source_type`를 Literal 호환 타입으로 정규화

### 2.3 요청 스키마 타입 계약 보강
- 수정: `backend/app/core/schemas.py`
  - `TruthCheckRequest.start_stage/end_stage`를 `PublicStageName`으로 교체
  - API 입력 단계 이름과 내부 실행 단계 이름 사이 타입 계약 일치

### 2.4 mypy 최소 규칙 + CI 통합
- 수정: `backend/requirements-dev.txt`
  - `mypy==1.15.0` 추가
  - `types-requests==2.32.0.20241016` 추가

- 신규: `backend/mypy.ini`
  - 핵심 모듈 strict 규칙 유지
  - `follow_imports = skip` 제거 (import 추적 정상화)

- 수정: `.github/workflows/backend-tests.yml`
  - `Run Mypy (Backend App)` 스텝으로 확장
  - 검사 범위: 핵심 파일 4개 -> `app` 전체

### 2.5 보조 타입 오류 정리 (mypy 연쇄 오류 대응)
- 수정: `backend/app/orchestrator/__init__.py`
  - `__all__` 타입 명시

- 수정: `backend/app/stages/_shared/guardrails.py`
  - JSON 파싱 함수 반환 타입을 `dict[str, Any]` 기준으로 정리
  - non-dict JSON 루트에 대한 방어 로직 추가

### 2.6 테스트 추가
- 신규: `backend/tests/unit/test_stage_name_normalization.py`
  - stage alias 정규화(`stage03_collect` start/end) 동작 검증

## 3. 검증 결과
1. 문법/임포트 검증
   - 명령: `python3 -m compileall backend/app backend/tests backend/embed_chunks.py`
   - 결과: 성공

2. 타입 검사 (백엔드 앱 전체)
   - 명령: `cd backend && mypy --config-file mypy.ini app`
   - 결과: `Success: no issues found in 72 source files`

3. 테스트
   - 명령: `pytest backend/tests -q`
   - 결과: `17 passed, 1 warning`

4. CI 워크플로 정적 검증
   - 명령:
     `/bin/zsh -lc "docker run --rm -v \"$PWD\":/repo -w /repo rhysd/actionlint:latest .github/workflows/backend-tests.yml"`
   - 결과: 성공

## 4. 완료 기준(DoD) 충족 여부
- 핵심 모듈 타입 검사 통과: **충족**
- 오타/누락 필드 정적 탐지 가능성 강화: **충족**
  - Stage 이름 literal + stage alias 정규화 + GraphState 키 명시

## 5. 남은 리스크
- (해소) mypy 적용 범위가 핵심 모듈 중심이던 문제:
  - CI/로컬 검사 범위를 `app` 전체로 확장해 전체 모듈 타입 회귀를 탐지하도록 변경.
- (해소) `follow_imports = skip`로 인한 외곽 모듈 타입 일관성 공백:
  - `backend/mypy.ini`에서 제거하여 import 체인 기반 검사 정상화.
- (잔여) `ignore_missing_imports = True` 정책은 유지 중:
  - 외부 라이브러리 type stub 품질 이슈를 단계적으로 정리하기 위한 타협.
