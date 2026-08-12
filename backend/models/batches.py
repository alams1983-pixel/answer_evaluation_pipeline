from pydantic import BaseModel, Field
from typing import Optional, List, Any
from datetime import datetime


# Batch Job Models
class BatchJobBase(BaseModel):
    provider: str = "gemini"
    model: str = "gemini-2.5-flash"


class BatchJobCreate(BatchJobBase):
    pass


class BatchJobUpdate(BaseModel):
    provider: Optional[str] = None
    model: Optional[str] = None
    provider_batch_id: Optional[str] = None
    status: Optional[str] = None
    completed_count: Optional[int] = None
    failed_count: Optional[int] = None
    poll_error: Optional[str] = None


class UploadStatus(BaseModel):
    phase: str = "starting"
    current: int = 0
    total: int = 0
    message: str = ""


class BatchJobResponse(BatchJobBase):
    id: str
    exam_id: str
    provider_batch_id: Optional[str] = None
    input_file_path: Optional[str] = None
    uploaded_jsonl_path: Optional[str] = None
    output_file_path: Optional[str] = None
    uploaded_gemini_files: Optional[List[str]] = None
    item_count: int = 0
    completed_count: int = 0
    failed_count: int = 0
    status: str = "draft"
    upload_status: Optional[UploadStatus] = None
    submitted_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    last_polled_at: Optional[datetime] = None
    poll_error: Optional[str] = None
    created_by: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


# Batch Item Models
class BatchItemBase(BaseModel):
    batch_id: str
    sheet_id: str
    custom_id: str
    prompt_preview: Optional[str] = None


class BatchItemResponse(BatchItemBase):
    id: str
    status: str = "pending"
    error: Optional[str] = None
    raw_response: Optional[dict] = None
    created_at: datetime

    class Config:
        from_attributes = True


class BatchDetailResponse(BatchJobResponse):
    items: List[BatchItemResponse] = Field(default_factory=list)
