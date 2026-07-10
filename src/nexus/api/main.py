"""FastAPI application entry point."""

from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from nexus.config import get_settings
from nexus.database import Base, engine

settings = get_settings()
logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown events."""
    # Startup
    logger.info("nexus_startup", env=settings.nexus_env)

    # Create database tables (in production, use Alembic migrations instead)
    if settings.nexus_env == "development":
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    yield

    # Shutdown
    logger.info("nexus_shutdown")
    await engine.dispose()


# Create FastAPI app
app = FastAPI(
    title="Nexus Personal AI System",
    description="Autonomous intelligence platform for tasks, finance, and research",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.nexus_debug else None,
    redoc_url="/redoc" if settings.nexus_debug else None,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],  # Next.js dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """Root endpoint."""
    return {"service": "Nexus Personal AI System", "version": "0.1.0", "status": "operational"}


@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring."""
    # TODO: Add database connectivity check
    return {"status": "healthy", "env": settings.nexus_env}


# Import and include routers
# from nexus.api.routers import auth, tasks, finance, research, automations
# app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
# app.include_router(tasks.router, prefix="/api/v1/tasks", tags=["tasks"])
# app.include_router(finance.router, prefix="/api/v1/finance", tags=["finance"])
# app.include_router(research.router, prefix="/api/v1/research", tags=["research"])
# app.include_router(automations.router, prefix="/api/v1/automations", tags=["automations"])
