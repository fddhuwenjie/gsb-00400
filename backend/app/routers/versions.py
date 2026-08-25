from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from typing import Optional
from datetime import datetime
import logging

from app.database import get_db
from app.models import DocumentGroup, DocumentVersion, FileRecord, FileTag, User
from app.routers.auth import get_current_user
from app.services.versioning import get_published_version_map

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["versions"])


async def _user_name_map(db: AsyncSession):
    result = await db.execute(select(User))
    return {u.id: u.username for u in result.scalars().all()}


@router.get("/docs", summary="文档分组列表", description="按文档标识列出所有业务文档及其版本概况")
async def list_doc_groups(db: AsyncSession = Depends(get_db)):
    groups_result = await db.execute(select(DocumentGroup).order_by(DocumentGroup.updated_at.desc()))
    groups = groups_result.scalars().all()
    published = await get_published_version_map(db)

    items = []
    for g in groups:
        versions_result = await db.execute(
            select(DocumentVersion).where(DocumentVersion.group_id == g.id).order_by(DocumentVersion.version_no)
        )
        versions = versions_result.scalars().all()
        latest = versions[-1] if versions else None
        pub_file_ids = {fid for fid, v in published.items() if v.group_id == g.id}
        published_no = published[next(iter(pub_file_ids))].version_no if pub_file_ids else None
        items.append({
            "doc_key": g.doc_key,
            "title": g.title,
            "bucket": g.bucket,
            "version_count": len(versions),
            "latest_version_no": latest.version_no if latest else 0,
            "published_version_no": published_no,
            "latest_review_status": latest.review_status if latest else "pending",
            "updated_at": g.updated_at
        })
    return {"groups": items}


@router.get("/docs/{doc_key}/versions", summary="文档版本列表", description="列出指定业务文档的全部版本，含版本号、上传人、上传时间、变更说明与审核状态")
async def list_versions(doc_key: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(DocumentGroup).where(DocumentGroup.doc_key == doc_key))
    group = result.scalar_one_or_none()
    if not group:
        raise HTTPException(status_code=404, detail="Document group not found")

    versions_result = await db.execute(
        select(DocumentVersion).where(DocumentVersion.group_id == group.id).order_by(DocumentVersion.version_no.desc())
    )
    versions = versions_result.scalars().all()
    published = await get_published_version_map(db)
    user_names = await _user_name_map(db)

    items = []
    for v in versions:
        file = await db.get(FileRecord, v.file_id)
        items.append({
            "id": v.id,
            "file_id": v.file_id,
            "version_no": v.version_no,
            "filename": file.original_name if file else "",
            "change_note": v.change_note,
            "uploaded_by": user_names.get(v.uploaded_by),
            "uploaded_at": v.uploaded_at,
            "review_status": v.review_status,
            "review_note": v.review_note,
            "reviewed_by": user_names.get(v.reviewed_by),
            "reviewed_at": v.reviewed_at,
            "is_published": v.file_id in published,
            "file_size": file.file_size if file else None,
            "status": file.process_status if file else "unknown"
        })
    return {"doc_key": group.doc_key, "title": group.title, "versions": items}


@router.get("/versions/{version_id}", summary="版本详情", description="查看指定版本的详细信息（含旧版本），包括标准名、摘要与标签")
async def get_version(version_id: int, db: AsyncSession = Depends(get_db)):
    version = await db.get(DocumentVersion, version_id)
    if not version:
        raise HTTPException(status_code=404, detail="Version not found")
    group = await db.get(DocumentGroup, version.group_id)
    file = await db.get(FileRecord, version.file_id)
    if not file:
        raise HTTPException(status_code=404, detail="File not found")

    tags_result = await db.execute(select(FileTag).where(FileTag.file_id == file.id))
    published = await get_published_version_map(db)
    user_names = await _user_name_map(db)

    return {
        "id": version.id,
        "file_id": file.id,
        "doc_key": group.doc_key if group else None,
        "version_no": version.version_no,
        "filename": file.original_name,
        "standard_name": file.standard_name,
        "bucket": file.bucket,
        "summary": file.summary,
        "change_note": version.change_note,
        "uploaded_by": user_names.get(version.uploaded_by),
        "uploaded_at": version.uploaded_at,
        "review_status": version.review_status,
        "review_note": version.review_note,
        "is_published": file.id in published,
        "tags": [{"tag_type": t.tag_type, "tag_name": t.tag_name, "tag_value": t.tag_value}
                 for t in tags_result.scalars().all()]
    }


@router.post("/versions/{version_id}/review", summary="审核文档版本", description="审核员（仅管理员）对指定版本选择通过(approve)或退回(reject)，可附退回原因；只有审核通过的版本进入搜索与统计")
async def review_version(
    version_id: int,
    action: str,
    note: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="仅管理员可执行审核操作")
    if action not in ["approve", "reject"]:
        raise HTTPException(status_code=400, detail="Invalid action")
    version = await db.get(DocumentVersion, version_id)
    if not version:
        raise HTTPException(status_code=404, detail="Version not found")

    new_status = "approved" if action == "approve" else "rejected"
    await db.execute(update(DocumentVersion).where(DocumentVersion.id == version_id).values(
        review_status=new_status,
        review_note=note if action == "reject" else None,
        reviewed_by=user.id if user else None,
        reviewed_at=datetime.utcnow()
    ))
    # 同步文件记录的审核状态，保持管理端文件列表一致
    await db.execute(update(FileRecord).where(FileRecord.id == version.file_id).values(
        review_status=new_status
    ))
    await db.commit()

    published = await get_published_version_map(db)
    return {"success": True, "review_status": new_status, "is_published": version.file_id in published}
