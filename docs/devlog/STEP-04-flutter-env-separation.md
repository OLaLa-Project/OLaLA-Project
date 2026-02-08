# STEP-04 Flutter Env Separation

- Date: 2026-02-07
- Status: Completed
- Scope: Flutter 실행/빌드 환경을 `dev/beta/prod`로 분리하고, `dart-define` 주입을 표준화

## 목표
Flutter UI를 깨지 않으면서 환경값(API/WS)을 코드에 하드코딩하지 않고, 실행/빌드 시점에 일관되게 주입되도록 구조를 고정한다.

## 수행 작업
1. 앱 환경 모델 추가
- 파일: `apps/flutter/lib/app/env.dart`
- 내용:
  - `AppEnvironment`(`dev`, `beta`, `prod`) enum 추가
  - `APP_ENV`, `API_BASE`, `WS_BASE`를 `String.fromEnvironment`로 읽도록 추가
  - 환경 미지정 시 fallback 규칙 추가
    - `prod` 기본
    - trailing slash 정규화
    - `API_BASE` 기준 `WS_BASE` 자동 추론

2. API 엔드포인트 계층 연결 변경
- 파일: `apps/flutter/lib/shared/network/api_endpoints.dart`
- 변경:
  - 기존 내부 상수 기반 분기 제거
  - `AppEnv.apiBase`, `AppEnv.wsBase` 사용으로 통일

3. 환경 파일 분리
- 디렉토리: `apps/flutter/config/env`
- 파일:
  - `dev.json`
  - `beta.json`
  - `prod.json`
- 목적:
  - `--dart-define-from-file` 방식으로 환경별 주입 실수 방지

4. 실행/빌드 스크립트 추가
- 파일:
  - `scripts/flutter_run_env.sh`
  - `scripts/flutter_build_android_env.sh`
- 기능:
  - env 파라미터 검증(`dev|beta|prod`, 빌드는 `beta|prod`)
  - env 파일 존재 검증
  - `flutter run/build ... --dart-define-from-file=<env.json>` 강제

5. 문서 업데이트
- 파일:
  - `apps/flutter/README.md`
  - `docs/NEXT_ACTIONS.md`
  - `README.md`
  - `docs/STEP_BY_STEP.md`
  - `docs/devlog/INDEX.md`
- 내용:
  - 환경별 실행/빌드 커맨드 표준화
  - 네트워크 주의사항(에뮬레이터/실기기) 명시

## 기존 대비 변경 사항
- 기존:
  - `API_BASE`, `WS_BASE`를 커맨드에서 직접 입력하는 방식 중심
  - 환경별 실행 명령 표준이 문서/스크립트로 고정되지 않음
- 변경:
  - `config/env/*.json` + 실행/빌드 스크립트 기반 표준 경로 확립
  - 코드에서 환경 해석 책임을 `AppEnv`로 일원화
- 효과:
  - 베타/프로덕션 빌드 시 잘못된 API 주입 가능성 감소
  - Flutter UI는 기존 리포지토리 호출 구조를 유지하며 환경만 치환

## 검증 결과
1. 스크립트 문법
- `bash -n scripts/flutter_run_env.sh` 통과
- `bash -n scripts/flutter_build_android_env.sh` 통과

2. 환경 파일 존재
- `dev.json`, `beta.json`, `prod.json` 존재 확인

3. 코드 참조 연결
- `ApiEndpoints`가 `AppEnv`를 참조하도록 변경 확인

## 남은 리스크
1. 실제 Flutter 런타임 검증 미완료
- 현재 작업 환경에 `flutter` 바이너리가 없어 `flutter run/build` 실실행 검증은 미수행

2. beta/prod API 도메인 확정 필요
- `beta.json`/`prod.json`의 도메인은 운영 실제 값으로 치환 필요

3. Android 실기기 네트워크 변수
- 실기기 테스트 시 `127.0.0.1` 대신 네트워크 접근 가능한 호스트 IP로 설정 필요

## 다음 단계
- STEP-05: Android 베타 산출물(APK/AAB) 실제 생성 및 산출물 검증(설치/기동/기본 플로우 smoke test)
