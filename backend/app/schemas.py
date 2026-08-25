from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime

class ErrorResponse(BaseModel):
    error_code: str
    message: str

class FileInfo(BaseModel):
    id: int
    filename: str
    bucket: str
    doc_key: Optional[str] = None
    version_no: Optional[int] = None

class UploadResponse(BaseModel):
    uploaded: int
    files: List[FileInfo]

class FileItem(BaseModel):
    id: int
    name: str
    standard_name: Optional[str] = None
    bucket: str
    status: str
    review_status: str
    summary: Optional[str] = None

class FileListResponse(BaseModel):
    files: List[FileItem]

class SearchResultItem(BaseModel):
    file_id: int
    filename: str
    standard_name: Optional[str] = None
    bucket: str
    score: float
    doc_key: Optional[str] = None
    version_no: Optional[int] = None

class SearchResponse(BaseModel):
    query: str
    results: List[SearchResultItem]

class OverviewResponse(BaseModel):
    total_files: int
    completed: int
    pending_review: int
    approved: int
    by_bucket: Dict[str, int]

class TagItem(BaseModel):
    name: str
    value: str
    count: int

class TagStatsResponse(BaseModel):
    tags: List[TagItem]

class TokenResponse(BaseModel):
    access_token: str
    token_type: str

class UserResponse(BaseModel):
    id: int
    username: str
    role: str

class ReviewResponse(BaseModel):
    success: bool

class ReindexResponse(BaseModel):
    success: bool
    indexed_files: int

class ProcessPendingResponse(BaseModel):
    success: bool
    processed: int
    errors: List[Dict[str, Any]]

class DocGroupItem(BaseModel):
    doc_key: str
    title: str
    bucket: Optional[str] = None
    version_count: int
    latest_version_no: int
    published_version_no: Optional[int] = None
    latest_review_status: str
    updated_at: Optional[datetime] = None

class DocGroupListResponse(BaseModel):
    groups: List[DocGroupItem]

class VersionItem(BaseModel):
    id: int
    file_id: int
    version_no: int
    filename: str
    change_note: Optional[str] = None
    uploaded_by: Optional[str] = None
    uploaded_at: Optional[datetime] = None
    review_status: str
    review_note: Optional[str] = None
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    is_published: bool = False
    file_size: Optional[int] = None
    status: str

class VersionListResponse(BaseModel):
    doc_key: str
    title: str
    versions: List[VersionItem]

class TagInfo(BaseModel):
    tag_type: str
    tag_name: str
    tag_value: str

class VersionDetailResponse(BaseModel):
    id: int
    file_id: int
    doc_key: str
    version_no: int
    filename: str
    standard_name: Optional[str] = None
    bucket: Optional[str] = None
    summary: Optional[str] = None
    change_note: Optional[str] = None
    uploaded_by: Optional[str] = None
    uploaded_at: Optional[datetime] = None
    review_status: str
    review_note: Optional[str] = None
    is_published: bool = False
    tags: List[TagInfo] = []
