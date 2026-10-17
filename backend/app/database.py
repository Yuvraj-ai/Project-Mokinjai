from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from app.logging import logger
from app.config import get_settings

settings = get_settings()

engine = create_async_engine(settings.DATABASE_URL, echo=False, pool_pre_ping=True)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

# Host and database only: the URL carries the database password, and this module
# is imported by Alembic on every migration, so logging it in full would print
# the credential to the log stream on every run.
_url = make_url(settings.DATABASE_URL)
logger.info(f"Database engine initialized — host: {_url.host}, database: {_url.database}")


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()
