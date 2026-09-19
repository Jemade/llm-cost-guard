from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as _models  # noqa: F401
from app.api.health import router as health_router
from app.api.metrics import router as metrics_router
from app.api.v1 import router as v1_router
from app.config import get_settings
from app.core.database import Base, engine, get_db
from app.core.logging import logger
from app.services.analytics_service import analytics_service
from app.services.pricing_catalog import pricing_catalog


@asynccontextmanager
async def lifespan(app_instance: FastAPI):
    settings = get_settings()
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION} [{settings.APP_ENV}]")

    # Ensure tables exist (helpful for local dev and testing)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Ensure pricing catalog is loaded
    pricing_catalog.load()
    logger.info("Pricing catalog verified.")

    yield

    # Clean up DB engine
    await engine.dispose()
    logger.info(f"Shutdown complete for {settings.APP_NAME}")


settings = get_settings()

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=(
        "LLM Cost Guard is a production-grade token cost estimation, usage tracking, "
        "and concurrency-safe budget enforcement system for AI applications."
    ),
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static and Templates
BASE_DIR = Path(__file__).resolve().parent
static_dir = BASE_DIR / "static"
templates_dir = BASE_DIR / "templates"

if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

templates = Jinja2Templates(directory=str(templates_dir))

# Include API Routers
app.include_router(health_router, tags=["Health"])
app.include_router(metrics_router, tags=["Metrics"])
app.include_router(v1_router)


@app.get("/dashboard", response_class=HTMLResponse, tags=["Dashboard"], include_in_schema=False)
async def get_dashboard(request: Request, db: AsyncSession = Depends(get_db)):
    summary = await analytics_service.get_summary(db)
    models = await analytics_service.get_spend_by_model(db)
    endpoints = await analytics_service.get_spend_by_endpoint(db)
    recent = await analytics_service.get_recent_requests(db, limit=25)

    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "summary": summary,
            "models": models,
            "endpoints": endpoints,
            "recent": recent,
            "app_name": settings.APP_NAME,
            "version": settings.APP_VERSION,
        },
    )


@app.get("/", include_in_schema=False)
async def root():
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "online",
        "docs": "/docs",
        "dashboard": "/dashboard",
    }
