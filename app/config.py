"""
N.E.S.T – Application configuration.
Reads environment variables from a .env file via pydantic-settings.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central configuration loaded from environment / .env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # ── App ──
    APP_NAME: str = "N.E.S.T"
    DEBUG: bool = True

    # ── Database ──
    DATABASE_URL: str = "sqlite+aiosqlite:///./smartcampus.db"

    # ── JWT ──
    SECRET_KEY: str = "change-me-to-a-random-secret"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # ── OAuth — Google ──
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""

    # ── OAuth — GitHub ──
    GITHUB_CLIENT_ID: str = ""
    GITHUB_CLIENT_SECRET: str = ""

    # ── GitHub Repo Creation ──
    GITHUB_TOKEN: str = ""
    GITHUB_ORG: str = ""

    # ── Notifications (SMTP) ──
    SMTP_SERVER: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""

settings = Settings()
