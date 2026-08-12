from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from pydantic import BaseModel
from typing import Optional, List
import bson
import os

from models.auth import UserResponse
from models.sheets import (
    QuestionPaperResponse, ExtractionTaskResponse,
    ExtractedQuestionItem, QuestionPaperPageItem,
    QuestionPaperCropResponse, CropBBox, CropCreateRequest,
    AdditionalPdfResponse,
)
from core.deps import get_current_user, require_roles
from db.database import (
    exams_collection, question_papers_collection, extraction_tasks_collection,
    answer_keys_collection, classes_collection, question_paper_crops_collection,
    additional_pdfs_collection,
)
from core.config import settings
from services.question_extraction_service import (
    start_extraction,
    get_extraction_status,
    get_question_paper,
    update_question_paper_review,
)
from services import crop_service, additional_pdf_service

router = APIRouter(
    prefix="/exams",
    tags=["question-papers"],
)


async def _verify_exam_access(exam_id: str, current_user: UserResponse):
    """Helper to verify exam exists and user has access."""
    exam = await exams_collection.find_one({"_id": bson.ObjectId(exam_id)})
    if not exam:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exam not found")

    # Only teachers need class ownership check; admins always have access
    if current_user.role == "teacher":
        cls = await classes_collection.find_one({"_id": bson.ObjectId(exam["class_id"])})
        if not cls or current_user.id not in cls.get("teacher_ids", []):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

    return exam


@router.post("/{exam_id}/question-paper/upload/", status_code=status.HTTP_201_CREATED)
async def upload_question_paper(
    exam_id: str,
    file: UploadFile = File(...),
    current_user: UserResponse = Depends(require_roles("admin", "teacher")),
):
    await _verify_exam_access(exam_id, current_user)

    storage_dir = os.path.join(settings.STORAGE_PATH, "question_papers", exam_id)
    os.makedirs(storage_dir, exist_ok=True)

    file_path = os.path.join(storage_dir, "original.pdf")
    with open(file_path, "wb") as f:
        content = await file.read()
        f.write(content)

    exam = await exams_collection.find_one({"_id": bson.ObjectId(exam_id)})
    total_marks = exam.get("total_marks", 100)

    task_id = await start_extraction(exam_id, file_path, total_marks)

    return {
        "message": "Question paper uploaded. Extraction started.",
        "task_id": task_id,
        "file_path": file_path,
    }


@router.get("/{exam_id}/question-paper/", response_model=Optional[QuestionPaperResponse])
async def get_exam_question_paper(
    exam_id: str,
    current_user: UserResponse = Depends(get_current_user),
):
    await _verify_exam_access(exam_id, current_user)

    qp = await get_question_paper(exam_id)
    if not qp:
        return None

    crops_by_question = {}
    all_crops = await crop_service.get_all_crops_for_exam(exam_id)
    for crop in all_crops:
        idx = crop["question_index"]
        if idx not in crops_by_question:
            crops_by_question[idx] = []
        crops_by_question[idx].append(crop)

    questions_with_crops = []
    for i, q in enumerate(qp.get("extracted_questions", [])):
        q_copy = dict(q)
        q_copy["attached_images"] = crops_by_question.get(i, [])
        questions_with_crops.append(q_copy)

    return QuestionPaperResponse(
        id=qp["id"],
        exam_id=qp["exam_id"],
        source_file=qp["source_file"],
        total_pages=qp["total_pages"],
        pages=[QuestionPaperPageItem(**p) for p in qp.get("pages", [])],
        extracted_questions=[ExtractedQuestionItem(**q) for q in questions_with_crops],
        status=qp["status"],
        extraction_model=qp.get("extraction_model"),
        created_at=qp["created_at"],
        updated_at=qp["updated_at"],
    )


@router.get("/{exam_id}/question-paper/extraction-status/")
async def get_extraction_status_endpoint(
    exam_id: str,
    current_user: UserResponse = Depends(get_current_user),
):
    await _verify_exam_access(exam_id, current_user)

    task = await extraction_tasks_collection.find_one({"exam_id": exam_id})
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No extraction task found")

    return {
        "id": str(task["_id"]),
        "exam_id": task["exam_id"],
        "status": task.get("status", "pending"),
        "total_pages": task.get("total_pages", 0),
        "processed_pages": task.get("processed_pages", 0),
        "current_page": task.get("current_page", 0),
        "current_step": task.get("current_step", ""),
        "questions_found_so_far": task.get("questions_found_so_far", 0),
        "error": task.get("error"),
        "started_at": task.get("started_at"),
        "completed_at": task.get("completed_at"),
    }


