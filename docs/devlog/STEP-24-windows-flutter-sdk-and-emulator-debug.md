# STEP-24 Windows Flutter SDK and Emulator Debug

- Date: 2026-02-09
- Status: In progress
- Scope: Windows 환경에서 Flutter SDK/Android cmdline-tools 부트스트랩, Emulator 실행, `flutter run` 디버그 연결 안정화

## 목표
Android Studio(또는 CLI)에서 Android Emulator로 Flutter 앱을 실행하고, 로컬 베타 백엔드(`:8080`)에 연결해 실제 동작을 확인한다.

## 수행 작업
1. Flutter SDK 설치(Windows)
- 위치: `C:\Users\alber\sdks\flutter` (stable channel)
- 확인: `flutter --version`, `flutter doctor`

2. Android SDK Command-line Tools 설치
- 배경: `flutter doctor`에서 `cmdline-tools component is missing`로 Android toolchain 이슈 발생
- 조치: cmdline-tools 최신(zip)을 SDK root에 설치
- 자동화 스크립트(신규):
  - `scripts/windows/install_android_cmdline_tools.ps1`

3. Android 라이선스 수락 자동화
- `flutter doctor --android-licenses` 실행이 필요
- 자동화 스크립트(신규):
  - `scripts/windows/flutter_accept_android_licenses.ps1`

4. Emulator 실행 및 Android Studio 프로젝트 오픈
- AVD 확인: `Medium_Phone_API_36.1`
- Emulator 기동 후 `adb devices`에서 `emulator-5554 device` 확인
- Android Studio로 `apps/flutter` 오픈(Windows GUI)

5. Flutter Android 로컬 SDK 경로 정리(로컬)
- 파일: `apps/flutter/android/local.properties`
- 변경: Windows `sdk.dir`, `flutter.sdk`로 갱신
  - 주의: `local.properties`는 로컬 환경 파일 성격(일반적으로 git ignore)이라 팀 공유 대상이 아님

6. Emulator 실행 자동화 스크립트 추가(신규)
- 파일: `scripts/windows/flutter_run_android_emulator.ps1`
- 내용: `--dart-define-from-file=config/env/dev_android.json`로 실행(Emulator host loopback = `10.0.2.2`)

## 관찰된 이슈(블로커)
1. `flutter run` 디버그 프로토콜 연결 실패
- 증상: APK 빌드/설치 및 앱 런치까지는 성공하지만, Flutter tool이 VM service에 attach 실패로 종료
- 에러:
  - `Error connecting to the service protocol: failed to connect to http://127.0.0.1:<port>/<token>/ ... Connection closed before full header was received`
- 참고: logcat 상에서는 VM service가 `http://127.0.0.1:<vm_port>/<token>/`로 listen 중임

2. ADB/Emulator 상태 불안정
- `adb kill-server` 이후 `adb devices`가 `offline`으로 남는 경우가 있어, Flutter attach/forwarding 디버깅을 방해함

## 다음 단계
1. 디버그 attach 안정화
- `flutter run -v`로 `adb forward`/port 사용 흐름 확인
- `adb forward --list`와 logcat의 VM service 포트/토큰이 일치하는지 점검
- 필요 시 Emulator 재기동(offline 상태 해소) 후 재시도

2. 동작 확인 우회로(디버그가 막힐 때)
- `flutter run --release` 또는 Android Studio에서 release/프로파일 빌드로 앱 실행 후,
  - `dev_android.json` 기반(`10.0.2.2:8080`)으로 API 호출이 정상인지 확인

