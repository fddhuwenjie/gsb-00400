from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.database import get_db
from app.models import FileRecord, FileTag, FileRelation, DocumentVersion
from app.services.versioning import get_published_version_map

router = APIRouter(prefix="/api/stats", tags=["stats"])

@router.get("/overview", summary="数据总览", description="获取文件总数、处理状态、审核状态和分类统计；仅审核通过的当前发布版本计入统计")
async def get_overview(db: AsyncSession = Depends(get_db)):
    published = await get_published_version_map(db)  # {file_id: 当前发布版本}
    versioned_file_ids = set(
        (await db.execute(select(DocumentVersion.file_id))).scalars().all()
    )
    all_files = (await db.execute(select(FileRecord))).scalars().all()

    # 仅统计“已发布”的文件：当前发布版本对应的文件；无版本的历史数据沿用旧的审核状态
    visible = []
    for f in all_files:
        if f.id in published:
            visible.append(f)
        elif f.id not in versioned_file_ids and f.review_status == "approved":
            visible.append(f)

    total = len(visible)
    completed = sum(1 for f in visible if f.process_status == "completed")
    approved = total

    # 待审核：待审核版本（文件已处理完成）+ 无版本历史数据中待审核的文件
    pending_versions = (await db.execute(
        select(DocumentVersion).where(DocumentVersion.review_status == "pending")
    )).scalars().all()
    pending = 0
    for v in pending_versions:
        f = await db.get(FileRecord, v.file_id)
        if f and f.process_status == "completed":
            pending += 1
    pending += sum(
        1 for f in all_files
        if f.id not in versioned_file_ids and f.review_status == "pending" and f.process_status == "completed"
    )

    # 按桶统计（仅已发布文件）
    buckets = {}
    for f in visible:
        buckets[f.bucket] = buckets.get(f.bucket, 0) + 1

    return {
        "total_files": total,
        "completed": completed,
        "pending_review": pending,
        "approved": approved,
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
