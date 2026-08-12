from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from typing import List, Optional
from datetime import datetime
import bson
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
from db.database import (
    exams_collection, answer_sheets_collection, sheet_pages_collection,
    upload_batches_collection, subjects_collection, classes_collection,
    exam_students_collection,
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
):
    exam = await exams_collection.find_one({"_id": bson.ObjectId(exam_id)})
    if not exam:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exam not found")

    if current_user.role == "teacher":
        cls = await classes_collection.find_one({"_id": bson.ObjectId(exam["class_id"])})
        if not cls or current_user.id not in cls.get("teacher_ids", []):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

    temp_dir = os.path.join(settings.STORAGE_PATH, "temp_uploads", exam_id, uuid.uuid4().hex)
    os.makedirs(temp_dir, exist_ok=True)

    zip_path = os.path.join(temp_dir, file.filename or "upload.zip")
    with open(zip_path, "wb") as f:
        content = await file.read()
        f.write(content)

    upload_batch_doc = {
        "exam_id": bson.ObjectId(exam_id),
        "uploaded_by": bson.ObjectId(current_user.id),
        "zip_filename": file.filename or "upload.zip",
        "total_pdfs": 0,
        "processed_pdfs": 0,
        "status": "extracting",
        "created_at": datetime.utcnow(),
    }
    batch_result = await upload_batches_collection.insert_one(upload_batch_doc)
    upload_batch_id = str(batch_result.inserted_id)

    async def process_zip_background():
        try:
            print(f"[DEBUG] Starting background processing for batch {upload_batch_id}")
            print(f"[DEBUG] Storage path: {settings.STORAGE_PATH}")

            extract_dir = os.path.join(temp_dir, "extracted")
            pdf_paths = extract_pdf_files_from_zip(zip_path, extract_dir)
            print(f"[DEBUG] Extracted {len(pdf_paths)} PDFs from zip")

            await upload_batches_collection.update_one(
                {"_id": batch_result.inserted_id},
                {"$set": {"total_pdfs": len(pdf_paths)}}
            )

            for idx, pdf_path in enumerate(pdf_paths):
                parsed = parse_pdf_filename(os.path.basename(pdf_path))

                pdf_storage_dir = os.path.join(settings.STORAGE_PATH, "original_pdfs")
                os.makedirs(pdf_storage_dir, exist_ok=True)

                sheet_id = bson.ObjectId()
                pdf_dest = os.path.join(pdf_storage_dir, f"{sheet_id}.pdf")
                os.rename(pdf_path, pdf_dest)

                pages_dir = os.path.join(settings.STORAGE_PATH, "answer_sheets", str(sheet_id))
                print(f"[DEBUG] Rasterizing PDF {idx+1}/{len(pdf_paths)}: {pdf_dest} -> {pages_dir}")
                page_infos = rasterize_pdf_to_pngs(pdf_dest, pages_dir, dpi=150)
                print(f"[DEBUG] Generated {len(page_infos)} pages: {[pi['image_path'] for pi in page_infos]}")

                sheet_doc = {
                    "_id": sheet_id,
                    "exam_id": bson.ObjectId(exam_id),
                    "subject_id": exam.get("subject_id"),
                    "student_id": None,
                    "student_name": parsed.student_name,
                    "roll_no": parsed.roll_no,
                    "class_label": parsed.class_label,
                    "original_filename": parsed.original_filename,
                    "original_pdf_path": pdf_dest,
                    "page_count": len(page_infos),
                    "status": "pending_mapping",
                    "current_batch_id": None,
                    "uploaded_by": bson.ObjectId(current_user.id),
                    "batch_upload_id": batch_result.inserted_id,
                    "created_at": datetime.utcnow(),
                    "updated_at": None,
                }
                await answer_sheets_collection.insert_one(sheet_doc)

                for pi in page_infos:
                    page_doc = {
                        "sheet_id": sheet_id,
                        "page_no": pi["page_no"],
                        "image_path": pi["image_path"],
                        "width": pi["width"],
                        "height": pi["height"],
                        "is_deleted": False,
                        "created_at": datetime.utcnow(),
                    }
                    await sheet_pages_collection.insert_one(page_doc)

                processed_count = idx + 1
                await upload_batches_collection.update_one(
                    {"_id": batch_result.inserted_id},
                    {"$set": {"processed_pdfs": processed_count}}
                )

            await upload_batches_collection.update_one(
                {"_id": batch_result.inserted_id},
                {"$set": {"status": "ready_for_mapping"}}
            )

            if os.path.exists(extract_dir):
                cleanup_extract_dir(extract_dir)
            if os.path.exists(zip_path):
                os.remove(zip_path)

        except Exception as e:
            import traceback
            error_trace = traceback.format_exc()
            print(f"[ERROR] Background processing failed: {error_trace}")
            await upload_batches_collection.update_one(
                {"_id": batch_result.inserted_id},
                {"$set": {"status": "failed", "error": str(e)}}
            )

    asyncio.create_task(process_zip_background())

    return UploadBatchResponse(
        id=upload_batch_id,
        exam_id=exam_id,
        uploaded_by=current_user.id,
        zip_filename=file.filename or "upload.zip",
        total_pdfs=0,
        processed_pdfs=0,
        status="extracting",
        created_at=upload_batch_doc["created_at"],
    )


