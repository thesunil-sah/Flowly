"""Geo-IP enrichment (Phase 11 adds city).

`lookup` must stay fail-open (no DB / bad IP → empty strings) and now returns a
third element, the city. A fake reader stands in for the MaxMind .mmdb.
"""

from app.services import geo


class _FakeCity:
    def __init__(self, country: str, region: str, city: str) -> None:
        self.country = type("C", (), {"iso_code": country})()
        sub = type("S", (), {"name": region})()
        self.subdivisions = type("Subs", (), {"most_specific": sub})()
        self.city = type("City", (), {"name": city})()


class _FakeReader:
    def __init__(self, resp: _FakeCity) -> None:
        self._resp = resp

    def city(self, ip: str) -> _FakeCity:
        return self._resp


def test_lookup_fails_open_without_a_database(monkeypatch) -> None:
    monkeypatch.setattr(geo, "_get_reader", lambda: None)
    assert geo.lookup("1.2.3.4") == ("", "", "")


def test_lookup_returns_country_region_city(monkeypatch) -> None:
    reader = _FakeReader(_FakeCity("FR", "Île-de-France", "Paris"))
    monkeypatch.setattr(geo, "_get_reader", lambda: reader)
    assert geo.lookup("1.2.3.4") == ("FR", "Île-de-France", "Paris")


def test_lookup_empty_ip_is_empty(monkeypatch) -> None:
    reader = _FakeReader(_FakeCity("FR", "", "Paris"))
    monkeypatch.setattr(geo, "_get_reader", lambda: reader)
    assert geo.lookup("") == ("", "", "")
