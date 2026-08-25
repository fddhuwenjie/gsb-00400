from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, BackgroundTasks, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func
from typing import List, Optional
from pathlib import Path
from datetime import datetime
import aiofiles
import asyncio
import logging
import threading
import traceback
import os

from app.database import get_db, async_session
from app.models import FileRecord, FileTag, TextChunk, ProcessLog, DocumentGroup, User
from app.routers.auth import get_current_user, require_admin
from app.services import DocumentParser, VideoParser, EmbeddingService, TagGenerator

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/files", tags=["files"])


def _upload_root() -> Path:
    """上传根目录：默认 /data/uploads（容器内挂载），不可写时回退到本地目录。"""
    root = Path(os.environ.get("UPLOAD_DIR", "/data/uploads"))
    try:
        root.mkdir(parents=True, exist_ok=True)
    except OSError:
        root = Path(os.getcwd()) / "uploads"
        root.mkdir(parents=True, exist_ok=True)
    return root


doc_parser = DocumentParser()
video_parser = VideoParser()
embedding_service = EmbeddingService()
tag_generator = TagGenerator()

def run_in_thread(file_id: int, file_path: str, file_type: str):
    """在独立线程中运行文件处理"""
    def worker():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(process_file_async(file_id, file_path, file_type))
        except Exception as e:
            logger.error(f"Background task error for file {file_id}: {e}")
            logger.error(traceback.format_exc())
        finally:
            loop.close()
    
    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    logger.info(f"Started processing thread for file {file_id}")

