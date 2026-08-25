from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_, and_
from app.database import get_db
from app.models import FileRecord, FileTag, FileRelation, DocumentGroup

router = APIRouter(prefix="/api/stats", tags=["stats"])


def _published_file_ids_subquery():
    """构造“已发布/有效”版本 file_id 的子查询。

    有效版本 = 属于某分组且是该组当前的已发布版本；或无分组但审核通过的历史记录。
    未审核、已退回、以及被新版本取代的历史旧版本都不计入统计。
    """
    published_group_versions = (
        select(DocumentGroup.published_version_id)
        .where(DocumentGroup.published_version_id.isnot(None))
    )
    return (
        select(FileRecord.id).where(
            or_(
                FileRecord.id.in_(published_group_versions),
                and_(FileRecord.group_id.is_(None), FileRecord.review_status == "approved"),
            )
        )
    )


@router.get("/overview", summary="数据总览", description="获取文档总数、处理状态、审核状态和分类统计。已入库与分类口径均以“已发布版本”为准。")
async def get_overview(db: AsyncSession = Depends(get_db)):
    total = await db.execute(select(func.count(FileRecord.id)))
    completed = await db.execute(select(func.count(FileRecord.id)).where(FileRecord.process_status == "completed"))
    pending = await db.execute(select(func.count(FileRecord.id)).where(FileRecord.review_status == "pending", FileRecord.process_status == "completed"))

    valid_ids = _published_file_ids_subquery().subquery()

    # 已入库 = 有效（已发布/审核通过）版本数
    approved_result = await db.execute(select(func.count()).select_from(valid_ids))
    approved = approved_result.scalar() or 0

    # 文档分组总数
    group_total = await db.execute(select(func.count(DocumentGroup.id)))

    # 按桶统计：仅统计已发布/审核通过的版本，避免未审核、已退回、历史旧版本混入
    buckets_result = await db.execute(
        select(FileRecord.bucket, func.count(FileRecord.id))
        .where(FileRecord.id.in_(select(valid_ids.c.id)))
        .group_by(FileRecord.bucket)
    )
    buckets = {row[0]: row[1] for row in buckets_result.fetchall()}

    return {
        "total_files": total.scalar() or 0,
        "total_groups": group_total.scalar() or 0,
        "completed": completed.scalar() or 0,
        "pending_review": pending.scalar() or 0,
        "approved": approved,
        "by_bucket": buckets
    }

@router.get("/tags", summary="标签统计", description="获取标签使用频率排行，仅统计已发布版本的标签，返回前50个标签")
async def get_tag_stats(db: AsyncSession = Depends(get_db)):
    valid_ids = _published_file_ids_subquery().subquery()
    result = await db.execute(
        select(FileTag.tag_name, FileTag.tag_value, func.count(FileTag.id))
        .where(FileTag.file_id.in_(select(valid_ids.c.id)))
        .group_by(FileTag.tag_name, FileTag.tag_value)
        .order_by(func.count(FileTag.id).desc())
        .limit(50)
    )
    tags = [{"name": row[0], "value": row[1], "count": row[2]} for row in result.fetchall()]
    return {"tags": tags}
