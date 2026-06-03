from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    demo_mode: bool = Field(default=False)

    anthropic_api_key: str = Field(default="")
    anthropic_model: str = Field(default="claude-sonnet-4-6")
    database_url: str = Field(default="")

    pipeline_max_sql_retries: int = Field(default=2, ge=0, le=5)
    pipeline_query_timeout_seconds: int = Field(default=15, ge=1, le=120)
    pipeline_max_result_rows: int = Field(default=1000, ge=1, le=100_000)
    pipeline_schema_cache_ttl_seconds: float = Field(default=300.0, ge=0.0, le=3600.0)

    db_pool_size: int = Field(default=10, ge=1, le=200)
    db_max_overflow: int = Field(default=10, ge=0, le=200)
    db_pool_recycle_seconds: int = Field(default=1800, ge=60, le=86_400)
    db_pool_pre_ping: bool = Field(default=True)

    api_rate_limit: str = Field(default="20/minute")

    log_level: str = Field(default="INFO")

    @model_validator(mode="after")
    def _require_credentials_when_not_demo(self) -> "Settings":
        if self.demo_mode:
            return self
        missing = []
        if not self.anthropic_api_key:
            missing.append("ANTHROPIC_API_KEY")
        if not self.database_url:
            missing.append("DATABASE_URL")
        if missing:
            raise ValueError(
                f"Missing required env vars when DEMO_MODE=false: {', '.join(missing)}. "
                "Set them in .env, or set DEMO_MODE=true to use canned demo data."
            )
        return self


def load_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
