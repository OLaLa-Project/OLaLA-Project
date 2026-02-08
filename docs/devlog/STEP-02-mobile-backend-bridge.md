# STEP-02 Mobile-Backend Bridge

- Date: 2026-02-07
- Status: Completed
- Scope: Flutter(olala_frontend)와 백엔드 간 실연결을 위한 모바일 호환 브리지 구현

## 목표
Flutter UI 동작을 깨지 않으면서 기존 백엔드에 최소 변경으로 모바일 호환 API/WS 경로를 제공하고, 검증 기능을 Mock 중심에서 API 우선 구조로 전환한다.

## 수행 작업
1. 모바일 브리지 API 추가
- 파일: `services/backend/app/api/mobile_bridge.py`
- 추가 엔드포인트:
  - `GET /v1/issues/today`
  - `GET /v1/chat/messages/{issue_id}`
  - `WS /v1/chat/{issue_id}`
- 이벤트 지원:
  - client -> server: `join`, `message.create`, `reaction.toggle`
  - server -> client: `message.ack`, `message.created`, `reaction.updated`, `presence`, `error`

2. FastAPI 라우터 등록
- 파일: `services/backend/app/main.py`
- `mobile_router` import + `app.include_router(mobile_router)` 추가

3. Flutter 검증 저장소 추가
- 파일: `apps/flutter/lib/features/verify/repository/api_verify_repository.dart`
- `POST /truth/check` 호출 후 Flutter `VerificationResult`로 매핑
- 예외 시 fallback 저장소 호출 가능 구조

4. Flutter 결과 컨트롤러 연결 전환
- 파일: `apps/flutter/lib/features/verify/presentation/result_controller.dart`
- 기존:
  - `MockVerifyRepository()` 단독
- 변경:
  - `ApiVerifyRepository(baseUrl: ApiEndpoints.apiBase, fallback: MockVerifyRepository())`

## 기존 대비 변경 사항
- 기존: 채팅/이슈는 로컬 도구 서버 전제, 검증은 Mock 저장소 중심
- 변경: 백엔드가 Flutter가 기대하는 `/v1` 경로를 직접 제공, 검증은 API 우선
- 효과:
  - UI 플로우를 유지한 채 서버 연동 전환
  - 네트워크 실패 시 Mock fallback으로 개발 안정성 확보

## 검증 결과
1. 라우터 등록 확인
- `app/main.py`에서 `mobile_router` import 및 include 확인

2. 엔드포인트 선언 확인
- `mobile_bridge.py` 내 `/issues/today`, `/chat/messages/{issue_id}`, `/chat/{issue_id}` 선언 확인

3. Flutter 연결 확인
- `result_controller.dart`가 `ApiVerifyRepository`를 사용하도록 변경 확인
- fallback이 `MockVerifyRepository`로 설정된 것 확인

4. 정적 문법 확인
- 신규 Python 파일 문법 컴파일 체크 통과

## 남은 리스크
1. 인메모리 채팅 상태
- 현재 채팅 저장소가 인메모리 기반이라 프로세스 재기동 시 데이터 유실
- 베타에는 허용 가능하나 프로덕션에서는 DB 영속화 필요

2. 스케일 리스크
- 멀티 인스턴스 배포 시 room/state 공유가 되지 않음
- Redis/pubsub 또는 DB 기반 세션 동기화 필요

3. 계약 적합성 추가 검증 필요
- 실제 Flutter 화면에서 WS reconnect/ack 시나리오 E2E 확인 필요

## 다음 단계
- STEP-03: 베타 스택 실제 기동(`run_beta.sh`) + 헬스체크 + wiki DB 적재 실행 검증
