#!/bin/sh
# Production start command (Render): migrate, seed admin/API key, then serve.
set -e

echo "Running database migrations..."
alembic upgrade head

echo "Bootstrapping admin user and ingest key..."
python -m app.cli bootstrap

# The demo data for the SIMULATED sites is generated here in the cloud, so no PC has to
# stay on. Real ESP32 stations post on their own. Set SIMULATOR_ENABLED=false to turn off.
if [ "${SIMULATOR_ENABLED:-true}" = "true" ] && [ -n "${INGEST_API_KEY:-}" ]; then
  echo "Starting the simulator for the simulated sites..."
  (
    cd ../simulator
    while true; do
      python replay.py --api "http://127.0.0.1:${PORT:-8000}" --key "$INGEST_API_KEY" \
        --backfill-hours 48 --interval "${SIM_INTERVAL:-60}" || true
      echo "simulator stopped; restarting in 30 s"
      sleep 30
    done
  ) &
fi

echo "Starting API on port ${PORT:-8000}"
# One worker keeps the in-process SSE broadcaster consistent (see docs/ARCHITECTURE.md).
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" --proxy-headers --forwarded-allow-ips="*"
