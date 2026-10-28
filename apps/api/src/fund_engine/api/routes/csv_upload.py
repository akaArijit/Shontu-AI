"""
CSV Upload Endpoints for Scheme Master Data
Allows MFDs to upload scheme master CSV files for deduplication and benchmark mapping
"""

from fastapi import APIRouter, UploadFile, File, HTTPException, Query
from fastapi.responses import StreamingResponse
import csv
import io
import logging
from typing import List, Optional
from datetime import date, datetime
from pydantic import BaseModel, validator
from enum import Enum

from fund_engine.db.connection import get_cursor
from fund_engine.db import persistence

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/mfd/csv", tags=["MFD CSV Upload"])


def _persist(callback):
    """Run a writer callback, translating infrastructure failures into 503s."""
    try:
        with get_cursor() as cur:
            return callback(cur)
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.error("CSV persistence failed: %s", exc)
        raise HTTPException(status_code=503, detail="Database unavailable") from exc


def _ensure_csv(file: UploadFile) -> None:
    """Reject non-CSV uploads (case-insensitive) before reading the body."""
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="File must be a CSV")


def _decode_csv(content: bytes) -> str:
    """Decode an uploaded CSV, stripping the BOM that Excel exports include."""
    try:
        return content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise HTTPException(
            status_code=400, detail="Unable to decode CSV. Ensure UTF-8 encoding."
        ) from exc


def _parse_history_date(raw: str) -> date:
    """Accept ISO and common Indian date formats used in NSE exports."""
    text = (raw or "").strip()
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%d %b %Y", "%d-%b-%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Unrecognised date: {raw}")


class SchemeCategory(str, Enum):
    LARGE_CAP = "Large Cap"
    LARGE_AND_MID_CAP = "Large & Mid Cap"
    FLEXI_CAP = "Flexi Cap"
    MULTI_CAP = "Multi Cap"
    MID_CAP = "Mid Cap"
    SMALL_CAP = "Small Cap"
    ELSS = "ELSS"
    SECTORAL_CONSUMPTION = "Sectoral - Consumption"
    SECTORAL_INFRASTRUCTURE = "Sectoral - Infrastructure"
    SECTORAL_PHARMA = "Sectoral - Pharma"
    SECTORAL_BANKING = "Sectoral - Banking"
    SECTORAL_IT = "Sectoral - IT"
    THEMATIC = "Thematic"
    HYBRID_AGGRESSIVE = "Hybrid Aggressive"
    HYBRID_CONSERVATIVE = "Hybrid Conservative"
    DEBT_ULTRA_SHORT = "Debt - Ultra Short Duration"
    DEBT_SHORT = "Debt - Short Duration"
    DEBT_MEDIUM = "Debt - Medium Duration"
    INTERNATIONAL_US = "International - US"
    INTERNATIONAL_GLOBAL = "International - Global"


class SchemeCSVRow(BaseModel):
    """Expected CSV columns for scheme master upload"""

    scheme_code: str
    scheme_name: str
    amc: str
    category: str
    sub_category: Optional[str] = None
    benchmark_index: Optional[str] = None
    fund_manager: Optional[str] = None
    expense_ratio: Optional[float] = None
    aum: Optional[float] = None
    inception_date: Optional[date] = None
    is_active: bool = True
    short_name: Optional[str] = None  # Short name for display

    @validator("category")
    def validate_category(cls, v):
        valid_categories = [c.value for c in SchemeCategory]
        if v not in valid_categories:
            raise ValueError(
                f"Invalid category. Must be one of: {', '.join(valid_categories)}"
            )
        return v


class CSVUploadResponse(BaseModel):
    success: bool
    message: str
    total_rows: int
    valid_rows: int
    invalid_rows: int
    persisted_rows: int = 0
    skipped_rows: int = 0
    errors: List[dict] = []
    preview: List[dict] = []


class SchemeMasterExport(BaseModel):
    scheme_code: str
    scheme_name: str
    amc: str
    category: str
    sub_category: Optional[str]
    benchmark_index: Optional[str]
    fund_manager: Optional[str]
    expense_ratio: Optional[float]
    aum: Optional[float]
    inception_date: Optional[date]
    is_active: bool
    short_name: Optional[str]


