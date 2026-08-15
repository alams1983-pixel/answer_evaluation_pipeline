from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, func
from typing import List, Optional
from datetime import datetime
import os
import uuid
import asyncio

from models.auth import UserResponse
from models.sheets import (
    AnswerSheetCreate, AnswerSheetUpdate, AnswerSheetResponse,
    SheetPageResponse, UploadBatchResponse, SheetMapping,
    AutoMatchRequest,
)
from core.deps import get_current_user, require_roles
from db.database import get_db, AsyncSessionLocal
from db.models import (
    Exam, AnswerSheet, SheetPage, UploadBatch, Class, Subject, ExamStudent
)
from core.config import settings
from services.pdf_service import rasterize_pdf_to_pngs
from services.zip_service import extract_pdf_files_from_zip, parse_pdf_filename, cleanup_extract_dir
from services.auto_match_service import find_student_matches, apply_student_matches

router = APIRouter(
    prefix="/exams",
    tags=["sheets"],
)


@router.post("/{exam_id}/sheets/upload-zip/", response_model=UploadBatchResponse, status_code=status.HTTP_201_CREATED)
async def upload_zip_sheets(
    exam_id: str,
    file: UploadFile = File(...),
    current_user: UserResponse = Depends(require_roles("admin", "teacher")),
    db: AsyncSession = Depends(get_db)
):
    res = await db.execute(select(Exam).where(Exam.id == exam_id))
    exam = res.scalar_one_or_none()
    if not exam:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exam not found")

    temp_dir = os.path.join(settings.STORAGE_PATH, "temp_uploads", exam_id, uuid.uuid4().hex)
    os.makedirs(temp_dir, exist_ok=True)

    zip_path = os.path.join(temp_dir, file.filename or "upload.zip")
    with open(zip_path, "wb") as f:
        content = await file.read()
        f.write(content)

    upload_batch_obj = UploadBatch(
        exam_id=exam_id,
        uploaded_by=current_user.id,
        zip_filename=file.filename or "upload.zip",
        total_pdfs=0,
        processed_pdfs=0,
        status="extracting",
        created_at=datetime.utcnow(),
    )
    db.add(upload_batch_obj)
    await db.commit()
    await db.refresh(upload_batch_obj)
    upload_batch_id = str(upload_batch_obj.id)

    async def process_zip_background():
        try:
            extract_dir = os.path.join(temp_dir, "extracted")
            pdf_paths = extract_pdf_files_from_zip(zip_path, extract_dir)

            async with AsyncSessionLocal() as session:
                b_res = await session.execute(select(UploadBatch).where(UploadBatch.id == upload_batch_id))
                b_obj = b_res.scalar_one_or_none()
                if b_obj:
                    b_obj.total_pdfs = len(pdf_paths)
                    await session.commit()

            for idx, pdf_path in enumerate(pdf_paths):
                parsed = parse_pdf_filename(os.path.basename(pdf_path))
                pdf_storage_dir = os.path.join(settings.STORAGE_PATH, "original_pdfs")
                os.makedirs(pdf_storage_dir, exist_ok=True)

                sheet_uuid = uuid.uuid4().hex
                pdf_dest = os.path.join(pdf_storage_dir, f"{sheet_uuid}.pdf")
                os.rename(pdf_path, pdf_dest)

                pages_dir = os.path.join(settings.STORAGE_PATH, "answer_sheets", sheet_uuid)
                page_infos = rasterize_pdf_to_pngs(pdf_dest, pages_dir, dpi=150)

                async with AsyncSessionLocal() as session:
                    sheet_obj = AnswerSheet(
                        id=sheet_uuid,
                        exam_id=exam_id,
                        subject_id=exam.subject_id,
                        student_id=None,
                        student_name=parsed.student_name,
                        roll_no=parsed.roll_no,
                        class_label=parsed.class_label,
                        original_filename=parsed.original_filename,
                        original_pdf_path=pdf_dest,
                        page_count=len(page_infos),
                        status="pending_mapping",
                        current_batch_id=None,
                        uploaded_by=current_user.id,
                        batch_upload_id=upload_batch_id,
                        created_at=datetime.utcnow(),
                    )
                    session.add(sheet_obj)
                    await session.commit()

                    for pi in page_infos:
                        page_obj = SheetPage(
                            sheet_id=sheet_uuid,
                            page_no=pi["page_no"],
                            image_path=pi["image_path"],
                            width=pi["width"],
                            height=pi["height"],
                            is_deleted=False,
                            created_at=datetime.utcnow(),
                        )
                        session.add(page_obj)

                    b_res = await session.execute(select(UploadBatch).where(UploadBatch.id == upload_batch_id))
                    b_obj = b_res.scalar_one_or_none()
                    if b_obj:
                        b_obj.processed_pdfs = idx + 1
                    await session.commit()

            async with AsyncSessionLocal() as session:
                b_res = await session.execute(select(UploadBatch).where(UploadBatch.id == upload_batch_id))
                b_obj = b_res.scalar_one_or_none()
                if b_obj:
                    b_obj.status = "ready_for_mapping"
                    await session.commit()

            # Automatically run auto-matching for high confidence student matches
            try:
                from services.auto_match_service import find_student_matches, apply_student_matches
                suggestions = await find_student_matches(exam_id)
                auto_matches = [
                    {"sheet_id": s["sheet_id"], "student_id": s["suggested_student_id"]}
                    for s in suggestions
                    if s.get("confidence") == "high" and s.get("suggested_student_id")
                ]
                if auto_matches:
                    await apply_student_matches(exam_id, auto_matches)
            except Exception as match_err:
                print(f"[ZIP Upload] Auto-match background exception: {match_err}")

            if os.path.exists(extract_dir):
                cleanup_extract_dir(extract_dir)
            if os.path.exists(zip_path):
                os.remove(zip_path)


        except Exception as e:
            print(f"[ERROR] Background processing failed: {e}")
            async with AsyncSessionLocal() as session:
                b_res = await session.execute(select(UploadBatch).where(UploadBatch.id == upload_batch_id))
                b_obj = b_res.scalar_one_or_none()
                if b_obj:
                    b_obj.status = "failed"
                    await session.commit()

    asyncio.create_task(process_zip_background())

    return UploadBatchResponse(
        id=upload_batch_id,
        exam_id=exam_id,
        uploaded_by=current_user.id,
        zip_filename=file.filename or "upload.zip",
        total_pdfs=0,
        processed_pdfs=0,
        status="extracting",
        created_at=upload_batch_obj.created_at,
    )


