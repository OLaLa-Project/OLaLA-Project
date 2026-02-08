#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

TAG="${1:-}"
BUNDLE_DIR="${2:-}"
FIREBASE_APP_ID="${FIREBASE_APP_ID:-${FIREBASE_ANDROID_APP_ID:-}}"
FIREBASE_GROUPS="${FIREBASE_GROUPS:-beta-testers}"
FIREBASE_TESTERS="${FIREBASE_TESTERS:-}"
FIREBASE_TOKEN="${FIREBASE_TOKEN:-}"

if [ -z "$TAG" ]; then
  echo "[usage] FIREBASE_APP_ID=<app_id> bash scripts/firebase_distribute_beta.sh <tag> [bundle_dir]"
  exit 1
fi

if [ -z "$BUNDLE_DIR" ]; then
  BUNDLE_DIR="$ROOT_DIR/releases/beta/$TAG"
fi

APK_FILE="$BUNDLE_DIR/OLaLA-beta.apk"
NOTES_FILE="$BUNDLE_DIR/RELEASE_NOTES.md"

if [ -z "$FIREBASE_APP_ID" ]; then
  echo "[error] FIREBASE_APP_ID (or FIREBASE_ANDROID_APP_ID) is required"
  exit 1
fi

for f in "$APK_FILE" "$NOTES_FILE"; do
  if [ ! -f "$f" ]; then
    echo "[error] missing file: $f"
    exit 1
  fi
done

LOCAL_CMD=(
  firebase appdistribution:distribute
  "$APK_FILE"
  --app "$FIREBASE_APP_ID"
  --release-notes-file "$NOTES_FILE"
)

if [ -n "$FIREBASE_TESTERS" ]; then
  LOCAL_CMD+=( --testers "$FIREBASE_TESTERS" )
else
  LOCAL_CMD+=( --groups "$FIREBASE_GROUPS" )
fi

if command -v firebase >/dev/null 2>&1; then
  "${LOCAL_CMD[@]}"
elif command -v docker >/dev/null 2>&1; then
  if [ -z "$FIREBASE_TOKEN" ]; then
    echo "[error] firebase CLI 없음. Docker fallback에는 FIREBASE_TOKEN env가 필요합니다."
    exit 1
  fi

  DIST_ARGS=()
  if [ -n "$FIREBASE_TESTERS" ]; then
    DIST_ARGS+=( --testers "$FIREBASE_TESTERS" )
  else
    DIST_ARGS+=( --groups "$FIREBASE_GROUPS" )
  fi

  docker run --rm \
    -e FIREBASE_TOKEN="$FIREBASE_TOKEN" \
    -v "$BUNDLE_DIR:/work" \
    -w /work \
    node:20-bullseye \
    bash -lc "npm install -g firebase-tools >/dev/null 2>&1 && firebase appdistribution:distribute OLaLA-beta.apk --app '$FIREBASE_APP_ID' --release-notes-file RELEASE_NOTES.md ${DIST_ARGS[*]} --token '$FIREBASE_TOKEN'"
else
  echo "[error] firebase CLI/docker 모두 없음"
  exit 1
fi

echo "[ok] firebase app distribution uploaded"
echo "[info] app=$FIREBASE_APP_ID tag=$TAG"
