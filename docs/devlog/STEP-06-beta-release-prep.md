# STEP-06 Beta Release Preparation

- Date: 2026-02-07
- Status: Completed
- Scope: 베타 릴리스 패키징 및 배포 경로(GitHub/Firebase) 자동화 준비

## 목표
STEP-05에서 생성한 APK/AAB를 즉시 배포 가능한 형태로 패키징하고, GitHub pre-release 또는 Firebase 무료 배포를 실행할 수 있는 자동화 경로를 준비한다.

## 수행 작업
1. 베타 릴리스 번들 스크립트 추가
- 파일: `scripts/prepare_beta_release_bundle.sh`
- 기능:
  - 빌드 산출물 존재 확인(APK/AAB)
  - `releases/beta/<tag>/` 생성
  - 산출물 복사(`OLaLA-beta.apk`, `OLaLA-beta.aab`)
  - `SHA256SUMS.txt` 생성
  - `RELEASE_NOTES.md` 템플릿 자동 생성

2. GitHub pre-release 업로드 스크립트 추가
- 파일: `scripts/github_prerelease_beta.sh`
- 기능:
  - `gh` CLI 존재/파일 유효성 검증
  - APK/AAB + 릴리스 노트를 prerelease로 업로드

3. Firebase App Distribution 업로드 스크립트 추가
- 파일: `scripts/firebase_distribute_beta.sh`
- 기능:
  - `firebase` CLI 존재/환경변수 검증
  - APK + 릴리스 노트 업로드
  - `FIREBASE_GROUPS` 또는 `FIREBASE_TESTERS` 선택 지원

4. 문서/가이드 반영
- 파일:
  - `docs/BETA_RELEASE.md`
  - `docs/NEXT_ACTIONS.md`
  - `README.md`
- 내용:
  - 빌드 -> 번들 -> 배포까지 실행 순서 표준화

5. 실제 번들 생성 검증
- 실행: `bash scripts/prepare_beta_release_bundle.sh beta-20260207`
- 결과:
  - 생성 경로: `releases/beta/beta-20260207/`
  - 파일:
    - `OLaLA-beta.apk`
    - `OLaLA-beta.aab`
    - `SHA256SUMS.txt`
    - `RELEASE_NOTES.md`

## 기존 대비 변경 사항
- 기존:
  - APK/AAB 생성 후 수동으로 파일 정리/업로드 필요
- 변경:
  - 번들 생성 + 두 배포 채널(GitHub/Firebase) 스크립트화
- 효과:
  - 운영자가 레포/앱ID만 있으면 즉시 베타 배포 수행 가능

## 검증 결과
1. 신규 스크립트 문법
- `prepare_beta_release_bundle.sh` 통과
- `github_prerelease_beta.sh` 통과
- `firebase_distribute_beta.sh` 통과

2. 번들 생성
- `releases/beta/beta-20260207` 생성 확인
- `SHA256SUMS.txt` 생성 확인

3. STEP-05 연동
- Docker fallback 빌드 경로로 생성된 APK/AAB가 번들 단계에서 정상 처리됨

## 남은 리스크
1. 실제 원격 배포 미실행
- GitHub org/repo 정보 미입력
- Firebase app id/CLI 인증 미입력

2. 서명 정책
- Android release가 debug signing 기반이므로 공개 스토어 배포 전 keystore 전환 필요

## 다음 단계
- STEP-07: 실제 채널 선택 후 원격 베타 배포 실행
  - Option A: GitHub pre-release 생성
  - Option B: Firebase App Distribution 업로드
