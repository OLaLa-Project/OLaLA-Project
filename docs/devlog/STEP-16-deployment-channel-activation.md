# STEP-16 Deployment Channel Activation Prep

- Date: 2026-02-07
- Status: Completed
- Scope: Firebase 베타 배포 채널 활성화 준비(무배포)

## 목표
Firebase App Distribution 경로를 실제 업로드 직전 상태로 정렬하고,
남은 블로커를 채널별로 분리해 명확히 관리한다.

## 수행 작업
1. Firebase 인증/프로젝트 접근 검증
- `firebase login:list` 결과: `Logged in as albert08120131@gmail.com`
- `firebase projects:list` 결과: `olala-beta-1` 조회 성공

2. 배포용 환경변수 반영
- 파일: `.env.beta`
- 추가: `FIREBASE_APP_ID=1:288602230546:android:02db672cc8e0b4b3572dcb`

3. 릴리스 채널 진단 재실행
- 실행: `FIREBASE_APP_ID=... bash scripts/release_channels_doctor.sh beta-20260207`
- (권한 상승 환경 기준) 결과:
  - 번들 파일/체크섬: 통과
  - Firebase 채널: `cli found`, `auth ready`, `FIREBASE_APP_ID set` (준비 완료)
  - GitHub 채널: `gh cli missing`, `GITHUB_REPO not set` (미준비)

4. Firebase 프로젝트 바인딩 확인 시도
- `firebase use olala-beta-1` 실행 시도
- 결과: 현재 디렉토리가 Firebase Hosting/Functions 프로젝트 구조가 아니어서 거부됨
- 판단: App Distribution 스크립트는 `FIREBASE_APP_ID` 직접 지정 방식이므로 필수 블로커 아님

## 기존 대비 변경 사항
- 기존:
  - Firebase 로그인/프로젝트 접근 불가
  - `FIREBASE_APP_ID` 미설정
- 변경:
  - Firebase 인증 완료 및 프로젝트 조회 가능
  - 배포용 앱 ID 환경값 반영
  - Firebase 채널 단독 기준으로는 배포 실행 가능한 상태 확보

## 현재 리스크
1. GitHub 릴리스 채널 미준비
- `gh` CLI 미설치, `GITHUB_REPO` 미설정
- Firebase-only 전략에는 영향 없음

2. 스크립트 실행 환경 차이
- 샌드박스 환경에서는 Firebase auth 체크가 오탐 실패할 수 있음
- 실제 실행은 사용자 셸/권한 상승 환경 기준으로 판단 필요

3. Android namespace 기술부채
- `applicationId=com.olala.beta.one`, `namespace=com.example.olala_frontend`
- 즉시 장애는 아니지만 추후 정렬 권장

## 다음 단계
- STEP-17: Firebase 베타 배포 실행(사용자 승인 후)
  - `bash scripts/firebase_distribute_beta.sh beta-20260207 /mnt/c/Users/alber/Desktop/OLaLA-Production-v2/releases/beta/beta-20260207`
  - 필요시 `FIREBASE_GROUPS` 또는 `FIREBASE_TESTERS` 지정
