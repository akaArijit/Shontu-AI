"""Tests for the API SQL layer using a scripted cursor (no live database)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from fund_engine.db import repository


class ScriptedCursor:
    """Cursor double: each execute() pops the next scripted result."""

    def __init__(self, results):
        self.results = list(results)
        self.calls: list[tuple[str, dict]] = []
        self.rowcount = 0
        self._current = None

    def execute(self, sql, params=None):
        self.calls.append((sql, params))
        self._current = self.results.pop(0) if self.results else None

    def fetchone(self):
        return self._current if isinstance(self._current, dict) else None

    def fetchall(self):
        return self._current if isinstance(self._current, list) else []


def test_fetch_scores_applies_filters_and_pagination():
    cur = ScriptedCursor([[{"scheme_code": "100001"}], {"total": 1}])

    rows, total = repository.fetch_scores(
        cur,
        as_of_date=date(2026, 10, 27),
        scheme_codes=["100001", "100002"],
        category="Large Cap",
        min_score=60,
        limit=25,
        offset=50,
    )

    sql, params = cur.calls[0]
    assert "fs.as_of_date = %(as_of_date)s" in sql
    assert "fs.scheme_code = ANY(%(scheme_codes)s)" in sql
    assert "sm.category = %(category)s" in sql
    assert "fs.fund_health_score >= %(min_score)s" in sql
    assert "ORDER BY fs.fund_health_score DESC NULLS LAST" in sql
    assert params["limit"] == 25
    assert params["offset"] == 50
    assert rows == [{"scheme_code": "100001"}]
    assert total == 1


def test_sort_input_is_whitelisted():
    cur = ScriptedCursor([[], {"total": 0}])

    repository.fetch_scores(
        cur,
        as_of_date=date(2026, 10, 27),
        sort_by="fs.fund_health_score; DROP TABLE fund_scores",
        sort_order="ascending",
    )

    sql, _ = cur.calls[0]
    assert "ORDER BY fs.fund_health_score DESC NULLS LAST" in sql
    assert "DROP" not in sql


def test_latest_score_date_handles_empty_table():
    cur = ScriptedCursor([{"latest": None}])

    assert repository.latest_score_date(cur) is None


def test_fetch_alerts_unresolved_by_default():
    cur = ScriptedCursor([[{"alert_id": "1"}], {"total": 1}])

    rows, total = repository.fetch_alerts(cur, date(2026, 10, 27))

    sql, params = cur.calls[0]
    assert "fa.resolved_on IS NULL" in sql
    assert "CASE fa.severity" in sql
    assert "alert_types" not in params
    assert total == 1
    assert rows[0]["alert_id"] == "1"


def test_fetch_schemes_uses_lateral_latest_features():
    cur = ScriptedCursor([[], {"total": 0}])

    repository.fetch_schemes(cur, date(2026, 10, 27), has_high_alerts=True)

    sql, _ = cur.calls[0]
    assert "LEFT JOIN LATERAL" in sql
    assert "COALESCE(ac.high, 0) > 0" in sql


def test_update_alert_rejects_non_numeric_id_without_query():
    cur = ScriptedCursor([])

    assert repository.update_alert(cur, "not-an-id", True) is False
    assert cur.calls == []


def test_update_alert_merges_resolution_details():
    cur = ScriptedCursor([])
    cur.rowcount = 1

    assert (
        repository.update_alert(cur, "42", False, actor="mfd1", reason="false positive")
        is True
    )

    sql, params = cur.calls[0]
    assert "details = COALESCE" in sql
    assert params["alert_id"] == 42
    assert params["resolved"] is False
    assert (
        params["extra"]
        == '{"handled_by": "mfd1", "resolution_reason": "false positive", "dismissed": true}'
    )


def test_bulk_update_alerts_ignores_bad_ids():
    cur = ScriptedCursor([])
    cur.rowcount = 2

    updated = repository.bulk_update_alerts(cur, ["1", "x", "2"], True)

    assert updated == 2
    _, params = cur.calls[0]
    assert params["alert_ids"] == [1, 2]
    assert params["resolved"] is True


def test_benchmark_history_returns_none_for_unknown_code():
    cur = ScriptedCursor([None])

    assert repository.benchmark_history(cur, "NOPE") is None
    assert len(cur.calls) == 1


def test_benchmark_history_serialises_points():
    cur = ScriptedCursor(
        [
            {"benchmark_name": "Nifty 500 TRI"},
            [{"index_date": date(2026, 1, 1), "index_value": Decimal("123.4567")}],
        ]
    )

    payload = repository.benchmark_history(cur, "NIFTY500_TRI")

    assert payload["benchmark_name"] == "Nifty 500 TRI"
    assert payload["data"] == [{"date": "2026-01-01", "value": 123.4567}]


def test_macro_series_groups_rows_by_indicator():
    cur = ScriptedCursor(
        [
            [
                {
                    "indicator_name": "cpi",
                    "indicator_date": date(2026, 1, 1),
                    "value": Decimal("5.1"),
                }
            ]
        ]
    )

    payload = repository.macro_series(cur, ["cpi", "repo_rate"])

    assert payload["data"]["cpi"] == [{"date": "2026-01-01", "value": 5.1}]
    assert payload["data"]["repo_rate"] == []


def test_pipeline_health_merges_freshness_and_last_run():
    cur = ScriptedCursor(
        [
            {
                "latest_nav_date": date(2026, 10, 26),
                "latest_score_date": date(2026, 10, 27),
                "latest_alert_date": date(2026, 10, 25),
            },
            {
                "status": "completed",
                "as_of_date": date(2026, 10, 27),
                "schemes_processed": 412,
                "alerts_generated": 37,
                "duration_seconds": Decimal("12.5"),
            },
        ]
    )

    payload = repository.pipeline_health(cur)

    assert payload["latest_nav_date"] == date(2026, 10, 26)
    assert payload["last_run_status"] == "completed"
    assert payload["schemes_processed"] == 412
    assert payload["last_run_duration_seconds"] == 12.5


def test_category_rankings_use_requested_metric():
    cur = ScriptedCursor([[]])

    repository.category_rankings(cur, "Large Cap", metric="alpha", limit=10)

    sql, params = cur.calls[0]
    assert "ORDER BY alpha_rank ASC NULLS LAST" in sql
    assert params["category"] == "Large Cap"
    assert params["limit"] == 10


def test_all_category_rankings_limits_each_category():
    rows = [
        {"category": "Flexi Cap", "scheme_code": "1", "score_rank": 1},
        {"category": "Large Cap", "scheme_code": "2", "score_rank": 1},
        {"category": "Large Cap", "scheme_code": "3", "score_rank": 2},
        {"category": "Large Cap", "scheme_code": "4", "score_rank": 3},
    ]
    cur = ScriptedCursor([rows])

    result = repository.all_category_rankings(cur, limit_per_category=2)

    assert [row["scheme_code"] for row in result] == ["1", "2", "3"]


def test_config_snapshots_load_real_yaml():
    scoring = repository.scoring_config()
    rules = repository.rules_config()

    assert isinstance(scoring, dict) and scoring
    assert isinstance(rules, dict) and rules
