#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

if [ ! -f .env.beta ]; then
  cp .env.example .env.beta
  echo "[info] .env.beta 생성 완료 (.env.example 기반)"
fi

mkdir -p .runtime/pgdata .runtime/ollama

docker compose -f infra/docker/docker-compose.beta.yml up -d --build

echo "[ok] beta stack started"
echo "[hint] health: bash scripts/check_stack.sh"
