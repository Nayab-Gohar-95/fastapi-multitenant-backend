"""
main.py
-------
FastAPI application factory and entry point.

Application lifecycle:
  1. App is created by create_application().
  2. lifespan context manager runs on startup / shutdown.
  3. Routers are registered with their URL prefixes.
  4. Global exception handlers normalise unexpected errors.

Run with:
    uvicorn main:app --reload              # development
    uvicorn main:app --workers 4           # production (no --reload)
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import admin, auth, messages, tenants
from app.core.config import settings
from app.core.logging import configure_logging, get_logger
from app.db.session import engine

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """
    Startup / shutdown lifecycle hook.

    Startup:
      - Configure structured logging
      - (Optionally) verify DB connectivity

    Shutdown:
      - Dispose the async engine (graceful connection pool drain)
    """
    configure_logging()
    logger.info(
        "Starting up",
        app=settings.APP_NAME,
        env=settings.APP_ENV,
        debug=settings.DEBUG,
    )
    yield
    logger.info("Shutting down — disposing DB engine")
    await engine.dispose()


def create_application() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        description=(
            "Multi-tenant LLM SaaS backend with JWT auth, RBAC, "
            "and full tenant data isolation."
        ),
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # ── CORS ─────────────────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Routers ───────────────────────────────────────────────────────────────
    app.include_router(tenants.router)
    app.include_router(auth.router)
    app.include_router(messages.router)
    app.include_router(admin.router)

    # ── Global Exception Handlers ─────────────────────────────────────────────

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        logger.error(
            "Unhandled exception",
            path=request.url.path,
            method=request.method,
            error=str(exc),
            exc_info=True,
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Internal server error"},
        )

    # ── Health Check ──────────────────────────────────────────────────────────

    @app.get("/health", tags=["Health"], summary="Service health check")
    async def health() -> dict:
        return {"status": "ok", "app": settings.APP_NAME, "env": settings.APP_ENV}

    return app


app = create_application()
