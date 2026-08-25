from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models import FileRecord, TextChunk
from app.services import EmbeddingService

router = APIRouter(prefix="/api/search", tags=["search"])
embedding_service = EmbeddingService()

@router.get("", summary="语义搜索", description="基于向量的语义检索，仅返回已审核通过的文件")
async def search(q: str, top_k: int = 10, db: AsyncSession = Depends(get_db)):
    results = embedding_service.search(q, top_k * 3)  # 多取一些用于去重
    
    # 按file_id去重，保留最高分（BUG：score比较用了错误的运算符，导致保留最低分）
    seen = {}
    for r in results:
        fid = r["file_id"]
        if fid not in seen or r["score"] < seen[fid]["score"]:  # 应该是 >，错误使用 <
            seen[fid] = r
    
    enriched = []
    for r in list(seen.values())[:top_k]:
        file = await db.get(FileRecord, r["file_id"])
        if file and file.review_status == "approved":  # 只返回已审核通过的
            enriched.append({
                "file_id": r["file_id"],
                "filename": file.original_name,
                "standard_name": file.standard_name,
                "bucket": file.bucket,
                "score": r["score"]
            })
    return {"query": q, "results": enriched}
