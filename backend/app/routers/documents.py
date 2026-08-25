from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional, List, Dict

from app.database import get_db
from app.models import Document, FileRecord, User

router = APIRouter(prefix="/api/documents", tags=["documents"])


def serialize_version(f: FileRecord, uploader_name: Optional[str]) -> Dict:
    """序列化单个版本（FileRecord）为对外字典"""
    return {
        "file_id": f.id,
        "document_id": f.document_id,
        "version_number": f.version_number or 1,
        "name": f.original_name,
        "standard_name": f.standard_name,
        "bucket": f.bucket,
        "file_type": f.file_type,
        "file_size": f.file_size,
        "status": f.process_status,
        "review_status": f.review_status,
        "is_published": bool(f.is_published),
        "uploaded_by": uploader_name,
        "upload_date": f.upload_date.isoformat() if f.upload_date else None,
        "change_note": f.change_note,
        "summary": f.summary,
        "review_comment": f.review_comment,
        "reviewed_at": f.reviewed_at.isoformat() if f.reviewed_at else None,
    }


async def uploader_name_map(db: AsyncSession, user_ids: List[Optional[int]]) -> Dict[int, str]:
    """批量查询上传人用户名"""
    ids = {uid for uid in user_ids if uid}
    if not ids:
        return {}
    result = await db.execute(select(User).where(User.id.in_(ids)))
    return {u.id: u.username for u in result.scalars().all()}


def serialize_document(doc: Document, versions: List[FileRecord]) -> Dict:
    """序列化逻辑文档（含版本聚合信息）"""
    published = next((v for v in versions if v.id == doc.published_version_id), None)
    return {
        "id": doc.id,
        "doc_key": doc.doc_key,
        "title": doc.title,
        "bucket": doc.bucket,
        "current_version": doc.current_version or 0,
        "published_version": published.version_number if published else None,
        "published_file_id": doc.published_version_id,
        "version_count": len(versions),
        "has_pending": any(
            v.review_status == "pending" and v.process_status == "completed" for v in versions
        ),
        "updated_at": doc.updated_at.isoformat() if doc.updated_at else None,
    }


@router.get("", summary="文档列表", description="获取业务文档列表，每个文档聚合其版本数、最新版本与已发布版本，支持按分类和审核状态筛选")
async def list_documents(
    bucket: Optional[str] = None,
    status: Optional[str] = None,  # published=已发布, pending=有待审核版本
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Document).order_by(Document.updated_at.desc()))
    docs = result.scalars().all()
    if not docs:
        return {"documents": []}

    vresult = await db.execute(
        select(FileRecord).where(FileRecord.document_id.in_([d.id for d in docs]))
    )
    versions_by_doc: Dict[int, List[FileRecord]] = {}
    for v in vresult.scalars().all():
        versions_by_doc.setdefault(v.document_id, []).append(v)

    items = []
    for d in docs:
        versions = versions_by_doc.get(d.id, [])
        item = serialize_document(d, versions)
        if bucket and item["bucket"] != bucket:
            continue
        if status == "published" and not item["published_version"]:
            continue
        if status == "pending" and not item["has_pending"]:
            continue
        items.append(item)
    return {"documents": items}


@router.get("/{document_id}", summary="文档详情", description="获取指定业务文档的信息及其全部版本（按版本号倒序），用于版本切换与审核")
async def get_document(document_id: int, db: AsyncSession = Depends(get_db)):
    doc = await db.get(Document, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    vresult = await db.execute(
        select(FileRecord)
        .where(FileRecord.document_id == doc.id)
        .order_by(FileRecord.version_number.desc())
    )
    versions = vresult.scalars().all()
    name_map = await uploader_name_map(db, [v.uploaded_by for v in versions])
    return {
        "document": serialize_document(doc, versions),
        "versions": [serialize_version(v, name_map.get(v.uploaded_by)) for v in versions]
    }
