"""Local API routes for the four-file InvestWell snapshot."""

from __future__ import annotations

import hashlib
import tempfile
from pathlib import Path
from typing import Literal

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Query,
    Response,
    UploadFile,
)
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from mfd_dashboard.benchmark_coverage import build_benchmark_coverage
from mfd_dashboard.benchmark_data import (
    benchmark_level_names,
    benchmark_level_summaries,
    import_benchmark_levels,
    refresh_benchmark_levels,
)
from mfd_dashboard.benchmark_graph import get_benchmark_graph
from mfd_dashboard.benchmark_mappings import (
    accept_benchmark_suggestions,
    apply_mapping_import,
    bulk_update_benchmark_mappings,
    export_benchmark_mappings,
    keyword_mapping_rule,
    list_benchmark_mappings,
    preview_mapping_import,
    update_benchmark_mapping,
)
from mfd_dashboard.benchmarks import benchmark_names
from mfd_dashboard.business_review import get_business_review
from mfd_dashboard.core.paths import UPLOADS_DIR
from mfd_dashboard.core.settings import API_PREFIX
from mfd_dashboard.dashboard import get_dashboard
from mfd_dashboard.db.session import get_db
from mfd_dashboard.demo import DemoDataExistsError, load_demo_data
from mfd_dashboard.ingest.service import confirm_import, preview_import
from mfd_dashboard.ingest.xlsx import WorkbookError


router = APIRouter(prefix=API_PREFIX)

MAX_FILE_SIZE = 25 * 1024 * 1024
UPLOAD_CHUNK_SIZE = 1024 * 1024


class BenchmarkMappingUpdate(BaseModel):
    benchmark_name: str


class BenchmarkBulkMappingUpdate(BaseModel):
    scheme_ids: list[int]
    benchmark_name: str


class BenchmarkSuggestionAccept(BaseModel):
    scheme_ids: list[int] | None = None


class BenchmarkKeywordMapping(BaseModel):
    keyword: str
    benchmark_name: str
    apply: bool = False


def _validate_filename(file: UploadFile, label: str) -> tuple[str, str]:
    name = Path(file.filename or "").name
    suffix = Path(name).suffix.lower()
    if suffix not in {".xlsx", ".csv"}:
        raise HTTPException(
            status_code=400,
            detail=f"{label} must be an .xlsx or .csv file.",
        )
    if not name:
        raise HTTPException(status_code=400, detail=f"{label} has no file name.")
    return name, suffix


async def _store_upload(
    file: UploadFile,
    label: str,
    target: Path,
) -> tuple[str, int, str]:
    """Write one upload to a temporary file while hashing it.

    Keeping the original bytes out of process memory is what lets the preview
    read large exports in a streaming pass.  The file is deleted when the
    request finishes.
    """

    name, _ = _validate_filename(file, label)
    digest = hashlib.sha256()
    size = 0
    try:
        with target.open("wb") as output:
            while True:
                chunk = await file.read(UPLOAD_CHUNK_SIZE)
                if not chunk:
                    break
                size += len(chunk)
                if size > MAX_FILE_SIZE:
                    raise HTTPException(
                        status_code=413,
                        detail=(
                            f"{label} is larger than 25 MB. Please export a "
                            "smaller file or split the snapshot."
                        ),
                    )
                digest.update(chunk)
                output.write(chunk)
    except Exception:
        target.unlink(missing_ok=True)
        raise
    if size == 0:
        target.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=f"{label} is empty.")
    return name, size, digest.hexdigest()


async def _read_mapping_upload(file: UploadFile) -> bytes:
    """Read a small mapping file into memory with the same upload limit."""

    name, _ = _validate_filename(file, "Mapping file")
    chunks: list[bytes] = []
    size = 0
    while True:
        chunk = await file.read(UPLOAD_CHUNK_SIZE)
        if not chunk:
            break
        size += len(chunk)
        if size > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=413,
                detail=(
                    f"{name} is larger than 25 MB. Export a smaller mapping "
                    "file."
                ),
            )
        chunks.append(chunk)
    if size == 0:
        raise HTTPException(status_code=400, detail=f"{name} is empty.")
    return b"".join(chunks)


def _temporary_upload_dir() -> tempfile.TemporaryDirectory[str]:
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    return tempfile.TemporaryDirectory(
        prefix="mfd-upload-",
        dir=str(UPLOADS_DIR),
    )


@router.get("/health")
def health() -> dict:
    return {"status": "healthy", "service": "mfd-dashboard-api", "version": "0.6.0"}


