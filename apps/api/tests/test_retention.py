"""Per-plan retention — cutoff math, delete builder, worker scoping (§9)."""

from datetime import UTC, datetime, timedelta
from typing import Any

from app.models.tables import Account, Site
from app.services import retention
from app.workers import retention as retention_worker

NOW = datetime(2026, 7, 4, 12, 0, tzinfo=UTC)


def test_retention_days_per_plan() -> None:
    assert retention.retention_days("free") == 30
    assert retention.retention_days("pro") == 365
    assert retention.retention_days("business") == 730
    assert retention.retention_days("mystery") == 30  # unknown -> free window


def test_cutoff_for_subtracts_window() -> None:
    assert retention.cutoff_for("free", NOW) == NOW - timedelta(days=30)
    assert retention.cutoff_for("pro", NOW) == NOW - timedelta(days=365)


def test_build_delete_query_is_site_scoped_and_parameterized() -> None:
    sql, params = retention.build_delete_query("pub0", NOW - timedelta(days=30))
    assert "site_id = {site_id:String}" in sql
    assert "ts < {cutoff:DateTime}" in sql
    assert params["site_id"] == "pub0"
    # tz-aware UTC: a naive param would be parsed in the ClickHouse *server*
    # timezone, shifting the cutoff (see services/stats.py::_range_params).
    assert params["cutoff"] == NOW - timedelta(days=30)
    assert params["cutoff"].utcoffset().total_seconds() == 0


class MockCH:
    def __init__(self) -> None:
        self.commands: list[tuple[str, dict[str, Any] | None]] = []

    async def command(self, sql: str, parameters: dict[str, Any] | None = None) -> None:
        self.commands.append((sql, parameters))


async def test_worker_deletes_per_site_with_plan_specific_cutoff(
    session_factory, monkeypatch
) -> None:
    async with session_factory() as s:
        free = Account(email="f@e.com", username="f", plan="free", status="active")
        pro = Account(email="p@e.com", username="p", plan="pro", status="active")
        s.add_all([free, pro])
        await s.flush()
        s.add(Site(account_id=free.id, site_id="free-site", domain="f.com"))
        s.add(Site(account_id=pro.id, site_id="pro-site", domain="p.com"))
        await s.commit()

    ch = MockCH()

    async def fake_ch():
        return ch

    monkeypatch.setattr(retention_worker, "get_clickhouse", fake_ch)
    monkeypatch.setattr(retention_worker, "async_session_factory", session_factory)

    processed = await retention_worker.run(NOW)
    assert processed == 2
    by_site = {params["site_id"]: params["cutoff"] for _sql, params in ch.commands}
    # Each site got its own cutoff, derived from its owner's plan.
    assert by_site["free-site"] == NOW - timedelta(days=30)
    assert by_site["pro-site"] == NOW - timedelta(days=365)


async def test_worker_uses_free_window_for_lapsed_trial(session_factory, monkeypatch) -> None:
    # plan="pro" but the trial has ended with no active sub -> effectively free.
    async with session_factory() as s:
        acc = Account(
            email="l@e.com",
            username="l",
            plan="pro",
            status="trialing",
            trial_ends_at=NOW - timedelta(days=1),
        )
        s.add(acc)
        await s.flush()
        s.add(Site(account_id=acc.id, site_id="lapsed", domain="l.com"))
        await s.commit()

    ch = MockCH()

    async def fake_ch():
        return ch

    monkeypatch.setattr(retention_worker, "get_clickhouse", fake_ch)
    monkeypatch.setattr(retention_worker, "async_session_factory", session_factory)

    await retention_worker.run(NOW)
    _sql, params = ch.commands[0]
    assert params["cutoff"] == NOW - timedelta(days=30)
