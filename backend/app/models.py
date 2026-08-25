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
    summary = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    tags = relationship("FileTag", back_populates="file")
    chunks = relationship("TextChunk", back_populates="file")

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

class DocumentGroup(Base):
    """业务文档分组：同一文档标识(doc_key)的多次上传归入同一组"""
    __tablename__ = "document_groups"
    id = Column(Integer, primary_key=True, index=True)
    doc_key = Column(String(255), unique=True, index=True)  # 文档标识
    title = Column(String(255))  # 业务文档显示名
    bucket = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    versions = relationship("DocumentVersion", back_populates="group", order_by="DocumentVersion.version_no")

class DocumentVersion(Base):
    """文档版本：每次上传生成一个版本，保留版本号、上传人、上传时间与变更说明"""
    __tablename__ = "document_versions"
    id = Column(Integer, primary_key=True, index=True)
    group_id = Column(Integer, ForeignKey("document_groups.id"), index=True)
    file_id = Column(Integer, ForeignKey("file_records.id"), unique=True)
    version_no = Column(Integer)  # 组内递增版本号
    change_note = Column(String(500), nullable=True)  # 变更说明
    uploaded_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    uploaded_at = Column(DateTime, default=datetime.utcnow)
    review_status = Column(String(20), default="pending")  # pending, approved, rejected
    review_note = Column(String(500), nullable=True)  # 退回原因
    reviewed_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    group = relationship("DocumentGroup", back_populates="versions")
    file = relationship("FileRecord")
