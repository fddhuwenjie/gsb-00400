import pytest
import io
import os
from sqlalchemy import select, update

from app.models import FileRecord, DocumentVersion, User
from app.routers import search as search_module
from app.routers.auth import pwd_context


async def upload(client, filename="方案文档.txt", content=b"v1 content", doc_key="doc-A", note=None):
    data = {"doc_key": doc_key}
    if note:
        data["change_note"] = note
    resp = await client.post(
        "/api/files/upload",
        files={"files": (filename, io.BytesIO(content), "text/plain")},
        data=data
    )
    assert resp.status_code == 200
    return resp.json()["files"][0]


@pytest.fixture
def mock_embedding(monkeypatch):
    """替换向量检索，返回预设结果"""
    state = {"results": []}

    def fake_search(query, top_k=10):
        return state["results"][:top_k]

    monkeypatch.setattr(search_module.embedding_service, "search", fake_search)
    return state


class TestVersionedUpload:
    async def test_same_doc_key_creates_versions_without_overwrite(self, auth_client, db_session):
        f1 = await upload(auth_client, content=b"first version", note="初始版本")
        f2 = await upload(auth_client, content=b"second version", note="修订内容")

        assert f1["doc_key"] == "doc-A"
        assert f1["version_no"] == 1
        assert f2["version_no"] == 2

        # 旧文件未被覆盖：路径不同且内容各自保留
        r1 = await db_session.get(FileRecord, f1["id"])
        r2 = await db_session.get(FileRecord, f2["id"])
        assert r1.original_path != r2.original_path
        with open(r1.original_path, "rb") as fp:
            assert fp.read() == b"first version"
        with open(r2.original_path, "rb") as fp:
            assert fp.read() == b"second version"

    async def test_upload_records_uploader_and_change_note(self, auth_client):
        await upload(auth_client, note="初始版本")
        resp = await auth_client.get("/api/docs/doc-A/versions")
        assert resp.status_code == 200
        versions = resp.json()["versions"]
        assert len(versions) == 1
        v = versions[0]
        assert v["version_no"] == 1
        assert v["change_note"] == "初始版本"
        assert v["uploaded_by"] == "admin"
        assert v["uploaded_at"] is not None
        assert v["review_status"] == "pending"

    async def test_default_doc_key_from_filename(self, auth_client):
        resp = await auth_client.post(
            "/api/files/upload",
            files={"files": ("产品手册.txt", io.BytesIO(b"content"), "text/plain")}
        )
        assert resp.status_code == 200
        assert resp.json()["files"][0]["doc_key"] == "产品手册"


