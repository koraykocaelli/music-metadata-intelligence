from fastapi import FastAPI
from sqlalchemy import text

from app.api.tracks import router as tracks_router
from app.core.config import settings
from app.db.session import engine


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
)

app.include_router(tracks_router)


@app.get("/health")
def health_check() -> dict[str, str]:
    return {
        "status": "ok",
        "service": "music-metadata-intelligence",
        "environment": settings.app_env,
    }


@app.get("/health/database")
def database_health_check() -> dict[str, str]:
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))

    return {
        "status": "ok",
        "database": "postgresql",
    }