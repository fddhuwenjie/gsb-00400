import io
import os
from pathlib import Path

import app.routers.search as search_mod


async def _upload(client, filename, content=b"test content", **params):
    return await client.post(
        "/api/files/upload",
        params=params,
        files={"files": (filename, io.BytesIO(content), "text/plain")}
    )


async def _process_pending(client):
    """在请求内同步完成文件解析（测试覆盖 get_db 使用独立内存引擎，后台线程的写入对测试库不可见）"""
    resp = await client.post("/api/files/process-pending")
    assert resp.status_code == 200
    items = (await client.get("/api/files/list")).json()["files"]
    assert all(i["status"] == "completed" for i in items), [i["status"] for i in items]
    return items


class TestVersionUpload:
    async def test_same_document_creates_versions(self, auth_client):
        r1 = await _upload(auth_client, "产品A-解决方案-v1-2023.txt", b"v1 content", change_note="首次发布")
        r2 = await _upload(auth_client, "产品A-解决方案-v2-2024.txt", b"v2 content", change_note="更新架构章节")
        assert r1.status_code == 200 and r2.status_code == 200
        f1, f2 = r1.json()["files"][0], r2.json()["files"][0]

        # 同一业务文档归并，版本号递增
        assert f1["document_id"] == f2["document_id"]
        assert f1["version_number"] == 1
        assert f2["version_number"] == 2
        assert f1["is_new_document"] is True
        assert f2["is_new_document"] is False

    async def test_physical_files_not_overwritten(self, auth_client):
        await _upload(auth_client, "spec.txt", b"old content", change_note="v1")
        await _upload(auth_client, "spec.txt", b"new content", change_note="v2")
        upload_root = Path(os.environ["UPLOAD_DIR"])
        files = list(upload_root.rglob("spec.txt"))
        assert len(files) == 2
        contents = sorted(f.read_bytes() for f in files)
        assert contents == [b"new content", b"old content"]

    async def test_different_documents_not_grouped(self, auth_client):
        r1 = await _upload(auth_client, "产品A-解决方案-v1.txt")
        r2 = await _upload(auth_client, "产品B-彩页-v1.txt")
        assert r1.json()["files"][0]["document_id"] != r2.json()["files"][0]["document_id"]

    async def test_upload_records_uploader_and_note(self, auth_client):
        resp = await _upload(auth_client, "产品A-方案-v1.txt", b"x", change_note="修正错别字")
        info = resp.json()["files"][0]
        detail = await auth_client.get(f"/api/documents/{info['document_id']}")
        assert detail.status_code == 200
        versions = detail.json()["versions"]
        assert versions[0]["change_note"] == "修正错别字"
        assert versions[0]["uploaded_by"] == "admin"
        assert versions[0]["upload_date"] is not None


