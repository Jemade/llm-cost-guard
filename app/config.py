from functools import lru_cache
from pathlib import Path
from typing import List, Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    APP_NAME: str = "LLM Cost Guard"
    APP_VERSION: str = "1.0.0"
    APP_ENV: str = "development"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"

    # Database
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/costguard",
        description="Async database connection string. Accepts postgresql+asyncpg or sqlite+aiosqlite.",
    )
    DB_ECHO: bool = False

    # Pricing
    PRICING_FILE_PATH: str = Field(
        default=str(Path(__file__).resolve().parent.parent / "config" / "pricing.yaml"),
        description="Absolute or relative path to pricing configuration YAML.",
    )

    # Budget Defaults
    DEFAULT_DAILY_BUDGET: float = Field(default=5.0, ge=0.0)
    DEFAULT_WEEKLY_BUDGET: float = Field(default=25.0, ge=0.0)
    DEFAULT_MONTHLY_BUDGET: float = Field(default=100.0, ge=0.0)
    DEFAULT_ALERT_THRESHOLDS: List[float] = Field(
        default_factory=lambda: [0.80, 0.90, 1.00]
    )

    # Concurrency & Reservations
    RESERVATION_TTL_SECONDS: int = Field(
        default=60,
        description="Time-to-live in seconds for temporary budget reservations.",
    )

    # Alert Notifications
    ALERT_WEBHOOK_URL: Optional[str] = Field(
        default=None,
        description="Optional HTTP webhook URL for external alert notifications (Slack, Discord, generic webhook).",
    )
    ALERT_WEBHOOK_TIMEOUT_SECONDS: float = 5.0
    ALERT_WEBHOOK_MAX_RETRIES: int = 2


@lru_cache
def get_settings() -> Settings:
    return Settings()
