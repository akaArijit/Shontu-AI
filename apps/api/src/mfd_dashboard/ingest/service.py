"""Build and confirm a four-file InvestWell snapshot import.

The preview is a JSON plan containing only whitelisted, normalized values.  Raw
uploads are read from temporary local files and deleted when the request ends;
they are not kept as part of the snapshot.  Confirming the preview replaces the
previous local snapshot so the dashboard always represents one consistent
export run.
"""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from mfd_dashboard.benchmarks import match_benchmark
from mfd_dashboard.calculations import classify_transaction
from mfd_dashboard.core.paths import PREVIEWS_DIR
from mfd_dashboard.db.models import (
    Client,
    ClientIdentifier,
    Folio,
    ImportIssue,
    PortfolioValuation,
    Scheme,
    SchemeBenchmark,
    Transaction,
    UploadBatch,
)
from mfd_dashboard.ingest.config import date_formats, file_config
from mfd_dashboard.ingest.values import (
    clean_code,
    clean_text,
    key_for_name,
    normalize_code,
    normalize_folio,
    parse_date_value,
    parse_decimal,
)
from mfd_dashboard.ingest.xlsx import (
    FileSource,
    Table,
    WorkbookError,
    extract_report_date,
    load_table,
)

KINDS = ("clients", "folios", "portfolio", "transactions")
REQUIRED_KINDS = ("clients", "folios", "portfolio")
FILE_LABELS = {
    "clients": "Client Details",
    "folios": "Folios",
    "portfolio": "Portfolio Valuation",
    "transactions": "Transaction Statement",
}
ONE_RUPEE = Decimal("1.00")
MAX_STORED_ISSUES = 500
MAX_PREVIEW_ISSUES = 200
_FILENAME_DATE_RE = re.compile(
    r"(?<!\d)(\d{1,2})[-_/.](\d{1,2})[-_/.](\d{2,4})(?!\d)|"
    r"(?<!\d)(\d{4})[-_/.](\d{1,2})[-_/.](\d{1,2})(?!\d)"
)


@dataclass
class Issue:
    file_type: str
    row_number: int | None
    field: str | None
    message: str
    severity: str = "warning"

    def as_dict(self) -> dict[str, Any]:
        return {
            "file_type": self.file_type,
            "row_number": self.row_number,
            "field": self.field,
            "message": self.message,
            "severity": self.severity,
        }


@dataclass
class ParsedClient:
    source_row: int
    name: str
    iwell_code: str | None
    iwell_code_2: str | None
    app_code: str | None
    first_investment_date: date | None
    dedupe_key: str


@dataclass
class ParsedFolio:
    source_row: int
    client_name: str
    iwell_code: str | None
    iwell_code_2: str | None
    app_code: str | None
    folio_number: str
    scheme_name: str
    folio_type: str | None
    units: Decimal | None
    aum: Decimal | None


@dataclass
class ParsedValuation:
    source_row: int
    client_name: str
    iwell_code: str | None
    iwell_code_2: str | None
    app_code: str | None
    balance_units: Decimal | None
    purchase_value: Decimal | None
    current_value: Decimal | None
    gain: Decimal | None
    absolute_return: Decimal | None
    cagr: Decimal | None
    avg_holding_days: int | None
    one_day_change: Decimal | None
    dividend: Decimal | None


@dataclass
class ParsedTransaction:
    source_row: int
    transaction_date: date | None
    transaction_type_raw: str
    transaction_type: str
    amount: Decimal | None
    units: Decimal | None
    nav: Decimal | None
    folio_number: str
    scheme_name: str
    client_name: str
    iwell_code: str | None
    iwell_code_2: str | None
    app_code: str | None
    source_scheme_name: str | None
    target_scheme_name: str | None
    description: str | None
    sip_reg_date: date | None


@dataclass
class ParsedFile:
    kind: str
    name: str
    row_count: int = 0
    rows_read: int = 0
    blank_rows: int = 0
    total_rows: int = 0
    duplicate_rows: int = 0
    missing_required_rows: int = 0
    invalid_date_rows: int = 0
    invalid_number_rows: int = 0
    invalid_number_row_numbers: set[int] = field(
        default_factory=set,
        repr=False,
    )
    records: list[Any] = field(default_factory=list)
    issues: list[Issue] = field(default_factory=list)
    detected: dict[str, Any] = field(default_factory=dict)
    report_date: date | None = None
    report_date_format: str | None = None
    total_values: dict[str, Decimal | None] = field(default_factory=dict)
    total_row_found: bool = False
    supplied: bool = True
    skip_reasons: Counter[str] = field(default_factory=Counter)


def _add_issue(
    issues: list[Issue],
    file_type: str,
    row_number: int | None,
    field_name: str | None,
    message: str,
    severity: str = "warning",
) -> None:
    issues.append(
        Issue(
            file_type=file_type,
            row_number=row_number,
            field=field_name,
            message=message,
            severity=severity,
        )
    )


def _number(
    value: Any,
    *,
    file_type: str,
    row_number: int,
    field_name: str,
    issues: list[Issue],
    blank_message: str | None = None,
    integer: bool = False,
    parsed_file: ParsedFile | None = None,
) -> Decimal | int | None:
    text = clean_text(value)
    if not text:
        if blank_message:
            _add_issue(issues, file_type, row_number, field_name, blank_message)
        return None

    parsed = parse_decimal(value)
    if parsed is None:
        if (
            parsed_file is not None
            and row_number not in parsed_file.invalid_number_row_numbers
        ):
            parsed_file.invalid_number_row_numbers.add(row_number)
            parsed_file.invalid_number_rows += 1
        _add_issue(
            issues,
            file_type,
            row_number,
            field_name,
            f"{field_name} could not be read as a number; marked Not available.",
        )
        return None

    if integer:
        if parsed != parsed.to_integral_value():
            if (
                parsed_file is not None
                and row_number not in parsed_file.invalid_number_row_numbers
            ):
                parsed_file.invalid_number_row_numbers.add(row_number)
                parsed_file.invalid_number_rows += 1
            _add_issue(
                issues,
                file_type,
                row_number,
                field_name,
                f"{field_name} is not a whole number; marked Not available.",
            )
            return None
        return int(parsed)
    return parsed


def _missing_table(kind: str) -> dict[str, Any]:
    required = [str(item) for item in file_config(kind).get("required", [])]
    return {
        "file_type": kind,
        "sheet": None,
        "header_row": None,
        "mapping": {},
        "headers": [],
        "unmapped_columns": [],
        "ignored_sensitive_columns": [],
        "missing_required": required,
        "duplicate_targets": [],
    }


def _parse_clients(table: Table, name: str) -> ParsedFile:
    parsed = ParsedFile(
        kind="clients",
        name=name,
        detected=table.detected("clients"),
    )
    if table.missing_required:
        for field_name in table.missing_required:
            _add_issue(
                parsed.issues,
                "clients",
                None,
                field_name,
                f"Required column '{field_name.replace('_', ' ').upper()}' was not found in the Client Details workbook.",
                "error",
            )

    added: set[str] = set()
    formats = date_formats()
    for row_number, row in table.data_rows():
        parsed.rows_read += 1
        if not any(clean_text(value) for value in row):
            parsed.blank_rows += 1
            continue
        if _is_total_row(row):
            parsed.total_rows += 1
            continue
        parsed.row_count += 1

        client_name = clean_text(table.value(row, "name"))
        iwell_code = clean_code(table.value(row, "iwell_code")) or None
        iwell_code_2 = clean_code(table.value(row, "iwell_code_2")) or None
        app_code = clean_code(table.value(row, "app_code")) or None

        if not client_name:
            parsed.missing_required_rows += 1
            parsed.skip_reasons["missing_required_fields"] += 1
            _add_issue(
                parsed.issues,
                "clients",
                row_number,
                "name",
                "Client name is blank; the row was skipped.",
            )
            continue

        dedupe_key = (
            normalize_code(iwell_code)
            or normalize_code(iwell_code_2)
            or normalize_code(app_code)
            or key_for_name(client_name)
        )
        if dedupe_key in added:
            parsed.duplicate_rows += 1
            parsed.skip_reasons["duplicate"] += 1
            _add_issue(
                parsed.issues,
                "clients",
                row_number,
                "IWELL CODE",
                "Duplicate client row; the first row was kept.",
            )
            continue
        added.add(dedupe_key)

        raw_first_date = table.value(row, "first_investment_date")
        first_date, _, date_status = parse_date_value(raw_first_date, formats)
        if date_status == "invalid":
            parsed.invalid_date_rows += 1
            _add_issue(
                parsed.issues,
                "clients",
                row_number,
                "First Investment Date",
                "First Investment Date could not be read; marked Not available.",
            )

        if not (iwell_code or iwell_code_2 or app_code):
            _add_issue(
                parsed.issues,
                "clients",
                row_number,
                "IWELL CODE",
                "No client code is present; exact client-name matching will be used as a fallback.",
                "info",
            )

        parsed.records.append(
            ParsedClient(
                source_row=row_number,
                name=client_name,
                iwell_code=iwell_code,
                iwell_code_2=iwell_code_2,
                app_code=app_code,
                first_investment_date=first_date,
                dedupe_key=dedupe_key,
            )
        )
    return parsed


