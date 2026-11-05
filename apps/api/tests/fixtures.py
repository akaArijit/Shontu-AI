"""XLSX workbook builders used by the backend tests."""

from __future__ import annotations

import csv
import io
from io import BytesIO
from typing import Iterable

from openpyxl import Workbook


CLIENT_HEADERS = [
    "IWELL CODE",
    "IWELL CODE 2",
    "APPCODE",
    "NAME",
    "First Investment Date",
    "AUM",
    "PAN",
    "Email",
    "Mobile",
]


def _workbook_bytes(rows: Iterable[Iterable[object]], title: str) -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = title
    for row in rows:
        sheet.append(list(row))
    buffer = BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def clients_xlsx(rows: list[tuple[object, ...]] | None = None) -> bytes:
    rows = rows or [
        ("C001", "", "", "Alice Example", "01-01-2020", "15000", "REDACTED", "a@example.invalid", "REDACTED"),
        ("C002", "", "", "Bob Example", "02-02-2021", "7000", "REDACTED", "b@example.invalid", "REDACTED"),
    ]
    return _workbook_bytes([CLIENT_HEADERS, *rows], "Client Details")


def folios_xlsx(rows: list[tuple[object, ...]] | None = None) -> bytes:
    rows = rows or [
        ("C001", "", "", "F001", "Apex Bluechip Fund", "100", "10000", "Single", "Alice Example", "REDACTED"),
        ("C001", "", "", "F002", "Apex Midcap Fund", "50", "5000", "Single", "Alice Example", "REDACTED"),
        ("C999", "", "", "F900", "Apex Small Cap Fund", "10", "1000", "Single", "Unmatched Example", "REDACTED"),
    ]
    return _workbook_bytes(
        [
            [
                "IWELL CODE",
                "IWELLCODE2",
                "APP CODE",
                "FOLIO NO",
                "SCHEME NAME",
                "UNITS",
                "AUM",
                "FOLIO TYPE",
                "CLIENT NAME",
                "PAN",
            ],
            *rows,
        ],
        "Folios",
    )


def portfolio_xlsx(
    rows: list[tuple[object, ...]] | None = None,
    *,
    report_date: str | None = "27-10-2026",
    total_current: str | None = "24000",
) -> bytes:
    rows = rows or [
        ("C001", "", "Alice Example", "150", "12000", "15000", "3000", "25.00", "12.00", "1000", "10", "0"),
        ("C002", "", "Bob Example", "0", "7000", "7000", "0", "0.00", "0.00", "0", "0", "0"),
        ("C900", "", "Unmatched Example", "10", "2000", "2000", "0", "0.00", "0.00", "100", "0", "0"),
    ]
    title_rows: list[tuple[object, ...]] = [
        ("Portfolio Valuation Report",),
        ("Mutual fund portfolio snapshot",),
    ]
    if report_date is not None:
        title_rows.append((f"Report printed on: {report_date}",))
    headers = (
        "IWELL CODE",
        "IWELL CODE2",
        "CLIENT NAME",
        "BALANCE UNITS",
        "PURCHASE VALUE",
        "CURRENT VALUE",
        "GAIN",
        "ABSOLUTE RETURN",
        "CAGR",
        "AVG HOLDING DAYS",
        "ONE DAY CHANGE",
        "DIVIDEND",
    )
    all_rows = [*title_rows, headers, *rows]
    if total_current is not None:
        all_rows.append(("", "", "Total", "", "", total_current, "", "", "", "", "", ""))
    return _workbook_bytes(all_rows, "Portfolio Valuation")


TRANSACTION_HEADERS = [
    "TRANSACTION DATE",
    "SCHEME NAME",
    "FOLIO NO",
    "APPLICANT",
    "PAN",
    "TXN TYPE",
    "TOTAL AMOUNT",
    "UNITS",
    "NAV",
    "TXN DESCRIPTION",
    "SOURCE SCHEME NAME",
    "TARGET SCHEME NAME",
    "IWELL CODE",
    "IWELL CODE 2",
    "APP CODE",
    "SIP REG DATE",
]