@router.get("/{exam_id}/sheets/", response_model=List[AnswerSheetResponse])
async def list_sheets(
    exam_id: str,
    status_filter: Optional[str] = None,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    query = select(AnswerSheet).where(AnswerSheet.exam_id == exam_id)
    if status_filter:
        query = query.where(AnswerSheet.status == status_filter)

    res = await db.execute(query.order_by(AnswerSheet.created_at.asc()))
    sheets = res.scalars().all()

    return [
        AnswerSheetResponse(
            id=str(s.id),
            exam_id=exam_id,
            subject_id=str(s.subject_id) if s.subject_id else None,
            student_name=s.student_name,
            roll_no=s.roll_no,
            class_label=s.class_label,
            original_filename=s.original_filename,
            student_id=str(s.student_id) if s.student_id else None,
            original_pdf_path=s.original_pdf_path,
            page_count=s.page_count or 0,
            status=s.status or "pending_mapping",
            current_batch_id=str(s.current_batch_id) if s.current_batch_id else None,
            uploaded_by=str(s.uploaded_by) if s.uploaded_by else None,
            batch_upload_id=str(s.batch_upload_id) if s.batch_upload_id else None,
            created_at=s.created_at,
            updated_at=s.updated_at,
        )
        for s in sheets
    ]


@router.get("/{exam_id}/sheets/upload-batches/", response_model=List[UploadBatchResponse])
async def list_upload_batches(
    exam_id: str,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    res = await db.execute(
        select(UploadBatch)
        .where(UploadBatch.exam_id == exam_id)
        .order_by(UploadBatch.created_at.desc())
    )
    batches = res.scalars().all()

    return [
        UploadBatchResponse(
            id=str(b.id),
            exam_id=exam_id,
            uploaded_by=str(b.uploaded_by) if b.uploaded_by else None,
            zip_filename=b.zip_filename,
            total_pdfs=b.total_pdfs or 0,
            processed_pdfs=b.processed_pdfs or 0,
            status=b.status or "extracting",
            created_at=b.created_at,
        )
        for b in batches
    ]


@router.delete("/{exam_id}/sheets/upload-batches/{batch_id}/", status_code=status.HTTP_204_NO_CONTENT)
async def delete_upload_batch(
    exam_id: str,
    batch_id: str,
    current_user: UserResponse = Depends(require_roles("admin", "teacher")),
    db: AsyncSession = Depends(get_db)
):
    b_res = await db.execute(select(UploadBatch).where(UploadBatch.id == batch_id))
    batch = b_res.scalar_one_or_none()
    if not batch or str(batch.exam_id) != exam_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found")

    sh_res = await db.execute(select(AnswerSheet).where(AnswerSheet.batch_upload_id == batch_id))
    sheets = sh_res.scalars().all()
    sheet_ids = [s.id for s in sheets]

    if sheet_ids:
        p_res = await db.execute(select(SheetPage).where(SheetPage.sheet_id.in_(sheet_ids)))
        pages = p_res.scalars().all()
        for page in pages:
            if page.image_path and os.path.exists(page.image_path):
                os.remove(page.image_path)

        for sheet in sheets:
            if sheet.original_pdf_path and os.path.exists(sheet.original_pdf_path):
                os.remove(sheet.original_pdf_path)

        await db.execute(delete(SheetPage).where(SheetPage.sheet_id.in_(sheet_ids)))
        await db.execute(delete(AnswerSheet).where(AnswerSheet.id.in_(sheet_ids)))

    await db.delete(batch)
    await db.commit()


@router.get("/sheets/{sheet_id}/", response_model=AnswerSheetResponse)
async def get_sheet(
    sheet_id: str,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    res = await db.execute(select(AnswerSheet).where(AnswerSheet.id == sheet_id))
    sheet = res.scalar_one_or_none()
    if not sheet:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sheet not found")

    return AnswerSheetResponse(
        id=str(sheet.id),
        exam_id=str(sheet.exam_id),
        subject_id=str(sheet.subject_id) if sheet.subject_id else None,
        student_name=sheet.student_name,
        roll_no=sheet.roll_no,
        class_label=sheet.class_label,
        original_filename=sheet.original_filename,
        student_id=str(sheet.student_id) if sheet.student_id else None,
        original_pdf_path=sheet.original_pdf_path,
        page_count=sheet.page_count or 0,
        status=sheet.status or "pending_mapping",
        current_batch_id=str(sheet.current_batch_id) if sheet.current_batch_id else None,
        uploaded_by=str(sheet.uploaded_by) if sheet.uploaded_by else None,
        batch_upload_id=str(sheet.batch_upload_id) if sheet.batch_upload_id else None,
        created_at=sheet.created_at,
        updated_at=sheet.updated_at,
    )


@router.get("/sheets/{sheet_id}/pages/", response_model=List[SheetPageResponse])
async def get_sheet_pages(
    sheet_id: str,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    res = await db.execute(
        select(SheetPage)
        .where(SheetPage.sheet_id == sheet_id, SheetPage.is_deleted == False)
        .order_by(SheetPage.page_no.asc())
    )
    pages = res.scalars().all()

    return [
        SheetPageResponse(
            id=str(p.id),
            sheet_id=str(p.sheet_id),
            page_no=p.page_no,
            image_path=p.image_path,
            width=p.width or 0,
            height=p.height or 0,
            is_deleted=p.is_deleted or False,
            created_at=p.created_at,
        )
        for p in pages
    ]


@router.patch("/sheets/{sheet_id}/", response_model=AnswerSheetResponse)
async def update_sheet_mapping(
    sheet_id: str,
    mapping: SheetMapping,
    current_user: UserResponse = Depends(require_roles("admin", "teacher")),
    db: AsyncSession = Depends(get_db)
):
    res = await db.execute(select(AnswerSheet).where(AnswerSheet.id == sheet_id))
    sheet = res.scalar_one_or_none()
    if not sheet:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sheet not found")

    if mapping.student_name is not None:
        sheet.student_name = mapping.student_name
    if mapping.roll_no is not None:
        sheet.roll_no = mapping.roll_no
    if mapping.class_label is not None:
        sheet.class_label = mapping.class_label
    if mapping.student_id is not None:
        e_res = await db.execute(
            select(ExamStudent).where(
                ExamStudent.exam_id == sheet.exam_id,
                ExamStudent.student_id == mapping.student_id,
                ExamStudent.status == "active",
            )
        )
        if not e_res.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Student is not enrolled in this exam")
        sheet.student_id = mapping.student_id

    sheet.status = "mapped"
    sheet.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(sheet)

    return AnswerSheetResponse(
        id=str(sheet.id),
        exam_id=str(sheet.exam_id),
        subject_id=str(sheet.subject_id) if sheet.subject_id else None,
        student_name=sheet.student_name,
        roll_no=sheet.roll_no,
        class_label=sheet.class_label,
        original_filename=sheet.original_filename,
        student_id=str(sheet.student_id) if sheet.student_id else None,
        original_pdf_path=sheet.original_pdf_path,
        page_count=sheet.page_count or 0,
        status=sheet.status or "pending_mapping",
        current_batch_id=str(sheet.current_batch_id) if sheet.current_batch_id else None,
        uploaded_by=str(sheet.uploaded_by) if sheet.uploaded_by else None,
        batch_upload_id=str(sheet.batch_upload_id) if sheet.batch_upload_id else None,
        created_at=sheet.created_at,
        updated_at=sheet.updated_at,
    )


@router.patch("/sheets/{sheet_id}/pages/{page_no}/", status_code=status.HTTP_204_NO_CONTENT)
async def delete_sheet_page(
    sheet_id: str,
    page_no: int,
    current_user: UserResponse = Depends(require_roles("admin", "teacher")),
    db: AsyncSession = Depends(get_db)
):
    await db.execute(
        update(SheetPage)
        .where(SheetPage.sheet_id == sheet_id, SheetPage.page_no == page_no)
        .values(is_deleted=True)
    )
    await db.commit()

    # Recalculate remaining active page count for the answer sheet
    res_count = await db.execute(
        select(func.count(SheetPage.id))
        .where(SheetPage.sheet_id == sheet_id, SheetPage.is_deleted == False)
    )
    active_pages = res_count.scalar() or 0

    await db.execute(
        update(AnswerSheet)
        .where(AnswerSheet.id == sheet_id)
        .values(page_count=active_pages, updated_at=datetime.utcnow())
    )
    await db.commit()


@router.delete("/sheets/{sheet_id}/", status_code=status.HTTP_204_NO_CONTENT)
async def delete_sheet(
    sheet_id: str,
    current_user: UserResponse = Depends(require_roles("admin", "teacher")),
    db: AsyncSession = Depends(get_db)
):
    res = await db.execute(select(AnswerSheet).where(AnswerSheet.id == sheet_id))
    sheet = res.scalar_one_or_none()
    if not sheet:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sheet not found")

    p_res = await db.execute(select(SheetPage).where(SheetPage.sheet_id == sheet_id))
    pages = p_res.scalars().all()
    for page in pages:
        if page.image_path and os.path.exists(page.image_path):
            os.remove(page.image_path)

    if sheet.original_pdf_path and os.path.exists(sheet.original_pdf_path):
        os.remove(sheet.original_pdf_path)

    await db.execute(delete(SheetPage).where(SheetPage.sheet_id == sheet_id))
    await db.delete(sheet)
    await db.commit()


@router.delete("/{exam_id}/sheets/pending/", status_code=status.HTTP_204_NO_CONTENT)
async def delete_all_pending_sheets(
    exam_id: str,
    current_user: UserResponse = Depends(require_roles("admin", "teacher")),
    db: AsyncSession = Depends(get_db)
):
    res = await db.execute(
        select(AnswerSheet).where(
            AnswerSheet.exam_id == exam_id,
            AnswerSheet.status == "pending_mapping",
        )
    )
    pending_sheets = res.scalars().all()
    sheet_ids = [s.id for s in pending_sheets]

    if sheet_ids:
        p_res = await db.execute(select(SheetPage).where(SheetPage.sheet_id.in_(sheet_ids)))
        pages = p_res.scalars().all()
        for page in pages:
            if page.image_path and os.path.exists(page.image_path):
                os.remove(page.image_path)

        for sheet in pending_sheets:
            if sheet.original_pdf_path and os.path.exists(sheet.original_pdf_path):
                os.remove(sheet.original_pdf_path)

        await db.execute(delete(SheetPage).where(SheetPage.sheet_id.in_(sheet_ids)))
        await db.execute(delete(AnswerSheet).where(AnswerSheet.id.in_(sheet_ids)))
        await db.commit()


@router.post("/sheets/{sheet_id}/skip/", response_model=AnswerSheetResponse)
async def skip_sheet(
    sheet_id: str,
    current_user: UserResponse = Depends(require_roles("admin", "teacher")),
    db: AsyncSession = Depends(get_db)
):
    res = await db.execute(select(AnswerSheet).where(AnswerSheet.id == sheet_id))
    sheet = res.scalar_one_or_none()
    if not sheet:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sheet not found")

    sheet.status = "skipped"
    sheet.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(sheet)

    return AnswerSheetResponse(
        id=str(sheet.id),
        exam_id=str(sheet.exam_id),
        subject_id=str(sheet.subject_id) if sheet.subject_id else None,
        student_name=sheet.student_name,
        roll_no=sheet.roll_no,
        class_label=sheet.class_label,
        original_filename=sheet.original_filename,
        student_id=str(sheet.student_id) if sheet.student_id else None,
        original_pdf_path=sheet.original_pdf_path,
        page_count=sheet.page_count or 0,
        status=sheet.status,
        current_batch_id=str(sheet.current_batch_id) if sheet.current_batch_id else None,
        uploaded_by=str(sheet.uploaded_by) if sheet.uploaded_by else None,
        batch_upload_id=str(sheet.batch_upload_id) if sheet.batch_upload_id else None,
        created_at=sheet.created_at,
        updated_at=sheet.updated_at,
    )


@router.post("/{exam_id}/sheets/auto-match/")
async def auto_match_sheets(
    exam_id: str,
    request: AutoMatchRequest,
    current_user: UserResponse = Depends(require_roles("admin", "teacher")),
):
    matches_to_apply = [
        {"sheet_id": m.sheet_id, "student_id": m.student_id, "keep_parsed_name": m.keep_parsed_name}
        for m in request.matches
    ]
    return await apply_student_matches(exam_id, matches_to_apply)


@router.get("/{exam_id}/sheets/auto-match/suggestions/")
async def get_auto_match_suggestions(
    exam_id: str,
    current_user: UserResponse = Depends(get_current_user),
):
    suggestions = await find_student_matches(exam_id)
    return {"suggestions": suggestions, "total_pending": len(suggestions)}