def _parse_folios(table: Table, name: str) -> ParsedFile:
    parsed = ParsedFile(
        kind="folios",
        name=name,
        detected=table.detected("folios"),
    )
    if table.missing_required:
        for field_name in table.missing_required:
            _add_issue(
                parsed.issues,
                "folios",
                None,
                field_name,
                f"Required column '{field_name.replace('_', ' ').upper()}' was not found in the Folios workbook.",
                "error",
            )

    for row_number, row in table.data_rows():
        parsed.rows_read += 1
        if not any(clean_text(value) for value in row):
            parsed.blank_rows += 1
            continue
        if _is_total_row(row):
            parsed.total_rows += 1
            continue
        parsed.row_count += 1

        folio_number = clean_text(table.value(row, "folio_number"))
        scheme_name = clean_text(table.value(row, "scheme_name"))

        if not folio_number or not scheme_name:
            parsed.missing_required_rows += 1
            parsed.skip_reasons["missing_required_fields"] += 1
            _add_issue(
                parsed.issues,
                "folios",
                row_number,
                "FOLIO NO / SCHEME NAME",
                "Incomplete folio row skipped: both a folio number and a scheme name are required.",
            )
            continue

        units = _number(
            table.value(row, "units"),
            file_type="folios",
            row_number=row_number,
            field_name="UNITS",
            issues=parsed.issues,
            parsed_file=parsed,
        )
        aum = _number(
            table.value(row, "aum"),
            file_type="folios",
            row_number=row_number,
            field_name="AUM",
            issues=parsed.issues,
            blank_message="Folio AUM is blank; current value is shown as Not available.",
            parsed_file=parsed,
        )

        parsed.records.append(
            ParsedFolio(
                source_row=row_number,
                client_name=clean_text(table.value(row, "client_name")),
                iwell_code=clean_code(table.value(row, "iwell_code")) or None,
                iwell_code_2=clean_code(table.value(row, "iwell_code_2")) or None,
                app_code=clean_code(table.value(row, "app_code")) or None,
                folio_number=folio_number,
                scheme_name=scheme_name,
                folio_type=clean_text(table.value(row, "folio_type")) or None,
                units=units if isinstance(units, Decimal) else None,
                aum=aum if isinstance(aum, Decimal) else None,
            )
        )
    return parsed


def _is_total_row(row: tuple[Any, ...]) -> bool:
    for value in row:
        normalized = " ".join(clean_text(value).casefold().split())
        if normalized == "total" or normalized.startswith("total "):
            return True
    return False


def _parse_portfolio(table: Table, name: str) -> ParsedFile:
    parsed = ParsedFile(
        kind="portfolio",
        name=name,
        detected=table.detected("portfolio"),
    )
    if table.missing_required:
        for field_name in table.missing_required:
            _add_issue(
                parsed.issues,
                "portfolio",
                None,
                field_name,
                f"Required column '{field_name.replace('_', ' ').upper()}' was not found in the Portfolio Valuation workbook.",
                "error",
            )

    report_date, report_format, report_status = extract_report_date(table)
    parsed.report_date = report_date
    parsed.report_date_format = report_format
    if report_status == "missing":
        _add_issue(
            parsed.issues,
            "portfolio",
            None,
            "Report printed on",
            "The Portfolio Valuation report date was not found. The import needs a report date before it can be confirmed.",
            "error",
        )
    elif report_status == "invalid":
        _add_issue(
            parsed.issues,
            "portfolio",
            None,
            "Report printed on",
            "The Portfolio Valuation report date could not be read. Use a date such as 27-10-2026.",
            "error",
        )

    for row_number, row in table.data_rows():
        parsed.rows_read += 1
        if not any(clean_text(value) for value in row):
            parsed.blank_rows += 1
            continue
        if _is_total_row(row):
            parsed.total_rows += 1
            parsed.total_row_found = True
            for field_name, canonical in (
                ("BALANCE UNITS", "balance_units"),
                ("PURCHASE VALUE", "purchase_value"),
                ("CURRENT VALUE", "current_value"),
            ):
                value = _number(
                    table.value(row, canonical),
                    file_type="portfolio",
                    row_number=row_number,
                    field_name=field_name,
                    issues=[],
                )
                parsed.total_values[canonical] = (
                    value if isinstance(value, Decimal) else None
                )
            continue
        parsed.row_count += 1

        client_name = clean_text(table.value(row, "client_name"))
        iwell_code = clean_code(table.value(row, "iwell_code")) or None
        iwell_code_2 = clean_code(table.value(row, "iwell_code_2")) or None
        app_code = clean_code(table.value(row, "app_code")) or None

        if not (client_name or iwell_code or iwell_code_2 or app_code):
            parsed.missing_required_rows += 1
            parsed.skip_reasons["missing_required_fields"] += 1
            _add_issue(
                parsed.issues,
                "portfolio",
                row_number,
                "CLIENT NAME / IWELL CODE",
                "Portfolio row has no client identifier; the row was skipped.",
            )
            continue

        current_value = _number(
            table.value(row, "current_value"),
            file_type="portfolio",
            row_number=row_number,
            field_name="CURRENT VALUE",
            issues=parsed.issues,
            blank_message="Client current value is blank; shown as Not available.",
            parsed_file=parsed,
        )
        purchase_value = _number(
            table.value(row, "purchase_value"),
            file_type="portfolio",
            row_number=row_number,
            field_name="PURCHASE VALUE",
            issues=parsed.issues,
            parsed_file=parsed,
        )
        gain = _number(
            table.value(row, "gain"),
            file_type="portfolio",
            row_number=row_number,
            field_name="GAIN",
            issues=parsed.issues,
            parsed_file=parsed,
        )
        absolute_return = _number(
            table.value(row, "absolute_return"),
            file_type="portfolio",
            row_number=row_number,
            field_name="ABSOLUTE RETURN",
            issues=parsed.issues,
            parsed_file=parsed,
        )
        cagr = _number(
            table.value(row, "cagr"),
            file_type="portfolio",
            row_number=row_number,
            field_name="CAGR",
            issues=parsed.issues,
            parsed_file=parsed,
        )
        avg_holding_days = _number(
            table.value(row, "avg_holding_days"),
            file_type="portfolio",
            row_number=row_number,
            field_name="AVG HOLDING DAYS",
            issues=parsed.issues,
            integer=True,
            parsed_file=parsed,
        )
        one_day_change = _number(
            table.value(row, "one_day_change"),
            file_type="portfolio",
            row_number=row_number,
            field_name="ONE DAY CHANGE",
            issues=parsed.issues,
            parsed_file=parsed,
        )
        dividend = _number(
            table.value(row, "dividend"),
            file_type="portfolio",
            row_number=row_number,
            field_name="DIVIDEND",
            issues=parsed.issues,
            parsed_file=parsed,
        )
        balance_units = _number(
            table.value(row, "balance_units"),
            file_type="portfolio",
            row_number=row_number,
            field_name="BALANCE UNITS",
            issues=parsed.issues,
            parsed_file=parsed,
        )

        parsed.records.append(
            ParsedValuation(
                source_row=row_number,
                client_name=client_name,
                iwell_code=iwell_code,
                iwell_code_2=iwell_code_2,
                app_code=app_code,
                balance_units=balance_units
                if isinstance(balance_units, Decimal)
                else None,
                purchase_value=purchase_value
                if isinstance(purchase_value, Decimal)
                else None,
                current_value=current_value
                if isinstance(current_value, Decimal)
                else None,
                gain=gain if isinstance(gain, Decimal) else None,
                absolute_return=absolute_return
                if isinstance(absolute_return, Decimal)
                else None,
                cagr=cagr if isinstance(cagr, Decimal) else None,
                avg_holding_days=avg_holding_days
                if isinstance(avg_holding_days, int)
                else None,
                one_day_change=one_day_change
                if isinstance(one_day_change, Decimal)
                else None,
                dividend=dividend if isinstance(dividend, Decimal) else None,
            )
        )
    return parsed


