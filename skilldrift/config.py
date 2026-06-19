from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    environment: str = "development"
    log_level: str = "INFO"

    database_url: str | None = None
    jobs_db_path: Path = Path("data/jobs.db")
    trends_db_path: Path = Path("data/trends.db")

    remoteok_url: str = "https://remoteok.com/api"
    remoteok_user_agent: str = "SkillDrift/1.0"

    solr_url: str = "http://localhost:8983/solr/jobs_core"
    solr_timeout_seconds: float = 10.0
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    s3_bucket: str = "skilldrift-output"
    aws_endpoint_url: str | None = "http://localhost:4566"
    aws_region: str = "us-east-1"

    @property
    def allowed_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def normalized_database_url(self) -> str | None:
        if not self.database_url:
            return None
        if self.database_url.startswith("postgresql://"):
            return self.database_url.replace("postgresql://", "postgresql+psycopg://", 1)
        if self.database_url.startswith("postgres://"):
            return self.database_url.replace("postgres://", "postgresql+psycopg://", 1)
        return self.database_url

    def ensure_local_directories(self) -> None:
        if not self.database_url:
            self.jobs_db_path.parent.mkdir(parents=True, exist_ok=True)
            self.trends_db_path.parent.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_local_directories()
    return settings
