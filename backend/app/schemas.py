from pydantic import BaseModel
from typing import List, Optional, Dict, Any

class ErrorResponse(BaseModel):
    error_code: str
    message: str

class FileInfo(BaseModel):
    id: int
    filename: str
    bucket: str

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
    group_id: Optional[int] = None
    version_no: Optional[int] = None
    change_note: Optional[str] = None

class FileListResponse(BaseModel):
    files: List[FileItem]

class SearchResultItem(BaseModel):
    file_id: int
    group_id: Optional[int] = None
    filename: str
    standard_name: Optional[str] = None
    bucket: str
    version_no: Optional[int] = None
    score: float

class SearchResponse(BaseModel):
    query: str
    results: List[SearchResultItem]

class OverviewResponse(BaseModel):
    total_files: int
    total_groups: int
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