def _parse_transactions(table: Table, name: str) -> ParsedFile:
    parsed = ParsedFile(
        kind="transactions",
        name=name,
        detected=table.detected("transactions"),
    )
    if table.missing_required:
        for field_name in table.missing_required:
            _add_issue(
                parsed.issues,
                "transactions",
                None,
                field_name,
                f"Required column '{field_name.replace('_', ' ').upper()}' was not found in the Transaction Statement.",
                "error",
            )

    formats = date_formats()
    exact_rows: set[tuple[str, ...]] = set()
    for row_number, row in table.data_rows():
        parsed.rows_read += 1
        if not any(clean_text(value) for value in row):
            parsed.blank_rows += 1
            continue
        if _is_total_row(row):
            parsed.total_rows += 1
            continue
        parsed.row_count += 1

        raw_type = clean_text(table.value(row, "txn_type"))
        description = clean_text(table.value(row, "description"))
        source_scheme = clean_text(table.value(row, "source_scheme_name"))
        target_scheme = clean_text(table.value(row, "target_scheme_name"))
        transaction_type = classify_transaction(
            raw_type,
            description=description,
            source_scheme_name=source_scheme,
            target_scheme_name=target_scheme,
        )

        # Only exact duplicate statement lines are removed.  Two legitimate SIP
        # instalments with the same date and amount usually differ in units/nav
        # or description, so those remain separate rows.
        duplicate_key = tuple(
            clean_text(value).casefold() for value in row
        )
        if duplicate_key in exact_rows:
            parsed.duplicate_rows += 1
            parsed.skip_reasons["duplicate"] += 1
            _add_issue(
                parsed.issues,
                "transactions",
                row_number,
                "ROW",
                "Exact duplicate transaction row skipped; the first occurrence was kept.",
            )
            continue
        exact_rows.add(duplicate_key)

        raw_date = table.value(row, "transaction_date")
        transaction_date, _, date_status = parse_date_value(raw_date, formats)
        if date_status in {"missing", "invalid", "ambiguous"}:
            parsed.invalid_date_rows += 1
            _add_issue(
                parsed.issues,
                "transactions",
                row_number,
                "TRANSACTION DATE",
                "Transaction date is missing or could not be read; this transaction is excluded from holding-period and return calculations.",
                "warning",
            )

        amount = _number(
            table.value(row, "amount"),
            file_type="transactions",
            row_number=row_number,
            field_name="TOTAL AMOUNT",
            issues=parsed.issues,
            blank_message="Transaction amount is blank; this transaction is excluded from return calculations.",
            parsed_file=parsed,
        )
        amount_value = amount if isinstance(amount, Decimal) else None
        if amount_value is not None and amount_value == 0:
            _add_issue(
                parsed.issues,
                "transactions",
                row_number,
                "TOTAL AMOUNT",
                "Transaction amount is zero; it is excluded from return calculations.",
                "warning",
            )

        folio_number = clean_text(table.value(row, "folio_number"))
        scheme_name = clean_text(table.value(row, "scheme_name"))
        if not folio_number:
            _add_issue(
                parsed.issues,
                "transactions",
                row_number,
                "FOLIO NO",
                "Transaction has no folio number and cannot be matched to a Folios row.",
                "warning",
            )
        if not scheme_name:
            _add_issue(
                parsed.issues,
                "transactions",
                row_number,
                "SCHEME NAME",
                "Transaction has no scheme name and cannot be matched to a Folios row.",
                "warning",
            )

        if transaction_type == "unknown":
            _add_issue(
                parsed.issues,
                "transactions",
                row_number,
                "TXN TYPE",
                f"Unknown transaction type '{raw_type or '(blank)'}'; it is excluded from return calculations and needs review.",
                "warning",
            )

        units = _number(
            table.value(row, "units"),
            file_type="transactions",
            row_number=row_number,
            field_name="UNITS",
            issues=parsed.issues,
            parsed_file=parsed,
        )
        nav = _number(
            table.value(row, "nav"),
            file_type="transactions",
            row_number=row_number,
            field_name="NAV",
            issues=parsed.issues,
            parsed_file=parsed,
        )
        sip_reg_date, _, _ = parse_date_value(
            table.value(row, "sip_reg_date"), formats
        )

        parsed.records.append(
            ParsedTransaction(
                source_row=row_number,
                transaction_date=transaction_date,
                transaction_type_raw=raw_type,
                transaction_type=transaction_type,
                amount=amount_value,
                units=units if isinstance(units, Decimal) else None,
                nav=nav if isinstance(nav, Decimal) else None,
                folio_number=folio_number,
                scheme_name=scheme_name,
                client_name=clean_text(table.value(row, "client_name")),
                iwell_code=clean_code(table.value(row, "iwell_code")) or None,
                iwell_code_2=clean_code(table.value(row, "iwell_code_2")) or None,
                app_code=clean_code(table.value(row, "app_code")) or None,
                source_scheme_name=source_scheme or None,
                target_scheme_name=target_scheme or None,
                description=description or None,
                sip_reg_date=sip_reg_date,
            )
        )
    return parsed


def parse_file(source: FileSource, name: str, kind: str) -> ParsedFile:
    if kind not in KINDS:
        raise ValueError(f"Unknown import file type: {kind}")
    table = load_table(source, name, kind)
    if table is None:
        parsed = ParsedFile(
            kind=kind,
            name=name,
            detected=_missing_table(kind),
        )
        _add_issue(
            parsed.issues,
            kind,
            None,
            None,
            f"Could not find the expected header row in {name}. "
            "Check that this is the correct InvestWell export.",
            "error",
        )
        return parsed

    if kind == "clients":
        return _parse_clients(table, name)
    if kind == "folios":
        return _parse_folios(table, name)
    if kind == "portfolio":
        return _parse_portfolio(table, name)
    return _parse_transactions(table, name)


def _file_info(name: str, source: FileSource) -> dict[str, Any]:
    if isinstance(source, Path):
        size = source.stat().st_size
        digest = hashlib.sha256()
        with source.open("rb") as handle:
            while chunk := handle.read(1024 * 1024):
                digest.update(chunk)
        return {
            "name": name,
            "size": size,
            "sha256": digest.hexdigest(),
        }
    return {
        "name": name,
        "size": len(source),
        "sha256": hashlib.sha256(source).hexdigest(),
    }


def _client_search_indexes(
    clients: list[ParsedClient],
) -> tuple[dict[tuple[str, str], list[int]], dict[str, list[int]]]:
    code_index: dict[tuple[str, str], list[int]] = defaultdict(list)
    name_index: dict[str, list[int]] = defaultdict(list)
    for ref, client in enumerate(clients):
        if client.iwell_code:
            code_index[("iwell_code", normalize_code(client.iwell_code))].append(ref)
        if client.iwell_code_2:
            code_index[("iwell_code_2", normalize_code(client.iwell_code_2))].append(
                ref
            )
        if client.app_code:
            code_index[("app_code", normalize_code(client.app_code))].append(ref)
        name_index[key_for_name(client.name)].append(ref)
    return code_index, name_index


def _match_client(
    *,
    iwell_code: str | None,
    iwell_code_2: str | None,
    app_code: str | None,
    client_name: str,
    code_index: dict[tuple[str, str], list[int]],
    name_index: dict[str, list[int]],
) -> tuple[int | None, str | None, str | None]:
    for identifier_type, value in (
        ("iwell_code", iwell_code),
        ("iwell_code_2", iwell_code_2),
        ("app_code", app_code),
    ):
        if not value:
            continue
        matches = code_index.get((identifier_type, normalize_code(value)), [])
        if len(matches) == 1:
            return matches[0], identifier_type, None
        if len(matches) > 1:
            return (
                None,
                identifier_type,
                f"{identifier_type} matches more than one client in Client Details.",
            )

    if client_name:
        matches = name_index.get(key_for_name(client_name), [])
        if len(matches) == 1:
            return matches[0], "name", None
        if len(matches) > 1:
            return (
                None,
                "name",
                "Client name matches more than one client in Client Details.",
            )

    return None, None, "No matching client was found in Client Details."


def _as_text(value: Decimal | int | None) -> str | None:
    if value is None:
        return None
    return str(value)


def _source_client_key(
    *,
    iwell_code: str | None,
    iwell_code_2: str | None,
    app_code: str | None,
    client_name: str,
    source_row: int,
) -> str:
    return (
        normalize_code(iwell_code)
        or normalize_code(iwell_code_2)
        or normalize_code(app_code)
        or key_for_name(client_name)
        or f"row-{source_row}"
    )


def _filename_dates(name: str) -> list[date]:
    """Extract plausible export dates from an InvestWell filename."""

    found: set[date] = set()
    for match in _FILENAME_DATE_RE.finditer(name or ""):
        groups = match.groups()
        try:
            if groups[0] is not None:
                day = int(groups[0])
                month = int(groups[1])
                year = int(groups[2])
                if year < 100:
                    year += 2000
            else:
                year = int(groups[3])
                month = int(groups[4])
                day = int(groups[5])
            found.add(date(year, month, day))
        except (TypeError, ValueError):
            continue
    return sorted(found)


def _export_run_check(
    files: dict[str, tuple[str, FileSource]],
    report_date: date | None,
) -> dict[str, Any]:
    per_file: dict[str, dict[str, Any]] = {}
    latest_dates: list[date] = []
    for kind in KINDS:
        if kind not in files:
            continue
        name = files[kind][0]
        dates = _filename_dates(name)
        per_file[kind] = {
            "file_name": name,
            "dates": [item.isoformat() for item in dates],
            "latest_date": dates[-1].isoformat() if dates else None,
        }
        if dates:
            latest_dates.append(dates[-1])

    distinct = sorted({item for item in latest_dates})
    mismatched = bool(report_date and distinct and any(item != report_date for item in distinct))
    if mismatched:
        message = (
            "The file names point to different export dates ("
            + ", ".join(item.isoformat() for item in distinct)
            + "). Confirm that all four files came from the same InvestWell export run."
        )
        status = "review"
    elif report_date and distinct:
        message = (
            "All file names with a date point to the same export run: "
            f"{report_date.isoformat()}."
        )
        status = "consistent"
    else:
        message = (
            "The file names do not all include an export date. Check that the "
            "four files came from the same InvestWell export run."
        )
        status = "unconfirmed"
    return {
        "status": status,
        "message": message,
        "report_date": report_date.isoformat() if report_date else None,
        "files": per_file,
    }


