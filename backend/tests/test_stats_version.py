import pytest
from app.models import DocumentGroup, FileRecord, FileTag, TextChunk
from tests.conftest import TestSession


async def _seed_group_with_versions():
    """构造一个含三个版本的文档：v1 已通过(旧), v2 待审核, v3 已通过并发布。
    另外构造一个独立文档：只有一个已退回版本。
    返回相关 id。
    """
    async with TestSession() as s:
        group = DocumentGroup(doc_key="stats-doc", title="统计文档", bucket="方案")
        s.add(group)
        await s.commit()
        await s.refresh(group)

        v1 = FileRecord(group_id=group.id, version_no=1, original_name="a.txt",
                        bucket="方案", process_status="completed", review_status="approved")
        v2 = FileRecord(group_id=group.id, version_no=2, original_name="a.txt",
                        bucket="方案", process_status="completed", review_status="pending")
        v3 = FileRecord(group_id=group.id, version_no=3, original_name="a.txt",
                        bucket="方案", process_status="completed", review_status="approved")
        s.add_all([v1, v2, v3])
        await s.commit()
        await s.refresh(v1); await s.refresh(v2); await s.refresh(v3)

        # v3 为当前发布版本
        group.published_version_id = v3.id
        await s.commit()

        # 每个版本各挂一个标签、一段文本
        for v in (v1, v2, v3):
            s.add(FileTag(file_id=v.id, tag_type="basic", tag_name="主题", tag_value="产品方案"))
            s.add(TextChunk(file_id=v.id, chunk_index=0, content=f"版本{v.version_no}的正文内容"))

        # 另一个仅含被退回版本的分组（不应计入统计）
        g2 = DocumentGroup(doc_key="rejected-doc", title="被退回文档", bucket="彩页")
        s.add(g2)
        await s.commit()
        await s.refresh(g2)
        rej = FileRecord(group_id=g2.id, version_no=1, original_name="b.txt",
                         bucket="彩页", process_status="completed", review_status="rejected")
        s.add(rej)
        await s.commit()
        await s.refresh(rej)
        s.add(FileTag(file_id=rej.id, tag_type="basic", tag_name="主题", tag_value="彩页宣传"))
        await s.commit()

        return {"group_id": group.id, "v1": v1.id, "v2": v2.id, "v3": v3.id, "rej": rej.id}


class TestStatsPublishedOnly:
    async def test_overview_counts_published_only(self, auth_client):
        ids = await _seed_group_with_versions()
        resp = await auth_client.get("/api/stats/overview")
        data = resp.json()
        # 已入库仅计已发布版本：v3 一条（v1 旧版本、v2 待审、rej 退回均不计）
        assert data["approved"] == 1
        # 分类统计只含已发布版本，故“方案”=1，且不含“彩页”
        assert data["by_bucket"].get("方案") == 1
        assert "彩页" not in data["by_bucket"]

    async def test_tags_counts_published_only(self, auth_client):
        ids = await _seed_group_with_versions()
        resp = await auth_client.get("/api/stats/tags")
        tags = resp.json()["tags"]
        # 只有 v3 的标签计入：产品方案=1；退回/旧/待审版本的标签不混入
        product = [t for t in tags if t["value"] == "产品方案"]
        assert len(product) == 1
        assert product[0]["count"] == 1
        assert all(t["value"] != "彩页宣传" for t in tags)


class TestVersionDetail:
    async def test_open_old_version_detail(self, auth_client):
        ids = await _seed_group_with_versions()
        # 打开旧版本 v1 的详情：内容可查看，但标记为不进入默认检索
        resp = await auth_client.get(f"/api/files/versions/{ids['v1']}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["version"]["version_no"] == 1
        assert data["version"]["is_published"] is False
        assert data["version"]["searchable"] is False
        assert any("版本1" in c["content"] for c in data["chunks"])

    async def test_open_published_version_detail(self, auth_client):
        ids = await _seed_group_with_versions()
        resp = await auth_client.get(f"/api/files/versions/{ids['v3']}")
        data = resp.json()
        assert data["version"]["is_published"] is True
        assert data["version"]["searchable"] is True

    async def test_version_detail_not_found(self, auth_client):
        resp = await auth_client.get("/api/files/versions/999999")
        assert resp.status_code == 404
