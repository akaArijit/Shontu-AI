"""Shared value cleanup and parsing helpers.

The helpers deliberately return ``None`` for blank or malformed numeric values
instead of guessing.  Codes are always handled as text; no PAN or contact field
is ever parsed or stored.
"""

from __future__ import annotations

import math
import re
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation


_SPACE_RE = re.compile(r"\s+")
_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")
_WHOLE_NUMBER_FLOAT_RE = re.compile(r"^-?\d+\.0+$")
_MISSING_MARKERS = {
    "-",
    "--",
    "na",
    "n/a",
    "nil",
    "none",
    "not available",
    "notapplicable",
    "null",
}


def clean_text(value: object | None) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and math.isnan(value):
        return ""
    return _SPACE_RE.sub(" ", str(value).replace("\ufeff", " ")).strip()


def clean_code(value: object | None) -> str:
    """Preserve a code as text, trim it, and remove a leading apostrophe."""

    text = clean_text(value)
    text = text.lstrip("'’`").strip()
    if _WHOLE_NUMBER_FLOAT_RE.fullmatch(text):
        text = text.split(".", 1)[0]
    return text


def normalize_code(value: object | None) -> str:
    """Normalised key for matching codes.  The stored value remains text."""

    text = clean_code(value).casefold()
    return _SPACE_RE.sub("", text)


def normalize_header(value: object | None) -> str:
    text = clean_text(value).casefold()
    text = _NON_ALNUM_RE.sub(" ", text)
    return _SPACE_RE.sub(" ", text).strip()


def key_for_name(value: str | None) -> str:
    return normalize_header(value)


def normalize_folio(value: object | None) -> str:
    return re.sub(r"[^a-z0-9]+", "", clean_code(value).casefold())


def is_sensitive_header(value: str) -> bool:
    normalized = normalize_header(value)
    tokens = set(normalized.split())
    exact = {
        "pan",
        "pan no",
        "pan number",
        "permanent account number",
        "aadhaar",
        "aadhar",
        "aadhaar no",
        "aadhaar number",
        "email",
        "email id",
        "email address",
        "mobile",
        "mobile no",
        "mobile number",
        "phone",
        "phone no",
        "phone number",
        "contact",
        "contact no",
        "contact number",
        "address",
        "residential address",
        "correspondence address",
        "bank",
        "bank account",
        "bank account no",
        "bank account number",
        "ifsc",
        "micr",
        "kyc",
        "kyc status",
        "nominee",
        "nominee name",
        "guardian",
        "guardian name",
        "joint holder",
        "joint holder name",
        "date of birth",
        "dob",
        "gender",
        "occupation",
        "nationality",
        "signature",
        "photo",
        "passport",
        "driving licence",
        "driving license",
        "voter id",
    }
    if normalized in exact or "pan" in tokens:
        return True
    sensitive_fragments = (
        "aadhaar",
        "aadhar",
        "email",
        "mobile",
        "phone",
        "contact",
        "address",
        "bank",
        "kyc",
        "nominee",
        "guardian",
        "joint holder",
    )
    return any(fragment in normalized for fragment in sensitive_fragments)


def parse_decimal(value: object | None) -> Decimal | None:
    """Parse Indian-formatted money/unit strings without guessing.

    Handles ``1,23,456.78``, ``Rs. 1,000``, ``₹1,000``, percentages, and
    accounting parentheses such as ``(1,000)``.  Blank, ``N/A`` and malformed
    values return ``None``.
    """

    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float, Decimal)):
        try:
            number = Decimal(str(value))
        except InvalidOperation:
            return None
        if not number.is_finite():
            return None
        return number

    text = clean_text(value)
    if not text or text.casefold().replace(" ", "") in _MISSING_MARKERS:
        return None

    negative = text.startswith("(") and text.endswith(")")
    if negative:
        text = text[1:-1]

    for token in ("₹", "Rs.", "Rs", "INR", ",", " ", "\u00a0"):
        text = text.replace(token, "")

    if text.endswith("%"):
        text = text[:-1]

    try:
        number = Decimal(text)
    except InvalidOperation:
        return None

    if not number.is_finite():
        return None
    return -number if negative else number


def parse_date_value(
    value: object | None,
    formats: list[str],
) -> tuple[date | None, str | None, str]:
    """Return ``(parsed_date, format_used, status)``.

    Status is ``ok``, ``missing``, ``invalid``, or ``ambiguous``.
    """

    if isinstance(value, datetime):
        return value.date(), "datetime", "ok"
    if isinstance(value, date):
        return value, "date", "ok"

    text = clean_text(value)
    if not text:
        return None, None, "missing"

    if re.fullmatch(r"\d{5}(?:\.\d+)?", text):
        try:
            serial = float(text)
            parsed = (datetime(1899, 12, 30) + timedelta(days=serial)).date()
            return parsed, "excel_serial", "ok"
        except (ValueError, OverflowError):
            pass

    candidates: list[tuple[date, str]] = []
    for fmt in formats:
        try:
            candidates.append((datetime.strptime(text, fmt).date(), fmt))
        except ValueError:
            continue

    if not candidates:
        try:
            return datetime.fromisoformat(text).date(), "iso", "ok"
        except ValueError:
            return None, None, "invalid"

    distinct = {candidate[0] for candidate in candidates}
    if len(distinct) > 1:
        return None, None, "ambiguous"

    return candidates[0][0], candidates[0][1], "ok"