def _file_skip_reasons(parsed: ParsedFile, imported: int) -> list[dict[str, Any]]:
    reasons: list[tuple[str, str, int]] = [
        ("blank", "blank rows", parsed.blank_rows),
        ("total", "total/summary rows", parsed.total_rows),
        ("duplicate", "duplicate rows", parsed.duplicate_rows),
        (
            "missing_required_fields",
            "rows with missing required fields",
            parsed.missing_required_rows,
        ),
    ]
    reason_total = sum(item[2] for item in reasons)
    skipped = max(0, parsed.rows_read - imported)
    if skipped > reason_total:
        reasons.append(("other", "other unreadable rows", skipped - reason_total))
    return [
        {"key": key, "label": label, "count": count}
        for key, label, count in reasons
        if count > 0
    ]


def _file_reports(
    parsed: dict[str, ParsedFile],
    *,
    clients_imported: int,
    folios_imported: int,
    portfolio_imported: int,
    transactions_imported: int,
    folios_unmatched: int,
    portfolio_unmatched: int,
    transactions_unmatched: int,
) -> dict[str, dict[str, Any]]:
    imported_by_kind = {
        "clients": clients_imported,
        "folios": folios_imported,
        "portfolio": portfolio_imported,
        "transactions": transactions_imported,
    }
    unmatched_by_kind = {
        "clients": 0,
        "folios": folios_unmatched,
        "portfolio": portfolio_unmatched,
        "transactions": transactions_unmatched,
    }
    reports: dict[str, dict[str, Any]] = {}
    for kind in KINDS:
        item = parsed[kind]
        if not item.supplied:
            reports[kind] = {
                "file_type": kind,
                "label": FILE_LABELS[kind],
                "supplied": False,
                "rows_read": 0,
                "imported_rows": 0,
                "matched_rows": None,
                "unmatched_rows": None,
                "skipped_rows": 0,
                "blank_rows": 0,
                "total_rows": 0,
                "duplicate_rows": 0,
                "invalid_date_rows": 0,
                "invalid_number_rows": 0,
                "header_ok": True,
                "message": "Not supplied.",
                "reasons": [],
            }
            continue
        imported = imported_by_kind[kind]
        unmatched = unmatched_by_kind[kind] if kind != "clients" else None
        matched = imported - unmatched if unmatched is not None else None
        skipped = max(0, item.rows_read - imported)
        header_ok = not item.detected.get("missing_required")
        label = FILE_LABELS[kind]
        if item.rows_read == 0 and not header_ok:
            message = f"{label}: no usable data table was found."
        elif kind == "transactions":
            message = (
                f"{label}: {item.rows_read:,} rows read, "
                f"{matched or 0:,} matched to folios, "
                f"{unmatched or 0:,} unmatched, {skipped:,} skipped."
            )
        elif kind == "clients":
            message = (
                f"{label}: {item.rows_read:,} rows read, "
                f"{imported:,} valid clients, {skipped:,} skipped."
            )
        else:
            message = (
                f"{label}: {item.rows_read:,} rows read, "
                f"{imported:,} valid rows, {skipped:,} skipped, "
                f"{matched or 0:,} matched to clients."
            )
        reports[kind] = {
            "file_type": kind,
            "label": label,
            "supplied": True,
            "rows_read": item.rows_read,
            "imported_rows": imported,
            "matched_rows": matched,
            "unmatched_rows": unmatched,
            "skipped_rows": skipped,
            "blank_rows": item.blank_rows,
            "total_rows": item.total_rows,
            "duplicate_rows": item.duplicate_rows,
            "invalid_date_rows": item.invalid_date_rows,
            "invalid_number_rows": item.invalid_number_rows,
            "header_ok": header_ok,
            "message": message if header_ok else f"{label}: required columns are missing.",
            "reasons": _file_skip_reasons(item, imported),
        }
    return reports


def _client_matching_summary(
    *,
    clients: int,
    folios: int,
    folios_unmatched: int,
    portfolio: int,
    portfolio_unmatched: int,
    transactions: int | None,
    transactions_unmatched: int | None,
) -> dict[str, Any]:
    folios_matched = max(0, folios - folios_unmatched)
    portfolio_matched = max(0, portfolio - portfolio_unmatched)
    transactions_matched = (
        max(0, transactions - transactions_unmatched)
        if transactions is not None and transactions_unmatched is not None
        else None
    )
    unchecked_files = [
        label
        for label, total, matched in (
            ("folios", folios, folios_matched),
            ("portfolio rows", portfolio, portfolio_matched),
            ("transactions", transactions, transactions_matched),
        )
        if total is not None and total > 0 and matched == 0
    ]
    has_unmatched = bool(
        folios_unmatched
        or portfolio_unmatched
        or (transactions_unmatched or 0)
    )
    if clients == 0:
        status = "no_clients"
        message = "No valid clients were found in Client Details."
    elif unchecked_files:
        status = "review"
        message = (
            f"No {', '.join(unchecked_files)} matched a client. Check that all "
            "files came from the same InvestWell export run."
        )
    elif has_unmatched:
        status = "review"
        message = (
            "Some client keys do not match across files. Review the unmatched "
            "folios, portfolio rows and transactions before relying on the snapshot."
        )
    else:
        status = "matched"
        message = "All supplied client keys match across the files."
    return {
        "status": status,
        "message": message,
        "clients": clients,
        "folios": {
            "total": folios,
            "matched": folios_matched,
            "unmatched": folios_unmatched,
        },
        "portfolio": {
            "total": portfolio,
            "matched": portfolio_matched,
            "unmatched": portfolio_unmatched,
        },
        "transactions": (
            {
                "total": transactions,
                "matched": transactions_matched,
                "unmatched": transactions_unmatched,
            }
            if transactions is not None
            else None
        ),
    }


