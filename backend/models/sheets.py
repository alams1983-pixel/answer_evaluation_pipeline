from pydantic import BaseModel, Field
from typing import Optional, List, Any
from datetime import datetime


# Exam Models
class ExamBase(BaseModel):
    title: str
    subject_id: str
    class_id: str
    total_marks: int
    scheduled_on: Optional[str] = None
    complexity_tier: str = "standard"
    grading_rubric: str = "strict"
    rubric_notes: Optional[str] = None
    answer_key_id: Optional[str] = None
    result_schema_id: Optional[str] = None


class ExamCreate(ExamBase):
    pass


class ExamUpdate(BaseModel):
    title: Optional[str] = None
    subject_id: Optional[str] = None
    class_id: Optional[str] = None
    total_marks: Optional[int] = None
    scheduled_on: Optional[str] = None
    complexity_tier: Optional[str] = None
    grading_rubric: Optional[str] = None
    rubric_notes: Optional[str] = None
    answer_key_id: Optional[str] = None
    result_schema_id: Optional[str] = None
    status: Optional[str] = None


class ExamResponse(ExamBase):
    id: str
    status: str
    created_by: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# Answer Key Models
class QuestionItem(BaseModel):
    q_no: str
    question: Optional[str] = None
    expected_answer: Optional[str] = None
    marks: int
    keywords: List[str] = Field(default_factory=list)
    marking_scheme: Optional[str] = None


class SampleSheetItem(BaseModel):
    kind: str  # "pdf" | "text" | "image"
    path: str
    label: str
    notes: Optional[str] = None


class AnswerKeyBase(BaseModel):
    exam_id: str
    questions: List[QuestionItem] = Field(default_factory=list)
    question_paper_id: Optional[str] = None
    included_page_refs: List[int] = Field(default_factory=list)
    excluded_page_refs: List[int] = Field(default_factory=list)
    sample_sheets: List[SampleSheetItem] = Field(default_factory=list)
    source: str = "manual"
    source_file: Optional[str] = None
    extraction_status: str = "none"


class AnswerKeyCreate(AnswerKeyBase):
    pass


class AnswerKeyUpdate(BaseModel):
    questions: Optional[List[QuestionItem]] = None
    question_paper_id: Optional[str] = None
    included_page_refs: Optional[List[int]] = None
    excluded_page_refs: Optional[List[int]] = None
    sample_sheets: Optional[List[SampleSheetItem]] = None
    source: Optional[str] = None
    source_file: Optional[str] = None
    extraction_status: Optional[str] = None


class AnswerKeyResponse(AnswerKeyBase):
    id: str
    created_at: datetime

    class Config:
        from_attributes = True


# Result Schema Models
class ResultSchemaBase(BaseModel):
    name: str
    description: Optional[str] = None
    schema_definition: dict


class ResultSchemaCreate(ResultSchemaBase):
    pass


class ResultSchemaUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    schema_definition: Optional[dict] = None


class ResultSchemaResponse(ResultSchemaBase):
    id: str
    created_by: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


# Answer Sheet Upload Models (Phase 4)
class AnswerSheetBase(BaseModel):
    exam_id: str
    subject_id: Optional[str] = None
    student_name: Optional[str] = None
    roll_no: Optional[str] = None
    class_label: Optional[str] = None
    original_filename: str


class AnswerSheetCreate(AnswerSheetBase):
    pass


class AnswerSheetUpdate(BaseModel):
    student_name: Optional[str] = None
    roll_no: Optional[str] = None
    class_label: Optional[str] = None
    student_id: Optional[str] = None
    status: Optional[str] = None


class AnswerSheetResponse(AnswerSheetBase):
    id: str
    subject_id: Optional[str] = None
    student_id: Optional[str] = None
    original_pdf_path: Optional[str] = None
    page_count: int = 0
    status: str = "pending_mapping"
    current_batch_id: Optional[str] = None
    uploaded_by: Optional[str] = None
    batch_upload_id: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class SheetPageBase(BaseModel):
    sheet_id: str
    page_no: int
    image_path: str
    width: int = 0
    height: int = 0
    is_deleted: bool = False


