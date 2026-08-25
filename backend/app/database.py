from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import inspect, text
from app.config import settings
from app.models import Base
import logging
import os

logger = logging.getLogger(__name__)

os.makedirs("data", exist_ok=True)

engine = create_async_engine(settings.DATABASE_URL, echo=False)
async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

# 新增字段的兼容升级清单：{表名: [(列名, 列定义SQL), ...]}
# 用于为缺少这些字段的旧库补齐，避免因缺列导致访问失败。
_COLUMN_MIGRATIONS = {
    "file_records": [
        ("group_id", "INTEGER"),
        ("version_no", "INTEGER DEFAULT 1"),
        ("change_note", "TEXT"),
        ("uploaded_by", "INTEGER"),
    ],
}


def _sync_migrate(conn):
    """轻量级迁移：为已有 SQLite 库补充新增表与字段。

    - create_all 会创建缺失的新表（如 document_groups），已存在的表不受影响。
    - 随后逐列检查 file_records，补齐缺失字段，兼容旧数据库。
    """
    Base.metadata.create_all(conn)

    inspector = inspect(conn)
    existing_tables = set(inspector.get_table_names())
    for table, columns in _COLUMN_MIGRATIONS.items():
        if table not in existing_tables:
            continue
        existing_cols = {col["name"] for col in inspector.get_columns(table)}
        for col_name, col_def in columns:
            if col_name not in existing_cols:
                logger.info(f"Migrating {table}: add column {col_name}")
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col_name} {col_def}"))


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(_sync_migrate)

async def get_db():
    async with async_session() as session:
        yield session
