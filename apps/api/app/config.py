from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# apps/api/app/config.py -> parents[3] == repo root.
# Anchoring to the root keeps `.env` resolution independent of the current
# working directory. If the folder depth changes, update this index.
_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_ROOT / ".env",
        env_file_encoding="utf-8",
        # `.env` carries vars for later phases (STRIPE_*, EMAIL_*, ...) not
        # defined here; ignore them instead of failing validation.
        extra="ignore",
    )

    # --- App --------------------------------------------------------------
    # Defaults mean a missing `.env` does not crash the app (e.g. `/health`).
    environment: str = "local"  # ENVIRONMENT
    api_base_url: str = "http://localhost:8000"  # API_BASE_URL
    web_base_url: str = "http://localhost:3000"  # WEB_BASE_URL

    # --- Auth -------------------------------------------------------------
    # jwt_secret has a dev-only default so imports never crash locally.
    # Production MUST override it with a long random value (never commit it).
    jwt_secret: str = "dev-insecure-change-me"  # JWT_SECRET
    jwt_algorithm: str = "HS256"  # JWT_ALGORITHM
    access_token_ttl: int = 900  # ACCESS_TOKEN_TTL (15 min)
    refresh_token_ttl: int = 604800  # REFRESH_TOKEN_TTL (7 days)

    # --- Postgres ---------------------------------------------------------
    database_url: str = "postgresql+asyncpg://user:pass@localhost:5432/flowly"  # DATABASE_URL

    # --- ClickHouse (connectivity only in Phase 1) ------------------------
    clickhouse_host: str = "localhost"  # CLICKHOUSE_HOST
    clickhouse_user: str = "default"  # CLICKHOUSE_USER
    clickhouse_password: str = ""  # CLICKHOUSE_PASSWORD
    clickhouse_db: str = "flowly"  # CLICKHOUSE_DB

    # --- Redis ------------------------------------------------------------
    redis_url: str = "redis://localhost:6379/0"  # REDIS_URL

    # --- Email ------------------------------------------------------------
    # With no provider configured the email service falls back to a dev stub
    # (logs the code); production must set a real key + verified sender.
    email_api_key: str = ""  # EMAIL_API_KEY
    email_from: str = "Flowly <noreply@flowly.local>"  # EMAIL_FROM

    # --- Social OAuth -----------------------------------------------------
    # A provider is "enabled" only when both its id and secret are set.
    google_client_id: str = ""  # GOOGLE_CLIENT_ID
    google_client_secret: str = ""  # GOOGLE_CLIENT_SECRET
    github_client_id: str = ""  # GITHUB_CLIENT_ID
    github_client_secret: str = ""  # GITHUB_CLIENT_SECRET

    # --- Ingestion (Phase 3) ----------------------------------------------
    # Pepper folded into the cookieless visitor hash. Dev-only default so
    # imports never crash; production MUST override with a long random value.
    visitor_salt_secret: str = "dev-insecure-visitor-salt"  # VISITOR_SALT_SECRET
    # Path to a MaxMind GeoLite2-City .mmdb file. Blank -> geo enrichment
    # fails open (country/region left empty); ingestion never breaks.
    geoip_db_path: str = ""  # GEOIP_DB_PATH
    # Approximate cap for the Redis ingest stream (XADD MAXLEN ~). Sized well
    # above the batch writer's drain rate so healthy operation never trims.
    stream_maxlen: int = 1_000_000  # STREAM_MAXLEN
    # Per-(site_id, IP) ingestion rate limit: a generous abuse backstop.
    collect_rate_limit: int = 600  # COLLECT_RATE_LIMIT (events per window)
    collect_rate_window: int = 60  # COLLECT_RATE_WINDOW (seconds)


settings = Settings()
