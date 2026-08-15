from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
from typing import List, Optional
from datetime import datetime
import os
import uuid

from models.auth import UserResponse
from models.sheets import (
    ExamCreate, ExamUpdate, ExamResponse,
    AnswerKeyCreate, AnswerKeyUpdate, AnswerKeyResponse,
    QuestionItem, SampleSheetItem,
    ResultSchemaCreate, ResultSchemaUpdate, ResultSchemaResponse,
    AutoMatchRequest, StudentEnrollmentResponse, StudentDropdownItem,
    ExamStudentsSummary,
)
from core.deps import get_current_user, require_roles
from db.database import get_db
from db.models import Exam, AnswerKey, ResultSchema, Class, Subject
from core.config import settings
from services import enrollment_service
from services.auto_match_service import find_student_matches, apply_student_matches

router = APIRouter(
    prefix="/exams",
    tags=["exams"],
)

SAMPLE_RESULT_SCHEMA = {
    "name": "Standard Written Paper",
    "description": "Subjective paper with per-question marks + feedback",
    "schema_definition": {
        "type": "object",
        "required": ["student", "total_awarded", "total_max", "questions"],
        "properties": {
            "student": {
                "type": "object",
                "required": ["name", "roll_no", "class"],
                "properties": {
                    "name": {"type": "string", "description": "Student full name"},
                    "roll_no": {"type": "string", "description": "Roll number"},
                    "class": {"type": "string", "description": "Class/section"}
                }
            },
            "subject": {"type": "string", "description": "Subject name"},
            "exam_title": {"type": "string", "description": "Exam title"},
            "total_max": {"type": "number", "description": "Maximum possible marks"},
            "total_awarded": {"type": "number", "description": "Marks awarded"},
            "overall_feedback": {"type": "string", "description": "General feedback for the student"},
            "questions": {
                "type": "array",
                "description": "Per-question evaluation",
                "items": {
                    "type": "object",
                    "required": ["q_no", "awarded", "max"],
                    "properties": {
                        "q_no": {"type": "string", "description": "Question number/identifier"},
                        "awarded": {"type": "number", "minimum": 0, "description": "Marks awarded"},
                        "max": {"type": "number", "minimum": 0, "description": "Maximum marks for this question"},
                        "feedback": {"type": "string", "description": "Question-specific feedback"},
                        "page_refs": {
                            "type": "array",
                            "items": {"type": "integer"},
                            "description": "Page numbers where this question appears"
                        },
                        "confidence": {
                            "type": "number",
                            "minimum": 0,
                            "maximum": 1,
                            "description": "AI confidence score (0-1)"
                        }
                    }
                }
            }
        }
    }
}

