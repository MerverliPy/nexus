"""FastAPI application entry point."""

from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from nexus.api.routers import audit, auth, finance, research, tasks, ws
from nexus.config import get_settings
from nexus.database import Base, engine
from nexus.utils.metrics import PrometheusMiddleware, metrics_endpoint

settings = get_settings()
logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown events."""
    logger.info("nexus_startup", env=settings.nexus_env)
    if settings.nexus_env == "development":
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    yield
    logger.info("nexus_shutdown")
    await engine.dispose()


app = FastAPI(
    title="Nexus Personal AI System",
    description="Autonomous intelligence platform for tasks, finance, and research",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.nexus_debug else None,
    redoc_url="/redoc" if settings.nexus_debug else None,
)

# Prometheus metrics middleware (first, to capture all requests)
app.add_middleware(PrometheusMiddleware)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    return {"service": "Nexus Personal AI System", "version": "0.1.0", "status": "operational"}


@app.get("/health")
async def health_check():
    # TODO: Add database connectivity check
    return {"status": "healthy", "env": settings.nexus_env}


@app.get("/metrics")
async def metrics(request: Request):
    """Prometheus scrape endpoint."""
    return await metrics_endpoint(request)


app.include_router(auth.router)
app.include_router(finance.router)
app.include_router(tasks.router)
app.include_router(audit.router)
app.include_router(research.router)
app.include_router(ws.router)
