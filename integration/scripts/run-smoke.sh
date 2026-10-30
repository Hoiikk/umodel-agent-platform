#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
ENV_FILE="$ROOT_DIR/../rms/.env"
PYTHON="$ROOT_DIR/../connector/.venv/bin/python"

test -f "$ENV_FILE" || { echo "Missing local env file: $ENV_FILE" >&2; exit 1; }
test -x "$PYTHON" || { echo "Missing assistant virtual environment: $PYTHON" >&2; exit 1; }

set -a
# The file is local-only and created from rms/.env.example.
. "$ENV_FILE"
set +a

export UMODEL_ADDR="${UMODEL_ADDR:-http://127.0.0.1:8080}"
export UMODEL_WORKSPACE="${UMODEL_WORKSPACE:-rms}"
export RMS_MYSQL_ENDPOINT="${RMS_MYSQL_ENDPOINT:-127.0.0.1:3308}"

curl --fail --silent --show-error "$UMODEL_ADDR/healthz" >/dev/null
if ! curl --fail --silent "$UMODEL_ADDR/api/v1/workspaces/$UMODEL_WORKSPACE" >/dev/null; then
  curl --fail --silent --show-error \
    -X POST "$UMODEL_ADDR/api/v1/workspaces" \
    -H 'content-type: application/json' \
    --data "{\"id\":\"$UMODEL_WORKSPACE\",\"name\":\"RMS integration smoke\"}" >/dev/null
fi
curl --fail --silent --show-error \
  -X POST "$UMODEL_ADDR/api/v1/umodel/$UMODEL_WORKSPACE/import" \
  -H 'content-type: application/json' \
  --data '{"path":"/model-packs/rms"}' >/dev/null

PYTHONPATH="$ROOT_DIR/../connector/src" "$PYTHON" "$ROOT_DIR/scripts/smoke.py"
