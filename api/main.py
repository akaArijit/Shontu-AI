"""
MFD Fund Monitoring API - FastAPI Application
Internal use only - Mutual Fund Distributors
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging
from pathlib import Path

from api.routes import mfd_scores

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
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
    redoc_url="/redoc"
)

# CORS configuration for internal MFD dashboard
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include MFD routes
app.include_router(mfd_scores.router)


@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "service": "MFD Fund Monitoring API",
        "version": "1.0.0",
        "status": "operational",
        "docs": "/docs"
    }


@app.get("/health")
async def health_check():
    """Detailed health check for load balancers."""
    return {
        "status": "healthy",
        "service": "mfd-fund-monitoring-api",
        "version": "1.0.0"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )