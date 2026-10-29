# Transitional root build entrypoint for Railway services created before the
# monorepo split. Preferred: set the service Root Directory to `apps/api` and
# delete this file plus the root `railway*.json` files.
#
# The build context is the repository root, so every path points at `apps/api`.

# ============================================================
# BUILD STAGE
# ============================================================
FROM python:3.11-slim as builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY apps/api/requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# ============================================================
# PRODUCTION STAGE
# ============================================================
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd -r appuser && useradd -r -g appuser appuser

COPY --from=builder /root/.local /home/appuser/.local

COPY --chown=appuser:appuser apps/api/src ./src
COPY --chown=appuser:appuser apps/api/config ./config
COPY --chown=appuser:appuser apps/api/migrations ./migrations
COPY --chown=appuser:appuser apps/api/scripts ./scripts

# Legacy start commands used `uvicorn api.main:app`; keep a tiny alias so those
# services boot during the transition. New services use fund_engine.api.main.
RUN mkdir -p /app/logs /app/api \
    && printf 'from fund_engine.api.main import app\n' > /app/api/main.py \
    && touch /app/api/__init__.py \
    && chown -R appuser:appuser /app/logs /app/api

USER appuser

ENV PATH=/home/appuser/.local/bin:$PATH \
    PYTHONPATH=/app/src:/app \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f "http://localhost:${PORT:-8000}/health" || exit 1

EXPOSE 8000

CMD ["sh", "-c", "uvicorn fund_engine.api.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 2"]
