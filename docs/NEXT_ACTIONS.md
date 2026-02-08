# Next Actions (즉시 실행 순서)

1. `cp .env.example .env.beta`
2. `bash scripts/run_beta.sh`
3. `bash scripts/import_wiki_db.sh`
4. `bash scripts/check_stack.sh`
5. 임베딩 현황 확인
   - `bash scripts/wiki_embeddings_status.sh`
6. 임베딩 배치 백필(bootstrap)
   - 내부 ollama를 함께 띄울 때: `OLALA_START_OLLAMA=1 bash scripts/wiki_embeddings_backfill.sh --batch-size 64 --report-every 10 --timeout-sec 120 --sleep-ms 150`
   - 외부 OLLAMA_URL 사용 시: `bash scripts/wiki_embeddings_backfill.sh --batch-size 64 --report-every 10 --timeout-sec 120 --sleep-ms 150`
7. 임베딩 중단/재개(필요 시)
   - 중단: `bash scripts/wiki_embeddings_stop.sh`
   - 재개: `bash scripts/wiki_embeddings_resume.sh`
8. 임베딩 완료 후 ready 전환
   - `.env.beta`에서 `WIKI_EMBEDDINGS_READY=true`
   - `bash scripts/run_beta.sh`
9. 프론트-백엔드 스모크 테스트
   - `bash scripts/smoke_mobile_bridge.sh`
10. Android 툴체인 점검
   - `bash scripts/check_android_toolchain.sh`
11. Android release 산출물
   - `bash scripts/flutter_build_android_env.sh beta apk`
   - `bash scripts/flutter_build_android_env.sh beta aab`
12. 베타 릴리스 번들 생성
   - `bash scripts/prepare_beta_release_bundle.sh <tag>`
13. 배포 채널 진단
   - `bash scripts/release_channels_doctor.sh <tag> <bundle_dir>`
14. 배포(선택)
   - GitHub pre-release:
     - `bash scripts/github_prerelease_beta.sh <tag> <owner/repo>`
   - Firebase App Distribution:
     - `FIREBASE_APP_ID=<app_id> bash scripts/firebase_distribute_beta.sh <tag>`

## 대안: 직접 dart-define 사용
- Web: `flutter run -d chrome --dart-define-from-file=config/env/dev.json`
- Android: `flutter run -d <device_id> --dart-define-from-file=config/env/beta.json`

## 모바일 실기기 빌드 시
- Android 에뮬레이터: `10.0.2.2`
- USB 연결 실기기: 같은 네트워크의 WSL 호스트 IP 사용
