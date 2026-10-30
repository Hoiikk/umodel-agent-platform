#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
LAB_DIR="$ROOT_DIR/integration"
RMS_DIR="$ROOT_DIR/rms"
ASSISTANT_DIR="$ROOT_DIR/connector"
UMODEL_DIR="$ROOT_DIR/third_party/UnifiedModel"
ENV_FILE="$RMS_DIR/.env"

test -f "$ENV_FILE" || { echo "Missing local env file: $ENV_FILE" >&2; exit 1; }
test -x "$ASSISTANT_DIR/.venv/bin/python" || { echo "Missing Connector virtual environment" >&2; exit 1; }

cleanup() {
  if [[ "${KEEP_STACK:-0}" != "1" ]]; then
    docker compose --env-file "$ENV_FILE" -f "$LAB_DIR/compose.yaml" down
  fi
}
trap cleanup EXIT

(cd "$RMS_DIR" && npm ci && npm run ci)
(cd "$ASSISTANT_DIR" && .venv/bin/python -m pytest && .venv/bin/python -m ruff check . && .venv/bin/python -m build --no-isolation)
(cd "$UMODEL_DIR" && make check-env)

docker compose --env-file "$ENV_FILE" -f "$LAB_DIR/compose.yaml" up -d --build
"$LAB_DIR/scripts/run-smoke.sh"
