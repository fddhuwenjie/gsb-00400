from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models import FileRecord, TextChunk, DocumentVersion
from app.services import EmbeddingService
from app.services.versioning import get_published_version_map, get_group_map

router = APIRouter(prefix="/api/search", tags=["search"])
embedding_service = EmbeddingService()

@router.get("", summary="语义搜索", description="基于向量的语义检索，仅返回已审核通过的当前发布版本，结果包含命中的版本号；旧版本不被默认检索")
async def search(q: str, top_k: int = 10, db: AsyncSession = Depends(get_db)):
    results = embedding_service.search(q, top_k * 3)  # 多取一些用于去重

    # 按file_id去重，保留最高分
    seen = {}
    for r in results:
        fid = r["file_id"]
        if fid not in seen or r["score"] > seen[fid]["score"]:
            seen[fid] = r

    published = await get_published_version_map(db)  # {file_id: 当前发布版本}
    versioned_file_ids = set(
        (await db.execute(select(DocumentVersion.file_id))).scalars().all()
    )
    groups = await get_group_map(db)

    enriched = []
    for r in list(seen.values())[:top_k]:
        fid = r["file_id"]
        version = published.get(fid)
        if fid in versioned_file_ids:
            # 有版本的文件：仅当前发布版本（审核通过且为组内最新通过版本）可被检索
            if version is None:
                continue
        else:
            # 无版本的历史数据：沿用旧的审核状态
            file = await db.get(FileRecord, fid)
            if not file or file.review_status != "approved":
                continue

        file = await db.get(FileRecord, fid)
        if not file:
            continue
        group = groups.get(version.group_id) if version else None
        enriched.append({
            "file_id": fid,
            "filename": file.original_name,
            "standard_name": file.standard_name,
            "bucket": file.bucket,
            "score": r["score"],
            "doc_key": group.doc_key if group else None,
            "version_no": version.version_no if version else None
        })
    return {"query": q, "results": enriched}
