import uuid
from datetime import datetime
from sqlalchemy import (
    Column, String, Integer, Float, Boolean, DateTime, Text, JSON,
    ForeignKey, Table, UniqueConstraint, Index
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

def generate_uuid():
    return uuid.uuid4().hex

# Many-to-Many Junction Tables
class_teachers = Table(
    "class_teachers",
    Base.metadata,
    Column("class_id", String(36), ForeignKey("classes.id", ondelete="CASCADE"), primary_key=True),
    Column("teacher_id", String(36), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
)

subject_teachers = Table(
    "subject_teachers",
    Base.metadata,
    Column("subject_id", String(36), ForeignKey("subjects.id", ondelete="CASCADE"), primary_key=True),
    Column("teacher_id", String(36), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
)

class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False, default="student")  # admin, teacher, student
    class_id = Column(String(36), ForeignKey("classes.id", ondelete="SET NULL"), nullable=True)
    roll_no = Column(String(50), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_by = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, nullable=True)


class PasswordReset(Base):
    __tablename__ = "password_resets"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    token = Column(String(255), unique=True, nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class Class(Base):
    __tablename__ = "classes"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    name = Column(String(100), nullable=False, index=True)
    session = Column(String(50), nullable=False)
    section = Column(String(50), nullable=True, index=True)
    class_teacher_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_by = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, nullable=True)


class Subject(Base):
    __tablename__ = "subjects"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    name = Column(String(100), nullable=False, index=True)
    code = Column(String(50), nullable=True)
    class_id = Column(String(36), ForeignKey("classes.id", ondelete="CASCADE"), nullable=False, index=True)
    created_by = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, nullable=True)


class Enrollment(Base):
    __tablename__ = "enrollments"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    student_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    class_id = Column(String(36), ForeignKey("classes.id", ondelete="CASCADE"), nullable=False, index=True)
    roll_no = Column(String(50), nullable=False)
    enrolled_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    __table_args__ = (
        UniqueConstraint("class_id", "roll_no", name="uix_class_roll"),
    )


class ResultSchema(Base):
    __tablename__ = "result_schemas"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    name = Column(String(100), nullable=False, index=True)
    description = Column(Text, nullable=True)
    schema_definition = Column(JSON, nullable=False)
    created_by = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class Exam(Base):
    __tablename__ = "exams"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    title = Column(String(255), nullable=False)
    subject_id = Column(String(36), ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False, index=True)
    class_id = Column(String(36), ForeignKey("classes.id", ondelete="CASCADE"), nullable=False, index=True)
    total_marks = Column(Integer, nullable=False)
    scheduled_on = Column(String(50), nullable=True)
    complexity_tier = Column(String(50), default="standard")
    grading_rubric = Column(String(50), default="strict")
    rubric_notes = Column(Text, nullable=True)
    answer_key_id = Column(String(36), nullable=True)
    result_schema_id = Column(String(36), ForeignKey("result_schemas.id", ondelete="SET NULL"), nullable=True)
    status = Column(String(50), default="draft", nullable=False, index=True)
    created_by = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, nullable=True)


