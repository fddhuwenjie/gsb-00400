from pydantic import BaseModel
from typing import List, Optional, Dict, Any

class ErrorResponse(BaseModel):
    error_code: str
    message: str

class FileInfo(BaseModel):
    id: int
    filename: str
    bucket: str
    document_id: Optional[int] = None
    version_number: Optional[int] = None
    is_new_document: Optional[bool] = None

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
    document_id: Optional[int] = None
    version_number: Optional[int] = None
    is_published: Optional[bool] = None
    uploaded_by: Optional[str] = None
    upload_date: Optional[str] = None
    change_note: Optional[str] = None

class FileListResponse(BaseModel):
    files: List[FileItem]

class VersionItem(BaseModel):
    file_id: int
    document_id: Optional[int] = None
    version_number: int
    name: str
    standard_name: Optional[str] = None
    bucket: str
    status: str
    review_status: str
    is_published: bool
    uploaded_by: Optional[str] = None
    upload_date: Optional[str] = None
    change_note: Optional[str] = None
    summary: Optional[str] = None
    review_comment: Optional[str] = None

class DocumentItem(BaseModel):
    id: int
    doc_key: str
    title: Optional[str] = None
    bucket: Optional[str] = None
    current_version: int
    published_version: Optional[int] = None
    published_file_id: Optional[int] = None
    version_count: int
    has_pending: bool
    updated_at: Optional[str] = None

class DocumentListResponse(BaseModel):
    documents: List[DocumentItem]

class DocumentDetailResponse(BaseModel):
    document: DocumentItem
    versions: List[VersionItem]

class SearchResultItem(BaseModel):
    file_id: int
    document_id: Optional[int] = None
    version_number: Optional[int] = None
    filename: str
    standard_name: Optional[str] = None
    bucket: str
    score: float

class SearchResponse(BaseModel):
    query: str
    results: List[SearchResultItem]

class OverviewResponse(BaseModel):
    total_files: int
    total_documents: int
    total_versions: int
    completed: int
    pending_review: int
    approved: int
    published: int
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
