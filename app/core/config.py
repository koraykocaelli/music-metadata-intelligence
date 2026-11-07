from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Music Metadata Intelligence"
    app_version: str = "1.0.0"
    app_env: str = "development"

    database_url: str
    test_database_url: str | None = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        # .env also holds Docker Compose variables (POSTGRES_*, APP_PORT, ...)
        # that the application itself does not use.
        extra="ignore",
    )


settings = Settings()