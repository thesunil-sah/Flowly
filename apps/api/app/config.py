from pathlib import Path

from pydantic import field_validator
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

    @field_validator("web_base_url")
    @classmethod
    def _canonical_origin(cls, value: str) -> str:
        """Canonicalize WEB_BASE_URL to a browser-comparable Origin.

        A browser `Origin` is `scheme://host[:port]` — lowercase, no trailing
        slash. Both surfaces that gate on this value do an exact string compare
        against such an Origin: the CORS middleware (`allow_origins`) and the
        live-socket origin check. Normalizing once here means a stray trailing
        slash or mixed case in the env var can't silently reject every request
        and every WebSocket. Scheme is preserved (http vs https is a real
        setting, not noise).
        """
        return value.strip().lower().rstrip("/")

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
    # Inbox that public contact-form submissions are delivered to. Blank falls
    # back to email_from (self-send). Set a real monitored address in prod.
    contact_email: str = ""  # CONTACT_EMAIL

    # --- Assistant / support chatbot (Phase F7) ---------------------------
    # Anthropic API key for the support chatbot's AI fallback. Blank -> the bot
    # still answers the hardcoded FAQ intents and otherwise points to contact
    # (no API call). A small/cheap model (Haiku) handles unmatched questions.
    anthropic_api_key: str = ""  # ANTHROPIC_API_KEY

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
    # Public URL the tracking snippet loads `script.js` from. Baked into the
    # install snippet shown at onboarding (server owns the URL; the frontend
    # never needs a copy). Prod must point this at the real CDN/host.
    tracker_script_url: str = "http://localhost:8000/script.js"  # TRACKER_SCRIPT_URL
    # Approximate cap for the Redis ingest stream (XADD MAXLEN ~). Sized well
    # above the batch writer's drain rate so healthy operation never trims.
    stream_maxlen: int = 1_000_000  # STREAM_MAXLEN
    # Per-(site_id, IP) ingestion rate limit: a generous abuse backstop.
    collect_rate_limit: int = 600  # COLLECT_RATE_LIMIT (events per window)
    collect_rate_window: int = 60  # COLLECT_RATE_WINDOW (seconds)

    # --- Stripe / Billing (Phase 7) ---------------------------------------
    # Empty defaults so imports never crash locally; billing is inert until a
    # real test/live key is set. Prices are Stripe-dashboard-created product
    # prices referenced by id (we never create products from code).
    stripe_secret_key: str = ""  # STRIPE_SECRET_KEY
    stripe_webhook_secret: str = ""  # STRIPE_WEBHOOK_SECRET
    stripe_price_pro: str = ""  # STRIPE_PRICE_PRO (monthly)
    stripe_price_business: str = ""  # STRIPE_PRICE_BUSINESS (monthly)
    stripe_price_pro_annual: str = ""  # STRIPE_PRICE_PRO_ANNUAL
    stripe_price_business_annual: str = ""  # STRIPE_PRICE_BUSINESS_ANNUAL


# Monthly pageview quota per plan tier. `free` is both the entry tier and the
# lapsed-trial / canceled-subscription fallback (see billing.effective_plan).
# Placeholder values — tune to real pricing before launch.
PLAN_QUOTAS: dict[str, int] = {"free": 10_000, "pro": 100_000, "business": 1_000_000}

# Absolute drop ceiling as a multiple of the plan quota: a runaway/abuse guard,
# NOT a paying-customer experience (a real account never reaches it). Below it
# the soft cap keeps ingesting (§9: never drop a paying customer's data).
HARD_CEILING_MULTIPLE: int = 3

# Per-plan event retention window in days (§9 — "30 days free, 1 year Pro"). The
# retention worker deletes ClickHouse events older than the owner's window. An
# unknown plan falls back to the free (shortest) window — never keep more than
# entitled by mistake.
RETENTION_DAYS: dict[str, int] = {"free": 30, "pro": 365, "business": 730}


settings = Settings()
