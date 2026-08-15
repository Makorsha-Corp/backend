#!/usr/bin/env bash
# Push Cloudinary + CORS env from backend/.env to linked Railway service.
# Prereq: railway login && railway link (backend service selected)
#
# Usage (from backend/):
#   bash scripts/sync_railway_upload_env.sh
#
# Does not print secret values. Redeploy Railway after running.

set -euo pipefail
cd "$(dirname "$0")/.."

if [[ ! -f .env ]]; then
  echo "FAIL: backend/.env not found"
  exit 1
fi

if ! command -v railway >/dev/null 2>&1; then
  echo "FAIL: railway CLI not installed (npm i -g @railway/cli)"
  exit 1
fi

if ! railway status >/dev/null 2>&1; then
  echo "FAIL: no linked Railway project. Run: railway login && railway link -p <project> -s <backend-service>"
  exit 1
fi

EXPECTED_HOST="${EXPECTED_RAILWAY_HOST:-backend-production-847f}"
if ! railway status 2>&1 | grep -q "$EXPECTED_HOST"; then
  echo "FAIL: linked Railway service URL should contain '$EXPECTED_HOST' (Makorsha ERP backend)."
  echo "Run: railway link -p <project> -s <backend-service>"
  railway status 2>&1 || true
  exit 1
fi

# shellcheck disable=SC1091
set -a
source .env
set +a

missing=()
for key in CLOUDINARY_CLOUD_NAME CLOUDINARY_API_KEY CLOUDINARY_API_SECRET; do
  if [[ -z "${!key:-}" ]]; then
    missing+=("$key")
  fi
done

if ((${#missing[@]} > 0)); then
  echo "FAIL: missing in .env: ${missing[*]}"
  exit 1
fi

VERCEL_ORIGIN="${VERCEL_ORIGIN:-https://frontend-theta-dusky-91.vercel.app}"
CORS="${BACKEND_CORS_ORIGINS:-}"
if [[ "$CORS" != *"$VERCEL_ORIGIN"* ]]; then
  if [[ -n "$CORS" ]]; then
    CORS="${CORS},${VERCEL_ORIGIN}"
  else
    CORS="${VERCEL_ORIGIN},http://localhost:5173"
  fi
fi

echo "Setting Railway variables (values hidden)..."
railway variables set \
  "CLOUDINARY_CLOUD_NAME=${CLOUDINARY_CLOUD_NAME}" \
  "CLOUDINARY_API_KEY=${CLOUDINARY_API_KEY}" \
  "CLOUDINARY_API_SECRET=${CLOUDINARY_API_SECRET}" \
  "CLOUDINARY_UPLOAD_ENV=production" \
  "ENVIRONMENT=production" \
  "BACKEND_CORS_ORIGINS=${CORS}"

echo "OK: Cloudinary + CORS synced to Railway."
echo "Next: redeploy backend service, then test phone QR upload on hosted site."
echo "Optional verify: railway redeploy"
