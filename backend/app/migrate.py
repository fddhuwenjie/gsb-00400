import logging
from sqlalchemy import text, inspect
from sqlalchemy.ext.asyncio import AsyncEngine
from app.models import Base

logger = logging.getLogger(__name__)

NEW_COLUMNS = {
    "file_records": [
        ("document_id", "INTEGER"),
        ("version_number", "INTEGER DEFAULT 1"),
        ("review_comment", "TEXT"),
        ("reviewed_by", "INTEGER"),
        ("reviewed_at", "DATETIME"),
        ("change_description", "TEXT"),
        ("uploaded_by", "INTEGER"),
    ]
}

NEW_TABLES = ["documents"]


async def _get_existing_tables(conn) -> set:
    result = await conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
    return {row[0] for row in result.fetchall()}


async def _get_existing_columns(conn, table_name: str) -> set:
    result = await conn.execute(text(f"PRAGMA table_info({table_name})"))
    return {row[1] for row in result.fetchall()}


async def run_migrations(engine: AsyncEngine):
    """可重复执行的数据库迁移：新增表、新增列、回填历史数据。"""
    async with engine.begin() as conn:
        existing_tables = await _get_existing_tables(conn)

        for table_name in NEW_TABLES:
            if table_name not in existing_tables:
                logger.info(f"[migrate] 创建新表: {table_name}")
                await conn.run_sync(
                    lambda sync_conn, t=table_name: Base.metadata.tables[t].create(sync_conn, checkfirst=True)
                )
            else:
                logger.info(f"[migrate] 表 {table_name} 已存在，跳过")

        for table_name, columns in NEW_COLUMNS.items():
            if table_name not in existing_tables:
                continue
            existing_cols = await _get_existing_columns(conn, table_name)
            for col_name, col_type in columns:
                if col_name not in existing_cols:
                    logger.info(f"[migrate] 表 {table_name} 添加列: {col_name}")
                    await conn.execute(text(
                        f"ALTER TABLE {table_name} ADD COLUMN {col_name} {col_type}"
                    ))
                else:
                    logger.info(f"[migrate] 列 {table_name}.{col_name} 已存在，跳过")

        if "documents" in await _get_existing_tables(conn) and "file_records" in await _get_existing_tables(conn):
            await _backfill_documents(conn)
            await _backfill_current_versions(conn)


async def _backfill_documents(conn):
    """为没有 document_id 的旧 file_records 创建 Document 并关联。"""
    result = await conn.execute(text(
        "SELECT id, original_name, bucket FROM file_records WHERE document_id IS NULL"
    ))
    orphan_files = result.fetchall()
    if not orphan_files:
        return

    logger.info(f"[migrate] 发现 {len(orphan_files)} 条无文档关联的文件记录，正在回填...")

    for file_id, original_name, bucket in orphan_files:
        key_base = (original_name or "untitled").rsplit(".", 1)[0].lower()
        key_base = "".join(c if c.isalnum() or c in "-_" else "-" for c in key_base)
        doc_key = f"{key_base}-{file_id}"

        await conn.execute(text(
            "INSERT INTO documents (document_key, title, created_at, updated_at) "
            "VALUES (:key, :title, datetime('now'), datetime('now'))"
        ), {"key": doc_key, "title": original_name})

        doc_result = await conn.execute(text("SELECT last_insert_rowid()"))
        doc_id = doc_result.scalar()

        await conn.execute(text(
            "UPDATE file_records SET document_id = :doc_id, version_number = 1 WHERE id = :fid"
        ), {"doc_id": doc_id, "fid": file_id})

    logger.info(f"[migrate] 回填完成，创建了 {len(orphan_files)} 个文档记录")


async def _backfill_current_versions(conn):
    """将已审核通过的旧版本设为对应文档的当前版本（仅当文档尚未设置 current_version_id 时）。"""
    result = await conn.execute(text(
        "SELECT d.id, COALESCE(f.id, NULL) AS ver_id "
        "FROM documents d "
        "LEFT JOIN file_records f ON f.document_id = d.id AND f.review_status = 'approved' "
        "WHERE d.current_version_id IS NULL"
    ))
    rows = result.fetchall()
    updated = 0
    for doc_id, ver_id in rows:
        if ver_id is not None:
            await conn.execute(text(
                "UPDATE documents SET current_version_id = :vid, updated_at = datetime('now') WHERE id = :did"
            ), {"vid": ver_id, "did": doc_id})
            updated += 1
    if updated:
        logger.info(f"[migrate] 为 {updated} 个文档回填了当前发布版本")
