# STEP-11 Production Hardening and Build Test

- Date: 2026-02-07
- Status: Completed
- Scope: 원격 배포 전, 프로덕션 하드닝 점검 + Android 빌드 재검증

## 목표
배포 단계로 넘어가기 전 필수 운영 게이트(스택/헬스/스모크/성능/릴리스 채널 준비도)를 재검증하고, Android 산출물(APK/AAB)을 다시 빌드해 현재 환경에서 재현 가능한 빌드 경로를 확정한다.

## 수행 작업
1. 베타 스택/헬스 점검
- 실행:
  - `bash scripts/run_beta.sh`
  - `bash scripts/check_stack.sh`
- 결과:
  - `olala-backend` running
  - `olala-wiki-db` healthy
  - `/health` 정상 응답

2. 임베딩 상태 점검
- 실행: `bash scripts/wiki_embeddings_status.sh`
- 결과:
  - `wiki_embeddings_ready=false`
  - `embedded=0`, `missing=1002975`, `coverage_pct=0.00`

3. 프론트-백엔드 스모크 재검증
- 실행: `bash scripts/smoke_mobile_bridge.sh`
- 결과:
  - `/health`, `/v1/issues/today`, `/v1/chat/messages/{issueId}` 정상
  - `/truth/check` reachable(status=405)

4. 릴리스 채널 준비도 재점검
- 실행: `bash scripts/release_channels_doctor.sh beta-20260207 releases/beta/beta-20260207`
- 결과:
  - 번들 파일/체크섬 정상
  - GitHub/Firebase 실제 배포 준비는 미완료(`gh`/`firebase` 및 토큰/식별자 부재)

5. Android 빌드 테스트
- 실행:
  - `bash scripts/check_android_toolchain.sh`
  - `bash scripts/flutter_build_android_env.sh beta apk`
  - `bash scripts/flutter_build_android_env.sh beta aab`
- 결과:
  - 로컬 `flutter/java/adb`는 없음
  - Docker fallback 빌드 경로는 정상
  - APK/AAB 빌드 성공

6. 릴리스 번들 최신화
- 실행: `bash scripts/prepare_beta_release_bundle.sh beta-20260207`
- 결과:
  - 최신 산출물/체크섬으로 `releases/beta/beta-20260207/` 갱신

7. 성능 기준 리포트 갱신
- 실행: `bash scripts/wiki_db_perf_check.sh 코로나`
- 산출물: `docs/perf/wiki-db-perf-20260207-054305.txt`

## 산출물
1. Android 산출물
- APK: `apps/flutter/build/app/outputs/flutter-apk/app-release.apk` (약 51MB)
- AAB: `apps/flutter/build/app/outputs/bundle/release/app-release.aab` (약 43MB)

2. 번들 체크섬
- 파일: `releases/beta/beta-20260207/SHA256SUMS.txt`
- APK SHA256: `6aa160a1158e943a17f0b319eef0c065b5c4e1d3c944dd89d8771fdda5884b8b`
- AAB SHA256: `3da050337748a0579cb4a31571ab97f3a20adf96119f4ee1bcc1b329df742cdd`

## 기존 대비 변경 사항
- 기존:
  - STEP-10 기준으로 임베딩 정책은 수립되었지만, 최신 환경 기준 하드닝/빌드 재검증 로그가 부족
- 변경:
  - 운영 게이트(헬스/스모크/릴리스진단/성능) 재검증 완료
  - APK/AAB를 현재 시점에서 재빌드하고 번들/체크섬 갱신
- 효과:
  - 배포 직전 품질 상태를 최신 산출물 기준으로 재확인 가능

## 검증 결과 요약
- 스택/헬스: PASS
- 모바일 브리지 스모크: PASS
- Android 툴체인(도커 fallback): PASS
- Android APK 빌드: PASS
- Android AAB 빌드: PASS
- 릴리스 채널 준비도: NOT READY (운영값 미입력)

## 남은 리스크
1. 임베딩 미생성
- `embedding` 0건 상태로 vector 검색 경로는 아직 비활성 수준

2. 배포 채널 운영값 부재
- `GITHUB_REPO`, `GH_TOKEN`, `FIREBASE_APP_ID`, `FIREBASE_TOKEN` 미설정

3. Docker 빌드 시간
- Docker Flutter는 매 빌드마다 SDK/NDK 설치 시간이 반복되어 빌드 지연 가능

4. 실기기 설치 스모크 미수행
- 현재 단계는 산출물 생성 검증까지 완료, 실제 단말 설치/기동 검증은 별도 필요

## 다음 단계
- STEP-12: 원격 배포 제외 기준 최종 마감
  - (선택 A) 임베딩 실백필 실행 후 `WIKI_EMBEDDINGS_READY=true` 전환
  - (선택 B) 원격 배포 입력값(repo/token/app id)만 주입하여 배포 준비 상태를 `READY`로 전환
