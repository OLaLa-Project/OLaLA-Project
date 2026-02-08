#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

TAG="${1:-}"
REPO="${2:-}"
BUNDLE_DIR="${3:-}"

if [ -z "$TAG" ] || [ -z "$REPO" ]; then
  echo "[usage] bash scripts/github_prerelease_beta.sh <tag> <owner/repo> [bundle_dir]"
  exit 1
fi

if [ -z "$BUNDLE_DIR" ]; then
  BUNDLE_DIR="$ROOT_DIR/releases/beta/$TAG"
fi

APK_FILE="$BUNDLE_DIR/OLaLA-beta.apk"
AAB_FILE="$BUNDLE_DIR/OLaLA-beta.aab"
NOTES_FILE="$BUNDLE_DIR/RELEASE_NOTES.md"

for f in "$APK_FILE" "$AAB_FILE" "$NOTES_FILE"; do
  if [ ! -f "$f" ]; then
    echo "[error] missing file: $f"
    exit 1
  fi
done

if command -v gh >/dev/null 2>&1; then
  gh release create "$TAG" \
    "$APK_FILE#OLaLA Beta APK" \
    "$AAB_FILE#OLaLA Beta AAB" \
    --repo "$REPO" \
    --prerelease \
    --title "OLaLA Beta $TAG" \
    --notes-file "$NOTES_FILE"
elif command -v docker >/dev/null 2>&1; then
  if [ -z "${GH_TOKEN:-}" ]; then
    echo "[error] gh CLI 없음. Docker fallback에는 GH_TOKEN env가 필요합니다."
    exit 1
  fi

  docker run --rm \
    -e GH_TOKEN \
    -v "$BUNDLE_DIR:/work" \
    -w /work \
    ghcr.io/cli/cli:latest \
    release create "$TAG" \
    "OLaLA-beta.apk#OLaLA Beta APK" \
    "OLaLA-beta.aab#OLaLA Beta AAB" \
    --repo "$REPO" \
    --prerelease \
    --title "OLaLA Beta $TAG" \
    --notes-file "RELEASE_NOTES.md"
else
  echo "[error] gh CLI/docker 모두 없음"
  exit 1
fi

echo "[ok] github prerelease created"
echo "[info] repo=$REPO tag=$TAG"
