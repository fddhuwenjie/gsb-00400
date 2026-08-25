import pytest
import io

class TestFilesAPI:
    async def test_upload_file(self, auth_client):
        content = "测试文件内容".encode("utf-8")
        resp = await auth_client.post(
            "/api/files/upload",
            files={"files": ("test.txt", io.BytesIO(content), "text/plain")}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["uploaded"] == 1
        assert len(data["files"]) == 1

    async def test_list_files_empty(self, auth_client):
        resp = await auth_client.get("/api/files/list")
        assert resp.status_code == 200
        assert resp.json()["files"] == []

    async def test_list_files_after_upload(self, auth_client):
        await auth_client.post(
            "/api/files/upload",
            files={"files": ("test.txt", io.BytesIO(b"content"), "text/plain")}
        )
        import asyncio
        await asyncio.sleep(1)
        resp = await auth_client.get("/api/files/list")
        assert resp.status_code == 200
        assert len(resp.json()["files"]) >= 1

    async def test_list_files_filter_bucket(self, auth_client):
        resp = await auth_client.get("/api/files/list", params={"bucket": "方案"})
        assert resp.status_code == 200

    async def test_review_approve(self, auth_client):
        await auth_client.post(
            "/api/files/upload",
            files={"files": ("test.txt", io.BytesIO(b"content"), "text/plain")}
        )
        import asyncio
        await asyncio.sleep(1)
        resp = await auth_client.post("/api/files/1/review", params={"action": "approve"})
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    async def test_review_invalid_action(self, auth_client):
        await auth_client.post(
            "/api/files/upload",
            files={"files": ("test.txt", io.BytesIO(b"content"), "text/plain")}
        )
        resp = await auth_client.post("/api/files/1/review", params={"action": "invalid"})
        assert resp.status_code == 400