# Result Schema Endpoints
@router.get("/result-schemas/", response_model=List[ResultSchemaResponse])
async def list_result_schemas(
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    res = await db.execute(select(ResultSchema).order_by(ResultSchema.created_at.desc()))
    schemas = res.scalars().all()
    return [
        ResultSchemaResponse(
            id=str(s.id),
            name=s.name,
            description=s.description,
            schema_definition=s.schema_definition or {},
            created_by=str(s.created_by) if s.created_by else None,
            created_at=s.created_at,
        )
        for s in schemas
    ]

@router.post("/result-schemas/", response_model=ResultSchemaResponse, status_code=status.HTTP_201_CREATED)
async def create_result_schema(
    schema_data: ResultSchemaCreate,
    current_user: UserResponse = Depends(require_roles("admin", "teacher")),
    db: AsyncSession = Depends(get_db)
):
    schema_obj = ResultSchema(
        name=schema_data.name,
        description=schema_data.description,
        schema_definition=schema_data.schema_definition,
        created_by=current_user.id,
        created_at=datetime.utcnow(),
    )
    db.add(schema_obj)
    await db.commit()
    await db.refresh(schema_obj)

    return ResultSchemaResponse(
        id=str(schema_obj.id),
        name=schema_obj.name,
        description=schema_obj.description,
        schema_definition=schema_obj.schema_definition,
        created_by=current_user.id,
        created_at=schema_obj.created_at,
    )

@router.get("/result-schemas/sample/")
async def get_sample_schema():
    return SAMPLE_RESULT_SCHEMA

@router.get("/result-schemas/{schema_id}/", response_model=ResultSchemaResponse)
async def get_result_schema(
    schema_id: str,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    res = await db.execute(select(ResultSchema).where(ResultSchema.id == schema_id))
    schema = res.scalar_one_or_none()
    if not schema:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Result schema not found")

    return ResultSchemaResponse(
        id=str(schema.id),
        name=schema.name,
        description=schema.description,
        schema_definition=schema.schema_definition or {},
        created_by=str(schema.created_by) if schema.created_by else None,
        created_at=schema.created_at,
    )

@router.patch("/result-schemas/{schema_id}/", response_model=ResultSchemaResponse)
async def update_result_schema(
    schema_id: str,
    update_data: ResultSchemaUpdate,
    current_user: UserResponse = Depends(require_roles("admin", "teacher")),
    db: AsyncSession = Depends(get_db)
):
    res = await db.execute(select(ResultSchema).where(ResultSchema.id == schema_id))
    schema = res.scalar_one_or_none()
    if not schema:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Result schema not found")

    update_dict = update_data.dict(exclude_unset=True)
    if "name" in update_dict:
        schema.name = update_dict["name"]
    if "description" in update_dict:
        schema.description = update_dict["description"]
    if "schema_definition" in update_dict:
        schema.schema_definition = update_dict["schema_definition"]

    await db.commit()
    await db.refresh(schema)

    return ResultSchemaResponse(
        id=str(schema.id),
        name=schema.name,
        description=schema.description,
        schema_definition=schema.schema_definition,
        created_by=str(schema.created_by) if schema.created_by else None,
        created_at=schema.created_at,
    )

@router.delete("/result-schemas/{schema_id}/", status_code=status.HTTP_204_NO_CONTENT)
async def delete_result_schema(
    schema_id: str,
    current_user: UserResponse = Depends(require_roles("admin")),
    db: AsyncSession = Depends(get_db)
):
    res = await db.execute(select(ResultSchema).where(ResultSchema.id == schema_id))
    schema = res.scalar_one_or_none()
    if not schema:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Result schema not found")

    await db.delete(schema)
    await db.execute(update(Exam).where(Exam.result_schema_id == schema_id).values(result_schema_id=None))
    await db.commit()

@router.get("/{exam_id}/result-schema/", response_model=Optional[ResultSchemaResponse])
async def get_exam_result_schema(
    exam_id: str,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    res = await db.execute(select(Exam).where(Exam.id == exam_id))
    exam = res.scalar_one_or_none()
    if not exam:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exam not found")

    if not exam.result_schema_id:
        return None

    res = await db.execute(select(ResultSchema).where(ResultSchema.id == exam.result_schema_id))
    schema = res.scalar_one_or_none()
    if not schema:
        return None

    return ResultSchemaResponse(
        id=str(schema.id),
        name=schema.name,
        description=schema.description,
        schema_definition=schema.schema_definition or {},
        created_by=str(schema.created_by) if schema.created_by else None,
        created_at=schema.created_at,
    )

@router.post("/{exam_id}/result-schema/", response_model=ResultSchemaResponse, status_code=status.HTTP_201_CREATED)
async def create_and_link_exam_result_schema(
    exam_id: str,
    schema_data: ResultSchemaCreate,
    current_user: UserResponse = Depends(require_roles("admin", "teacher")),
    db: AsyncSession = Depends(get_db)
):
    res = await db.execute(select(Exam).where(Exam.id == exam_id))
    exam = res.scalar_one_or_none()
    if not exam:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exam not found")

    schema_obj = ResultSchema(
        name=schema_data.name,
        description=schema_data.description,
        schema_definition=schema_data.schema_definition,
        created_by=current_user.id,
        created_at=datetime.utcnow(),
    )
    db.add(schema_obj)
    await db.commit()
    await db.refresh(schema_obj)

    exam.result_schema_id = schema_obj.id
    exam.updated_at = datetime.utcnow()
    await db.commit()

    return ResultSchemaResponse(
        id=str(schema_obj.id),
        name=schema_obj.name,
        description=schema_obj.description,
        schema_definition=schema_obj.schema_definition,
        created_by=current_user.id,
        created_at=schema_obj.created_at,
    )

# Exam CRUD
@router.get("/", response_model=List[ExamResponse])
async def list_exams(
    class_id: Optional[str] = None,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    query = select(Exam)
    if class_id:
        query = query.where(Exam.class_id == class_id)

    res = await db.execute(query.order_by(Exam.created_at.desc()))
    exams = res.scalars().all()

    return [
        ExamResponse(
            id=str(e.id),
            title=e.title,
            subject_id=e.subject_id,
            class_id=e.class_id,
            total_marks=e.total_marks,
            scheduled_on=e.scheduled_on,
            complexity_tier=e.complexity_tier or "standard",
            grading_rubric=e.grading_rubric or "strict",
            rubric_notes=e.rubric_notes,
            answer_key_id=str(e.answer_key_id) if e.answer_key_id else None,
            result_schema_id=str(e.result_schema_id) if e.result_schema_id else None,
            status=e.status or "draft",
            created_by=str(e.created_by) if e.created_by else None,
            created_at=e.created_at,
            updated_at=e.updated_at,
        )
        for e in exams
    ]

@router.get("/{exam_id}/", response_model=ExamResponse)
async def get_exam(
    exam_id: str,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    res = await db.execute(select(Exam).where(Exam.id == exam_id))
    exam = res.scalar_one_or_none()
    if not exam:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exam not found")

    return ExamResponse(
        id=str(exam.id),
        title=exam.title,
        subject_id=exam.subject_id,
        class_id=exam.class_id,
        total_marks=exam.total_marks,
        scheduled_on=exam.scheduled_on,
        complexity_tier=exam.complexity_tier or "standard",
        grading_rubric=exam.grading_rubric or "strict",
        rubric_notes=exam.rubric_notes,
        answer_key_id=str(exam.answer_key_id) if exam.answer_key_id else None,
        result_schema_id=str(exam.result_schema_id) if exam.result_schema_id else None,
        status=exam.status or "draft",
        created_by=str(exam.created_by) if exam.created_by else None,
        created_at=exam.created_at,
        updated_at=exam.updated_at,
    )

@router.post("/", response_model=ExamResponse, status_code=status.HTTP_201_CREATED)
async def create_exam(
    exam_data: ExamCreate,
    current_user: UserResponse = Depends(require_roles("admin", "teacher")),
    db: AsyncSession = Depends(get_db)
):
    res = await db.execute(select(Class).where(Class.id == exam_data.class_id))
    if not res.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Class not found")

    res = await db.execute(select(Subject).where(Subject.id == exam_data.subject_id, Subject.class_id == exam_data.class_id))
    if not res.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Subject not found for this class")

    exam_obj = Exam(
        title=exam_data.title,
        subject_id=exam_data.subject_id,
        class_id=exam_data.class_id,
        total_marks=exam_data.total_marks,
        scheduled_on=exam_data.scheduled_on,
        complexity_tier=exam_data.complexity_tier,
        grading_rubric=exam_data.grading_rubric,
        rubric_notes=exam_data.rubric_notes,
        answer_key_id=exam_data.answer_key_id if exam_data.answer_key_id else None,
        result_schema_id=exam_data.result_schema_id if exam_data.result_schema_id else None,
        status="draft",
        created_by=current_user.id,
        created_at=datetime.utcnow(),
    )
    db.add(exam_obj)
    await db.commit()
    await db.refresh(exam_obj)

    await enrollment_service.populate_exam_students(str(exam_obj.id), exam_data.class_id)

    return ExamResponse(
        id=str(exam_obj.id),
        title=exam_obj.title,
        subject_id=exam_obj.subject_id,
        class_id=exam_obj.class_id,
        total_marks=exam_obj.total_marks,
        scheduled_on=exam_obj.scheduled_on,
        complexity_tier=exam_obj.complexity_tier or "standard",
        grading_rubric=exam_obj.grading_rubric or "strict",
        rubric_notes=exam_obj.rubric_notes,
        answer_key_id=str(exam_obj.answer_key_id) if exam_obj.answer_key_id else None,
        result_schema_id=str(exam_obj.result_schema_id) if exam_obj.result_schema_id else None,
        status=exam_obj.status,
        created_by=current_user.id,
        created_at=exam_obj.created_at,
        updated_at=exam_obj.updated_at,
    )

@router.patch("/{exam_id}/", response_model=ExamResponse)
async def update_exam(
    exam_id: str,
    update_data: ExamUpdate,
    current_user: UserResponse = Depends(require_roles("admin", "teacher")),
    db: AsyncSession = Depends(get_db)
):
    res = await db.execute(select(Exam).where(Exam.id == exam_id))
    exam = res.scalar_one_or_none()
    if not exam:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exam not found")

    update_dict = update_data.dict(exclude_unset=True)
    if "title" in update_dict:
        exam.title = update_dict["title"]
    if "subject_id" in update_dict:
        exam.subject_id = update_dict["subject_id"]
    if "class_id" in update_dict:
        exam.class_id = update_dict["class_id"]
    if "total_marks" in update_dict:
        exam.total_marks = update_dict["total_marks"]
    if "scheduled_on" in update_dict:
        exam.scheduled_on = update_dict["scheduled_on"]
    if "complexity_tier" in update_dict:
        exam.complexity_tier = update_dict["complexity_tier"]
    if "grading_rubric" in update_dict:
        exam.grading_rubric = update_dict["grading_rubric"]
    if "rubric_notes" in update_dict:
        exam.rubric_notes = update_dict["rubric_notes"]
    if "answer_key_id" in update_dict:
        exam.answer_key_id = update_dict["answer_key_id"]
    if "result_schema_id" in update_dict:
        exam.result_schema_id = update_dict["result_schema_id"]
    if "status" in update_dict and update_dict["status"]:
        exam.status = update_dict["status"]

    exam.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(exam)

    return ExamResponse(
        id=str(exam.id),
        title=exam.title,
        subject_id=exam.subject_id,
        class_id=exam.class_id,
        total_marks=exam.total_marks,
        scheduled_on=exam.scheduled_on,
        complexity_tier=exam.complexity_tier or "standard",
        grading_rubric=exam.grading_rubric or "strict",
        rubric_notes=exam.rubric_notes,
        answer_key_id=str(exam.answer_key_id) if exam.answer_key_id else None,
        result_schema_id=str(exam.result_schema_id) if exam.result_schema_id else None,
        status=exam.status,
        created_by=str(exam.created_by) if exam.created_by else None,
        created_at=exam.created_at,
        updated_at=exam.updated_at,
    )

@router.delete("/{exam_id}/", status_code=status.HTTP_204_NO_CONTENT)
async def delete_exam(
    exam_id: str,
    current_user: UserResponse = Depends(require_roles("admin")),
    db: AsyncSession = Depends(get_db)
):
    res = await db.execute(select(Exam).where(Exam.id == exam_id))
    exam = res.scalar_one_or_none()
    if not exam:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exam not found")

    await db.delete(exam)
    await db.commit()

# Answer Key Endpoints
@router.post("/{exam_id}/answer-key/", response_model=AnswerKeyResponse, status_code=status.HTTP_201_CREATED)
async def create_or_update_answer_key(
    exam_id: str,
    key_data: AnswerKeyCreate,
    current_user: UserResponse = Depends(require_roles("admin", "teacher")),
    db: AsyncSession = Depends(get_db)
):
    res = await db.execute(select(Exam).where(Exam.id == exam_id))
    exam = res.scalar_one_or_none()
    if not exam:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exam not found")

    key_res = await db.execute(select(AnswerKey).where(AnswerKey.exam_id == exam_id))
    existing_key = key_res.scalar_one_or_none()

    questions_list = [q.dict() for q in key_data.questions]
    samples_list = [s.dict() for s in key_data.sample_sheets]

    if existing_key:
        existing_key.questions = questions_list
        existing_key.question_paper_id = key_data.question_paper_id
        existing_key.included_page_refs = key_data.included_page_refs
        existing_key.excluded_page_refs = key_data.excluded_page_refs
        existing_key.sample_sheets = samples_list
        existing_key.source = key_data.source
        existing_key.source_file = key_data.source_file
        existing_key.extraction_status = key_data.extraction_status
        key_obj = existing_key
    else:
        key_obj = AnswerKey(
            exam_id=exam_id,
            questions=questions_list,
            question_paper_id=key_data.question_paper_id,
            included_page_refs=key_data.included_page_refs,
            excluded_page_refs=key_data.excluded_page_refs,
            sample_sheets=samples_list,
            source=key_data.source,
            source_file=key_data.source_file,
            extraction_status=key_data.extraction_status,
            created_at=datetime.utcnow(),
        )
        db.add(key_obj)

    await db.commit()
    await db.refresh(key_obj)

    exam.answer_key_id = key_obj.id
    exam.updated_at = datetime.utcnow()
    await db.commit()

    return AnswerKeyResponse(
        id=str(key_obj.id),
        exam_id=exam_id,
        questions=key_data.questions,
        question_paper_id=key_data.question_paper_id,
        included_page_refs=key_data.included_page_refs,
        excluded_page_refs=key_data.excluded_page_refs,
        sample_sheets=key_data.sample_sheets,
        source=key_obj.source or "manual",
        source_file=key_obj.source_file,
        extraction_status=key_obj.extraction_status or "none",
        created_at=key_obj.created_at,
    )

@router.get("/{exam_id}/answer-key/", response_model=Optional[AnswerKeyResponse])
async def get_answer_key(
    exam_id: str,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    res = await db.execute(select(AnswerKey).where(AnswerKey.exam_id == exam_id))
    key = res.scalar_one_or_none()
    if not key:
        return None

    return AnswerKeyResponse(
        id=str(key.id),
        exam_id=str(key.exam_id),
        questions=key.questions or [],
        question_paper_id=str(key.question_paper_id) if key.question_paper_id else None,
        included_page_refs=key.included_page_refs or [],
        excluded_page_refs=key.excluded_page_refs or [],
        sample_sheets=key.sample_sheets or [],
        source=key.source or "manual",
        source_file=key.source_file,
        extraction_status=key.extraction_status or "none",
        created_at=key.created_at,
    )

# Sample Sheets Endpoints
@router.post("/{exam_id}/sample-sheets/", status_code=status.HTTP_201_CREATED)
async def upload_sample_sheet(
    exam_id: str,
    file: UploadFile = File(...),
    label: str = Form(...),
    notes: Optional[str] = Form(None),
    current_user: UserResponse = Depends(require_roles("admin", "teacher")),
    db: AsyncSession = Depends(get_db)
):
    res = await db.execute(select(Exam).where(Exam.id == exam_id))
    if not res.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exam not found")

    storage_dir = os.path.join(settings.STORAGE_PATH, "samples", exam_id)
    os.makedirs(storage_dir, exist_ok=True)

    ext = os.path.splitext(file.filename or "")[1] or ".bin"
    unique_name = f"sample_{uuid.uuid4().hex[:8]}{ext}"
    file_path = os.path.join(storage_dir, unique_name)

    with open(file_path, "wb") as f:
        content = await file.read()
        f.write(content)

    file_ext = ext.lower()
    kind = "pdf" if file_ext == ".pdf" else ("image" if file_ext in [".png", ".jpg", ".jpeg", ".gif", ".webp"] else "text")

    sample_dict = {"kind": kind, "path": file_path, "label": label, "notes": notes}

    key_res = await db.execute(select(AnswerKey).where(AnswerKey.exam_id == exam_id))
    key = key_res.scalar_one_or_none()
    if key:
        samples = list(key.sample_sheets or [])
        samples.append(sample_dict)
        key.sample_sheets = samples
    else:
        key = AnswerKey(
            exam_id=exam_id,
            sample_sheets=[sample_dict],
            created_at=datetime.utcnow(),
        )
        db.add(key)

    await db.commit()
    return {"message": "Sample sheet uploaded", "path": file_path, "kind": kind}

@router.get("/{exam_id}/sample-sheets/", response_model=List[SampleSheetItem])
async def list_sample_sheets(
    exam_id: str,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    key_res = await db.execute(select(AnswerKey).where(AnswerKey.exam_id == exam_id))
    key = key_res.scalar_one_or_none()
    if not key or not key.sample_sheets:
        return []
    return [SampleSheetItem(**s) for s in key.sample_sheets]

@router.delete("/{exam_id}/sample-sheets/{sample_index}/", status_code=status.HTTP_204_NO_CONTENT)
async def delete_sample_sheet(
    exam_id: str,
    sample_index: int,
    current_user: UserResponse = Depends(require_roles("admin", "teacher")),
    db: AsyncSession = Depends(get_db)
):
    key_res = await db.execute(select(AnswerKey).where(AnswerKey.exam_id == exam_id))
    key = key_res.scalar_one_or_none()
    if not key or not key.sample_sheets:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sample sheet not found")

    samples = list(key.sample_sheets)
    if sample_index < 0 or sample_index >= len(samples):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sample sheet not found")

    removed = samples.pop(sample_index)
    key.sample_sheets = samples
    await db.commit()

    if "path" in removed and os.path.exists(removed["path"]):
        os.remove(removed["path"])

# Exam-Student Enrollment Endpoints
@router.post("/{exam_id}/sync-students/")
async def sync_exam_students_endpoint(
    exam_id: str,
    current_user: UserResponse = Depends(require_roles("admin", "teacher")),
    db: AsyncSession = Depends(get_db)
):
    res = await db.execute(select(Exam).where(Exam.id == exam_id))
    exam = res.scalar_one_or_none()
    if not exam:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exam not found")

    result = await enrollment_service.sync_exam_students(exam_id, exam.class_id)
    return {"message": "Students synced", **result}

@router.get("/{exam_id}/students/")
async def list_exam_students(
    exam_id: str,
    status_filter: Optional[str] = None,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    students = await enrollment_service.get_exam_students(exam_id, include_sheet_status=True)
    if status_filter:
        students = [s for s in students if s["enrollment_status"] == status_filter]
    return students

@router.get("/{exam_id}/students/summary/", response_model=ExamStudentsSummary)
async def get_exam_students_summary_endpoint(
    exam_id: str,
    current_user: UserResponse = Depends(get_current_user)
):
    return await enrollment_service.get_exam_students_summary(exam_id)

@router.get("/{exam_id}/students/dropdown/", response_model=List[StudentDropdownItem])
async def get_exam_students_dropdown(
    exam_id: str,
    current_user: UserResponse = Depends(get_current_user)
):
    return await enrollment_service.get_enrolled_students_for_dropdown(exam_id)
