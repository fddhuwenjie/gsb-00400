import io
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text

from app.models import Base


class TestPermissions:
    async def _upload(self, client, filename="test.txt", content=b"hello"):
        return await client.post(
            "/api/files/upload",
            files={"files": (filename, io.BytesIO(content), "text/plain")},
            data={}
        )

    async def test_upload_requires_auth(self, client):
        resp = await self._upload(client)
        assert resp.status_code == 401

    async def test_upload_allowed_for_logged_in_user(self, user_client):
        resp = await self._upload(user_client)
        assert resp.status_code == 200
        assert resp.json()["uploaded"] == 1

    async def test_upload_records_uploaded_by(self, auth_client):
        resp = await self._upload(auth_client)
        file_id = resp.json()["files"][0]["id"]
        await asyncio.sleep(0.5)
        detail = await auth_client.get(f"/api/files/{file_id}")
        assert detail.status_code == 200

    async def test_review_requires_admin(self, user_client):
        upload = await self._upload(user_client)
        file_id = upload.json()["files"][0]["id"]
        doc_id = upload.json()["files"][0]["document_id"]
        await asyncio.sleep(0.5)

        resp = await user_client.post(
            f"/api/documents/{doc_id}/versions/{file_id}/review",
            params={"action": "approve"}
        )
        assert resp.status_code == 403

    async def test_review_legacy_requires_admin(self, user_client):
        upload = await self._upload(user_client)
        file_id = upload.json()["files"][0]["id"]
        resp = await user_client.post(f"/api/files/{file_id}/review", params={"action": "approve"})
        assert resp.status_code == 403

    async def test_switch_version_requires_admin(self, auth_client, user_client):
        upload = await self._upload(auth_client)
        doc_id = upload.json()["files"][0]["document_id"]
        v1 = upload.json()["files"][0]["id"]
        await asyncio.sleep(0.5)
        await auth_client.post(
            f"/api/documents/{doc_id}/versions/{v1}/review",
            params={"action": "approve"}
        )

        resp = await user_client.post(f"/api/documents/{doc_id}/switch-version/{v1}")
        assert resp.status_code == 403

    async def test_reindex_requires_admin(self, user_client):
        resp = await user_client.post("/api/files/reindex")
        assert resp.status_code == 403

    async def test_review_records_reviewer(self, auth_client):
        upload = await self._upload(auth_client, "reviewer-test.txt")
        doc_id = upload.json()["files"][0]["document_id"]
        v1 = upload.json()["files"][0]["id"]
        await asyncio.sleep(0.5)

        await auth_client.post(
            f"/api/documents/{doc_id}/versions/{v1}/review",
            params={"action": "approve", "comment": "looks good"}
        )

        doc_resp = await auth_client.get(f"/api/documents/{doc_id}")
        version = doc_resp.json()["versions"][0]
        assert version["reviewer_name"] == "admin"
        assert version["uploader_name"] == "admin"


class TestRejectRequiresReason:
    async def _upload_and_get_ids(self, client, name="reject-reason.txt"):
        resp = await client.post(
            "/api/files/upload",
            files={"files": (name, io.BytesIO(b"content"), "text/plain")}
        )
        await asyncio.sleep(0.3)
        data = resp.json()["files"][0]
        return data["document_id"], data["id"]

    async def test_document_reject_without_comment_fails(self, auth_client):
        doc_id, ver_id = await self._upload_and_get_ids(auth_client)
        resp = await auth_client.post(
            f"/api/documents/{doc_id}/versions/{ver_id}/review",
            params={"action": "reject"}
        )
        assert resp.status_code == 400
        assert "原因" in resp.json()["message"]

    async def test_document_reject_with_empty_comment_fails(self, auth_client):
        doc_id, ver_id = await self._upload_and_get_ids(auth_client)
        resp = await auth_client.post(
            f"/api/documents/{doc_id}/versions/{ver_id}/review",
            params={"action": "reject", "comment": "   "}
        )
        assert resp.status_code == 400

    async def test_document_reject_with_comment_succeeds(self, auth_client):
        doc_id, ver_id = await self._upload_and_get_ids(auth_client)
        resp = await auth_client.post(
            f"/api/documents/{doc_id}/versions/{ver_id}/review",
            params={"action": "reject", "comment": "内容不完整"}
        )
        assert resp.status_code == 200

    async def test_legacy_reject_without_comment_fails(self, auth_client):
        _, file_id = await self._upload_and_get_ids(auth_client, "legacy-reject.txt")
        resp = await auth_client.post(
            f"/api/files/{file_id}/review",
            params={"action": "reject"}
        )
        assert resp.status_code == 400

    async def test_approve_without_comment_succeeds(self, auth_client):
        doc_id, ver_id = await self._upload_and_get_ids(auth_client, "approve-nocomment.txt")
        resp = await auth_client.post(
            f"/api/documents/{doc_id}/versions/{ver_id}/review",
            params={"action": "approve"}
        )
        assert resp.status_code == 200


