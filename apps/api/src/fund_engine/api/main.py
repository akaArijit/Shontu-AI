"""
MFD Fund Monitoring API - FastAPI application factory.

Internal use only - Mutual Fund Distributors.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from fund_engine.api.routes import csv_upload, mfd_scores
from fund_engine.core.logging import configure_logging
from fund_engine.core.settings import get_cors_settings

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle events."""
    configure_logging()
    logger.info("Starting MFD Fund Monitoring API")
    yield
    logger.info("Shutting down MFD Fund Monitoring API")


def create_app() -> FastAPI:
    """Build the FastAPI application (useful for tests and ASGI servers)."""
    application = FastAPI(
        title="MFD Fund Monitoring API",
        description=(
            "Internal API for Mutual Fund Distributors - "
            "fund health scores, alerts, and monitoring"
        ),
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # ALLOWED_ORIGINS: comma-separated exact origins, e.g.
    #   "https://fund-engine.vercel.app,http://localhost:3000"
    # ALLOWED_ORIGIN_REGEX: optional regex for preview deployments, e.g.
    #   "https://fund-engine-[a-z0-9-]+\\.vercel\\.app"
    allowed_origins, allowed_origin_regex = get_cors_settings()
    application.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_origin_regex=allowed_origin_regex,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Public API is versioned under /api/v1 (matches the frontend baseURL).
    api_v1 = APIRouter(prefix="/api/v1")
    api_v1.include_router(mfd_scores.router)
    api_v1.include_router(csv_upload.router)
    application.include_router(api_v1)

    @application.get("/")
    async def root():
        """Service metadata endpoint."""
        return {
            "service": "MFD Fund Monitoring API",
            "version": "1.0.0",
            "status": "operational",
            "docs": "/docs",
        }

    @application.get("/health")
    async def health_check():
        """Detailed health check for load balancers."""
        return {
            "status": "healthy",
            "service": "mfd-fund-monitoring-api",
            "version": "1.0.0",
        }

    return application


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "fund_engine.api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )
