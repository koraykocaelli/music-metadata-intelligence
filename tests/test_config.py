from app.core.config import Settings


def test_settings_ignore_docker_compose_variables_in_env_file(tmp_path, monkeypatch) -> None:
    # .env is shared with Docker Compose; its POSTGRES_* / APP_* keys must not
    # break application startup.
    for name in ("DATABASE_URL", "TEST_DATABASE_URL"):
        monkeypatch.delenv(name, raising=False)

    env_file = tmp_path / ".env"
    env_file.write_text(
        "DATABASE_URL=postgresql+psycopg://user:placeholder@localhost:5432/app_db\n"
        "POSTGRES_USER=user\n"
        "POSTGRES_PASSWORD=placeholder\n"
        "POSTGRES_DB=app_db\n"
        "APP_DATABASE_NAME=app_db\n"
        "APP_PORT=8000\n",
        encoding="utf-8",
    )

    settings = Settings(_env_file=env_file)

    assert settings.database_url.endswith("/app_db")
    assert not hasattr(settings, "postgres_password")
