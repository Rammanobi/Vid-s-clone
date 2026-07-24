from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.db import DatabaseClient
from app.logging_setup import configure_logging, get_logger
from app.middleware import (
    HTTPSEnforcementMiddleware,
    RequestLoggingMiddleware,
    add_rate_limiting,
)
from app.monitoring import start_metrics_server
from app.routes import auth, health, ingest, session

logger = get_logger(__name__)

db_client: DatabaseClient | None = None


def get_db() -> DatabaseClient | None:
    return db_client


def create_app() -> FastAPI:
    configure_logging()

    app = FastAPI(
        title="Vid's Clone API",
        version="1.0.0",
        docs_url="/docs" if settings.environment != "production" else None,
        redoc_url="/redoc" if settings.environment != "production" else None,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(HTTPSEnforcementMiddleware)
    app.add_middleware(RequestLoggingMiddleware)

    add_rate_limiting(app)

    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(ingest.router)
    app.include_router(session.router)

    app.dependency_overrides[lambda: None] = get_db

    return app


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    global db_client
    db_client = DatabaseClient(settings.database_url)
    await db_client.connect()
    start_metrics_server()
    logger.info("app_started", environment=settings.environment)
    try:
        from app.analytics import snapshot_all_metrics

        snap_result = await snapshot_all_metrics(db_client, limit=50)
        logger.info(
            "startup_snapshot_complete",
            snapshots=snap_result["snapshots_created"],
        )
    except Exception as exc:
        logger.warning("startup_snapshot_skipped", error=str(exc))
    yield
    if db_client:
        await db_client.close()
    logger.info("app_shutdown")


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.environment != "production",
    )