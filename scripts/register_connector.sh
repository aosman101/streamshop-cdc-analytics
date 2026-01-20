#!/usr/bin/env bash
set -euo pipefail

CONNECT_URL="${CONNECT_URL:-http://localhost:8083}"
CONFIG_FILE="${1:-connectors/postgres-source.json}"
MAX_RETRIES="${MAX_RETRIES:-30}"

echo "Waiting for Kafka Connect at ${CONNECT_URL} ..."
for i in $(seq 1 "${MAX_RETRIES}"); do
  status="$(curl -s -o /dev/null -w "%{http_code}" "${CONNECT_URL}/connectors" || true)"
  if [[ "${status}" == "200" ]]; then
    echo "Kafka Connect is ready (attempt ${i})."
    break
  fi
  echo "  not ready yet (status: ${status:-curl_error}), retrying..."
  sleep 2
done

curl -sS -X POST \
  -H "Accept: application/json" \
  -H "Content-Type: application/json" \
  "${CONNECT_URL}/connectors" \
  --data @"${CONFIG_FILE}" | python -m json.tool