def transactions_xlsx(rows: list[tuple[object, ...]] | None = None) -> bytes:
    rows = rows or [
        (
            "15-01-2024",
            "Apex Bluechip Fund",
            "F001",
            "Alice Example",
            "REDACTED",
            "PURCHASE",
            "10000",
            "100",
            "100",
            "LUMPSUM PURCHASE",
            "",
            "",
            "C001",
            "",
            "",
            "",
        ),
        (
            "15-01-2025",
            "Apex Midcap Fund",
            "F002",
            "Alice Example",
            "REDACTED",
            "SIP",
            "1000",
            "10",
            "100",
            "SYSTEMATIC INVESTMENT",
            "",
            "",
            "C001",
            "",
            "",
            "",
        ),
        (
            "15-06-2025",
            "Apex Midcap Fund",
            "F002",
            "Alice Example",
            "REDACTED",
            "SIP",
            "1000",
            "10",
            "100",
            "SYSTEMATIC INVESTMENT",
            "",
            "",
            "C001",
            "",
            "",
            "",
        ),
    ]
    return _workbook_bytes([TRANSACTION_HEADERS, *rows], "Transactions")


def transactions_csv(rows: list[tuple[object, ...]] | None = None) -> bytes:
    rows = rows or [
        (
            "15-01-2024",
            "Apex Bluechip Fund",
            "F001",
            "Alice Example",
            "REDACTED",
            "PURCHASE",
            "10000",
            "100",
            "100",
            "LUMPSUM PURCHASE",
            "",
            "",
            "C001",
            "",
            "",
            "",
        )
    ]
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer)
    writer.writerow(TRANSACTION_HEADERS)
    for row in rows:
        writer.writerow(row)
    return buffer.getvalue().encode("utf-8")


def portfolio_csv(
    rows: list[tuple[object, ...]] | None = None,
    *,
    report_date: str = "27-10-2026",
    total_current: str | None = "15000",
) -> bytes:
    """Build the headerless 13-column Portfolio Valuation CSV layout."""

    data_rows = rows or [
        (
            "Alice Example",
            "",
            "C001",
            "REDACTED",
            "0",
            "0",
            "15000",
            "0",
            "0",
            "0",
            "0",
            "0",
            "0",
        )
    ]
    output: list[list[object]] = [
        ["abcd", *[f"Unnamed: {index}" for index in range(1, 13)]],
        ["Portfolio Valuation for Mutual Funds", *([""] * 12)],
        ["", "", "", "", "", f"Report printed on: {report_date}", *([""] * 7)],
        *[list(row) for row in data_rows],
    ]
    if total_current is not None:
        output.append(
            [
                "Total",
                "",
                "",
                "",
                "",
                "",
                total_current,
                "",
                "",
                "",
                "",
                "",
                "",
            ]
        )
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer)
    writer.writerows(output)
    return buffer.getvalue().encode("utf-8")


def four_files(
    *,
    clients: bytes | None = None,
    folios: bytes | None = None,
    portfolio: bytes | None = None,
    transactions: bytes | None = None,
) -> dict[str, tuple[str, bytes]]:
    return {
        **three_files(clients=clients, folios=folios, portfolio=portfolio),
        "transactions": (
            "Transaction Statement.xlsx",
            transactions or transactions_xlsx(),
        ),
    }


def three_files(
    *,
    clients: bytes | None = None,
    folios: bytes | None = None,
    portfolio: bytes | None = None,
) -> dict[str, tuple[str, bytes]]:
    return {
        "clients": ("Client Details.xlsx", clients or clients_xlsx()),
        "folios": ("Folios.xlsx", folios or folios_xlsx()),
        "portfolio": ("PortfolioValuationReportMF.xlsx", portfolio or portfolio_xlsx()),
    }
