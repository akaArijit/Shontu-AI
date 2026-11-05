"""Read InvestWell XLSX/CSV exports and find their data tables.

Real exports are usually XLSX workbooks and can contain thousands of rows.  The
reader therefore opens XLSX workbooks in openpyxl's read-only mode, scans only a
small header window, and streams data rows when the import plan is built.  CSV
files are streamed in the same way.

Header matching is unchanged; the only special case is the headerless Portfolio
Valuation CSV/XLSX, which is accepted only when it matches the documented
13-column layout exactly.
"""

from __future__ import annotations

import csv
import io
import re
import zipfile
from dataclasses import dataclass, field
from datetime import date
from io import BytesIO
from pathlib import Path
from typing import Any, Iterator

from openpyxl import load_workbook

from mfd_dashboard.ingest.config import column_aliases, date_formats, file_config
from mfd_dashboard.ingest.values import (
    clean_text,
    is_sensitive_header,
    normalize_header,
    parse_date_value,
    parse_decimal,
)


class WorkbookError(ValueError):
    """Raised when an uploaded file cannot be read as an XLSX/CSV table."""


# A file at the upload limit should still fail clearly rather than consume all
# memory.  The row limit is deliberately far above the 10,000-row target.
MAX_DATA_ROWS = 100_000
MAX_UNCOMPRESSED_BYTES = 256 * 1024 * 1024
HEADER_SCAN_ROWS = 40

_REPORT_DATE_RE = re.compile(
    r"report\s*(?:printed|generated|date)?\s*(?:on|as\s*on)?\s*[:\-]?\s*(.+)$",
    re.IGNORECASE,
)

PORTFOLIO_HEADERLESS_HEADERS = [
    "CLIENT NAME",
    "APP CODE",
    "IWELL CODE",
    "PAN",
    "BALANCE UNITS",
    "PURCHASE VALUE",
    "CURRENT VALUE",
    "ONE DAY CHANGE",
    "DIVIDEND",
    "AVG HOLDING DAYS",
    "GAIN",
    "ABSOLUTE RETURN",
    "CAGR",
]

PORTFOLIO_HEADERLESS_MAPPING = {
    "client_name": 0,
    "app_code": 1,
    "iwell_code": 2,
    "balance_units": 4,
    "purchase_value": 5,
    "current_value": 6,
    "one_day_change": 7,
    "dividend": 8,
    "avg_holding_days": 9,
    "gain": 10,
    "absolute_return": 11,
    "cagr": 12,
}


FileSource = bytes | Path


