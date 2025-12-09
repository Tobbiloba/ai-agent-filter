"""Main FastAPI application."""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from server.config import get_settings
from server.database import init_db, close_db, get_database_type
from server.cache import init_cache, close_cache, get_cache
from server.routes import validate_router, policies_router, logs_router, projects_router

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup/shutdown."""
    # Startup
    await init_db()
    await init_cache()
    yield
    # Shutdown
    await close_cache()
    await close_db()


app = FastAPI(
    title="AI Agent Safety Filter",
    description="Middleware that intercepts AI agent actions, validates them against policy rules, and logs all activity.",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    cache = get_cache()
    return {
        "status": "healthy",
        "version": "0.1.0",
        "database": get_database_type(),
        "cache": "redis" if cache.is_available else "disabled",
    }


@app.get("/")
async def root():
    """Root endpoint with API info."""
    return {
        "name": "AI Agent Safety Filter",
        "version": "0.1.0",
        "docs": "/docs",
        "health": "/health",
    }


# Include routers
app.include_router(validate_router)
app.include_router(policies_router)
app.include_router(logs_router)
app.include_router(projects_router)
