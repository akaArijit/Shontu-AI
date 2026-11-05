"""Deterministic synthetic InvestWell workbooks for local verification.

The demo files use the same header structure as the real exports but contain
only invented names and values.  They are generated on demand under
``samples/investwell_demo`` and are never sent anywhere.
"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from mfd_dashboard.core.paths import SAMPLES_DIR
from mfd_dashboard.db.models import Client, UploadBatch
from mfd_dashboard.ingest.service import confirm_import, preview_import


class DemoDataExistsError(ValueError):
    pass


DEMO_DIR = SAMPLES_DIR / "investwell_demo"
REPORT_DATE = "27-10-2026"

CLIENTS = [
    ("C001", "", "", "Aarav Mehta", "12-04-2019", "340000"),
    ("C002", "", "", "Diya Sharma", "03-08-2020", "160000"),
    ("C003", "", "", "Kabir Nair", "21-01-2018", "255000"),
    ("C004", "", "", "Meera Iyer", "15-06-2021", "80000"),
    ("C005", "", "", "Rohan Patel", "09-02-2019", "140000"),
    ("C006", "", "", "Ananya Rao", "18-11-2022", "60000"),
    ("C007", "", "", "Vihaan Gupta", "07-05-2020", "50000"),
    ("C008", "", "", "Isha Verma", "26-09-2017", "90000"),
    ("C009", "", "", "Arjun Singh", "14-03-2023", "110000"),
    ("C010", "", "", "Nisha Kulkarni", "02-12-2018", "130000"),
    ("C011", "", "", "Dev Joshi", "30-07-2024", ""),
]

FOLIOS = [
    ("C001", "", "", "F001", "Apex Bluechip Fund", "1200.500", "180000", "Single", "Aarav Mehta"),
    ("C001", "", "", "F002", "Apex Midcap Opportunities Fund", "800.250", "160000", "Single", "Aarav Mehta"),
    ("C002", "", "", "F003", "Apex Small Cap Fund", "500.000", "90000", "Single", "Diya Sharma"),
    ("C002", "", "", "F004", "Apex Healthcare Fund", "350.750", "70000", "Single", "Diya Sharma"),
    ("C003", "", "", "F005", "Apex PSU Equity Fund", "900.000", "135000", "Single", "Kabir Nair"),
    ("C003", "", "", "F006", "Apex Flexi Cap Fund", "600.000", "120000", "Single", "Kabir Nair"),
    ("C004", "", "", "F007", "Apex Large Cap Fund", "400.000", "80000", "Single", "Meera Iyer"),
    ("C005", "", "", "F008", "Apex Mid Cap 150 Index Fund", "700.000", "140000", "Single", "Rohan Patel"),
    ("C006", "", "", "F009", "Apex Small Cap 250 Index Fund", "300.000", "60000", "Single", "Ananya Rao"),
    ("C007", "", "", "F010", "Apex Pharma Fund", "250.000", "", "Single", "Vihaan Gupta"),
    ("C008", "", "", "F011", "Apex Public Sector Fund", "450.000", "90000", "Single", "Isha Verma"),
    ("C009", "", "", "F012", "Apex Broad Market Fund", "550.000", "110000", "Single", "Arjun Singh"),
    ("C010", "", "", "F013", "Apex Blue Chip Advantage Fund", "650.000", "130000", "Single", "Nisha Kulkarni"),
    ("C999", "", "", "F014", "Apex Unknown Sector Fund", "100.000", "20000", "Single", "Unmatched Export Client"),
]

PORTFOLIO = [
    ("C001", "", "Aarav Mehta", "1200.500", "280000", "340000", "60000", "21.43", "12.10", "900", "1200", "0"),
    ("C002", "", "Diya Sharma", "500.000", "140000", "160000", "20000", "14.29", "8.40", "640", "800", "0"),
    ("C003", "", "Kabir Nair", "900.000", "230000", "245000", "15000", "6.52", "4.10", "1100", "-500", "0"),
    ("C004", "", "Meera Iyer", "400.000", "72000", "80000", "8000", "11.11", "6.80", "420", "n/a", "0"),
    ("C005", "", "Rohan Patel", "700.000", "125000", "140000", "15000", "12.00", "7.20", "760", "300", "0"),
    ("C006", "", "Ananya Rao", "300.000", "55000", "60000", "5000", "9.09", "5.10", "300", "100", "0"),
    ("C007", "", "Vihaan Gupta", "250.000", "45000", "50000", "5000", "11.11", "6.20", "580", "200", "0"),
    ("C008", "", "Isha Verma", "450.000", "80000", "90000", "10000", "12.50", "7.00", "1200", "400", "0"),
    ("C009", "", "Arjun Singh", "550.000", "100000", "110000", "10000", "10.00", "8.30", "240", "150", "0"),
    ("C010", "", "Nisha Kulkarni", "650.000", "115000", "130000", "15000", "13.04", "9.10", "980", "-250", "0"),
    ("C011", "", "Dev Joshi", "", "40000", "", "", "", "", "120", "0", "0"),
    ("C900", "", "Unmatched Export Client", "100.000", "70000", "75000", "5000", "7.14", "4.00", "300", "50", "0"),
    ("C999", "", "Unmatched Export Client 2", "100.000", "18000", "20000", "2000", "11.11", "5.00", "360", "20", "0"),
]


def _tx(
    *,
    code: str,
    client_name: str,
    folio: str,
    scheme: str,
    date_text: str,
    txn_type: str,
    amount: str,
    source_scheme: str = "",
    target_scheme: str = "",
) -> tuple[object, ...]:
    return (
        date_text,
        scheme,
        "Equity",
        "Equity: Flexi Cap",
        folio,
        client_name,
        "",
        "REDACTED",
        txn_type,
        "",
        amount,
        "Synthetic Fund",
        "0",
        "0",
        "",
        "",
        "",
        "",
        txn_type,
        "",
        "",
        source_scheme,
        target_scheme,
        "",
        "",
        "",
        code,
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
    )


DEMO_TRANSACTIONS = [
    _tx(code="C001", client_name="Aarav Mehta", folio="F001", scheme="Apex Bluechip Fund", date_text="15-01-2020", txn_type="PURCHASE", amount="200000"),
    _tx(code="C001", client_name="Aarav Mehta", folio="F002", scheme="Apex Midcap Opportunities Fund", date_text="15-01-2025", txn_type="SIP", amount="10000"),
    _tx(code="C001", client_name="Aarav Mehta", folio="F002", scheme="Apex Midcap Opportunities Fund", date_text="15-02-2025", txn_type="SIP", amount="10000"),
    _tx(code="C001", client_name="Aarav Mehta", folio="F002", scheme="Apex Midcap Opportunities Fund", date_text="15-03-2025", txn_type="SIP", amount="10000"),
    _tx(code="C002", client_name="Diya Sharma", folio="F003", scheme="Apex Small Cap Fund", date_text="15-01-2024", txn_type="PURCHASE", amount="90000"),
    _tx(code="C002", client_name="Diya Sharma", folio="F003", scheme="Apex Small Cap Fund", date_text="15-01-2026", txn_type="REDEMPTION", amount="20000"),
    _tx(code="C002", client_name="Diya Sharma", folio="F004", scheme="Apex Healthcare Fund", date_text="15-01-2023", txn_type="PURCHASE", amount="60000"),
    _tx(code="C003", client_name="Kabir Nair", folio="F005", scheme="Apex PSU Equity Fund", date_text="15-01-2022", txn_type="PURCHASE", amount="120000"),
    _tx(code="C003", client_name="Kabir Nair", folio="F005", scheme="Apex PSU Equity Fund", date_text="15-06-2026", txn_type="SWITCH OUT", amount="15000", source_scheme="Apex PSU Equity Fund", target_scheme="Apex Flexi Cap Fund"),
    _tx(code="C003", client_name="Kabir Nair", folio="F006", scheme="Apex Flexi Cap Fund", date_text="15-01-2022", txn_type="PURCHASE", amount="100000"),
    _tx(code="C003", client_name="Kabir Nair", folio="F006", scheme="Apex Flexi Cap Fund", date_text="15-06-2026", txn_type="SWITCH IN", amount="15000", source_scheme="Apex PSU Equity Fund", target_scheme="Apex Flexi Cap Fund"),
    _tx(code="C004", client_name="Meera Iyer", folio="F007", scheme="Apex Large Cap Fund", date_text="15-01-2021", txn_type="PURCHASE", amount="70000"),
    _tx(code="C005", client_name="Rohan Patel", folio="F008", scheme="Apex Mid Cap 150 Index Fund", date_text="15-01-2025", txn_type="SIP", amount="14000"),
    _tx(code="C005", client_name="Rohan Patel", folio="F008", scheme="Apex Mid Cap 150 Index Fund", date_text="15-02-2025", txn_type="SIP", amount="14000"),
    _tx(code="C006", client_name="Ananya Rao", folio="F009", scheme="Apex Small Cap 250 Index Fund", date_text="15-01-2024", txn_type="PURCHASE", amount="65000"),
    _tx(code="C007", client_name="Vihaan Gupta", folio="F010", scheme="Apex Pharma Fund", date_text="15-01-2024", txn_type="PURCHASE", amount="50000"),
    _tx(code="C008", client_name="Isha Verma", folio="F011", scheme="Apex Public Sector Fund", date_text="15-01-2019", txn_type="PURCHASE", amount="85000"),
    _tx(code="C009", client_name="Arjun Singh", folio="F012", scheme="Apex Broad Market Fund", date_text="15-01-2025", txn_type="PURCHASE", amount="100000"),
    _tx(code="C010", client_name="Nisha Kulkarni", folio="F013", scheme="Apex Blue Chip Advantage Fund", date_text="15-01-2018", txn_type="PURCHASE", amount="120000"),
    _tx(code="C999", client_name="Unmatched Export Client", folio="F014", scheme="Apex Unknown Sector Fund", date_text="15-01-2023", txn_type="PURCHASE", amount="22000"),
]


def _write_clients(path: Path) -> None:
    from openpyxl import Workbook

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Client Details"
    sheet.append(
        [
            "IWELL CODE",
            "IWELL CODE 2",
            "APPCODE",
            "NAME",
            "First Investment Date",
            "AUM",
            "PAN",
            "Email",
            "Mobile",
            "Address",
            "KYC Status",
            "Bank Account No",
        ]
    )
    for code, code2, app_code, name, first_date, aum in CLIENTS:
        sheet.append(
            [
                code,
                code2,
                app_code,
                name,
                first_date,
                aum,
                "REDACTED",
                "redacted@example.invalid",
                "REDACTED",
                "REDACTED",
                "REDACTED",
                "REDACTED",
            ]
        )
    workbook.save(path)


def _write_folios(path: Path) -> None:
    from openpyxl import Workbook

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Folios"
    sheet.append(
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
        ]
    )
    for row in FOLIOS:
        sheet.append([*row, "REDACTED"])
    workbook.save(path)


def _write_portfolio(path: Path) -> None:
    from openpyxl import Workbook

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Portfolio Valuation"
    sheet.append(["Portfolio Valuation Report"])
    sheet.append(["Mutual fund portfolio snapshot"])
    sheet.append([f"Report printed on: {REPORT_DATE}"])
    sheet.append(
        [
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
        ]
    )
    for row in PORTFOLIO:
        sheet.append(list(row))
    sheet.append(
        [
            "",
            "",
            "Total",
            "",
            "",
            "1500000",
            "",
            "",
            "",
            "",
            "",
            "",
        ]
    )
    workbook.save(path)


def _write_transactions(path: Path) -> None:
    from openpyxl import Workbook

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Transactions"
    sheet.append(
        [
            "TRANSACTION DATE",
            "SCHEME NAME",
            "CATEGORY",
            "SUB CATEGORY",
            "FOLIO NO",
            "APPLICANT",
            "FAMILY HEAD",
            "PAN",
            "TXN TYPE",
            "EUIN",
            "TOTAL AMOUNT",
            "FUND NAME",
            "UNITS",
            "NAV",
            "STT",
            "TDS",
            "STAMP DUTY",
            "ARN NO",
            "TXN DESCRIPTION",
            "TXN SOURCE",
            "SIP REG DATE",
            "SOURCE SCHEME NAME",
            "TARGET SCHEME NAME",
            "REMARKS",
            "EQUITY CODE",
            "APP CODE",
            "IWELL CODE",
            "SB CODE",
            " OPERATIONS",
            " OPERATIONS CODE",
            " RELATIONSHIP  MANAGER",
            " RELATIONSHIP  MANAGER CODE",
            " SUB  BROKER",
            " SUB  BROKER CODE",
        ]
    )
    for row in DEMO_TRANSACTIONS:
        sheet.append(list(row))
    workbook.save(path)


def ensure_demo_files() -> dict[str, Path]:
    DEMO_DIR.mkdir(parents=True, exist_ok=True)
    paths = {
        "clients": DEMO_DIR / "demo_client_details.xlsx",
        "folios": DEMO_DIR / "demo_folios.xlsx",
        "portfolio": DEMO_DIR / "demo_portfolio_valuation.xlsx",
        "transactions": DEMO_DIR / "demo_transactions.xlsx",
    }
    if not paths["clients"].exists():
        _write_clients(paths["clients"])
    if not paths["folios"].exists():
        _write_folios(paths["folios"])
    if not paths["portfolio"].exists():
        _write_portfolio(paths["portfolio"])
    if not paths["transactions"].exists():
        _write_transactions(paths["transactions"])
    return paths


def load_demo_data(db: Session, replace: bool = False) -> dict:
    has_data = bool(db.scalar(select(func.count(UploadBatch.id))))
    if has_data and not replace:
        raise DemoDataExistsError(
            "Local data already exists. Confirm replacement before loading the demo."
        )

    paths = ensure_demo_files()
    files = {kind: (path.name, path) for kind, path in paths.items()}
    plan = preview_import(files)
    if not plan["can_confirm"]:
        raise ValueError("The demo workbook preview failed validation.")
    return confirm_import(db, plan["import_id"])


def latest_batch(db: Session) -> UploadBatch | None:
    return db.scalar(
        select(UploadBatch).order_by(UploadBatch.confirmed_at.desc()).limit(1)
    )


def demo_client_count(db: Session) -> int:
    return int(db.scalar(select(func.count(Client.id))) or 0)