class AnswerKey(Base):
    __tablename__ = "answer_keys"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    exam_id = Column(String(36), ForeignKey("exams.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    question_paper_id = Column(String(36), nullable=True)
    questions = Column(JSON, default=list)
    included_page_refs = Column(JSON, default=list)
    excluded_page_refs = Column(JSON, default=list)
    sample_sheets = Column(JSON, default=list)
    source = Column(String(50), default="manual")
    source_file = Column(Text, nullable=True)
    extraction_status = Column(String(50), default="none")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class QuestionPaper(Base):
    __tablename__ = "question_papers"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    exam_id = Column(String(36), ForeignKey("exams.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    source_file = Column(Text, nullable=False)
    total_pages = Column(Integer, default=0)
    pages = Column(JSON, default=list)
    extracted_questions = Column(JSON, default=list)
    status = Column(String(50), default="pending_extraction", index=True)
    extraction_model = Column(String(100), nullable=True)
    warnings = Column(JSON, default=list)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, nullable=True)


class ExtractionTask(Base):
    __tablename__ = "extraction_tasks"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    exam_id = Column(String(36), ForeignKey("exams.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    status = Column(String(50), default="pending", index=True)
    total_pages = Column(Integer, default=0)
    processed_pages = Column(Integer, default=0)
    current_page = Column(Integer, default=0)
    current_step = Column(String(255), default="")
    questions_found_so_far = Column(Integer, default=0)
    error = Column(Text, nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)


class QuestionPaperCrop(Base):
    __tablename__ = "question_paper_crops"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    exam_id = Column(String(36), ForeignKey("exams.id", ondelete="CASCADE"), nullable=False, index=True)
    question_paper_id = Column(String(36), ForeignKey("question_papers.id", ondelete="CASCADE"), nullable=False)
    question_index = Column(Integer, nullable=False)
    q_no = Column(String(50), nullable=False)
    image_path = Column(Text, nullable=False)
    source_pdf = Column(Text, nullable=False)
    page_no = Column(Integer, nullable=False)
    bbox = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class AdditionalPdf(Base):
    __tablename__ = "additional_pdfs"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    exam_id = Column(String(36), ForeignKey("exams.id", ondelete="CASCADE"), nullable=False, index=True)
    source_file = Column(Text, nullable=False)
    label = Column(String(255), nullable=False)
    type = Column(String(50), default="reference")
    total_pages = Column(Integer, default=0)
    filename = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class UploadBatch(Base):
    __tablename__ = "upload_batches"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    exam_id = Column(String(36), ForeignKey("exams.id", ondelete="CASCADE"), nullable=False, index=True)
    uploaded_by = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    zip_filename = Column(String(255), nullable=False)
    total_pdfs = Column(Integer, default=0)
    processed_pdfs = Column(Integer, default=0)
    status = Column(String(50), default="extracting", index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class AnswerSheet(Base):
    __tablename__ = "answer_sheets"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    exam_id = Column(String(36), ForeignKey("exams.id", ondelete="CASCADE"), nullable=False, index=True)
    subject_id = Column(String(36), ForeignKey("subjects.id", ondelete="SET NULL"), nullable=True)
    student_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    student_name = Column(String(255), nullable=True)
    roll_no = Column(String(50), nullable=True)
    class_label = Column(String(100), nullable=True)
    original_filename = Column(String(255), nullable=False)
    original_pdf_path = Column(Text, nullable=True)
    page_count = Column(Integer, default=0)
    status = Column(String(50), default="pending_mapping", index=True)
    current_batch_id = Column(String(36), nullable=True)
    uploaded_by = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    batch_upload_id = Column(String(36), ForeignKey("upload_batches.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, nullable=True)


class SheetPage(Base):
    __tablename__ = "sheet_pages"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    sheet_id = Column(String(36), ForeignKey("answer_sheets.id", ondelete="CASCADE"), nullable=False, index=True)
    page_no = Column(Integer, nullable=False)
    image_path = Column(Text, nullable=False)
    width = Column(Integer, default=0)
    height = Column(Integer, default=0)
    is_deleted = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("sheet_id", "page_no", name="uix_sheet_page"),
    )


class BatchJob(Base):
    __tablename__ = "batch_jobs"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    exam_id = Column(String(36), ForeignKey("exams.id", ondelete="CASCADE"), nullable=False, index=True)
    provider = Column(String(50), default="gemini")
    model = Column(String(100), default="gemini-2.5-flash")
    provider_batch_id = Column(String(255), nullable=True, index=True)
    input_file_path = Column(Text, nullable=True)
    uploaded_jsonl_path = Column(Text, nullable=True)
    output_file_path = Column(Text, nullable=True)
    uploaded_gemini_files = Column(JSON, default=list)
    item_count = Column(Integer, default=0)
    completed_count = Column(Integer, default=0)
    failed_count = Column(Integer, default=0)
    status = Column(String(50), default="draft", index=True)
    upload_status = Column(JSON, nullable=True)
    submitted_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    last_polled_at = Column(DateTime, nullable=True)
    poll_error = Column(Text, nullable=True)
    created_by = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class BatchItem(Base):
    __tablename__ = "batch_items"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    batch_id = Column(String(36), ForeignKey("batch_jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    sheet_id = Column(String(36), ForeignKey("answer_sheets.id", ondelete="CASCADE"), nullable=False, index=True)
    custom_id = Column(String(255), nullable=False, index=True)
    prompt_preview = Column(Text, nullable=True)
    status = Column(String(50), default="pending")
    error = Column(Text, nullable=True)
    raw_response = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class Grading(Base):
    __tablename__ = "gradings"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    sheet_id = Column(String(36), ForeignKey("answer_sheets.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    exam_id = Column(String(36), ForeignKey("exams.id", ondelete="CASCADE"), nullable=False, index=True)
    batch_id = Column(String(36), ForeignKey("batch_jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    student_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    result_schema_id = Column(String(36), ForeignKey("result_schemas.id", ondelete="SET NULL"), nullable=True)
    result = Column(JSON, default=dict)
    total_awarded = Column(Float, default=0.0)
    total_max = Column(Float, default=0.0)
    status = Column(String(50), default="auto", index=True)
    reviewed_by = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    published_at = Column(DateTime, nullable=True)
    override_log = Column(JSON, default=list)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class ExamStudent(Base):
    __tablename__ = "exam_students"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    exam_id = Column(String(36), ForeignKey("exams.id", ondelete="CASCADE"), nullable=False, index=True)
    student_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    status = Column(String(50), default="active", index=True)  # active, removed
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, nullable=True)

    __table_args__ = (
        UniqueConstraint("exam_id", "student_id", name="uix_exam_student"),
    )
