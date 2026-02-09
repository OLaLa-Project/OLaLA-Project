# OLaLA Flutter App

## Environment Profiles
`dart-define-from-file` 기준으로 환경을 분리합니다.

- `config/env/dev.json`
- `config/env/beta.json`
- `config/env/prod.json`

기본 키:
- `APP_ENV`
- `API_BASE`
- `WS_BASE`

## Run
프로덕션 루트에서 실행:

```bash
bash scripts/flutter_run_env.sh dev
bash scripts/flutter_run_env.sh dev_android
bash scripts/flutter_run_env.sh dev_emulator
bash scripts/flutter_run_env.sh beta
bash scripts/flutter_run_env.sh prod
```

디바이스 지정:

```bash
bash scripts/flutter_run_env.sh dev emulator-5554
```

## Android Build (Release)
프로덕션 루트에서 실행:

```bash
bash scripts/flutter_build_android_env.sh beta apk
bash scripts/flutter_build_android_env.sh beta aab
bash scripts/flutter_build_android_env.sh prod apk
bash scripts/flutter_build_android_env.sh prod aab
```

## Network Notes
- Android 에뮬레이터 로컬 백엔드 접속은 보통 `10.0.2.2`를 사용합니다.
- 실기기는 백엔드가 열린 동일 네트워크 IP를 사용해야 합니다.
- 현재 `dev.json`은 로컬 웹/데스크톱 기준값(`127.0.0.1`)으로 설정되어 있습니다.
- Android Studio/에뮬레이터에서 로컬 백엔드 테스트는 `dev_android.json`을 사용하세요.
  - Run args 예시: `--dart-define-from-file=config/env/dev_android.json`
- Windows+WSL 조합에서 `10.0.2.2:8080`이 타임아웃 나는 경우:
  - `adb reverse tcp:8080 tcp:8080`를 켠 뒤 `dev_emulator.json`(127.0.0.1)을 사용하세요.
