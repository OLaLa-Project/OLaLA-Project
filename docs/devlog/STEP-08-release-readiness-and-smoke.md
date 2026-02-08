# STEP-08 Release Readiness and Smoke

- Date: 2026-02-07
- Status: Completed
- Scope: 프론트-백엔드 통합 스모크 검증 + 배포 채널 실행 전 진단 체계 확립

## 목표
원격 배포(GitHub/Firebase)를 바로 실행하지 않는 조건에서, 실제 프로덕션 릴리스 직전 품질 게이트를 고정하고 차단 요인을 명확히 진단할 수 있도록 한다.

## 수행 작업
1. 통합 스모크 스크립트 추가
- 파일: `scripts/smoke_mobile_bridge.sh`
- 검증 항목:
  - `GET /health`
  - `GET /v1/issues/today`
  - `GET /v1/chat/messages/{issueId}`
  - `/truth/check` 엔드포인트 reachability(상태코드 기준)

2. 배포 채널 진단 스크립트 추가
- 파일: `scripts/release_channels_doctor.sh`
- 진단 항목:
  - 번들 파일 존재(APK/AAB/SHA256/노트)
  - 체크섬 검증
  - GitHub CLI/auth/repo 준비상태
  - Firebase CLI/auth/app id 준비상태

3. 베타 스택 재기동 및 스모크 실행
- 실행:
  - `bash scripts/run_beta.sh`
  - `bash scripts/smoke_mobile_bridge.sh`
- 결과:
  - 백엔드/모바일 브리지 핵심 경로 정상 응답 확인

4. 릴리스 채널 진단 실행
- 실행:
  - `bash scripts/release_channels_doctor.sh beta-20260207 releases/beta/beta-20260207`
- 결과:
  - 번들/체크섬 정상
  - `gh`/`firebase` CLI 미설치 및 인증/배포 식별자 미설정으로 원격 배포는 대기 상태

5. 문서/체크리스트 반영
- 파일:
  - `docs/NEXT_ACTIONS.md`
  - `docs/BETA_RELEASE.md`
  - `docs/STEP_BY_STEP.md`
- 반영 내용:
  - 스모크/배포진단 단계를 표준 실행 순서로 고정
  - Firebase 경로는 "정리 완료"로 상태 반영

## 검증 결과
1. 스모크 테스트
- `/health` 정상
- `/v1/issues/today` 정상
- `/v1/chat/messages/{issueId}` 정상
- `/truth/check` reachable 확인

2. 릴리스 번들 상태
- `releases/beta/beta-20260207/` 내 APK/AAB/체크섬/노트 존재 및 체크섬 일치

3. 배포 채널 준비도
- GitHub: CLI 없음, repo 미지정
- Firebase: CLI 없음, app id 미지정

## 기존 대비 변경 사항
- 기존:
  - 원격 배포 직전 실패 가능성을 사전에 기계적으로 검증할 수 있는 스크립트 부재
- 변경:
  - 스모크 + 채널 진단 스크립트 도입
- 효과:
  - 배포 가능/불가능 상태를 즉시 판단 가능
  - 원격 배포 전 장애 지점을 선제 제거 가능

## 남은 리스크
1. 원격 배포 미실행
- 현재 단계는 실행 전 준비 검증까지 완료, 실제 배포는 대기

2. 배포 도구/인증
- `gh`/`firebase` CLI 및 인증이 준비되지 않으면 자동 배포 실행 불가

## 다음 단계
- STEP-09: GitHub Pre-release 실제 배포 (repo 정보 제공 후 실행)
