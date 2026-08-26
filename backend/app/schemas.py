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
    document_id: Optional[int] = None
    version_number: int = 1
    is_new_document: bool = False

class UploadResponse(BaseModel):
    uploaded: int
    files: List[FileInfo]

class VersionItem(BaseModel):
    id: int
    version_number: int
    original_name: str
    standard_name: Optional[str] = None
    bucket: str
    process_status: str
    review_status: str
    change_description: Optional[str] = None
    review_comment: Optional[str] = None
    uploaded_by: Optional[int] = None
    uploader_name: Optional[str] = None
    reviewer_name: Optional[str] = None
    uploaded_at: Optional[datetime] = None
    reviewed_at: Optional[datetime] = None
    is_current: bool = False

class DocumentItem(BaseModel):
    id: int
    document_key: str
    title: str
    current_version: Optional[int] = None
    latest_version: Optional[int] = None
    version_count: int = 0
    bucket: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

class DocumentDetail(BaseModel):
    id: int
    document_key: str
    title: str
    current_version_id: Optional[int] = None
    versions: List[VersionItem]

class FileItem(BaseModel):
    id: int
    name: str
    standard_name: Optional[str] = None
    bucket: str
    status: str
    review_status: str
    summary: Optional[str] = None
    document_id: Optional[int] = None
    version_number: int = 1
    change_description: Optional[str] = None
    is_current: bool = False

class FileListResponse(BaseModel):
    files: List[FileItem]

class SearchResultItem(BaseModel):
    file_id: int
    document_id: Optional[int] = None
    version_number: int = 1
    filename: str
    standard_name: Optional[str] = None
    bucket: str
    score: float

class SearchResponse(BaseModel):
    query: str
    results: List[SearchResultItem]

class OverviewResponse(BaseModel):
    total_files: int
    completed: int
    pending_review: int
    approved: int
    by_bucket: Dict[str, int]
    total_documents: int = 0

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

class ReviewRequest(BaseModel):
    action: str
    comment: Optional[str] = None