@router.get("/dashboard")
def dashboard(db: Session = Depends(get_db)) -> dict:
    return get_dashboard(db)


@router.get("/business-review")
def business_review(
    performance: Literal[
        "all",
        "ahead",
        "behind",
        "in_line",
        "not_available",
        "needs_review",
    ] = Query("all"),
    benchmark: str = Query("all"),
    client: str = Query("all"),
    min_current_value: float | None = Query(None, ge=0),
    sort: Literal[
        "current_value",
        "difference",
        "xirr",
        "client_name",
    ] = Query("current_value"),
    direction: Literal["asc", "desc"] = Query("desc"),
    db: Session = Depends(get_db),
) -> dict:
    return get_business_review(
        db,
        performance=performance,
        benchmark=benchmark,
        client=client,
        min_current_value=min_current_value,
        sort=sort,
        direction=direction,
    )


@router.get("/benchmark-graph")
def benchmark_graph(db: Session = Depends(get_db)) -> dict:
    return get_benchmark_graph(db)


@router.get("/benchmarks")
def benchmarks() -> dict:
    return {
        "benchmarks": benchmark_names(),
        "note": (
            "Suggested benchmark categories. Automatic mappings remain Needs "
            "Review until saved on the local mapping screen."
        ),
    }


@router.get("/benchmark-mappings")
def benchmark_mappings(db: Session = Depends(get_db)) -> dict:
    return list_benchmark_mappings(db)


@router.get("/benchmarks/coverage")
def benchmark_coverage(db: Session = Depends(get_db)) -> dict:
    return build_benchmark_coverage(db)


@router.patch("/benchmark-mappings/{scheme_id}")
def benchmark_mapping_update(
    scheme_id: int,
    payload: BenchmarkMappingUpdate,
    db: Session = Depends(get_db),
) -> dict:
    try:
        return update_benchmark_mapping(db, scheme_id, payload.benchmark_name)
    except LookupError as exc:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception:
        db.rollback()
        raise


@router.post("/benchmark-mappings/bulk")
def benchmark_mapping_bulk(
    payload: BenchmarkBulkMappingUpdate,
    db: Session = Depends(get_db),
) -> dict:
    try:
        return bulk_update_benchmark_mappings(
            db,
            payload.scheme_ids,
            payload.benchmark_name,
        )
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception:
        db.rollback()
        raise


@router.post("/benchmark-mappings/accept-suggestions")
def benchmark_mapping_accept_suggestions(
    payload: BenchmarkSuggestionAccept | None = None,
    db: Session = Depends(get_db),
) -> dict:
    try:
        return accept_benchmark_suggestions(
            db,
            payload.scheme_ids if payload is not None else None,
        )
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception:
        db.rollback()
        raise


@router.post("/benchmark-mappings/accept-high-confidence")
def benchmark_mapping_accept_high_confidence(
    db: Session = Depends(get_db),
) -> dict:
    try:
        return accept_high_confidence_suggestions(db)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception:
        db.rollback()
        raise


@router.post("/benchmark-mappings/keyword")
def benchmark_mapping_keyword(
    payload: BenchmarkKeywordMapping,
    db: Session = Depends(get_db),
) -> dict:
    try:
        return keyword_mapping_rule(
            db,
            payload.keyword,
            payload.benchmark_name,
            apply=payload.apply,
        )
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception:
        db.rollback()
        raise


@router.post("/data/reset")
def reset_data(db: Session = Depends(get_db)) -> dict:
    """Delete the current snapshot and scheme catalog, then re‑seed the default Indian fund list."""
    # Remove snapshot tables first (FK order)
    db.execute(text("DELETE FROM transactions"))
    db.execute(text("DELETE FROM folios"))
    db.execute(text("DELETE FROM clients"))
    db.execute(text("DELETE FROM portfolio_valuations"))
    db.execute(text("DELETE FROM import_issues"))
    db.execute(text("DELETE FROM upload_batches"))
    # Remove scheme‑level data
    db.execute(text("DELETE FROM scheme_benchmarks"))
    db.execute(text("DELETE FROM benchmark_levels"))
    db.execute(text("DELETE FROM schemes"))
    db.commit()

    # Re‑seed default Indian‑style fund names
    from mfd_dashboard.ingest.values import key_for_name
    from mfd_dashboard.db.models import Scheme

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
    for name in default_funds:
        nk = key_for_name(name)
        db.add(Scheme(name=name, name_key=nk, normalized_name=nk))
    db.commit()

    return {"status": "ok", "message": "All data cleared and default fund catalog restored."}


