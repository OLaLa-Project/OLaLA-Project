# OLaLA Refactoring Step 00 - 분석 및 실행 단계 정리

**작성일:** 2026-02-06  
**기준 문서:** `docs/REFACTORING_PRIORITY.md`  
**목적:** 우선순위 문서를 실제 실행 가능한 단계로 재정렬하고, 이후 단계별 산출물 규칙을 고정한다.

---

## 1. 분석 결과 요약

`REFACTORING_PRIORITY.md`의 핵심 방향은 타당하다.

1. 테스트 선행
2. 타입 안정성 강화
3. 운영 안정성(에러 처리, 설정 중앙화, 실행 경로 정리)
4. 고급 기능(체크포인트, 레이트리밋, 관측성)
5. 대규모 구조 변경(Async 통일, 리네이밍)

다만 실제 작업 순서에서는 Quick Win과 리스크 완화 단계를 앞에 배치하는 것이 효율적이다.

---

## 2. 실행 단계(확정안)

## Step 00 (현재 단계) - 분석/설계
- 목표: 리팩토링 단계, 산출물 형식, 검증 기준 확정
- 코드 변경: 없음
- 산출물: 본 문서

## Step 01 - 테스트 프레임워크 최소 골격 구축 (#1)
- 목표: `pytest`, `pytest-asyncio`, `pytest-cov` 기반 실행 가능 상태 확보
- 범위:
1. 테스트 디렉토리 표준화 (`backend/tests/unit`, `backend/tests/integration`)
2. `conftest.py` 기본 fixture 구성
3. 최소 1개 API 스모크 테스트, 최소 1개 Stage 단위 테스트
- 완료 기준(DoD):
1. `pytest`가 에러 없이 실행됨
2. 실패/성공 케이스가 구분되는 테스트 최소 2개 확보

## Step 02 - API 에러 처리 정비 (#3) + 실행 경로 통합 (#5)
- 목표: 실패 시 일관된 응답과 로그를 보장하고 중복 초기화 경로 제거
- 범위:
1. `/truth/check` 및 stream 경로 예외 처리 표준화
2. `service.py` state 초기화 함수 통합
3. 에러 코드/메시지 스키마 정리
- 완료 기준(DoD):
1. 파이프라인 내부 예외 발생 시 API 500/에러 payload 규격 일치
2. state 초기화 중복 제거

## Step 03 - Config 중앙화 (#4)
- 목표: 분산된 `os.getenv`를 단일 Settings 계층으로 통합
- 범위:
1. `config.py`(또는 `core/settings.py`) 추가
2. 핵심 환경변수(LLM, DB, 외부 API) 타입 검증
3. `.env.example` 정비
- 완료 기준(DoD):
1. 필수 env 누락 시 앱 시작 단계에서 명확히 실패
2. 핵심 모듈에서 직접 `os.getenv` 호출 제거

## Step 04 - Type Safety 강화 (#2)
- 목표: Stage/Graph/Service 경계의 타입 계약 강화
- 범위:
1. `GraphState` 정리 및 stage I/O 타입 명시
2. 주요 함수 시그니처 타입 명시
3. 최소 mypy/pyright 기본 규칙 적용
- 완료 기준(DoD):
1. 핵심 모듈 타입 검사 통과
2. 오타/누락 필드가 정적 검사에서 탐지됨

## Step 05 - Checkpointing 도입 (#6)
- 목표: 중단 복구 가능성 확보
- 범위:
1. LangGraph checkpointer 연결
2. `thread_id`/resume 전략 정의
3. checkpoint 정리 정책(TTL) 정의
- 완료 기준(DoD):
1. 중간 stage 실패 후 재개 시나리오 검증

## Step 06 - External API Rate Limiting (#7)
- 목표: Naver/DDG 호출량 제어 및 429 내성 강화
- 범위:
1. limiter + retry 정책 도입
2. timeout/retry/backoff 표준화
- 완료 기준(DoD):
1. burst 요청에서 과호출 없이 정상 처리

## Step 07 - Observability 기본 세트 (#8)
- 목표: 운영 지표/로그 추적 기반 확보
- 범위:
1. stage latency, error count, external API success ratio
2. 추적 가능한 request/trace id 연결
- 완료 기준(DoD):
1. 최소 메트릭과 구조화 로그로 병목/실패 stage 확인 가능

## Step 08 - Stage Async 통일 (#9)
- 목표: sync/async 혼합 구조를 단계적으로 통일
- 범위:
1. I/O 중심 stage부터 async 순차 전환
2. 이벤트 루프 충돌 지점 제거
- 완료 기준(DoD):
1. 기존 기능 회귀 없이 async 경로 안정 동작

## Step 09 - Gateway 리네이밍 (#10)
- 목표: 네이밍/책임 명확화
- 범위:
1. 디렉토리/모듈명 변경
2. import 경로 일괄 정리
- 완료 기준(DoD):
1. 전 경로 import 깨짐 없이 동작

---

## 3. 단계 간 의존성

1. Step 01 완료 전에는 Step 04/08 진행 금지
2. Step 02는 Step 01 이후 즉시 진행 (빠른 안정성 확보)
3. Step 03은 Step 02 이후 진행 (에러/초기화 경로 고정 후 설정 통합)
4. Step 08/09는 마지막에 진행 (변경량/회귀 리스크 큼)

---

## 4. 단계별 문서 산출 규칙

각 단계 완료 시 아래 패턴으로 문서를 추가한다.

- 파일명: `docs/REFACTORING_STEP_XX_<SHORT_TITLE>.md`
- 필수 섹션:
1. 배경/목표
2. 변경 파일 목록
3. 핵심 변경 내용
4. 검증 방법 및 결과
5. 리스크/후속 작업

예시:
- `docs/REFACTORING_STEP_01_TEST_FOUNDATION.md`
- `docs/REFACTORING_STEP_02_ERROR_HANDLING_AND_STATE_INIT.md`

---

## 5. 이번 단계 변경 내역

1. 추가 파일: `docs/REFACTORING_STEP_00_ANALYSIS.md`
2. 소스 코드 변경: 없음

