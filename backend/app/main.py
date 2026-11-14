"""Spider FastAPI application entrypoint."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api.routes import (
    admin_webhooks,
    analytics,
    audit,
    auth,
    exports,
    github,
    health,
    pull_requests,
    repositories,
    reviews,
    settings,
    webhooks,
)
from app.core.config import settings as app_settings
from app.core.logging import get_logger, setup_logging

setup_logging()
logger = get_logger(__name__)

if app_settings.sentry_dsn:
    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.celery import CeleryIntegration

        sentry_sdk.init(
            dsn=app_settings.sentry_dsn,
            integrations=[FastApiIntegration(), CeleryIntegration()],
            traces_sample_rate=0.1,
            environment=app_settings.app_env,
        )
        logger.info("sentry_initialized")
    except Exception as exc:
        logger.warning("sentry_init_failed", error=str(exc))


@asynccontextmanager
async def lifespan(_app: FastAPI):
    logger.info(
        "startup",
        app=app_settings.app_name,
        version=__version__,
        env=app_settings.app_env,
        github_configured=app_settings.github_app_configured,
        gemini_configured=app_settings.gemini_configured,
    )
    yield
    logger.info("shutdown")


app = FastAPI(
    title=app_settings.app_name,
    version=__version__,
    description="AI-powered GitHub code review platform",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=app_settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

API_PREFIX = "/api"

app.include_router(health.router, prefix=API_PREFIX)
app.include_router(auth.router, prefix=API_PREFIX)
app.include_router(analytics.router, prefix=API_PREFIX)
app.include_router(github.router, prefix=API_PREFIX)
app.include_router(repositories.router, prefix=API_PREFIX)
app.include_router(pull_requests.router, prefix=API_PREFIX)
app.include_router(reviews.router, prefix=API_PREFIX)
app.include_router(settings.router, prefix=API_PREFIX)
app.include_router(webhooks.router, prefix=API_PREFIX)
app.include_router(exports.router, prefix=API_PREFIX)
app.include_router(audit.router, prefix=API_PREFIX)
app.include_router(admin_webhooks.router, prefix=API_PREFIX)


@app.get("/")
async def root() -> dict[str, str]:
    return {
        "app": app_settings.app_name,
        "version": __version__,
        "docs": "/docs",
        "health": "/api/health",
    }
