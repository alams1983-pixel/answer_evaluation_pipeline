from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import os

from core.deps import get_current_user_optional
from core.config import settings
from db.database import get_db, AsyncSessionLocal
from db.models import (
    AnswerSheet, SheetPage, Exam, Class, AnswerKey,
    QuestionPaperCrop, AdditionalPdf
)

router = APIRouter(
    prefix="/files",
    tags=["files"],
)


async def _verify_sheet_access(sheet: AnswerSheet, user, db: AsyncSession) -> None:
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")

    res = await db.execute(select(Exam).where(Exam.id == sheet.exam_id))
    exam = res.scalar_one_or_none()
    if not exam:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exam not found")

    if user.role == "teacher":
        cls_res = await db.execute(select(Class).where(Class.id == exam.class_id))
        cls = cls_res.scalar_one_or_none()
        if not cls:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
    elif user.role == "student":
        if str(sheet.student_id) != user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")


async def _verify_exam_access(exam: Exam, user, db: AsyncSession) -> None:
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")

    if user.role == "teacher":
        cls_res = await db.execute(select(Class).where(Class.id == exam.class_id))
        cls = cls_res.scalar_one_or_none()
        if not cls:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")


@router.get("/sheets/{sheet_id}/pages/{page_no}")
async def get_sheet_page(
    sheet_id: str,
    page_no: int,
    current_user = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db)
):
    res = await db.execute(select(AnswerSheet).where(AnswerSheet.id == sheet_id))
    sheet = res.scalar_one_or_none()
    if not sheet:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sheet not found")

    await _verify_sheet_access(sheet, current_user, db)

    page_res = await db.execute(
        select(SheetPage).where(
            SheetPage.sheet_id == sheet_id,
            SheetPage.page_no == page_no,
            SheetPage.is_deleted == False,
        )
    )
    page = page_res.scalar_one_or_none()
    if not page:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Page not found")

    image_path = page.image_path
    if not os.path.exists(image_path):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Image file not found")

    return FileResponse(image_path, media_type="image/png")


@router.get("/sheets/{sheet_id}/pdf")
async def get_sheet_pdf(
    sheet_id: str,
    current_user = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db)
):
    res = await db.execute(select(AnswerSheet).where(AnswerSheet.id == sheet_id))
    sheet = res.scalar_one_or_none()
    if not sheet:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sheet not found")

    await _verify_sheet_access(sheet, current_user, db)

    pdf_path = sheet.original_pdf_path
    if not pdf_path or not os.path.exists(pdf_path):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="PDF file not found")

    return FileResponse(pdf_path, media_type="application/pdf")


@router.get("/exams/{exam_id}/key-pdf")
async def get_exam_key_pdf(
    exam_id: str,
    current_user = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db)
):
    res = await db.execute(select(Exam).where(Exam.id == exam_id))
    exam = res.scalar_one_or_none()
    if not exam:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exam not found")

    await _verify_exam_access(exam, current_user, db)

    key_res = await db.execute(select(AnswerKey).where(AnswerKey.exam_id == exam_id))
    key = key_res.scalar_one_or_none()
    if not key or not key.source_file:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Answer key PDF not found")

    pdf_path = key.source_file
    if not os.path.exists(pdf_path):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="PDF file not found")

    return FileResponse(pdf_path, media_type="application/pdf")


@router.get("/exams/{exam_id}/samples/{sample_index}")
async def get_sample_file(
    exam_id: str,
    sample_index: int,
    current_user = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db)
):
    res = await db.execute(select(Exam).where(Exam.id == exam_id))
    exam = res.scalar_one_or_none()
    if not exam:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exam not found")

    await _verify_exam_access(exam, current_user, db)

    key_res = await db.execute(select(AnswerKey).where(AnswerKey.exam_id == exam_id))
    key = key_res.scalar_one_or_none()
    if not key:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Answer key not found")

    samples = key.sample_sheets or []
    if sample_index < 0 or sample_index >= len(samples):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sample not found")

    sample = samples[sample_index]
    file_path = sample.get("path")
    if not file_path or not os.path.exists(file_path):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sample file not found")

    ext = os.path.splitext(file_path)[1].lower()
    media_types = {
        ".pdf": "application/pdf",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".webp": "image/webp",
        ".txt": "text/plain",
    }

    if ext == ".txt":
        with open(file_path, "r") as f:
            content = f.read()
        return {"content": content, "label": sample.get("label"), "notes": sample.get("notes")}

    return FileResponse(file_path, media_type=media_types.get(ext, "application/octet-stream"))


