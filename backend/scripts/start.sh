#!/bin/sh
# Production start command (Render): migrate, seed admin/API key, then serve.
set -e

echo "Running database migrations..."
alembic upgrade head

echo "Bootstrapping admin user and ingest key..."
python -m app.cli bootstrap

echo "Starting API on port ${PORT:-8000}"
# One worker keeps the in-process SSE broadcaster consistent (see docs/ARCHITECTURE.md).
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" --proxy-headers --forwarded-allow-ips="*"