def _build_plan(
    parsed: dict[str, ParsedFile],
    files: dict[str, tuple[str, FileSource]],
) -> dict[str, Any]:
    clients: list[ParsedClient] = parsed["clients"].records
    issues: list[Issue] = [
        issue for item in parsed.values() for issue in item.issues
    ]
    code_index, name_index = _client_search_indexes(clients)

    if not clients:
        _add_issue(
            issues,
            "clients",
            None,
            None,
            "No usable client rows were found in the Client Details workbook.",
            "error",
        )

    portfolio_layout_warning = parsed["portfolio"].detected.get("layout_warning")
    if portfolio_layout_warning:
        _add_issue(
            issues,
            "portfolio",
            None,
            "HEADER",
            str(portfolio_layout_warning),
            "warning",
        )

    export_run = _export_run_check(files, parsed["portfolio"].report_date)
    if export_run["status"] == "review":
        _add_issue(
            issues,
            "portfolio",
            None,
            "EXPORT RUN",
            str(export_run["message"]),
            "warning",
        )
    elif export_run["status"] == "unconfirmed":
        _add_issue(
            issues,
            "portfolio",
            None,
            "EXPORT RUN",
            str(export_run["message"]),
            "info",
        )

    schemes: dict[str, dict[str, Any]] = {}
    folios: list[dict[str, Any]] = []
    folio_keys: set[str] = set()

    for row in parsed["folios"].records:
        assert isinstance(row, ParsedFolio)
        client_ref, matched_by, match_note = _match_client(
            iwell_code=row.iwell_code,
            iwell_code_2=row.iwell_code_2,
            app_code=row.app_code,
            client_name=row.client_name,
            code_index=code_index,
            name_index=name_index,
        )
        if client_ref is None:
            match_status = "unmatched"
            _add_issue(
                issues,
                "folios",
                row.source_row,
                "IWELL CODE / CLIENT NAME",
                f"Folio {row.folio_number} — {match_note} Marked Unmatched — needs review.",
            )
        elif matched_by == "name":
            match_status = "name_fallback"
            _add_issue(
                issues,
                "folios",
                row.source_row,
                "CLIENT NAME",
                f"Folio {row.folio_number} matched by exact client name. Please review.",
                "info",
            )
        else:
            match_status = "matched"

        client_key = (
            clients[client_ref].dedupe_key
            if client_ref is not None
            else _source_client_key(
                iwell_code=row.iwell_code,
                iwell_code_2=row.iwell_code_2,
                app_code=row.app_code,
                client_name=row.client_name,
                source_row=row.source_row,
            )
        )
        scheme_key = key_for_name(row.scheme_name)
        dedupe_key = f"{client_key}|{normalize_folio(row.folio_number)}|{scheme_key}"
        if dedupe_key in folio_keys:
            parsed["folios"].duplicate_rows += 1
            parsed["folios"].skip_reasons["duplicate"] += 1
            _add_issue(
                issues,
                "folios",
                row.source_row,
                "FOLIO NO / SCHEME NAME",
                f"Duplicate folio/scheme row skipped: {row.folio_number} — {row.scheme_name}.",
            )
            continue
        folio_keys.add(dedupe_key)

        if scheme_key not in schemes:
            schemes[scheme_key] = {
                "name": row.scheme_name,
                "name_key": scheme_key,
                "normalized_name": scheme_key,
                "benchmark_name": match_benchmark(row.scheme_name),
                "benchmark_status": "needs_review",
            }

        folios.append(
            {
                "source_row": row.source_row,
                "client_ref": client_ref,
                "match_status": match_status,
                "match_note": match_note,
                "dedupe_key": dedupe_key,
                "folio_number": row.folio_number,
                "normalized_folio_number": normalize_folio(row.folio_number),
                "scheme_key": scheme_key,
                "folio_type": row.folio_type,
                "units": _as_text(row.units),
                "aum": _as_text(row.aum),
                "source_client_name": row.client_name or None,
                "source_iwell_code": row.iwell_code or row.iwell_code_2 or row.app_code,
            }
        )

    if not folios:
        _add_issue(
            issues,
            "folios",
            None,
            None,
            "No usable folio rows were found. The import cannot be confirmed.",
            "error",
        )

    valuations: list[dict[str, Any]] = []
    valuation_keys: set[str] = set()
    for row in parsed["portfolio"].records:
        assert isinstance(row, ParsedValuation)
        client_ref, matched_by, match_note = _match_client(
            iwell_code=row.iwell_code,
            iwell_code_2=row.iwell_code_2,
            app_code=row.app_code,
            client_name=row.client_name,
            code_index=code_index,
            name_index=name_index,
        )
        if client_ref is None:
            match_status = "unmatched"
            _add_issue(
                issues,
                "portfolio",
                row.source_row,
                "IWELL CODE / CLIENT NAME",
                f"Portfolio row — {match_note} Marked Unmatched — needs review.",
            )
        elif matched_by == "name":
            match_status = "name_fallback"
            _add_issue(
                issues,
                "portfolio",
                row.source_row,
                "CLIENT NAME",
                "Portfolio row matched by exact client name. Please review.",
                "info",
            )
        else:
            match_status = "matched"

        client_key = (
            clients[client_ref].dedupe_key
            if client_ref is not None
            else _source_client_key(
                iwell_code=row.iwell_code,
                iwell_code_2=row.iwell_code_2,
                app_code=row.app_code,
                client_name=row.client_name,
                source_row=row.source_row,
            )
        )
        dedupe_key = client_key
        if dedupe_key in valuation_keys:
            parsed["portfolio"].duplicate_rows += 1
            parsed["portfolio"].skip_reasons["duplicate"] += 1
            _add_issue(
                issues,
                "portfolio",
                row.source_row,
                "IWELL CODE / CLIENT NAME",
                "Duplicate client valuation row skipped; one client-level value is kept per import.",
            )
            continue
        valuation_keys.add(dedupe_key)

        valuations.append(
            {
                "source_row": row.source_row,
                "client_ref": client_ref,
                "match_status": match_status,
                "match_note": match_note,
                "dedupe_key": dedupe_key,
                "balance_units": _as_text(row.balance_units),
                "purchase_value": _as_text(row.purchase_value),
                "current_value": _as_text(row.current_value),
                "gain": _as_text(row.gain),
                "absolute_return": _as_text(row.absolute_return),
                "cagr": _as_text(row.cagr),
                "avg_holding_days": row.avg_holding_days,
                "one_day_change": _as_text(row.one_day_change),
                "dividend": _as_text(row.dividend),
                "source_client_name": row.client_name or None,
                "source_iwell_code": row.iwell_code or row.iwell_code_2 or row.app_code,
            }
        )

    folio_by_key: dict[tuple[str, str], int] = {}
    folios_by_number: dict[str, list[int]] = defaultdict(list)
    for index, folio in enumerate(folios):
        normalized_number = folio["normalized_folio_number"]
        folio_by_key[(normalized_number, folio["scheme_key"])] = index
        folios_by_number[normalized_number].append(index)

    transaction_rows: list[dict[str, Any]] = []
    for row in parsed["transactions"].records:
        assert isinstance(row, ParsedTransaction)
        normalized_number = normalize_folio(row.folio_number)
        scheme_key = key_for_name(row.scheme_name)
        folio_ref = folio_by_key.get((normalized_number, scheme_key))
        match_status = "matched"
        review_note: str | None = None
        issue_message: str | None = None

        if not row.folio_number:
            match_status = "missing_folio"
            issue_message = "Transaction has no folio number and was not matched to a Folios row."
        elif not row.scheme_name:
            match_status = "missing_scheme"
            issue_message = "Transaction has no scheme name and was not matched to a Folios row."
        elif folio_ref is None:
            candidates = folios_by_number.get(normalized_number, [])
            if candidates:
                match_status = "scheme_mismatch"
                issue_message = (
                    f"Transaction folio {row.folio_number} was found in Folios, but the "
                    f"scheme name '{row.scheme_name}' does not match the Folios scheme. "
                    "The transaction was not matched."
                )
            else:
                match_status = "folio_not_found"
                issue_message = (
                    f"Transaction folio {row.folio_number} — {row.scheme_name} was not "
                    "found in the Folios export. The transaction was not matched."
                )

        transaction_client_ref, _, transaction_client_note = _match_client(
            iwell_code=row.iwell_code,
            iwell_code_2=row.iwell_code_2,
            app_code=row.app_code,
            client_name=row.client_name,
            code_index=code_index,
            name_index=name_index,
        )
        if folio_ref is not None:
            folio_client_ref = folios[folio_ref]["client_ref"]
            if (
                transaction_client_ref is not None
                and folio_client_ref is not None
                and transaction_client_ref != folio_client_ref
            ):
                review_note = (
                    "Transaction client does not match the client on the matched folio. "
                    "The folio match was kept and needs review."
                )
                _add_issue(
                    issues,
                    "transactions",
                    row.source_row,
                    "IWELL CODE / CLIENT NAME",
                    review_note,
                    "warning",
                )
            elif transaction_client_ref is None and (
                row.iwell_code or row.iwell_code_2 or row.app_code or row.client_name
            ):
                review_note = (
                    "Transaction client could not be matched to Client Details; the "
                    "folio match was used."
                )
                _add_issue(
                    issues,
                    "transactions",
                    row.source_row,
                    "IWELL CODE / CLIENT NAME",
                    f"{review_note} {transaction_client_note or ''}".strip(),
                    "info",
                )

        if issue_message:
            _add_issue(
                issues,
                "transactions",
                row.source_row,
                "FOLIO NO / SCHEME NAME",
                issue_message,
                "warning",
            )

        client_ref = (
            folios[folio_ref]["client_ref"] if folio_ref is not None else transaction_client_ref
        )
        transaction_rows.append(
            {
                "source_row": row.source_row,
                "folio_ref": folio_ref,
                "client_ref": client_ref,
                "scheme_key": folios[folio_ref]["scheme_key"] if folio_ref is not None else None,
                "transaction_date": (
                    row.transaction_date.isoformat() if row.transaction_date else None
                ),
                "transaction_type_raw": row.transaction_type_raw,
                "transaction_type": row.transaction_type,
                "amount": _as_text(row.amount),
                "units": _as_text(row.units),
                "nav": _as_text(row.nav),
                "source_scheme_name": row.source_scheme_name,
                "target_scheme_name": row.target_scheme_name,
                "description": row.description,
                "source_folio_number": row.folio_number,
                "normalized_folio_number": normalized_number,
                "source_iwell_code": row.iwell_code
                or row.iwell_code_2
                or row.app_code,
                "source_client_name": row.client_name or None,
                "match_status": match_status,
                "review_note": review_note,
                "switch_pair_key": None,
                "switch_review_status": None,
            }
        )

    switch_groups: dict[tuple[Any, str, Decimal], dict[str, list[int]]] = {}
    for index, item in enumerate(transaction_rows):
        if item["transaction_type"] not in {"switch_in", "switch_out"}:
            continue
        if (
            item["folio_ref"] is None
            or item["transaction_date"] is None
            or item["amount"] is None
            or Decimal(item["amount"]) == 0
        ):
            item["switch_review_status"] = "cannot_pair"
            _add_issue(
                issues,
                "transactions",
                item["source_row"],
                "SWITCH",
                "Switch leg cannot be paired because its folio, date or amount is missing or invalid.",
                "warning",
            )
            continue
        client_identity = (
            item["client_ref"]
            if item["client_ref"] is not None
            else (
                normalize_code(item.get("source_iwell_code"))
                or key_for_name(item.get("source_client_name") or "")
            )
        )
        group_key = (
            client_identity,
            item["transaction_date"],
            abs(Decimal(item["amount"])).quantize(Decimal("0.01")),
        )
        group = switch_groups.setdefault(group_key, {"switch_out": [], "switch_in": []})
        group[item["transaction_type"]].append(index)

    pair_number = 0
    switch_pairs = 0
    for group in switch_groups.values():
        outs = group["switch_out"]
        ins = group["switch_in"]
        if len(outs) == 1 and len(ins) == 1:
            pair_number += 1
            switch_pairs += 1
            pair_key = f"switch-{pair_number}"
            for index in (outs[0], ins[0]):
                transaction_rows[index]["switch_pair_key"] = pair_key
                transaction_rows[index]["switch_review_status"] = "paired"
            continue

        for index in outs:
            transaction_rows[index]["switch_review_status"] = (
                "ambiguous" if ins else "unpaired"
            )
            _add_issue(
                issues,
                "transactions",
                transaction_rows[index]["source_row"],
                "SWITCH",
                (
                    "Multiple switch legs share the same client, date and amount; "
                    "pairing is ambiguous and needs review."
                    if ins
                    else "Switch-out has no matching switch-in with the same client, date and amount. Review the missing leg."
                ),
                "warning",
            )
        for index in ins:
            transaction_rows[index]["switch_review_status"] = (
                "ambiguous" if outs else "unpaired"
            )
            _add_issue(
                issues,
                "transactions",
                transaction_rows[index]["source_row"],
                "SWITCH",
                (
                    "Multiple switch legs share the same client, date and amount; "
                    "pairing is ambiguous and needs review."
                    if outs
                    else "Switch-in has no matching switch-out with the same client, date and amount. Review the missing leg."
                ),
                "warning",
            )

    switch_reviews = sum(
        1
        for item in transaction_rows
        if item["switch_review_status"] in {"unpaired", "ambiguous", "cannot_pair"}
    )
    unknown_transactions = sum(
        1 for item in transaction_rows if item["transaction_type"] == "unknown"
    )
    unmatched_transactions = sum(
        1 for item in transaction_rows if item["match_status"] != "matched"
    )

    reconciliation: list[dict[str, Any]] = []
    folios_by_client: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for folio in folios:
        if folio["client_ref"] is not None:
            folios_by_client[folio["client_ref"]].append(folio)
    valuations_by_client = {
        item["client_ref"]: item
        for item in valuations
        if item["client_ref"] is not None
    }

    for ref, client in enumerate(clients):
        client_folios = folios_by_client.get(ref, [])
        aum_values = [
            Decimal(item["aum"])
            for item in client_folios
            if item["aum"] is not None
        ]
        folio_aum_total = sum(aum_values, Decimal("0")) if aum_values else None
        missing_aum = sum(1 for item in client_folios if item["aum"] is None)
        valuation = valuations_by_client.get(ref)
        current_value = (
            Decimal(valuation["current_value"])
            if valuation and valuation["current_value"] is not None
            else None
        )

        if not client_folios:
            status = "no_folios"
        elif current_value is None:
            status = "not_available"
        elif missing_aum:
            status = "partial"
        elif folio_aum_total is not None and abs(
            folio_aum_total - current_value
        ) <= ONE_RUPEE:
            status = "matched"
        else:
            status = "mismatch"

        difference = (
            folio_aum_total - current_value
            if folio_aum_total is not None and current_value is not None
            else None
        )
        reconciliation.append(
            {
                "client_ref": ref,
                "client_name": client.name,
                "folio_count": len(client_folios),
                "folio_aum_total": _as_text(folio_aum_total),
                "folio_aum_missing_count": missing_aum,
                "client_current_value": _as_text(current_value),
                "difference": _as_text(difference),
                "status": status,
            }
        )

        if status == "mismatch":
            _add_issue(
                issues,
                "reconciliation",
                None,
                "CURRENT VALUE",
                f"{client.name}: the sum of folio AUM does not match the client current value. "
                "Review the two InvestWell exports; no allocation has been made.",
            )
        elif status == "partial":
            _add_issue(
                issues,
                "reconciliation",
                None,
                "AUM",
                f"{client.name}: some folio AUM values are missing, so reconciliation is incomplete.",
                "info",
            )
        elif status == "not_available":
            _add_issue(
                issues,
                "reconciliation",
                None,
                "CURRENT VALUE",
                f"{client.name}: the client-level current value is missing, so reconciliation is Not available.",
                "warning",
            )

    total_portfolio_current = parsed["portfolio"].total_values.get("current_value")
    total_client_current_values = [
        Decimal(item["current_value"])
        for item in valuations
        if item["current_value"] is not None
    ]
    total_client_current = (
        sum(total_client_current_values, Decimal("0"))
        if total_client_current_values
        else None
    )
    if (
        parsed["portfolio"].total_row_found
        and total_portfolio_current is not None
        and total_client_current is not None
        and len(total_client_current_values) == len(valuations)
        and abs(total_portfolio_current - total_client_current) > ONE_RUPEE
    ):
        _add_issue(
            issues,
            "reconciliation",
            None,
            "CURRENT VALUE",
            "The Portfolio Valuation total row does not match the sum of the client rows. "
            "The total row is used only for this check.",
        )

    unmatched_folios = sum(1 for item in folios if item["match_status"] == "unmatched")
    unmatched_portfolio = sum(
        1 for item in valuations if item["match_status"] == "unmatched"
    )
    all_folios_unmatched = bool(folios) and unmatched_folios == len(folios)
    all_portfolio_unmatched = bool(valuations) and unmatched_portfolio == len(valuations)
    if clients and all_folios_unmatched and all_portfolio_unmatched:
        _add_issue(
            issues,
            "reconciliation",
            None,
            "CLIENT MATCHING",
            "No client rows could be matched between the snapshot files. "
            "Check that the Client Details, Folios and Portfolio Valuation files "
            "come from the same export run before confirming.",
            "error",
        )
    elif all_folios_unmatched:
        _add_issue(
            issues,
            "folios",
            None,
            "CLIENT MATCHING",
            "None of the folio rows matched a client in Client Details. "
            "Review the IWELL code and client-name fallback before relying on the snapshot.",
        )
    elif all_portfolio_unmatched:
        _add_issue(
            issues,
            "portfolio",
            None,
            "CLIENT MATCHING",
            "None of the portfolio valuation rows matched a client in Client Details. "
            "Review the IWELL code and client-name fallback before relying on the snapshot.",
        )
    needs_review = sum(
        1
        for item in schemes.values()
        if item["benchmark_status"] == "needs_review"
    )
    reconciliation_warnings = sum(
        1 for item in reconciliation if item["status"] == "mismatch"
    )

    portfolio_rows = parsed["portfolio"].row_count

    counts = {
        "client_rows": parsed["clients"].row_count,
        "clients_imported": len(clients),
        "clients_skipped": max(0, parsed["clients"].rows_read - len(clients)),
        "folio_rows": parsed["folios"].row_count,
        "folios_imported": len(folios),
        "folios_skipped": max(0, parsed["folios"].rows_read - len(folios)),
        "portfolio_rows": max(0, portfolio_rows),
        "portfolio_imported": len(valuations),
        "portfolio_skipped": max(0, parsed["portfolio"].rows_read - len(valuations)),
        "transaction_rows": parsed["transactions"].row_count,
        "transactions_imported": len(transaction_rows),
        "transaction_skipped": max(
            0, parsed["transactions"].rows_read - len(transaction_rows)
        ),
        "rows_read": sum(parsed[kind].rows_read for kind in KINDS),
        "blank_rows": sum(parsed[kind].blank_rows for kind in KINDS),
        "total_rows": sum(parsed[kind].total_rows for kind in KINDS),
        "duplicate_rows": sum(parsed[kind].duplicate_rows for kind in KINDS),
        "invalid_date_rows": sum(parsed[kind].invalid_date_rows for kind in KINDS),
        "invalid_number_rows": sum(
            parsed[kind].invalid_number_rows for kind in KINDS
        ),
        "transactions_unmatched": unmatched_transactions,
        "unknown_transactions": unknown_transactions,
        "switch_pairs": switch_pairs,
        "switch_reviews": switch_reviews,
        "schemes": len(schemes),
        "needs_review": needs_review,
        "unmatched_folios": unmatched_folios,
        "unmatched_portfolio_rows": unmatched_portfolio,
        "reconciliation_warnings": reconciliation_warnings,
        "issues": len(issues),
        "errors": sum(1 for issue in issues if issue.severity == "error"),
        "warnings": sum(1 for issue in issues if issue.severity == "warning"),
    }

    file_reports = _file_reports(
        parsed,
        clients_imported=len(clients),
        folios_imported=len(folios),
        portfolio_imported=len(valuations),
        transactions_imported=len(transaction_rows),
        folios_unmatched=unmatched_folios,
        portfolio_unmatched=unmatched_portfolio,
        transactions_unmatched=unmatched_transactions,
    )
    client_matching = _client_matching_summary(
        clients=len(clients),
        folios=len(folios),
        folios_unmatched=unmatched_folios,
        portfolio=len(valuations),
        portfolio_unmatched=unmatched_portfolio,
        transactions=(
            len(transaction_rows) if parsed["transactions"].supplied else None
        ),
        transactions_unmatched=(
            unmatched_transactions if parsed["transactions"].supplied else None
        ),
    )

    total_folio_aum_values = [
        Decimal(item["aum"]) for item in folios if item["aum"] is not None
    ]
    total_folio_aum = (
        sum(total_folio_aum_values, Decimal("0"))
        if total_folio_aum_values
        else None
    )

    can_confirm = (
        parsed["portfolio"].report_date is not None
        and counts["errors"] == 0
        and len(clients) > 0
        and len(folios) > 0
    )

    warnings = [
        "The preview reads only whitelisted columns; PAN, contact, bank and KYC columns are ignored.",
        "Automatic benchmark mappings remain Needs Review. Review them on the Benchmark Mapping & Data screen; comparisons also need local benchmark levels imported there.",
        "Client-level absolute return and CAGR are shown exactly as reported by InvestWell.",
        "Confirming this import replaces the current local snapshot.",
        "The valuation date is taken from the Portfolio Valuation report date and applied to this import batch.",
    ]
    if parsed["transactions"].supplied:
        warnings.insert(
            2,
            "Folio invested amount, holding period, absolute return and XIRR are calculated from the transaction statement. Missing dates or amounts are excluded and shown as Not available.",
        )
    else:
        warnings.insert(
            2,
            "No transaction statement was supplied, so folio-level invested amount, holding period, absolute return and XIRR are Not available.",
        )
    if portfolio_layout_warning:
        warnings.insert(
            0,
            "The Portfolio Valuation file had no header row. Its fixed 13-column layout was used and every data row was checked; PAN was ignored.",
        )

    issue_dicts = [issue.as_dict() for issue in issues]
    issue_count = len(issue_dicts)
    issues_truncated = issue_count > MAX_STORED_ISSUES
    display_issues = issue_dicts[:MAX_STORED_ISSUES]
    if issues_truncated:
        display_issues.append(
            {
                "file_type": "import",
                "row_number": None,
                "field": None,
                "message": (
                    f"Showing the first {MAX_STORED_ISSUES:,} of {issue_count:,} "
                    "issues. The counts above include every row."
                ),
                "severity": "info",
            }
        )

    return {
        "import_id": uuid.uuid4().hex,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "preview",
        "report_date": (
            parsed["portfolio"].report_date.isoformat()
            if parsed["portfolio"].report_date
            else None
        ),
        "report_date_format": parsed["portfolio"].report_date_format,
        "transactions_supplied": parsed["transactions"].supplied,
        "files": {
            kind: (
                _file_info(files[kind][0], files[kind][1])
                if kind in files
                else None
            )
            for kind in KINDS
        },
        "detected_columns": {
            kind: parsed[kind].detected for kind in KINDS
        },
        "counts": counts,
        "file_reports": file_reports,
        "client_matching": client_matching,
        "export_run": export_run,
        "issues": display_issues,
        "issue_count": issue_count,
        "issues_truncated": issues_truncated,
        "warnings": warnings,
        "can_confirm": can_confirm,
        "clients": [
            {
                "source_row": client.source_row,
                "name": client.name,
                "name_key": key_for_name(client.name),
                "iwell_code": client.iwell_code,
                "iwell_code_2": client.iwell_code_2,
                "app_code": client.app_code,
                "first_investment_date": (
                    client.first_investment_date.isoformat()
                    if client.first_investment_date
                    else None
                ),
                "dedupe_key": client.dedupe_key,
            }
            for client in clients
        ],
        "schemes": list(schemes.values()),
        "folios": folios,
        "valuations": valuations,
        "transactions": transaction_rows,
        "reconciliation": reconciliation,
        "total_folio_aum": _as_text(total_folio_aum),
        "total_client_current_value": _as_text(total_client_current),
        "portfolio_total_current_value": _as_text(total_portfolio_current),
        "portfolio_total_row_found": parsed["portfolio"].total_row_found,
        "sample_folios": [
            {
                "client_name": (
                    clients[item["client_ref"]].name
                    if item["client_ref"] is not None
                    else (item["source_client_name"] or "Unmatched — needs review")
                ),
                "folio_number": item["folio_number"],
                "scheme_name": schemes[item["scheme_key"]]["name"],
                "benchmark_name": schemes[item["scheme_key"]]["benchmark_name"],
                "benchmark_status": schemes[item["scheme_key"]]["benchmark_status"],
                "match_status": item["match_status"],
                "aum": item["aum"],
            }
            for item in folios[:8]
        ],
    }


