import asyncio
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

import backend.app.models  # Register all models on Base.metadata
from backend.app.core.database import Base, get_db, init_db
from backend.app.core.config import settings
from backend.app.main import app
from backend.app.services.location_service import LocationService
from backend.app.engine.scheduler import background_engine_scheduler

# Ensure background scheduler is stopped during unit test execution
background_engine_scheduler.stop()

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
)

TestSessionLocal = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


import uuid
from backend.app.models.user import User
from backend.app.core.security import get_password_hash, create_access_token

TEST_ADMIN_ID = "00000000-0000-0000-0000-000000000001"
TEST_ADMIN_EMAIL = "testadmin@sih2026.gov.in"


@pytest_asyncio.fixture(scope="session", autouse=True)
async def init_main_db():
    await init_db()


@pytest_asyncio.fixture(scope="function")
async def db_session():
    # Set data mode to SIMULATION for fast, reliable, offline-safe unit test execution
    original_mode = settings.DATA_MODE
    settings.DATA_MODE = "SIMULATION"

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with TestSessionLocal() as session:
        await LocationService.seed_initial_locations(session)
        # Seed test admin user for authenticated test operations
        test_admin = User(
            id=TEST_ADMIN_ID,
            email=TEST_ADMIN_EMAIL,
            hashed_password=get_password_hash("AdminPass123!"),
            full_name="System Test Admin",
            role="ADMIN",
            is_active=True,
        )
        session.add(test_admin)
        await session.commit()

        yield session
        await session.rollback()

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    settings.DATA_MODE = original_mode


@pytest_asyncio.fixture(scope="function")
async def client(db_session):
    async def override_get_db():
        yield db_session

    admin_token = create_access_token(
        user_id=TEST_ADMIN_ID,
        role="ADMIN",
    )



    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"Authorization": f"Bearer {admin_token}"},
    ) as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest_asyncio.fixture(scope="function")
async def anon_client(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as ac:
        yield ac
    app.dependency_overrides.clear()