@router.get("/{exam_id}/sheets/", response_model=List[AnswerSheetResponse])
async def list_sheets(
    exam_id: str,
    status_filter: Optional[str] = None,
    current_user: UserResponse = Depends(get_current_user),
):
    exam = await exams_collection.find_one({"_id": bson.ObjectId(exam_id)})
    if not exam:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exam not found")

    if current_user.role == "teacher":
        cls = await classes_collection.find_one({"_id": bson.ObjectId(exam["class_id"])})
        if not cls or current_user.id not in cls.get("teacher_ids", []):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

    query = {"exam_id": bson.ObjectId(exam_id)}
    if status_filter:
        query["status"] = status_filter

    sheets = await answer_sheets_collection.find(query).sort("created_at", 1).to_list(length=None)
    return [
        AnswerSheetResponse(
            id=str(s["_id"]),
            exam_id=exam_id,
            subject_id=str(s["subject_id"]) if s.get("subject_id") else None,
            student_name=s.get("student_name"),
            roll_no=s.get("roll_no"),
            class_label=s.get("class_label"),
            original_filename=s["original_filename"],
            student_id=str(s["student_id"]) if s.get("student_id") else None,
            original_pdf_path=s.get("original_pdf_path"),
            page_count=s.get("page_count", 0),
            status=s.get("status", "pending_mapping"),
            current_batch_id=str(s["current_batch_id"]) if s.get("current_batch_id") else None,
            uploaded_by=str(s["uploaded_by"]) if s.get("uploaded_by") else None,
            batch_upload_id=str(s["batch_upload_id"]) if s.get("batch_upload_id") else None,
            created_at=s["created_at"],
            updated_at=s.get("updated_at"),
        )
        for s in sheets
    ]


@router.get("/{exam_id}/sheets/upload-batches/", response_model=List[UploadBatchResponse])
async def list_upload_batches(
    exam_id: str,
    current_user: UserResponse = Depends(get_current_user),
):
    exam = await exams_collection.find_one({"_id": bson.ObjectId(exam_id)})
    if not exam:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exam not found")

    batches = await upload_batches_collection.find(
        {"exam_id": bson.ObjectId(exam_id)}
    ).sort("created_at", -1).to_list(length=None)

    return [
        UploadBatchResponse(
            id=str(b["_id"]),
            exam_id=exam_id,
            uploaded_by=str(b["uploaded_by"]) if b.get("uploaded_by") else None,
            zip_filename=b["zip_filename"],
            total_pdfs=b.get("total_pdfs", 0),
            processed_pdfs=b.get("processed_pdfs", 0),
            status=b.get("status", "extracting"),
            created_at=b["created_at"],
        )
        for b in batches
    ]


@router.delete("/{exam_id}/sheets/upload-batches/{batch_id}/", status_code=status.HTTP_204_NO_CONTENT)
async def delete_upload_batch(
    exam_id: str,
    batch_id: str,
    current_user: UserResponse = Depends(require_roles("admin", "teacher")),
):
    exam = await exams_collection.find_one({"_id": bson.ObjectId(exam_id)})
    if not exam:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exam not found")

    if current_user.role == "teacher":
        cls = await classes_collection.find_one({"_id": bson.ObjectId(exam["class_id"])})
        if not cls or current_user.id not in cls.get("teacher_ids", []):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

    batch = await upload_batches_collection.find_one({"_id": bson.ObjectId(batch_id)})
    if not batch or str(batch["exam_id"]) != exam_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found")

    # Find all sheets created from this batch
    sheets = await answer_sheets_collection.find({"batch_upload_id": bson.ObjectId(batch_id)}).to_list(length=None)
    sheet_ids = [s["_id"] for s in sheets]

    # Delete page image files
    pages = await sheet_pages_collection.find({"sheet_id": {"$in": sheet_ids}}).to_list(length=None)
    for page in pages:
        image_path = page.get("image_path")
        if image_path and os.path.exists(image_path):
            os.remove(image_path)

    # Delete original PDFs
    for sheet in sheets:
        pdf_path = sheet.get("original_pdf_path")
        if pdf_path and os.path.exists(pdf_path):
            os.remove(pdf_path)

    # Delete page records
    await sheet_pages_collection.delete_many({"sheet_id": {"$in": sheet_ids}})

    # Delete sheet records
    await answer_sheets_collection.delete_many({"_id": {"$in": sheet_ids}})

    # Delete batch record
    await upload_batches_collection.delete_one({"_id": bson.ObjectId(batch_id)})


