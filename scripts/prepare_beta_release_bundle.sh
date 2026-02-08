#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
APP_DIR="$ROOT_DIR/apps/flutter"

TAG="${1:-beta-$(date +%Y%m%d-%H%M%S)}"
OUT_DIR="$ROOT_DIR/releases/beta/$TAG"

APK_SRC="$APP_DIR/build/app/outputs/flutter-apk/app-release.apk"
AAB_SRC="$APP_DIR/build/app/outputs/bundle/release/app-release.aab"
APK_OUT="$OUT_DIR/OLaLA-beta.apk"
AAB_OUT="$OUT_DIR/OLaLA-beta.aab"

if [ ! -f "$APK_SRC" ]; then
  echo "[error] missing apk: $APK_SRC"
  echo "[hint] run: bash scripts/flutter_build_android_env.sh beta apk"
  exit 1
fi

if [ ! -f "$AAB_SRC" ]; then
  echo "[error] missing aab: $AAB_SRC"
  echo "[hint] run: bash scripts/flutter_build_android_env.sh beta aab"
  exit 1
fi

mkdir -p "$OUT_DIR"
cp -f "$APK_SRC" "$APK_OUT"
cp -f "$AAB_SRC" "$AAB_OUT"

(
  cd "$OUT_DIR"
  sha256sum "$(basename "$APK_OUT")" "$(basename "$AAB_OUT")" > SHA256SUMS.txt
)

cat > "$OUT_DIR/RELEASE_NOTES.md" <<EOF
# OLaLA Beta $TAG

## Artifacts
- OLaLA-beta.apk
- OLaLA-beta.aab
- SHA256SUMS.txt

## Build
- Environment: beta
- Command:
  - bash scripts/flutter_build_android_env.sh beta apk
  - bash scripts/flutter_build_android_env.sh beta aab

## Notes
- Android release build currently uses debug signing config.
- Replace with production keystore before public store deployment.
EOF

echo "[ok] beta release bundle prepared"
echo "[info] tag=$TAG"
echo "[info] dir=$OUT_DIR"
echo "[info] files:"
ls -lh "$OUT_DIR"