class TestDocGroupsAndVersions:
    async def test_doc_groups_list(self, auth_client):
        await upload(auth_client, doc_key="doc-A")
        await upload(auth_client, doc_key="doc-A")
        await upload(auth_client, filename="其他.txt", doc_key="doc-B")

        resp = await auth_client.get("/api/docs")
        assert resp.status_code == 200
        groups = {g["doc_key"]: g for g in resp.json()["groups"]}
        assert groups["doc-A"]["version_count"] == 2
        assert groups["doc-A"]["latest_version_no"] == 2
        assert groups["doc-A"]["published_version_no"] is None
        assert groups["doc-B"]["version_count"] == 1

    async def test_versions_list_order_desc(self, auth_client):
        await upload(auth_client, note="v1")
        await upload(auth_client, note="v2")
        resp = await auth_client.get("/api/docs/doc-A/versions")
        versions = resp.json()["versions"]
        assert [v["version_no"] for v in versions] == [2, 1]

    async def test_versions_of_unknown_doc_key_404(self, auth_client):
        resp = await auth_client.get("/api/docs/no-such-doc/versions")
        assert resp.status_code == 404

    async def test_version_detail(self, auth_client):
        f = await upload(auth_client, note="初始版本")
        vid = (await auth_client.get("/api/docs/doc-A/versions")).json()["versions"][0]["id"]
        resp = await auth_client.get(f"/api/versions/{vid}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["doc_key"] == "doc-A"
        assert data["version_no"] == 1
        assert data["change_note"] == "初始版本"
        assert data["is_published"] is False

    async def test_version_detail_404(self, auth_client):
        resp = await auth_client.get("/api/versions/999")
        assert resp.status_code == 404


class TestVersionReview:
    async def test_approve_marks_published(self, auth_client):
        await upload(auth_client)
        vid = (await auth_client.get("/api/docs/doc-A/versions")).json()["versions"][0]["id"]
        resp = await auth_client.post(f"/api/versions/{vid}/review", params={"action": "approve"})
        assert resp.status_code == 200
        assert resp.json()["review_status"] == "approved"
        assert resp.json()["is_published"] is True

        detail = (await auth_client.get(f"/api/versions/{vid}")).json()
        assert detail["review_status"] == "approved"
        assert detail["is_published"] is True

    async def test_reject_with_note(self, auth_client):
        await upload(auth_client)
        vid = (await auth_client.get("/api/docs/doc-A/versions")).json()["versions"][0]["id"]
        resp = await auth_client.post(
            f"/api/versions/{vid}/review", params={"action": "reject", "note": "内容过期"}
        )
        assert resp.status_code == 200
        detail = (await auth_client.get(f"/api/versions/{vid}")).json()
        assert detail["review_status"] == "rejected"
        assert detail["review_note"] == "内容过期"
        assert detail["is_published"] is False

    async def test_review_syncs_file_status(self, auth_client, db_session):
        f = await upload(auth_client)
        vid = (await auth_client.get("/api/docs/doc-A/versions")).json()["versions"][0]["id"]
        await auth_client.post(f"/api/versions/{vid}/review", params={"action": "approve"})
        file = await db_session.get(FileRecord, f["id"])
        assert file.review_status == "approved"

    async def test_review_invalid_action(self, auth_client):
        await upload(auth_client)
        vid = (await auth_client.get("/api/docs/doc-A/versions")).json()["versions"][0]["id"]
        resp = await auth_client.post(f"/api/versions/{vid}/review", params={"action": "invalid"})
        assert resp.status_code == 400

    async def test_review_not_found(self, auth_client):
        resp = await auth_client.post("/api/versions/999/review", params={"action": "approve"})
        assert resp.status_code == 404


class TestReviewPermissions:
    async def _create_version(self, auth_client):
        await upload(auth_client)
        return (await auth_client.get("/api/docs/doc-A/versions")).json()["versions"][0]["id"]

    async def test_anonymous_user_cannot_review(self, client, auth_client):
        """未登录用户审核应被拒绝（401）"""
        vid = await self._create_version(auth_client)
        client.headers.pop("Authorization", None)  # 确保匿名（auth_client 与 client 共享实例）
        resp = await client.post(f"/api/versions/{vid}/review", params={"action": "approve"})
        assert resp.status_code == 401
        # 状态未被修改
        detail = (await auth_client.get(f"/api/versions/{vid}")).json()
        assert detail["review_status"] == "pending"

    async def test_normal_user_cannot_review(self, client, auth_client, db_session):
        """普通用户（非管理员）审核应被拒绝（403）"""
        vid = await self._create_version(auth_client)
        db_session.add(User(username="viewer", hashed_password=pwd_context.hash("viewer123"), role="user"))
        await db_session.commit()
        login = await client.post("/api/auth/login", data={"username": "viewer", "password": "viewer123"})
        assert login.status_code == 200
        token = login.json()["access_token"]

        for action in ["approve", "reject"]:
            resp = await client.post(
                f"/api/versions/{vid}/review",
                params={"action": action},
                headers={"Authorization": f"Bearer {token}"}
            )
            assert resp.status_code == 403
        detail = (await auth_client.get(f"/api/versions/{vid}")).json()
        assert detail["review_status"] == "pending"

    async def test_admin_can_review(self, client, auth_client):
        """管理员可以正常执行通过与退回"""
        vid = await self._create_version(auth_client)
        resp = await auth_client.post(f"/api/versions/{vid}/review", params={"action": "approve"})
        assert resp.status_code == 200
        assert resp.json()["review_status"] == "approved"


class TestSearchWithVersions:
    async def test_unapproved_version_not_searchable(self, auth_client, mock_embedding):
        f = await upload(auth_client)
        mock_embedding["results"] = [{"file_id": f["id"], "chunk_index": 0, "score": 0.9}]
        resp = await auth_client.get("/api/search", params={"q": "方案"})
        assert resp.json()["results"] == []

    async def test_search_returns_version_no(self, auth_client, mock_embedding):
        f = await upload(auth_client)
        vid = (await auth_client.get("/api/docs/doc-A/versions")).json()["versions"][0]["id"]
        await auth_client.post(f"/api/versions/{vid}/review", params={"action": "approve"})

        mock_embedding["results"] = [{"file_id": f["id"], "chunk_index": 0, "score": 0.9}]
        resp = await auth_client.get("/api/search", params={"q": "方案"})
        results = resp.json()["results"]
        assert len(results) == 1
        assert results[0]["doc_key"] == "doc-A"
        assert results[0]["version_no"] == 1

    async def test_old_approved_version_not_searchable_after_newer_approved(self, auth_client, mock_embedding):
        f1 = await upload(auth_client, content=b"first")
        f2 = await upload(auth_client, content=b"second")
        versions = (await auth_client.get("/api/docs/doc-A/versions")).json()["versions"]
        for v in versions:
            await auth_client.post(f"/api/versions/{v['id']}/review", params={"action": "approve"})

        mock_embedding["results"] = [
            {"file_id": f1["id"], "chunk_index": 0, "score": 0.95},
            {"file_id": f2["id"], "chunk_index": 0, "score": 0.8},
        ]
        resp = await auth_client.get("/api/search", params={"q": "方案"})
        results = resp.json()["results"]
        # 旧版本 v1 不再被默认检索，只命中最新的已通过版本 v2
        assert len(results) == 1
        assert results[0]["file_id"] == f2["id"]
        assert results[0]["version_no"] == 2

    async def test_old_version_still_searchable_when_newer_pending(self, auth_client, mock_embedding):
        f1 = await upload(auth_client, content=b"first")
        f2 = await upload(auth_client, content=b"second")
        versions = (await auth_client.get("/api/docs/doc-A/versions")).json()["versions"]
        v1 = next(v for v in versions if v["version_no"] == 1)
        await auth_client.post(f"/api/versions/{v1['id']}/review", params={"action": "approve"})

        mock_embedding["results"] = [
            {"file_id": f1["id"], "chunk_index": 0, "score": 0.9},
            {"file_id": f2["id"], "chunk_index": 0, "score": 0.95},
        ]
        resp = await auth_client.get("/api/search", params={"q": "方案"})
        results = resp.json()["results"]
        assert len(results) == 1
        assert results[0]["file_id"] == f1["id"]
        assert results[0]["version_no"] == 1

    async def test_search_keeps_highest_score_per_file(self, auth_client, mock_embedding):
        f = await upload(auth_client)
        vid = (await auth_client.get("/api/docs/doc-A/versions")).json()["versions"][0]["id"]
        await auth_client.post(f"/api/versions/{vid}/review", params={"action": "approve"})

        mock_embedding["results"] = [
            {"file_id": f["id"], "chunk_index": 0, "score": 0.5},
            {"file_id": f["id"], "chunk_index": 1, "score": 0.9},
        ]
        resp = await auth_client.get("/api/search", params={"q": "方案"})
        results = resp.json()["results"]
        assert len(results) == 1
        assert results[0]["score"] == 0.9

    async def test_valid_result_after_high_score_invalid_not_truncated(self, auth_client, mock_embedding):
        """高分无效结果（未审核/已退回/非当前发布版本）被排除后，后面的有效文档仍应进入 top_k"""
        invalid = await upload(auth_client, content=b"unpublished", doc_key="doc-X")
        valid = await upload(auth_client, content=b"published", doc_key="doc-Y")
        vid = (await auth_client.get("/api/docs/doc-Y/versions")).json()["versions"][0]["id"]
        await auth_client.post(f"/api/versions/{vid}/review", params={"action": "approve"})

        # 未发布版本分数更高，且 top_k=1：有效文档不得被提前截掉
        mock_embedding["results"] = [
            {"file_id": invalid["id"], "chunk_index": 0, "score": 0.99},
            {"file_id": valid["id"], "chunk_index": 0, "score": 0.5},
        ]
        resp = await auth_client.get("/api/search", params={"q": "方案", "top_k": 1})
        results = resp.json()["results"]
        assert len(results) == 1
        assert results[0]["file_id"] == valid["id"]
        assert results[0]["score"] == 0.5

    async def test_top_k_applies_to_valid_results_sorted_by_score(self, auth_client, mock_embedding):
        """top_k 截取发生在过滤之后，且按相关度排序"""
        files = []
        for i, key in enumerate(["doc-K1", "doc-K2", "doc-K3"]):
            f = await upload(auth_client, content=f"c{i}".encode(), doc_key=key)
            vid = (await auth_client.get(f"/api/docs/{key}/versions")).json()["versions"][0]["id"]
            await auth_client.post(f"/api/versions/{vid}/review", params={"action": "approve"})
            files.append(f)

        mock_embedding["results"] = [
            {"file_id": files[0]["id"], "chunk_index": 0, "score": 0.6},
            {"file_id": files[1]["id"], "chunk_index": 0, "score": 0.9},
            {"file_id": files[2]["id"], "chunk_index": 0, "score": 0.8},
        ]
        resp = await auth_client.get("/api/search", params={"q": "方案", "top_k": 2})
        results = resp.json()["results"]
        assert [r["file_id"] for r in results] == [files[1]["id"], files[2]["id"]]


class TestStatsWithVersions:
    async def _mark_completed(self, db_session, file_id):
        await db_session.execute(
            update(FileRecord).where(FileRecord.id == file_id).values(process_status="completed")
        )
        await db_session.commit()

    async def test_overview_counts_only_published(self, auth_client, db_session):
        f = await upload(auth_client)
        await self._mark_completed(db_session, f["id"])

        # 未审核：不进入统计，但计入待审核
        overview = (await auth_client.get("/api/stats/overview")).json()
        assert overview["total_files"] == 0
        assert overview["approved"] == 0
        assert overview["pending_review"] == 1

        # 审核通过后进入统计
        vid = (await auth_client.get("/api/docs/doc-A/versions")).json()["versions"][0]["id"]
        await auth_client.post(f"/api/versions/{vid}/review", params={"action": "approve"})
        overview = (await auth_client.get("/api/stats/overview")).json()
        assert overview["total_files"] == 1
        assert overview["approved"] == 1
        assert overview["completed"] == 1
        assert overview["pending_review"] == 0
        assert overview["by_bucket"] == {"方案": 1}

    async def test_old_version_excluded_from_stats(self, auth_client, db_session):
        f1 = await upload(auth_client, content=b"first")
        f2 = await upload(auth_client, content=b"second")
        await self._mark_completed(db_session, f1["id"])
        await self._mark_completed(db_session, f2["id"])
        versions = (await auth_client.get("/api/docs/doc-A/versions")).json()["versions"]
        for v in versions:
            await auth_client.post(f"/api/versions/{v['id']}/review", params={"action": "approve"})

        overview = (await auth_client.get("/api/stats/overview")).json()
        # 同一文档两个已通过版本，仅当前发布版本（v2）计入统计
        assert overview["total_files"] == 1
        assert overview["approved"] == 1
