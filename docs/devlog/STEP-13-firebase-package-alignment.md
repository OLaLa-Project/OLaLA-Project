# STEP-13 Firebase Package Alignment and Build Validation

- Date: 2026-02-07
- Status: Completed
- Scope: Firebase Android 패키지 매칭 정합성 복구 및 빌드 검증

## 목표
Firebase Android 설정에서 `google-services.json`의 패키지명과 앱 `applicationId`를 일치시켜,
Google Services 처리 실패(`No matching client found for package name`) 가능성을 제거한다.

## 수행 작업
1. Firebase CLI 설치 및 동작 확인
- 실행: `npm install -g firebase-tools`
- 확인: `firebase --version` -> `15.5.1`

2. 정합성 점검
- `google-services.json` 패키지명 확인: `OLaLA.beta.one`
- Flutter Android `applicationId` 확인: `com.example.olala_frontend`
- 결론: 빌드/런타임 Firebase 초기화 실패 가능 상태

3. Android 앱 식별자 정렬
- 파일: `apps/flutter/android/app/build.gradle.kts`
- 변경 전: `applicationId = "com.example.olala_frontend"`
- 변경 후: `applicationId = "OLaLA.beta.one"`

4. 빌드 검증
- 직접 `./gradlew :app:processDebugGoogleServices` 실행 시도 중, 호스트 셸의 `JAVA_HOME` 미설정 확인
- 표준 경로로 전환:
  - `bash scripts/check_android_toolchain.sh`
  - `bash scripts/flutter_build_android_env.sh beta apk`
- 결과: `app-release.apk` 빌드 성공

## 기존 대비 변경 사항
- 기존:
  - Firebase Gradle 플러그인/SDK는 추가됐지만 패키지 불일치로 연동 실패 리스크 존재
- 변경:
  - `applicationId`를 Firebase 설정 파일과 일치시켜 매칭 리스크 제거
  - Docker 기반 표준 빌드 경로에서 APK 생성 성공으로 설정 유효성 검증 완료

## 현재 리스크
1. 패키지명 대소문자 정책 리스크
- 현재 패키지명 `OLaLA.beta.one`은 관례상 비권장(일반적으로 소문자 사용)
- 향후 Play 배포/외부 도구 호환성 이슈가 발생하면, 소문자 패키지로 재등록 + 새 `google-services.json` 재발급 필요

2. Android `namespace`와 `applicationId` 불일치 유지
- 현재 `namespace`는 `com.example.olala_frontend`
- 즉시 장애는 아니지만, 장기적으로 코드/패키지 관리 복잡성 증가 가능

3. Firebase 프로젝트 인증 미완료 가능성
- CLI 설치는 완료됐지만, 실제 배포 전 `firebase login` 및 프로젝트 바인딩(`firebase use`) 확인 필요

## 다음 단계
- STEP-14: Firebase 베타 배포 사전검증(무배포)
  - `firebase login:list` 상태 확인
  - Firebase 프로젝트 alias/ID 바인딩 점검
  - App Distribution 대상 그룹/테스터 정의 점검
  - 실제 업로드 명령은 사용자 승인 후 실행