@router.get("/sheets/{sheet_id}/", response_model=AnswerSheetResponse)
async def get_sheet(
    sheet_id: str,
    current_user: UserResponse = Depends(get_current_user),
):
    sheet = await answer_sheets_collection.find_one({"_id": bson.ObjectId(sheet_id)})
    if not sheet:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sheet not found")

    exam = await exams_collection.find_one({"_id": sheet["exam_id"]})
    if not exam:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exam not found")

    if current_user.role == "teacher":
        cls = await classes_collection.find_one({"_id": bson.ObjectId(exam["class_id"])})
        if not cls or current_user.id not in cls.get("teacher_ids", []):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

    return AnswerSheetResponse(
        id=str(sheet["_id"]),
        exam_id=str(sheet["exam_id"]),
        subject_id=str(sheet["subject_id"]) if sheet.get("subject_id") else None,
        student_name=sheet.get("student_name"),
        roll_no=sheet.get("roll_no"),
        class_label=sheet.get("class_label"),
        original_filename=sheet["original_filename"],
        student_id=str(sheet["student_id"]) if sheet.get("student_id") else None,
        original_pdf_path=sheet.get("original_pdf_path"),
        page_count=sheet.get("page_count", 0),
        status=sheet.get("status", "pending_mapping"),
        current_batch_id=str(sheet["current_batch_id"]) if sheet.get("current_batch_id") else None,
        uploaded_by=str(sheet["uploaded_by"]) if sheet.get("uploaded_by") else None,
        batch_upload_id=str(sheet["batch_upload_id"]) if sheet.get("batch_upload_id") else None,
        created_at=sheet["created_at"],
        updated_at=sheet.get("updated_at"),
    )


@router.get("/sheets/{sheet_id}/pages/", response_model=List[SheetPageResponse])
async def get_sheet_pages(
    sheet_id: str,
    current_user: UserResponse = Depends(get_current_user),
):
    sheet = await answer_sheets_collection.find_one({"_id": bson.ObjectId(sheet_id)})
    if not sheet:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sheet not found")

    pages = await sheet_pages_collection.find(
        {"sheet_id": bson.ObjectId(sheet_id), "is_deleted": False}
    ).sort("page_no", 1).to_list(length=None)

    return [
        SheetPageResponse(
            id=str(p["_id"]),
            sheet_id=str(p["sheet_id"]),
            page_no=p["page_no"],
            image_path=p["image_path"],
            width=p.get("width", 0),
            height=p.get("height", 0),
            is_deleted=p.get("is_deleted", False),
            created_at=p["created_at"],
        )
        for p in pages
    ]