class TestDocumentEndpoints:
    async def test_document_list(self, auth_client):
        await _upload(auth_client, "产品A-方案-v1.txt")
        await _upload(auth_client, "产品A-方案-v2.txt")
        resp = await auth_client.get("/api/documents")
        assert resp.status_code == 200
        docs = resp.json()["documents"]
        assert len(docs) == 1
        doc = docs[0]
        assert doc["current_version"] == 2
        assert doc["version_count"] == 2
        assert doc["published_version"] is None  # 尚未审核

    async def test_document_detail_versions_ordered(self, auth_client):
        r = await _upload(auth_client, "spec-v1.txt")
        doc_id = r.json()["files"][0]["document_id"]
        await _upload(auth_client, "spec-v2.txt")
        resp = await auth_client.get(f"/api/documents/{doc_id}")
        versions = resp.json()["versions"]
        assert [v["version_number"] for v in versions] == [2, 1]  # 倒序

    async def test_document_detail_404(self, auth_client):
        resp = await auth_client.get("/api/documents/9999")
        assert resp.status_code == 404

    async def test_document_list_status_filter(self, auth_client):
        r1 = await _upload(auth_client, "产品A-方案-v1.txt")
        v1 = r1.json()["files"][0]
        await _upload(auth_client, "产品B-彩页-v1.txt")
        await _process_pending(auth_client)

        # 全部未发布：published 过滤为空，pending 过滤为全部
        assert len((await auth_client.get("/api/documents", params={"status": "published"})).json()["documents"]) == 0
        pending_docs = (await auth_client.get("/api/documents", params={"status": "pending"})).json()["documents"]
        assert len(pending_docs) == 2

        # v1 发布后：published 过滤只含文档 A
        await auth_client.post(f"/api/files/{v1['id']}/review", params={"action": "approve"})
        published_docs = (await auth_client.get("/api/documents", params={"status": "published"})).json()["documents"]
        assert len(published_docs) == 1
        assert published_docs[0]["id"] == v1["document_id"]

    async def test_document_list_bucket_filter(self, auth_client):
        await _upload(auth_client, "产品A-方案-v1.txt")
        resp = await auth_client.get("/api/documents", params={"bucket": "彩页"})
        assert resp.json()["documents"] == []
        resp = await auth_client.get("/api/documents", params={"bucket": "方案"})
        assert len(resp.json()["documents"]) == 1

    async def test_file_list_contains_version_fields(self, auth_client):
        await _upload(auth_client, "spec-v1.txt", change_note="初版")
        resp = await auth_client.get("/api/files/list")
        item = resp.json()["files"][0]
        assert item["version_number"] == 1
        assert item["document_id"] is not None
        assert item["is_published"] is False
        assert item["change_note"] == "初版"


