import time
from typing import AsyncGenerator, Dict, Any
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy import text
from backend.app.core.config import settings
from backend.app.core.logging import logger

db_url = settings.ASYNC_DATABASE_URL
is_sqlite = db_url.startswith("sqlite")
is_postgres = "postgres" in db_url

connect_args: Dict[str, Any] = {}
engine_kwargs: Dict[str, Any] = {
    "echo": settings.DB_ECHO,
    "future": True,
}

if is_sqlite:
    connect_args["check_same_thread"] = False
    engine_kwargs["connect_args"] = connect_args
elif is_postgres:
    # PostgreSQL / Supabase Connection Pool configuration
    # pool_pre_ping=True tests connections prior to checkout (vital for Supabase Transaction Pooler)
    engine_kwargs["pool_size"] = settings.DB_POOL_SIZE
    engine_kwargs["max_overflow"] = settings.DB_MAX_OVERFLOW
    engine_kwargs["pool_timeout"] = settings.DB_POOL_TIMEOUT
    engine_kwargs["pool_recycle"] = settings.DB_POOL_RECYCLE
    engine_kwargs["pool_pre_ping"] = True

    # Supabase Transaction Pooler (PgBouncer port 6543) requires statement_cache_size=0
    connect_args["statement_cache_size"] = 0
    connect_args["prepared_statement_cache_size"] = 0

    # SSL handling for remote PostgreSQL / Supabase
    if "ssl" not in db_url.lower() and settings.DB_SSL_MODE in ["require", "prefer"]:
        if settings.DB_SSL_MODE == "require":
            connect_args["ssl"] = True
    if connect_args:
        engine_kwargs["connect_args"] = connect_args


engine = create_async_engine(db_url, **engine_kwargs)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

Base = declarative_base()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for injecting an async database session per request."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def check_database_health() -> Dict[str, Any]:
    """
    Validates database connectivity and measures round-trip query latency.
    Exposes no secrets or connection strings.
    """
    start_time = time.perf_counter()
    dialect = "sqlite" if is_sqlite else "postgresql"
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
        return {
            "status": "healthy",
            "reachable": True,
            "latency_ms": latency_ms,
            "engine": dialect,
            "pool_pre_ping": engine_kwargs.get("pool_pre_ping", False),
        }
    except Exception as e:
        latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
        logger.error(f"Database health check failed: {e}")
        return {
            "status": "unhealthy",
            "reachable": False,
            "latency_ms": latency_ms,
            "engine": dialect,
            "error": "Connection error to configured database.",
        }


async def init_db():
    """Initializes the database schema."""
    logger.info(f"Initializing database tables on {dialect_name()}...")
    # Import all models to register with Base.metadata
    from backend.app.models import (
        location,
        weather,
        risk,
        event,
        history,
        field,
        alerting,
        analytics,
        audit,
        public,
        earth_observation,
        citizen,
        user,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database initialized successfully.")


def dialect_name() -> str:
    return "SQLite" if is_sqlite else "PostgreSQL (Supabase)"
