from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, BackgroundTasks, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func
from typing import List, Optional
from pathlib import Path
import aiofiles
import asyncio
import logging
import threading
import traceback
from datetime import datetime

from app.database import get_db, async_session
from app.models import FileRecord, FileTag, TextChunk, ProcessLog, Document, User
from app.services import DocumentParser, VideoParser, EmbeddingService, TagGenerator
from app.routers.documents import normalize_document_key
from app.routers.auth import get_current_user, require_admin
from app.config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/files", tags=["files"])
doc_parser = DocumentParser()
video_parser = VideoParser()
embedding_service = EmbeddingService()
tag_generator = TagGenerator()

def run_in_thread(file_id: int, file_path: str, file_type: str):
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

@router.post("/upload", summary="批量上传文件（支持版本）", description="上传一个或多个文件。相同document_key的文件会自动创建新版本，不覆盖旧版本。需要登录。")
async def upload_files(
    files: List[UploadFile] = File(...),
    bucket: Optional[str] = Form(None),
    document_key: Optional[str] = Form(None),
    change_description: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    upload_dir = Path(settings.UPLOAD_DIR)
    upload_dir.mkdir(parents=True, exist_ok=True)
    results = []

    for file in files:
        file_ext = Path(file.filename).suffix.lower().strip(".")
        suggested_bucket = bucket or tag_generator.suggest_bucket(file.filename, file_ext)

        doc_key = document_key or normalize_document_key(file.filename)

        existing_doc = await db.execute(
            select(Document).where(Document.document_key == doc_key)
        )
        document = existing_doc.scalar_one_or_none()

        is_new_document = False
        if document:
            max_ver_result = await db.execute(
                select(func.max(FileRecord.version_number)).where(FileRecord.document_id == document.id)
            )
            max_ver = max_ver_result.scalar() or 0
            next_version = max_ver + 1
        else:
            document = Document(
                document_key=doc_key,
                title=Path(file.filename).stem,
            )
            db.add(document)
            await db.flush()
            next_version = 1
            is_new_document = True

        version_dir = upload_dir / f"doc_{document.id}" / f"v{next_version}"
        version_dir.mkdir(parents=True, exist_ok=True)
        file_path = version_dir / file.filename
        async with aiofiles.open(file_path, "wb") as f:
            content = await file.read()
            await f.write(content)

        record = FileRecord(
            document_id=document.id,
            version_number=next_version,
            original_path=str(file_path),
            original_name=file.filename,
            file_type=file_ext,
            file_size=len(content),
            bucket=suggested_bucket,
            process_status="pending",
            change_description=change_description if not is_new_document else None,
            uploaded_by=current_user.id,
        )
        db.add(record)
        await db.flush()

        if is_new_document:
            document.title = record.original_name

        await db.commit()
        await db.refresh(record)

        run_in_thread(record.id, str(file_path), file_ext)
        results.append({
            "id": record.id,
            "filename": file.filename,
            "bucket": suggested_bucket,
            "document_id": document.id,
            "version_number": next_version,
            "is_new_document": is_new_document
        })

    return {"uploaded": len(results), "files": results}

async def process_file_async(file_id: int, file_path: str, file_type: str):
    logger.info(f"Starting async processing for file {file_id}: {file_path}")
    async with async_session() as db:
        await db.execute(update(FileRecord).where(FileRecord.id == file_id).values(process_status="processing"))
        await db.commit()

        try:
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

            record = await db.get(FileRecord, file_id)
            tags = tag_generator.generate_tags(record.original_name, content, file_type)
            standard_name = tag_generator.generate_standard_name(record.original_name, content, record.bucket, tags)
            logger.info(f"Generated standard name for file {file_id}: {standard_name}")

            for tag in tags:
                db.add(FileTag(file_id=file_id, tag_type=tag["type"], tag_name=tag["name"], tag_value=tag["value"]))

            chunk_data = []
            for i, chunk in enumerate(chunks):
                db.add(TextChunk(file_id=file_id, chunk_index=i, content=chunk["content"]))
                chunk_data.append({"index": i, "content": chunk["content"]})

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

@router.get("/list", summary="文件列表", description="获取文件列表，支持按分类和状态筛选，包含版本信息")
async def list_files(
    bucket: Optional[str] = None,
    status: Optional[str] = None,
    review_status: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    query = select(FileRecord)
    if bucket:
        query = query.where(FileRecord.bucket == bucket)
    if status:
        query = query.where(FileRecord.process_status == status)
    if review_status:
        query = query.where(FileRecord.review_status == review_status)
    result = await db.execute(query.order_by(FileRecord.created_at.desc()))
    files = result.scalars().all()

    doc_ids = list({f.document_id for f in files if f.document_id})
    current_versions = {}
    if doc_ids:
        docs_result = await db.execute(select(Document).where(Document.id.in_(doc_ids)))
        for d in docs_result.scalars().all():
            if d.current_version_id:
                current_versions[d.id] = d.current_version_id

    return {"files": [{
        "id": f.id,
        "name": f.original_name,
        "standard_name": f.standard_name,
        "bucket": f.bucket,
        "status": f.process_status,
        "review_status": f.review_status,
        "summary": f.summary,
        "document_id": f.document_id,
        "version_number": f.version_number,
        "change_description": f.change_description,
        "is_current": current_versions.get(f.document_id) == f.id if f.document_id else False
    } for f in files]}

@router.get("/{file_id}", summary="文件详情", description="获取指定文件的详细信息和标签，包含所属文档和版本信息")
async def get_file(file_id: int, db: AsyncSession = Depends(get_db)):
    file = await db.get(FileRecord, file_id)
    if not file:
        raise HTTPException(status_code=404, detail="File not found")
    tags = await db.execute(select(FileTag).where(FileTag.file_id == file_id))
    tags = tags.scalars().all()

    document = None
    is_current = False
    sibling_versions = []
    if file.document_id:
        document = await db.get(Document, file.document_id)
        if document:
            is_current = (document.current_version_id == file.id)
            vers_result = await db.execute(
                select(FileRecord)
                .where(FileRecord.document_id == file.document_id)
                .order_by(FileRecord.version_number.desc())
            )
            for v in vers_result.scalars().all():
                sibling_versions.append({
                    "id": v.id,
                    "version_number": v.version_number,
                    "review_status": v.review_status,
                    "process_status": v.process_status,
                    "is_current": document.current_version_id == v.id
                })

    return {
        "file": {
            "id": file.id,
            "document_id": file.document_id,
            "version_number": file.version_number,
            "original_name": file.original_name,
            "standard_name": file.standard_name,
            "file_type": file.file_type,
            "file_size": file.file_size,
            "bucket": file.bucket,
            "summary": file.summary,
            "process_status": file.process_status,
            "review_status": file.review_status,
            "review_comment": file.review_comment,
            "change_description": file.change_description,
            "upload_date": file.upload_date.isoformat() if file.upload_date else None,
            "reviewed_at": file.reviewed_at.isoformat() if file.reviewed_at else None,
            "is_current": is_current,
        },
        "document": {
            "id": document.id,
            "document_key": document.document_key,
            "title": document.title,
            "current_version_id": document.current_version_id,
        } if document else None,
        "tags": [{"id": t.id, "type": t.tag_type, "name": t.tag_name, "value": t.tag_value} for t in tags],
        "versions": sibling_versions
    }

@router.post("/{file_id}/review", summary="审核文件（兼容旧接口）", description="通过或拒绝文件，通过后自动设为所属文档的当前版本。需要管理员权限，退回时必须填写原因。")
async def review_file(
    file_id: int,
    action: str,
    comment: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    if action not in ["approve", "reject"]:
        raise HTTPException(status_code=400, detail="Invalid action")
    if action == "reject" and not (comment and comment.strip()):
        raise HTTPException(status_code=400, detail="退回时必须填写原因")

    file = await db.get(FileRecord, file_id)
    if not file:
        raise HTTPException(status_code=404, detail="File not found")

    now = datetime.utcnow()
    if action == "approve":
        await db.execute(update(FileRecord).where(FileRecord.id == file_id).values(
            review_status="approved",
            review_comment=comment,
            reviewed_by=current_user.id,
            reviewed_at=now
        ))
        if file.document_id:
            doc = await db.get(Document, file.document_id)
            if doc:
                doc.current_version_id = file_id
                if not doc.title:
                    doc.title = file.standard_name or file.original_name
    else:
        await db.execute(update(FileRecord).where(FileRecord.id == file_id).values(
            review_status="rejected",
            review_comment=comment,
            reviewed_by=current_user.id,
            reviewed_at=now
        ))

    await db.commit()
    return {"success": True, "action": action, "file_id": file_id}

@router.post("/reindex", summary="重建向量索引", description="重新索引所有已处理完成且为当前审核通过版本的文件到FAISS向量库。需要管理员权限。")
async def reindex_all(db: AsyncSession = Depends(get_db), current_user: User = Depends(require_admin)):
    embedding_service.reset_load_attempts()
    embedding_service.init_index()

    result = await db.execute(
        select(FileRecord).where(FileRecord.process_status == "completed")
    )
    files = result.scalars().all()

    doc_ids = list({f.document_id for f in files if f.document_id})
    current_versions = {}
    if doc_ids:
        docs_result = await db.execute(select(Document).where(Document.id.in_(doc_ids)))
        for d in docs_result.scalars().all():
            if d.current_version_id:
                current_versions[d.id] = d.current_version_id

    indexed = 0
    for file in files:
        is_searchable = file.review_status == "approved"
        if file.document_id and current_versions.get(file.document_id) != file.id:
            is_searchable = False
        if not is_searchable:
            continue

        chunks_result = await db.execute(
            select(TextChunk).where(TextChunk.file_id == file.id).order_by(TextChunk.chunk_index)
        )
        chunks = chunks_result.scalars().all()

        if chunks:
            chunk_data = [{"index": c.chunk_index, "content": c.content} for c in chunks]
            embedding_service.add_chunks(file.id, chunk_data)
            indexed += 1

    return {"success": True, "indexed_files": indexed}

@router.post("/process-pending", summary="处理待处理文件", description="手动触发处理所有待处理和处理中的文件。需要管理员权限。")
async def process_pending_files(db: AsyncSession = Depends(get_db), current_user: User = Depends(require_admin)):
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

            tags = tag_generator.generate_tags(file.original_name, content, file_type)
            standard_name = tag_generator.generate_standard_name(file.original_name, content, file.bucket, tags)

            for tag in tags:
                db.add(FileTag(file_id=file.id, tag_type=tag["type"], tag_name=tag["name"], tag_value=tag["value"]))

            chunk_data = []
            for i, chunk in enumerate(chunks):
                db.add(TextChunk(file_id=file.id, chunk_index=i, content=chunk["content"]))
                chunk_data.append({"index": i, "content": chunk["content"]})

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