@router.get("/question-papers/{exam_id}/pages/{page_no}")
async def get_question_paper_page(
    exam_id: str,
    page_no: int,
    current_user = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db)
):
    res = await db.execute(select(Exam).where(Exam.id == exam_id))
    exam = res.scalar_one_or_none()
    if not exam:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exam not found")

    await _verify_exam_access(exam, current_user, db)

    image_path = os.path.join(
        settings.STORAGE_PATH, "question_papers", exam_id, f"page_{page_no:03d}.png"
    )
    if not os.path.exists(image_path):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Page image not found")

    return FileResponse(image_path, media_type="image/png")


@router.get("/question-papers/{exam_id}/original")
async def get_question_paper_original(
    exam_id: str,
    current_user = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db)
):
    res = await db.execute(select(Exam).where(Exam.id == exam_id))
    exam = res.scalar_one_or_none()
    if not exam:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exam not found")

    await _verify_exam_access(exam, current_user, db)

    pdf_path = os.path.join(settings.STORAGE_PATH, "question_papers", exam_id, "original.pdf")
    if not os.path.exists(pdf_path):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question paper PDF not found")

    return FileResponse(pdf_path, media_type="application/pdf")


@router.get("/question-papers/{exam_id}/crops/{crop_id}")
async def get_crop_image(
    exam_id: str,
    crop_id: str,
    current_user = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db)
):
    res = await db.execute(select(Exam).where(Exam.id == exam_id))
    exam = res.scalar_one_or_none()
    if not exam:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exam not found")

    await _verify_exam_access(exam, current_user, db)

    crop_res = await db.execute(select(QuestionPaperCrop).where(QuestionPaperCrop.id == crop_id))
    crop = crop_res.scalar_one_or_none()
    if not crop:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Crop not found")

    image_path = crop.image_path
    if not os.path.exists(image_path):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Crop image file not found")

    return FileResponse(image_path, media_type="image/png")


@router.get("/question-papers/{exam_id}/additional/{pdf_id}/pages/{page_no}")
async def get_additional_pdf_page(
    exam_id: str,
    pdf_id: str,
    page_no: int,
    current_user = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db)
):
    res = await db.execute(select(Exam).where(Exam.id == exam_id))
    exam = res.scalar_one_or_none()
    if not exam:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exam not found")

    await _verify_exam_access(exam, current_user, db)

    pdf_res = await db.execute(select(AdditionalPdf).where(AdditionalPdf.id == pdf_id))
    pdf = pdf_res.scalar_one_or_none()
    if not pdf:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Additional PDF not found")

    pdf_dir = os.path.dirname(pdf.source_file)
    image_path = os.path.join(pdf_dir, f"page_{page_no:03d}.png")
    if not os.path.exists(image_path):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Page image not found")

    return FileResponse(image_path, media_type="image/png")


@router.get("/question-papers/{exam_id}/additional/{pdf_id}/original")
async def get_additional_pdf_original(
    exam_id: str,
    pdf_id: str,
    current_user = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db)
):
    res = await db.execute(select(Exam).where(Exam.id == exam_id))
    exam = res.scalar_one_or_none()
    if not exam:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exam not found")

    await _verify_exam_access(exam, current_user, db)

    pdf_res = await db.execute(select(AdditionalPdf).where(AdditionalPdf.id == pdf_id))
    pdf = pdf_res.scalar_one_or_none()
    if not pdf:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Additional PDF not found")

    pdf_path = pdf.source_file
    if not os.path.exists(pdf_path):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="PDF file not found")

    return FileResponse(pdf_path, media_type="application/pdf")
