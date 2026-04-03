from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = Field(default="Proyecto Transporte Webhooks")
    app_env: str = Field(default="development")
    thingspeak_base_url: str = Field(default="https://api.thingspeak.com")
    thingspeak_channel_id: str | None = Field(default=None)
    thingspeak_read_api_key: str | None = Field(default=None)
    thingspeak_field1_url: str | None = Field(default=None)
    thingspeak_timeout: int = Field(default=10)
    thingspeak_poll_enabled: bool = Field(default=False)
    thingspeak_poll_seconds: int = Field(default=8)
    firebase_credentials_path: str | None = Field(default="caminesproyecto.json")
    firebase_collection: str = Field(default="sensor_readings")
    firebase_realtime_db_url: str | None = Field(default=None)
    session_secret: str = Field(default="sync-truck-secret-key")
    frontend_origin: str = Field(default="http://localhost:5173")

    model_config = SettingsConfigDict(
        env_file=(".env", ".env.example"),  
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


settings = Settings()
