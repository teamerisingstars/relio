from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="RELIO_")

    db_path: str = "relio.db"
    model: str = "claude-opus-4-8"
    recall_limit: int = 5
