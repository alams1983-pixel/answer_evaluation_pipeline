from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

# Class Models
class ClassBase(BaseModel):
    name: str
    session: str
    section: Optional[str] = None
    teacher_ids: List[str] = Field(default_factory=list)
    class_teacher_id: Optional[str] = None

class ClassCreate(ClassBase):
    pass

class ClassUpdate(BaseModel):
    name: Optional[str] = None
    session: Optional[str] = None
    section: Optional[str] = None
    teacher_ids: Optional[List[str]] = None
    class_teacher_id: Optional[str] = None

class ClassResponse(ClassBase):
    id: str
    created_by: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

# Subject Models
class SubjectBase(BaseModel):
    name: str
    code: Optional[str] = None
    class_id: str
    teacher_ids: List[str] = Field(default_factory=list)

class SubjectCreate(SubjectBase):
    pass

class SubjectUpdate(BaseModel):
    name: Optional[str] = None
    code: Optional[str] = None
    class_id: Optional[str] = None
    teacher_ids: Optional[List[str]] = None

class SubjectResponse(SubjectBase):
    id: str
    created_by: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

# Enrollment Models
class EnrollmentBase(BaseModel):
    student_id: str
    class_id: str
    roll_no: str

class EnrollmentCreate(EnrollmentBase):
    pass

class EnrollmentResponse(EnrollmentBase):
    id: str
    enrolled_at: datetime
    is_active: bool = True

    class Config:
        from_attributes = True
