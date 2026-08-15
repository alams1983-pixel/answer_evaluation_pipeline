from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
from typing import List, Optional
from datetime import datetime
import os
import asyncio
import queue

from models.auth import UserResponse
from models.batches import (
    BatchJobResponse,
    BatchJobUpdate,
    BatchItemResponse,
    BatchDetailResponse,
)
from core.deps import get_current_user, require_roles
from db.database import get_db, AsyncSessionLocal
from db.models import (
    Exam, AnswerSheet, SheetPage, AnswerKey, ResultSchema,
    BatchJob, BatchItem, Subject, QuestionPaperCrop
)
from core.config import settings, COMPLEXITY_MODEL_MAP
from services import jsonl_service
from services.jsonl_service import build_jsonl_line, write_batch_input, UNIVERSAL_RESULT_SCHEMA
from services import batch_service



router = APIRouter(
    prefix="/exams",
    tags=["batches"],
)


@router.post("/{exam_id}/batches/", response_model=BatchJobResponse, status_code=status.HTTP_201_CREATED)
async def create_batch(
    exam_id: str,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    current_user: UserResponse = Depends(require_roles("admin", "teacher")),
    db: AsyncSession = Depends(get_db)
):
    res = await db.execute(select(Exam).where(Exam.id == exam_id))
    exam = res.scalar_one_or_none()
    if not exam:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exam not found")

    complexity_tier = exam.complexity_tier or "standard"
    selected_provider = provider if (provider and provider != "gemini") else settings.BATCH_PROVIDER_DEFAULT
    selected_model = model if model else COMPLEXITY_MODEL_MAP.get(complexity_tier, COMPLEXITY_MODEL_MAP["standard"])

    s_res = await db.execute(
        select(AnswerSheet).where(AnswerSheet.exam_id == exam_id, AnswerSheet.status == "mapped")
    )
    sheets = s_res.scalars().all()
    if not sheets:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No mapped sheets available for batch creation"
        )

    batch_obj = BatchJob(
        exam_id=exam_id,
        provider=selected_provider,
        model=selected_model,
        item_count=len(sheets),
        completed_count=0,
        failed_count=0,
        status="draft",
        created_by=current_user.id,
        created_at=datetime.utcnow(),
    )
    db.add(batch_obj)
    await db.commit()
    await db.refresh(batch_obj)
    batch_id = str(batch_obj.id)

    batch_dir = os.path.join(settings.STORAGE_PATH, "batches", batch_id)
    os.makedirs(batch_dir, exist_ok=True)

    ak_res = await db.execute(select(AnswerKey).where(AnswerKey.exam_id == exam_id))
    answer_key = ak_res.scalar_one_or_none()

    answer_key_questions = answer_key.questions or [] if answer_key else []
    sample_sheets = answer_key.sample_sheets or [] if answer_key else []
    included_refs = answer_key.included_page_refs or [] if answer_key else []

    qp_page_paths = []
    for page_no in included_refs:
        qp_path = os.path.join(
            settings.STORAGE_PATH, "question_papers", exam_id, f"page_{page_no:03d}.png"
        )
        if os.path.exists(qp_path):
            qp_page_paths.append(qp_path)

    cr_res = await db.execute(
        select(QuestionPaperCrop)
        .where(QuestionPaperCrop.exam_id == exam_id)
        .order_by(QuestionPaperCrop.created_at.asc())
    )
    crops = cr_res.scalars().all()
    crops_by_index = {}
    for crop in crops:
        idx = crop.question_index or 0
        if idx not in crops_by_index:
            crops_by_index[idx] = []
        crops_by_index[idx].append({
            "image_path": crop.image_path,
            "q_no": crop.q_no,
            "page_no": crop.page_no,
            "source_pdf": crop.source_pdf,
            "bbox": crop.bbox,
            "id": str(crop.id),
        })

    for i, q in enumerate(answer_key_questions):
        if isinstance(q, dict) and i in crops_by_index:
            q["attached_images"] = crops_by_index[i]

    result_schema_doc = None
    if exam.result_schema_id:
        rs_res = await db.execute(select(ResultSchema).where(ResultSchema.id == exam.result_schema_id))
        result_schema_doc = rs_res.scalar_one_or_none()

    result_schema = (result_schema_doc.schema_definition if result_schema_doc else None) or jsonl_service.UNIVERSAL_RESULT_SCHEMA

    subject_name = ""
    if exam.subject_id:
        sb_res = await db.execute(select(Subject).where(Subject.id == exam.subject_id))
        subject_doc = sb_res.scalar_one_or_none()
        if subject_doc:
            subject_name = subject_doc.name or ""

    jsonl_lines = []
    for sheet in sheets:
        sheet_id = str(sheet.id)
        p_res = await db.execute(
            select(SheetPage)
            .where(SheetPage.sheet_id == sheet_id, SheetPage.is_deleted == False)
            .order_by(SheetPage.page_no.asc())
        )
        pages = p_res.scalars().all()
        page_image_paths = [p.image_path for p in pages if os.path.exists(p.image_path or "")]

        if not page_image_paths:
            continue

        line = build_jsonl_line(
            sheet_id=sheet_id,
            student_name=sheet.student_name or "Unknown",
            roll_no=sheet.roll_no or "N/A",
            class_label=sheet.class_label or "N/A",
            subject=subject_name,
            page_image_paths=page_image_paths,
            answer_key_questions=answer_key_questions,
            sample_sheets=sample_sheets,
            result_schema=result_schema,
            provider=selected_provider,
            model=selected_model,
            qp_page_paths=qp_page_paths,
            complexity_tier=complexity_tier,
        )
        jsonl_lines.append(line)

        custom_id = f"sheet_{sheet_id}"
        item_obj = BatchItem(
            batch_id=batch_id,
            sheet_id=sheet_id,
            custom_id=custom_id,
            prompt_preview=f"Student: {sheet.student_name or 'Unknown'} | Roll: {sheet.roll_no or 'N/A'}",
            status="pending",
            created_at=datetime.utcnow(),
        )
        db.add(item_obj)

    input_file_path = write_batch_input(batch_id, jsonl_lines)
    batch_obj.input_file_path = input_file_path
    batch_obj.item_count = len(jsonl_lines)

    for sheet in sheets:
        sheet.status = "jsonl_ready"
        sheet.current_batch_id = batch_id

    await db.commit()

    return BatchJobResponse(
        id=batch_id,
        exam_id=exam_id,
        provider=selected_provider,
        model=selected_model,
        item_count=len(jsonl_lines),
        completed_count=0,
        failed_count=0,
        input_file_path=input_file_path,
        status="draft",
        created_by=current_user.id,
        created_at=batch_obj.created_at,
    )


