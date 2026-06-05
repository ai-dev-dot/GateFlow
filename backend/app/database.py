from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings

settings = get_settings()

# P0-5: explicit connection pool tuning.
# Defaults before: 5 connections, no pre-ping, no recycle. Symptoms in
# production: stale connections after PG idle-timeout (idle clients
# returning 500 to users), pool exhaustion under bursty traffic.
# Now configurable via .env (DB_POOL_SIZE, DB_MAX_OVERFLOW, DB_POOL_RECYCLE_SECONDS).
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_pre_ping=True,   # verify connection is alive before checkout
    pool_recycle=settings.DB_POOL_RECYCLE_SECONDS,  # recycle before idle-timeout
)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db():
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()
