# STEP-14 Firebase Lowercase Package Sync

- Date: 2026-02-07
- Status: Completed
- Scope: Firebase Android 앱 식별자(패키지) 소문자 통일 및 빌드 검증

## 목표
Firebase 등록 앱 패키지(`com.olala.beta.one`)와 Android `applicationId`를 정확히 일치시켜,
연동 실패 리스크를 제거하고 소문자 패키지 정책으로 안정성을 높인다.

## 수행 작업
1. Firebase 설정 파일 교체
- 소스: `C:\\Users\\alber\\Downloads\\google-services.json`
- 대상: `apps/flutter/android/app/google-services.json`
- 교체 후 `package_name` 확인: `com.olala.beta.one`

2. Android applicationId 정렬
- 파일: `apps/flutter/android/app/build.gradle.kts`
- 변경 전: `applicationId = "OLaLA.beta.one"`
- 변경 후: `applicationId = "com.olala.beta.one"`

3. 정합성 검증
- `google-services.json`의 `package_name`과 `applicationId` 일치 확인
- 결과: 모두 `com.olala.beta.one`

4. 빌드 검증
- 실행: `bash scripts/flutter_build_android_env.sh beta apk`
- 결과: release APK 빌드 성공
- 산출물: `apps/flutter/build/app/outputs/flutter-apk/app-release.apk`

## 기존 대비 변경 사항
- 기존:
  - Firebase 설정은 대문자 패키지(`OLaLA.beta.one`) 기반
  - 호환성 리스크 존재
- 변경:
  - Firebase/앱 패키지를 소문자(`com.olala.beta.one`)로 정렬
  - 빌드 성공으로 적용 상태 검증 완료

## 현재 리스크
1. Android namespace 미정렬
- 현재 `namespace`는 `com.example.olala_frontend`
- 즉시 장애는 없지만 장기 유지보수 관점에서 정렬 권장

2. Firebase 배포 인증/프로젝트 선택 미검증
- CLI 설치는 완료됐으나 `firebase login`/`firebase use` 상태는 아직 미점검

## 다음 단계
- STEP-15: Firebase 베타 배포 사전검증(무배포)
  - `firebase login:list` 확인
  - `firebase projects:list` / 프로젝트 바인딩 확인
  - App Distribution 테스터 그룹/릴리스 노트 템플릿 점검
