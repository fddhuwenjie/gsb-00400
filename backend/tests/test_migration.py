import pytest
from sqlalchemy import create_engine, text, inspect
from app.database import _sync_migrate


def _make_legacy_db(path):
    """构造一个“旧版”SQLite 库：只有精简的 file_records 表，缺少新增列，
    且没有 document_groups 表，模拟升级前的历史数据库。"""
    engine = create_engine(f"sqlite:///{path}")
    with engine.begin() as conn:
        conn.execute(text(
            """
            CREATE TABLE file_records (
                id INTEGER PRIMARY KEY,
                original_name VARCHAR(255),
                bucket VARCHAR(50),
                process_status VARCHAR(20),
                review_status VARCHAR(20)
            )
            """
        ))
        conn.execute(text(
            "INSERT INTO file_records (original_name, bucket, process_status, review_status) "
            "VALUES ('legacy.txt', '方案', 'completed', 'approved')"
        ))
    return engine


class TestSqliteMigration:
    def test_migration_adds_table_and_columns(self, tmp_path):
        db_path = tmp_path / "legacy.db"
        engine = _make_legacy_db(str(db_path))

        # 执行迁移
        with engine.begin() as conn:
            _sync_migrate(conn)

        insp = inspect(engine)
        tables = set(insp.get_table_names())
        # 新增表已创建
        assert "document_groups" in tables
        # file_records 补齐了新字段
        cols = {c["name"] for c in insp.get_columns("file_records")}
        for expected in ("group_id", "version_no", "change_note", "uploaded_by"):
            assert expected in cols

    def test_migration_preserves_existing_data(self, tmp_path):
        db_path = tmp_path / "legacy2.db"
        engine = _make_legacy_db(str(db_path))
        with engine.begin() as conn:
            _sync_migrate(conn)
        # 旧数据仍在，且新列默认值可读取
        with engine.begin() as conn:
            row = conn.execute(text(
                "SELECT original_name, version_no FROM file_records"
            )).fetchone()
        assert row[0] == "legacy.txt"
        # version_no 默认 1
        assert row[1] == 1

    def test_migration_is_idempotent(self, tmp_path):
        db_path = tmp_path / "legacy3.db"
        engine = _make_legacy_db(str(db_path))
        with engine.begin() as conn:
            _sync_migrate(conn)
        # 再次执行不应报错（列已存在时跳过）
        with engine.begin() as conn:
            _sync_migrate(conn)
        insp = inspect(engine)
        cols = {c["name"] for c in insp.get_columns("file_records")}
        assert "group_id" in cols