@dataclass
class Table:
    sheet_name: str
    header_row: int | None
    data_start_row: int
    mapping: dict[str, int]
    headers: list[str]
    sensitive_columns: list[str]
    unmapped_columns: list[str]
    missing_required: list[str]
    duplicate_targets: list[str]
    source: FileSource = field(repr=False)
    title_rows: list[list[Any]] = field(default_factory=list, repr=False)
    headerless: bool = False
    layout_warning: str | None = None
    source_kind: str = "xlsx"

    def value(self, row: tuple[Any, ...] | list[Any], canonical: str) -> Any:
        index = self.mapping.get(canonical)
        if index is None or index >= len(row):
            return None
        return row[index]

    @property
    def mapped_indices(self) -> set[int]:
        return set(self.mapping.values())

    def detected(self, kind: str) -> dict[str, Any]:
        return {
            "file_type": kind,
            "sheet": self.sheet_name,
            "header_row": self.header_row,
            "mapping": {
                canonical: self.headers[index]
                for canonical, index in self.mapping.items()
                if index < len(self.headers)
            },
            "headers": self.headers,
            "unmapped_columns": self.unmapped_columns,
            "ignored_sensitive_columns": self.sensitive_columns,
            "missing_required": self.missing_required,
            "duplicate_targets": self.duplicate_targets,
            "headerless": self.headerless,
            "layout_warning": self.layout_warning,
            "source_kind": self.source_kind,
        }

    def _normalise_row(
        self,
        row_number: int,
        values: tuple[Any, ...] | list[Any],
    ) -> tuple[Any, ...]:
        if not self.headerless:
            return tuple(values)

        cells = [clean_text(value) for value in values]
        nonempty = [index for index, value in enumerate(cells) if value]
        if nonempty and max(nonempty) >= 13:
            raise WorkbookError(
                "The Portfolio Valuation file has more than 13 columns in its "
                "headerless layout. The fixed layout was not used because the "
                "file structure does not match. Re-export the report with a header."
            )
        result = list(values)
        if len(result) < 13:
            result.extend([""] * (13 - len(result)))
        return tuple(result)

    def data_rows(self) -> Iterator[tuple[int, tuple[Any, ...]]]:
        """Yield every data row, including blank and total rows.

        Callers are responsible for skipping blank/total rows and counting why
        rows were skipped.  Yielding all rows lets the preview report an honest
        rows-read count without keeping the workbook rows in memory.
        """

        if self.source_kind == "csv":
            rows = _iter_csv_rows(
                self.source,
                self.sheet_name,
                start_row=self.data_start_row,
            )
        else:
            workbook = _open_workbook(self.source, self.sheet_name)
            try:
                worksheet = workbook[self.sheet_name]
                rows = worksheet.iter_rows(
                    min_row=self.data_start_row,
                    values_only=True,
                )
                for offset, values in enumerate(rows):
                    row_number = self.data_start_row + offset
                    if offset >= MAX_DATA_ROWS:
                        raise WorkbookError(
                            f"The file has more than {MAX_DATA_ROWS:,} data rows. "
                            "Please split the export into smaller files."
                        )
                    yield row_number, self._normalise_row(row_number, values)
                return
            finally:
                workbook.close()

        for row_number, values in rows:
            if row_number - self.data_start_row >= MAX_DATA_ROWS:
                raise WorkbookError(
                    f"The file has more than {MAX_DATA_ROWS:,} data rows. "
                    "Please split the export into smaller files."
                )
            yield row_number, self._normalise_row(row_number, values)


def _check_compressed_workbook(source: FileSource, file_name: str) -> None:
    """Reject zip bombs before openpyxl expands the workbook."""

    try:
        archive_source: Any = source if isinstance(source, Path) else BytesIO(source)
        with zipfile.ZipFile(archive_source) as archive:
            uncompressed = sum(item.file_size for item in archive.infolist())
    except (OSError, zipfile.BadZipFile) as exc:
        raise WorkbookError(
            f"{file_name} could not be read as an XLSX workbook. "
            "Please upload the original .xlsx file."
        ) from exc
    if uncompressed > MAX_UNCOMPRESSED_BYTES:
        raise WorkbookError(
            f"{file_name} expands to more than "
            f"{MAX_UNCOMPRESSED_BYTES // (1024 * 1024)} MB. Please split the "
            "export into smaller files."
        )


def _open_workbook(source: FileSource, file_name: str):
    _check_compressed_workbook(source, file_name)
    try:
        return load_workbook(
            source if isinstance(source, Path) else BytesIO(source),
            data_only=True,
            read_only=True,
        )
    except Exception as exc:  # openpyxl raises several exception types
        raise WorkbookError(
            f"{file_name} could not be read as an XLSX workbook. "
            "Please upload the original .xlsx file."
        ) from exc


def _iter_csv_rows(
    source: FileSource,
    file_name: str,
    *,
    start_row: int = 1,
) -> Iterator[tuple[int, list[str]]]:
    """Stream CSV rows without loading the whole decoded file into memory."""

    if isinstance(source, Path):
        try:
            handle = source.open("r", encoding="utf-8-sig", newline="")
            handle.read(4096)
            handle.seek(0)
        except UnicodeDecodeError:
            handle = source.open("r", encoding="cp1252", newline="")
        except OSError as exc:
            raise WorkbookError(f"{file_name} could not be read.") from exc
        close_handle = True
    else:
        if not source:
            raise WorkbookError(f"{file_name} is empty.")
        try:
            text = source.decode("utf-8-sig")
        except UnicodeDecodeError:
            try:
                text = source.decode("cp1252")
            except UnicodeDecodeError as exc:
                raise WorkbookError(
                    f"{file_name} could not be decoded as CSV. Save it as UTF-8 CSV."
                ) from exc
        handle = io.StringIO(text, newline="")
        close_handle = False

    try:
        reader = csv.reader(handle)
        try:
            for index, values in enumerate(reader, start=1):
                if index < start_row:
                    continue
                yield index, list(values)
        except csv.Error as exc:
            raise WorkbookError(
                f"{file_name} could not be read as CSV. Check the file and try again."
            ) from exc
    finally:
        if close_handle:
            handle.close()


