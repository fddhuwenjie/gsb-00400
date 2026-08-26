import pytest
import io
import asyncio


class TestDocumentVersioning:
    async def _upload_and_wait(self, auth_client, filename, content=b"version content", doc_key=None, change_desc=None):
        data = {}
        if doc_key:
            data["document_key"] = doc_key
        if change_desc:
            data["change_description"] = change_desc
        resp = await auth_client.post(
            "/api/files/upload",
            files={"files": (filename, io.BytesIO(content), "text/plain")},
            data=data
        )
        assert resp.status_code == 200
        await asyncio.sleep(1)
        return resp.json()

    async def test_upload_creates_document(self, auth_client):
        result = await self._upload_and_wait(auth_client, "产品说明.txt", b"hello")
        assert result["uploaded"] == 1
        f = result["files"][0]
        assert f["document_id"] is not None
        assert f["version_number"] == 1
        assert f["is_new_document"] is True

    async def test_upload_same_key_creates_new_version(self, auth_client):
        r1 = await self._upload_and_wait(auth_client, "spec.txt", b"v1 content", doc_key="spec-doc")
        doc_id = r1["files"][0]["document_id"]
        assert r1["files"][0]["version_number"] == 1

        r2 = await self._upload_and_wait(auth_client, "spec.txt", b"v2 content", doc_key="spec-doc", change_desc="更新内容")
        assert r2["files"][0]["document_id"] == doc_id
        assert r2["files"][0]["version_number"] == 2
        assert r2["files"][0]["is_new_document"] is False

    async def test_upload_same_filename_auto_versions(self, auth_client):
        r1 = await self._upload_and_wait(auth_client, "产品手册-v1-2024.txt", b"v1")
        doc_id = r1["files"][0]["document_id"]
        r2 = await self._upload_and_wait(auth_client, "产品手册-v2-2024.txt", b"v2")
        assert r2["files"][0]["document_id"] == doc_id
        assert r2["files"][0]["version_number"] == 2

    async def test_document_list(self, auth_client):
        await self._upload_and_wait(auth_client, "doc-a.txt", b"a")
        resp = await auth_client.get("/api/documents")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        doc = data["documents"][0]
        assert "document_key" in doc
        assert doc["version_count"] >= 1
        assert doc["latest_version"] >= 1

    async def test_document_detail_versions(self, auth_client):
        r1 = await self._upload_and_wait(auth_client, "guide.txt", b"v1", doc_key="guide")
        doc_id = r1["files"][0]["document_id"]
        await self._upload_and_wait(auth_client, "guide.txt", b"v2", doc_key="guide", change_desc="fix")

        resp = await auth_client.get(f"/api/documents/{doc_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["versions"]) == 2
        assert data["versions"][0]["version_number"] == 2
        assert data["versions"][0]["change_description"] == "fix"

    async def test_version_detail(self, auth_client):
        r = await self._upload_and_wait(auth_client, "detail.txt", b"content here")
        doc_id = r["files"][0]["document_id"]
        version_id = r["files"][0]["id"]

        resp = await auth_client.get(f"/api/documents/{doc_id}/versions/{version_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["version"]["id"] == version_id
        assert data["version"]["version_number"] == 1
        assert "file" in data
        assert "all_versions" in data

    async def test_review_approve_sets_current(self, auth_client):
        r = await self._upload_and_wait(auth_client, "approve-me.txt", b"approved content")
        doc_id = r["files"][0]["document_id"]
        version_id = r["files"][0]["id"]

        resp = await auth_client.post(
            f"/api/documents/{doc_id}/versions/{version_id}/review",
            params={"action": "approve", "comment": "ok"}
        )
        assert resp.status_code == 200
        assert resp.json()["success"] is True

        doc_resp = await auth_client.get(f"/api/documents/{doc_id}")
        assert doc_resp.json()["current_version_id"] == version_id

    async def test_review_reject(self, auth_client):
        r = await self._upload_and_wait(auth_client, "reject-me.txt", b"bad content")
        doc_id = r["files"][0]["document_id"]
        version_id = r["files"][0]["id"]

        resp = await auth_client.post(
            f"/api/documents/{doc_id}/versions/{version_id}/review",
            params={"action": "reject", "comment": "quality issue"}
        )
        assert resp.status_code == 200
        doc_resp = await auth_client.get(f"/api/documents/{doc_id}")
        assert doc_resp.json()["current_version_id"] is None

    async def test_switch_version_requires_approved(self, auth_client):
        r1 = await self._upload_and_wait(auth_client, "switch.txt", b"v1", doc_key="sw")
        doc_id = r1["files"][0]["document_id"]
        v1 = r1["files"][0]["id"]
        r2 = await self._upload_and_wait(auth_client, "switch.txt", b"v2", doc_key="sw")
        v2 = r2["files"][0]["id"]

        resp = await auth_client.post(f"/api/documents/{doc_id}/switch-version/{v2}")
        assert resp.status_code == 400

        await auth_client.post(
            f"/api/documents/{doc_id}/versions/{v2}/review",
            params={"action": "approve"}
        )
        await auth_client.post(
            f"/api/documents/{doc_id}/versions/{v1}/review",
            params={"action": "approve"}
        )
        await auth_client.post(f"/api/documents/{doc_id}/switch-version/{v1}")
        doc_resp = await auth_client.get(f"/api/documents/{doc_id}")
        assert doc_resp.json()["current_version_id"] == v1

    async def test_approve_new_version_updates_current(self, auth_client):
        r1 = await self._upload_and_wait(auth_client, "multi.txt", b"v1", doc_key="multi")
        doc_id = r1["files"][0]["document_id"]
        v1 = r1["files"][0]["id"]
        await auth_client.post(
            f"/api/documents/{doc_id}/versions/{v1}/review",
            params={"action": "approve"}
        )

        r2 = await self._upload_and_wait(auth_client, "multi.txt", b"v2", doc_key="multi")
        v2 = r2["files"][0]["id"]

        doc_before = await auth_client.get(f"/api/documents/{doc_id}")
        assert doc_before.json()["current_version_id"] == v1

        await auth_client.post(
            f"/api/documents/{doc_id}/versions/{v2}/review",
            params={"action": "approve"}
        )
        doc_after = await auth_client.get(f"/api/documents/{doc_id}")
        assert doc_after.json()["current_version_id"] == v2

    async def test_review_invalid_action(self, auth_client):
        r = await self._upload_and_wait(auth_client, "invalid.txt", b"x")
        doc_id = r["files"][0]["document_id"]
        version_id = r["files"][0]["id"]
        resp = await auth_client.post(
            f"/api/documents/{doc_id}/versions/{version_id}/review",
            params={"action": "invalid"}
        )
        assert resp.status_code == 400

    async def test_file_list_includes_version_info(self, auth_client):
        await self._upload_and_wait(auth_client, "list-test.txt", b"x")
        resp = await auth_client.get("/api/files/list")
        assert resp.status_code == 200
        files = resp.json()["files"]
        assert len(files) >= 1
        f = files[0]
        assert "document_id" in f
        assert "version_number" in f
        assert "is_current" in f
        assert "change_description" in f

    async def test_file_detail_includes_versions(self, auth_client):
        r = await self._upload_and_wait(auth_client, "detail-file.txt", b"x")
        file_id = r["files"][0]["id"]
        resp = await auth_client.get(f"/api/files/{file_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert "versions" in data
        assert "document" in data
        assert data["file"]["version_number"] == 1

    async def test_stats_includes_total_documents(self, auth_client):
        await self._upload_and_wait(auth_client, "stat-doc.txt", b"x")
        resp = await auth_client.get("/api/stats/overview")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_documents" in data
        assert data["total_documents"] >= 1

    async def test_old_version_review_endpoint_backward_compat(self, auth_client):
        r = await self._upload_and_wait(auth_client, "legacy.txt", b"x")
        file_id = r["files"][0]["id"]
        resp = await auth_client.post(f"/api/files/{file_id}/review", params={"action": "approve"})
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    async def test_document_not_found(self, auth_client):
        resp = await auth_client.get("/api/documents/99999")
        assert resp.status_code == 404

    async def test_version_not_found(self, auth_client):
        r = await self._upload_and_wait(auth_client, "nf.txt", b"x")
        doc_id = r["files"][0]["document_id"]
        resp = await auth_client.get(f"/api/documents/{doc_id}/versions/99999")
        assert resp.status_code == 404
