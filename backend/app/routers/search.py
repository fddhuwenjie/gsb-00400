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
    published = await get_published_version_map(db)  # {file_id: 当前发布版本}
    versioned_file_ids = set(
        (await db.execute(select(DocumentVersion.file_id))).scalars().all()
    )
    groups = await get_group_map(db)
    file_cache = {}

    async def get_file(fid: int):
        if fid not in file_cache:
            file_cache[fid] = await db.get(FileRecord, fid)
        return file_cache[fid]

    async def filter_valid(candidates):
        """先排除未审核、已退回和非当前发布版本，返回有效结果"""
        valid = []
        for r in candidates:
            fid = r["file_id"]
            version = published.get(fid)
            if fid in versioned_file_ids:
                # 有版本的文件：仅当前发布版本（审核通过且为组内最新通过版本）可被检索
                if version is None:
                    continue
            else:
                # 无版本的历史数据：沿用旧的审核状态
                file = await get_file(fid)
                if not file or file.review_status != "approved":
                    continue
            valid.append((r, version))
        return valid

    # 逐步放大向量取数范围：高分无效结果被排除后，继续取后面的候选，
    # 直到凑够 top_k 个有效结果或索引耗尽，避免有效文档被提前截掉
    seen = {}
    valid = []
    fetch_k = top_k * 3
    while True:
        results = embedding_service.search(q, fetch_k)
        # 按file_id去重，保留最高分
        for r in results:
            fid = r["file_id"]
            if fid not in seen or r["score"] > seen[fid]["score"]:
                seen[fid] = r

        valid = await filter_valid(seen.values())
        total = embedding_service.index.ntotal if embedding_service.index is not None else 0
        if len(valid) >= top_k or total == 0 or fetch_k >= total:
            break
        fetch_k = min(fetch_k * 2, total)

    enriched = []
    for r, version in valid:
        file = await get_file(r["file_id"])
        if not file:
            continue
        group = groups.get(version.group_id) if version else None
        enriched.append({
            "file_id": r["file_id"],
            "filename": file.original_name,
            "standard_name": file.standard_name,
            "bucket": file.bucket,
            "score": r["score"],
            "doc_key": group.doc_key if group else None,
            "version_no": version.version_no if version else None
        })

    # 过滤完成后再按相关度截取 top_k
    enriched.sort(key=lambda x: x["score"], reverse=True)
    return {"query": q, "results": enriched[:top_k]}
