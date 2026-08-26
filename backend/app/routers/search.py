from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models import FileRecord, TextChunk, Document
from app.services import EmbeddingService

router = APIRouter(prefix="/api/search", tags=["search"])
embedding_service = EmbeddingService()

@router.get("", summary="语义搜索", description="基于向量的语义检索，仅返回文档当前已审核通过的版本。不支持检索历史版本。")
async def search(
    request: Request,
    q: str,
    top_k: int = 10,
    db: AsyncSession = Depends(get_db)
):
    if "include_old_versions" in request.query_params:
        raise HTTPException(status_code=400, detail="include_old_versions 参数已移除，搜索仅返回当前发布版本")

    results = embedding_service.search(q, top_k * 5)

    seen = {}
    for r in results:
        fid = r["file_id"]
        if fid not in seen or r["score"] > seen[fid]["score"]:
            seen[fid] = r

    file_ids = list(seen.keys())
    if not file_ids:
        return {"query": q, "results": []}

    files_result = await db.execute(select(FileRecord).where(FileRecord.id.in_(file_ids)))
    files_map = {f.id: f for f in files_result.scalars().all()}

    doc_ids = list({f.document_id for f in files_map.values() if f.document_id})
    current_versions = {}
    if doc_ids:
        docs_result = await db.execute(select(Document).where(Document.id.in_(doc_ids)))
        for d in docs_result.scalars().all():
            if d.current_version_id:
                current_versions[d.id] = d.current_version_id

    enriched = []
    for fid, r in seen.items():
        file = files_map.get(fid)
        if not file or file.review_status != "approved":
            continue

        if file.document_id and current_versions.get(file.document_id) != file.id:
            continue

        enriched.append({
            "file_id": r["file_id"],
            "document_id": file.document_id,
            "version_number": file.version_number,
            "filename": file.original_name,
            "standard_name": file.standard_name,
            "bucket": file.bucket,
            "score": r["score"]
        })

    enriched.sort(key=lambda x: x["score"], reverse=True)
    return {"query": q, "results": enriched[:top_k]}