# Expected CSV template
CSV_TEMPLATE_HEADERS = [
    "scheme_code",
    "scheme_name",
    "amc",
    "category",
    "sub_category",
    "benchmark_index",
    "fund_manager",
    "expense_ratio",
    "aum",
    "inception_date",
    "is_active",
    "short_name",
]

CSV_TEMPLATE_EXAMPLE = [
    "INF204K01VX3",
    "HDFC Top 100 Fund",
    "HDFC Mutual Fund",
    "Large Cap",
    "",
    "NIFTY100_TRI",
    "Prashant Jain",
    "1.05",
    "25000",
    "2010-01-01",
    "true",
    "HDFC Top 100",
]


@router.get("/template")
async def download_csv_template():
    """Download CSV template for scheme master upload"""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(CSV_TEMPLATE_HEADERS)
    writer.writerow(CSV_TEMPLATE_EXAMPLE)
    writer.writerow(
        [
            "INF767K01EW8",
            "Parag Parikh Flexi Cap Fund",
            "PPFAS Mutual Fund",
            "Flexi Cap",
            "",
            "NIFTY500_TRI",
            "Rajeev Thakkar",
            "0.95",
            "18000",
            "2013-05-01",
            "true",
            "PPFCF",
        ]
    )

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=scheme_master_template.csv"
        },
    )


@router.post("/upload/scheme-master", response_model=CSVUploadResponse)
async def upload_scheme_master_csv(
    file: UploadFile = File(...),
    dry_run: bool = Query(False, description="Validate only, don't persist"),
    overwrite: bool = Query(False, description="Overwrite existing schemes"),
):
    """
    Upload scheme master CSV file.

    Expected columns: scheme_code, scheme_name, amc, category, sub_category,
    benchmark_index, fund_manager, expense_ratio, aum, inception_date, is_active, short_name

    Returns validation results and preview of parsed data.
    """
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="File must be a CSV")

    content = await file.read()
    content_str = _decode_csv(content)

    # Parse CSV
    reader = csv.DictReader(io.StringIO(content_str))
    rows = list(reader)

    # Validate each row
    valid_rows = []
    errors = []
    valid_count = 0
    invalid_count = 0

    for idx, row in enumerate(rows, start=1):
        try:
            # Clean empty strings
            cleaned = {
                k: v.strip() if isinstance(v, str) else v for k, v in row.items()
            }

            # Convert empty strings to None for optional fields
            for key in [
                "sub_category",
                "benchmark_index",
                "fund_manager",
                "short_name",
            ]:
                if cleaned.get(key) == "":
                    cleaned[key] = None

            # Convert numeric fields
            for key in ["expense_ratio", "aum"]:
                if cleaned.get(key) not in (None, ""):
                    try:
                        cleaned[key] = float(cleaned[key])
                    except ValueError:
                        cleaned[key] = None

            # Convert date
            if cleaned.get("inception_date") not in (None, ""):
                try:
                    cleaned["inception_date"] = date.fromisoformat(
                        cleaned["inception_date"]
                    )
                except ValueError:
                    try:
                        # Try DD-MM-YYYY format
                        cleaned["inception_date"] = date.strptime(
                            cleaned["inception_date"], "%d-%m-%Y"
                        )
                    except ValueError:
                        cleaned["inception_date"] = None

            # Convert boolean
            if cleaned.get("is_active") not in (None, ""):
                cleaned["is_active"] = str(cleaned["is_active"]).lower() in (
                    "true",
                    "1",
                    "yes",
                    "y",
                )

            # Validate with Pydantic
            scheme = SchemeCSVRow(**cleaned)
            valid_rows.append(scheme.dict())
            valid_count += 1

        except Exception as e:
            errors.append({"row": idx, "error": str(e), "data": row})
            invalid_count += 1

    # Generate preview (first 10 valid rows)
    preview = valid_rows[:10]

    # Persist to database unless this is a validation-only request.
    persisted_count = 0
    skipped_count = 0
    if not dry_run and valid_count > 0:

        def _write(cur):
            codes = [row["scheme_code"] for row in valid_rows]
            existing = set()
            if not overwrite:
                cur.execute(
                    "SELECT scheme_code FROM scheme_master WHERE scheme_code = ANY(%(codes)s)",
                    {"codes": codes},
                )
                existing = {row["scheme_code"] for row in cur.fetchall()}

            benchmarks = {
                row["benchmark_index"]: {
                    "benchmark_code": row["benchmark_index"],
                    "benchmark_name": row["benchmark_index"],
                    "category": row["category"],
                }
                for row in valid_rows
                if row.get("benchmark_index")
            }
            persistence.upsert_benchmarks(cur, list(benchmarks.values()))

            new_rows = [row for row in valid_rows if row["scheme_code"] not in existing]
            written = persistence.upsert_schemes(cur, new_rows)
            return written, len(valid_rows) - written

        persisted_count, skipped_count = _persist(_write)

    message = (
        f"Processed {len(rows)} rows: {valid_count} valid, {invalid_count} invalid"
    )
    if not dry_run:
        message += f", {persisted_count} persisted, {skipped_count} skipped"

    return CSVUploadResponse(
        success=invalid_count == 0,
        message=message,
        total_rows=len(rows),
        valid_rows=valid_count,
        invalid_rows=invalid_count,
        persisted_rows=persisted_count,
        skipped_rows=skipped_count,
        errors=errors,
        preview=preview,
    )