def _read_head_rows(source: FileSource, file_name: str) -> list[tuple[str, list[list[Any]], str]]:
    """Read only the first 40 rows of each worksheet for header detection."""

    name = (file_name or "").casefold()
    is_csv = name.endswith(".csv")
    is_xlsx = name.endswith(".xlsx")

    if not is_csv and not is_xlsx:
        head = source[:2] if isinstance(source, bytes) else b""
        if head == b"PK" or name.endswith((".xlsm", ".xltx", ".xltm")):
            is_xlsx = True
        else:
            is_csv = True

    if is_csv:
        rows: list[list[Any]] = []
        for index, values in _iter_csv_rows(source, file_name, start_row=1):
            rows.append(values)
            if index >= HEADER_SCAN_ROWS:
                break
        return [("CSV", rows, "csv")]

    workbook = _open_workbook(source, file_name)
    try:
        sheets: list[tuple[str, list[list[Any]], str]] = []
        for worksheet in workbook.worksheets:
            rows: list[list[Any]] = []
            for index, values in enumerate(
                worksheet.iter_rows(min_row=1, max_row=HEADER_SCAN_ROWS, values_only=True),
                start=1,
            ):
                rows.append(list(values))
                if index >= HEADER_SCAN_ROWS:
                    break
            sheets.append((worksheet.title, rows, "xlsx"))
        return sheets
    finally:
        workbook.close()


def _best_table_for_rows(
    rows: list[list[Any]],
    kind: str,
    sheet_name: str,
    source_kind: str,
    source: FileSource,
) -> Table | None:
    config = file_config(kind)
    required = [str(item) for item in config.get("required", [])]
    aliases = {
        canonical: [normalize_header(alias) for alias in values]
        for canonical, values in column_aliases(kind).items()
    }
    known_aliases = {alias for values in aliases.values() for alias in values}

    best: Table | None = None
    best_score = -1e9
    max_scan = min(max(len(rows), 1), HEADER_SCAN_ROWS)

    for header_index in range(max_scan):
        values = rows[header_index]
        headers = [clean_text(value) for value in values]
        normalized_headers = [normalize_header(value) for value in headers]
        header_index_map: dict[str, int] = {}
        duplicates: set[str] = set()
        for index, header in enumerate(normalized_headers):
            if not header:
                continue
            if header in header_index_map:
                duplicates.add(header)
            else:
                header_index_map[header] = index

        mapping: dict[str, int] = {}
        for canonical, alias_set in aliases.items():
            for alias in alias_set:
                if alias in header_index_map:
                    mapping[canonical] = header_index_map[alias]
                    break

        if not mapping:
            continue

        mapped_indices = set(mapping.values())
        sensitive = [
            headers[index]
            for index, header in enumerate(headers)
            if header and is_sensitive_header(header)
        ]
        unmapped = [
            headers[index]
            for index, header in enumerate(headers)
            if header and index not in mapped_indices and not is_sensitive_header(header)
        ]
        missing_required = [field for field in required if field not in mapping]
        duplicate_targets = [
            headers[header_index_map[header]]
            for header in duplicates
            if header in known_aliases
        ]

        score = (
            len(mapping)
            + (4 * len(required))
            - (4 * len(missing_required))
            - (header_index / 1000.0)
        )
        if score > best_score:
            best_score = score
            best = Table(
                sheet_name=sheet_name,
                header_row=header_index + 1,
                data_start_row=header_index + 2,
                mapping=mapping,
                headers=headers,
                sensitive_columns=sensitive,
                unmapped_columns=unmapped,
                missing_required=missing_required,
                duplicate_targets=duplicate_targets,
                source=source,
                title_rows=rows[:header_index],
                source_kind=source_kind,
            )

    return best