@router.get("/{exam_id}/batches/", response_model=List[BatchJobResponse])
async def list_batches(
    exam_id: str,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    res = await db.execute(
        select(BatchJob).where(BatchJob.exam_id == exam_id).order_by(BatchJob.created_at.desc())
    )
    batches = res.scalars().all()

    return [
        BatchJobResponse(
            id=str(b.id),
            exam_id=exam_id,
            provider=b.provider or "gemini",
            model=b.model or "gemini-2.5-flash",
            provider_batch_id=b.provider_batch_id,
            input_file_path=b.input_file_path,
            uploaded_jsonl_path=b.uploaded_jsonl_path,
            output_file_path=b.output_file_path,
            uploaded_gemini_files=b.uploaded_gemini_files,
            item_count=b.item_count or 0,
            completed_count=b.completed_count or 0,
            failed_count=b.failed_count or 0,
            status=b.status or "draft",
            upload_status=b.upload_status,
            submitted_at=b.submitted_at,
            completed_at=b.completed_at,
            last_polled_at=b.last_polled_at,
            poll_error=b.poll_error,
            created_by=str(b.created_by) if b.created_by else None,
            created_at=b.created_at,
        )
        for b in batches
    ]


@router.get("/batches/{batch_id}/", response_model=BatchDetailResponse)
async def get_batch(
    batch_id: str,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    res = await db.execute(select(BatchJob).where(BatchJob.id == batch_id))
    batch = res.scalar_one_or_none()
    if not batch:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found")

    bi_res = await db.execute(
        select(BatchItem).where(BatchItem.batch_id == batch_id).order_by(BatchItem.created_at.asc())
    )
    items = bi_res.scalars().all()

    item_responses = [
        BatchItemResponse(
            id=str(it.id),
            batch_id=str(it.batch_id),
            sheet_id=str(it.sheet_id),
            custom_id=it.custom_id,
            prompt_preview=it.prompt_preview,
            status=it.status or "pending",
            error=it.error,
            raw_response=it.raw_response,
            created_at=it.created_at,
        )
        for it in items
    ]

    return BatchDetailResponse(
        id=str(batch.id),
        exam_id=str(batch.exam_id),
        provider=batch.provider or "gemini",
        model=batch.model or "gemini-2.5-flash",
        provider_batch_id=batch.provider_batch_id,
        input_file_path=batch.input_file_path,
        uploaded_jsonl_path=batch.uploaded_jsonl_path,
        output_file_path=batch.output_file_path,
        uploaded_gemini_files=batch.uploaded_gemini_files,
        item_count=batch.item_count or 0,
        completed_count=batch.completed_count or 0,
        failed_count=batch.failed_count or 0,
        status=batch.status or "draft",
        upload_status=batch.upload_status,
        submitted_at=batch.submitted_at,
        completed_at=batch.completed_at,
        last_polled_at=batch.last_polled_at,
        poll_error=batch.poll_error,
        created_by=str(batch.created_by) if batch.created_by else None,
        created_at=batch.created_at,
        items=item_responses,
    )


@router.get("/batches/{batch_id}/jsonl/")
async def download_batch_jsonl(
    batch_id: str,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    res = await db.execute(select(BatchJob).where(BatchJob.id == batch_id))
    batch = res.scalar_one_or_none()
    if not batch:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found")

    input_path = batch.input_file_path
    if not input_path or not os.path.exists(input_path):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="JSONL file not found")

    return FileResponse(
        path=input_path,
        media_type="application/x-jsonlines",
        filename=f"batch_{batch_id}_input.jsonl",
    )


@router.delete("/batches/{batch_id}/items/{item_id}/", status_code=status.HTTP_204_NO_CONTENT)
async def delete_batch_item(
    batch_id: str,
    item_id: str,
    current_user: UserResponse = Depends(require_roles("admin", "teacher")),
    db: AsyncSession = Depends(get_db)
):
    res = await db.execute(select(BatchJob).where(BatchJob.id == batch_id))
    batch = res.scalar_one_or_none()
    if not batch:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found")

    bi_res = await db.execute(select(BatchItem).where(BatchItem.id == item_id))
    item = bi_res.scalar_one_or_none()
    if not item or str(item.batch_id) != batch_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")

    await db.execute(
        update(AnswerSheet)
        .where(AnswerSheet.id == item.sheet_id)
        .values(status="mapped", current_batch_id=None)
    )
    await db.delete(item)
    await db.commit()


@router.patch("/batches/{batch_id}/", response_model=BatchJobResponse)
async def update_batch(
    batch_id: str,
    update_data: BatchJobUpdate,
    current_user: UserResponse = Depends(require_roles("admin", "teacher")),
    db: AsyncSession = Depends(get_db)
):
    res = await db.execute(select(BatchJob).where(BatchJob.id == batch_id))
    batch = res.scalar_one_or_none()
    if not batch:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found")

    update_dict = update_data.dict(exclude_unset=True)
    if "provider" in update_dict:
        batch.provider = update_dict["provider"]
    if "model" in update_dict:
        batch.model = update_dict["model"]

    await db.commit()
    await db.refresh(batch)

    return BatchJobResponse(
        id=str(batch.id),
        exam_id=str(batch.exam_id),
        provider=batch.provider or "gemini",
        model=batch.model or "gemini-2.5-flash",
        provider_batch_id=batch.provider_batch_id,
        input_file_path=batch.input_file_path,
        uploaded_jsonl_path=batch.uploaded_jsonl_path,
        output_file_path=batch.output_file_path,
        uploaded_gemini_files=batch.uploaded_gemini_files,
        item_count=batch.item_count or 0,
        completed_count=batch.completed_count or 0,
        failed_count=batch.failed_count or 0,
        status=batch.status or "draft",
        upload_status=batch.upload_status,
        submitted_at=batch.submitted_at,
        completed_at=batch.completed_at,
        last_polled_at=batch.last_polled_at,
        poll_error=batch.poll_error,
        created_by=str(batch.created_by) if batch.created_by else None,
        created_at=batch.created_at,
    )


@router.post("/batches/{batch_id}/submit/", response_model=BatchJobResponse)
async def submit_batch_endpoint(
    batch_id: str,
    current_user: UserResponse = Depends(require_roles("admin", "teacher")),
    db: AsyncSession = Depends(get_db)
):
    res = await db.execute(select(BatchJob).where(BatchJob.id == batch_id))
    batch = res.scalar_one_or_none()
    if not batch:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found")

    input_path = batch.input_file_path
    if not input_path or not os.path.exists(input_path):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Batch has no input file")

    provider = batch.provider or "gemini"
    model = batch.model or COMPLEXITY_MODEL_MAP.get("standard")
    progress_q: queue.Queue = queue.Queue()

    async def monitor_progress(bid: str):
        loop = asyncio.get_event_loop()
        while True:
            try:
                item = await loop.run_in_executor(None, progress_q.get, True, 1.0)
                if item is None:
                    break
                current, total, message = item
                async with AsyncSessionLocal() as session:
                    await session.execute(
                        update(BatchJob)
                        .where(BatchJob.id == bid)
                        .values(upload_status={"phase": "uploading", "current": current, "total": total, "message": message})
                    )
                    await session.commit()
            except queue.Empty:
                continue

    async def run_upload():
        monitor_task = asyncio.create_task(monitor_progress(batch_id))
        try:
            if provider == "gemini":
                uploaded_jsonl_path, uploaded_files = await batch_service.upload_files_for_batch(
                    provider, input_path, batch_id, progress_q
                )
                async with AsyncSessionLocal() as session:
                    await session.execute(
                        update(BatchJob)
                        .where(BatchJob.id == batch_id)
                        .values(
                            uploaded_jsonl_path=uploaded_jsonl_path,
                            uploaded_gemini_files=uploaded_files,
                            status="files_uploaded",
                            upload_status={"phase": "ready", "current": len(uploaded_files), "total": len(uploaded_files), "message": "Ready to submit."},
                        )
                    )
                    await session.commit()
            else:
                async with AsyncSessionLocal() as session:
                    await session.execute(
                        update(BatchJob)
                        .where(BatchJob.id == batch_id)
                        .values(status="files_uploaded", upload_status={"phase": "ready", "current": 0, "total": 0, "message": "Ready to submit."})
                    )
                    await session.commit()

            progress_q.put(None)
            await asyncio.wait_for(monitor_task, timeout=5.0)

        except Exception as e:
            progress_q.put(None)
            async with AsyncSessionLocal() as session:
                await session.execute(
                    update(BatchJob)
                    .where(BatchJob.id == batch_id)
                    .values(status="failed", poll_error=str(e))
                )
                await session.commit()

    asyncio.create_task(run_upload())

    batch.status = "uploading"
    await db.commit()
    await db.refresh(batch)

    return BatchJobResponse(
        id=str(batch.id),
        exam_id=str(batch.exam_id),
        provider=provider,
        model=model,
        provider_batch_id=batch.provider_batch_id,
        input_file_path=input_path,
        uploaded_jsonl_path=batch.uploaded_jsonl_path,
        output_file_path=batch.output_file_path,
        uploaded_gemini_files=batch.uploaded_gemini_files,
        item_count=batch.item_count or 0,
        completed_count=0,
        failed_count=0,
        status="uploading",
        created_by=str(batch.created_by) if batch.created_by else None,
        created_at=batch.created_at,
    )


@router.post("/batches/{batch_id}/submit-to-gemini/", response_model=BatchJobResponse)
async def submit_to_gemini_endpoint(
    batch_id: str,
    current_user: UserResponse = Depends(require_roles("admin", "teacher")),
    db: AsyncSession = Depends(get_db)
):
    res = await db.execute(select(BatchJob).where(BatchJob.id == batch_id))
    batch = res.scalar_one_or_none()
    if not batch:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found")

    provider = batch.provider or "gemini"
    model = batch.model or COMPLEXITY_MODEL_MAP.get("standard")
    submit_path = batch.uploaded_jsonl_path if provider == "gemini" else batch.input_file_path

    if not submit_path or not os.path.exists(submit_path):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No JSONL file ready for submission")

    provider_batch_id = await batch_service.submit_batch(provider, model, submit_path)
    now = datetime.utcnow()

    batch.provider_batch_id = provider_batch_id
    batch.status = "submitted"
    batch.submitted_at = now
    batch.upload_status = None

    await db.execute(
        update(AnswerSheet)
        .where(AnswerSheet.current_batch_id == batch_id)
        .values(status="in_batch", updated_at=now)
    )
    await db.commit()
    await db.refresh(batch)

    return BatchJobResponse(
        id=str(batch.id),
        exam_id=str(batch.exam_id),
        provider=provider,
        model=model,
        provider_batch_id=provider_batch_id,
        input_file_path=batch.input_file_path,
        uploaded_jsonl_path=batch.uploaded_jsonl_path,
        output_file_path=batch.output_file_path,
        uploaded_gemini_files=batch.uploaded_gemini_files,
        item_count=batch.item_count or 0,
        completed_count=0,
        failed_count=0,
        status="submitted",
        submitted_at=now,
        created_by=str(batch.created_by) if batch.created_by else None,
        created_at=batch.created_at,
    )


@router.get("/batches/{batch_id}/jsonl-final/")
async def download_final_jsonl(
    batch_id: str,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    res = await db.execute(select(BatchJob).where(BatchJob.id == batch_id))
    batch = res.scalar_one_or_none()
    if not batch:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found")

    final_path = batch.uploaded_jsonl_path or batch.input_file_path
    if not final_path or not os.path.exists(final_path):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Final JSONL file not found")

    return FileResponse(
        path=final_path,
        media_type="application/x-jsonlines",
        filename=f"batch_{batch_id}_final.jsonl",
    )


@router.get("/batches/{batch_id}/upload-status/")
async def get_upload_status(
    batch_id: str,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    res = await db.execute(select(BatchJob).where(BatchJob.id == batch_id))
    batch = res.scalar_one_or_none()
    if not batch:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found")

    return {
        "batch_id": str(batch.id),
        "status": batch.status,
        "upload_progress": batch.upload_status,
    }


@router.post("/batches/{batch_id}/cancel/", response_model=BatchJobResponse)
async def cancel_batch_endpoint(
    batch_id: str,
    current_user: UserResponse = Depends(require_roles("admin", "teacher")),
    db: AsyncSession = Depends(get_db)
):
    res = await db.execute(select(BatchJob).where(BatchJob.id == batch_id))
    batch = res.scalar_one_or_none()
    if not batch:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found")

    if batch.provider_batch_id:
        await batch_service.cancel_batch(batch.provider or "gemini", batch.provider_batch_id)

    now = datetime.utcnow()
    batch.status = "cancelled"
    batch.completed_at = now

    await db.execute(
        update(AnswerSheet)
        .where(AnswerSheet.current_batch_id == batch_id)
        .values(status="jsonl_ready", updated_at=now)
    )
    await db.commit()
    await db.refresh(batch)

    return BatchJobResponse(
        id=str(batch.id),
        exam_id=str(batch.exam_id),
        provider=batch.provider or "gemini",
        model=batch.model or "gemini-2.5-flash",
        provider_batch_id=batch.provider_batch_id,
        input_file_path=batch.input_file_path,
        item_count=batch.item_count or 0,
        completed_count=batch.completed_count or 0,
        failed_count=batch.failed_count or 0,
        status="cancelled",
        completed_at=now,
        created_by=str(batch.created_by) if batch.created_by else None,
        created_at=batch.created_at,
    )


@router.post("/batches/{batch_id}/refresh/", response_model=BatchDetailResponse)
async def refresh_batch_endpoint(
    batch_id: str,
    current_user: UserResponse = Depends(require_roles("admin", "teacher")),
    db: AsyncSession = Depends(get_db)
):
    res = await db.execute(select(BatchJob).where(BatchJob.id == batch_id))
    batch = res.scalar_one_or_none()
    if not batch:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found")

    from workers.batch_poller import poll_single_batch
    await poll_single_batch(batch)

    await db.refresh(batch)

    bi_res = await db.execute(
        select(BatchItem).where(BatchItem.batch_id == batch_id).order_by(BatchItem.created_at.asc())
    )
    items = bi_res.scalars().all()

    item_responses = [
        BatchItemResponse(
            id=str(it.id),
            batch_id=str(it.batch_id),
            sheet_id=str(it.sheet_id),
            custom_id=it.custom_id,
            prompt_preview=it.prompt_preview,
            status=it.status or "pending",
            error=it.error,
            raw_response=it.raw_response,
            created_at=it.created_at,
        )
        for it in items
    ]

    return BatchDetailResponse(
        id=str(batch.id),
        exam_id=str(batch.exam_id),
        provider=batch.provider or "gemini",
        model=batch.model or "gemini-2.5-flash",
        provider_batch_id=batch.provider_batch_id,
        input_file_path=batch.input_file_path,
        uploaded_jsonl_path=batch.uploaded_jsonl_path,
        output_file_path=batch.output_file_path,
        uploaded_gemini_files=batch.uploaded_gemini_files,
        item_count=batch.item_count or 0,
        completed_count=batch.completed_count or 0,
        failed_count=batch.failed_count or 0,
        status=batch.status or "draft",
        upload_status=batch.upload_status,
        submitted_at=batch.submitted_at,
        completed_at=batch.completed_at,
        last_polled_at=batch.last_polled_at,
        poll_error=batch.poll_error,
        created_by=str(batch.created_by) if batch.created_by else None,
        created_at=batch.created_at,
        items=item_responses,
    )


@router.delete("/batches/{batch_id}/", status_code=status.HTTP_204_NO_CONTENT)
async def delete_batch_endpoint(
    batch_id: str,
    current_user: UserResponse = Depends(require_roles("admin", "teacher")),
    db: AsyncSession = Depends(get_db)
):
    res = await db.execute(select(BatchJob).where(BatchJob.id == batch_id))
    batch = res.scalar_one_or_none()
    if not batch:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found")

    await db.execute(delete(BatchItem).where(BatchItem.batch_id == batch_id))
    await db.delete(batch)

    await db.execute(
        update(AnswerSheet)
        .where(AnswerSheet.current_batch_id == batch_id)
        .values(status="mapped", current_batch_id=None)
    )
    await db.commit()
