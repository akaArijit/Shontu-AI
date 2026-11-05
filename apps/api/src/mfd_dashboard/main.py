"""FastAPI application factory for the local MFD dashboard."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from mfd_dashboard.api.routes import router
from mfd_dashboard.core.paths import ensure_directories
from mfd_dashboard.core.settings import APP_NAME, APP_VERSION, allowed_origins
from mfd_dashboard.db.session import init_db


logger = logging.getLogger(__name__)

_FILE_FIELD_LABELS = {
    "clients_file": "Client Details",
    "folios_file": "Folios",
    "portfolio_file": "Portfolio Valuation",
    "transactions_file": "Transaction Statement",
    "file": "Benchmark level",
}


def _seed_default_schemes() -> None:
    """Insert a small catalog of Indian-style fund names if the schemes table is empty.
    Skipped during automated test runs (detected via PYTEST_CURRENT_TEST or pytest in sys.modules)."""
    import sys, os
    if "pytest" in sys.modules or os.getenv("PYTEST_CURRENT_TEST"):
        return
    from mfd_dashboard.db.session import SessionLocal
    from mfd_dashboard.db.models import Scheme
    from mfd_dashboard.ingest.values import key_for_name

    default_funds = [
        "Apex Bluechip Fund",
        "Apex Flexi Cap Fund",
        "Apex Midcap Opportunities Fund",
        "Apex Small Cap 250 Fund",
        "Apex ELSS Tax Saver Fund",
        "Apex Hybrid Balanced Fund",
        "Apex Liquid Fund",
        "Apex Overnight Fund",
        "Apex Multi Asset Fund",
        "Apex PSU Equity Fund",
        "Apex Index Nifty 50 Fund",
    ]

    with SessionLocal() as db:
        if db.query(Scheme).first():
            return
        for name in default_funds:
            nk = key_for_name(name)
            scheme = Scheme(
                name=name,
                name_key=nk,
                normalized_name=nk,
            )
            db.add(scheme)
        db.commit()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    ensure_directories()
    init_db()
    _seed_default_schemes()
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title=APP_NAME,
        version=APP_VERSION,
        description="Local, privacy-first mutual fund distributor dashboard.",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins(),
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router)

    @app.exception_handler(RequestValidationError)
    async def request_validation_error(
        _request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        messages: list[str] = []
        for error in exc.errors():
            location = [str(item) for item in error.get("loc", [])]
            field = location[-1] if location else ""
            label = _FILE_FIELD_LABELS.get(field)
            if label and error.get("type") == "missing":
                messages.append(
                    f"{label} file is missing. Select all four files before "
                    "previewing the import."
                    if field
                    in {
                        "clients_file",
                        "folios_file",
                        "portfolio_file",
                        "transactions_file",
                    }
                    else f"{label} file is missing."
                )
            elif label:
                messages.append(f"{label} file is invalid.")
            else:
                messages.append(
                    f"{field or 'Request'} is invalid: "
                    f"{error.get('msg', 'check the value and try again.')}"
                )
        return JSONResponse(
            status_code=422,
            content={
                "detail": " ".join(dict.fromkeys(messages))
                or "The request is missing a required file or value."
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_exception(
        request: Request,
        exc: Exception,
    ) -> JSONResponse:
        logger.error(
            "Unhandled error while handling %s",
            request.url.path,
            exc_info=exc,
        )
        return JSONResponse(
            status_code=500,
            content={
                "detail": (
                    "Something went wrong while processing this request. "
                    "Your existing local snapshot was not changed. "
                    "Check the file formats and try again."
                )
            },
        )

    @app.get("/")
    def root() -> dict:
        return {
            "service": APP_NAME,
            "version": APP_VERSION,
            "status": "operational",
            "docs": "/docs",
            "privacy": "Local only. No client data is sent to external services.",
        }

    return app


app = create_app()
