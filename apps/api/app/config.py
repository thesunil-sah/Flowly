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
        # `.env` carries vars for later phases (JWT_*, STRIPE_*, ...) not defined
        # here; ignore them instead of failing validation.
        extra="ignore",
    )

    # Defaults mean a missing `.env` does not crash the app.
    environment: str = "local"  # ENVIRONMENT
    api_base_url: str = "http://localhost:8000"  # API_BASE_URL
    web_base_url: str = "http://localhost:3000"  # WEB_BASE_URL


settings = Settings()