@router.patch("/sheets/{sheet_id}/", response_model=AnswerSheetResponse)
async def update_sheet_mapping(
    sheet_id: str,
    mapping: SheetMapping,
    current_user: UserResponse = Depends(require_roles("admin", "teacher")),
):
    sheet = await answer_sheets_collection.find_one({"_id": bson.ObjectId(sheet_id)})
    if not sheet:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sheet not found")

    exam = await exams_collection.find_one({"_id": sheet["exam_id"]})
    if not exam:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exam not found")

    if current_user.role == "teacher":
        cls = await classes_collection.find_one({"_id": bson.ObjectId(exam["class_id"])})
        if not cls or current_user.id not in cls.get("teacher_ids", []):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

    update_dict = {}
    if mapping.student_name is not None:
        update_dict["student_name"] = mapping.student_name
    if mapping.roll_no is not None:
        update_dict["roll_no"] = mapping.roll_no
    if mapping.class_label is not None:
        update_dict["class_label"] = mapping.class_label
    if mapping.student_id is not None:
        enrollment = await exam_students_collection.find_one({
            "exam_id": bson.ObjectId(str(exam["_id"])),
            "student_id": bson.ObjectId(mapping.student_id),
            "status": "active",
        })
        if not enrollment:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Student is not enrolled in this exam"
            )
        update_dict["student_id"] = bson.ObjectId(mapping.student_id)

    update_dict["status"] = "mapped"
    update_dict["updated_at"] = datetime.utcnow()

    result = await answer_sheets_collection.find_one_and_update(
        {"_id": bson.ObjectId(sheet_id)},
        {"$set": update_dict},
        return_document=True,
    )

    return AnswerSheetResponse(
        id=str(result["_id"]),
        exam_id=str(result["exam_id"]),
        subject_id=str(result["subject_id"]) if result.get("subject_id") else None,
        student_name=result.get("student_name"),
        roll_no=result.get("roll_no"),
        class_label=result.get("class_label"),
        original_filename=result["original_filename"],
        student_id=str(result["student_id"]) if result.get("student_id") else None,
        original_pdf_path=result.get("original_pdf_path"),
        page_count=result.get("page_count", 0),
        status=result.get("status", "pending_mapping"),
        current_batch_id=str(result["current_batch_id"]) if result.get("current_batch_id") else None,
        uploaded_by=str(result["uploaded_by"]) if result.get("uploaded_by") else None,
        batch_upload_id=str(result["batch_upload_id"]) if result.get("batch_upload_id") else None,
        created_at=result["created_at"],
        updated_at=result.get("updated_at"),
    )


@router.patch("/sheets/{sheet_id}/pages/{page_no}/", status_code=status.HTTP_204_NO_CONTENT)
async def delete_sheet_page(
    sheet_id: str,
    page_no: int,
    current_user: UserResponse = Depends(require_roles("admin", "teacher")),
):
    sheet = await answer_sheets_collection.find_one({"_id": bson.ObjectId(sheet_id)})
    if not sheet:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sheet not found")

    exam = await exams_collection.find_one({"_id": sheet["exam_id"]})
    if not exam:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exam not found")

    if current_user.role == "teacher":
        cls = await classes_collection.find_one({"_id": bson.ObjectId(exam["class_id"])})
        if not cls or current_user.id not in cls.get("teacher_ids", []):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

    await sheet_pages_collection.update_one(
        {"sheet_id": bson.ObjectId(sheet_id), "page_no": page_no},
        {"$set": {"is_deleted": True}}
    )


@router.delete("/sheets/{sheet_id}/", status_code=status.HTTP_204_NO_CONTENT)
async def delete_sheet(
    sheet_id: str,
    current_user: UserResponse = Depends(require_roles("admin", "teacher")),
):
    sheet = await answer_sheets_collection.find_one({"_id": bson.ObjectId(sheet_id)})
    if not sheet:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sheet not found")

    if sheet["status"] != "pending_mapping":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Can only delete sheets that are pending mapping"
        )

    exam = await exams_collection.find_one({"_id": sheet["exam_id"]})
    if not exam:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exam not found")

    if current_user.role == "teacher":
        cls = await classes_collection.find_one({"_id": bson.ObjectId(exam["class_id"])})
        if not cls or current_user.id not in cls.get("teacher_ids", []):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

    # Delete page image files
    pages = await sheet_pages_collection.find({"sheet_id": bson.ObjectId(sheet_id)}).to_list(length=None)
    for page in pages:
        image_path = page.get("image_path")
        if image_path and os.path.exists(image_path):
            os.remove(image_path)

    # Delete original PDF
    pdf_path = sheet.get("original_pdf_path")
    if pdf_path and os.path.exists(pdf_path):
        os.remove(pdf_path)

    # Delete page records from DB
    await sheet_pages_collection.delete_many({"sheet_id": bson.ObjectId(sheet_id)})

    # Delete sheet record
    await answer_sheets_collection.delete_one({"_id": bson.ObjectId(sheet_id)})


