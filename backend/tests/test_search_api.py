import io
import asyncio
from unittest.mock import patch


class TestSearchVersionIsolation:
    async def _upload(self, auth_client, filename, content, doc_key=None, change_desc=None):
        data = {}
        if doc_key:
            data["document_key"] = doc_key
        if change_desc:
            data["change_description"] = change_desc
        resp = await auth_client.post(
            "/api/files/upload",
            files={"files": (filename, io.BytesIO(content.encode()), "text/plain")},
            data=data
        )
        assert resp.status_code == 200
        await asyncio.sleep(0.5)
        return resp.json()["files"][0]

    async def _approve(self, auth_client, doc_id, version_id):
        resp = await auth_client.post(
            f"/api/documents/{doc_id}/versions/{version_id}/review",
            params={"action": "approve"}
        )
        assert resp.status_code == 200

    def _mock_search(self, file_ids_with_scores):
        """Create a mock search function returning specified file IDs and scores."""
        def _mock(query, top_k=10):
            return [
                {"file_id": fid, "chunk_index": 0, "score": score}
                for fid, score in file_ids_with_scores[:top_k]
            ]
        return _mock

    async def test_search_rejects_include_old_versions_true(self, auth_client):
        resp = await auth_client.get("/api/search", params={"q": "test", "include_old_versions": "true"})
        assert resp.status_code == 400
        assert "include_old_versions" in resp.json()["message"]

    async def test_search_rejects_include_old_versions_false(self, auth_client):
        resp = await auth_client.get("/api/search", params={"q": "test", "include_old_versions": "false"})
        assert resp.status_code == 400

    async def test_search_rejects_include_old_versions_empty(self, auth_client):
        resp = await auth_client.get("/api/search", params={"q": "test", "include_old_versions": ""})
        assert resp.status_code == 400

    async def test_normal_search_without_param_succeeds(self, auth_client):
        with patch("app.routers.search.embedding_service.search", return_value=[]):
            resp = await auth_client.get("/api/search", params={"q": "test"})
        assert resp.status_code == 200
        data = resp.json()
        assert "results" in data
        for r in data["results"]:
            assert "document_id" in r
            assert "version_number" in r

    async def test_search_filters_out_non_current_versions(self, auth_client):
        v1 = await self._upload(auth_client, "iso.txt", "v1 content", doc_key="iso-filter")
        await self._approve(auth_client, v1["document_id"], v1["id"])

        v2 = await self._upload(auth_client, "iso.txt", "v2 content", doc_key="iso-filter", change_desc="v2")
        await self._approve(auth_client, v2["document_id"], v2["id"])

        mock_results = [
            {"file_id": v1["id"], "chunk_index": 0, "score": 0.9},
            {"file_id": v2["id"], "chunk_index": 0, "score": 0.8},
        ]
        with patch("app.routers.search.embedding_service.search", return_value=mock_results):
            resp = await auth_client.get("/api/search", params={"q": "content", "top_k": 20})

        assert resp.status_code == 200
        results = resp.json()["results"]
        result_ids = {r["file_id"] for r in results}

        assert v2["id"] in result_ids
        assert v1["id"] not in result_ids

        for r in results:
            if r["document_id"] == v1["document_id"]:
                assert r["file_id"] == v2["id"]
                assert r["version_number"] == v2["version_number"]

    async def test_search_returns_version_number(self, auth_client):
        v1 = await self._upload(auth_client, "ver-num.txt", "version number test", doc_key="ver-num")
        await self._approve(auth_client, v1["document_id"], v1["id"])

        mock_results = [{"file_id": v1["id"], "chunk_index": 0, "score": 0.95}]
        with patch("app.routers.search.embedding_service.search", return_value=mock_results):
            resp = await auth_client.get("/api/search", params={"q": "test"})

        assert resp.status_code == 200
        results = resp.json()["results"]
        assert len(results) == 1
        assert results[0]["version_number"] == 1
        assert results[0]["document_id"] == v1["document_id"]

    async def test_old_version_accessible_via_detail(self, auth_client):
        v1 = await self._upload(auth_client, "detail-access.txt", "old version content", doc_key="detail-access")
        await self._approve(auth_client, v1["document_id"], v1["id"])

        v2 = await self._upload(auth_client, "detail-access.txt", "new version content", doc_key="detail-access", change_desc="v2")
        await self._approve(auth_client, v2["document_id"], v2["id"])

        doc_resp = await auth_client.get(f"/api/documents/{v1['document_id']}")
        assert doc_resp.status_code == 200
        versions = doc_resp.json()["versions"]
        assert len(versions) == 2

        old_detail = await auth_client.get(
            f"/api/documents/{v1['document_id']}/versions/{v1['id']}"
        )
        assert old_detail.status_code == 200
        assert old_detail.json()["version"]["id"] == v1["id"]

        file_detail = await auth_client.get(f"/api/files/{v1['id']}")
        assert file_detail.status_code == 200
        assert file_detail.json()["file"]["is_current"] is False
