from pydantic import BaseModel, Field
from typing import Optional, List, Any
from datetime import datetime


class GradingBase(BaseModel):
    sheet_id: str
    exam_id: str
    batch_id: str
    result_schema_id: Optional[str] = None
    result: dict = Field(default_factory=dict)
    total_awarded: float = 0
    total_max: float = 0
    status: str = "auto"


class GradingCreate(GradingBase):
    pass


class GradingUpdate(BaseModel):
    result: Optional[dict] = None
    total_awarded: Optional[float] = None
    total_max: Optional[float] = None
    status: Optional[str] = None


class GradingResponse(GradingBase):
    id: str
    student_id: Optional[str] = None
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    published_at: Optional[datetime] = None
    override_log: List[dict] = Field(default_factory=list)
    created_at: datetime

    class Config:
        from_attributes = True
