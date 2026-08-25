from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, Float, ForeignKey, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime

Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True)
    hashed_password = Column(String(255))
    role = Column(String(20), default="user")  # admin, user
    created_at = Column(DateTime, default=datetime.utcnow)

class Document(Base):
    """逻辑业务文档：同一业务文档的多次上传归为同一 Document，每次上传产生一个新版本（FileRecord）"""
    __tablename__ = "documents"
    id = Column(Integer, primary_key=True, index=True)
    doc_key = Column(String(500), unique=True, index=True)  # 业务文档标识（文件名归一化）
    title = Column(String(500), nullable=True)  # 展示名（取最新标准名）
    bucket = Column(String(50), nullable=True)  # 方案, 彩页, 视频, 安装包
    current_version = Column(Integer, default=0)  # 最新版本号
    published_version_id = Column(
        Integer,
        ForeignKey("file_records.id", use_alter=True, name="fk_document_published_version"),
        nullable=True
    )  # 当前审核通过并发布的版本
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    versions = relationship(
        "FileRecord", back_populates="document",
        foreign_keys="FileRecord.document_id",
        order_by="FileRecord.version_number"
    )
    published_version = relationship("FileRecord", foreign_keys=[published_version_id], post_update=True)

class FileRecord(Base):
    __tablename__ = "file_records"
    id = Column(Integer, primary_key=True, index=True)
    original_path = Column(String(500))
    original_name = Column(String(255))
    standard_name = Column(String(500))
    file_type = Column(String(50))  # pdf, docx, pptx, video, archive
    file_size = Column(Integer)
    bucket = Column(String(50))  # 方案, 彩页, 视频, 安装包
    upload_date = Column(DateTime, default=datetime.utcnow)
    process_status = Column(String(20), default="pending")  # pending, processing, completed, failed
    review_status = Column(String(20), default="pending")  # pending, approved, rejected
    reviewed_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    review_comment = Column(Text, nullable=True)  # 退回原因/审核备注
    summary = Column(Text, nullable=True)
    # --- 版本管理字段 ---
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=True, index=True)
    version_number = Column(Integer, default=1)  # 版本号，从 1 开始
    uploaded_by = Column(Integer, ForeignKey("users.id"), nullable=True)  # 上传人
    change_note = Column(Text, nullable=True)  # 变更说明
    is_published = Column(Boolean, default=False, index=True)  # 是否为当前发布版本
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    tags = relationship("FileTag", back_populates="file")
    chunks = relationship("TextChunk", back_populates="file")
    document = relationship(
        "Document", back_populates="versions", foreign_keys=[document_id]
    )
    uploader = relationship("User", foreign_keys=[uploaded_by])

class FileTag(Base):
    __tablename__ = "file_tags"
    id = Column(Integer, primary_key=True, index=True)
    file_id = Column(Integer, ForeignKey("file_records.id"))
    tag_type = Column(String(50))  # basic, semantic, status, relation
    tag_name = Column(String(100))
    tag_value = Column(String(255))
    file = relationship("FileRecord", back_populates="tags")

class TextChunk(Base):
    __tablename__ = "text_chunks"
    id = Column(Integer, primary_key=True, index=True)
    file_id = Column(Integer, ForeignKey("file_records.id"))
    chunk_index = Column(Integer)
    content = Column(Text)
    vector_id = Column(String(100), nullable=True)
    timestamp_start = Column(Float, nullable=True)  # for video
    timestamp_end = Column(Float, nullable=True)
    file = relationship("FileRecord", back_populates="chunks")

class FileRelation(Base):
    __tablename__ = "file_relations"
    id = Column(Integer, primary_key=True, index=True)
    source_file_id = Column(Integer, ForeignKey("file_records.id"))
    target_file_id = Column(Integer, ForeignKey("file_records.id"))
    relation_type = Column(String(50))  # 方案→彩页, 文档→视频, 视频→安装包
    confidence = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)

class ProcessLog(Base):
    __tablename__ = "process_logs"
    id = Column(Integer, primary_key=True, index=True)
    file_id = Column(Integer, ForeignKey("file_records.id"))
    action = Column(String(50))
    status = Column(String(20))
    message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
