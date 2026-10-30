#!/usr/bin/env bash
set -euo pipefail

: "${DEPLOY_PATH:?DEPLOY_PATH is required}"
: "${IMAGE_TAG:?IMAGE_TAG is required}"

deployment_dir="$DEPLOY_PATH/deployment"
release_env="$deployment_dir/release.env"

test -f "$deployment_dir/.env" || {
  echo "Missing $deployment_dir/.env; create it from .env.example on the deployment host." >&2
  exit 1
}

cat > "$release_env" <<EOF
RMS_IMAGE=ghcr.io/hoiikk/umodel-agent-platform-rms:${IMAGE_TAG}
UMODEL_IMAGE=ghcr.io/hoiikk/umodel-agent-platform-umodel:${IMAGE_TAG}
EOF

docker compose --env-file "$deployment_dir/.env" --env-file "$release_env" -f "$deployment_dir/compose.yaml" pull
docker compose --env-file "$deployment_dir/.env" --env-file "$release_env" -f "$deployment_dir/compose.yaml" up -d --remove-orphans

for attempt in $(seq 1 30); do
  if curl --fail --silent --show-error http://127.0.0.1:3001/healthz >/dev/null; then
    echo "Deployment healthy: ${IMAGE_TAG}"
    exit 0
  fi
  sleep 2
done

echo "Deployment health check failed for ${IMAGE_TAG}" >&2
exit 1