class TestReviewPublish:
    async def test_approve_publishes_version(self, auth_client):
        r1 = await _upload(auth_client, "spec-v1.txt")
        v1 = r1.json()["files"][0]
        resp = await auth_client.post(f"/api/files/{v1['id']}/review", params={"action": "approve"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["is_published"] is True

        detail = await auth_client.get(f"/api/documents/{v1['document_id']}")
        doc = detail.json()["document"]
        assert doc["published_version"] == 1

    async def test_approve_new_version_supersedes_old(self, auth_client):
        r1 = await _upload(auth_client, "spec-v1.txt", b"v1")
        r2 = await _upload(auth_client, "spec-v2.txt", b"v2")
        v1, v2 = r1.json()["files"][0], r2.json()["files"][0]

        await auth_client.post(f"/api/files/{v1['id']}/review", params={"action": "approve"})
        await auth_client.post(f"/api/files/{v2['id']}/review", params={"action": "approve"})

        detail = (await auth_client.get(f"/api/documents/{v1['document_id']}")).json()
        doc = detail["document"]
        versions = {v["version_number"]: v for v in detail["versions"]}
        assert doc["published_version"] == 2
        assert versions[2]["is_published"] is True
        assert versions[1]["is_published"] is False  # 旧版本取消发布但仍保留

    async def test_reject_does_not_publish(self, auth_client):
        r1 = await _upload(auth_client, "spec-v1.txt")
        v1 = r1.json()["files"][0]
        resp = await auth_client.post(
            f"/api/files/{v1['id']}/review",
            params={"action": "reject", "comment": "内容过期，退回修改"}
        )
        assert resp.status_code == 200
        assert resp.json()["is_published"] is False

        detail = (await auth_client.get(f"/api/files/{v1['id']}")).json()
        assert detail["file"]["review_status"] == "rejected"
        assert detail["file"]["review_comment"] == "内容过期，退回修改"

    async def test_old_version_still_viewable(self, auth_client):
        r1 = await _upload(auth_client, "spec-v1.txt")
        r2 = await _upload(auth_client, "spec-v2.txt")
        v1, v2 = r1.json()["files"][0], r2.json()["files"][0]
        await auth_client.post(f"/api/files/{v2['id']}/review", params={"action": "approve"})

        # 旧版本详情页仍可查看，并能看到全部版本
        resp = await auth_client.get(f"/api/files/{v1['id']}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["file"]["version_number"] == 1
        assert body["file"]["is_published"] is False
        assert {v["version_number"] for v in body["versions"]} == {1, 2}

    async def test_reject_without_comment_rejected(self, auth_client):
        r1 = await _upload(auth_client, "spec-v1.txt")
        v1 = r1.json()["files"][0]
        resp = await auth_client.post(
            f"/api/files/{v1['id']}/review", params={"action": "reject"}
        )
        assert resp.status_code == 400
        # 未被误改状态
        detail = (await auth_client.get(f"/api/files/{v1['id']}")).json()
        assert detail["file"]["review_status"] == "pending"

    async def test_review_invalid_action(self, auth_client):
        r1 = await _upload(auth_client, "spec-v1.txt")
        v1 = r1.json()["files"][0]
        resp = await auth_client.post(f"/api/files/{v1['id']}/review", params={"action": "bogus"})
        assert resp.status_code == 400

    async def test_review_missing_file_404(self, auth_client):
        resp = await auth_client.post("/api/files/9999/review", params={"action": "approve"})
        assert resp.status_code == 404


class TestSearchVersionFilter:
    async def test_search_only_returns_published_version(self, auth_client, monkeypatch):
        r1 = await _upload(auth_client, "产品A-解决方案-v1.txt", b"v1")
        r2 = await _upload(auth_client, "产品A-解决方案-v2.txt", b"v2")
        v1, v2 = r1.json()["files"][0], r2.json()["files"][0]

        # 模拟向量库命中：两个版本及 v2 的多个 chunk 都被命中
        monkeypatch.setattr(search_mod.embedding_service, "search", lambda q, top_k=10: [
            {"file_id": v1["id"], "chunk_index": 0, "score": 0.70},
            {"file_id": v2["id"], "chunk_index": 0, "score": 0.80},
            {"file_id": v2["id"], "chunk_index": 1, "score": 0.95},
        ])

        # 未审核：搜索结果为空
        resp = await auth_client.get("/api/search", params={"q": "方案"})
        assert resp.json()["results"] == []

        # 仅 v1 通过：返回 v1
        await auth_client.post(f"/api/files/{v1['id']}/review", params={"action": "approve"})
        resp = await auth_client.get("/api/search", params={"q": "方案"})
        results = resp.json()["results"]
        assert len(results) == 1
        assert results[0]["version_number"] == 1
        assert results[0]["document_id"] == v1["document_id"]

        # v2 通过后：旧版本 v1 不再被检索，同文档去重且保留最高分
        await auth_client.post(f"/api/files/{v2['id']}/review", params={"action": "approve"})
        resp = await auth_client.get("/api/search", params={"q": "方案"})
        results = resp.json()["results"]
        assert len(results) == 1
        assert results[0]["file_id"] == v2["id"]
        assert results[0]["version_number"] == 2
        assert results[0]["score"] == 0.95  # 同文件多 chunk 保留最高分


class TestVersionStats:
    async def test_overview_counts(self, auth_client):
        r1 = await _upload(auth_client, "产品A-解决方案-v1.txt", b"v1")
        r2 = await _upload(auth_client, "产品A-解决方案-v2.txt", b"v2")
        v2 = r2.json()["files"][0]
        await auth_client.post(f"/api/files/{v2['id']}/review", params={"action": "approve"})

        resp = await auth_client.get("/api/stats/overview")
        data = resp.json()
        assert data["total_documents"] == 1
        assert data["total_versions"] == 2
        assert data["published"] == 1
        assert data["approved"] == 1
        # 分类统计只包含已发布版本
        assert data["by_bucket"] == {"方案": 1}

    async def test_unpublished_not_in_bucket_stats(self, auth_client):
        await _upload(auth_client, "产品A-解决方案-v1.txt")
        data = (await auth_client.get("/api/stats/overview")).json()
        assert data["by_bucket"] == {}

    async def test_tags_endpoint_available(self, auth_client):
        r1 = await _upload(auth_client, "产品A-解决方案-v1.txt")
        v1 = r1.json()["files"][0]
        await auth_client.post(f"/api/files/{v1['id']}/review", params={"action": "approve"})
        resp = await auth_client.get("/api/stats/tags")
        assert resp.status_code == 200
        assert "tags" in resp.json()
