from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, BackgroundTasks, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from typing import List, Optional
from pathlib import Path
import aiofiles
import asyncio
import logging
import threading
import traceback

from app.database import get_db, async_session
from app.models import FileRecord, FileTag, TextChunk, ProcessLog, User, DocumentVersion
from app.services import DocumentParser, VideoParser, EmbeddingService, TagGenerator
from app.services.versioning import get_or_create_group, next_version_no
from app.routers.auth import get_current_user_optional
from app.config import settings

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

@router.post("/upload", summary="批量上传文件", description="上传一个或多个文件，自动进行后台解析和标签生成。同一文档标识(doc_key)的重复上传会创建新版本而不会覆盖旧文件")
async def upload_files(
    files: List[UploadFile] = File(...),
    bucket: Optional[str] = Form(None),
    doc_key: Optional[str] = Form(None),
    change_note: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db),
    user: Optional[User] = Depends(get_current_user_optional)
):
    """批量上传文件，按文档标识(doc_key)分组创建版本"""
    upload_dir = Path(settings.UPLOAD_DIR)
    upload_dir.mkdir(parents=True, exist_ok=True)
    results = []

    for file in files:
        content = await file.read()
        file_ext = Path(file.filename).suffix.lower().strip(".")
        suggested_bucket = bucket or tag_generator.suggest_bucket(file.filename, file_ext)

        # 按文档标识分组并分配版本号
        key = (doc_key or Path(file.filename).stem).strip()
        group = await get_or_create_group(db, key, title=Path(file.filename).stem, bucket=suggested_bucket)
        version_no = await next_version_no(db, group.id)

        # 每个版本独立存储，不覆盖旧文件
        version_dir = upload_dir / str(group.id)
        version_dir.mkdir(parents=True, exist_ok=True)
        file_path = version_dir / f"v{version_no}_{file.filename}"
        async with aiofiles.open(file_path, "wb") as f:
            await f.write(content)

        record = FileRecord(
            original_path=str(file_path),
            original_name=file.filename,
            file_type=file_ext,
            file_size=len(content),
            bucket=suggested_bucket,
            process_status="pending"
        )
        db.add(record)
        await db.flush()

        version = DocumentVersion(
            group_id=group.id,
            file_id=record.id,
            version_no=version_no,
            change_note=change_note,
            uploaded_by=user.id if user else None
        )
        db.add(version)
        await db.commit()
        await db.refresh(record)

        # 在独立线程中处理文件
        run_in_thread(record.id, str(file_path), file_ext)
        results.append({"id": record.id, "filename": file.filename, "bucket": suggested_bucket,
                        "doc_key": key, "version_no": version_no})

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

@router.get("/list", summary="文件列表", description="获取文件列表，支持按分类和状态筛选")
async def list_files(bucket: Optional[str] = None, status: Optional[str] = None, db: AsyncSession = Depends(get_db)):
    query = select(FileRecord)
    if bucket:
        query = query.where(FileRecord.bucket == bucket)
    if status:
        query = query.where(FileRecord.process_status == status)
    result = await db.execute(query.order_by(FileRecord.created_at.desc()))
    files = result.scalars().all()
    return {"files": [{"id": f.id, "name": f.original_name, "standard_name": f.standard_name, "bucket": f.bucket,
                       "status": f.process_status, "review_status": f.review_status, "summary": f.summary} for f in files]}

@router.get("/{file_id}", summary="文件详情", description="获取指定文件的详细信息和标签")
async def get_file(file_id: int, db: AsyncSession = Depends(get_db)):
    file = await db.get(FileRecord, file_id)
    if not file:
        raise HTTPException(status_code=404, detail="File not found")
    tags = await db.execute(select(FileTag).where(FileTag.file_id == file_id))
    return {"file": file, "tags": tags.scalars().all()}

@router.post("/{file_id}/review", summary="审核文件", description="通过或拒绝文件的AI分类建议")
async def review_file(file_id: int, action: str, db: AsyncSession = Depends(get_db)):
    if action not in ["approve", "reject"]:
        raise HTTPException(status_code=400, detail="Invalid action")
    await db.execute(update(FileRecord).where(FileRecord.id == file_id).values(
        review_status="approved" if action == "approve" else "rejected"
    ))
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