@router.post("/{exam_id}/question-paper/crop/", status_code=status.HTTP_201_CREATED)
async def create_crop(
    exam_id: str,
    crop_data: CropCreateRequest,
    current_user: UserResponse = Depends(require_roles("admin", "teacher")),
):
    await _verify_exam_access(exam_id, current_user)

    crop_id = await crop_service.save_crop(
        exam_id=exam_id,
        question_index=crop_data.question_index,
        q_no=crop_data.q_no,
        page_no=crop_data.page_no,
        source_pdf=crop_data.source_pdf,
        bbox=crop_data.bbox.model_dump(),
        image_data_base64=crop_data.image_data_base64,
    )

    crop = await crop_service.get_crops_for_question(exam_id, crop_data.question_index)
    new_crop = next((c for c in crop if c["id"] == crop_id), None)

    return {
        "message": "Crop attached to question",
        "crop_id": crop_id,
        "crop": new_crop,
    }


@router.delete("/{exam_id}/question-paper/crop/{crop_id}/")
async def delete_crop(
    exam_id: str,
    crop_id: str,
    current_user: UserResponse = Depends(require_roles("admin", "teacher")),
):
    await _verify_exam_access(exam_id, current_user)

    success = await crop_service.delete_crop(crop_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Crop not found")

    return {"message": "Crop deleted"}


@router.get("/{exam_id}/question-paper/crops/")
async def get_crops(
    exam_id: str,
    question_index: Optional[int] = None,
    current_user: UserResponse = Depends(get_current_user),
):
    await _verify_exam_access(exam_id, current_user)

    if question_index is not None:
        crops = await crop_service.get_crops_for_question(exam_id, question_index)
    else:
        crops = await crop_service.get_all_crops_for_exam(exam_id)

    return {"crops": crops}


@router.post("/{exam_id}/question-paper/additional-pdf/", status_code=status.HTTP_201_CREATED)
async def upload_additional_pdf(
    exam_id: str,
    file: UploadFile = File(...),
    label: str = Form(...),
    pdf_type: str = Form("reference"),
    current_user: UserResponse = Depends(require_roles("admin", "teacher")),
):
    await _verify_exam_access(exam_id, current_user)

    if pdf_type not in ("instructions", "answer_key", "reference"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid PDF type")

    result = await additional_pdf_service.upload_additional_pdf(
        exam_id=exam_id,
        file=file,
        label=label,
        pdf_type=pdf_type,
    )

    return result


@router.get("/{exam_id}/question-paper/additional-pdfs/")
async def list_additional_pdfs(
    exam_id: str,
    current_user: UserResponse = Depends(get_current_user),
):
    await _verify_exam_access(exam_id, current_user)

    pdfs = await additional_pdf_service.list_additional_pdfs(exam_id)
    return {"pdfs": pdfs}


@router.delete("/{exam_id}/question-paper/additional-pdf/{pdf_id}/")
async def delete_additional_pdf(
    exam_id: str,
    pdf_id: str,
    current_user: UserResponse = Depends(require_roles("admin", "teacher")),
):
    await _verify_exam_access(exam_id, current_user)

    success = await additional_pdf_service.delete_additional_pdf(pdf_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="PDF not found")

    return {"message": "Additional PDF deleted"}


class QuestionPaperReviewRequest(BaseModel):
    included_page_refs: List[int]
    excluded_page_refs: List[int]
    questions: Optional[List[dict]] = None


@router.post("/{exam_id}/question-paper/review/")
async def review_question_paper(
    exam_id: str,
    review_data: QuestionPaperReviewRequest,
    current_user: UserResponse = Depends(require_roles("admin", "teacher")),
):
    await _verify_exam_access(exam_id, current_user)

    success = await update_question_paper_review(
        exam_id,
        review_data.included_page_refs,
        review_data.excluded_page_refs,
        review_data.questions,
    )

    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question paper not found")

    return {"message": "Question paper review saved"}
