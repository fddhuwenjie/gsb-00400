from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models import FileRecord, TextChunk, DocumentGroup
from app.services import EmbeddingService

router = APIRouter(prefix="/api/search", tags=["search"])
embedding_service = EmbeddingService()

async def _is_searchable(file: FileRecord, db: AsyncSession) -> bool:
    """判断某个版本是否可被默认检索。

    - 属于某文档分组的版本：必须是该组当前的“已发布版本”（审核通过并被设为发布）。
      这样旧版本即使命中向量索引也不会进入搜索结果。
    - 无分组的历史记录：沿用旧逻辑，审核通过即可检索。
    """
    if file.review_status != "approved":
        return False
    if file.group_id is None:
        return True
    group = await db.get(DocumentGroup, file.group_id)
    return bool(group and group.published_version_id == file.id)

@router.get("", summary="语义搜索", description="基于向量的语义检索，仅返回已审核通过并已发布的文档版本，结果附带命中的版本号")
async def search(q: str, top_k: int = 10, db: AsyncSession = Depends(get_db)):
    # 多取一些候选用于去重和有效性过滤
    results = embedding_service.search(q, top_k * 5)

    # 按 file_id 去重，保留最高分
    seen = {}
    for r in results:
        fid = r["file_id"]
        if fid not in seen or r["score"] > seen[fid]["score"]:
            seen[fid] = r

    # 先按分数排序，再逐条过滤出可检索版本，最后截取 top_k
    ordered = sorted(seen.values(), key=lambda x: x["score"], reverse=True)

    enriched = []
    for r in ordered:
        file = await db.get(FileRecord, r["file_id"])
        if file and await _is_searchable(file, db):
            enriched.append({
                "file_id": r["file_id"],
                "group_id": file.group_id,
                "filename": file.original_name,
                "standard_name": file.standard_name,
                "bucket": file.bucket,
                "version_no": file.version_no,
                "score": r["score"]
            })
        if len(enriched) >= top_k:
            break
    return {"query": q, "results": enriched}
