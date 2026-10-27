"""
MFD Fund Monitoring API - FastAPI Application
Internal use only - Mutual Fund Distributors
"""

from fastapi import FastAPI, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging
import os
from pathlib import Path

from api.routes import mfd_scores, csv_upload

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle events."""
    # Startup
    logger.info("Starting MFD Fund Monitoring API")
    # Initialize DB connections, load configs, etc.
    yield
    # Shutdown
    logger.info("Shutting down MFD Fund Monitoring API")


app = FastAPI(
    title="MFD Fund Monitoring API",
    description="Internal API for Mutual Fund Distributors - Fund health scores, alerts, and monitoring",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS configuration for internal MFD dashboard
# Comma-separated list, e.g. "https://web.up.railway.app,http://localhost:3000"
_allowed_origins = [
    origin.strip()
    for origin in os.getenv(
        "ALLOWED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000"
    ).split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Public API is versioned under /api/v1 (matches the frontend client baseURL)
api_v1 = APIRouter(prefix="/api/v1")
api_v1.include_router(mfd_scores.router)
api_v1.include_router(csv_upload.router)
app.include_router(api_v1)


@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "service": "MFD Fund Monitoring API",
        "version": "1.0.0",
        "status": "operational",
        "docs": "/docs",
    }


@app.get("/health")
async def health_check():
    """Detailed health check for load balancers."""
    return {
        "status": "healthy",
        "service": "mfd-fund-monitoring-api",
        "version": "1.0.0",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "api.main:app", host="0.0.0.0", port=8000, reload=True, log_level="info"
    )
