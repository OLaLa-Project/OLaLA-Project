#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

set +e
docker compose -f infra/docker/docker-compose.beta.yml ps
curl -fsS "http://127.0.0.1:${BACKEND_PORT:-8080}/health" && echo
set -e
