from __future__ import annotations

from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="RELIO_")

    db_path: str = "relio.db"
    database_url: Optional[str] = None  # set to use the Postgres+pgvector backend
    provider: str = "claude"  # claude | openai | gemini | fake | none  (RELIO_PROVIDER)
    model: str = "claude-opus-4-8"
    recall_limit: int = 5
