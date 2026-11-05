"""Database models for the InvestWell snapshot import.

The Client Details, Folios and Portfolio Valuation exports are full snapshots.
The Transaction Statement is a dated ledger used for folio return calculations.
The schema therefore stores:

* the client master (matched by IWELL code where possible),
* folio holdings from the Folios export,
* one client-level valuation from the Portfolio Valuation export,
* dated transactions and paired switch legs,
* scheme-to-benchmark mappings with local review state,
* locally imported benchmark closing levels, and
* import issues / reconciliation warnings.

PAN and similar sensitive identifiers are intentionally absent.  Money and
units use ``Numeric`` so values read from the workbook are not distorted by
floating-point rounding.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from mfd_dashboard.db.base import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class UploadBatch(Base):
    """One confirmed set of the InvestWell files."""

    __tablename__ = "upload_batches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    import_id: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    client_file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    folios_file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    portfolio_file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    client_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    folios_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    portfolio_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    report_date: Mapped[date] = mapped_column(Date, nullable=False)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    confirmed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="confirmed")

    transaction_file_name: Mapped[str | None] = mapped_column(String(255))
    transaction_hash: Mapped[str | None] = mapped_column(String(64))
    client_rows: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    clients_imported: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    folio_rows: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    folios_imported: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    portfolio_rows: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    portfolio_imported: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    transaction_rows: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    transactions_imported: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )
    transaction_skipped: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )
    transactions_unmatched: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )
    switch_reviews: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    needs_review: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    unmatched_folios: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    unmatched_portfolio_rows: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )
    reconciliation_warnings: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )
    total_folio_aum: Mapped[Decimal | None] = mapped_column(Numeric(20, 2))
    total_client_current_value: Mapped[Decimal | None] = mapped_column(Numeric(20, 2))
    portfolio_total_current_value: Mapped[Decimal | None] = mapped_column(
        Numeric(20, 2)
    )
    notes: Mapped[str | None] = mapped_column(Text)

    issues: Mapped[list["ImportIssue"]] = relationship(
        back_populates="batch", cascade="all, delete-orphan"
    )
    folios: Mapped[list["Folio"]] = relationship(
        back_populates="batch", cascade="all, delete-orphan"
    )
    valuations: Mapped[list["PortfolioValuation"]] = relationship(
        back_populates="batch", cascade="all, delete-orphan"
    )
    transactions: Mapped[list["Transaction"]] = relationship(
        back_populates="batch", cascade="all, delete-orphan"
    )


class Client(Base):
    __tablename__ = "clients"
    __table_args__ = (
        Index("ix_clients_name_key", "name_key"),
        Index("ix_clients_iwell_code_key", "iwell_code_key"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(220), nullable=False)
    name_key: Mapped[str] = mapped_column(String(240), nullable=False)
    iwell_code: Mapped[str | None] = mapped_column(String(80))
    iwell_code_key: Mapped[str | None] = mapped_column(String(90))
    iwell_code_2: Mapped[str | None] = mapped_column(String(120))
    app_code: Mapped[str | None] = mapped_column(String(100))
    first_investment_date: Mapped[date | None] = mapped_column(Date)
    source_row: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    folios: Mapped[list["Folio"]] = relationship(back_populates="client")
    valuations: Mapped[list["PortfolioValuation"]] = relationship(
        back_populates="client"
    )
    transactions: Mapped[list["Transaction"]] = relationship(back_populates="client")
    identifiers: Mapped[list["ClientIdentifier"]] = relationship(
        back_populates="client", cascade="all, delete-orphan"
    )


class ClientIdentifier(Base):
    """Auditable matching identifiers.  No PAN or contact details are stored."""

    __tablename__ = "client_identifiers"
    __table_args__ = (
        UniqueConstraint(
            "client_id",
            "identifier_type",
            "normalized_value",
            name="uq_client_identifier_value",
        ),
        Index("ix_client_identifier_lookup", "identifier_type", "normalized_value"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    client_id: Mapped[int] = mapped_column(
        ForeignKey("clients.id", ondelete="CASCADE"), nullable=False
    )
    identifier_type: Mapped[str] = mapped_column(String(30), nullable=False)
    value: Mapped[str] = mapped_column(String(180), nullable=False)
    normalized_value: Mapped[str] = mapped_column(String(200), nullable=False)
    source_file: Mapped[str] = mapped_column(String(40), nullable=False, default="clients")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    client: Mapped[Client] = relationship(back_populates="identifiers")


class Scheme(Base):
    __tablename__ = "schemes"
    __table_args__ = (Index("ix_schemes_name_key", "name_key", unique=True),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    name_key: Mapped[str] = mapped_column(String(320), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(320), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    folios: Mapped[list["Folio"]] = relationship(back_populates="scheme")
    transactions: Mapped[list["Transaction"]] = relationship(
        back_populates="scheme"
    )
    benchmark: Mapped["SchemeBenchmark | None"] = relationship(
        back_populates="scheme", uselist=False
    )


class SchemeBenchmark(Base):
    """Scheme-to-benchmark mapping with local review state.

    Automatic keyword matches start as ``needs_review``.  A mapping saved from
    the local review screen becomes ``reviewed`` and is preserved when a new
    InvestWell snapshot is confirmed.
    """

    __tablename__ = "scheme_benchmarks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    scheme_id: Mapped[int] = mapped_column(
        ForeignKey("schemes.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    benchmark_name: Mapped[str] = mapped_column(String(180), nullable=False)
    normalized_scheme_name: Mapped[str] = mapped_column(String(320), nullable=False)
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="needs_review"
    )
    source: Mapped[str] = mapped_column(String(30), nullable=False, default="auto")
    notes: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    scheme: Mapped[Scheme] = relationship(back_populates="benchmark")


class BenchmarkLevel(Base):
    """One locally imported closing level for a benchmark and date.

    Levels are reference data, not part of an InvestWell snapshot, so a new
    snapshot import does not delete them.  The unique key uses a normalized
    benchmark name so casing and punctuation differences update the same row.
    """

    __tablename__ = "benchmark_levels"
    __table_args__ = (
        UniqueConstraint(
            "benchmark_name_key",
            "level_date",
            name="uq_benchmark_level_date",
        ),
        Index("ix_benchmark_levels_name", "benchmark_name_key"),
        Index("ix_benchmark_levels_date", "level_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    benchmark_name: Mapped[str] = mapped_column(String(180), nullable=False)
    benchmark_name_key: Mapped[str] = mapped_column(String(200), nullable=False)
    level_date: Mapped[date] = mapped_column(Date, nullable=False)
    level: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    source_file: Mapped[str] = mapped_column(String(255), nullable=False)
    imported_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class Folio(Base):
    """A folio/scheme holding.  A folio can hold multiple schemes."""

    __tablename__ = "folios"
    __table_args__ = (
        UniqueConstraint("dedupe_key", name="uq_folio_dedupe_key"),
        Index("ix_folios_client", "client_id"),
        Index("ix_folios_scheme", "scheme_id"),
        Index("ix_folios_batch", "batch_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    batch_id: Mapped[int] = mapped_column(
        ForeignKey("upload_batches.id", ondelete="CASCADE"), nullable=False
    )
    client_id: Mapped[int | None] = mapped_column(
        ForeignKey("clients.id", ondelete="CASCADE")
    )
    scheme_id: Mapped[int] = mapped_column(
        ForeignKey("schemes.id", ondelete="CASCADE"), nullable=False
    )
    folio_number: Mapped[str] = mapped_column(String(140), nullable=False)
    normalized_folio_number: Mapped[str] = mapped_column(String(160), nullable=False)
    folio_type: Mapped[str | None] = mapped_column(String(80))
    units: Mapped[Decimal | None] = mapped_column(Numeric(20, 4))
    aum: Mapped[Decimal | None] = mapped_column(Numeric(20, 2))
    value_date: Mapped[date] = mapped_column(Date, nullable=False)
    match_status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="matched"
    )
    match_note: Mapped[str | None] = mapped_column(Text)
    source_client_name: Mapped[str | None] = mapped_column(String(220))
    source_iwell_code: Mapped[str | None] = mapped_column(String(80))
    source_row: Mapped[int | None] = mapped_column(Integer)
    dedupe_key: Mapped[str] = mapped_column(String(500), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    batch: Mapped[UploadBatch] = relationship(back_populates="folios")
    client: Mapped[Client | None] = relationship(back_populates="folios")
    scheme: Mapped[Scheme] = relationship(back_populates="folios")
    transactions: Mapped[list["Transaction"]] = relationship(
        back_populates="folio"
    )


class PortfolioValuation(Base):
    """One client-level row from the Portfolio Valuation report."""

    __tablename__ = "portfolio_valuations"
    __table_args__ = (
        UniqueConstraint("dedupe_key", name="uq_portfolio_valuation_dedupe_key"),
        Index("ix_portfolio_valuations_client", "client_id"),
        Index("ix_portfolio_valuations_batch", "batch_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    batch_id: Mapped[int] = mapped_column(
        ForeignKey("upload_batches.id", ondelete="CASCADE"), nullable=False
    )
    client_id: Mapped[int | None] = mapped_column(
        ForeignKey("clients.id", ondelete="CASCADE")
    )
    valuation_date: Mapped[date] = mapped_column(Date, nullable=False)
    balance_units: Mapped[Decimal | None] = mapped_column(Numeric(20, 4))
    purchase_value: Mapped[Decimal | None] = mapped_column(Numeric(20, 2))
    current_value: Mapped[Decimal | None] = mapped_column(Numeric(20, 2))
    one_day_change: Mapped[Decimal | None] = mapped_column(Numeric(20, 2))
    dividend: Mapped[Decimal | None] = mapped_column(Numeric(20, 2))
    avg_holding_days: Mapped[int | None] = mapped_column(Integer)
    gain: Mapped[Decimal | None] = mapped_column(Numeric(20, 2))
    absolute_return: Mapped[Decimal | None] = mapped_column(Numeric(14, 4))
    cagr: Mapped[Decimal | None] = mapped_column(Numeric(14, 4))
    match_status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="matched"
    )
    match_note: Mapped[str | None] = mapped_column(Text)
    source_client_name: Mapped[str | None] = mapped_column(String(220))
    source_iwell_code: Mapped[str | None] = mapped_column(String(80))
    source_row: Mapped[int | None] = mapped_column(Integer)
    dedupe_key: Mapped[str] = mapped_column(String(500), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    batch: Mapped[UploadBatch] = relationship(back_populates="valuations")
    client: Mapped[Client | None] = relationship(back_populates="valuations")


class Transaction(Base):
    """One normalized transaction from the InvestWell transaction statement.

    PAN and other sensitive columns are never mapped or stored.  A transaction
    can be retained even when its folio or scheme cannot be matched; in that case
    it is excluded from calculations and shown as an import issue.
    """

    __tablename__ = "transactions"
    __table_args__ = (
        Index("ix_transactions_batch", "batch_id"),
        Index("ix_transactions_folio", "folio_id"),
        Index("ix_transactions_client", "client_id"),
        Index("ix_transactions_date", "transaction_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    batch_id: Mapped[int] = mapped_column(
        ForeignKey("upload_batches.id", ondelete="CASCADE"), nullable=False
    )
    folio_id: Mapped[int | None] = mapped_column(
        ForeignKey("folios.id", ondelete="CASCADE")
    )
    client_id: Mapped[int | None] = mapped_column(
        ForeignKey("clients.id", ondelete="CASCADE")
    )
    scheme_id: Mapped[int | None] = mapped_column(
        ForeignKey("schemes.id", ondelete="CASCADE")
    )
    transaction_date: Mapped[date | None] = mapped_column(Date)
    transaction_type_raw: Mapped[str] = mapped_column(String(160), nullable=False)
    transaction_type: Mapped[str] = mapped_column(String(30), nullable=False)
    amount: Mapped[Decimal | None] = mapped_column(Numeric(20, 2))
    units: Mapped[Decimal | None] = mapped_column(Numeric(20, 4))
    nav: Mapped[Decimal | None] = mapped_column(Numeric(20, 4))
    source_scheme_name: Mapped[str | None] = mapped_column(String(300))
    target_scheme_name: Mapped[str | None] = mapped_column(String(300))
    description: Mapped[str | None] = mapped_column(Text)
    source_folio_number: Mapped[str] = mapped_column(String(140), nullable=False)
    normalized_folio_number: Mapped[str] = mapped_column(String(160), nullable=False)
    source_iwell_code: Mapped[str | None] = mapped_column(String(80))
    source_client_name: Mapped[str | None] = mapped_column(String(220))
    match_status: Mapped[str] = mapped_column(
        String(40), nullable=False, default="matched"
    )
    review_note: Mapped[str | None] = mapped_column(Text)
    switch_pair_key: Mapped[str | None] = mapped_column(String(80))
    source_row: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    batch: Mapped[UploadBatch] = relationship(back_populates="transactions")
    folio: Mapped[Folio | None] = relationship(back_populates="transactions")
    client: Mapped[Client | None] = relationship(back_populates="transactions")
    scheme: Mapped[Scheme | None] = relationship(back_populates="transactions")


class ImportIssue(Base):
    __tablename__ = "import_issues"
    __table_args__ = (Index("ix_import_issues_batch", "batch_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    batch_id: Mapped[int] = mapped_column(
        ForeignKey("upload_batches.id", ondelete="CASCADE"), nullable=False
    )
    file_type: Mapped[str] = mapped_column(String(40), nullable=False)
    row_number: Mapped[int | None] = mapped_column(Integer)
    field: Mapped[str | None] = mapped_column(String(100))
    message: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False, default="warning")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    batch: Mapped[UploadBatch] = relationship(back_populates="issues")
