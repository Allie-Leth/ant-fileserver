#!/usr/bin/env bash
set -euo pipefail

###############################################################################
#  Spin up a local MinIO side-car, run all integration tests, tear down
###############################################################################

# Resolve project root even if script is called from a sub-dir
ROOT_DIR=$(git -C "$(dirname "${BASH_SOURCE[0]}")" rev-parse --show-toplevel 2>/dev/null \
           || realpath "$(dirname "${BASH_SOURCE[0]}")/..")
COMPOSE_FILE="${ROOT_DIR}/tests/integration/docker-compose.yml"

echo "➡️  Starting MinIO (compose file: ${COMPOSE_FILE})"
docker compose -f "${COMPOSE_FILE}" up -d --quiet-pull
trap 'docker compose -f "${COMPOSE_FILE}" down --remove-orphans' EXIT

# Wait until the health endpoint responds
printf "⏳  Waiting for MinIO to become ready"
until curl -s -o /dev/null http://localhost:19000/minio/health/ready; do
  printf "."
  sleep 1
done
echo " ✅"

# Export the same variables your CI pipeline uses
export STORAGE_ENDPOINT="http://localhost:19000"
export STORAGE_BUCKET="firmware"
export STORAGE_ACCESS_KEY_ID="minioadmin"
export STORAGE_SECRET_ACCESS_KEY="minioadmin"
export STORAGE_REGION="us-east-1"
export JWT_SECRET_KEY="test-secret"

echo "▶️  Running integration tests"
pytest "${ROOT_DIR}/tests/integration" "$@"

# docker-compose is cleaned up automatically by the trap
