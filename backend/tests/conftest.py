"""Shared fixtures for GateFlow tests.

提供 in-memory SQLite 引擎和异步 session fixture，
让 service 层和 router 层测试可以跑起来（不需要外部 PostgreSQL）。
"""

import asyncio
import uuid
from datetime import datetime
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

from app.models import Base
from app.models.user import Department, Role, User
from app.models.agent_type import AgentType
from app.services.provider_adapters import (
    AnthropicAdapter,
    OpenAIAdapter,
    get_adapter,
)


# ---------- Provider adapter fixtures ----------

@pytest.fixture
def openai_adapter():
    return OpenAIAdapter()


@pytest.fixture
def anthropic_adapter():
    return AnthropicAdapter()


# ---------- DB fixtures (in-memory SQLite) ----------

@pytest_asyncio.fixture
async def db_engine():
    """In-memory SQLite engine with shared connection (StaticPool).

    In-memory SQLite normally gives each connection a separate database.
    StaticPool forces a single shared connection so all sessions see the
    same schema and data.
    """
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(db_engine) -> AsyncGenerator[AsyncSession, None]:
    """Single async session for a test. Caller responsible for commit/rollback."""
    async_session_maker = async_sessionmaker(
        db_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with async_session_maker() as session:
        yield session


# ---------- Domain fixtures ----------

@pytest_asyncio.fixture
async def test_user(db_session: AsyncSession) -> User:
    """A regular test user with department + role eagerly loaded."""
    from sqlalchemy.orm import selectinload

    dept = Department(name="工程部")
    db_session.add(dept)
    role = Role(name="user", permissions={})
    db_session.add(role)
    await db_session.flush()

    user = User(
        username="alice",
        email="alice@test.local",
        hashed_password="dummy",
        department_id=dept.id,
        role_id=role.id,
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()

    # Re-fetch with eager loaded relationships (avoids lazy-load greenlet issues
    # when callers access user.department / user.role in services).
    result = await db_session.execute(
        select(User)
        .where(User.id == user.id)
        .options(selectinload(User.department), selectinload(User.role))
    )
    return result.scalar_one()


@pytest_asyncio.fixture
async def admin_user(db_session: AsyncSession) -> User:
    from sqlalchemy.orm import selectinload

    dept = Department(name="管理部")
    db_session.add(dept)
    role = Role(name="admin", permissions={"all": True})
    db_session.add(role)
    await db_session.flush()

    user = User(
        username="admin",
        email="admin@test.local",
        hashed_password="dummy",
        department_id=dept.id,
        role_id=role.id,
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()

    result = await db_session.execute(
        select(User)
        .where(User.id == user.id)
        .options(selectinload(User.department), selectinload(User.role))
    )
    return result.scalar_one()