def build_preview(files: dict[str, tuple[str, FileSource]]) -> dict[str, Any]:
    missing = [kind for kind in REQUIRED_KINDS if kind not in files]
    if missing:
        labels = ", ".join(FILE_LABELS[kind] for kind in missing)
        raise ValueError(f"Required InvestWell file(s) missing: {labels}.")

    parsed = {
        kind: parse_file(files[kind][1], files[kind][0], kind)
        for kind in KINDS
        if kind in files
    }
    if "transactions" not in parsed:
        detected = _missing_table("transactions")
        detected["missing_required"] = []
        detected["not_supplied"] = True
        parsed["transactions"] = ParsedFile(
            kind="transactions",
            name="",
            detected=detected,
            supplied=False,
        )
    return _build_plan(parsed, files)


PREVIEW_HEAVY_KEYS = {
    "clients",
    "schemes",
    "folios",
    "valuations",
    "transactions",
    "reconciliation",
}


def public_preview(plan: dict[str, Any]) -> dict[str, Any]:
    """Return the small summary that the browser needs.

    The full normalized plan stays on this machine for confirmation.  Sending
    thousands of rows to the browser would make previews needlessly heavy and
    slow; the preview screen only uses counts, issues and a small sample.
    """

    public = {
        key: value for key, value in plan.items() if key not in PREVIEW_HEAVY_KEYS
    }
    if len(public.get("issues", [])) > MAX_PREVIEW_ISSUES:
        issue_count = public.get("issue_count", len(public["issues"]))
        public["issues"] = public["issues"][:MAX_PREVIEW_ISSUES]
        public["issues"].append(
            {
                "file_type": "import",
                "row_number": None,
                "field": None,
                "message": (
                    f"Showing the first {MAX_PREVIEW_ISSUES:,} of "
                    f"{issue_count:,} issues in the browser. The stored preview "
                    "and import counts include every row."
                ),
                "severity": "info",
            }
        )
        public["preview_issues_truncated"] = True
    else:
        public["preview_issues_truncated"] = False
    public["preview_rows_omitted"] = True
    return public


