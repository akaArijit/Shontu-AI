"""Database engine and session helpers."""

from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.orm import Session, sessionmaker

from mfd_dashboard.core.paths import ensure_directories
from mfd_dashboard.core.settings import DATABASE_URL
from mfd_dashboard.db.base import Base


_is_sqlite = DATABASE_URL.startswith("sqlite")
_connect_args = {"check_same_thread": False} if _is_sqlite else {}

engine = create_engine(
    DATABASE_URL,
    connect_args=_connect_args,
    pool_pre_ping=True,
    future=True,
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
    class_=Session,
)


if _is_sqlite:

    @event.listens_for(engine, "connect")
    def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


def _ensure_sqlite_columns() -> None:
    """Add Milestone 2 columns to an existing local SQLite database.

    ``create_all`` creates new tables but does not alter existing ones.  The
    local app is not a migration framework, so this small, additive upgrade
    keeps an existing Milestone 1 database usable.  No existing column or row is
    changed.
    """

    if not _is_sqlite:
        return
    inspector = inspect(engine)
    if "upload_batches" not in inspector.get_table_names():
        return
    existing = {
        column["name"] for column in inspector.get_columns("upload_batches")
    }
    additions = {
        "transaction_file_name": "VARCHAR(255)",
        "transaction_hash": "VARCHAR(64)",
        "transaction_rows": "INTEGER NOT NULL DEFAULT 0",
        "transactions_imported": "INTEGER NOT NULL DEFAULT 0",
        "transaction_skipped": "INTEGER NOT NULL DEFAULT 0",
        "transactions_unmatched": "INTEGER NOT NULL DEFAULT 0",
        "switch_reviews": "INTEGER NOT NULL DEFAULT 0",
    }
    with engine.begin() as connection:
        for name, ddl in additions.items():
            if name not in existing:
                connection.execute(
                    text(f"ALTER TABLE upload_batches ADD COLUMN {name} {ddl}")
                )


def init_db() -> None:
    """Create the local tables if they do not exist yet."""

    ensure_directories()
    # Import models before create_all so every table is registered.
    from mfd_dashboard.db import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _ensure_sqlite_columns()


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
