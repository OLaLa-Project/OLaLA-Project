# STEP-23 Android Studio Local Backend (dev_android)

- Date: 2026-02-09
- Status: Completed
- Scope: Android Studio/에뮬레이터에서 로컬 백엔드(8080)로 동작 확인 가능하도록 Flutter env 프로파일 추가

## 목표/범위
- Android 에뮬레이터에서 로컬 백엔드에 접근할 때 `127.0.0.1` 대신 `10.0.2.2`를 사용하도록 설정을 제공한다.
- Android Studio에서 바로 실행(run)할 때도 동일 설정을 적용할 수 있게 한다.

## 수행 작업
1. dev_android env 추가
- 파일: `apps/flutter/config/env/dev_android.json`
- 값:
  - `API_BASE=http://10.0.2.2:8080/v1`
  - `WS_BASE=ws://10.0.2.2:8080/v1`
  - `APP_ENV=dev`

2. 실행 스크립트 지원 추가
- 파일: `scripts/flutter_run_env.sh`
- 변경: `dev_android` env 허용 및 사용법 업데이트

3. 문서 업데이트
- 파일: `apps/flutter/README.md`
- 변경: `dev_android` 실행 예시 및 Android Studio run args 안내 추가

## 변경 사항(기존 대비)
- 기존: `dev.json`이 `127.0.0.1` 기반이라 Android 에뮬레이터에서 로컬 백엔드 접속 실패 가능
- 변경: `dev_android.json`으로 에뮬레이터 표준 주소(`10.0.2.2`)를 제공해 즉시 테스트 가능

## 검증 결과
- (수동) Android Studio에서 `--dart-define-from-file=config/env/dev_android.json`로 실행 후
  - `/v1/issues/today` 로드
  - `/v1/truth/check` 호출
  - `/v1/chat/{issue_id}` WebSocket 연결 확인 예정

## 남은 리스크
- 실기기 테스트 시 `10.0.2.2`는 동작하지 않음(동일 네트워크의 PC IP로 별도 env 필요)
- Windows 방화벽/보안 정책에 따라 8080 포트 접근이 차단될 수 있음

## 다음 단계
- 실기기용 `dev_device.json`(LAN IP 기반) 프로파일 추가(필요 시)
- Android Studio 실행 스모크 체크리스트를 스크립트/문서로 표준화

