# STEP-15 Firebase Readiness Preflight (No Deploy)

- Date: 2026-02-07
- Status: Completed
- Scope: Firebase/GitHub 베타 배포 전 사전검증(무배포)

## 목표
실제 업로드 없이 베타 배포 채널(Firebase App Distribution, GitHub Release)의 준비 상태를 점검하고,
남은 블로커를 명확히 식별한다.

## 수행 작업
1. Firebase 인증 상태 점검
- 실행: `firebase login:list`
- 결과: `No authorized accounts` (인증 계정 없음)

2. Firebase 프로젝트 접근 점검
- 실행: `firebase projects:list`
- 결과: 인증 실패로 프로젝트 목록 조회 불가

3. 릴리스 채널 종합 점검
- 실행: `bash scripts/release_channels_doctor.sh beta-20260207`
- 결과 요약:
  - 번들 파일(APK/AAB/SHA/노트): 정상
  - 체크섬 검증: 통과
  - GitHub 채널: `gh` CLI 없음, `GITHUB_REPO` 미설정
  - Firebase 채널: CLI는 설치됨, 인증 미완료, `FIREBASE_APP_ID` 미설정

4. 운영 상태 교차 확인
- wiki 임베딩 상태:
  - `embedded=1002975`
  - `missing=0`
  - `coverage_pct=100.00`
- `.env.beta`:
  - `WIKI_EMBEDDINGS_READY=true`
- docker compose 서비스 상태:
  - backend / wiki-db / ollama 모두 실행 중

## 기존 대비 변경 사항
- 기존:
  - Firebase SDK와 앱 식별자 정합성은 맞춰졌지만 배포 채널 준비 상태가 불명확
- 변경:
  - 무배포 사전검증으로 실제 블로커를 명확히 식별
  - 배포 외 프로덕션 핵심 상태(스택 가동, 임베딩 100%) 재확인 완료

## 현재 리스크
1. Firebase 인증 미완료
- `firebase login` 미완료로 App Distribution 실행 불가

2. 배포 채널 환경변수 미설정
- `FIREBASE_APP_ID` 및 `GITHUB_REPO` 미설정 상태

3. GitHub CLI 미설치
- GitHub 릴리스 자동화 경로(`gh`) 미사용 상태

4. Android namespace 미정렬(기술부채)
- `applicationId=com.olala.beta.one`, `namespace=com.example.olala_frontend`
- 즉시 장애는 아니나 장기 유지보수 리스크

## 다음 단계
- STEP-16: 배포 채널 활성화 준비(배포 실행 전)
  - Firebase 로그인(`firebase login`) 및 프로젝트 선택
  - `.env.beta` 또는 실행 env에 `FIREBASE_APP_ID=1:288602230546:android:02db672cc8e0b4b3572dcb` 설정
  - GitHub 경로 선택:
    - A안: `gh` 설치 + 로그인
    - B안: `GH_TOKEN` + Docker fallback
  - 이후 사용자 승인 시 실제 업로드 단계 진행