class SheetPageResponse(SheetPageBase):
    id: str
    created_at: datetime

    class Config:
        from_attributes = True


class UploadBatchBase(BaseModel):
    exam_id: str
    uploaded_by: Optional[str] = None
    zip_filename: str
    total_pdfs: int = 0
    processed_pdfs: int = 0


class UploadBatchResponse(UploadBatchBase):
    id: str
    status: str = "extracting"
    created_at: datetime

    class Config:
        from_attributes = True


class SheetMapping(BaseModel):
    student_name: Optional[str] = None
    roll_no: Optional[str] = None
    class_label: Optional[str] = None
    student_id: Optional[str] = None


class AutoMatchItem(BaseModel):
    sheet_id: str
    student_id: str
    keep_parsed_name: bool = False


class AutoMatchRequest(BaseModel):
    matches: List[AutoMatchItem]


class StudentEnrollmentResponse(BaseModel):
    id: str
    email: str
    full_name: str
    role: str
    class_id: Optional[str] = None
    roll_no: Optional[str] = None
    is_active: bool = True
    enrollment_status: str
    enrolled_at: datetime
    removed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class StudentDropdownItem(BaseModel):
    id: str
    full_name: str
    roll_no: Optional[str] = None
    email: str


class ExamStudentsSummary(BaseModel):
    active_students: int
    removed_students: int
    mapped_sheets: int
    unmapped_sheets: int


class PageReorderRequest(BaseModel):
    page_order: List[int]


# Question Paper Models (Phase 4)
class QuestionPaperPageItem(BaseModel):
    page_no: int
    image_path: str
    is_instruction_page: bool = False
    has_questions: bool = False
    has_diagrams: bool = False
    has_graphs: bool = False
    is_needed_for_grading: bool = False
    reason: str = ""


class ExtractedQuestionItem(BaseModel):
    q_no: str
    question: Optional[str] = None
    question_page_refs: List[int] = Field(default_factory=list)
    expected_answer: Optional[str] = None
    marks: int = 0
    keywords: List[str] = Field(default_factory=list)
    marking_scheme: Optional[str] = None
    marking_scheme_page_ref: Optional[int] = None
    has_diagram: bool = False
    diagram_page_refs: List[int] = Field(default_factory=list)
    attached_images: List[dict] = Field(default_factory=list)


class QuestionPaperBase(BaseModel):
    exam_id: str
    source_file: str
    total_pages: int = 0


class QuestionPaperCreate(BaseModel):
    exam_id: str


class QuestionPaperUpdate(BaseModel):
    included_page_refs: Optional[List[int]] = None
    excluded_page_refs: Optional[List[int]] = None
    questions: Optional[List[ExtractedQuestionItem]] = None


class QuestionPaperResponse(BaseModel):
    id: str
    exam_id: str
    source_file: str
    total_pages: int
    pages: List[QuestionPaperPageItem] = Field(default_factory=list)
    extracted_questions: List[ExtractedQuestionItem] = Field(default_factory=list)
    status: str = "pending_extraction"
    extraction_model: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# Extraction Task Models (Phase 4)
class ExtractionTaskResponse(BaseModel):
    id: str
    exam_id: str
    status: str = "pending"
    total_pages: int = 0
    processed_pages: int = 0
    current_page: int = 0
    current_step: str = ""
    questions_found_so_far: int = 0
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# Question Paper Crop Models (Phase 4)
class CropBBox(BaseModel):
    x: int
    y: int
    width: int
    height: int


class QuestionPaperCropResponse(BaseModel):
    id: str
    exam_id: str
    question_paper_id: str
    question_index: int
    q_no: str
    image_path: str
    source_pdf: str
    page_no: int
    bbox: CropBBox
    created_at: datetime

    class Config:
        from_attributes = True


class CropCreateRequest(BaseModel):
    question_index: int
    q_no: str
    page_no: int
    source_pdf: str
    bbox: CropBBox
    image_data_base64: str


# Additional PDF Models (Phase 4)
class AdditionalPdfResponse(BaseModel):
    id: str
    exam_id: str
    source_file: str
    label: str
    type: str
    total_pages: int
    filename: str
    created_at: datetime

    class Config:
        from_attributes = True
