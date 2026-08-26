from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.config import settings
from app.models import Base
import os
import logging

logger = logging.getLogger(__name__)

os.makedirs("data", exist_ok=True)

engine = create_async_engine(settings.DATABASE_URL, echo=False)
async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    from app.migrate import run_migrations
    await run_migrations(engine)
    logger.info("Database migrations completed")

async def get_db():
    async with async_session() as session:
        yield session
