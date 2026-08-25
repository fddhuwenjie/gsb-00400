import pytest
import io


async def _upload(client, filename, doc_key, content=b"content"):
    return await client.post(
        "/api/files/upload",
        data={"doc_key": doc_key},
        files={"files": (filename, io.BytesIO(content), "text/plain")}
    )


class TestSearchVersionFilter:
    async def test_only_published_version_in_results(self, auth_client, monkeypatch):
        from app.routers import search as search_module

        r1 = await _upload(auth_client, "a.txt", doc_key="s-doc")
        r2 = await _upload(auth_client, "a.txt", doc_key="s-doc")
        v1_id = r1.json()["files"][0]["id"]
        v2_id = r2.json()["files"][0]["id"]

        # 审核通过 v2，使其成为发布版本
        await auth_client.post(f"/api/files/{v2_id}/review", params={"action": "approve"})

        # 向量层伪造：两个版本都“命中”，v1 分数更高
        def fake_search(query, top_k):
            return [
                {"file_id": v1_id, "chunk_index": 0, "score": 0.99},
                {"file_id": v2_id, "chunk_index": 0, "score": 0.80},
            ]
        monkeypatch.setattr(search_module.embedding_service, "search", fake_search)

        resp = await auth_client.get("/api/search", params={"q": "test"})
        results = resp.json()["results"]
        # 只有已发布的 v2 进入结果，即使旧版本 v1 分数更高
        assert len(results) == 1
        assert results[0]["file_id"] == v2_id
        assert results[0]["version_no"] == 2

    async def test_high_score_unpublished_does_not_block_valid_results(self, auth_client, monkeypatch):
        from app.routers import search as search_module

        # 文档A：未发布任何版本（高分但应被排除）
        ra = await _upload(auth_client, "a.txt", doc_key="s-A")
        a_id = ra.json()["files"][0]["id"]
        # 文档B：发布 v1
        rb = await _upload(auth_client, "b.txt", doc_key="s-B")
        b_id = rb.json()["files"][0]["id"]
        await auth_client.post(f"/api/files/{b_id}/review", params={"action": "approve"})

        def fake_search(query, top_k):
            return [
                {"file_id": a_id, "chunk_index": 0, "score": 0.99},
                {"file_id": b_id, "chunk_index": 0, "score": 0.50},
            ]
        monkeypatch.setattr(search_module.embedding_service, "search", fake_search)

        # top_k=1：先过滤无效再截取，确保仍能返回有效的 B
        resp = await auth_client.get("/api/search", params={"q": "test", "top_k": 1})
        results = resp.json()["results"]
        assert len(results) == 1
        assert results[0]["file_id"] == b_id

    async def test_rejected_version_excluded(self, auth_client, monkeypatch):
        from app.routers import search as search_module

        r = await _upload(auth_client, "a.txt", doc_key="s-rej")
        fid = r.json()["files"][0]["id"]
        await auth_client.post(f"/api/files/{fid}/review", params={"action": "reject"})

        def fake_search(query, top_k):
            return [{"file_id": fid, "chunk_index": 0, "score": 0.99}]
        monkeypatch.setattr(search_module.embedding_service, "search", fake_search)

        resp = await auth_client.get("/api/search", params={"q": "test"})
        assert resp.json()["results"] == []
