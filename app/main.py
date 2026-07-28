from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.cache import get_redis, close_redis
from app.config import settings
from app.db import DatabaseClient
from app.deps import get_db_dependency
from app.logging_setup import configure_logging, get_logger
from app.middleware import (
    AuditLogMiddleware,
    HTTPSEnforcementMiddleware,
    InputValidationMiddleware,
    RequestIDMiddleware,
    RequestLoggingMiddleware,
    SecurityHeadersMiddleware,
)
from app.monitoring import start_metrics_server
from app.reel_bot.reel_router import router as reel_bot_router
from app.routes import agent, analytics, auth, content, creator, health, ingest, knowledge, pipeline, session

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
        # `lifespan` (defined below) was never wired in - the DB pool, Redis,
        # metrics server, startup pipeline and schedulers have never run in
        # any environment. This is the actual fix, not a config issue.
        lifespan=lifespan,
    )

    # Configure CORS based on environment
    # Production: require explicit CORS_ORIGINS config
    # Development: allow localhost variants
    cors_origins: list[str] = []
    if settings.environment == "production":
        # Production: use configured origins or default to no cross-origin requests
        cors_origins_str = os.environ.get("CORS_ORIGINS", "")
        if cors_origins_str:
            cors_origins = [origin.strip() for origin in cors_origins_str.split(",")]
        else:
            logger.warning("CORS_ORIGINS not configured in production - cross-origin requests disabled")
    else:
        # Development: allow common localhost variants
        cors_origins = [
            "http://localhost:3000",
            "http://localhost:8000",
            "http://127.0.0.1:3000",
            "http://127.0.0.1:8000",
        ]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True if cors_origins else False,  # Only if origins specified
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization"],
    )
    app.add_middleware(RequestIDMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(InputValidationMiddleware)
    app.add_middleware(AuditLogMiddleware)
    app.add_middleware(HTTPSEnforcementMiddleware)
    app.add_middleware(RequestLoggingMiddleware)

    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(ingest.router)
    app.include_router(session.router)
    app.include_router(analytics.router)
    app.include_router(content.router)
    app.include_router(creator.router)
    app.include_router(knowledge.router)
    app.include_router(agent.router)
    app.include_router(pipeline.router)
    app.include_router(reel_bot_router)

    app.dependency_overrides[get_db_dependency] = get_db

    return app


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    global db_client
    db_client = DatabaseClient(
        settings.database_url,
        min_size=settings.db_pool_min_size,
        max_size=settings.db_pool_max_size,
        max_queries=settings.db_pool_max_queries,
        max_inactive_connection_lifetime=settings.db_pool_max_lifetime,
    )
    await db_client.connect()

    if settings.redis_url:
        redis_client = get_redis()
        if redis_client:
            logger.info("redis_initialized")
        else:
            logger.warning("redis_not_available")

    start_metrics_server()
    logger.info("app_started", environment=settings.environment)

    run_startup_jobs = os.environ.get("RUN_STARTUP_JOBS", "false").lower() == "true"

    if run_startup_jobs:
        try:
            from app.analytics import snapshot_all_metrics

            snap_result = await snapshot_all_metrics(db_client, limit=50)
            logger.info(
                "startup_snapshot_complete",
                snapshots=snap_result["snapshots_created"],
            )
        except Exception as exc:
            logger.warning("startup_snapshot_skipped", error=str(exc))
        try:
            from app.creator_pipeline import run_creator_intelligence_pipeline

            creator_result = await run_creator_intelligence_pipeline(db_client, limit=100)
            logger.info(
                "startup_creator_intelligence_complete",
                reels_analyzed=creator_result.get("reels_analyzed", 0),
            )
        except Exception as exc:
            logger.warning("startup_creator_intelligence_skipped", error=str(exc))
        try:
            from app.pipeline import PipelineStage, run_pipeline

            logger.info("startup_pipeline_started")
            startup_result = await run_pipeline(
                db_client,
                stages=[
                    PipelineStage.ENRICHMENT,
                    PipelineStage.ANALYTICS,
                    PipelineStage.INTELLIGENCE,
                    PipelineStage.KNOWLEDGE,
                    PipelineStage.AGENT,
                    PipelineStage.RETRIEVAL,
                ],
                enrichment_limit=10,
                analytics_limit=50,
                intelligence_limit=50,
                intelligence_use_llm=False,
                knowledge_limit=100,
            )
            logger.info(
                "startup_pipeline_complete",
                status=startup_result.status,
                elapsed_sec=startup_result.elapsed_sec,
                stages=[s.stage.value for s in startup_result.stages],
            )
        except Exception as exc:
            logger.warning("startup_pipeline_skipped", error=str(exc))
    else:
        logger.info("startup_pipelines_disabled", reason="RUN_STARTUP_JOBS not set to true")

    creator_task: asyncio.Task[Any] | None = None
    pipeline_task: asyncio.Task[Any] | None = None
    if settings.schedulers_enabled:
        try:
            from app.scheduler import creator_update_loop, pipeline_update_loop

            creator_task = asyncio.create_task(creator_update_loop(db_client))
            pipeline_task = asyncio.create_task(pipeline_update_loop(db_client))
            logger.info("schedulers_started")
        except Exception as exc:
            logger.warning("schedulers_failed", error=str(exc))
    else:
        logger.info("schedulers_disabled", reason="SCHEDULERS_ENABLED is not set")
    yield
    for task in (creator_task, pipeline_task):
        if task and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
    if db_client:
        await db_client.close()
    await close_redis()
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