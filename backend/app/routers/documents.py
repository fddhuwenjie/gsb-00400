from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, update
from typing import Optional, List
import logging
import re

from app.database import get_db
from app.models import Document, FileRecord, User, TextChunk, FileTag
from app.schemas import DocumentItem, DocumentDetail, VersionItem
from app.routers.auth import require_admin

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/documents", tags=["documents"])


def normalize_document_key(filename: str) -> str:
    name = filename
    name = re.sub(r'\.[^.]+$', '', name)
    name = re.sub(r'[_\-]?v\d+(\.\d+)*[_\-]?\d{4}.*$', '', name, flags=re.IGNORECASE)
    name = re.sub(r'[_\-]?\d{4}[_\-]?\d{0,2}.*$', '', name)
    name = re.sub(r'[\s_\-]+', '-', name).strip('-').lower()
    return name or "untitled"


async def _get_version_item(db: AsyncSession, file: FileRecord, current_version_id: Optional[int]) -> VersionItem:
    uploader_name = None
    reviewer_name = None
    if file.uploaded_by:
        uploader = await db.get(User, file.uploaded_by)
        uploader_name = uploader.username if uploader else None
    if file.reviewed_by:
        reviewer = await db.get(User, file.reviewed_by)
        reviewer_name = reviewer.username if reviewer else None
    return VersionItem(
        id=file.id,
        version_number=file.version_number,
        original_name=file.original_name,
        standard_name=file.standard_name,
        bucket=file.bucket,
        process_status=file.process_status,
        review_status=file.review_status,
        change_description=file.change_description,
        review_comment=file.review_comment,
        uploaded_by=file.uploaded_by,
        uploader_name=uploader_name,
        reviewer_name=reviewer_name,
        uploaded_at=file.upload_date or file.created_at,
        reviewed_at=file.reviewed_at,
        is_current=(file.id == current_version_id)
    )


