#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
APP_DIR="$ROOT_DIR/apps/flutter"

ENV_NAME="${1:-dev}"
DEVICE_ID="${2:-}"

	case "$ENV_NAME" in
	  dev|dev_android|dev_emulator|beta|prod)
	    ;;
	  *)
	    echo "[error] invalid env: $ENV_NAME"
	    echo "[usage] bash scripts/flutter_run_env.sh <dev|dev_android|dev_emulator|beta|prod> [device_id]"
	    exit 1
	    ;;
	esac

ENV_FILE="$APP_DIR/config/env/${ENV_NAME}.json"
if [ ! -f "$ENV_FILE" ]; then
  echo "[error] env file not found: $ENV_FILE"
  exit 1
fi

CMD=(flutter run --dart-define-from-file="$ENV_FILE")
if [ -n "$DEVICE_ID" ]; then
  CMD+=( -d "$DEVICE_ID" )
fi

echo "[info] env=$ENV_NAME"
echo "[info] define=$ENV_FILE"
(
  cd "$APP_DIR"
  "${CMD[@]}"
)
