from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    bot_token: str
    masters_chat_id: int
    master_telegram_ids: Annotated[list[int], NoDecode] = Field(default_factory=list)
    admin_telegram_ids: Annotated[list[int], NoDecode] = Field(default_factory=list)

    ai_api_key: str
    ai_base_url: str = "https://api.openai.com/v1"
    ai_text_model: str = "gpt-4o"
    ai_transcribe_model: str = "whisper-1"

    database_url: str
    redis_url: str = "redis://redis:6379/0"
    run_migrations_on_startup: bool = True

    storage_dir: str = "storage"
    storage_backend: str = "local"  # local|s3
    s3_endpoint_url: str | None = None
    s3_access_key_id: str | None = None
    s3_secret_access_key: str | None = None
    s3_bucket: str = "scooter-service-media"
    s3_region: str = "us-east-1"
    s3_public_base_url: str | None = None

    media_group_wait_seconds: float = 2.0
    max_photos_per_ticket: int = 8
    max_voice_size_mb: int = 20
    rate_limit_per_minute: int = 20

    service_timezone: str = "Europe/Bucharest"
    workday_start_hour: int = 10
    workday_end_hour: int = 19
    workday_numbers: Annotated[list[int], NoDecode] = Field(default_factory=lambda: [0, 1, 2, 3, 4, 5])
    slot_duration_minutes: int = 120
    slot_search_days: int = 14
    stale_ticket_minutes: int = 30

    observability_enabled: bool = True
    health_host: str = "0.0.0.0"
    health_port: int = 8080

    retention_auto_send_enabled: bool = True
    retention_check_interval_seconds: int = 60
    retention_batch_size: int = 20

    webapp_base_url: str = "http://localhost:8080"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @field_validator("master_telegram_ids", "admin_telegram_ids", "workday_numbers", mode="before")
    @classmethod
    def parse_int_list(cls, value):
        if value is None or value == "":
            return []
        if isinstance(value, str):
            return [int(item.strip()) for item in value.split(",") if item.strip()]
        return value


settings = Settings()
