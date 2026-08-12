from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from typing import List, Optional
from datetime import datetime
import bson
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
from db.database import (
    exams_collection, answer_keys_collection, result_schemas_collection,
    classes_collection, subjects_collection,
)
from core.config import settings
from services import enrollment_service
from services.auto_match_service import find_student_matches, apply_student_matches
from models.sheets import (
    AutoMatchRequest, StudentEnrollmentResponse, StudentDropdownItem,
    ExamStudentsSummary,
)

router = APIRouter(
    prefix="/exams",
    tags=["exams"],
)


# ============================================================
# Result Schema Endpoints (static routes — MUST come before /{exam_id})
# ============================================================

@router.get("/result-schemas/", response_model=List[ResultSchemaResponse])
async def list_result_schemas(
    current_user: UserResponse = Depends(get_current_user)
):
    schemas = await result_schemas_collection.find({}).sort("created_at", -1).to_list(length=None)
    return [
        ResultSchemaResponse(
            id=str(s["_id"]),
            name=s["name"],
            description=s.get("description"),
            schema_definition=s["schema_definition"],
            created_by=str(s["created_by"]) if s.get("created_by") else None,
            created_at=s["created_at"],
        )
        for s in schemas
    ]


@router.post("/result-schemas/", response_model=ResultSchemaResponse, status_code=status.HTTP_201_CREATED)
async def create_result_schema(
    schema_data: ResultSchemaCreate,
    current_user: UserResponse = Depends(require_roles("admin", "teacher"))
):
    schema_doc = {
        "name": schema_data.name,
        "description": schema_data.description,
        "schema_definition": schema_data.schema_definition,
        "created_by": bson.ObjectId(current_user.id),
        "created_at": datetime.utcnow(),
    }
    result = await result_schemas_collection.insert_one(schema_doc)
    return ResultSchemaResponse(
        id=str(result.inserted_id),
        name=schema_doc["name"],
        description=schema_doc.get("description"),
        schema_definition=schema_doc["schema_definition"],
        created_by=current_user.id,
        created_at=schema_doc["created_at"],
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


@router.get("/result-schemas/sample/")
async def get_sample_schema():
    return SAMPLE_RESULT_SCHEMA


@router.patch("/result-schemas/{schema_id}/", response_model=ResultSchemaResponse)
async def update_result_schema(
    schema_id: str,
    update_data: ResultSchemaUpdate,
    current_user: UserResponse = Depends(require_roles("admin", "teacher"))
):
    schema = await result_schemas_collection.find_one({"_id": bson.ObjectId(schema_id)})
    if not schema:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Result schema not found")

    update_dict = update_data.dict(exclude_unset=True)
    if not update_dict:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No update data provided")

    result = await result_schemas_collection.find_one_and_update(
        {"_id": bson.ObjectId(schema_id)},
        {"$set": update_dict},
        return_document=True
    )

    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Result schema not found")

    return ResultSchemaResponse(
        id=str(result["_id"]),
        name=result["name"],
        description=result.get("description"),
        schema_definition=result["schema_definition"],
        created_by=str(result["created_by"]) if result.get("created_by") else None,
        created_at=result["created_at"],
    )


@router.delete("/result-schemas/{schema_id}/", status_code=status.HTTP_204_NO_CONTENT)
async def delete_result_schema(
    schema_id: str,
    current_user: UserResponse = Depends(require_roles("admin"))
):
    result = await result_schemas_collection.delete_one({"_id": bson.ObjectId(schema_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Result schema not found")

    await exams_collection.update_many(
        {"result_schema_id": bson.ObjectId(schema_id)},
        {"$set": {"result_schema_id": None, "updated_at": datetime.utcnow()}}
    )


# ============================================================
# Exam CRUD
# ============================================================

@router.get("/", response_model=List[ExamResponse])
async def list_exams(
    class_id: Optional[str] = None,
    current_user: UserResponse = Depends(get_current_user)
):
    query = {}
    if class_id:
        query["class_id"] = class_id

    if current_user.role == "teacher":
        teacher_classes = await classes_collection.find({"teacher_ids": current_user.id}).to_list(length=None)
        class_ids = [str(c["_id"]) for c in teacher_classes]
        if class_id:
            if class_id not in class_ids:
                return []
            query["class_id"] = class_id
        else:
            query["class_id"] = {"$in": class_ids}

    exams = await exams_collection.find(query).sort("created_at", -1).to_list(length=None)
    return [
        ExamResponse(
            id=str(e["_id"]),
            title=e["title"],
            subject_id=e["subject_id"],
            class_id=e["class_id"],
            total_marks=e["total_marks"],
            scheduled_on=e.get("scheduled_on"),
            complexity_tier=e.get("complexity_tier", "standard"),
            grading_rubric=e.get("grading_rubric", "strict"),
            rubric_notes=e.get("rubric_notes"),
            answer_key_id=str(e["answer_key_id"]) if e.get("answer_key_id") else None,
            result_schema_id=str(e["result_schema_id"]) if e.get("result_schema_id") else None,
            status=e.get("status", "draft"),
            created_by=str(e["created_by"]) if e.get("created_by") else None,
            created_at=e["created_at"],
            updated_at=e.get("updated_at"),
        )
        for e in exams
    ]


@router.get("/{exam_id}/", response_model=ExamResponse)
async def get_exam(
    exam_id: str,
    current_user: UserResponse = Depends(get_current_user)
):
    exam = await exams_collection.find_one({"_id": bson.ObjectId(exam_id)})
    if not exam:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exam not found")

    if current_user.role == "teacher":
        cls = await classes_collection.find_one({"_id": bson.ObjectId(exam["class_id"])})
        if not cls or current_user.id not in cls.get("teacher_ids", []):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

    return ExamResponse(
        id=str(exam["_id"]),
        title=exam["title"],
        subject_id=exam["subject_id"],
        class_id=exam["class_id"],
        total_marks=exam["total_marks"],
        scheduled_on=exam.get("scheduled_on"),
        complexity_tier=exam.get("complexity_tier", "standard"),
        grading_rubric=exam.get("grading_rubric", "strict"),
        rubric_notes=exam.get("rubric_notes"),
        answer_key_id=str(exam["answer_key_id"]) if exam.get("answer_key_id") else None,
        result_schema_id=str(exam["result_schema_id"]) if exam.get("result_schema_id") else None,
        status=exam.get("status", "draft"),
        created_by=str(exam["created_by"]) if exam.get("created_by") else None,
        created_at=exam["created_at"],
        updated_at=exam.get("updated_at"),
    )


@router.post("/", response_model=ExamResponse, status_code=status.HTTP_201_CREATED)
async def create_exam(
    exam_data: ExamCreate,
    current_user: UserResponse = Depends(require_roles("admin", "teacher"))
):
    existing_class = await classes_collection.find_one({"_id": bson.ObjectId(exam_data.class_id)})
    if not existing_class:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Class not found")

    existing_subject = await subjects_collection.find_one({
        "_id": bson.ObjectId(exam_data.subject_id),
        "class_id": exam_data.class_id,
    })
    if not existing_subject:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Subject not found for this class")

    if current_user.role == "teacher":
        if current_user.id not in existing_class.get("teacher_ids", []):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to create exams for this class"
            )

    exam_doc = {
        "title": exam_data.title,
        "subject_id": exam_data.subject_id,
        "class_id": exam_data.class_id,
        "total_marks": exam_data.total_marks,
        "scheduled_on": exam_data.scheduled_on,
        "complexity_tier": exam_data.complexity_tier,
        "grading_rubric": exam_data.grading_rubric,
        "rubric_notes": exam_data.rubric_notes,
        "answer_key_id": bson.ObjectId(exam_data.answer_key_id) if exam_data.answer_key_id else None,
        "result_schema_id": bson.ObjectId(exam_data.result_schema_id) if exam_data.result_schema_id else None,
        "status": "draft",
        "created_by": bson.ObjectId(current_user.id),
        "created_at": datetime.utcnow(),
        "updated_at": None,
    }

    result = await exams_collection.insert_one(exam_doc)

    await enrollment_service.populate_exam_students(str(result.inserted_id), exam_data.class_id)

    return ExamResponse(
        id=str(result.inserted_id),
        title=exam_doc["title"],
        subject_id=exam_doc["subject_id"],
        class_id=exam_doc["class_id"],
        total_marks=exam_doc["total_marks"],
        scheduled_on=exam_doc.get("scheduled_on"),
        complexity_tier=exam_doc.get("complexity_tier", "standard"),
        grading_rubric=exam_doc["grading_rubric"],
        rubric_notes=exam_doc.get("rubric_notes"),
        answer_key_id=str(exam_doc["answer_key_id"]) if exam_doc["answer_key_id"] else None,
        result_schema_id=str(exam_doc["result_schema_id"]) if exam_doc["result_schema_id"] else None,
        status=exam_doc["status"],
        created_by=current_user.id,
        created_at=exam_doc["created_at"],
        updated_at=exam_doc["updated_at"],
    )


@router.patch("/{exam_id}/", response_model=ExamResponse)
async def update_exam(
    exam_id: str,
    update_data: ExamUpdate,
    current_user: UserResponse = Depends(require_roles("admin", "teacher"))
):
    exam = await exams_collection.find_one({"_id": bson.ObjectId(exam_id)})
    if not exam:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exam not found")

    if current_user.role == "teacher":
        cls = await classes_collection.find_one({"_id": bson.ObjectId(exam["class_id"])})
        if not cls or current_user.id not in cls.get("teacher_ids", []):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

    update_dict = update_data.dict(exclude_unset=True)
    if not update_dict:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No update data provided")

    if "answer_key_id" in update_dict and update_dict["answer_key_id"]:
        update_dict["answer_key_id"] = bson.ObjectId(update_dict["answer_key_id"])
    else:
        update_dict["answer_key_id"] = None

    if "result_schema_id" in update_dict and update_dict["result_schema_id"]:
        update_dict["result_schema_id"] = bson.ObjectId(update_dict["result_schema_id"])
    else:
        update_dict["result_schema_id"] = None

    class_id_changed = "class_id" in update_dict
    old_class_id = exam.get("class_id")

    update_dict["updated_at"] = datetime.utcnow()

    result = await exams_collection.find_one_and_update(
        {"_id": bson.ObjectId(exam_id)},
        {"$set": update_dict},
        return_document=True
    )

    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exam not found")

    if class_id_changed and result.get("class_id"):
        await enrollment_service.sync_exam_students(exam_id, result["class_id"])

    return ExamResponse(
        id=str(result["_id"]),
        title=result["title"],
        subject_id=result["subject_id"],
        class_id=result["class_id"],
        total_marks=result["total_marks"],
        scheduled_on=result.get("scheduled_on"),
        complexity_tier=result.get("complexity_tier", "standard"),
        grading_rubric=result.get("grading_rubric", "strict"),
        rubric_notes=result.get("rubric_notes"),
        answer_key_id=str(result["answer_key_id"]) if result.get("answer_key_id") else None,
        result_schema_id=str(result["result_schema_id"]) if result.get("result_schema_id") else None,
        status=result.get("status", "draft"),
        created_by=str(result["created_by"]) if result.get("created_by") else None,
        created_at=result["created_at"],
        updated_at=result.get("updated_at"),
    )


@router.delete("/{exam_id}/", status_code=status.HTTP_204_NO_CONTENT)
async def delete_exam(
    exam_id: str,
    current_user: UserResponse = Depends(require_roles("admin"))
):
    result = await exams_collection.delete_one({"_id": bson.ObjectId(exam_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exam not found")


# ============================================================
# Answer Key Endpoints
# ============================================================

@router.post("/{exam_id}/answer-key/", response_model=AnswerKeyResponse, status_code=status.HTTP_201_CREATED)
async def create_or_update_answer_key(
    exam_id: str,
    key_data: AnswerKeyCreate,
    current_user: UserResponse = Depends(require_roles("admin", "teacher"))
):
    exam = await exams_collection.find_one({"_id": bson.ObjectId(exam_id)})
    if not exam:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exam not found")

    if current_user.role == "teacher":
        cls = await classes_collection.find_one({"_id": bson.ObjectId(exam["class_id"])})
        if not cls or current_user.id not in cls.get("teacher_ids", []):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

    existing_key = await answer_keys_collection.find_one({"exam_id": bson.ObjectId(exam_id)})

    key_dict = {
        "exam_id": bson.ObjectId(exam_id),
        "questions": [q.dict() for q in key_data.questions],
        "question_paper_id": bson.ObjectId(key_data.question_paper_id) if key_data.question_paper_id else None,
        "included_page_refs": key_data.included_page_refs,
        "excluded_page_refs": key_data.excluded_page_refs,
        "sample_sheets": [s.dict() for s in key_data.sample_sheets],
        "source": key_data.source,
        "source_file": key_data.source_file,
        "extraction_status": key_data.extraction_status,
        "created_at": datetime.utcnow(),
    }

    if existing_key:
        await answer_keys_collection.update_one(
            {"_id": existing_key["_id"]},
            {"$set": key_dict}
        )
        key_dict["_id"] = existing_key["_id"]

        await exams_collection.update_one(
            {"_id": bson.ObjectId(exam_id)},
            {"$set": {"answer_key_id": existing_key["_id"], "updated_at": datetime.utcnow()}}
        )
    else:
        result = await answer_keys_collection.insert_one(key_dict)
        key_dict["_id"] = result.inserted_id

        await exams_collection.update_one(
            {"_id": bson.ObjectId(exam_id)},
            {"$set": {"answer_key_id": result.inserted_id, "updated_at": datetime.utcnow()}}
        )

    return AnswerKeyResponse(
        id=str(key_dict["_id"]),
        exam_id=exam_id,
        questions=key_data.questions,
        question_paper_id=key_data.question_paper_id,
        included_page_refs=key_data.included_page_refs,
        excluded_page_refs=key_data.excluded_page_refs,
        sample_sheets=key_data.sample_sheets,
        source=key_dict["source"],
        source_file=key_dict["source_file"],
        extraction_status=key_dict["extraction_status"],
        created_at=key_dict["created_at"],
    )


@router.get("/{exam_id}/answer-key/", response_model=Optional[AnswerKeyResponse])
async def get_answer_key(
    exam_id: str,
    current_user: UserResponse = Depends(get_current_user)
):
    exam = await exams_collection.find_one({"_id": bson.ObjectId(exam_id)})
    if not exam:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exam not found")

    if current_user.role == "teacher":
        cls = await classes_collection.find_one({"_id": bson.ObjectId(exam["class_id"])})
        if not cls or current_user.id not in cls.get("teacher_ids", []):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

    key = await answer_keys_collection.find_one({"exam_id": bson.ObjectId(exam_id)})
    if not key:
        return None

    return AnswerKeyResponse(
        id=str(key["_id"]),
        exam_id=str(key["exam_id"]),
        questions=key.get("questions", []),
        question_paper_id=str(key["question_paper_id"]) if key.get("question_paper_id") else None,
        included_page_refs=key.get("included_page_refs", []),
        excluded_page_refs=key.get("excluded_page_refs", []),
        sample_sheets=key.get("sample_sheets", []),
        source=key.get("source", "manual"),
        source_file=key.get("source_file"),
        extraction_status=key.get("extraction_status", "none"),
        created_at=key["created_at"],
    )


@router.post("/{exam_id}/answer-key/upload-pdf/", response_model=AnswerKeyResponse, status_code=status.HTTP_201_CREATED)
async def upload_answer_key_pdf(
    exam_id: str,
    file: UploadFile = File(...),
    current_user: UserResponse = Depends(require_roles("admin", "teacher"))
):
    exam = await exams_collection.find_one({"_id": bson.ObjectId(exam_id)})
    if not exam:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exam not found")

    if current_user.role == "teacher":
        cls = await classes_collection.find_one({"_id": bson.ObjectId(exam["class_id"])})
        if not cls or current_user.id not in cls.get("teacher_ids", []):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

    storage_dir = os.path.join(settings.STORAGE_PATH, "answer_keys", exam_id)
    os.makedirs(storage_dir, exist_ok=True)

    file_path = os.path.join(storage_dir, "key.pdf")
    with open(file_path, "wb") as f:
        content = await file.read()
        f.write(content)

    key_doc = {
        "exam_id": bson.ObjectId(exam_id),
        "questions": [],
        "question_paper_id": None,
        "included_page_refs": [],
        "excluded_page_refs": [],
        "sample_sheets": [],
        "source": "pdf_extracted",
        "source_file": file_path,
        "extraction_status": "none",
        "created_at": datetime.utcnow(),
    }

    result = await answer_keys_collection.insert_one(key_doc)

    await exams_collection.update_one(
        {"_id": bson.ObjectId(exam_id)},
        {"$set": {"answer_key_id": result.inserted_id, "updated_at": datetime.utcnow()}}
    )

    return AnswerKeyResponse(
        id=str(result.inserted_id),
        exam_id=exam_id,
        questions=[],
        question_paper_id=None,
        included_page_refs=[],
        excluded_page_refs=[],
        sample_sheets=[],
        source="pdf_extracted",
        source_file=file_path,
        extraction_status="none",
        created_at=key_doc["created_at"],
    )


# ============================================================
# Sample Sheets Endpoints
# ============================================================

@router.post("/{exam_id}/sample-sheets/", status_code=status.HTTP_201_CREATED)
async def upload_sample_sheet(
    exam_id: str,
    file: UploadFile = File(...),
    label: str = Form(...),
    notes: Optional[str] = Form(None),
    current_user: UserResponse = Depends(require_roles("admin", "teacher"))
):
    exam = await exams_collection.find_one({"_id": bson.ObjectId(exam_id)})
    if not exam:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exam not found")

    if current_user.role == "teacher":
        cls = await classes_collection.find_one({"_id": bson.ObjectId(exam["class_id"])})
        if not cls or current_user.id not in cls.get("teacher_ids", []):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

    storage_dir = os.path.join(settings.STORAGE_PATH, "samples", exam_id)
    os.makedirs(storage_dir, exist_ok=True)

    ext = os.path.splitext(file.filename or "")[1] or ".bin"
    unique_name = f"sample_{uuid.uuid4().hex[:8]}{ext}"
    file_path = os.path.join(storage_dir, unique_name)

    with open(file_path, "wb") as f:
        content = await file.read()
        f.write(content)

    file_ext = ext.lower()
    if file_ext in [".pdf"]:
        kind = "pdf"
    elif file_ext in [".png", ".jpg", ".jpeg", ".gif", ".webp"]:
        kind = "image"
    else:
        kind = "text"

    sample_item = SampleSheetItem(
        kind=kind,
        path=file_path,
        label=label,
        notes=notes,
    )

    await answer_keys_collection.update_one(
        {"exam_id": bson.ObjectId(exam_id)},
        {
            "$push": {"sample_sheets": sample_item.dict()},
            "$setOnInsert": {
                "exam_id": bson.ObjectId(exam_id),
                "questions": [],
                "question_paper_id": None,
                "included_page_refs": [],
                "excluded_page_refs": [],
                "source": "manual",
                "source_file": None,
                "extraction_status": "none",
                "created_at": datetime.utcnow(),
            }
        },
        upsert=True
    )

    return {"message": "Sample sheet uploaded", "path": file_path, "kind": kind}


@router.get("/{exam_id}/sample-sheets/", response_model=List[SampleSheetItem])
async def list_sample_sheets(
    exam_id: str,
    current_user: UserResponse = Depends(get_current_user)
):
    exam = await exams_collection.find_one({"_id": bson.ObjectId(exam_id)})
    if not exam:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exam not found")

    if current_user.role == "teacher":
        cls = await classes_collection.find_one({"_id": bson.ObjectId(exam["class_id"])})
        if not cls or current_user.id not in cls.get("teacher_ids", []):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

    key = await answer_keys_collection.find_one({"exam_id": bson.ObjectId(exam_id)})
    if not key:
        return []

    samples = key.get("sample_sheets", [])
    return [SampleSheetItem(**s) for s in samples]


@router.delete("/{exam_id}/sample-sheets/{sample_index}/", status_code=status.HTTP_204_NO_CONTENT)
async def delete_sample_sheet(
    exam_id: str,
    sample_index: int,
    current_user: UserResponse = Depends(require_roles("admin", "teacher"))
):
    exam = await exams_collection.find_one({"_id": bson.ObjectId(exam_id)})
    if not exam:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exam not found")

    if current_user.role == "teacher":
        cls = await classes_collection.find_one({"_id": bson.ObjectId(exam["class_id"])})
        if not cls or current_user.id not in cls.get("teacher_ids", []):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

    key = await answer_keys_collection.find_one({"exam_id": bson.ObjectId(exam_id)})
    if not key:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Answer key not found")

    samples = key.get("sample_sheets", [])
    if sample_index < 0 or sample_index >= len(samples):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sample sheet not found")

    removed = samples.pop(sample_index)

    await answer_keys_collection.update_one(
        {"_id": key["_id"]},
        {"$set": {"sample_sheets": samples}}
    )

    if "path" in removed and os.path.exists(removed["path"]):
        os.remove(removed["path"])


# ============================================================
# Result Schema per-exam Endpoints
# ============================================================

@router.post("/{exam_id}/result-schema/", response_model=ResultSchemaResponse, status_code=status.HTTP_201_CREATED)
async def link_result_schema(
    exam_id: str,
    schema_data: ResultSchemaCreate,
    current_user: UserResponse = Depends(require_roles("admin", "teacher"))
):
    exam = await exams_collection.find_one({"_id": bson.ObjectId(exam_id)})
    if not exam:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exam not found")

    if current_user.role == "teacher":
        cls = await classes_collection.find_one({"_id": bson.ObjectId(exam["class_id"])})
        if not cls or current_user.id not in cls.get("teacher_ids", []):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

    schema_doc = {
        "name": schema_data.name,
        "description": schema_data.description,
        "schema_definition": schema_data.schema_definition,
        "created_by": bson.ObjectId(current_user.id),
        "created_at": datetime.utcnow(),
    }

    result = await result_schemas_collection.insert_one(schema_doc)

    await exams_collection.update_one(
        {"_id": bson.ObjectId(exam_id)},
        {"$set": {"result_schema_id": result.inserted_id, "updated_at": datetime.utcnow()}}
    )

    return ResultSchemaResponse(
        id=str(result.inserted_id),
        name=schema_doc["name"],
        description=schema_doc.get("description"),
        schema_definition=schema_doc["schema_definition"],
        created_by=current_user.id,
        created_at=schema_doc["created_at"],
    )


@router.get("/{exam_id}/result-schema/", response_model=Optional[ResultSchemaResponse])
async def get_exam_result_schema(
    exam_id: str,
    current_user: UserResponse = Depends(get_current_user)
):
    exam = await exams_collection.find_one({"_id": bson.ObjectId(exam_id)})
    if not exam:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exam not found")

    if current_user.role == "teacher":
        cls = await classes_collection.find_one({"_id": bson.ObjectId(exam["class_id"])})
        if not cls or current_user.id not in cls.get("teacher_ids", []):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

    if not exam.get("result_schema_id"):
        return None

    schema = await result_schemas_collection.find_one({"_id": exam["result_schema_id"]})
    if not schema:
        return None

    return ResultSchemaResponse(
        id=str(schema["_id"]),
        name=schema["name"],
        description=schema.get("description"),
        schema_definition=schema["schema_definition"],
        created_by=str(schema["created_by"]) if schema.get("created_by") else None,
        created_at=schema["created_at"],
    )


# ============================================================
# Exam-Student Enrollment Endpoints (Phase 12)
# ============================================================

@router.post("/{exam_id}/sync-students/")
async def sync_exam_students_endpoint(
    exam_id: str,
    current_user: UserResponse = Depends(require_roles("admin", "teacher"))
):
    exam = await exams_collection.find_one({"_id": bson.ObjectId(exam_id)})
    if not exam:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exam not found")

    if current_user.role == "teacher":
        cls = await classes_collection.find_one({"_id": bson.ObjectId(exam["class_id"])})
        if not cls or current_user.id not in cls.get("teacher_ids", []):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

    result = await enrollment_service.sync_exam_students(exam_id, exam["class_id"])

    return {"message": "Students synced", **result}


@router.get("/{exam_id}/students/")
async def list_exam_students(
    exam_id: str,
    status_filter: Optional[str] = None,
    current_user: UserResponse = Depends(get_current_user)
):
    exam = await exams_collection.find_one({"_id": bson.ObjectId(exam_id)})
    if not exam:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exam not found")

    if current_user.role == "teacher":
        cls = await classes_collection.find_one({"_id": bson.ObjectId(exam["class_id"])})
        if not cls or current_user.id not in cls.get("teacher_ids", []):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

    students = await enrollment_service.get_exam_students(exam_id, include_sheet_status=True)

    if status_filter:
        students = [s for s in students if s["enrollment_status"] == status_filter]

    return students


@router.get("/{exam_id}/students/summary/", response_model=ExamStudentsSummary)
async def get_exam_students_summary_endpoint(
    exam_id: str,
    current_user: UserResponse = Depends(get_current_user)
):
    exam = await exams_collection.find_one({"_id": bson.ObjectId(exam_id)})
    if not exam:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exam not found")

    if current_user.role == "teacher":
        cls = await classes_collection.find_one({"_id": bson.ObjectId(exam["class_id"])})
        if not cls or current_user.id not in cls.get("teacher_ids", []):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

    return await enrollment_service.get_exam_students_summary(exam_id)


@router.get("/{exam_id}/students/dropdown/", response_model=List[StudentDropdownItem])
async def get_exam_students_dropdown(
    exam_id: str,
    current_user: UserResponse = Depends(get_current_user)
):
    exam = await exams_collection.find_one({"_id": bson.ObjectId(exam_id)})
    if not exam:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exam not found")

    if current_user.role == "teacher":
        cls = await classes_collection.find_one({"_id": bson.ObjectId(exam["class_id"])})
        if not cls or current_user.id not in cls.get("teacher_ids", []):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

    return await enrollment_service.get_enrolled_students_for_dropdown(exam_id)
