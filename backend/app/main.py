from contextlib import asynccontextmanager
from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.auth import router as auth_router
from app.api.calendar import router as calendar_router
from app.api.health import router as health_router
from app.api.insights import router as insights_router
from app.api.posts import router as posts_router
from app.api.publishing import router as publishing_router
from app.api.queue import router as queue_router
from app.api.workspaces import router as workspaces_router
from app.core.config import settings
from app.core.database import engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    yield
    # Shutdown: gracefully close the connection engine pool
    await engine.dispose()


app = FastAPI(
    title="Social Operations Hub V2 API",
    description="Backend API for Social Operations Hub V2",
    version="0.1.0",
    lifespan=lifespan,
)

cors_origins = [str(origin).rstrip("/") for origin in settings.CORS_ORIGINS]
has_wildcard = "*" in cors_origins

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=not has_wildcard,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API v1 Router aggregation
api_v1_router = APIRouter(prefix="/api/v1")
api_v1_router.include_router(health_router)
api_v1_router.include_router(auth_router)
api_v1_router.include_router(workspaces_router)
api_v1_router.include_router(posts_router)
api_v1_router.include_router(publishing_router)
api_v1_router.include_router(queue_router)
api_v1_router.include_router(calendar_router)
api_v1_router.include_router(insights_router)

# Mount both root /health and /api/v1/*
app.include_router(health_router)
app.include_router(api_v1_router)


@app.get("/")
async def root():
    return {
        "service": "Social Operations Hub V2 API",
        "version": "0.1.0",
        "status": "running",
        "docs_url": "/docs",
    }
