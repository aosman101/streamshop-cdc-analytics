#!/usr/bin/env bash
set -euo pipefail

CONNECT_URL="${CONNECT_URL:-http://localhost:8083}"
CONFIG_FILE="${1:-connectors/postgres-source.json}"

curl -sS -X POST \
  -H "Accept: application/json" \
  -H "Content-Type: application/json" \
  "${CONNECT_URL}/connectors" \
  --data @"${CONFIG_FILE}" | python -m json.tool