class TestStatsConsistency:
    async def _upload_and_approve(self, auth_client, filename, content=b"approved content"):
        resp = await auth_client.post(
            "/api/files/upload",
            files={"files": (filename, io.BytesIO(content), "text/plain")}
        )
        await asyncio.sleep(0.5)
        data = resp.json()["files"][0]
        await auth_client.post(
            f"/api/documents/{data['document_id']}/versions/{data['id']}/review",
            params={"action": "approve"}
        )
        return data

    async def test_tag_stats_only_approved_current(self, auth_client):
        await self._upload_and_approve(auth_client, "published.txt", b"published v1 content")

        resp2 = await auth_client.post(
            "/api/files/upload",
            files={"files": ("published.txt", io.BytesIO(b"published v2 content"), "text/plain")},
            data={"change_description": "v2 update"}
        )
        await asyncio.sleep(0.5)
        v2 = resp2.json()["files"][0]

        tag_resp = await auth_client.get("/api/stats/tags")
        assert tag_resp.status_code == 200

    async def test_overview_approved_counts_only_current(self, auth_client):
        d1 = await self._upload_and_approve(auth_client, "over1.txt", b"first")
        d2 = await self._upload_and_approve(auth_client, "over2.txt", b"second")

        resp = await auth_client.get("/api/stats/overview")
        data = resp.json()
        assert data["approved"] >= 2
        assert data["total_documents"] >= 2

    async def test_old_version_not_in_default_search(self, auth_client):
        d1 = await self._upload_and_approve(auth_client, "searchable.txt", b"version one content")
        doc_id = d1["document_id"]
        v1 = d1["id"]

        resp2 = await auth_client.post(
            "/api/files/upload",
            files={"files": ("searchable.txt", io.BytesIO(b"version two content"), "text/plain")},
            data={"change_description": "v2"}
        )
        await asyncio.sleep(0.5)
        v2 = resp2.json()["files"][0]["id"]

        await auth_client.post(
            f"/api/documents/{doc_id}/versions/{v2}/review",
            params={"action": "approve"}
        )

        detail = await auth_client.get(f"/api/files/{v1}")
        assert detail.status_code == 200
        assert detail.json()["file"]["is_current"] is False


class TestMigrationIdempotency:
    async def test_migration_runs_repeatedly(self):
        from app.migrate import run_migrations
        engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
        async with engine.begin() as conn:
            from app.models import Base
            await conn.run_sync(Base.metadata.create_all)

        await run_migrations(engine)
        await run_migrations(engine)

        async with AsyncSession(engine) as session:
            result = await session.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
            tables = {row[0] for row in result.fetchall()}
            assert "documents" in tables
            assert "file_records" in tables

            result = await session.execute(text("PRAGMA table_info(file_records)"))
            columns = {row[1] for row in result.fetchall()}
            assert "document_id" in columns
            assert "version_number" in columns
            assert "uploaded_by" in columns
            assert "reviewed_by" in columns

        await engine.dispose()

    async def test_migration_backfills_orphan_files(self):
        from app.migrate import run_migrations
        engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)

        async with engine.begin() as conn:
            await conn.execute(text("""
                CREATE TABLE file_records (
                    id INTEGER PRIMARY KEY,
                    original_name VARCHAR(255),
                    file_type VARCHAR(50),
                    bucket VARCHAR(50),
                    process_status VARCHAR(20) DEFAULT 'pending',
                    review_status VARCHAR(20) DEFAULT 'pending',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """))
            await conn.execute(text(
                "INSERT INTO file_records (id, original_name, bucket, review_status) "
                "VALUES (1, 'old-doc.txt', '方案', 'approved')"
            ))
            await conn.execute(text(
                "INSERT INTO file_records (id, original_name, bucket, review_status) "
                "VALUES (2, 'another.txt', '彩页', 'pending')"
            ))

        await run_migrations(engine)

        async with AsyncSession(engine) as session:
            result = await session.execute(text("SELECT COUNT(*) FROM documents"))
            doc_count = result.scalar()
            assert doc_count == 2

            result = await session.execute(text(
                "SELECT document_id, version_number FROM file_records WHERE id = 1"
            ))
            row = result.fetchone()
            assert row[0] is not None
            assert row[1] == 1

            result = await session.execute(text(
                "SELECT current_version_id FROM documents WHERE id = ("
                "SELECT document_id FROM file_records WHERE id = 1)"
            ))
            current_vid = result.scalar()
            assert current_vid == 1

        await engine.dispose()
