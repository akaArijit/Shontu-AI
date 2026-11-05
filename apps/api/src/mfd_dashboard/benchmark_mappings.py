"""Local benchmark mapping review, bulk rules and mapping-file exchange."""

from __future__ import annotations

import csv
import io
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Any, Iterable

from openpyxl import Workbook, load_workbook
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from mfd_dashboard.benchmark_coverage import build_benchmark_coverage
from mfd_dashboard.benchmark_data import (
    benchmark_level_names,
    benchmark_level_summaries,
)
from mfd_dashboard.benchmarks import (
    benchmark_master_names,
    benchmark_names,
    match_benchmark_detail,
    _matches,
)
from mfd_dashboard.db.models import Folio, Scheme, SchemeBenchmark
from mfd_dashboard.ingest.values import clean_text, normalize_header

DEFAULT_BENCHMARK = "Other / Unmapped"
MAX_IMPORT_ROWS = 100_000
MAX_IMPORT_ISSUES = 200

EXPORT_COLUMNS = [
    "scheme_id",
    "scheme_name",
    "normalized_scheme_name",
    "benchmark_name",
    "review_status",
    "folio_count",
    "source",
]

MAPPING_HEADER_ALIASES = {
    "scheme_id": {"scheme id", "scheme_id", "id"},
    "scheme_name": {
        "scheme name",
        "scheme_name",
        "scheme",
        "original scheme name",
    },
    "normalized_scheme_name": {
        "normalized scheme name",
        "normalized_scheme_name",
        "normalized name",
    },
    "benchmark_name": {
        "benchmark name",
        "benchmark_name",
        "benchmark",
        "mapping",
        "benchmark mapping",
    },
    "review_status": {"review status", "review_status", "status"},
    "folio_count": {"folio count", "folio_count", "folios"},
    "source": {"source", "mapping source"},
}


def _is_default(benchmark_name: str | None) -> bool:
    return normalize_header(benchmark_name) == normalize_header(DEFAULT_BENCHMARK)


def _folio_counts_by_scheme(db: Session) -> dict[int, int]:
    rows = db.execute(
        select(Folio.scheme_id, func.count(Folio.id))
        .where(Folio.scheme_id.is_not(None))
        .group_by(Folio.scheme_id)
    ).all()
    return {
        int(scheme_id): int(count)
        for scheme_id, count in rows
        if scheme_id is not None
    }


def _unmapped_folio_count(db: Session) -> int:
    """Count folios whose scheme has no reviewed, real benchmark."""

    mapped_schemes = select(SchemeBenchmark.scheme_id).where(
        SchemeBenchmark.benchmark_name != DEFAULT_BENCHMARK
    )
    count = db.scalar(
        select(func.count(Folio.id)).where(
            Folio.scheme_id.is_not(None),
            Folio.scheme_id.not_in(mapped_schemes),
        )
    )
    return int(count or 0)


def _suggestion(scheme: Scheme, mapping: SchemeBenchmark | None) -> dict[str, Any]:
    detail = match_benchmark_detail(scheme.name)
    keyword_name = str(detail.get("benchmark_name") or DEFAULT_BENCHMARK)
    automatic_name = (
        mapping.benchmark_name
        if mapping is not None
        and mapping.source == "auto"
        and mapping.benchmark_name
        and not _is_default(mapping.benchmark_name)
        else None
    )
    if not _is_default(keyword_name):
        return {
            "suggested_benchmark": keyword_name,
            "suggestion_keyword": detail.get("matched_keyword"),
            "suggestion_source": "keyword rule",
            "suggestion_match_type": detail.get("match_type"),
            "suggestion_confidence": detail.get("confidence"),
            "suggestion_reason": detail.get("reason"),
        }
    if automatic_name:
        return {
            "suggested_benchmark": automatic_name,
            "suggestion_keyword": None,
            "suggestion_source": "imported automatic suggestion",
            "suggestion_match_type": None,
            "suggestion_confidence": None,
            "suggestion_reason": None,
        }
    return {
        "suggested_benchmark": None,
        "suggestion_keyword": None,
        "suggestion_source": None,
        "suggestion_match_type": None,
        "suggestion_confidence": None,
        "suggestion_reason": None,
    }


