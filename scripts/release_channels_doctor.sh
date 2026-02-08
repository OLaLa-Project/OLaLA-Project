#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

TAG="${1:-beta-20260207}"
BUNDLE_DIR="${2:-$ROOT_DIR/releases/beta/$TAG}"

APK_FILE="$BUNDLE_DIR/OLaLA-beta.apk"
AAB_FILE="$BUNDLE_DIR/OLaLA-beta.aab"
SHA_FILE="$BUNDLE_DIR/SHA256SUMS.txt"
NOTES_FILE="$BUNDLE_DIR/RELEASE_NOTES.md"

GITHUB_REPO="${GITHUB_REPO:-}"
FIREBASE_APP_ID="${FIREBASE_APP_ID:-${FIREBASE_ANDROID_APP_ID:-}}"
GH_TOKEN="${GH_TOKEN:-}"
FIREBASE_TOKEN="${FIREBASE_TOKEN:-}"

FAILED=0

ok() { echo "[ok] $*"; }
warn() { echo "[warn] $*"; }
bad() { echo "[error] $*"; FAILED=1; }

echo "[info] tag=$TAG"
echo "[info] bundle_dir=$BUNDLE_DIR"

echo "[1/5] bundle files check"
for f in "$APK_FILE" "$AAB_FILE" "$SHA_FILE" "$NOTES_FILE"; do
  if [ -f "$f" ]; then
    ok "exists: $f"
  else
    bad "missing: $f"
  fi
done

echo "[2/5] checksum verify"
if [ -f "$SHA_FILE" ]; then
  if (cd "$BUNDLE_DIR" && sha256sum -c "$(basename "$SHA_FILE")" >/dev/null 2>&1); then
    ok "sha256 verify passed"
  else
    bad "sha256 verify failed"
  fi
else
  bad "cannot verify checksum: SHA256SUMS.txt missing"
fi

echo "[3/5] github prerelease readiness"
if command -v gh >/dev/null 2>&1; then
  ok "gh cli found"
  if gh auth status >/dev/null 2>&1; then
    ok "gh auth ready"
  else
    if [ -n "$GH_TOKEN" ]; then
      ok "gh auth 미설정이지만 GH_TOKEN으로 fallback 가능"
    else
      bad "gh auth missing (run: gh auth login or set GH_TOKEN)"
    fi
  fi
else
  if command -v docker >/dev/null 2>&1 && [ -n "$GH_TOKEN" ]; then
    ok "gh cli 없음. docker+GH_TOKEN fallback 가능"
  else
    bad "gh cli missing (or use docker fallback with GH_TOKEN)"
  fi
fi
if [ -n "$GITHUB_REPO" ]; then
  ok "GITHUB_REPO set: $GITHUB_REPO"
else
  warn "GITHUB_REPO not set (set env or pass repo to github_prerelease_beta.sh)"
fi

echo "[4/5] firebase distribution readiness"
if command -v firebase >/dev/null 2>&1; then
  ok "firebase cli found"
  if firebase login:list >/dev/null 2>&1; then
    ok "firebase auth ready"
  else
    if [ -n "$FIREBASE_TOKEN" ]; then
      ok "firebase auth 미설정이지만 FIREBASE_TOKEN으로 fallback 가능"
    else
      bad "firebase auth missing (run: firebase login or set FIREBASE_TOKEN)"
    fi
  fi
else
  if command -v docker >/dev/null 2>&1 && [ -n "$FIREBASE_TOKEN" ]; then
    ok "firebase cli 없음. docker+FIREBASE_TOKEN fallback 가능"
  else
    bad "firebase cli missing (or use docker fallback with FIREBASE_TOKEN)"
  fi
fi
if [ -n "$FIREBASE_APP_ID" ]; then
  ok "FIREBASE_APP_ID set"
else
  warn "FIREBASE_APP_ID not set"
fi

echo "[5/5] next commands"
echo "GitHub:   bash scripts/github_prerelease_beta.sh $TAG <owner/repo> $BUNDLE_DIR"
echo "Firebase: FIREBASE_APP_ID=<app_id> bash scripts/firebase_distribute_beta.sh $TAG $BUNDLE_DIR"

if [ "$FAILED" -ne 0 ]; then
  echo "[result] release channels NOT ready"
  exit 1
fi

echo "[result] release channels ready"