def preview_import(files: dict[str, tuple[str, FileSource]]) -> dict[str, Any]:
    plan = build_preview(files)
    PREVIEWS_DIR.mkdir(parents=True, exist_ok=True)
    path = PREVIEWS_DIR / f"{plan['import_id']}.json"
    path.write_text(
        json.dumps(plan, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    return public_preview(plan)


def _load_plan(import_id: str) -> tuple[Path, dict[str, Any]]:
    if not import_id or not all(
        character in "0123456789abcdef" for character in import_id.lower()
    ):
        raise FileNotFoundError("Import preview not found.")
    path = PREVIEWS_DIR / f"{import_id}.json"
    if not path.exists():
        raise FileNotFoundError("Import preview not found or already confirmed.")
    return path, json.loads(path.read_text(encoding="utf-8"))


def _decimal(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    return Decimal(str(value))


def _clear_snapshot(db: Session) -> None:
    # Child rows first so SQLite foreign keys remain satisfied.
    for model in (
        ImportIssue,
        Transaction,
        Folio,
        PortfolioValuation,
        SchemeBenchmark,
        ClientIdentifier,
        Scheme,
        Client,
        UploadBatch,
    ):
        db.execute(delete(model))
    db.flush()


def confirm_import(db: Session, import_id: str) -> dict[str, Any]:
    path, plan = _load_plan(import_id)
    if plan.get("status") == "confirmed":
        raise ValueError("This preview has already been confirmed.")
    if not plan.get("can_confirm"):
        raise ValueError("The preview has errors and cannot be confirmed.")

    report_date = date.fromisoformat(plan["report_date"])
    files = plan["files"]
    counts = plan["counts"]
    previous_reviews = {
        item.normalized_scheme_name: item.benchmark_name
        for item in db.scalars(
            select(SchemeBenchmark).where(SchemeBenchmark.status == "reviewed")
        )
        if item.benchmark_name
    }

    try:
        _clear_snapshot(db)

        batch = UploadBatch(
            import_id=plan["import_id"],
            client_file_name=files["clients"]["name"],
            folios_file_name=files["folios"]["name"],
            portfolio_file_name=files["portfolio"]["name"],
            client_hash=files["clients"]["sha256"],
            folios_hash=files["folios"]["sha256"],
            portfolio_hash=files["portfolio"]["sha256"],
            transaction_file_name=(
                files["transactions"]["name"]
                if files.get("transactions")
                else None
            ),
            transaction_hash=(
                files["transactions"]["sha256"]
                if files.get("transactions")
                else None
            ),
            report_date=report_date,
            status="confirmed",
            client_rows=counts["client_rows"],
            clients_imported=counts["clients_imported"],
            folio_rows=counts["folio_rows"],
            folios_imported=counts["folios_imported"],
            portfolio_rows=counts["portfolio_rows"],
            portfolio_imported=counts["portfolio_imported"],
            transaction_rows=counts["transaction_rows"],
            transactions_imported=counts["transactions_imported"],
            transaction_skipped=counts["transaction_skipped"],
            transactions_unmatched=counts["transactions_unmatched"],
            switch_reviews=counts["switch_reviews"],
            needs_review=counts["needs_review"],
            unmatched_folios=counts["unmatched_folios"],
            unmatched_portfolio_rows=counts["unmatched_portfolio_rows"],
            reconciliation_warnings=counts["reconciliation_warnings"],
            total_folio_aum=_decimal(plan.get("total_folio_aum")),
            total_client_current_value=_decimal(
                plan.get("total_client_current_value")
            ),
            portfolio_total_current_value=_decimal(
                plan.get("portfolio_total_current_value")
            ),
            notes=(
                "Four-file InvestWell snapshot with transactions."
                if plan.get("transactions_supplied")
                else "Three-file InvestWell snapshot; transactions not supplied."
            ),
        )
        db.add(batch)
        db.flush()

        client_rows: list[Client] = []
        for item in plan["clients"]:
            client = Client(
                name=item["name"],
                name_key=item["name_key"],
                iwell_code=item.get("iwell_code"),
                iwell_code_key=(
                    normalize_code(item.get("iwell_code"))
                    if item.get("iwell_code")
                    else None
                ),
                iwell_code_2=item.get("iwell_code_2"),
                app_code=item.get("app_code"),
                first_investment_date=(
                    date.fromisoformat(item["first_investment_date"])
                    if item.get("first_investment_date")
                    else None
                ),
                source_row=item.get("source_row"),
            )
            db.add(client)
            client_rows.append(client)
        db.flush()

        for item, client in zip(plan["clients"], client_rows):
            identifiers = [
                ("iwell_code", item.get("iwell_code")),
                ("iwell_code_2", item.get("iwell_code_2")),
                ("app_code", item.get("app_code")),
                ("name", item.get("name")),
            ]
            for identifier_type, value in identifiers:
                if not value:
                    continue
                normalized = (
                    normalize_code(value)
                    if identifier_type != "name"
                    else key_for_name(value)
                )
                if not normalized:
                    continue
                db.add(
                    ClientIdentifier(
                        client_id=client.id,
                        identifier_type=identifier_type,
                        value=str(value),
                        normalized_value=normalized,
                        source_file="clients",
                    )
                )
        db.flush()

        schemes: dict[str, Scheme] = {}
        for item in plan["schemes"]:
            scheme = Scheme(
                name=item["name"],
                name_key=item["name_key"],
                normalized_name=item["normalized_name"],
            )
            db.add(scheme)
            schemes[item["name_key"]] = scheme
        db.flush()

        for item in plan["schemes"]:
            scheme = schemes[item["name_key"]]
            preserved_review = previous_reviews.get(item["normalized_name"])
            mapping_status = "reviewed" if preserved_review else "needs_review"
            benchmark_name = preserved_review or item["benchmark_name"]
            db.add(
                SchemeBenchmark(
                    scheme_id=scheme.id,
                    benchmark_name=benchmark_name,
                    normalized_scheme_name=item["normalized_name"],
                    status=mapping_status,
                    source="manual" if preserved_review else "auto",
                    notes=(
                        "Reviewed mapping preserved from the local database."
                        if preserved_review
                        else "Automatic sample mapping. Review before relying on it."
                    ),
                )
            )
        db.flush()
        mapping_needs_review = sum(
            1
            for item in db.scalars(
                select(SchemeBenchmark).where(
                    SchemeBenchmark.status == "needs_review"
                )
            )
        )
        batch.needs_review = mapping_needs_review

        folio_rows: list[Folio] = []
        for item in plan["folios"]:
            client = (
                client_rows[item["client_ref"]]
                if item.get("client_ref") is not None
                else None
            )
            scheme = schemes[item["scheme_key"]]
            folio = Folio(
                batch_id=batch.id,
                client_id=client.id if client else None,
                scheme_id=scheme.id,
                folio_number=item["folio_number"],
                normalized_folio_number=item["normalized_folio_number"],
                folio_type=item.get("folio_type"),
                units=_decimal(item.get("units")),
                aum=_decimal(item.get("aum")),
                value_date=report_date,
                match_status=item["match_status"],
                match_note=item.get("match_note"),
                source_client_name=item.get("source_client_name"),
                source_iwell_code=item.get("source_iwell_code"),
                source_row=item.get("source_row"),
                dedupe_key=item["dedupe_key"],
            )
            db.add(folio)
            folio_rows.append(folio)
        db.flush()

        for item in plan.get("transactions", []):
            folio = (
                folio_rows[item["folio_ref"]]
                if item.get("folio_ref") is not None
                else None
            )
            client = (
                client_rows[item["client_ref"]]
                if item.get("client_ref") is not None
                else None
            )
            scheme = (
                schemes[item["scheme_key"]]
                if item.get("scheme_key") is not None
                else None
            )
            db.add(
                Transaction(
                    batch_id=batch.id,
                    folio_id=folio.id if folio else None,
                    client_id=client.id if client else None,
                    scheme_id=scheme.id if scheme else None,
                    transaction_date=(
                        date.fromisoformat(item["transaction_date"])
                        if item.get("transaction_date")
                        else None
                    ),
                    transaction_type_raw=item.get("transaction_type_raw") or "",
                    transaction_type=item["transaction_type"],
                    amount=_decimal(item.get("amount")),
                    units=_decimal(item.get("units")),
                    nav=_decimal(item.get("nav")),
                    source_scheme_name=item.get("source_scheme_name"),
                    target_scheme_name=item.get("target_scheme_name"),
                    description=item.get("description"),
                    source_folio_number=item.get("source_folio_number") or "",
                    normalized_folio_number=item.get(
                        "normalized_folio_number", ""
                    ),
                    source_iwell_code=item.get("source_iwell_code"),
                    source_client_name=item.get("source_client_name"),
                    match_status=item.get("match_status", "matched"),
                    review_note=item.get("review_note"),
                    switch_pair_key=item.get("switch_pair_key"),
                    source_row=item.get("source_row"),
                )
            )

        for item in plan["valuations"]:
            client = (
                client_rows[item["client_ref"]]
                if item.get("client_ref") is not None
                else None
            )
            db.add(
                PortfolioValuation(
                    batch_id=batch.id,
                    client_id=client.id if client else None,
                    valuation_date=report_date,
                    balance_units=_decimal(item.get("balance_units")),
                    purchase_value=_decimal(item.get("purchase_value")),
                    current_value=_decimal(item.get("current_value")),
                    one_day_change=_decimal(item.get("one_day_change")),
                    dividend=_decimal(item.get("dividend")),
                    avg_holding_days=item.get("avg_holding_days"),
                    gain=_decimal(item.get("gain")),
                    absolute_return=_decimal(item.get("absolute_return")),
                    cagr=_decimal(item.get("cagr")),
                    match_status=item["match_status"],
                    match_note=item.get("match_note"),
                    source_client_name=item.get("source_client_name"),
                    source_iwell_code=item.get("source_iwell_code"),
                    source_row=item.get("source_row"),
                    dedupe_key=item["dedupe_key"],
                )
            )

        for item in plan["issues"]:
            db.add(
                ImportIssue(
                    batch_id=batch.id,
                    file_type=item["file_type"],
                    row_number=item.get("row_number"),
                    field=item.get("field"),
                    message=item["message"],
                    severity=item.get("severity", "warning"),
                )
            )

        db.commit()
        plan["status"] = "confirmed"
        plan["batch_id"] = batch.id
        path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        db.rollback()
        raise

    return {
        "import_id": plan["import_id"],
        "batch_id": batch.id,
        "report_date": report_date.isoformat(),
        "imported": {
            "clients": counts["clients_imported"],
            "folios": counts["folios_imported"],
            "portfolio_rows": counts["portfolio_imported"],
            "transactions": counts["transactions_imported"],
            "schemes": counts["schemes"],
            "needs_review": mapping_needs_review,
            "switch_pairs": counts["switch_pairs"],
            "switch_reviews": counts["switch_reviews"],
        },
        "skipped": {
            "clients": counts["clients_skipped"],
            "folios": counts["folios_skipped"],
            "portfolio_rows": counts["portfolio_skipped"],
            "transactions": counts["transaction_skipped"],
        },
        "unmatched": {
            "folios": counts["unmatched_folios"],
            "portfolio_rows": counts["unmatched_portfolio_rows"],
            "transactions": counts["transactions_unmatched"],
        },
        "reconciliation_warnings": counts["reconciliation_warnings"],
        "issues": counts["issues"],
        "warnings": plan.get("warnings", []),
    }