def _mapping_dict(
    scheme: Scheme,
    mapping: SchemeBenchmark | None,
    level_counts: dict[str, int],
    coverage: dict[str, Any] | None,
    folio_count: int,
) -> dict[str, Any]:
    benchmark_name = (
        mapping.benchmark_name
        if mapping is not None
        else DEFAULT_BENCHMARK
    )
    review_status = (
        "needs_mapping"
        if mapping is None or _is_default(benchmark_name)
        else mapping.status
    )
    benchmark_key = normalize_header(benchmark_name)
    coverage = coverage or {}
    return {
        "scheme_id": scheme.id,
        "scheme_name": scheme.name,
        "normalized_scheme_name": (
            mapping.normalized_scheme_name
            if mapping is not None
            else scheme.normalized_name
        ),
        "benchmark_name": benchmark_name,
        "review_status": review_status,
        "source": mapping.source if mapping is not None else "none",
        "folio_count": folio_count,
        "level_count": level_counts.get(benchmark_key, 0),
        "coverage_status": coverage.get("coverage_status", "unknown"),
        "coverage_missing_dates": coverage.get("missing_dates", []),
        "coverage_missing_date_count": coverage.get("missing_date_count", 0),
        "coverage_required_date_count": coverage.get("required_date_count", 0),
        "covers_first_transaction": coverage.get("covers_first_transaction"),
        "covers_valuation_date": coverage.get("covers_valuation_date"),
        "covers_all_comparison_dates": coverage.get(
            "covers_all_comparison_dates"
        ),
        "first_transaction_date": coverage.get("first_transaction_date"),
        "updated_at": (
            mapping.updated_at.isoformat()
            if mapping is not None and mapping.updated_at is not None
            else None
        ),
        **_suggestion(scheme, mapping),
    }


def available_benchmark_names(
    db: Session,
    *,
    include_default: bool = False,
    include_master: bool = True,
) -> list[str]:
    names = {
        name
        for name in benchmark_names()
        if include_default or not _is_default(name)
    }
    if include_master:
        names.update(
            name
            for name in benchmark_master_names()
            if include_default or not _is_default(name)
        )
    names.update(benchmark_level_names(db))
    names.update(
        item.benchmark_name
        for item in db.scalars(select(SchemeBenchmark))
        if item.benchmark_name and not _is_default(item.benchmark_name)
    )
    return sorted(names, key=str.casefold)


def _summary(mappings: list[dict[str, Any]]) -> dict[str, Any]:
    """The original four-key mapping summary kept for existing consumers."""

    reviewed = sum(1 for item in mappings if item["review_status"] == "reviewed")
    needs_review = sum(
        1 for item in mappings if item["review_status"] == "needs_review"
    )
    unmapped = sum(
        1 for item in mappings if item["review_status"] == "needs_mapping"
    )
    return {
        "schemes": len(mappings),
        "reviewed": reviewed,
        "needs_review": needs_review,
        "unmapped": unmapped,
    }


def _status_summary(mappings: list[dict[str, Any]]) -> dict[str, Any]:
    base = _summary(mappings)
    reviewed = base["reviewed"]
    needs_review = base["needs_review"]
    unmapped = base["unmapped"]
    mapped = reviewed + needs_review
    total_folios = sum(int(item["folio_count"]) for item in mappings)
    mapped_folios = sum(
        int(item["folio_count"])
        for item in mappings
        if item["review_status"] != "needs_mapping"
    )
    needs_review_folios = sum(
        int(item["folio_count"])
        for item in mappings
        if item["review_status"] == "needs_review"
    )
    unmapped_folios = sum(
        int(item["folio_count"])
        for item in mappings
        if item["review_status"] == "needs_mapping"
    )
    suggested = [
        item
        for item in mappings
        if item.get("suggested_benchmark")
        and item["review_status"] != "reviewed"
    ]
    return {
        "total_schemes": len(mappings),
        "mapped_schemes": mapped,
        "reviewed_schemes": reviewed,
        "needs_review_schemes": needs_review,
        "unmapped_schemes": unmapped,
        "total_folios": total_folios,
        "mapped_folios": mapped_folios,
        "needs_review_folios": needs_review_folios,
        "unmapped_folios": unmapped_folios,
        "suggested_schemes": len(suggested),
        "suggested_folios": sum(int(item["folio_count"]) for item in suggested),
    }


