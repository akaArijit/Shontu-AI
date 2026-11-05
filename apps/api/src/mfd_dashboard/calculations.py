"""Milestone 2 transaction classification and folio return calculations.

All calculations are pure functions so the rules can be tested without a
database.  Missing dates, amounts and values are never guessed; the result is
``None`` and the caller shows "Not available".
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Iterable, Mapping, Sequence

from mfd_dashboard.ingest.values import clean_text, normalize_header

ONE_RUPEE = Decimal("1.00")
ZERO = Decimal("0")


@dataclass(frozen=True)
class DatedAmount:
    flow_date: date | None
    amount: Decimal | None
    kind: str


@dataclass(frozen=True)
class SignedCashFlow:
    flow_date: date
    amount: Decimal


def _words(text: str) -> list[str]:
    return normalize_header(text).split()


def classify_transaction(
    raw_type: str,
    *,
    description: str = "",
    source_scheme_name: str = "",
    target_scheme_name: str = "",
) -> str:
    """Classify an InvestWell transaction type without guessing.

    Returns one of ``purchase``, ``sip``, ``switch_in``, ``switch_out``,
    ``redemption`` or ``unknown``.
    """

    raw = normalize_header(raw_type)
    combined = normalize_header(f"{raw_type} {description}")
    words = set(_words(combined))

    if not combined:
        return "unknown"

    # Directional switch/STP labels are the only cases where a single row can
    # be classified confidently. A bare "SWITCH" without a leg is ambiguous.
    if "switch" in words or "stp" in words:
        has_in = "in" in words or "inward" in words
        has_out = "out" in words or "outward" in words
        if has_in and not has_out:
            return "switch_in"
        if has_out and not has_in:
            return "switch_out"
        if has_in and has_out:
            return "unknown"
        if target_scheme_name and not source_scheme_name:
            return "switch_in"
        if source_scheme_name and not target_scheme_name:
            return "switch_out"
        return "unknown"

    if any(
        word in words
        for word in (
            "redemption",
            "redeem",
            "redeemed",
            "repurchase",
            "withdrawal",
            "swp",
            "sell",
            "sold",
        )
    ) or "systematic withdrawal" in combined:
        return "redemption"

    if any(
        word in words
        for word in (
            "sip",
            "systematic",
            "installment",
            "instalment",
            "instalments",
            "installments",
        )
    ):
        return "sip"

    if any(
        word in words
        for word in (
            "purchase",
            "subscription",
            "subscribe",
            "fresh",
            "additional",
            "lumpsum",
            "investment",
            "invest",
            "buy",
            "bought",
            "allotment",
        )
    ) or "lump sum" in combined:
        return "purchase"

    return "unknown"


def _float(value: Decimal) -> float:
    return float(value)


def xirr(cash_flows: Sequence[SignedCashFlow]) -> float | None:
    """Return XIRR as a percentage, or ``None`` when it cannot be solved.

    The calculation uses actual/365 day exponents and a Newton step followed by
    a bracketed bisection fallback.  It requires at least one negative and one
    positive cash flow.
    """

    if len(cash_flows) < 2:
        return None
    if not any(item.amount < 0 for item in cash_flows):
        return None
    if not any(item.amount > 0 for item in cash_flows):
        return None

    ordered = sorted(cash_flows, key=lambda item: item.flow_date)
    start = ordered[0].flow_date
    times = [((item.flow_date - start).days / 365.0) for item in ordered]
    if max(times) <= 0:
        return None
    amounts = [_float(item.amount) for item in ordered]

    def npv(rate: float) -> float:
        total = 0.0
        for amount, years in zip(amounts, times):
            try:
                total += amount / ((1.0 + rate) ** years)
            except (OverflowError, ZeroDivisionError):
                return float("nan")
        return total

    def derivative(rate: float) -> float:
        total = 0.0
        for amount, years in zip(amounts, times):
            if years == 0:
                continue
            try:
                total -= years * amount / ((1.0 + rate) ** (years + 1.0))
            except (OverflowError, ZeroDivisionError):
                return float("nan")
        return total

    # Newton-Raphson first.
    rate = 0.1
    for _ in range(120):
        value = npv(rate)
        slope = derivative(rate)
        if value != value or slope != slope or abs(slope) < 1e-14:
            break
        if abs(value) < 1e-9:
            return rate * 100.0
        next_rate = rate - (value / slope)
        if next_rate <= -0.999999 or next_rate > 1_000_000:
            break
        if abs(next_rate - rate) < 1e-12:
            return next_rate * 100.0
        rate = next_rate

    # Bracketed bisection fallback. Search a wide but finite range of rates.
    grid = (-0.9999, -0.9, -0.75, -0.5, -0.25, 0.0, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0, 100.0)
    previous_rate = grid[0]
    previous_value = npv(previous_rate)
    for current_rate in grid[1:]:
        current_value = npv(current_rate)
        if previous_value == previous_value and current_value == current_value:
            if previous_value == 0:
                return previous_rate * 100.0
            if (previous_value < 0 < current_value) or (
                current_value < 0 < previous_value
            ):
                low, high = previous_rate, current_rate
                low_value = previous_value
                for _ in range(200):
                    midpoint = (low + high) / 2.0
                    mid_value = npv(midpoint)
                    if abs(mid_value) < 1e-9:
                        return midpoint * 100.0
                    if (low_value < 0 < mid_value) or (mid_value < 0 < low_value):
                        high = midpoint
                    else:
                        low = midpoint
                        low_value = mid_value
                return ((low + high) / 2.0) * 100.0
        previous_rate = current_rate
        previous_value = current_value
    return None


def _safe_absolute_return(
    current_value: Decimal | None,
    redemption_proceeds: Decimal | None,
    switch_out_proceeds: Decimal | None,
    gross_invested: Decimal | None,
) -> Decimal | None:
    if current_value is None or gross_invested is None or gross_invested <= 0:
        return None
    proceeds = (redemption_proceeds or ZERO) + (switch_out_proceeds or ZERO)
    return ((current_value + proceeds - gross_invested) / gross_invested) * 100


def calculate_folio_metrics(
    transactions: Iterable[DatedAmount],
    *,
    current_value: Decimal | None,
    valuation_date: date | None,
) -> dict:
    """Calculate folio-level invested amounts, return, XIRR and coverage."""

    items = list(transactions)
    valid_dated = [item for item in items if item.flow_date is not None]
    missing_date_count = len(items) - len(valid_dated)
    valid_amounts = [item for item in valid_dated if item.amount is not None]
    missing_amount_count = len(valid_dated) - len(valid_amounts)

    gross_flows = [
        item
        for item in valid_amounts
        if item.kind in {"purchase", "sip", "switch_in"} and item.amount != 0
    ]
    redemption_flows = [
        item
        for item in valid_amounts
        if item.kind == "redemption" and item.amount != 0
    ]
    switch_out_flows = [
        item
        for item in valid_amounts
        if item.kind == "switch_out" and item.amount != 0
    ]
    unknown_flows = [item for item in items if item.kind == "unknown"]

    gross_invested = (
        sum((abs(item.amount or ZERO) for item in gross_flows), ZERO)
        if gross_flows
        else None
    )
    redemption_proceeds = (
        sum((abs(item.amount or ZERO) for item in redemption_flows), ZERO)
        if redemption_flows
        else (ZERO if gross_invested is not None else None)
    )
    switch_out_proceeds = (
        sum((abs(item.amount or ZERO) for item in switch_out_flows), ZERO)
        if switch_out_flows
        else (ZERO if gross_invested is not None else None)
    )
    net_invested = (
        gross_invested - redemption_proceeds - switch_out_proceeds
        if gross_invested is not None
        and redemption_proceeds is not None
        and switch_out_proceeds is not None
        else None
    )

    first_investment_date = (
        min(item.flow_date for item in gross_flows if item.flow_date is not None)
        if gross_flows
        else None
    )
    holding_period = None
    if first_investment_date is not None and valuation_date is not None:
        days = (valuation_date - first_investment_date).days
        holding_period = days if days >= 0 else None

    absolute_return = _safe_absolute_return(
        current_value,
        redemption_proceeds,
        switch_out_proceeds,
        gross_invested,
    )

    returned_cash_flows: list[SignedCashFlow] = []
    for item in valid_amounts:
        if item.flow_date is None or item.amount is None:
            continue
        if item.kind in {"purchase", "sip", "switch_in"}:
            returned_cash_flows.append(
                SignedCashFlow(item.flow_date, -abs(item.amount))
            )
        elif item.kind in {"redemption", "switch_out"}:
            returned_cash_flows.append(
                SignedCashFlow(item.flow_date, abs(item.amount))
            )

    xirr_value = None
    if current_value is not None and valuation_date is not None:
        xirr_value = xirr(
            [*returned_cash_flows, SignedCashFlow(valuation_date, current_value)]
        )

    return {
        "transaction_count": len(items),
        "valid_transaction_count": len(valid_amounts),
        "missing_date_count": missing_date_count,
        "missing_amount_count": missing_amount_count,
        "unknown_count": len(unknown_flows),
        "purchase_count": sum(1 for item in valid_amounts if item.kind == "purchase"),
        "sip_count": sum(1 for item in valid_amounts if item.kind == "sip"),
        "switch_in_count": sum(
            1 for item in valid_amounts if item.kind == "switch_in"
        ),
        "switch_out_count": sum(
            1 for item in valid_amounts if item.kind == "switch_out"
        ),
        "redemption_count": sum(
            1 for item in valid_amounts if item.kind == "redemption"
        ),
        "gross_invested": gross_invested,
        "net_invested": net_invested,
        "redemption_proceeds": redemption_proceeds,
        "switch_out_proceeds": switch_out_proceeds,
        "first_investment_date": first_investment_date,
        "holding_period": holding_period,
        "absolute_return": absolute_return,
        "xirr": xirr_value,
        "cash_flows": returned_cash_flows,
    }


def simulate_benchmark(
    cash_flows: Sequence[SignedCashFlow],
    levels: Mapping[date, Decimal],
    valuation_date: date,
) -> dict:
    """Apply the folio's dated cash flows to a local benchmark level series.

    Returns a status and values.  Any missing level or non-positive level makes
    the comparison unavailable; levels are never interpolated.
    """
    if not cash_flows:
        return {
            "status": "not_available",
            "message": "No dated transaction cash flows are available.",
            "xirr": None,
            "current_value": None,
            "missing_dates": [],
        }

    final_level = levels.get(valuation_date)
    if final_level is None or final_level <= 0:
        return {
            "status": "levels_missing",
            "message": "The benchmark level for the valuation date is missing.",
            "xirr": None,
            "current_value": None,
            "missing_dates": [valuation_date],
        }

    units = ZERO
    missing_dates: set[date] = set()
    for flow in sorted(cash_flows, key=lambda item: item.flow_date):
        level = levels.get(flow.flow_date)
        if level is None or level <= 0:
            missing_dates.add(flow.flow_date)
            continue
        units -= flow.amount / level

    if missing_dates:
        ordered = sorted(missing_dates)
        return {
            "status": "levels_missing",
            "message": (
                f"The benchmark level for {ordered[0].isoformat()} is missing."
                if len(ordered) == 1
                else (
                    f"{len(ordered)} benchmark levels are missing, starting "
                    f"with {ordered[0].isoformat()}."
                )
            ),
            "xirr": None,
            "current_value": None,
            "missing_dates": ordered,
        }

    benchmark_value = units * final_level
    flows = [
        *cash_flows,
        SignedCashFlow(valuation_date, benchmark_value),
    ]
    return {
        "status": "available",
        "message": None,
        "xirr": xirr(flows),
        "current_value": benchmark_value,
        "missing_dates": [],
    }


def point_to_point_return(
    levels: Mapping[date, Decimal],
    start_date: date,
    end_date: date,
) -> dict:
    """Return the benchmark's point-to-point absolute return percentage.

    Both endpoint levels must exist locally.  Gaps are never filled.
    """

    if start_date > end_date:
        return {
            "status": "invalid_period",
            "message": "The first investment date is after the valuation date.",
            "return": None,
            "missing_dates": [],
        }
    start_level = levels.get(start_date)
    end_level = levels.get(end_date)
    missing_dates = []
    if start_level is None or start_level <= 0:
        missing_dates.append(start_date)
    if (end_level is None or end_level <= 0) and end_date not in missing_dates:
        missing_dates.append(end_date)
    if missing_dates:
        ordered = sorted(missing_dates)
        if ordered == [end_date]:
            message = (
                f"The benchmark level for the valuation date "
                f"({end_date.isoformat()}) is missing."
            )
        elif len(ordered) == 1:
            message = (
                f"The benchmark level for {ordered[0].isoformat()} is missing."
            )
        else:
            parts = []
            for item in ordered:
                parts.append(
                    f"the valuation date ({item.isoformat()})"
                    if item == end_date
                    else item.isoformat()
                )
            message = "Benchmark levels are missing for " + " and ".join(parts) + "."
        return {
            "status": "levels_missing",
            "message": message,
            "return": None,
            "missing_dates": ordered,
        }
    return {
        "status": "available",
        "message": None,
        "return": ((end_level / start_level) - 1) * 100,
        "missing_dates": [],
    }