@router.get("/benchmark-mappings/export")
def benchmark_mapping_export(
    format: Literal["csv", "xlsx"] = Query("csv"),
    db: Session = Depends(get_db),
) -> Response:
    try:
        content, media_type, filename = export_benchmark_mappings(db, format)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return Response(
        content=content,
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-store",
        },
    )


@router.post("/benchmark-mappings/import/preview")
async def benchmark_mapping_import_preview(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> dict:
    content = await _read_mapping_upload(file)
    try:
        return preview_mapping_import(db, file.filename or "", content)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/benchmark-mappings/import/apply")
async def benchmark_mapping_import_apply(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> dict:
    content = await _read_mapping_upload(file)
    try:
        return apply_mapping_import(db, file.filename or "", content)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception:
        db.rollback()
        raise


@router.get("/benchmarks/levels")
def benchmark_levels(db: Session = Depends(get_db)) -> dict:
    summaries = benchmark_level_summaries(db)
    return {
        "summaries": summaries,
        "benchmark_names": benchmark_level_names(db),
        "total_benchmarks": len(summaries),
        "total_levels": sum(item["level_count"] for item in summaries),
    }


@router.post("/benchmarks/levels/refresh")
async def benchmark_levels_refresh(
    years: int = Query(5, ge=1, le=20),
    benchmark_names: list[str] | None = Query(None),
    db: Session = Depends(get_db),
) -> dict:
    """
    Fetch TRI data from NSE for benchmarks currently mapped to schemes.

    If benchmark_names is provided, only fetch for those benchmarks.
    Otherwise, fetch for all benchmarks that have at least one mapped scheme.
    """
    try:
        return await run_in_threadpool(
            refresh_benchmark_levels,
            db,
            years=years,
            benchmark_names=benchmark_names,
        )
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception:
        db.rollback()
        raise


@router.post("/benchmarks/levels/import")
async def benchmark_levels_import(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> dict:
    try:
        with _temporary_upload_dir() as temp_dir:
            name, _ = _validate_filename(file, "Benchmark level file")
            suffix = Path(name).suffix.lower()
            target = Path(temp_dir) / f"benchmark-levels{suffix}"
            original_name, _, _ = await _store_upload(
                file,
                "Benchmark level file",
                target,
            )
            return await run_in_threadpool(
                import_benchmark_levels,
                db,
                target,
                original_name,
            )
    except WorkbookError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise


@router.post("/imports/preview")
async def import_preview(
    clients_file: UploadFile = File(...),
    folios_file: UploadFile = File(...),
    portfolio_file: UploadFile = File(...),
    transactions_file: UploadFile | None = File(None),
) -> dict:
    try:
        with _temporary_upload_dir() as temp_dir:
            root = Path(temp_dir)
            uploads: list[dict] = []
            for kind, label, file in (
                ("clients", "Client Details file", clients_file),
                ("folios", "Folios file", folios_file),
                ("portfolio", "Portfolio Valuation file", portfolio_file),
            ):
                name, _ = _validate_filename(file, label)
                target = root / f"{kind}{Path(name).suffix.lower()}"
                original_name, _, _ = await _store_upload(file, label, target)
                uploads.append(
                    {"kind": kind, "name": original_name, "path": target}
                )
            if transactions_file is not None:
                label = "Transaction Statement file"
                name, _ = _validate_filename(transactions_file, label)
                target = root / f"transactions{Path(name).suffix.lower()}"
                original_name, _, _ = await _store_upload(
                    transactions_file,
                    label,
                    target,
                )
                uploads.append(
                    {
                        "kind": "transactions",
                        "name": original_name,
                        "path": target,
                    }
                )

            files = {
                item["kind"]: (item["name"], item["path"])
                for item in uploads
            }
            return await run_in_threadpool(preview_import, files)
    except WorkbookError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except HTTPException:
        raise
    except OSError as exc:
        raise HTTPException(
            status_code=500,
            detail=(
                "The uploaded files could not be read from local temporary "
                "storage. Check that the data folder is writable and try again."
            ),
        ) from exc


@router.post("/imports/{import_id}/confirm")
def import_confirm(import_id: str, db: Session = Depends(get_db)) -> dict:
    try:
        return confirm_import(db, import_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception:
        db.rollback()
        raise


@router.post("/demo/load")
def load_demo(
    replace: bool = Query(False, description="Replace existing local data."),
    db: Session = Depends(get_db),
) -> dict:
    try:
        return load_demo_data(db, replace=replace)
    except DemoDataExistsError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception:
        db.rollback()
        raise