def list_benchmark_mappings(db: Session) -> dict[str, Any]:
    schemes = db.scalars(
        select(Scheme)
        .options(joinedload(Scheme.benchmark))
        .order_by(Scheme.name)
    ).all()
    level_counts = {
        normalize_header(item["benchmark_name"]): item["level_count"]
        for item in benchmark_level_summaries(db)
    }
    folio_counts = _folio_counts_by_scheme(db)
    coverage = build_benchmark_coverage(db)
    coverage_by_scheme = {
        item["scheme_id"]: item for item in coverage["schemes"]
    }
    mappings = [
        _mapping_dict(
            scheme,
            scheme.benchmark,
            level_counts,
            coverage_by_scheme.get(scheme.id),
            folio_counts.get(scheme.id, 0),
        )
        for scheme in schemes
    ]
    return {
        "mappings": mappings,
        "available_benchmarks": available_benchmark_names(db),
        "summary": _summary(mappings),
        "status_summary": _status_summary(mappings),
        "coverage": coverage,
    }


def _resolve_benchmark_name(db: Session, benchmark_name: str) -> str:
    cleaned = clean_text(benchmark_name)
    if not cleaned:
        raise ValueError("Choose a benchmark before saving.")
    if _is_default(cleaned):
        raise ValueError(
            "Choose a real benchmark. 'Other / Unmapped' cannot be reviewed."
        )
    allowed = {
        normalize_header(name): name
        for name in available_benchmark_names(db)
    }
    resolved = allowed.get(normalize_header(cleaned))
    if resolved is None:
        raise ValueError(
            f"Benchmark '{cleaned}' is not available. Import local benchmark levels "
            "for that benchmark first, then choose it here."
        )
    return resolved


def _write_mapping(
    db: Session,
    scheme: Scheme,
    benchmark_name: str,
    *,
    source: str,
    notes: str,
    now: datetime,
) -> None:
    mapping = scheme.benchmark
    if mapping is None:
        mapping = SchemeBenchmark(
            scheme_id=scheme.id,
            benchmark_name=benchmark_name,
            normalized_scheme_name=scheme.normalized_name,
            status="reviewed",
            source=source,
            notes=notes,
            updated_at=now,
        )
        db.add(mapping)
    else:
        mapping.benchmark_name = benchmark_name
        mapping.status = "reviewed"
        mapping.source = source
        mapping.notes = notes
        mapping.updated_at = now


