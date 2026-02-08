# OLaLA Beta Release Guide

## 1) Build Artifacts
Run from the production root:

```bash
bash scripts/smoke_mobile_bridge.sh
bash scripts/check_android_toolchain.sh
bash scripts/flutter_build_android_env.sh beta apk
bash scripts/flutter_build_android_env.sh beta aab
```

`flutter`가 로컬에 없으면 `flutter_build_android_env.sh`는 Docker fallback(`ghcr.io/cirruslabs/flutter:stable`)을 사용합니다.

## 2) Prepare Release Bundle
```bash
bash scripts/prepare_beta_release_bundle.sh beta-20260207
```

Outputs:
- `releases/beta/<tag>/OLaLA-beta.apk`
- `releases/beta/<tag>/OLaLA-beta.aab`
- `releases/beta/<tag>/SHA256SUMS.txt`
- `releases/beta/<tag>/RELEASE_NOTES.md`

## 3) GitHub Pre-release (Option A)
사전 진단:
```bash
bash scripts/release_channels_doctor.sh <tag> releases/beta/<tag>
```

```bash
bash scripts/github_prerelease_beta.sh <tag> <owner/repo>
```

참고:
- `gh` CLI가 없으면 Docker fallback을 사용하며 `GH_TOKEN` 환경변수가 필요합니다.

Example:
```bash
bash scripts/github_prerelease_beta.sh beta-20260207 my-org/olala
```

## 4) Firebase App Distribution (Option B, Free Tier)
사전 진단:
```bash
bash scripts/release_channels_doctor.sh <tag> releases/beta/<tag>
```

```bash
FIREBASE_APP_ID=<app_id> bash scripts/firebase_distribute_beta.sh <tag>
```

참고:
- `firebase` CLI가 없으면 Docker fallback을 사용하며 `FIREBASE_TOKEN` 환경변수가 필요합니다.

Optional:
- `FIREBASE_GROUPS=beta-testers`
- `FIREBASE_TESTERS=email1@example.com,email2@example.com`

## 5) Current Constraints
- Android release build is currently signed with debug config.
- For public store release, switch to production keystore signing before publishing.
