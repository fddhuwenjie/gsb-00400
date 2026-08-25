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

class DocumentGroup(Base):
    """业务文档分组：同一业务文档的多个版本聚合在一个 group 下，通过 doc_key 唯一标识。

    published_version_id 指向当前进入搜索结果与统计的“已发布”版本；只有审核通过的版本
    才能被设置为发布版本。旧版本仍保留在 file_records 中，可在详情页查看但不会被默认检索。
    """
    __tablename__ = "document_groups"
    id = Column(Integer, primary_key=True, index=True)
    doc_key = Column(String(255), unique=True, index=True)  # 业务文档标识
    title = Column(String(255))
    bucket = Column(String(50))
    published_version_id = Column(Integer, ForeignKey("file_records.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    versions = relationship(
        "FileRecord", back_populates="group", foreign_keys="FileRecord.group_id"
    )

class FileRecord(Base):
    """文件记录，同时表示某个业务文档的一个版本。"""
    __tablename__ = "file_records"
    id = Column(Integer, primary_key=True, index=True)
    group_id = Column(Integer, ForeignKey("document_groups.id"), nullable=True, index=True)
    version_no = Column(Integer, default=1)  # 组内版本号，从 1 递增
    change_note = Column(Text, nullable=True)  # 变更说明
    uploaded_by = Column(Integer, ForeignKey("users.id"), nullable=True)  # 上传人
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
    group = relationship("DocumentGroup", back_populates="versions", foreign_keys=[group_id])
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
