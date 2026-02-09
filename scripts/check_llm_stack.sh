#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

if [ -f .env.beta ]; then
  # shellcheck disable=SC1091
  source .env.beta
elif [ -f .env.example ]; then
  # shellcheck disable=SC1091
  source .env.example
fi

SLM1_MODEL="${SLM1_MODEL:-}"
SLM2_MODEL="${SLM2_MODEL:-}"
JUDGE_BASE_URL="${JUDGE_BASE_URL:-}"
JUDGE_MODEL="${JUDGE_MODEL:-}"
# Allow common aliases so CI/ops can inject without editing .env files.
JUDGE_API_KEY="${JUDGE_API_KEY:-${OPENAI_API_KEY:-${PPLX_API_KEY:-${PERPLEXITY_API_KEY:-}}}}"
OLLAMA_CONTAINER="${OLLAMA_CONTAINER:-olala-ollama}"

echo "[info] checking llm stack"
echo "[info] SLM1_MODEL=$SLM1_MODEL"
echo "[info] SLM2_MODEL=$SLM2_MODEL"
echo "[info] JUDGE_BASE_URL=$JUDGE_BASE_URL"
echo "[info] JUDGE_MODEL=$JUDGE_MODEL"

FAILED=0
OLLAMA_MODELS=""

if docker ps --format '{{.Names}}' | grep -qx "$OLLAMA_CONTAINER"; then
  OLLAMA_MODELS="$(docker exec "$OLLAMA_CONTAINER" ollama list | awk 'NR>1 {print $1}')"
else
  echo "[warn] ollama container not running: $OLLAMA_CONTAINER"
fi

check_ollama_model() {
  local model_name="$1"
  local label="$2"
  if [ -z "$model_name" ]; then
    echo "[error] $label is empty"
    FAILED=1
    return
  fi
  if [ -z "$OLLAMA_MODELS" ]; then
    echo "[error] cannot verify $label (ollama list unavailable)"
    FAILED=1
    return
  fi
  if echo "$OLLAMA_MODELS" | grep -qx "$model_name"; then
    echo "[ok] $label exists in ollama: $model_name"
  else
    echo "[error] $label missing in ollama: $model_name"
    FAILED=1
  fi
}

check_ollama_model "$SLM1_MODEL" "SLM1_MODEL"
check_ollama_model "$SLM2_MODEL" "SLM2_MODEL"

if echo "$JUDGE_BASE_URL" | grep -qi "ollama"; then
  check_ollama_model "$JUDGE_MODEL" "JUDGE_MODEL(ollama)"
else
  if [ -n "$JUDGE_API_KEY" ]; then
    echo "[ok] JUDGE_API_KEY is set for external judge provider"
  else
    echo "[error] JUDGE_API_KEY is empty for external judge provider"
    FAILED=1
  fi
fi

if [ "$FAILED" -ne 0 ]; then
  echo "[error] llm stack check failed"
  exit 1
fi

echo "[ok] llm stack check passed"
