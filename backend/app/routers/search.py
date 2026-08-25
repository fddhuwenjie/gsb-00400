from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models import FileRecord
from app.services import EmbeddingService

router = APIRouter(prefix="/api/search", tags=["search"])
embedding_service = EmbeddingService()

@router.get("", summary="语义搜索", description="基于向量的语义检索，仅返回审核通过且当前发布的版本；同一业务文档只返回最新发布版本，结果中携带命中的版本号")
async def search(q: str, top_k: int = 10, db: AsyncSession = Depends(get_db)):
    results = embedding_service.search(q, top_k * 5)  # 多取一些用于过滤和去重

    # 按 file_id 去重，保留最高分
    best_by_file = {}
    for r in results:
        fid = r["file_id"]
        if fid not in best_by_file or r["score"] > best_by_file[fid]["score"]:
            best_by_file[fid] = r

    enriched = []
    seen_documents = set()
    for r in sorted(best_by_file.values(), key=lambda x: x["score"], reverse=True):
        file = await db.get(FileRecord, r["file_id"])
        # 只有审核通过且当前发布的版本才能被检索；旧版本/退回版本/待审版本一律排除
        if not file or file.review_status != "approved" or not file.is_published:
            continue
        # 同一业务文档只返回当前发布版本
        if file.document_id and file.document_id in seen_documents:
            continue
        if file.document_id:
            seen_documents.add(file.document_id)
        enriched.append({
            "file_id": r["file_id"],
            "document_id": file.document_id,
            "version_number": file.version_number,
            "filename": file.original_name,
            "standard_name": file.standard_name,
            "bucket": file.bucket,
            "score": r["score"]
        })
        if len(enriched) >= top_k:
            break
    return {"query": q, "results": enriched}