@router.delete("/exams/{exam_id}/sheets/pending/", status_code=status.HTTP_204_NO_CONTENT)
async def delete_all_pending_sheets(
    exam_id: str,
    current_user: UserResponse = Depends(require_roles("admin", "teacher")),
):
    exam = await exams_collection.find_one({"_id": bson.ObjectId(exam_id)})
    if not exam:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exam not found")

    if current_user.role == "teacher":
        cls = await classes_collection.find_one({"_id": bson.ObjectId(exam["class_id"])})
        if not cls or current_user.id not in cls.get("teacher_ids", []):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

    # Find all pending sheets
    pending_sheets = await answer_sheets_collection.find({
        "exam_id": bson.ObjectId(exam_id),
        "status": "pending_mapping",
    }).to_list(length=None)

    if not pending_sheets:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No pending sheets found")

    sheet_ids = [s["_id"] for s in pending_sheets]

    # Delete page image files
    pages = await sheet_pages_collection.find({"sheet_id": {"$in": sheet_ids}}).to_list(length=None)
    for page in pages:
        image_path = page.get("image_path")
        if image_path and os.path.exists(image_path):
            os.remove(image_path)

    # Delete original PDFs
    for sheet in pending_sheets:
        pdf_path = sheet.get("original_pdf_path")
        if pdf_path and os.path.exists(pdf_path):
            os.remove(pdf_path)

    # Delete page records from DB
    await sheet_pages_collection.delete_many({"sheet_id": {"$in": sheet_ids}})

    # Delete sheet records
    await answer_sheets_collection.delete_many({"_id": {"$in": sheet_ids}})


@router.post("/sheets/{sheet_id}/skip/", response_model=AnswerSheetResponse)
async def skip_sheet(
    sheet_id: str,
    current_user: UserResponse = Depends(require_roles("admin", "teacher")),
):
    sheet = await answer_sheets_collection.find_one({"_id": bson.ObjectId(sheet_id)})
    if not sheet:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sheet not found")

    exam = await exams_collection.find_one({"_id": sheet["exam_id"]})
    if not exam:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exam not found")

    if current_user.role == "teacher":
        cls = await classes_collection.find_one({"_id": bson.ObjectId(exam["class_id"])})
        if not cls or current_user.id not in cls.get("teacher_ids", []):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

    result = await answer_sheets_collection.find_one_and_update(
        {"_id": bson.ObjectId(sheet_id)},
        {"$set": {"status": "skipped", "updated_at": datetime.utcnow()}},
        return_document=True,
    )

    return AnswerSheetResponse(
        id=str(result["_id"]),
        exam_id=str(result["exam_id"]),
        subject_id=str(result["subject_id"]) if result.get("subject_id") else None,
        student_name=result.get("student_name"),
        roll_no=result.get("roll_no"),
        class_label=result.get("class_label"),
        original_filename=result["original_filename"],
        student_id=str(result["student_id"]) if result.get("student_id") else None,
        original_pdf_path=result.get("original_pdf_path"),
        page_count=result.get("page_count", 0),
        status=result.get("status", "pending_mapping"),
        current_batch_id=str(result["current_batch_id"]) if result.get("current_batch_id") else None,
        uploaded_by=str(result["uploaded_by"]) if result.get("uploaded_by") else None,
        batch_upload_id=str(result["batch_upload_id"]) if result.get("batch_upload_id") else None,
        created_at=result["created_at"],
        updated_at=result.get("updated_at"),
    )


# ============================================================
# Auto-Match Endpoints (Phase 12)
# ============================================================

@router.post("/{exam_id}/sheets/auto-match/")
async def auto_match_sheets(
    exam_id: str,
    request: AutoMatchRequest,
    current_user: UserResponse = Depends(require_roles("admin", "teacher")),
):
    exam = await exams_collection.find_one({"_id": bson.ObjectId(exam_id)})
    if not exam:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exam not found")

    if current_user.role == "teacher":
        cls = await classes_collection.find_one({"_id": bson.ObjectId(exam["class_id"])})
        if not cls or current_user.id not in cls.get("teacher_ids", []):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

    matches_to_apply = [
        {"sheet_id": m.sheet_id, "student_id": m.student_id, "keep_parsed_name": m.keep_parsed_name}
        for m in request.matches
    ]
    result = await apply_student_matches(exam_id, matches_to_apply)

    return result


@router.get("/{exam_id}/sheets/auto-match/suggestions/")
async def get_auto_match_suggestions(
    exam_id: str,
    current_user: UserResponse = Depends(get_current_user),
):
    exam = await exams_collection.find_one({"_id": bson.ObjectId(exam_id)})
    if not exam:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exam not found")

    if current_user.role == "teacher":
        cls = await classes_collection.find_one({"_id": bson.ObjectId(exam["class_id"])})
        if not cls or current_user.id not in cls.get("teacher_ids", []):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

    suggestions = await find_student_matches(exam_id)

    return {"suggestions": suggestions, "total_pending": len(suggestions)}
