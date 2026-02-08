#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
APP_DIR="$ROOT_DIR/apps/flutter"

ENV_NAME="${1:-beta}"
ARTIFACT="${2:-apk}"
FLUTTER_DOCKER_IMAGE="${FLUTTER_DOCKER_IMAGE:-ghcr.io/cirruslabs/flutter:stable}"

case "$ENV_NAME" in
  beta|prod)
    ;;
  *)
    echo "[error] android release build supports: beta|prod"
    echo "[usage] bash scripts/flutter_build_android_env.sh <beta|prod> [apk|aab]"
    exit 1
    ;;
esac

case "$ARTIFACT" in
  apk|aab)
    ;;
  *)
    echo "[error] invalid artifact: $ARTIFACT"
    echo "[usage] bash scripts/flutter_build_android_env.sh <beta|prod> [apk|aab]"
    exit 1
    ;;
esac

ENV_FILE="$APP_DIR/config/env/${ENV_NAME}.json"
if [ ! -f "$ENV_FILE" ]; then
  echo "[error] env file not found: $ENV_FILE"
  exit 1
fi

if [ "$ARTIFACT" = "apk" ]; then
  BUILD_ARGS=(build apk --release --dart-define-from-file="config/env/${ENV_NAME}.json")
else
  BUILD_ARGS=(build appbundle --release --dart-define-from-file="config/env/${ENV_NAME}.json")
fi

echo "[info] env=$ENV_NAME"
echo "[info] artifact=$ARTIFACT"
echo "[info] define=$ENV_FILE"

if command -v flutter >/dev/null 2>&1; then
  echo "[info] build mode=local flutter"
  (
    cd "$APP_DIR"
    flutter "${BUILD_ARGS[@]}"
  )
  exit 0
fi

if command -v docker >/dev/null 2>&1; then
  echo "[info] build mode=docker flutter image=$FLUTTER_DOCKER_IMAGE"
  docker run --rm \
    -v "$APP_DIR:/workspace" \
    -w /workspace \
    "$FLUTTER_DOCKER_IMAGE" \
    bash -lc "flutter ${BUILD_ARGS[*]}"
  exit 0
fi

echo "[error] flutter not found and docker not available"
exit 1
