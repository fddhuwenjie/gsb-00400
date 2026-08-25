from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from typing import List, Optional
from pathlib import Path
from datetime import datetime
import aiofiles
import asyncio
import logging
import threading
import traceback

from app.database import get_db, async_session
from app.models import FileRecord, FileTag, TextChunk, ProcessLog, Document, User
from app.services import DocumentParser, VideoParser, EmbeddingService, TagGenerator
from app.config import settings
from app.routers.auth import get_current_user_optional
from app.routers.documents import serialize_version, uploader_name_map

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/files", tags=["files"])
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

@router.post("/upload", summary="批量上传文件（自动版本化）", description="上传一个或多个文件，自动进行后台解析和标签生成。同一业务文档（按文件名归一化标识）重复上传时不覆盖旧文件，而是创建新版本，记录版本号、上传人、上传时间和变更说明")
async def upload_files(
    files: List[UploadFile] = File(...),
    bucket: Optional[str] = None,
    change_note: Optional[str] = None,
    document_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    """批量上传文件：同一业务文档按 doc_key 归并为新版本，物理文件按 文档/版本 目录隔离存储"""
    upload_dir = Path(settings.UPLOAD_DIR)
    results = []

    for file in files:
        file_ext = Path(file.filename).suffix.lower().strip(".")
        suggested_bucket = bucket or tag_generator.suggest_bucket(file.filename, file_ext)

        # 找到或创建逻辑业务文档
        is_new_document = False
        if document_id:
            document = await db.get(Document, document_id)
            if not document:
                raise HTTPException(status_code=404, detail="Document not found")
        else:
            key = tag_generator.doc_key(file.filename)
            document = (
                await db.execute(select(Document).where(Document.doc_key == key))
            ).scalar_one_or_none()
            if document is None:
                document = Document(
                    doc_key=key, title=file.filename,
                    bucket=suggested_bucket, current_version=0
                )
                db.add(document)
                await db.flush()
                is_new_document = True

        version_number = (document.current_version or 0) + 1

        # 版本化存储：uploads/doc_{id}/v{版本号}/文件名，绝不覆盖旧版本
        version_dir = upload_dir / f"doc_{document.id}" / f"v{version_number}"
        version_dir.mkdir(parents=True, exist_ok=True)
        file_path = version_dir / file.filename
        async with aiofiles.open(file_path, "wb") as f:
            content = await file.read()
            await f.write(content)

        record = FileRecord(
            original_path=str(file_path),
            original_name=file.filename,
            file_type=file_ext,
            file_size=len(content),
            bucket=document.bucket or suggested_bucket,
            process_status="pending",
            review_status="pending",
            document_id=document.id,
            version_number=version_number,
            uploaded_by=current_user.id if current_user else None,
            change_note=change_note,
            is_published=False,
        )
        db.add(record)
        document.current_version = version_number
        document.bucket = document.bucket or suggested_bucket
        await db.commit()
        await db.refresh(record)

        # 在独立线程中处理文件
        run_in_thread(record.id, str(file_path), file_ext)
        results.append({
            "id": record.id, "filename": file.filename, "bucket": record.bucket,
            "document_id": document.id, "version_number": version_number,
            "is_new_document": is_new_document
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
            if record.document_id:
                await db.execute(update(Document).where(Document.id == record.document_id).values(
                    title=standard_name, bucket=record.bucket
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

@router.get("/list", summary="文件版本列表", description="获取全部文件版本列表，支持按分类和处理状态筛选，返回版本号、上传人、变更说明与发布状态")
async def list_files(bucket: Optional[str] = None, status: Optional[str] = None, db: AsyncSession = Depends(get_db)):
    query = select(FileRecord)
    if bucket:
        query = query.where(FileRecord.bucket == bucket)
    if status:
        query = query.where(FileRecord.process_status == status)
    result = await db.execute(query.order_by(FileRecord.created_at.desc()))
    files = result.scalars().all()
    name_map = await uploader_name_map(db, [f.uploaded_by for f in files])
    return {"files": [{
        "id": f.id, "name": f.original_name, "standard_name": f.standard_name, "bucket": f.bucket,
        "status": f.process_status, "review_status": f.review_status, "summary": f.summary,
        "document_id": f.document_id, "version_number": f.version_number,
        "is_published": bool(f.is_published), "change_note": f.change_note,
        "uploaded_by": name_map.get(f.uploaded_by),
        "upload_date": f.upload_date.isoformat() if f.upload_date else None
    } for f in files]}

@router.get("/{file_id}", summary="文件版本详情", description="获取指定版本的详细信息、标签，以及所属文档的全部版本（用于版本切换与历史版本查看）")
async def get_file(file_id: int, db: AsyncSession = Depends(get_db)):
    file = await db.get(FileRecord, file_id)
    if not file:
        raise HTTPException(status_code=404, detail="File not found")
    tags = (await db.execute(select(FileTag).where(FileTag.file_id == file_id))).scalars().all()
    uploader = await db.get(User, file.uploaded_by) if file.uploaded_by else None
    file_data = serialize_version(file, uploader.username if uploader else None)

    document_data = None
    versions = []
    if file.document_id:
        doc = await db.get(Document, file.document_id)
        if doc:
            vresult = await db.execute(
                select(FileRecord)
                .where(FileRecord.document_id == doc.id)
                .order_by(FileRecord.version_number.desc())
            )
            vfiles = vresult.scalars().all()
            name_map = await uploader_name_map(db, [v.uploaded_by for v in vfiles])
            versions = [serialize_version(v, name_map.get(v.uploaded_by)) for v in vfiles]
            document_data = {
                "id": doc.id, "doc_key": doc.doc_key, "title": doc.title,
                "current_version": doc.current_version,
                "published_file_id": doc.published_version_id
            }

    return {
        "file": file_data,
        "tags": [{"id": t.id, "tag_type": t.tag_type, "tag_name": t.tag_name, "tag_value": t.tag_value} for t in tags],
        "document": document_data,
        "versions": versions
    }

@router.post("/{file_id}/review", summary="审核版本（通过发布/退回）", description="对指定版本执行通过(approve)或退回(reject)。通过后该版本成为文档的当前发布版本，同文档旧版本自动取消发布；退回需填写原因，退回版本不进入搜索与统计")
async def review_file(
    file_id: int,
    action: str,
    comment: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    if action not in ["approve", "reject"]:
        raise HTTPException(status_code=400, detail="Invalid action")
    file = await db.get(FileRecord, file_id)
    if not file:
        raise HTTPException(status_code=404, detail="File not found")

    if action == "approve":
        file.review_status = "approved"
        file.is_published = True
        file.review_comment = None
        if file.document_id:
            # 同文档其他版本取消发布（旧版本保留可查看，但不再被检索）
            await db.execute(
                update(FileRecord)
                .where(FileRecord.document_id == file.document_id, FileRecord.id != file.id)
                .values(is_published=False)
            )
            doc = await db.get(Document, file.document_id)
            if doc:
                doc.published_version_id = file.id
    else:
        if not comment or not comment.strip():
            raise HTTPException(status_code=400, detail="退回时必须填写退回原因")
        file.review_status = "rejected"
        file.is_published = False
        file.review_comment = comment.strip()
        if file.document_id:
            doc = await db.get(Document, file.document_id)
            if doc and doc.published_version_id == file.id:
                doc.published_version_id = None

    file.reviewed_by = current_user.id if current_user else None
    file.reviewed_at = datetime.utcnow()
    db.add(ProcessLog(file_id=file.id, action="review", status=action, message=comment))
    await db.commit()
    return {
        "success": True, "file_id": file.id,
        "review_status": file.review_status, "is_published": bool(file.is_published)
    }

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
            if file.document_id:
                await db.execute(update(Document).where(Document.id == file.document_id).values(
                    title=standard_name, bucket=file.bucket
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
