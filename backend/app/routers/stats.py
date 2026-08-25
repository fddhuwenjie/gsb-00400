from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.database import get_db
from app.models import FileRecord, FileTag, Document

router = APIRouter(prefix="/api/stats", tags=["stats"])

@router.get("/overview", summary="数据总览", description="获取文档/版本总数、处理状态、审核状态和分类统计。分类统计仅包含审核通过并发布的版本")
async def get_overview(db: AsyncSession = Depends(get_db)):
    total_versions = (await db.execute(select(func.count(FileRecord.id)))).scalar() or 0
    total_documents = (await db.execute(select(func.count(Document.id)))).scalar() or 0
    completed = (await db.execute(
        select(func.count(FileRecord.id)).where(FileRecord.process_status == "completed")
    )).scalar() or 0
    pending = (await db.execute(
        select(func.count(FileRecord.id)).where(
            FileRecord.review_status == "pending", FileRecord.process_status == "completed"
        )
    )).scalar() or 0
    published_count = (await db.execute(
        select(func.count(FileRecord.id)).where(FileRecord.is_published == True)  # noqa: E712
    )).scalar() or 0

    # 按桶统计（仅已发布版本进入统计）
    buckets_result = await db.execute(
        select(FileRecord.bucket, func.count(FileRecord.id))
        .where(FileRecord.is_published == True)  # noqa: E712
        .group_by(FileRecord.bucket)
    )
    buckets = {row[0]: row[1] for row in buckets_result.fetchall()}

    return {
        "total_files": total_versions,  # 兼容旧字段：版本总数
        "total_documents": total_documents,
        "total_versions": total_versions,
        "completed": completed,
        "pending_review": pending,
        "approved": published_count,
        "published": published_count,
        "by_bucket": buckets
    }

@router.get("/tags", summary="标签统计", description="获取标签使用频率排行（仅统计已发布版本的标签），返回前50个标签")
async def get_tag_stats(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(FileTag.tag_name, FileTag.tag_value, func.count(FileTag.id))
        .join(FileRecord, FileTag.file_id == FileRecord.id)
        .where(FileRecord.is_published == True)  # noqa: E712
        .group_by(FileTag.tag_name, FileTag.tag_value)
        .order_by(func.count(FileTag.id).desc())
        .limit(50)
    )
    tags = [{"name": row[0], "value": row[1], "count": row[2]} for row in result.fetchall()]
    return {"tags": tags}
