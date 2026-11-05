"""Local benchmark closing-level import and storage.

Milestone 3 keeps benchmark levels in SQLite.  A file may use either a long
layout (``benchmark_name, date, level``) or a wide layout (one date column and
one column per benchmark).  Invalid rows are reported and skipped; levels are
never fetched from the internet or interpolated.
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from openpyxl import load_workbook
from sqlalchemy import select
from sqlalchemy.orm import Session

from mfd_dashboard.db.models import BenchmarkLevel
from mfd_dashboard.ingest.config import date_formats
from datetime import date, datetime, timedelta, timezone
from typing import Any

from mfd_dashboard.ingest.values import (
    clean_text,
    normalize_header,
    parse_date_value,
    parse_decimal,
)
from mfd_dashboard.ingest.xlsx import MAX_DATA_ROWS, WorkbookError

BENCHMARK_HEADERS = {
    "benchmark",
    "benchmark name",
    "benchmark index",
    "index",
    "index name",
}
DATE_HEADERS = {
    "date",
    "level date",
    "closing date",
    "nav date",
    "as on",
    "as of",
}
LEVEL_HEADERS = {
    "level",
    "closing level",
    "close",
    "closing value",
    "value",
    "nav",
}


@dataclass(frozen=True)
class BenchmarkLevelRow:
    benchmark_name: str
    level_date: date
    level: Decimal
    row_number: int


@dataclass
class BenchmarkParseResult:
    rows: list[BenchmarkLevelRow]
    issues: list[dict[str, Any]]
    detected_format: str
    sheet_name: str
    header_row: int | None
    warnings: list[str] = field(default_factory=list)


def _read_csv_rows(data: bytes | Path, file_name: str) -> list[list[str]]:
    if isinstance(data, Path):
        if data.stat().st_size == 0:
            raise WorkbookError(f"{file_name} is empty.")
        try:
            with data.open("r", encoding="utf-8-sig", newline="") as handle:
                return [list(row) for row in csv.reader(handle)]
        except UnicodeDecodeError:
            try:
                with data.open("r", encoding="cp1252", newline="") as handle:
                    return [list(row) for row in csv.reader(handle)]
            except UnicodeDecodeError as exc:
                raise WorkbookError(
                    f"{file_name} could not be decoded as CSV. Save it as UTF-8 CSV."
                ) from exc
        except csv.Error as exc:
            raise WorkbookError(
                f"{file_name} could not be read as CSV. Check the file and try again."
            ) from exc

    if not data:
        raise WorkbookError(f"{file_name} is empty.")
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        try:
            text = data.decode("cp1252")
        except UnicodeDecodeError as exc:
            raise WorkbookError(
                f"{file_name} could not be decoded as CSV. Save it as UTF-8 CSV."
            ) from exc
    try:
        return [list(row) for row in csv.reader(io.StringIO(text, newline=""))]
    except csv.Error as exc:
        raise WorkbookError(
            f"{file_name} could not be read as CSV. Check the file and try again."
        ) from exc


def _read_sheets(
    data: bytes | Path, file_name: str
) -> list[tuple[str, list[list[Any]], str]]:
    if isinstance(data, Path):
        empty = data.stat().st_size == 0
    else:
        empty = not data
    if empty:
        raise WorkbookError(f"{file_name} is empty.")

    name = (file_name or "").casefold()
    is_csv = name.endswith(".csv")
    is_xlsx = name.endswith(".xlsx") or (
        isinstance(data, bytes) and data[:2] == b"PK"
    )
    if is_csv and not is_xlsx:
        return [("CSV", _read_csv_rows(data, file_name), "csv")]

    try:
        workbook = load_workbook(
            data if isinstance(data, Path) else io.BytesIO(data),
            data_only=True,
            read_only=True,
        )
    except Exception as exc:
        raise WorkbookError(
            f"{file_name} could not be read as an XLSX workbook."
        ) from exc
    try:
        sheets: list[tuple[str, list[list[Any]], str]] = []
        for worksheet in workbook.worksheets:
            rows: list[list[Any]] = []
            for index, row in enumerate(
                worksheet.iter_rows(values_only=True),
                start=1,
            ):
                if index > MAX_DATA_ROWS:
                    raise WorkbookError(
                        f"{file_name} has more than {MAX_DATA_ROWS:,} rows. "
                        "Please split the benchmark file."
                    )
                rows.append(list(row))
            sheets.append((worksheet.title, rows, "xlsx"))
        return sheets
    finally:
        workbook.close()


def _header_positions(
    normalized: list[str], aliases: set[str]
) -> list[int]:
    return [index for index, value in enumerate(normalized) if value in aliases]


def _detect_table(
    rows: list[list[Any]],
) -> tuple[str, int, int, int | None, list[str]] | None:
    """Return ``(format, header_index, date_index, benchmark_index, headers)``."""

    for index in range(min(len(rows), 40)):
        values = rows[index]
        headers = [clean_text(value) for value in values]
        normalized = [normalize_header(value) for value in headers]
        if not any(normalized):
            continue

        date_positions = _header_positions(normalized, DATE_HEADERS)
        if not date_positions:
            continue
        date_index = date_positions[0]

        benchmark_positions = _header_positions(normalized, BENCHMARK_HEADERS)
        level_positions = _header_positions(normalized, LEVEL_HEADERS)
        if benchmark_positions and level_positions:
            return "long", index, date_index, benchmark_positions[0], headers

        benchmark_columns = [
            position
            for position, header in enumerate(headers)
            if header and position != date_index
        ]
        if benchmark_columns:
            return "wide", index, date_index, None, headers

    return None


def _parse_date(value: Any) -> date | None:
    parsed, _, status = parse_date_value(value, date_formats())
    return parsed if status == "ok" else None


def _issue(
    issues: list[dict[str, Any]],
    row_number: int,
    field: str,
    message: str,
) -> None:
    issues.append(
        {
            "row_number": row_number,
            "field": field,
            "message": message,
            "severity": "warning",
        }
    )


def _add_row(
    parsed: dict[tuple[str, date], BenchmarkLevelRow],
    issues: list[dict[str, Any]],
    *,
    benchmark_name: str,
    level_date: date,
    level: Decimal,
    row_number: int,
) -> None:
    key = (normalize_header(benchmark_name), level_date)
    if key in parsed:
        _issue(
            issues,
            row_number,
            "level",
            f"Duplicate level for {benchmark_name} on {level_date.isoformat()}; "
            "the last value in the file was used.",
        )
    parsed[key] = BenchmarkLevelRow(
        benchmark_name=benchmark_name,
        level_date=level_date,
        level=level,
        row_number=row_number,
    )


def _parse_long(
    rows: list[list[Any]],
    header_index: int,
    date_index: int,
    benchmark_index: int,
    headers: list[str],
) -> tuple[list[BenchmarkLevelRow], list[dict[str, Any]]]:
    issues: list[dict[str, Any]] = []
    parsed: dict[tuple[str, date], BenchmarkLevelRow] = {}
    normalized = [normalize_header(value) for value in headers]
    level_index = next(
        (index for index, value in enumerate(normalized) if value in LEVEL_HEADERS),
        None,
    )
    if level_index is None:
        return [], issues

    for index in range(header_index + 1, len(rows)):
        values = rows[index]
        row_number = index + 1
        if not any(clean_text(value) for value in values):
            continue
        benchmark_name = clean_text(
            values[benchmark_index] if benchmark_index < len(values) else ""
        )
        raw_date = values[date_index] if date_index < len(values) else None
        raw_level = values[level_index] if level_index < len(values) else None
        if not benchmark_name:
            _issue(
                issues,
                row_number,
                "benchmark_name",
                "Row has a missing benchmark name and was skipped.",
            )
            continue
        level_date = _parse_date(raw_date)
        if level_date is None:
            _issue(
                issues,
                row_number,
                "date",
                "Row has a missing or invalid date and was skipped.",
            )
            continue
        level = parse_decimal(raw_level)
        if level is None or level <= 0:
            _issue(
                issues,
                row_number,
                "level",
                "Row has a missing, invalid or non-positive level and was skipped.",
            )
            continue
        _add_row(
            parsed,
            issues,
            benchmark_name=benchmark_name,
            level_date=level_date,
            level=level,
            row_number=row_number,
        )
    return list(parsed.values()), issues


def _parse_wide(
    rows: list[list[Any]],
    header_index: int,
    date_index: int,
    headers: list[str],
) -> tuple[list[BenchmarkLevelRow], list[dict[str, Any]]]:
    issues: list[dict[str, Any]] = []
    parsed: dict[tuple[str, date], BenchmarkLevelRow] = {}
    benchmark_columns = [
        (index, header)
        for index, header in enumerate(headers)
        if header and index != date_index
    ]

    for index in range(header_index + 1, len(rows)):
        values = rows[index]
        row_number = index + 1
        if not any(clean_text(value) for value in values):
            continue
        raw_date = values[date_index] if date_index < len(values) else None
        level_date = _parse_date(raw_date)
        if level_date is None:
            _issue(
                issues,
                row_number,
                "date",
                "Row has a missing or invalid date and was skipped.",
            )
            continue
        for column_index, benchmark_name in benchmark_columns:
            if column_index >= len(values):
                continue
            raw_level = values[column_index]
            if not clean_text(raw_level):
                continue
            level = parse_decimal(raw_level)
            if level is None or level <= 0:
                _issue(
                    issues,
                    row_number,
                    "level",
                    f"Row has an invalid or non-positive level for {benchmark_name} "
                    "and that value was skipped.",
                )
                continue
            _add_row(
                parsed,
                issues,
                benchmark_name=benchmark_name,
                level_date=level_date,
                level=level,
                row_number=row_number,
            )
    return list(parsed.values()), issues


def parse_benchmark_levels(
    data: bytes | Path,
    file_name: str,
) -> BenchmarkParseResult:
    sheets = _read_sheets(data, file_name)
    for sheet_name, rows, _source_kind in sheets:
        detected = _detect_table(rows)
        if detected is None:
            continue
        detected_format, header_index, date_index, benchmark_index, headers = detected
        if detected_format == "long" and benchmark_index is not None:
            parsed_rows, issues = _parse_long(
                rows,
                header_index,
                date_index,
                benchmark_index,
                headers,
            )
        else:
            parsed_rows, issues = _parse_wide(
                rows,
                header_index,
                date_index,
                headers,
            )
        warnings: list[str] = []
        if not parsed_rows:
            warnings.append(
                "No valid benchmark levels were found in the detected table."
            )
        return BenchmarkParseResult(
            rows=parsed_rows,
            issues=issues,
            detected_format=detected_format,
            sheet_name=sheet_name,
            header_row=header_index + 1,
            warnings=warnings,
        )

    raise WorkbookError(
        "No benchmark level table was found. Use either benchmark_name, date, level "
        "columns or a date column followed by one column per benchmark."
    )


def load_benchmark_levels(db: Session) -> dict[str, dict[date, Decimal]]:
    """Return levels keyed by normalized benchmark name, then date."""

    levels: dict[str, dict[date, Decimal]] = {}
    for item in db.scalars(
        select(BenchmarkLevel).order_by(
            BenchmarkLevel.benchmark_name_key,
            BenchmarkLevel.level_date,
        )
    ):
        levels.setdefault(item.benchmark_name_key, {})[item.level_date] = item.level
    return levels


def benchmark_level_names(db: Session) -> list[str]:
    names = {
        item.benchmark_name
        for item in db.scalars(
            select(BenchmarkLevel).order_by(BenchmarkLevel.benchmark_name)
        )
    }
    return sorted(names)


def benchmark_level_summaries(db: Session) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for item in db.scalars(
        select(BenchmarkLevel).order_by(
            BenchmarkLevel.benchmark_name_key,
            BenchmarkLevel.level_date,
        )
    ):
        row = grouped.setdefault(
            item.benchmark_name_key,
            {
                "benchmark_name": item.benchmark_name,
                "level_count": 0,
                "first_date": item.level_date,
                "last_date": item.level_date,
                "source_file": item.source_file,
                "updated_at": item.imported_at,
            },
        )
        row["level_count"] += 1
        row["first_date"] = min(row["first_date"], item.level_date)
        row["last_date"] = max(row["last_date"], item.level_date)
        if item.imported_at >= row["updated_at"]:
            row["source_file"] = item.source_file
            row["updated_at"] = item.imported_at

    return [
        {
            "benchmark_name": row["benchmark_name"],
            "level_count": row["level_count"],
            "first_date": row["first_date"].isoformat(),
            "last_date": row["last_date"].isoformat(),
            "source_file": row["source_file"],
            "updated_at": row["updated_at"].isoformat(),
        }
        for row in sorted(grouped.values(), key=lambda item: item["benchmark_name"])
    ]


def import_benchmark_levels(
    db: Session,
    data: bytes | Path,
    file_name: str,
) -> dict[str, Any]:
    parsed = parse_benchmark_levels(data, file_name)
    if not parsed.rows:
        raise ValueError(
            "No valid benchmark levels were imported. Check the date, benchmark "
            "name and closing-level values."
        )

    keys = {normalize_header(row.benchmark_name) for row in parsed.rows}
    existing_items = db.scalars(
        select(BenchmarkLevel).where(BenchmarkLevel.benchmark_name_key.in_(keys))
    ).all()
    existing = {
        (item.benchmark_name_key, item.level_date): item for item in existing_items
    }

    now = datetime.now(timezone.utc)
    created = 0
    updated = 0
    for row in parsed.rows:
        key = normalize_header(row.benchmark_name)
        item = existing.get((key, row.level_date))
        if item is None:
            db.add(
                BenchmarkLevel(
                    benchmark_name=row.benchmark_name,
                    benchmark_name_key=key,
                    level_date=row.level_date,
                    level=row.level,
                    source_file=file_name,
                    imported_at=now,
                )
            )
            created += 1
        else:
            item.level = row.level
            item.source_file = file_name
            item.imported_at = now
            updated += 1
    db.commit()

    summaries = benchmark_level_summaries(db)
    imported_names = sorted({row.benchmark_name for row in parsed.rows})
    dates = sorted(row.level_date for row in parsed.rows)
    return {
        "file_name": file_name,
        "detected_format": parsed.detected_format,
        "sheet_name": parsed.sheet_name,
        "header_row": parsed.header_row,
        "created": created,
        "updated": updated,
        "imported": created + updated,
        "skipped": len(parsed.issues),
        "benchmarks": imported_names,
        "first_date": dates[0].isoformat(),
        "last_date": dates[-1].isoformat(),
        "issues": parsed.issues,
        "warnings": parsed.warnings,
        "summaries": summaries,
    }


def refresh_benchmark_levels(
    db: Session,
    *,
    years: int = 5,
    benchmark_names: list[str] | None = None,
) -> dict[str, Any]:
    """
    Fetch TRI data from NSE for benchmarks currently mapped to schemes.

    If benchmark_names is provided, only fetch for those benchmarks.
    Otherwise, fetch for all benchmarks that have at least one mapped scheme.
    """
    from mfd_dashboard.tri_fetcher import NseTriFetcher
    from mfd_dashboard.benchmark_mappings import (
        DEFAULT_BENCHMARK,
        available_benchmark_names,
    )

    # Determine which benchmarks to fetch
    if benchmark_names is None:
        # Get all benchmarks that have mapped schemes
        available = available_benchmark_names(db, include_master=False, include_default=False)
        # Filter out default/unmapped
        to_fetch = [name for name in available if name != DEFAULT_BENCHMARK]
    else:
        to_fetch = [name for name in benchmark_names if name != DEFAULT_BENCHMARK]

    if not to_fetch:
        return {
            "attempted": 0,
            "succeeded": 0,
            "failed": 0,
            "benchmarks": [],
            "message": "No benchmarks to fetch",
        }

    fetcher = NseTriFetcher()
    to_date = date.today()
    from_date = to_date - timedelta(days=365 * years)

    # Filter to only supported benchmarks
    supported = [name for name in to_fetch if fetcher.is_supported(name)]
    unsupported = [name for name in to_fetch if not fetcher.is_supported(name)]

    # Fetch TRI data
    fetched_data = fetcher.fetch_tri_history_bulk(supported, from_date, to_date)

    # Store in database
    now = datetime.now(timezone.utc)
    created = 0
    updated = 0
    errors: list[dict[str, Any]] = []

    for benchmark_name, rows in fetched_data.items():
        if not rows:
            errors.append({
                "benchmark": benchmark_name,
                "error": "No data returned from NSE",
            })
            continue

        key = normalize_header(benchmark_name)
        existing_items = db.scalars(
            select(BenchmarkLevel).where(BenchmarkLevel.benchmark_name_key == key)
        ).all()
        existing = {(item.level_date): item for item in existing_items}

        for row_date, level in rows:
            if row_date in existing:
                item = existing[row_date]
                if item.level != level:
                    item.level = level
                    item.imported_at = datetime.now(timezone.utc)
                    updated += 1
            else:
                db.add(BenchmarkLevel(
                    benchmark_name=benchmark_name,
                    benchmark_name_key=key,
                    level_date=row_date,
                    level=level,
                    source_file="nse_tri_auto",
                    imported_at=datetime.now(timezone.utc),
                ))
                created += 1

    db.commit()

    # Return summary
    return {
        "attempted": len(supported),
        "succeeded": len(fetched_data),
        "failed": len(supported) - len(fetched_data),
        "unsupported": unsupported,
        "benchmarks": list(fetched_data.keys()),
        "date_range": {
            "from": from_date.isoformat(),
            "to": date.today().isoformat(),
        },
        "errors": errors,
    }
