from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Dict

from app.models import DocumentGroup, DocumentVersion


async def get_or_create_group(db: AsyncSession, doc_key: str, title: str, bucket: str = None) -> DocumentGroup:
    """按文档标识获取分组，不存在则创建"""
    result = await db.execute(select(DocumentGroup).where(DocumentGroup.doc_key == doc_key))
    group = result.scalar_one_or_none()
    if group is None:
        group = DocumentGroup(doc_key=doc_key, title=title, bucket=bucket)
        db.add(group)
        await db.flush()
    elif bucket and not group.bucket:
        group.bucket = bucket
        await db.flush()
    return group


async def next_version_no(db: AsyncSession, group_id: int) -> int:
    """组内下一个版本号"""
    result = await db.execute(
        select(DocumentVersion.version_no)
        .where(DocumentVersion.group_id == group_id)
        .order_by(DocumentVersion.version_no.desc())
        .limit(1)
    )
    latest = result.scalar_one_or_none()
    return (latest or 0) + 1


async def get_published_version_map(db: AsyncSession) -> Dict[int, DocumentVersion]:
    """返回 {file_id: DocumentVersion}：每个文档组中版本号最大的已通过版本（即当前发布版本）"""
    result = await db.execute(
        select(DocumentVersion).where(DocumentVersion.review_status == "approved")
    )
    best: Dict[int, DocumentVersion] = {}
    for v in result.scalars().all():
        cur = best.get(v.group_id)
        if cur is None or v.version_no > cur.version_no:
            best[v.group_id] = v
    return {v.file_id: v for v in best.values()}


async def get_group_map(db: AsyncSession) -> Dict[int, DocumentGroup]:
    """返回 {group_id: DocumentGroup}"""
    result = await db.execute(select(DocumentGroup))
    return {g.id: g for g in result.scalars().all()}
