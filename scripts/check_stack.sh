#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

FAILED=0

if ! docker compose -f infra/docker/docker-compose.beta.yml ps; then
  echo "[error] docker compose ps failed"
  FAILED=1
fi

if ! curl -fsS "http://127.0.0.1:${BACKEND_PORT:-8080}/health"; then
  echo "[error] backend health check failed"
  FAILED=1
else
  echo
fi

if ! bash scripts/check_llm_stack.sh; then
  echo "[error] llm stack preflight failed"
  FAILED=1
fi

if [ "$FAILED" -ne 0 ]; then
  echo "[error] stack check failed"
  exit 1
fi

echo "[ok] stack check passed"