@router.get("", summary="文档列表", description="获取所有业务文档及其版本概况")
async def list_documents(
    bucket: Optional[str] = None,
    review_status: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    query = select(Document).order_by(Document.updated_at.desc())
    result = await db.execute(query)
    documents = result.scalars().all()

    items = []
    for doc in documents:
        versions_result = await db.execute(
            select(FileRecord).where(FileRecord.document_id == doc.id).order_by(FileRecord.version_number.desc())
        )
        versions = versions_result.scalars().all()
        if not versions:
            continue

        latest = versions[0]
        if bucket and latest.bucket != bucket:
            continue

        current_version_num = None
        if doc.current_version_id:
            current = next((v for v in versions if v.id == doc.current_version_id), None)
            if current:
                current_version_num = current.version_number

        if review_status:
            if review_status == "approved" and not any(v.review_status == "approved" for v in versions):
                continue
            if review_status == "pending" and not any(v.review_status == "pending" for v in versions):
                continue
            if review_status == "rejected" and not any(v.review_status == "rejected" for v in versions):
                continue

        items.append(DocumentItem(
            id=doc.id,
            document_key=doc.document_key,
            title=doc.title or latest.standard_name or latest.original_name,
            current_version=current_version_num,
            latest_version=latest.version_number,
            version_count=len(versions),
            bucket=latest.bucket,
            created_at=doc.created_at,
            updated_at=doc.updated_at
        ))

    return {"documents": items, "total": len(items)}


@router.get("/{document_id}", summary="文档详情", description="获取指定业务文档的所有版本列表")
async def get_document(document_id: int, db: AsyncSession = Depends(get_db)):
    doc = await db.get(Document, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    versions_result = await db.execute(
        select(FileRecord).where(FileRecord.document_id == document_id).order_by(FileRecord.version_number.desc())
    )
    versions = versions_result.scalars().all()

    version_items = []
    for v in versions:
        version_items.append(await _get_version_item(db, v, doc.current_version_id))

    return DocumentDetail(
        id=doc.id,
        document_key=doc.document_key,
        title=doc.title or (versions[0].standard_name if versions else doc.document_key),
        current_version_id=doc.current_version_id,
        versions=version_items
    )


@router.get("/{document_id}/versions/{version_id}", summary="版本详情", description="获取指定版本的详细信息，包括标签和文本块")
async def get_version_detail(document_id: int, version_id: int, db: AsyncSession = Depends(get_db)):
    doc = await db.get(Document, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    file = await db.get(FileRecord, version_id)
    if not file or file.document_id != document_id:
        raise HTTPException(status_code=404, detail="Version not found")

    tags_result = await db.execute(select(FileTag).where(FileTag.file_id == version_id))
    tags = tags_result.scalars().all()

    chunks_result = await db.execute(
        select(TextChunk).where(TextChunk.file_id == version_id).order_by(TextChunk.chunk_index)
    )
    chunks = chunks_result.scalars().all()

    version_item = await _get_version_item(db, file, doc.current_version_id)

    return {
        "document": {"id": doc.id, "document_key": doc.document_key, "title": doc.title},
        "version": version_item,
        "file": {
            "id": file.id,
            "original_name": file.original_name,
            "standard_name": file.standard_name,
            "file_type": file.file_type,
            "file_size": file.file_size,
            "bucket": file.bucket,
            "summary": file.summary,
            "process_status": file.process_status,
        },
        "tags": [{"id": t.id, "type": t.tag_type, "name": t.tag_name, "value": t.tag_value} for t in tags],
        "chunks": [{"index": c.chunk_index, "content": c.content} for c in chunks],
        "all_versions": [
            await _get_version_item(db, v, doc.current_version_id)
            for v in (await db.execute(
                select(FileRecord).where(FileRecord.document_id == document_id).order_by(FileRecord.version_number.desc())
            )).scalars().all()
        ]
    }


@router.post("/{document_id}/versions/{version_id}/review", summary="审核版本", description="审核指定文档版本，通过后自动设为当前版本。需要管理员权限，退回时必须填写原因。")
async def review_version(
    document_id: int,
    version_id: int,
    action: str,
    comment: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    if action not in ["approve", "reject"]:
        raise HTTPException(status_code=400, detail="Invalid action. Use 'approve' or 'reject'")
    if action == "reject" and not (comment and comment.strip()):
        raise HTTPException(status_code=400, detail="退回时必须填写原因")

    doc = await db.get(Document, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    file = await db.get(FileRecord, version_id)
    if not file or file.document_id != document_id:
        raise HTTPException(status_code=404, detail="Version not found")

    from datetime import datetime
    now = datetime.utcnow()

    if action == "approve":
        await db.execute(
            update(FileRecord).where(FileRecord.id == version_id).values(
                review_status="approved",
                review_comment=comment,
                reviewed_by=current_user.id,
                reviewed_at=now
            )
        )
        doc.current_version_id = version_id
        if not doc.title:
            doc.title = file.standard_name or file.original_name
        logger.info(f"Version {version_id} of document {document_id} approved by {current_user.username}, set as current")
    else:
        await db.execute(
            update(FileRecord).where(FileRecord.id == version_id).values(
                review_status="rejected",
                review_comment=comment,
                reviewed_by=current_user.id,
                reviewed_at=now
            )
        )
        logger.info(f"Version {version_id} of document {document_id} rejected by {current_user.username}")

    await db.commit()
    return {"success": True, "action": action, "document_id": document_id, "version_id": version_id}


@router.post("/{document_id}/switch-version/{version_id}", summary="切换当前版本", description="将已审核通过的指定版本设为文档的当前检索版本。需要管理员权限。")
async def switch_version(
    document_id: int,
    version_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    doc = await db.get(Document, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    file = await db.get(FileRecord, version_id)
    if not file or file.document_id != document_id:
        raise HTTPException(status_code=404, detail="Version not found")

    if file.review_status != "approved":
        raise HTTPException(status_code=400, detail="Only approved versions can be set as current")

    doc.current_version_id = version_id
    await db.commit()
    return {"success": True, "current_version_id": version_id}
