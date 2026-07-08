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
    # Range bounds MUST bind tz-aware UTC: a naive param is parsed in the
    # ClickHouse *server* timezone, shifting every window by the server's UTC
    # offset (regression: the newest hour of events vanished on a BST server).
    assert params["from"] == FROM
    assert params["to"] == TO
    assert params["from"].tzinfo is not None
    assert params["to"].utcoffset().total_seconds() == 0


def test_sessionized_cte_bakes_timeout_literal() -> None:
    # The 30-min gap is an int constant, safe to inline; it must appear literally.
    cte = stats._sessionized_cte()
    assert f"> {stats.SESSION_TIMEOUT_SECONDS}" in cte
    assert "lagInFrame(ts)" in cte


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


# --- Phase 10: filters, channels, screens, heatmap, engagement -------------
def test_filter_value_is_bound_never_interpolated() -> None:
    # The §9 contract for the new dashboard filters: a filter VALUE must ride in
    # params under a namespaced key, never be string-formatted into the SQL text.
    sql, params = stats.build_overview("s", FROM, TO, {"country": "US'; DROP"})
    assert "{f_country:String}" in sql
    assert params["f_country"] == "US'; DROP"
    assert "US'; DROP" not in sql
    assert "DROP" not in sql


def test_filter_applies_inside_session_cte() -> None:
    # Sessions/bounce/entry/exit must honor filters too, so the clause has to land
    # inside the sessionization CTE's WHERE, not only the outer query.
    sql, _ = stats.build_pages("s", FROM, TO, "entry", 10, {"device": "mobile"})
    assert sql.count("{f_device:String}") >= 1
    # It appears within the _in_range predicate (the CTE), before `sessionized`.
    assert sql.index("{f_device:String}") < sql.index("WHERE is_start")


def test_multiple_filters_stack_with_namespaced_params() -> None:
    sql, params = stats.build_breakdown("s", FROM, TO, "source", 10, {"country": "US", "os": "iOS"})
    assert "{f_country:String}" in sql and "{f_os:String}" in sql
    assert params["f_country"] == "US" and params["f_os"] == "iOS"


def test_unknown_filter_key_rejected() -> None:
    import pytest

    from app.core.exceptions import ValidationError

    with pytest.raises(ValidationError):
        stats.build_overview("s", FROM, TO, {"evil": "x"})


def test_screen_bucket_boundaries() -> None:
    _, _ = stats.build_breakdown("s", FROM, TO, stats._SCREEN_BUCKET_SQL, 10)
    expr = stats._SCREEN_BUCKET_SQL
    # The bucket edges the audience report advertises.
    assert "screen_w = 0, 'Unknown'" in expr
    assert "screen_w <= 640, 'Mobile'" in expr
    assert "screen_w <= 1024, 'Tablet'" in expr
    assert "screen_w <= 1440, 'Laptop'" in expr
    assert "'Desktop'" in expr


# --- custom events + goals (Phase 15) ------------------------------------
def test_events_builder_scopes_to_custom_and_clamps_limit() -> None:
    sql, params = stats.build_events("s", FROM, TO, 999)
    assert "event_type = 'custom'" in sql
    assert "name != ''" in sql
    assert params["limit"] == stats.MAX_LIMIT  # 999 clamped down


def test_goal_conversion_target_is_bound_never_interpolated() -> None:
    # §9: the goal target is a server-side param, never string-formatted in.
    sql, params = stats.build_goal_conversions("s", FROM, TO, "custom", "sign'up; DROP")
    assert "{goal_target:String}" in sql
    assert params["goal_target"] == "sign'up; DROP"
    assert "DROP" not in sql
    # Conversions vs total visitors, both distinct-visitor counts.
    assert "uniqExactIf(visitor_hash" in sql
    assert "uniqExact(visitor_hash)" in sql


def test_goal_conversion_pageview_matches_path() -> None:
    sql, _ = stats.build_goal_conversions("s", FROM, TO, "pageview", "/thanks")
    assert "event_type = 'pageview' AND path = {goal_target:String}" in sql


def test_goal_conversion_unknown_kind_rejected() -> None:
    import pytest

    from app.core.exceptions import ValidationError

    with pytest.raises(ValidationError):
        stats.build_goal_conversions("s", FROM, TO, "evil", "x")


def test_channels_multiif_orders_ai_before_search() -> None:
    sql, _ = stats.build_channels("s", FROM, TO)
    assert "'direct'" in sql and "'referral'" in sql
    # AI must be matched before search (gemini.google.com vs the google. marker).
    assert sql.index("'ai'") < sql.index("'search'") < sql.index("'social'")


def test_channel_referrers_rejects_non_drilldown_channel() -> None:
    import pytest

    from app.core.exceptions import ValidationError

    # direct/referral have no per-host drill-down.
    with pytest.raises(ValidationError):
        stats.build_channel_referrers("s", FROM, TO, "direct", 10)
    sql, _ = stats.build_channel_referrers("s", FROM, TO, "ai", 10)
    assert "domainWithoutWWW(referrer)" in sql


def test_heatmap_binds_timezone_param() -> None:
    sql, params = stats.build_heatmap("s", FROM, TO, "Asia/Kolkata")
    assert "toHour(ts, {tz:String})" in sql
    # toDayOfWeek's tz is its THIRD arg (2nd is week_mode); getting this wrong is
    # a ClickHouse type error caught only by a live query, so pin the exact form.
    assert "toDayOfWeek(ts, 0, {tz:String})" in sql
    assert params["tz"] == "Asia/Kolkata"


def test_engagement_sort_uses_lead_frame_and_bounce() -> None:
    sql, _ = stats.build_pages("s", FROM, TO, "top", 10, sort="engagement")
    assert "leadInFrame(ts)" in sql
    assert "bounce_rate" in sql
    assert "avg_duration" in sql
    assert "ORDER BY avg_duration DESC" in sql