@router.post("/upload", summary="批量上传文件（版本化）", description="上传一个或多个文件。相同 doc_key 的文档会创建新版本而不覆盖旧文件，并记录版本号、上传人、上传时间与变更说明。")
async def upload_files(
    files: List[UploadFile] = File(...),
    bucket: Optional[str] = Form(None),
    doc_key: Optional[str] = Form(None),
    change_note: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """批量上传文件。

    - 若提供 doc_key（业务文档标识），同一 doc_key 下的多次上传会创建递增的版本号，
      旧版本文件保留在磁盘（按版本号命名子目录），不会被覆盖。
    - 未提供 doc_key 时，为每个文件按其文件名生成独立的 doc_key，行为等同于新建文档的第 1 版。
    """
    upload_dir = _upload_root()
    results = []

    for file in files:
        content = await file.read()
        file_ext = Path(file.filename).suffix.lower().strip(".")
        suggested_bucket = bucket or tag_generator.suggest_bucket(file.filename, file_ext)

        # 确定业务文档标识：显式 doc_key 优先，否则以文件名作为标识
        key = doc_key or file.filename

        # 查找或创建文档分组
        group_result = await db.execute(select(DocumentGroup).where(DocumentGroup.doc_key == key))
        group = group_result.scalar_one_or_none()
        if group is None:
            group = DocumentGroup(doc_key=key, title=file.filename, bucket=suggested_bucket)
            db.add(group)
            await db.commit()
            await db.refresh(group)

        # 计算组内下一个版本号
        max_version = await db.execute(
            select(func.max(FileRecord.version_no)).where(FileRecord.group_id == group.id)
        )
        next_version = (max_version.scalar() or 0) + 1

        # 每个版本存到独立子目录，避免覆盖旧文件
        version_dir = upload_dir / f"group_{group.id}" / f"v{next_version}"
        version_dir.mkdir(parents=True, exist_ok=True)
        file_path = version_dir / file.filename
        async with aiofiles.open(file_path, "wb") as f:
            await f.write(content)

        record = FileRecord(
            group_id=group.id,
            version_no=next_version,
            change_note=change_note,
            uploaded_by=user.id,
            original_path=str(file_path),
            original_name=file.filename,
            file_type=file_ext,
            file_size=len(content),
            bucket=suggested_bucket,
            process_status="pending"
        )
        db.add(record)
        await db.commit()
        await db.refresh(record)

        # 在独立线程中处理文件
        run_in_thread(record.id, str(file_path), file_ext)
        results.append({
            "id": record.id,
            "filename": file.filename,
            "bucket": suggested_bucket,
            "doc_key": key,
            "group_id": group.id,
            "version_no": next_version
        })

    return {"uploaded": len(results), "files": results}

async def process_file_async(file_id: int, file_path: str, file_type: str):
    """后台处理文件（异步版本）"""
    logger.info(f"Starting async processing for file {file_id}: {file_path}")
    async with async_session() as db:
        await db.execute(update(FileRecord).where(FileRecord.id == file_id).values(process_status="processing"))
        await db.commit()
        
        try:
            # 解析文件
            logger.info(f"Parsing file {file_id} of type {file_type}")
            if file_type in ["pdf"]:
                result = await doc_parser.parse_pdf(file_path)
            elif file_type in ["docx"]:
                result = await doc_parser.parse_docx(file_path)
            elif file_type in ["pptx"]:
                result = await doc_parser.parse_pptx(file_path)
            elif file_type in ["txt", "md"]:
                result = await doc_parser.parse_txt(file_path)
            elif file_type in ["mp4", "avi", "mov"]:
                result = await video_parser.transcribe(file_path)
            else:
                result = {"chunks": [], "metadata": {"type": "archive"}}
            
            logger.info(f"Parse result for file {file_id}: {len(result.get('chunks', []))} chunks")
            
            if "error" in result:
                raise Exception(result["error"])
            
            chunks = result.get("chunks", [])
            content = " ".join([c["content"] for c in chunks[:10]])
            
            # 生成标签
            record = await db.get(FileRecord, file_id)
            tags = tag_generator.generate_tags(record.original_name, content, file_type)
            standard_name = tag_generator.generate_standard_name(record.original_name, content, record.bucket, tags)
            logger.info(f"Generated standard name for file {file_id}: {standard_name}")

            # 保存标签
            for tag in tags:
                db.add(FileTag(file_id=file_id, tag_type=tag["type"], tag_name=tag["name"], tag_value=tag["value"]))
            
            # 保存文本块并添加到向量索引
            chunk_data = []
            for i, chunk in enumerate(chunks):
                db.add(TextChunk(file_id=file_id, chunk_index=i, content=chunk["content"]))
                chunk_data.append({"index": i, "content": chunk["content"]})
            
            # 添加到向量索引
            if chunk_data:
                logger.info(f"Adding {len(chunk_data)} chunks to vector index for file {file_id}")
                embedding_service.add_chunks(file_id, chunk_data)
            
            await db.execute(update(FileRecord).where(FileRecord.id == file_id).values(
                process_status="completed", standard_name=standard_name, summary=content[:500]
            ))
            db.add(ProcessLog(file_id=file_id, action="process", status="success"))
            await db.commit()
            logger.info(f"File {file_id} processed successfully with {len(chunks)} chunks")
        except Exception as e:
            logger.error(f"File {file_id} processing failed: {e}")
            logger.error(traceback.format_exc())
            await db.execute(update(FileRecord).where(FileRecord.id == file_id).values(process_status="failed"))
            db.add(ProcessLog(file_id=file_id, action="process", status="failed", message=str(e)))
            await db.commit()

@router.get("/list", summary="文件列表", description="获取文件列表，支持按分类和状态筛选。默认只返回每个文档的最新版本。")
async def list_files(
    bucket: Optional[str] = None,
    status: Optional[str] = None,
    all_versions: bool = False,
    db: AsyncSession = Depends(get_db)
):
    query = select(FileRecord)
    if bucket:
        query = query.where(FileRecord.bucket == bucket)
    if status:
        query = query.where(FileRecord.process_status == status)
    result = await db.execute(query.order_by(FileRecord.created_at.desc()))
    files = result.scalars().all()

    if not all_versions:
        # 每个 group 仅保留版本号最高的一条；无 group 的记录（历史数据）原样保留
        latest = {}
        singles = []
        for f in files:
            if f.group_id is None:
                singles.append(f)
                continue
            cur = latest.get(f.group_id)
            if cur is None or (f.version_no or 0) > (cur.version_no or 0):
                latest[f.group_id] = f
        files = list(latest.values()) + singles
        files.sort(key=lambda x: x.created_at or datetime.min, reverse=True)

    return {"files": [{"id": f.id, "name": f.original_name, "standard_name": f.standard_name, "bucket": f.bucket,
                       "status": f.process_status, "review_status": f.review_status, "summary": f.summary,
                       "group_id": f.group_id, "version_no": f.version_no, "change_note": f.change_note} for f in files]}

@router.get("/groups", summary="文档分组列表", description="按业务文档分组返回，包含已发布版本号与版本总数")
async def list_groups(bucket: Optional[str] = None, db: AsyncSession = Depends(get_db)):
    query = select(DocumentGroup)
    if bucket:
        query = query.where(DocumentGroup.bucket == bucket)
    result = await db.execute(query.order_by(DocumentGroup.updated_at.desc()))
    groups = result.scalars().all()
    items = []
    for g in groups:
        count = await db.execute(select(func.count(FileRecord.id)).where(FileRecord.group_id == g.id))
        published_version_no = None
        if g.published_version_id:
            pub = await db.get(FileRecord, g.published_version_id)
            published_version_no = pub.version_no if pub else None
        items.append({
            "group_id": g.id,
            "doc_key": g.doc_key,
            "title": g.title,
            "bucket": g.bucket,
            "version_count": count.scalar() or 0,
            "published_version_id": g.published_version_id,
            "published_version_no": published_version_no
        })
    return {"groups": items}

@router.get("/groups/{group_id}/versions", summary="文档版本列表", description="列出某业务文档的全部版本，审核员可在版本之间切换查看")
async def list_versions(group_id: int, db: AsyncSession = Depends(get_db)):
    group = await db.get(DocumentGroup, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Document group not found")
    result = await db.execute(
        select(FileRecord).where(FileRecord.group_id == group_id).order_by(FileRecord.version_no.desc())
    )
    versions = result.scalars().all()
    # 关联上传人用户名
    user_ids = {v.uploaded_by for v in versions if v.uploaded_by}
    users = {}
    if user_ids:
        u_result = await db.execute(select(User).where(User.id.in_(user_ids)))
        users = {u.id: u.username for u in u_result.scalars().all()}
    return {
        "group": {"group_id": group.id, "doc_key": group.doc_key, "title": group.title,
                  "bucket": group.bucket, "published_version_id": group.published_version_id},
        "versions": [{
            "id": v.id,
            "version_no": v.version_no,
            "change_note": v.change_note,
            "uploaded_by": v.uploaded_by,
            "uploaded_by_name": users.get(v.uploaded_by),
            "upload_date": v.upload_date.isoformat() if v.upload_date else None,
            "process_status": v.process_status,
            "review_status": v.review_status,
            "is_published": v.id == group.published_version_id,
            "standard_name": v.standard_name
        } for v in versions]
    }

@router.get("/versions/{file_id}", summary="版本详情", description="打开某个具体版本的详情，返回其标签与文本内容。旧版本内容仍可查看，但不会进入默认检索。")
async def get_version_detail(file_id: int, db: AsyncSession = Depends(get_db)):
    file = await db.get(FileRecord, file_id)
    if not file:
        raise HTTPException(status_code=404, detail="Version not found")

    # 关联信息：所属文档、是否为当前发布版本、上传人
    group = await db.get(DocumentGroup, file.group_id) if file.group_id else None
    is_published = bool(group and group.published_version_id == file.id)
    uploader = await db.get(User, file.uploaded_by) if file.uploaded_by else None

    tags_result = await db.execute(select(FileTag).where(FileTag.file_id == file_id))
    tags = tags_result.scalars().all()

    chunks_result = await db.execute(
        select(TextChunk).where(TextChunk.file_id == file_id).order_by(TextChunk.chunk_index)
    )
    chunks = chunks_result.scalars().all()

    return {
        "version": {
            "id": file.id,
            "group_id": file.group_id,
            "doc_key": group.doc_key if group else None,
            "version_no": file.version_no,
            "change_note": file.change_note,
            "uploaded_by": file.uploaded_by,
            "uploaded_by_name": uploader.username if uploader else None,
            "upload_date": file.upload_date.isoformat() if file.upload_date else None,
            "original_name": file.original_name,
            "standard_name": file.standard_name,
            "bucket": file.bucket,
            "file_type": file.file_type,
            "process_status": file.process_status,
            "review_status": file.review_status,
            "is_published": is_published,
            # 已发布版本才会进入默认检索；此接口用于查看，不受影响
            "searchable": is_published or (group is None and file.review_status == "approved"),
            "summary": file.summary,
        },
        "tags": [{"type": t.tag_type, "name": t.tag_name, "value": t.tag_value} for t in tags],
        "chunks": [{"index": c.chunk_index, "content": c.content} for c in chunks],
    }

@router.get("/{file_id}", summary="文件详情", description="获取指定文件（版本）的详细信息和标签，旧版本亦可查看")
async def get_file(file_id: int, db: AsyncSession = Depends(get_db)):
    file = await db.get(FileRecord, file_id)
    if not file:
        raise HTTPException(status_code=404, detail="File not found")
    tags = await db.execute(select(FileTag).where(FileTag.file_id == file_id))
    return {"file": file, "tags": tags.scalars().all()}

@router.post("/{file_id}/review", summary="审核版本", description="审核员对某个文档版本执行通过或退回。通过后该版本成为已发布版本，进入搜索与统计；旧发布版本自动下线。仅管理员可操作。")
async def review_file(
    file_id: int,
    action: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin)
):
    if action not in ["approve", "reject"]:
        raise HTTPException(status_code=400, detail="Invalid action")
    file = await db.get(FileRecord, file_id)
    if not file:
        raise HTTPException(status_code=404, detail="File not found")

    file.review_status = "approved" if action == "approve" else "rejected"
    file.reviewed_by = user.id
    file.reviewed_at = datetime.utcnow()

    if file.group_id:
        group = await db.get(DocumentGroup, file.group_id)
        if action == "approve":
            # 通过：该版本成为已发布版本，进入搜索/统计
            group.published_version_id = file.id
        elif action == "reject" and group.published_version_id == file.id:
            # 退回当前发布版本：下线，回退到该组其它已通过的最新版本（若有）
            fallback = await db.execute(
                select(FileRecord).where(
                    FileRecord.group_id == group.id,
                    FileRecord.review_status == "approved",
                    FileRecord.id != file.id
                ).order_by(FileRecord.version_no.desc())
            )
            fb = fallback.scalars().first()
            group.published_version_id = fb.id if fb else None

    await db.commit()
    return {"success": True}

@router.post("/reindex", summary="重建向量索引", description="重新索引所有已处理完成的文件到FAISS向量库")
async def reindex_all(db: AsyncSession = Depends(get_db)):
    # 重置模型加载尝试次数，允许重新尝试
    embedding_service.reset_load_attempts()
    
    # 重置向量索引
    embedding_service.init_index()
    
    # 获取所有已处理完成的文件
    result = await db.execute(
        select(FileRecord).where(FileRecord.process_status == "completed")
    )
    files = result.scalars().all()
    
    indexed = 0
    for file in files:
        # 获取文件的文本块
        chunks_result = await db.execute(
            select(TextChunk).where(TextChunk.file_id == file.id).order_by(TextChunk.chunk_index)
        )
        chunks = chunks_result.scalars().all()
        
        if chunks:
            chunk_data = [{"index": c.chunk_index, "content": c.content} for c in chunks]
            embedding_service.add_chunks(file.id, chunk_data)
            indexed += 1
    
    return {"success": True, "indexed_files": indexed}

@router.post("/process-pending", summary="处理待处理文件", description="手动触发处理所有待处理和处理中的文件")
async def process_pending_files(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(FileRecord).where(FileRecord.process_status.in_(["pending", "processing"]))
    )
    files = result.scalars().all()
    
    processed = 0
    errors = []
    
    for file in files:
        try:
            logger.info(f"Processing file {file.id}: {file.original_path}")
            file_type = file.file_type
            file_path = file.original_path
            
            # 解析文件
            if file_type in ["pdf"]:
                result_data = await doc_parser.parse_pdf(file_path)
            elif file_type in ["docx"]:
                result_data = await doc_parser.parse_docx(file_path)
            elif file_type in ["pptx"]:
                result_data = await doc_parser.parse_pptx(file_path)
            elif file_type in ["txt", "md"]:
                result_data = await doc_parser.parse_txt(file_path)
            elif file_type in ["mp4", "avi", "mov"]:
                result_data = await video_parser.transcribe(file_path)
            else:
                result_data = {"chunks": [], "metadata": {"type": "archive"}}
            
            if "error" in result_data:
                raise Exception(result_data["error"])
            
            chunks = result_data.get("chunks", [])
            content = " ".join([c["content"] for c in chunks[:10]])
            
            # 生成标签
            tags = tag_generator.generate_tags(file.original_name, content, file_type)
            standard_name = tag_generator.generate_standard_name(file.original_name, content, file.bucket, tags)

            # 保存标签
            for tag in tags:
                db.add(FileTag(file_id=file.id, tag_type=tag["type"], tag_name=tag["name"], tag_value=tag["value"]))
            
            # 保存文本块
            chunk_data = []
            for i, chunk in enumerate(chunks):
                db.add(TextChunk(file_id=file.id, chunk_index=i, content=chunk["content"]))
                chunk_data.append({"index": i, "content": chunk["content"]})
            
            # 添加到向量索引
            if chunk_data:
                embedding_service.add_chunks(file.id, chunk_data)
            
            await db.execute(update(FileRecord).where(FileRecord.id == file.id).values(
                process_status="completed", standard_name=standard_name, summary=content[:500]
            ))
            db.add(ProcessLog(file_id=file.id, action="process", status="success"))
            await db.commit()
            processed += 1
            logger.info(f"File {file.id} processed successfully")
        except Exception as e:
            logger.error(f"File {file.id} processing failed: {e}")
            await db.execute(update(FileRecord).where(FileRecord.id == file.id).values(process_status="failed"))
            db.add(ProcessLog(file_id=file.id, action="process", status="failed", message=str(e)))
            await db.commit()
            errors.append({"file_id": file.id, "error": str(e)})
    
    return {"success": True, "processed": processed, "errors": errors}
