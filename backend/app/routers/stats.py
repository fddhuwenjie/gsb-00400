from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.database import get_db
from app.models import FileRecord, FileTag, FileRelation

router = APIRouter(prefix="/api/stats", tags=["stats"])

@router.get("/overview", summary="数据总览", description="获取文件总数、处理状态、审核状态和分类统计")
async def get_overview(db: AsyncSession = Depends(get_db)):
    total = await db.execute(select(func.count(FileRecord.id)))
    completed = await db.execute(select(func.count(FileRecord.id)).where(FileRecord.process_status == "completed"))
    pending = await db.execute(select(func.count(FileRecord.id)).where(FileRecord.review_status == "pending", FileRecord.process_status == "completed"))
    approved = await db.execute(select(func.count(FileRecord.id)).where(FileRecord.review_status == "approved"))
    
    # 按桶统计
    buckets_result = await db.execute(
        select(FileRecord.bucket, func.count(FileRecord.id))
        .group_by(FileRecord.bucket)
    )
    buckets = {row[0]: row[1] for row in buckets_result.fetchall()}
    
    return {
        "total_files": total.scalar() or 0,
        "completed": completed.scalar() or 0,
        "pending_review": pending.scalar() or 0,
        "approved": approved.scalar() or 0,
        "by_bucket": buckets
    }

@router.get("/tags", summary="标签统计", description="获取标签使用频率排行，返回前50个标签")
async def get_tag_stats(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(FileTag.tag_name, FileTag.tag_value, func.count(FileTag.id))
        .group_by(FileTag.tag_name, FileTag.tag_value)
        .order_by(func.count(FileTag.id).desc())
        .limit(50)
    )
    tags = [{"name": row[0], "value": row[1], "count": row[2]} for row in result.fetchall()]
    return {"tags": tags}