def _is_totals_row(values: list[Any]) -> bool:
    for value in values:
        normalized = " ".join(clean_text(value).casefold().split())
        if normalized == "total" or normalized.startswith("total "):
            return True
    return False


def _headerless_portfolio_table(
    rows: list[list[Any]],
    sheet_name: str,
    source_kind: str,
    source: FileSource,
) -> Table:
    data_start: int | None = None
    for index, values in enumerate(rows):
        cells = [clean_text(value) for value in values]
        if len(cells) < 13 or not cells[0]:
            continue
        first = cells[0].casefold()
        if first.startswith(("portfolio", "report", "total", "unnamed")):
            continue
        if parse_decimal(cells[6]) is not None or parse_decimal(cells[5]) is not None:
            data_start = index + 1
            break

    if data_start is None:
        raise WorkbookError(
            "The Portfolio Valuation file has no header row and does not match "
            "the expected 13-column InvestWell layout. Re-export the report with "
            "a header or use the documented 13-column layout."
        )

    warning = (
        "The Portfolio Valuation file has no header row. The fixed 13-column "
        "InvestWell layout was used (client name, app code, IWELL code, PAN, "
        "balance units, purchase value, current value, one-day change, dividend, "
        "average holding days, gain, absolute return, CAGR). PAN is ignored."
    )
    return Table(
        sheet_name=sheet_name,
        header_row=None,
        data_start_row=data_start,
        mapping=dict(PORTFOLIO_HEADERLESS_MAPPING),
        headers=list(PORTFOLIO_HEADERLESS_HEADERS),
        sensitive_columns=["PAN"],
        unmapped_columns=[],
        missing_required=[],
        duplicate_targets=[],
        source=source,
        title_rows=rows[: max(0, data_start - 1)],
        headerless=True,
        layout_warning=warning,
        source_kind=source_kind,
    )


def _tables_for_rows(
    rows: list[list[Any]],
    kind: str,
    sheet_name: str,
    source_kind: str,
    source: FileSource,
) -> Table | None:
    table = _best_table_for_rows(rows, kind, sheet_name, source_kind, source)
    if table is not None:
        return table
    if kind == "portfolio":
        return _headerless_portfolio_table(rows, sheet_name, source_kind, source)
    return None


def load_table(source: FileSource, file_name: str, kind: str) -> Table | None:
    """Find the best table from an XLSX workbook or a CSV file.

    ``None`` means that no usable header was found in a normal table.  A
    malformed headerless Portfolio file raises ``WorkbookError`` so the import is
    blocked rather than guessed.
    """

    sheets = _read_head_rows(source, file_name)
    best: Table | None = None
    best_score = -1e9
    headerless_error: WorkbookError | None = None
    for sheet_name, rows, source_kind in sheets:
        try:
            table = _tables_for_rows(
                rows,
                kind,
                sheet_name,
                source_kind,
                source,
            )
        except WorkbookError as exc:
            headerless_error = exc
            continue
        if table is None:
            continue
        score = len(table.mapping) - (4 * len(table.missing_required))
        if score > best_score:
            best = table
            best_score = score
    if best is None and headerless_error is not None:
        raise headerless_error
    return best


def extract_report_date(table: Table) -> tuple[date | None, str | None, str]:
    """Find the Portfolio report date in the title rows above the data."""

    formats = date_formats()
    for values in table.title_rows:
        for index, value in enumerate(values):
            text = clean_text(value)
            if not text:
                continue
            match = _REPORT_DATE_RE.search(text)
            if not match:
                continue
            remainder = clean_text(match.group(1))
            candidate = remainder
            if not candidate:
                candidate = next(
                    (
                        clean_text(item)
                        for item in values[index + 1 :]
                        if clean_text(item)
                    ),
                    "",
                )
            parsed, fmt, status = parse_date_value(candidate, formats)
            if parsed is not None:
                return parsed, fmt, "ok"
            if status == "invalid":
                return None, None, "invalid"
    return None, None, "missing"