@router.get("/download/scheme-master")
async def download_scheme_master():
    """Download current scheme master as CSV (falls back to the template)."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(CSV_TEMPLATE_HEADERS)

    try:
        with get_cursor() as cur:
            cur.execute("""
                SELECT scheme_code, scheme_name, amc, category, sub_category,
                       benchmark_index, fund_manager, expense_ratio, aum,
                       inception_date, is_active
                FROM scheme_master
                ORDER BY scheme_code
                """)
            rows = cur.fetchall()
    except Exception as exc:  # noqa: BLE001 - export should still return a template
        logger.warning("Scheme master export falling back to template: %s", exc)
        rows = []

    if rows:
        for row in rows:
            writer.writerow(
                [
                    row["scheme_code"],
                    row["scheme_name"],
                    row["amc"],
                    row["category"],
                    row["sub_category"] or "",
                    row["benchmark_index"] or "",
                    row["fund_manager"] or "",
                    row["expense_ratio"] if row["expense_ratio"] is not None else "",
                    row["aum"] if row["aum"] is not None else "",
                    row["inception_date"].isoformat() if row["inception_date"] else "",
                    "true" if row["is_active"] else "false",
                    "",
                ]
            )
    else:
        writer.writerow(CSV_TEMPLATE_EXAMPLE)

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=scheme_master_export.csv"
        },
    )


@router.post("/upload/benchmark-mappings")
async def upload_benchmark_mappings_csv(
    file: UploadFile = File(...), dry_run: bool = Query(False)
):
    """
    Upload explicit benchmark mappings CSV.
    Expected columns: scheme_code, benchmark_code
    """
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="File must be a CSV")

    content = await file.read()
    content_str = _decode_csv(content)

    reader = csv.DictReader(io.StringIO(content_str))
    rows = list(reader)

    valid = []
    errors = []

    for idx, row in enumerate(rows, start=1):
        try:
            scheme_code = row.get("scheme_code", "").strip()
            benchmark_code = row.get("benchmark_code", "").strip()

            if not scheme_code or not benchmark_code:
                errors.append(
                    {
                        "row": idx,
                        "error": "Missing scheme_code or benchmark_code",
                        "data": row,
                    }
                )
                continue

            valid.append({"scheme_code": scheme_code, "benchmark_code": benchmark_code})
        except Exception as e:
            errors.append({"row": idx, "error": str(e), "data": row})

    persisted_count = 0
    skipped_count = 0

    if not dry_run and valid:

        def _write(cur):
            codes = [row["scheme_code"] for row in valid]
            cur.execute(
                "SELECT scheme_code FROM scheme_master WHERE scheme_code = ANY(%(codes)s)",
                {"codes": codes},
            )
            known = {row["scheme_code"] for row in cur.fetchall()}

            applicable = [row for row in valid if row["scheme_code"] in known]
            benchmarks = {
                row["benchmark_code"]: {
                    "benchmark_code": row["benchmark_code"],
                    "benchmark_name": row["benchmark_code"],
                    "category": None,
                }
                for row in applicable
            }
            persistence.upsert_benchmarks(cur, list(benchmarks.values()))
            persistence.update_scheme_benchmarks(
                cur,
                [
                    {
                        "scheme_code": row["scheme_code"],
                        "benchmark_index": row["benchmark_code"],
                    }
                    for row in applicable
                ],
            )
            return len(applicable), len(valid) - len(applicable)

        persisted_count, skipped_count = _persist(_write)

    message = f"Processed {len(rows)} rows: {len(valid)} valid, {len(errors)} invalid"
    if not dry_run:
        message += f", {persisted_count} applied, {skipped_count} unknown schemes"

    return {
        "success": len(errors) == 0,
        "message": message,
        "total_rows": len(rows),
        "valid_rows": len(valid),
        "invalid_rows": len(errors),
        "persisted_rows": persisted_count,
        "skipped_rows": skipped_count,
        "errors": errors,
        "mappings": valid if not dry_run else valid[:10],
    }


@router.post("/upload/benchmark-history")
async def upload_benchmark_history_csv(
    file: UploadFile = File(...), dry_run: bool = Query(False)
):
    """
    Upload benchmark index history CSV.
    Expected columns: benchmark_code, index_date, index_value

    Useful when NSE's site is unreachable or for non-NSE benchmarks
    (CRISIL, S&P 500). Existing points are overwritten.
    """
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="File must be a CSV")

    content = await file.read()
    content_str = _decode_csv(content)

    reader = csv.DictReader(io.StringIO(content_str))
    rows = list(reader)

    points: dict[tuple[str, date], dict] = {}
    errors = []
    duplicate_rows = 0

    for idx, row in enumerate(rows, start=1):
        try:
            benchmark_code = (row.get("benchmark_code") or "").strip()
            raw_date = (row.get("index_date") or "").strip()
            raw_value = (row.get("index_value") or "").strip()

            if not benchmark_code or not raw_date or not raw_value:
                errors.append(
                    {
                        "row": idx,
                        "error": "Missing benchmark_code, index_date or index_value",
                        "data": row,
                    }
                )
                continue

            try:
                index_date = _parse_history_date(raw_date)
            except ValueError as exc:
                errors.append({"row": idx, "error": str(exc), "data": row})
                continue

            try:
                index_value = float(raw_value.replace(",", ""))
            except ValueError:
                errors.append(
                    {
                        "row": idx,
                        "error": f"Invalid index_value: {raw_value}",
                        "data": row,
                    }
                )
                continue

            if index_value <= 0:
                errors.append(
                    {
                        "row": idx,
                        "error": f"index_value must be positive: {raw_value}",
                        "data": row,
                    }
                )
                continue

            key = (benchmark_code, index_date)
            if key in points:
                duplicate_rows += 1
            points[key] = {
                "benchmark_code": benchmark_code,
                "index_date": index_date,
                "index_value": index_value,
                "source": "csv",
            }
        except Exception as exc:  # noqa: BLE001 - report and continue
            errors.append({"row": idx, "error": str(exc), "data": row})

    valid = sorted(
        points.values(), key=lambda p: (p["benchmark_code"], p["index_date"])
    )

    persisted_count = 0
    if not dry_run and valid:
        codes = sorted({point["benchmark_code"] for point in valid})

        def _write(cur):
            persistence.upsert_benchmarks(
                cur,
                [
                    {
                        "benchmark_code": code,
                        "benchmark_name": code,
                        "category": None,
                    }
                    for code in codes
                ],
            )
            return persistence.upsert_benchmark_history(cur, valid)

        persisted_count = _persist(_write)

    message = f"Processed {len(rows)} rows: {len(valid)} valid, {len(errors)} invalid"
    if duplicate_rows:
        message += f", {duplicate_rows} duplicate dates replaced"
    if not dry_run:
        message += f", {persisted_count} persisted"

    return {
        "success": len(errors) == 0,
        "message": message,
        "total_rows": len(rows),
        "valid_rows": len(valid),
        "invalid_rows": len(errors),
        "duplicate_rows": duplicate_rows,
        "persisted_rows": persisted_count,
        "benchmarks": sorted({point["benchmark_code"] for point in valid}),
        "errors": errors,
        "preview": valid[:10],
    }


# Include in main API
def get_csv_router():
    return router
