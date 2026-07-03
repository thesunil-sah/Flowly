"""Pure query-builder tests — no database.

Builders return `(sql, params)`; these assert the SQL shape and that every
user value rides in `params` (server-side binding), never string-formatted into
the SQL text (the injection guard, CLAUDE.md §9).
"""

from datetime import UTC, datetime

from app.services import stats

FROM = datetime(2026, 7, 1, tzinfo=UTC)
TO = datetime(2026, 7, 8, tzinfo=UTC)


def test_overview_binds_site_id_and_omits_it_from_sql() -> None:
    sql, params = stats.build_overview("secret-site", FROM, TO)
    assert params["site_id"] == "secret-site"
    assert "secret-site" not in sql  # value is bound, not interpolated
    assert "{site_id:String}" in sql
    # Range bounds bound as naive UTC datetimes.
    assert params["from"] == datetime(2026, 7, 1)
    assert params["to"] == datetime(2026, 7, 8)
    assert params["from"].tzinfo is None


def test_sessionized_cte_bakes_timeout_literal() -> None:
    # The 30-min gap is an int constant, safe to inline; it must appear literally.
    assert f"> {stats.SESSION_TIMEOUT_SECONDS}" in stats._SESSIONIZED_CTE
    assert "lagInFrame(ts)" in stats._SESSIONIZED_CTE


def test_timeseries_uses_the_given_bucket_function() -> None:
    sql, _ = stats.build_timeseries("s", FROM, TO, stats._DAY_FN)
    assert "toStartOfDay(ts) AS bucket" in sql
    assert "GROUP BY bucket ORDER BY bucket" in sql


def test_breakdown_binds_column_and_clamps_limit() -> None:
    sql, params = stats.build_breakdown("s", FROM, TO, "country", 999)
    assert "country AS label" in sql
    assert "{limit:UInt32}" in sql
    assert params["limit"] == stats.MAX_LIMIT  # 999 clamped down
    _, low = stats.build_breakdown("s", FROM, TO, "country", 0)
    assert low["limit"] == 1  # 0 clamped up


def test_pages_top_needs_no_session_cte() -> None:
    sql, _ = stats.build_pages("s", FROM, TO, "top", 10)
    assert "sessionized" not in sql
    assert "FROM events" in sql


def test_pages_entry_uses_session_starts() -> None:
    sql, _ = stats.build_pages("s", FROM, TO, "entry", 10)
    assert "sessionized" in sql
    assert "WHERE is_start" in sql


def test_pages_exit_uses_argmax_last_page() -> None:
    sql, _ = stats.build_pages("s", FROM, TO, "exit", 10)
    assert "argMax(path, ts)" in sql
    assert "sessionized" in sql


def test_utm_excludes_untagged_traffic() -> None:
    sql, _ = stats.build_utm("s", FROM, TO, 10)
    assert "utm_source != ''" in sql
