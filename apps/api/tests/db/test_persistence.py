"""Tests for the PostgreSQL writer helpers (no live database required)."""

from __future__ import annotations

import json
from datetime import date

from fund_engine.db import persistence


class RecordingCursor:
    """Minimal cursor double that records SQL and returns scripted rows."""

    def __init__(self, fetchone_results=None):
        self.executed: list[tuple[str, dict]] = []
        self.executed_many: list[tuple[str, list[dict]]] = []
        self.rowcount = 0
        self.next_rowcount = None
        self.rowcounts: list[int] = []
        self._fetchone = list(fetchone_results or [])

    def execute(self, sql, params=None):
        self.executed.append((sql, params))
        if self.rowcounts:
            self.rowcount = self.rowcounts.pop(0)
        elif self.next_rowcount is not None:
            self.rowcount = self.next_rowcount

    def executemany(self, sql, rows):
        self.executed_many.append((sql, list(rows)))
        self.rowcount = len(rows)

    def fetchone(self):
        return self._fetchone.pop(0) if self._fetchone else None

    def fetchall(self):
        return []


def test_upsert_schemes_applies_defaults_and_conflict_clause():
    cur = RecordingCursor()

    written = persistence.upsert_schemes(cur, [{"scheme_code": "100001"}])

    assert written == 1
    sql, rows = cur.executed_many[0]
    assert "ON CONFLICT (scheme_code) DO UPDATE" in sql
    assert rows[0]["amc"] == "Unknown"
    assert rows[0]["category"] == "Unclassified"
    assert rows[0]["is_active"] is True


def test_upsert_rolling_returns_maps_every_column():
    cur = RecordingCursor()

    persistence.upsert_rolling_returns(
        cur,
        [
            {
                "scheme_code": "100001",
                "as_of_date": "2026-10-27",
                "return_1y": 0.12,
                "category_rank_1y": 4,
            }
        ],
    )

    sql, rows = cur.executed_many[0]
    assert rows[0]["return_1y"] == 0.12
    assert rows[0]["category_rank_1y"] == 4
    assert rows[0]["alpha_1y"] is None
    assert "ON CONFLICT (scheme_code, as_of_date)" in sql
    for column in persistence.ROLLING_RETURN_COLUMNS:
        assert column in rows[0]


def test_upsert_fund_scores_serialises_breakdown():
    cur = RecordingCursor()

    persistence.upsert_fund_scores(
        cur,
        [
            {
                "scheme_code": "100001",
                "as_of_date": "2026-10-27",
                "fund_health_score": 72,
                "category_rank": 3,
                "category_percentile": 88.5,
                "breakdown": [
                    {
                        "component": "1Y Return",
                        "points": 22.0,
                        "max_points": 25,
                        "reason": "Top quartile",
                        "raw_value": 0.18,
                    }
                ],
                "penalty": 0.0,
                "scoring_config_version": "1.0",
            }
        ],
    )

    _, rows = cur.executed_many[0]
    payload = json.loads(rows[0]["score_breakdown"])
    assert payload[0]["component"] == "1Y Return"
    assert rows[0]["fund_health_score"] == 72


def test_sync_alerts_inserts_new_alerts_and_resolves_stale():
    cur = RecordingCursor()
    cur.rowcounts = [0, 4]  # no open alert -> insert; 4 stale alerts resolved

    result = persistence.sync_alerts(
        cur,
        [
            {
                "scheme_code": "100001",
                "alert_type": "underperform_3m",
                "severity": "high",
                "triggered_on": date(2026, 10, 27),
                "details": {"rule_id": "R1"},
            }
        ],
        date(2026, 10, 27),
    )

    assert result == {"inserted": 1, "updated": 0, "resolved": 4}
    assert "UPDATE fund_alerts" in cur.executed[0][0]
    assert "INSERT INTO fund_alerts" in cur.executed[1][0]
    assert json.loads(cur.executed[1][1]["details"]) == {"rule_id": "R1"}
    assert cur.executed[2][1]["as_of_date"] == date(2026, 10, 27)
    assert cur.executed[2][1]["active_keys"] == ["100001::underperform_3m"]


def test_sync_alerts_keeps_original_trigger_date_for_open_alerts():
    cur = RecordingCursor()
    cur.rowcounts = [1, 0]  # one open alert updated; nothing stale

    result = persistence.sync_alerts(
        cur,
        [
            {
                "scheme_code": "100001",
                "alert_type": "underperform_3m",
                "severity": "medium",
                "triggered_on": date(2026, 10, 27),
                "details": {},
            }
        ],
        date(2026, 10, 27),
    )

    assert result == {"inserted": 0, "updated": 1, "resolved": 0}
    update_sql = cur.executed[0][0]
    assert "LEAST(triggered_on" in update_sql
    assert len(cur.executed) == 2  # update + resolve sweep, no insert


def test_sync_alerts_without_alerts_resolves_all_stale():
    cur = RecordingCursor()
    cur.rowcounts = [3]

    result = persistence.sync_alerts(cur, [], date(2026, 10, 27))

    assert result == {"inserted": 0, "updated": 0, "resolved": 3}
    assert len(cur.executed) == 1
    assert cur.executed[0][1]["active_keys"] == []
    assert "::text[]" in cur.executed[0][0]


def test_large_payloads_are_chunked():
    cur = RecordingCursor()
    records = [
        {
            "scheme_code": "100001",
            "nav_date": date(2026, 1, 1),
            "nav_value": 10 + index,
        }
        for index in range(1201)
    ]

    written = persistence.upsert_nav_history(cur, records)

    assert written == 1201
    assert [len(rows) for _, rows in cur.executed_many] == [500, 500, 201]


def test_pipeline_run_log_lifecycle():
    cur = RecordingCursor(fetchone_results=[{"run_id": "run-1"}])

    run_id = persistence.start_pipeline_run(cur, date(2026, 10, 27))
    assert run_id == "run-1"
    assert "INSERT INTO pipeline_run_log" in cur.executed[0][0]
    assert cur.executed[0][1]["as_of_date"] == date(2026, 10, 27)

    persistence.finish_pipeline_run(
        cur,
        run_id=run_id,
        status="partial",
        schemes_processed=3,
        folios_processed=7,
        alerts_generated=2,
        scores_computed=3,
        error_message="one scheme failed",
        metadata={"ingestion_errors": 1},
    )

    sql, params = cur.executed[-1]
    assert "UPDATE pipeline_run_log" in sql
    assert params["status"] == "partial"
    assert params["scores_computed"] == 3
    assert json.loads(params["metadata"]) == {"ingestion_errors": 1}
