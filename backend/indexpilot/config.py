from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="INDEXPILOT_", env_file=".env", extra="ignore")

    db_host: str = Field(default="127.0.0.1", min_length=1, max_length=253)
    db_port: int = Field(default=55432, ge=1, le=65535)
    secret_dir: Path = Path(".secrets")
    connect_timeout: int = Field(default=5, ge=1, le=30)
    statement_timeout_ms: int = Field(default=5000, ge=100, le=30000)
    lock_timeout_ms: int = Field(default=1000, ge=100, le=5000)
    frontend_origin: str = "http://localhost:5173"
    analysis_schemas: tuple[str, ...] = ("public",)
    evaluation_timeout_seconds: float = Field(default=30, ge=1, le=120, allow_inf_nan=False)
    statistics_collection_limit: int = Field(default=1000, ge=1, le=5000)

    @field_validator("analysis_schemas")
    @classmethod
    def validate_schemas(cls, values):
        if not 1 <= len(values) <= 16 or len(set(values)) != len(values):
            raise ValueError("Configure between 1 and 16 distinct analysis schemas")
        for value in values:
            if (
                not value
                or len(value.encode("utf-8")) > 63
                or "\x00" in value
                or value.startswith("pg_")
                or value == "information_schema"
            ):
                raise ValueError("Only configured application schemas are supported")
        return values
