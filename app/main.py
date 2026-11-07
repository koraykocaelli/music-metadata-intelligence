from fastapi import FastAPI
from sqlalchemy import text

from app.api.catalog import router as catalog_router
from app.api.tracks import router as tracks_router
from app.api.ui import router as ui_router, static_files
from app.core.config import settings
from app.db.session import engine


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
)

app.include_router(tracks_router)
app.include_router(catalog_router)
app.include_router(ui_router)
app.mount("/static", static_files, name="static")


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