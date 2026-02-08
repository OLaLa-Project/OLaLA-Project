#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
APP_DIR="$ROOT_DIR/apps/flutter"
FLUTTER_DOCKER_IMAGE="${FLUTTER_DOCKER_IMAGE:-ghcr.io/cirruslabs/flutter:stable}"

build_ready=0

check_cmd() {
  local name="$1"
  if command -v "$name" >/dev/null 2>&1; then
    echo "[ok] $name: $(command -v "$name")"
    return 0
  else
    echo "[missing] $name"
    return 1
  fi
}

echo "[info] checking Android toolchain"
if check_cmd flutter; then :; fi
if check_cmd java; then :; fi
check_cmd adb || true

if command -v flutter >/dev/null 2>&1; then
  build_ready=1
  echo "[info] flutter --version"
  flutter --version | head -n 2 || true

  if [ -d "$APP_DIR" ]; then
    echo "[info] flutter doctor -v (apps/flutter)"
    (
      cd "$APP_DIR"
      flutter doctor -v || true
    )
  fi
fi

if [ "$build_ready" -eq 0 ] && command -v docker >/dev/null 2>&1; then
  echo "[info] checking docker fallback image=$FLUTTER_DOCKER_IMAGE"
  if docker run --rm "$FLUTTER_DOCKER_IMAGE" flutter --version >/dev/null 2>&1; then
    build_ready=1
    echo "[ok] docker flutter fallback available"
  else
    echo "[missing] docker flutter fallback unavailable"
  fi
fi

if command -v adb >/dev/null 2>&1; then
  echo "[info] adb devices"
  adb devices || true
fi

if [ "$build_ready" -eq 0 ]; then
  echo "[result] android build toolchain not ready"
  exit 1
fi

echo "[result] android build toolchain ready"
