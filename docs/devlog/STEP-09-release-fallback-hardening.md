# STEP-09 Release Fallback Hardening

- Date: 2026-02-07
- Status: Completed
- Scope: gh/firebase CLI 미설치 환경에서도 Docker fallback으로 배포 실행 가능하도록 릴리스 스크립트 보강

## 목표
원격 배포 단계에서 로컬 CLI 의존성(`gh`, `firebase`)으로 막히지 않도록, Docker 기반 fallback 경로를 공식 지원한다.

## 수행 작업
1. GitHub prerelease 스크립트 보강
- 파일: `scripts/github_prerelease_beta.sh`
- 변경:
  - 로컬 `gh`가 있으면 기존 방식 유지
  - `gh`가 없으면 Docker(`ghcr.io/cli/cli:latest`) fallback 사용
  - fallback 실행 조건: `GH_TOKEN` 필수

2. Firebase distribution 스크립트 보강
- 파일: `scripts/firebase_distribute_beta.sh`
- 변경:
  - 로컬 `firebase`가 있으면 기존 방식 유지
  - `firebase`가 없으면 Docker(`node:20-bullseye` + firebase-tools 설치) fallback 사용
  - fallback 실행 조건: `FIREBASE_TOKEN` 필수

3. 채널 진단 스크립트 보강
- 파일: `scripts/release_channels_doctor.sh`
- 변경:
  - CLI 부재 시에도 `docker + token` 조합이면 준비 완료로 판단
  - 필수 입력값(repo/app id) 점검 강화

4. 문서 반영
- 파일: `docs/BETA_RELEASE.md`
- 변경:
  - Docker fallback과 토큰 기반 실행 조건(`GH_TOKEN`, `FIREBASE_TOKEN`) 명시

## 검증 결과
1. 문법 검증
- `github_prerelease_beta.sh` 통과
- `firebase_distribute_beta.sh` 통과
- `release_channels_doctor.sh` 통과

2. 진단 스크립트 동작 검증
- 기본 환경(토큰 미설정): `NOT ready` 정상
- fallback 조건 주입(더미 토큰/식별자): `ready` 판정 확인

## 기존 대비 변경 사항
- 기존:
  - 로컬 gh/firebase CLI가 없으면 배포 실행 자체 불가
- 변경:
  - Docker fallback 경로로 배포 실행 가능
- 효과:
  - 운영 입력값(repo/app id/token)만 있으면 환경 차이와 무관하게 배포 실행 가능

## 남은 리스크
1. 실제 원격 배포는 미실행
- repo/app id/token은 실제 운영값이 필요

2. Firebase Docker fallback 성능
- 실행 시 `firebase-tools` 설치 시간이 추가됨

## 다음 단계
- STEP-10: GitHub Pre-release 실제 배포 실행 (운영 repo/token 입력 후)
