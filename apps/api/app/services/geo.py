"""Geo-IP enrichment via MaxMind GeoLite2 (fail-open).

`lookup(ip)` maps a client IP to ``(country, region, city)`` for the audience
reports. It runs on the ingest hot path, so the reader (a memory-mapped .mmdb) is
opened once and reused; individual lookups are microsecond-scale.

Everything fails open: if `GEOIP_DB_PATH` is unset/unreadable, or the IP isn't
in the database, or the lookup raises, we return ``("", "", "")``. Ingestion must
never break because geo is unavailable (CLAUDE.md — "ingestion must never
throw"). The raw IP is used only here and never logged.
"""

from geoip2.database import Reader
from geoip2.errors import AddressNotFoundError

from app.config import settings

_reader: Reader | None = None
# Guards against re-attempting to open a missing/broken file on every request.
_load_attempted = False


def _get_reader() -> Reader | None:
    """Open the GeoLite2 reader once; return None if unavailable (fail-open)."""
    global _reader, _load_attempted
    if _load_attempted:
        return _reader
    _load_attempted = True
    path = settings.geoip_db_path
    if not path:
        return None
    try:
        _reader = Reader(path)
    except (OSError, ValueError):
        # Missing file or invalid database — run without geo, don't crash.
        _reader = None
    return _reader


def lookup(ip: str) -> tuple[str, str, str]:
    """Return ``(country_iso, region, city)`` for ``ip``; ``("", "", "")`` on any failure."""
    reader = _get_reader()
    if reader is None or not ip:
        return ("", "", "")
    try:
        resp = reader.city(ip)
    except (AddressNotFoundError, ValueError):
        # Not in the DB, or not a routable/valid address.
        return ("", "", "")
    except Exception:
        # Belt-and-braces: geo must never break ingestion.
        return ("", "", "")
    country = resp.country.iso_code or ""
    # `subdivisions.most_specific` is the finest region (state/province).
    region = resp.subdivisions.most_specific.name or ""
    city = resp.city.name or ""
    return (country, region, city)


def reset_reader_cache() -> None:
    """Test hook: drop the cached reader so a monkeypatched path is re-read."""
    global _reader, _load_attempted
    _reader = None
    _load_attempted = False
