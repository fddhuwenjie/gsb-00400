import pytest
import io
import asyncio


async def _upload(client, filename, content=b"content", doc_key=None, change_note=None):
    data = {}
    if doc_key is not None:
        data["doc_key"] = doc_key
    if change_note is not None:
        data["change_note"] = change_note
    return await client.post(
        "/api/files/upload",
        data=data,
        files={"files": (filename, io.BytesIO(content), "text/plain")}
    )


class TestVersioning:
    async def test_upload_same_doc_key_creates_versions(self, auth_client):
        r1 = await _upload(auth_client, "spec.txt", doc_key="业务文档A", change_note="初版")
        r2 = await _upload(auth_client, "spec.txt", doc_key="业务文档A", change_note="修订")
        assert r1.status_code == 200 and r2.status_code == 200
        v1 = r1.json()["files"][0]
        v2 = r2.json()["files"][0]
        # 同一 doc_key 归属同一分组，版本号递增，且未覆盖旧记录
        assert v1["group_id"] == v2["group_id"]
        assert v1["version_no"] == 1
        assert v2["version_no"] == 2
        assert v1["id"] != v2["id"]

    async def test_upload_records_uploader_and_note(self, auth_client):
        r = await _upload(auth_client, "spec.txt", doc_key="doc-note", change_note="变更说明XYZ")
        group_id = r.json()["files"][0]["group_id"]
        resp = await auth_client.get(f"/api/files/groups/{group_id}/versions")
        assert resp.status_code == 200
        ver = resp.json()["versions"][0]
        assert ver["change_note"] == "变更说明XYZ"
        assert ver["uploaded_by_name"] == "admin"
        assert ver["upload_date"] is not None

    async def test_list_default_returns_latest_version_only(self, auth_client):
        await _upload(auth_client, "a.txt", doc_key="grp1")
        await _upload(auth_client, "a.txt", doc_key="grp1")
        await asyncio.sleep(0.3)
        resp = await auth_client.get("/api/files/list")
        # 默认只返回该文档的最新版本
        files = [f for f in resp.json()["files"] if f["group_id"]]
        assert len(files) == 1
        assert files[0]["version_no"] == 2

    async def test_list_all_versions(self, auth_client):
        await _upload(auth_client, "a.txt", doc_key="grp2")
        await _upload(auth_client, "a.txt", doc_key="grp2")
        await asyncio.sleep(0.3)
        resp = await auth_client.get("/api/files/list", params={"all_versions": True})
        files = [f for f in resp.json()["files"] if f["group_id"]]
        assert len(files) == 2

    async def test_groups_endpoint(self, auth_client):
        await _upload(auth_client, "a.txt", doc_key="grp3")
        await _upload(auth_client, "a.txt", doc_key="grp3")
        resp = await auth_client.get("/api/files/groups")
        groups = [g for g in resp.json()["groups"] if g["doc_key"] == "grp3"]
        assert len(groups) == 1
        assert groups[0]["version_count"] == 2


class TestReviewPublish:
    async def test_approve_sets_published_version(self, auth_client):
        r1 = await _upload(auth_client, "a.txt", doc_key="pub1")
        r2 = await _upload(auth_client, "a.txt", doc_key="pub1")
        v1_id = r1.json()["files"][0]["id"]
        v2_id = r2.json()["files"][0]["id"]
        group_id = r1.json()["files"][0]["group_id"]

        # 通过 v2 -> 发布版本为 v2
        await auth_client.post(f"/api/files/{v2_id}/review", params={"action": "approve"})
        resp = await auth_client.get(f"/api/files/groups/{group_id}/versions")
        assert resp.json()["group"]["published_version_id"] == v2_id

    async def test_reject_published_falls_back(self, auth_client):
        r1 = await _upload(auth_client, "a.txt", doc_key="pub2")
        r2 = await _upload(auth_client, "a.txt", doc_key="pub2")
        v1_id = r1.json()["files"][0]["id"]
        v2_id = r2.json()["files"][0]["id"]
        group_id = r1.json()["files"][0]["group_id"]

        await auth_client.post(f"/api/files/{v1_id}/review", params={"action": "approve"})
        await auth_client.post(f"/api/files/{v2_id}/review", params={"action": "approve"})
        # 退回当前发布的 v2 -> 回退到已通过的 v1
        await auth_client.post(f"/api/files/{v2_id}/review", params={"action": "reject"})
        resp = await auth_client.get(f"/api/files/groups/{group_id}/versions")
        assert resp.json()["group"]["published_version_id"] == v1_id

    async def test_review_requires_admin(self, client):
        # 未登录用户不能审核
        resp = await client.post("/api/files/1/review", params={"action": "approve"})
        assert resp.status_code == 401

    async def test_review_forbidden_for_normal_user(self, auth_client, client):
        # 上传一个版本
        r = await _upload(auth_client, "a.txt", doc_key="perm1")
        fid = r.json()["files"][0]["id"]
        # 创建普通用户并登录
        from app.routers.auth import pwd_context
        from app.models import User
        from tests.conftest import TestSession
        async with TestSession() as s:
            s.add(User(username="normal", hashed_password=pwd_context.hash("pw"), role="user"))
            await s.commit()
        login = await client.post("/api/auth/login", data={"username": "normal", "password": "pw"})
        token = login.json()["access_token"]
        client.headers["Authorization"] = f"Bearer {token}"
        resp = await client.post(f"/api/files/{fid}/review", params={"action": "approve"})
        assert resp.status_code == 403

    async def test_invalid_action(self, auth_client):
        r = await _upload(auth_client, "a.txt", doc_key="inv1")
        fid = r.json()["files"][0]["id"]
        resp = await auth_client.post(f"/api/files/{fid}/review", params={"action": "bad"})
        assert resp.status_code == 400
