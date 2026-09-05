from contextlib import asynccontextmanager
from datetime import datetime, timezone
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.app.core.config import settings
from backend.app.core.database import init_db, AsyncSessionLocal
from backend.app.core.logging import logger
from backend.app.services.location_service import LocationService
from backend.app.api.v1.router import api_router


from backend.app.engine.scheduler import background_engine_scheduler, live_ingestion_scheduler
from backend.app.engine.status import engine_status_tracker


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize tables and seed initial NER monitoring stations
    logger.info(f"Starting {settings.PROJECT_NAME} v{settings.VERSION} [{settings.ENVIRONMENT}]")
    try:
        await init_db()
        async with AsyncSessionLocal() as session:
            await LocationService.seed_initial_locations(session)
        logger.info("Application startup completed successfully.")
    except Exception as err:
        logger.error(f"Database initialization deferred on startup ({err}). Server continuing startup...")

    # Start automated background assessment engine scheduler
    background_engine_scheduler.start()
    # Start dedicated continuous live telemetry ingestion scheduler
    live_ingestion_scheduler.start()

    yield

    # Shutdown
    logger.info("Shutting down application...")
    live_ingestion_scheduler.stop()
    background_engine_scheduler.stop()



app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description=(
        "MVP Disaster Intelligence Engine for DISASTRA: AI-Based Early Warning and "
        "Landslide Risk Monitoring System in the North Eastern Region (NER)."
    ),
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# CORS Configuration - Explicit origins + dynamic Vercel wildcard regex
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    """
    OWASP-aligned HTTP Security Headers Middleware.
    Enforces MIME sniffing protection, clickjacking defense, referrer policy,
    permissions policy, and content security policy across all endpoints.
    """
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=(self)"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "img-src 'self' data: https:; "
        "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
        "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
        "frame-ancestors 'none';"
    )
    return response



@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception on {request.method} {request.url.path}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An internal server error occurred while processing the request."}
    )


@app.get("/health", tags=["Health"])
async def health_check():
    """
    Consolidated health check endpoint returning system status, database reachability,
    cache health, engine execution state, and data provider metrics.
    Exposes NO passwords, API keys, or connection strings.
    """
    from backend.app.core.database import check_database_health
    from backend.app.core.redis import redis_service
    db_health = await check_database_health()
    cache_health = await redis_service.check_health()
    engine_state = engine_status_tracker.get_status_payload()
    return {
        "status": "healthy" if (db_health["reachable"] and cache_health["reachable"]) else "degraded",
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
        "application_mode": settings.DATA_MODE,
        "database": {
            "reachable": db_health["reachable"],
            "engine": db_health["engine"],
            "latency_ms": db_health["latency_ms"],
        },
        "cache": {
            "reachable": cache_health["reachable"],
            "backend": cache_health.get("backend", "in_memory"),
            "mode": cache_health.get("mode", "LOCAL_MEMORY"),
            "latency_ms": cache_health.get("latency_ms", 0.0),
        },
        "engine": {
            "status": engine_state["engine_status"],
            "version": engine_state["engine_version"],
            "last_run_at": engine_state["last_run_at"],
            "last_success_at": engine_state["last_success_at"],
            "locations_evaluated": engine_state["locations_evaluated"],
            "active_events_count": engine_state["active_events_count"],
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "disclaimer": "Landslide risk calculation formulas represent a prototype analytical model."
    }



from backend.app.api.v1.endpoints.health_ready import router as health_ready_router

# Include Health Probes & Prometheus Metrics
app.include_router(health_ready_router, prefix="/health", tags=["Health & Readiness"])
app.include_router(health_ready_router, prefix="", tags=["Metrics"])

# Include API v1 routes
app.include_router(api_router, prefix=settings.API_V1_STR)