def _finish_change(
    db: Session,
    *,
    updated_schemes: int,
    updated_folios: int,
    before_unmapped_folios: int,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    db.commit()
    payload = list_benchmark_mappings(db)
    after_unmapped = _unmapped_folio_count(db)
    payload.update(
        {
            "updated_schemes": updated_schemes,
            "updated_folios": updated_folios,
            "previous_unmapped_folios": before_unmapped_folios,
            "unmapped_folios": after_unmapped,
            "folios_moved_out_of_unmapped": max(
                0, before_unmapped_folios - after_unmapped
            ),
        }
    )
    if extra:
        payload.update(extra)
    return payload


def _bulk_update(
    db: Session,
    scheme_ids: Iterable[int],
    benchmark_name: str,
    *,
    source: str,
    notes: str,
) -> dict[str, Any]:
    resolved = _resolve_benchmark_name(db, benchmark_name)
    ids = list(dict.fromkeys(int(value) for value in scheme_ids))
    if not ids:
        raise ValueError("Select at least one scheme before applying a benchmark.")

    schemes = list(
        db.scalars(
            select(Scheme)
            .options(joinedload(Scheme.benchmark))
            .where(Scheme.id.in_(ids))
        )
    )
    found = {scheme.id for scheme in schemes}
    missing = [value for value in ids if value not in found]
    if missing:
        raise ValueError(
            "Some selected schemes no longer exist. Refresh the page and select "
            f"them again. Missing scheme id(s): {', '.join(map(str, missing[:10]))}."
        )

    folio_counts = _folio_counts_by_scheme(db)
    before = _unmapped_folio_count(db)
    now = datetime.now(timezone.utc)
    updated_folios = 0
    for scheme in schemes:
        _write_mapping(
            db,
            scheme,
            resolved,
            source=source,
            notes=notes,
            now=now,
        )
        updated_folios += folio_counts.get(scheme.id, 0)

    return _finish_change(
        db,
        updated_schemes=len(schemes),
        updated_folios=updated_folios,
        before_unmapped_folios=before,
    )


def update_benchmark_mapping(
    db: Session,
    scheme_id: int,
    benchmark_name: str,
) -> dict[str, Any]:
    scheme = db.get(Scheme, scheme_id)
    if scheme is None:
        raise LookupError("Scheme not found.")

    payload = _bulk_update(
        db,
        [scheme_id],
        benchmark_name,
        source="manual",
        notes="Reviewed in the local Benchmark Mapping screen.",
    )
    item = next(
        row for row in payload["mappings"] if row["scheme_id"] == scheme_id
    )
    return {
        "mapping": item,
        "summary": payload["summary"],
        "status_summary": payload["status_summary"],
        "available_benchmarks": payload["available_benchmarks"],
        "coverage": payload["coverage"],
        "folios_moved_out_of_unmapped": payload[
            "folios_moved_out_of_unmapped"
        ],
        "unmapped_folios": payload["unmapped_folios"],
    }


def bulk_update_benchmark_mappings(
    db: Session,
    scheme_ids: Iterable[int],
    benchmark_name: str,
) -> dict[str, Any]:
    return _bulk_update(
        db,
        scheme_ids,
        benchmark_name,
        source="bulk",
        notes="Applied to multiple schemes from the bulk mapping tool.",
    )


def accept_benchmark_suggestions(
    db: Session,
    scheme_ids: Iterable[int] | None = None,
) -> dict[str, Any]:
    """Accept only suggestions that are already visible for a scheme.

    No new benchmark is guessed.  A scheme is eligible when its existing
    imported mapping is an automatic suggestion, or when the configured
    scheme-name keyword rule produces a real benchmark.
    """

    requested = (
        {int(value) for value in scheme_ids} if scheme_ids is not None else None
    )
    if requested is not None and not requested:
        raise ValueError("Select at least one scheme before accepting suggestions.")

    schemes = list(
        db.scalars(
            select(Scheme)
            .options(joinedload(Scheme.benchmark))
            .order_by(Scheme.name)
        )
    )
    allowed = {
        normalize_header(name): name
        for name in available_benchmark_names(db)
    }
    folio_counts = _folio_counts_by_scheme(db)
    candidates: list[tuple[Scheme, str]] = []
    for scheme in schemes:
        if requested is not None and scheme.id not in requested:
            continue
        mapping = scheme.benchmark
        if mapping is not None and mapping.status == "reviewed":
            continue
        suggestion = _suggestion(scheme, mapping)
        name = suggestion.get("suggested_benchmark")
        if not name or _is_default(str(name)):
            continue
        resolved = allowed.get(normalize_header(str(name)))
        if resolved is None:
            # Never silently accept a benchmark that cannot be resolved.
            continue
        candidates.append((scheme, resolved))

    if not candidates:
        return _finish_change(
            db,
            updated_schemes=0,
            updated_folios=0,
            before_unmapped_folios=_unmapped_folio_count(db),
            extra={"accepted_schemes": 0, "accepted_folios": 0},
        )

    before = _unmapped_folio_count(db)
    now = datetime.now(timezone.utc)
    updated_folios = 0
    for scheme, resolved in candidates:
        _write_mapping(
            db,
            scheme,
            resolved,
            source="accepted_suggestion",
            notes=(
                "Automatic suggestion approved from the bulk mapping tools. "
                "The mapping remains reviewable in the scheme table."
            ),
            now=now,
        )
        updated_folios += folio_counts.get(scheme.id, 0)

    return _finish_change(
        db,
        updated_schemes=len(candidates),
        updated_folios=updated_folios,
        before_unmapped_folios=before,
        extra={
            "accepted_schemes": len(candidates),
            "accepted_folios": updated_folios,
        },
    )


def accept_high_confidence_suggestions(
    db: Session,
) -> dict[str, Any]:
    """Accept only high-confidence automatic suggestions for all schemes.

    Only applies suggestions with 'high' confidence from keyword rules.
    Does not apply medium/low confidence or imported automatic suggestions.
    """

    schemes = list(
        db.scalars(
            select(Scheme)
            .options(joinedload(Scheme.benchmark))
            .order_by(Scheme.name)
        )
    )
    allowed = {
        normalize_header(name): name
        for name in available_benchmark_names(db)
    }
    folio_counts = _folio_counts_by_scheme(db)
    candidates: list[tuple[Scheme, str]] = []
    for scheme in schemes:
        mapping = scheme.benchmark
        if mapping is not None and mapping.status == "reviewed":
            continue
        suggestion = _suggestion(scheme, mapping)
        name = suggestion.get("suggested_benchmark")
        if not name or _is_default(str(name)):
            continue
        # Only accept high-confidence keyword rule suggestions
        confidence = suggestion.get("suggestion_confidence")
        if confidence != "high":
            continue
        match_type = suggestion.get("suggestion_match_type")
        if match_type != "category":
            continue
        resolved = allowed.get(normalize_header(str(name)))
        if resolved is None:
            continue
        candidates.append((scheme, resolved))

    if not candidates:
        return _finish_change(
            db,
            updated_schemes=0,
            updated_folios=0,
            before_unmapped_folios=_unmapped_folio_count(db),
            extra={"accepted_schemes": 0, "accepted_folios": 0},
        )

    before = _unmapped_folio_count(db)
    now = datetime.now(timezone.utc)
    updated_folios = 0
    for scheme, resolved in candidates:
        _write_mapping(
            db,
            scheme,
            resolved,
            source="accepted_suggestion",
            notes=(
                "High-confidence automatic suggestion approved from the bulk mapping tools. "
                "The mapping remains reviewable in the scheme table."
            ),
            now=now,
        )
        updated_folios += folio_counts.get(scheme.id, 0)

    return _finish_change(
        db,
        updated_schemes=len(candidates),
        updated_folios=updated_folios,
        before_unmapped_folios=before,
        extra={
            "accepted_schemes": len(candidates),
            "accepted_folios": updated_folios,
        },
    )


def keyword_mapping_rule(
    db: Session,
    keyword: str,
    benchmark_name: str,
    *,
    apply: bool = False,
) -> dict[str, Any]:
    """Preview or apply a keyword rule at scheme level."""

    resolved = _resolve_benchmark_name(db, benchmark_name)
    normalized_keyword = normalize_header(keyword)
    if not normalized_keyword:
        raise ValueError("Enter a keyword such as 'Small Cap' before previewing.")

    payload = list_benchmark_mappings(db)
    matched = [
        item
        for item in payload["mappings"]
        if _matches(item["scheme_name"], keyword)
        or _matches(str(item["normalized_scheme_name"]), keyword)
    ]
    matched_ids = [item["scheme_id"] for item in matched]
    result: dict[str, Any] = {
        "keyword": clean_text(keyword),
        "normalized_keyword": normalized_keyword,
        "benchmark_name": resolved,
        "rule": (
            f"If the scheme name contains '{clean_text(keyword)}', map it to "
            f"'{resolved}'."
        ),
        "apply": apply,
        "matched_scheme_count": len(matched),
        "matched_folio_count": sum(
            int(item["folio_count"]) for item in matched
        ),
        "matched_unmapped_scheme_count": sum(
            1 for item in matched if item["review_status"] == "needs_mapping"
        ),
        "matched_unmapped_folio_count": sum(
            int(item["folio_count"])
            for item in matched
            if item["review_status"] == "needs_mapping"
        ),
        "matched_schemes": matched,
        "can_apply": bool(matched),
        "errors": [] if matched else ["No scheme name contains that keyword."],
    }
    if apply:
        if not matched:
            raise ValueError("No scheme name contains that keyword.")
        applied = _bulk_update(
            db,
            matched_ids,
            resolved,
            source="keyword_rule",
            notes=f"Bulk keyword rule: {result['rule']}",
        )
        result.update(
            {
                "apply": True,
                "mappings": applied["mappings"],
                "summary": applied["summary"],
                "status_summary": applied["status_summary"],
                "available_benchmarks": applied["available_benchmarks"],
                "coverage": applied["coverage"],
                "updated_schemes": applied["updated_schemes"],
                "updated_folios": applied["updated_folios"],
                "previous_unmapped_folios": applied[
                    "previous_unmapped_folios"
                ],
                "unmapped_folios": applied["unmapped_folios"],
                "folios_moved_out_of_unmapped": applied[
                    "folios_moved_out_of_unmapped"
                ],
            }
        )
    return result


def _mapping_export_rows(db: Session) -> list[dict[str, Any]]:
    payload = list_benchmark_mappings(db)
    return [
        {
            "scheme_id": item["scheme_id"],
            "scheme_name": item["scheme_name"],
            "normalized_scheme_name": item["normalized_scheme_name"],
            "benchmark_name": item["benchmark_name"],
            "review_status": item["review_status"],
            "folio_count": item["folio_count"],
            "source": item["source"],
        }
        for item in payload["mappings"]
    ]


def export_benchmark_mappings(
    db: Session,
    export_format: str = "csv",
) -> tuple[bytes, str, str]:
    normalized_format = export_format.casefold()
    if normalized_format not in {"csv", "xlsx"}:
        raise ValueError("Choose CSV or XLSX for the mapping export.")
    rows = _mapping_export_rows(db)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    if normalized_format == "csv":
        buffer = io.StringIO(newline="")
        writer = csv.DictWriter(buffer, fieldnames=EXPORT_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
        return (
            buffer.getvalue().encode("utf-8-sig"),
            "text/csv; charset=utf-8",
            f"scheme-benchmark-mappings-{stamp}.csv",
        )

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Scheme mappings"
    sheet.append(EXPORT_COLUMNS)
    for row in rows:
        sheet.append([row[column] for column in EXPORT_COLUMNS])
    sheet.freeze_panes = "A2"
    buffer_bytes = BytesIO()
    workbook.save(buffer_bytes)
    return (
        buffer_bytes.getvalue(),
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        f"scheme-benchmark-mappings-{stamp}.xlsx",
    )


def _header_index(headers: list[Any]) -> dict[str, int]:
    result: dict[str, int] = {}
    for index, header in enumerate(headers):
        normalized = normalize_header(header)
        for canonical, aliases in MAPPING_HEADER_ALIASES.items():
            if normalized in aliases:
                result.setdefault(canonical, index)
                break
    return result


def _find_header(
    rows: Iterable[list[Any]],
) -> tuple[list[Any] | None, int | None, list[list[Any]]]:
    buffered = list(rows)
    for index, row in enumerate(buffered[:10]):
        if not any(clean_text(value) for value in row):
            continue
        headers = _header_index(row)
        if "scheme_name" in headers or "scheme_id" in headers:
            if "benchmark_name" in headers:
                return row, index, buffered
    return None, None, buffered


def _read_mapping_file(
    filename: str,
    content: bytes,
) -> tuple[str, str, int, dict[str, int], list[list[Any]]]:
    if not content:
        raise ValueError("The mapping file is empty.")
    suffix = Path(filename or "").suffix.casefold()
    if suffix not in {".csv", ".xlsx"}:
        raise ValueError("The mapping file must be a .csv or .xlsx file.")

    if suffix == ".csv":
        try:
            text = content.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise ValueError(
                "The CSV mapping file is not valid UTF-8. Export it again or save "
                "it as UTF-8 CSV."
            ) from exc
        all_rows = list(csv.reader(io.StringIO(text, newline="")))
        sheet_name = "CSV"
        detected_format = "csv"
    else:
        try:
            workbook = load_workbook(
                BytesIO(content),
                read_only=True,
                data_only=True,
            )
        except Exception as exc:  # openpyxl raises several unrelated types
            raise ValueError(
                "The XLSX mapping file could not be opened. Export it again or "
                "use a CSV file."
            ) from exc
        sheet = workbook.active
        sheet_name = sheet.title
        detected_format = "xlsx"
        all_rows = [list(row) for row in sheet.iter_rows(values_only=True)]

    header, header_index, rows = _find_header(all_rows)
    if header is None or header_index is None:
        raise ValueError(
            "The mapping file must include a Scheme Name (or Scheme ID) column "
            "and a Benchmark Name column in the first 10 rows."
        )
    indexes = _header_index(header)
    data_rows = rows[header_index + 1 :]
    if len(data_rows) > MAX_IMPORT_ROWS:
        raise ValueError(
            f"The mapping file has more than {MAX_IMPORT_ROWS:,} data rows. "
            "Split it into smaller files."
        )
    return (
        detected_format,
        str(sheet_name or ""),
        header_index + 1,
        indexes,
        data_rows,
    )


def _value_at(row: list[Any], index: int | None) -> str:
    if index is None or index >= len(row):
        return ""
    return clean_text(row[index])


def preview_mapping_import(
    db: Session,
    filename: str,
    content: bytes,
) -> dict[str, Any]:
    """Validate a mapping CSV/XLSX without changing the database."""

    (
        detected_format,
        sheet_name,
        header_row,
        indexes,
        rows,
    ) = _read_mapping_file(filename, content)

    schemes = list(
        db.scalars(
            select(Scheme).options(joinedload(Scheme.benchmark))
        )
    )
    schemes_by_id = {scheme.id: scheme for scheme in schemes}
    schemes_by_name = {
        scheme.normalized_name: scheme for scheme in schemes
    }
    allowed = {
        normalize_header(name): name
        for name in available_benchmark_names(db)
    }
    folio_counts = _folio_counts_by_scheme(db)

    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    changes: list[dict[str, Any]] = []
    error_count = 0
    warning_count = 0
    skipped = 0
    unchanged = 0
    seen_schemes: dict[int, int] = {}

    def add_error(row_number: int, field: str, message: str) -> None:
        nonlocal error_count
        error_count += 1
        if len(errors) < MAX_IMPORT_ISSUES:
            errors.append(
                {
                    "row_number": row_number,
                    "field": field,
                    "message": message,
                }
            )

    def add_warning(row_number: int, field: str, message: str) -> None:
        nonlocal warning_count
        warning_count += 1
        if len(warnings) < MAX_IMPORT_ISSUES:
            warnings.append(
                {
                    "row_number": row_number,
                    "field": field,
                    "message": message,
                }
            )

    for offset, row in enumerate(rows):
        row_number = header_row + offset + 1
        if not any(clean_text(value) for value in row):
            continue
        scheme_id_text = _value_at(row, indexes.get("scheme_id"))
        scheme_name = _value_at(row, indexes.get("scheme_name"))
        normalized_name = _value_at(
            row, indexes.get("normalized_scheme_name")
        )
        benchmark_text = _value_at(row, indexes.get("benchmark_name"))

        scheme: Scheme | None = None
        if scheme_id_text:
            try:
                scheme_id = int(float(scheme_id_text))
            except ValueError:
                add_error(
                    row_number,
                    "scheme_id",
                    f"Scheme ID '{scheme_id_text}' is not a number.",
                )
                continue
            scheme = schemes_by_id.get(scheme_id)
            if scheme is None:
                add_error(
                    row_number,
                    "scheme_id",
                    f"Scheme ID {scheme_id} does not exist in the current snapshot.",
                )
                continue
            if scheme_name and normalize_header(scheme_name) != scheme.normalized_name:
                add_error(
                    row_number,
                    "scheme_name",
                    (
                        f"Scheme ID {scheme_id} belongs to '{scheme.name}', but "
                        f"the row says '{scheme_name}'. Fix the row before importing."
                    ),
                )
                continue
        else:
            lookup = normalize_header(scheme_name or normalized_name)
            if not lookup:
                add_error(
                    row_number,
                    "scheme_name",
                    "Each row needs a Scheme Name or Scheme ID.",
                )
                continue
            scheme = schemes_by_name.get(lookup)
            if scheme is None:
                add_error(
                    row_number,
                    "scheme_name",
                    (
                        f"Scheme '{clean_text(scheme_name or normalized_name)}' "
                        "was not found in the current snapshot."
                    ),
                )
                continue

        if scheme.id in seen_schemes:
            add_error(
                row_number,
                "scheme_name",
                (
                    f"Scheme '{scheme.name}' appears more than once (first on "
                    f"row {seen_schemes[scheme.id]})."
                ),
            )
            continue
        seen_schemes[scheme.id] = row_number

        if not benchmark_text or _is_default(benchmark_text):
            skipped += 1
            add_warning(
                row_number,
                "benchmark_name",
                (
                    f"'{scheme.name}' has no real benchmark in this file, so it "
                    "is left unchanged."
                ),
            )
            continue

        resolved = allowed.get(normalize_header(benchmark_text))
        if resolved is None:
            add_error(
                row_number,
                "benchmark_name",
                (
                    f"Benchmark '{benchmark_text}' is not available locally. "
                    "Import its benchmark levels first or use an existing name."
                ),
            )
            continue

        mapping = scheme.benchmark
        current = (
            mapping.benchmark_name if mapping is not None else DEFAULT_BENCHMARK
        )
        current_status = (
            "needs_mapping"
            if mapping is None or _is_default(current)
            else mapping.status
        )
        review_text = normalize_header(
            _value_at(row, indexes.get("review_status"))
        )
        requests_review = review_text in {"reviewed", "approved", "yes", "true"}
        same_benchmark = (
            not _is_default(current)
            and normalize_header(current) == normalize_header(resolved)
        )
        if same_benchmark and mapping is not None:
            # Re-importing an exported table without edits is a no-op.  A row
            # only becomes a change when its Benchmark Name differs or its
            # Review Status is explicitly set to reviewed.
            action = (
                "approve"
                if mapping.status != "reviewed" and requests_review
                else "unchanged"
            )
        else:
            action = "map"
        if action == "unchanged":
            unchanged += 1
        changes.append(
            {
                "row_number": row_number,
                "scheme_id": scheme.id,
                "scheme_name": scheme.name,
                "current_benchmark": current,
                "current_status": current_status,
                "benchmark_name": resolved,
                "action": action,
                "folio_count": folio_counts.get(scheme.id, 0),
            }
        )

    valid_changes = [item for item in changes if item["action"] != "unchanged"]
    can_apply = error_count == 0 and bool(valid_changes)
    if error_count == 0 and not valid_changes:
        add_error(
            header_row,
            "file",
            (
                "The file did not contain any mapping changes with a real, "
                "available benchmark."
            ),
        )
        can_apply = False

    return {
        "file_name": Path(filename or "mapping-file").name,
        "detected_format": detected_format,
        "sheet_name": sheet_name,
        "header_row": header_row,
        "row_count": len(changes) + skipped + error_count,
        "valid_count": len(changes),
        "change_count": len(valid_changes),
        "unchanged_count": unchanged,
        "skipped_count": skipped,
        "error_count": error_count,
        "warning_count": warning_count,
        "issues_truncated": (
            error_count > len(errors) or warning_count > len(warnings)
        ),
        "can_apply": can_apply,
        "errors": errors,
        "warnings": warnings,
        "changes": changes,
        "summary": {
            "valid_rows": len(changes),
            "change_rows": len(valid_changes),
            "unchanged_rows": unchanged,
            "skipped_rows": skipped,
            "errors": error_count,
            "warnings": warning_count,
            "schemes_to_update": len(
                {item["scheme_id"] for item in valid_changes}
            ),
            "folios_affected": sum(
                int(item["folio_count"]) for item in valid_changes
            ),
            "unmapped_folios_affected": sum(
                int(item["folio_count"])
                for item in valid_changes
                if item["current_status"] == "needs_mapping"
            ),
        },
    }


def apply_mapping_import(
    db: Session,
    filename: str,
    content: bytes,
) -> dict[str, Any]:
    preview = preview_mapping_import(db, filename, content)
    if preview["error_count"]:
        first = preview["errors"][0]["message"] if preview["errors"] else ""
        raise ValueError(
            "The mapping file was not applied because validation found "
            f"{preview['error_count']} error(s). {first}"
        )
    changes = [
        item for item in preview["changes"] if item["action"] != "unchanged"
    ]
    if not changes:
        raise ValueError(
            "The mapping file was not applied because it contains no changes."
        )

    grouped: dict[str, list[int]] = {}
    for item in changes:
        grouped.setdefault(item["benchmark_name"], []).append(item["scheme_id"])

    before = _unmapped_folio_count(db)
    folio_counts = _folio_counts_by_scheme(db)
    updated_folios = sum(
        folio_counts.get(item["scheme_id"], 0) for item in changes
    )
    now = datetime.now(timezone.utc)
    schemes = {
        scheme.id: scheme
        for scheme in db.scalars(
            select(Scheme)
            .options(joinedload(Scheme.benchmark))
            .where(Scheme.id.in_([item["scheme_id"] for item in changes]))
        )
    }
    for benchmark_name, scheme_ids in grouped.items():
        for scheme_id in scheme_ids:
            scheme = schemes.get(scheme_id)
            if scheme is None:
                raise ValueError(
                    f"Scheme ID {scheme_id} disappeared while applying the file. "
                    "Nothing was saved."
                )
            _write_mapping(
                db,
                scheme,
                benchmark_name,
                source="imported_file",
                notes=(
                    "Applied from a validated scheme-to-benchmark mapping file. "
                    "The mapping remains reviewable in the scheme table."
                ),
                now=now,
            )

    applied = _finish_change(
        db,
        updated_schemes=len({item["scheme_id"] for item in changes}),
        updated_folios=updated_folios,
        before_unmapped_folios=before,
    )
    preview.update(
        {
            "applied": True,
            "mappings": applied["mappings"],
            "mapping_summary": applied["summary"],
            "status_summary": applied["status_summary"],
            "available_benchmarks": applied["available_benchmarks"],
            "coverage": applied["coverage"],
            "updated_schemes": applied["updated_schemes"],
            "updated_folios": applied["updated_folios"],
            "previous_unmapped_folios": applied["previous_unmapped_folios"],
            "unmapped_folios": applied["unmapped_folios"],
            "folios_moved_out_of_unmapped": applied[
                "folios_moved_out_of_unmapped"
            ],
        }
    )
    return preview
