from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.base import Base
from app.db.models import User, UserRole
from app.services.catalog import seed_catalog


@pytest_asyncio.fixture
async def async_db_engine():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(async_db_engine):
    async_session = async_sessionmaker(async_db_engine, expire_on_commit=False, class_=AsyncSession)
    async with async_session() as session:
        await seed_catalog(session)
        yield session


@pytest.fixture
def mock_bot():
    bot = AsyncMock()
    bot.send_message = AsyncMock()
    return bot


@pytest_asyncio.fixture
async def client_user(db_session):
    user = User(
        telegram_id=100001,
        username="test_client",
        full_name="Иван Клиент",
        phone="+79991112233",
        role=UserRole.CLIENT,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def master_user(db_session):
    user = User(
        telegram_id=200002,
        username="test_master",
        full_name="Пётр Мастер",
        phone="+79992223344",
        role=UserRole.MASTER,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def admin_user(db_session):
    user = User(
        telegram_id=300003,
        username="test_admin",
        full_name="Алексей Админ",
        phone="+79993334455",
        role=UserRole.ADMIN,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user
