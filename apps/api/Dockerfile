# MFD Fund Monitoring - Production Dockerfile
# Multi-stage build for minimal production image

# ============================================================
# BUILD STAGE
# ============================================================
FROM python:3.11-slim as builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies (single lock-step requirements file)
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# ============================================================
# PRODUCTION STAGE
# ============================================================
FROM python:3.11-slim

WORKDIR /app

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Copy Python packages from builder
COPY --from=builder /root/.local /home/appuser/.local

# Copy application code (src layout; runtime config and migrations stay outside src)
COPY --chown=appuser:appuser src ./src
COPY --chown=appuser:appuser config ./config
COPY --chown=appuser:appuser migrations ./migrations
COPY --chown=appuser:appuser scripts ./scripts
COPY --chown=appuser:appuser pyproject.toml ./

# Create a writable log directory for the batch pipeline
RUN mkdir -p /app/logs && chown -R appuser:appuser /app/logs

# Switch to non-root user
USER appuser

# Add local packages to PATH and make the src layout importable
ENV PATH=/home/appuser/.local/bin:$PATH \
    PYTHONPATH=/app/src

# Environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f "http://localhost:${PORT:-8000}/health" || exit 1

# Expose port
EXPOSE 8000

# Run application (PORT is injected by the platform, e.g. Railway)
CMD ["sh", "-c", "uvicorn fund_engine.api.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 2"]