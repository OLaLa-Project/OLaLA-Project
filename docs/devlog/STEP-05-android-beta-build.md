# STEP-05 Android Beta Build

- Date: 2026-02-07
- Status: Completed
- Scope: Android 베타 산출물(APK/AAB) 생성 및 빌드 리스크 해소

## 목표
`beta` 환경으로 Android `apk`/`aab` 산출물을 생성하고, 빌드가 막히던 툴체인 리스크를 해소한다.

## 수행 작업
1. 초기 빌드 차단 확인
- 실행:
  - `bash scripts/flutter_build_android_env.sh beta apk`
  - `bash scripts/flutter_build_android_env.sh beta aab`
- 초기 결과:
  - `flutter: command not found`

2. 원인 확인
- `flutter`, `java`, `adb` 로컬 실행 경로 부재
- 이 상태에서는 로컬(Android SDK 기반) 빌드 불가

3. 리스크 해소 전략 적용
- Docker 기반 Flutter 툴체인(`ghcr.io/cirruslabs/flutter:stable`) 도입
- `scripts/flutter_build_android_env.sh`를 보강하여:
  - 로컬 `flutter`가 있으면 로컬 빌드
  - 로컬 `flutter`가 없으면 Docker fallback 빌드 자동 수행

4. 사전점검 스크립트 개선
- 파일: `scripts/check_android_toolchain.sh`
- 개선 내용:
  - 로컬 툴체인 점검 + Docker fallback 점검
  - 로컬 미설치여도 Docker fallback 가능 시 `android build toolchain ready` 반환

5. 실제 베타 산출물 생성(해결 검증)
- Docker Flutter로 실행:
  - `flutter build apk --release --dart-define-from-file=config/env/beta.json`
  - `flutter build appbundle --release --dart-define-from-file=config/env/beta.json`
- 결과:
  - `app-release.apk` 생성 완료
  - `app-release.aab` 생성 완료

## 산출물
1. APK
- 경로: `apps/flutter/build/app/outputs/flutter-apk/app-release.apk`
- 크기: 약 51MB
- SHA256: `d76bf0d61961cae049c107e59e4a5d764d86d012ac638ab32997256520f80603`

2. AAB
- 경로: `apps/flutter/build/app/outputs/bundle/release/app-release.aab`
- 크기: 약 43MB
- SHA256: `a93a0288cabb917b711fcba23733a9715dd9e838de22131e29cb88a5bd475ec5`

## 기존 대비 변경 사항
- 기존:
  - 로컬 Flutter/Java/ADB 미설치 시 빌드 완전 차단
- 변경:
  - Docker fallback 경로로 빌드 가능
  - 툴체인 점검이 로컬+Docker를 모두 판단하도록 개선
- 효과:
  - 환경 의존성 리스크를 우회하여 베타 산출물 생성 가능 상태 확보

## 검증 결과
1. 빌드 스크립트 문법
- `flutter_build_android_env.sh` 문법 통과

2. 툴체인 점검
- 로컬 경로는 여전히 미설치
- Docker fallback 점검 성공 (`android build toolchain ready`)

3. 산출물 생성
- APK/AAB 모두 생성 성공

## 남은 리스크
1. 실기기 smoke test 미수행
- 현재 작업 환경에서 `adb` 로컬 연동이 없어 설치/기동 실검증 미수행

2. 릴리스 서명 체계
- 현재 Android `release`는 debug signing 구성
- 실제 배포용 keystore/서명 정책은 다음 단계에서 분리 필요

## 다음 단계
- STEP-06: 베타 릴리스 패키징 및 배포 경로 준비(GitHub Pre-release / Firebase 무료 경로)
