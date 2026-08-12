from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from typing import List, Optional
from datetime import datetime
import bson
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
from db.database import (
    exams_collection,
    answer_sheets_collection,
    sheet_pages_collection,
    classes_collection,
    subjects_collection,
    answer_keys_collection,
    result_schemas_collection,
    batch_jobs_collection,
    batch_items_collection,
)
from core.config import settings, COMPLEXITY_MODEL_MAP, COMPLEXITY_MODEL_MAP
from services.jsonl_service import build_jsonl_line, write_batch_input
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
):
    exam = await exams_collection.find_one({"_id": bson.ObjectId(exam_id)})
    if not exam:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exam not found")

    if current_user.role == "teacher":
        cls = await classes_collection.find_one({"_id": bson.ObjectId(exam["class_id"])})
        if not cls or current_user.id not in cls.get("teacher_ids", []):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

    complexity_tier = exam.get("complexity_tier", "standard")
    if provider and provider != "gemini":
        selected_provider = provider
    else:
        selected_provider = settings.BATCH_PROVIDER_DEFAULT

    if model:
        selected_model = model
    else:
        selected_model = COMPLEXITY_MODEL_MAP.get(complexity_tier, COMPLEXITY_MODEL_MAP["standard"])

    sheets = await answer_sheets_collection.find({
        "exam_id": bson.ObjectId(exam_id),
        "status": "mapped",
    }).to_list(length=None)

    if not sheets:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No mapped sheets available for batch creation"
        )

    batch_doc = {
        "exam_id": bson.ObjectId(exam_id),
        "provider": selected_provider,
        "model": selected_model,
        "complexity_tier": complexity_tier,
        "provider_batch_id": None,
        "input_file_path": None,
        "output_file_path": None,
        "item_count": len(sheets),
        "completed_count": 0,
        "failed_count": 0,
        "status": "draft",
        "submitted_at": None,
        "completed_at": None,
        "last_polled_at": None,
        "poll_error": None,
        "created_by": bson.ObjectId(current_user.id),
        "created_at": datetime.utcnow(),
    }

    batch_result = await batch_jobs_collection.insert_one(batch_doc)
    batch_id = batch_result.inserted_id

    batch_dir = os.path.join(settings.STORAGE_PATH, "batches", str(batch_id))
    os.makedirs(batch_dir, exist_ok=True)

    answer_key_obj = await answer_keys_collection.find_one({"exam_id": bson.ObjectId(exam_id)})
    answer_key_str = await answer_keys_collection.find_one({"exam_id": exam_id})

    answer_keys = [ak for ak in [answer_key_obj, answer_key_str] if ak]
    unique_keys = []
    seen_ids = set()
    for ak in answer_keys:
        ak_id = str(ak["_id"])
        if ak_id not in seen_ids:
            seen_ids.add(ak_id)
            unique_keys.append(ak)

    preferred_key = None
    for ak in unique_keys:
        q_count = len(ak.get("questions", []))
        inc_count = len(ak.get("included_page_refs", []))
        if q_count > 0 or inc_count > 0:
            preferred_key = ak
            break

    if preferred_key is None and unique_keys:
        preferred_key = unique_keys[0]

    answer_key = preferred_key
    answer_key_questions = []
    sample_sheets = []
    qp_page_paths = []
    if answer_key:
        answer_key_questions = answer_key.get("questions", [])
        for ak in unique_keys:
            ak_samples = ak.get("sample_sheets", [])
            for s in ak_samples:
                if s not in sample_sheets:
                    sample_sheets.append(s)

        included_refs = answer_key.get("included_page_refs", [])
        for page_no in included_refs:
            qp_path = os.path.join(
                settings.STORAGE_PATH, "question_papers", exam_id, f"page_{page_no:03d}.png"
            )
            if os.path.exists(qp_path):
                qp_page_paths.append(qp_path)

    from db.database import question_paper_crops_collection
    crops_obj = await question_paper_crops_collection.find({"exam_id": bson.ObjectId(exam_id)}).sort("created_at", 1).to_list(length=None)
    crops_str = await question_paper_crops_collection.find({"exam_id": exam_id}).sort("created_at", 1).to_list(length=None)
    seen_crop_ids = set()
    crops = []
    for c in crops_obj + crops_str:
        cid = str(c["_id"])
        if cid not in seen_crop_ids:
            seen_crop_ids.add(cid)
            crops.append(c)
    crops_by_index = {}
    for crop in crops:
        idx = crop.get("question_index", 0)
        if idx not in crops_by_index:
            crops_by_index[idx] = []
        crops_by_index[idx].append({
            "image_path": crop["image_path"],
            "q_no": crop["q_no"],
            "page_no": crop["page_no"],
            "source_pdf": crop["source_pdf"],
            "bbox": crop["bbox"],
            "id": str(crop["_id"]),
        })

    for i, q in enumerate(answer_key_questions):
        if i in crops_by_index:
            q["attached_images"] = crops_by_index[i]

    result_schema_doc = None
    if exam.get("result_schema_id"):
        result_schema_doc = await result_schemas_collection.find_one({
            "_id": bson.ObjectId(exam["result_schema_id"])
        })

    if not result_schema_doc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Exam must have a result schema attached"
        )

    result_schema = result_schema_doc.get("schema_definition", {})
    subject_name = ""
    if exam.get("subject_id"):
        subject_doc = await subjects_collection.find_one({"_id": bson.ObjectId(exam["subject_id"])})
        if subject_doc:
            subject_name = subject_doc.get("name", "")

    jsonl_lines = []
    for sheet in sheets:
        sheet_id = sheet["_id"]
        pages = await sheet_pages_collection.find({
            "sheet_id": sheet_id,
            "is_deleted": False,
        }).sort("page_no", 1).to_list(length=None)

        page_image_paths = [p["image_path"] for p in pages if os.path.exists(p.get("image_path", ""))]

        if not page_image_paths:
            continue

        line = build_jsonl_line(
            sheet_id=str(sheet_id),
            student_name=sheet.get("student_name", "Unknown"),
            roll_no=sheet.get("roll_no", "N/A"),
            class_label=sheet.get("class_label", "N/A"),
            subject=subject_name,
            page_image_paths=page_image_paths,
            answer_key_questions=[q.dict() if hasattr(q, 'dict') else q for q in answer_key_questions],
            sample_sheets=sample_sheets,
            result_schema=result_schema,
            provider=selected_provider,
            model=selected_model,
            qp_page_paths=qp_page_paths,
            complexity_tier=complexity_tier,
        )
        jsonl_lines.append(line)

        custom_id = f"sheet_{sheet_id}"
        item_doc = {
            "batch_id": batch_id,
            "sheet_id": sheet_id,
            "custom_id": custom_id,
            "prompt_preview": f"Student: {sheet.get('student_name', 'Unknown')} | Roll: {sheet.get('roll_no', 'N/A')}",
            "status": "pending",
            "error": None,
            "raw_response": None,
            "created_at": datetime.utcnow(),
        }
        await batch_items_collection.insert_one(item_doc)

    input_file_path = write_batch_input(str(batch_id), jsonl_lines)

    await batch_jobs_collection.update_one(
        {"_id": batch_id},
        {
            "$set": {
                "input_file_path": input_file_path,
                "item_count": len(jsonl_lines),
            }
        }
    )

    await answer_sheets_collection.update_many(
        {"_id": {"$in": [s["_id"] for s in sheets]}},
        {"$set": {"status": "jsonl_ready", "current_batch_id": batch_id}}
    )

    return BatchJobResponse(
        id=str(batch_id),
        exam_id=exam_id,
        provider=selected_provider,
        model=selected_model,
        item_count=len(jsonl_lines),
        completed_count=0,
        failed_count=0,
        input_file_path=input_file_path,
        status="draft",
        created_by=current_user.id,
        created_at=batch_doc["created_at"],
    )


@router.get("/{exam_id}/batches/", response_model=List[BatchJobResponse])
async def list_batches(
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

    batches = await batch_jobs_collection.find(
        {"exam_id": bson.ObjectId(exam_id)}
    ).sort("created_at", -1).to_list(length=None)

    return [
        BatchJobResponse(
            id=str(b["_id"]),
            exam_id=exam_id,
            provider=b.get("provider", "gemini"),
            model=b.get("model", "gemini-2.5-flash"),
            provider_batch_id=b.get("provider_batch_id"),
            input_file_path=b.get("input_file_path"),
            uploaded_jsonl_path=b.get("uploaded_jsonl_path"),
            output_file_path=b.get("output_file_path"),
            uploaded_gemini_files=b.get("uploaded_gemini_files"),
            item_count=b.get("item_count", 0),
            completed_count=b.get("completed_count", 0),
            failed_count=b.get("failed_count", 0),
            status=b.get("status", "draft"),
            upload_status=b.get("upload_status"),
            submitted_at=b.get("submitted_at"),
            completed_at=b.get("completed_at"),
            last_polled_at=b.get("last_polled_at"),
            poll_error=b.get("poll_error"),
            created_by=str(b["created_by"]) if b.get("created_by") else None,
            created_at=b["created_at"],
        )
        for b in batches
    ]


@router.get("/batches/{batch_id}/", response_model=BatchDetailResponse)
async def get_batch(
    batch_id: str,
    current_user: UserResponse = Depends(get_current_user),
):
    batch = await batch_jobs_collection.find_one({"_id": bson.ObjectId(batch_id)})
    if not batch:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found")

    exam = await exams_collection.find_one({"_id": batch["exam_id"]})
    if not exam:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exam not found")

    if current_user.role == "teacher":
        cls = await classes_collection.find_one({"_id": bson.ObjectId(exam["class_id"])})
        if not cls or current_user.id not in cls.get("teacher_ids", []):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

    items = await batch_items_collection.find(
        {"batch_id": bson.ObjectId(batch_id)}
    ).sort("created_at", 1).to_list(length=None)

    item_responses = [
        BatchItemResponse(
            id=str(it["_id"]),
            batch_id=str(it["batch_id"]),
            sheet_id=str(it["sheet_id"]),
            custom_id=it["custom_id"],
            prompt_preview=it.get("prompt_preview"),
            status=it.get("status", "pending"),
            error=it.get("error"),
            raw_response=it.get("raw_response"),
            created_at=it["created_at"],
        )
        for it in items
    ]

    return BatchDetailResponse(
        id=str(batch["_id"]),
        exam_id=str(batch["exam_id"]),
        provider=batch.get("provider", "gemini"),
        model=batch.get("model", "gemini-2.5-flash"),
        provider_batch_id=batch.get("provider_batch_id"),
        input_file_path=batch.get("input_file_path"),
        uploaded_jsonl_path=batch.get("uploaded_jsonl_path"),
        output_file_path=batch.get("output_file_path"),
        uploaded_gemini_files=batch.get("uploaded_gemini_files"),
        item_count=batch.get("item_count", 0),
        completed_count=batch.get("completed_count", 0),
        failed_count=batch.get("failed_count", 0),
        status=batch.get("status", "draft"),
        upload_status=batch.get("upload_status"),
        submitted_at=batch.get("submitted_at"),
        completed_at=batch.get("completed_at"),
        last_polled_at=batch.get("last_polled_at"),
        poll_error=batch.get("poll_error"),
        created_by=str(batch["created_by"]) if batch.get("created_by") else None,
        created_at=batch["created_at"],
        items=item_responses,
    )


@router.get("/batches/{batch_id}/jsonl/")
async def download_batch_jsonl(
    batch_id: str,
    current_user: UserResponse = Depends(get_current_user),
):
    batch = await batch_jobs_collection.find_one({"_id": bson.ObjectId(batch_id)})
    if not batch:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found")

    exam = await exams_collection.find_one({"_id": batch["exam_id"]})
    if not exam:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exam not found")

    if current_user.role == "teacher":
        cls = await classes_collection.find_one({"_id": bson.ObjectId(exam["class_id"])})
        if not cls or current_user.id not in cls.get("teacher_ids", []):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

    input_path = batch.get("input_file_path")
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
):
    batch = await batch_jobs_collection.find_one({"_id": bson.ObjectId(batch_id)})
    if not batch:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found")

    if batch["status"] != "draft":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Can only remove items from draft batches"
        )

    exam = await exams_collection.find_one({"_id": batch["exam_id"]})
    if not exam:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exam not found")

    if current_user.role == "teacher":
        cls = await classes_collection.find_one({"_id": bson.ObjectId(exam["class_id"])})
        if not cls or current_user.id not in cls.get("teacher_ids", []):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

    item = await batch_items_collection.find_one({"_id": bson.ObjectId(item_id)})
    if not item or str(item["batch_id"]) != batch_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")

    await batch_items_collection.delete_one({"_id": bson.ObjectId(item_id)})

    await answer_sheets_collection.update_one(
        {"_id": item["sheet_id"]},
        {"$set": {"status": "mapped", "current_batch_id": None}}
    )

    remaining = await batch_items_collection.count_documents({"batch_id": bson.ObjectId(batch_id)})
    await batch_jobs_collection.update_one(
        {"_id": bson.ObjectId(batch_id)},
        {"$set": {"item_count": remaining}}
    )


@router.patch("/batches/{batch_id}/", response_model=BatchJobResponse)
async def update_batch(
    batch_id: str,
    update_data: BatchJobUpdate,
    current_user: UserResponse = Depends(require_roles("admin", "teacher")),
):
    batch = await batch_jobs_collection.find_one({"_id": bson.ObjectId(batch_id)})
    if not batch:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found")

    if batch["status"] != "draft":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Can only update draft batches"
        )

    exam = await exams_collection.find_one({"_id": batch["exam_id"]})
    if not exam:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exam not found")

    if current_user.role == "teacher":
        cls = await classes_collection.find_one({"_id": bson.ObjectId(exam["class_id"])})
        if not cls or current_user.id not in cls.get("teacher_ids", []):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

    update_dict = update_data.dict(exclude_unset=True)
    if update_dict:
        update_dict["updated_at"] = datetime.utcnow()
        await batch_jobs_collection.update_one(
            {"_id": bson.ObjectId(batch_id)},
            {"$set": update_dict}
        )

    updated_batch = await batch_jobs_collection.find_one({"_id": bson.ObjectId(batch_id)})

    return BatchJobResponse(
        id=str(updated_batch["_id"]),
        exam_id=str(updated_batch["exam_id"]),
        provider=updated_batch.get("provider", "gemini"),
        model=updated_batch.get("model", "gemini-2.5-flash"),
        provider_batch_id=updated_batch.get("provider_batch_id"),
        input_file_path=updated_batch.get("input_file_path"),
        uploaded_jsonl_path=updated_batch.get("uploaded_jsonl_path"),
        output_file_path=updated_batch.get("output_file_path"),
        uploaded_gemini_files=updated_batch.get("uploaded_gemini_files"),
        item_count=updated_batch.get("item_count", 0),
        completed_count=updated_batch.get("completed_count", 0),
        failed_count=updated_batch.get("failed_count", 0),
        status=updated_batch.get("status", "draft"),
        upload_status=updated_batch.get("upload_status"),
        submitted_at=updated_batch.get("submitted_at"),
        completed_at=updated_batch.get("completed_at"),
        last_polled_at=updated_batch.get("last_polled_at"),
        poll_error=updated_batch.get("poll_error"),
        created_by=str(updated_batch["created_by"]) if updated_batch.get("created_by") else None,
        created_at=updated_batch["created_at"],
    )


@router.post("/batches/{batch_id}/submit/", response_model=BatchJobResponse)
async def submit_batch_endpoint(
    batch_id: str,
    current_user: UserResponse = Depends(require_roles("admin", "teacher")),
):
    batch = await batch_jobs_collection.find_one({"_id": bson.ObjectId(batch_id)})
    if not batch:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found")

    if batch["status"] not in ("draft", "failed"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Can only submit draft or failed batches"
        )

    if batch["status"] == "failed":
        uploaded_jsonl = batch.get("uploaded_jsonl_path")
        if uploaded_jsonl and os.path.exists(uploaded_jsonl):
            pass
        else:
            await batch_jobs_collection.update_one(
                {"_id": bson.ObjectId(batch_id)},
                {"$set": {"uploaded_gemini_files": None, "uploaded_jsonl_path": None}}
            )

    exam = await exams_collection.find_one({"_id": batch["exam_id"]})
    if not exam:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exam not found")

    if current_user.role == "teacher":
        cls = await classes_collection.find_one({"_id": bson.ObjectId(exam["class_id"])})
        if not cls or current_user.id not in cls.get("teacher_ids", []):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

    input_path = batch.get("input_file_path")
    if not input_path or not os.path.exists(input_path):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Batch has no input file")

    provider = batch.get("provider", "gemini")
    model = batch.get("model") or COMPLEXITY_MODEL_MAP.get("standard")

    progress_q: queue.Queue = queue.Queue()

    async def monitor_progress(bid: str):
        loop = asyncio.get_event_loop()
        while True:
            try:
                item = await loop.run_in_executor(None, progress_q.get, True, 1.0)
                if item is None:
                    break
                current, total, message = item
                await batch_jobs_collection.update_one(
                    {"_id": bson.ObjectId(bid)},
                    {"$set": {
                        "upload_status": {
                            "phase": "uploading",
                            "current": current,
                            "total": total,
                            "message": message,
                        }
                    }}
                )
            except queue.Empty:
                continue

    async def run_upload():
        bid = batch_id
        prov = provider
        in_path = input_path

        print(f"[DEBUG] Starting file upload for batch {bid}")

        monitor_task = asyncio.create_task(monitor_progress(bid))

        try:
            await batch_jobs_collection.update_one(
                {"_id": bson.ObjectId(bid)},
                {"$set": {
                    "upload_status": {
                        "phase": "starting",
                        "current": 0,
                        "total": 0,
                        "message": "Starting file upload...",
                    }
                }}
            )

            if prov == "gemini":
                print(f"[DEBUG] Calling upload_files_for_batch...")
                uploaded_jsonl_path, uploaded_files = await batch_service.upload_files_for_batch(
                    prov, in_path, bid, progress_q
                )
                print(f"[DEBUG] Upload completed: {uploaded_jsonl_path}, {len(uploaded_files)} files")
                await batch_jobs_collection.update_one(
                    {"_id": bson.ObjectId(bid)},
                    {"$set": {
                        "uploaded_jsonl_path": uploaded_jsonl_path,
                        "uploaded_gemini_files": uploaded_files,
                        "status": "files_uploaded",
                        "upload_status": {
                            "phase": "ready",
                            "current": len(uploaded_files),
                            "total": len(uploaded_files),
                            "message": f"{len(uploaded_files)} files uploaded. Ready to submit.",
                        },
                    }}
                )
                print(f"[DEBUG] Status updated to files_uploaded")
                progress_q.put(None)
                try:
                    await asyncio.wait_for(monitor_task, timeout=5.0)
                except asyncio.TimeoutError:
                    print(f"[DEBUG] Monitor task timed out, cancelling...")
                    monitor_task.cancel()
            else:
                await batch_jobs_collection.update_one(
                    {"_id": bson.ObjectId(bid)},
                    {"$set": {
                        "status": "files_uploaded",
                        "upload_status": {
                            "phase": "ready",
                            "current": 0,
                            "total": 0,
                            "message": "Ready to submit.",
                        },
                    }}
                )
                progress_q.put(None)
                try:
                    await asyncio.wait_for(monitor_task, timeout=5.0)
                except asyncio.TimeoutError:
                    monitor_task.cancel()

        except Exception as e:
            progress_q.put(None)
            try:
                await monitor_task
            except Exception:
                pass
            print(f"[ERROR] Upload failed for batch {bid}: {e}")
            await batch_jobs_collection.update_one(
                {"_id": bson.ObjectId(bid)},
                {
                    "$set": {
                        "status": "failed",
                        "upload_status": {
                            "phase": "failed",
                            "current": 0,
                            "total": 0,
                            "message": f"Upload failed: {str(e)}",
                        },
                        "poll_error": str(e),
                    }
                }
            )

    UPLOAD_TIMEOUT_SEC = 300

    async def run_upload_with_timeout():
        task = asyncio.create_task(run_upload())
        try:
            await asyncio.wait_for(asyncio.shield(task), timeout=UPLOAD_TIMEOUT_SEC)
        except asyncio.TimeoutError:
            print(f"[ERROR] Batch {batch_id} upload timed out after {UPLOAD_TIMEOUT_SEC}s")
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            await batch_jobs_collection.update_one(
                {"_id": bson.ObjectId(batch_id)},
                {
                    "$set": {
                        "status": "failed",
                        "upload_status": {
                            "phase": "failed",
                            "current": 0,
                            "total": 0,
                            "message": f"Upload timed out after {UPLOAD_TIMEOUT_SEC}s",
                        },
                        "poll_error": f"Timeout after {UPLOAD_TIMEOUT_SEC}s",
                    }
                }
            )

    asyncio.create_task(run_upload_with_timeout())

    await batch_jobs_collection.update_one(
        {"_id": bson.ObjectId(batch_id)},
        {"$set": {
            "status": "uploading",
            "upload_status": None,
            "poll_error": None,
        }}
    )

    return BatchJobResponse(
        id=str(batch["_id"]),
        exam_id=str(batch["exam_id"]),
        provider=provider,
        model=model,
        provider_batch_id=batch.get("provider_batch_id"),
        input_file_path=input_path,
        uploaded_jsonl_path=batch.get("uploaded_jsonl_path"),
        output_file_path=batch.get("output_file_path"),
        uploaded_gemini_files=batch.get("uploaded_gemini_files"),
        item_count=batch.get("item_count", 0),
        completed_count=0,
        failed_count=0,
        status="uploading",
        upload_status=None,
        submitted_at=None,
        completed_at=batch.get("completed_at"),
        last_polled_at=batch.get("last_polled_at"),
        poll_error=batch.get("poll_error"),
        created_by=str(batch["created_by"]) if batch.get("created_by") else None,
        created_at=batch["created_at"],
    )


@router.post("/batches/{batch_id}/submit-to-gemini/", response_model=BatchJobResponse)
async def submit_to_gemini_endpoint(
    batch_id: str,
    current_user: UserResponse = Depends(require_roles("admin", "teacher")),
):
    batch = await batch_jobs_collection.find_one({"_id": bson.ObjectId(batch_id)})
    if not batch:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found")

    if batch["status"] not in ("files_uploaded", "failed"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Can only submit batches that have files uploaded (status: files_uploaded)"
        )

    exam = await exams_collection.find_one({"_id": batch["exam_id"]})
    if not exam:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exam not found")

    if current_user.role == "teacher":
        cls = await classes_collection.find_one({"_id": bson.ObjectId(exam["class_id"])})
        if not cls or current_user.id not in cls.get("teacher_ids", []):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

    provider = batch.get("provider", "gemini")
    model = batch.get("model") or COMPLEXITY_MODEL_MAP.get("standard")

    if provider == "gemini":
        submit_path = batch.get("uploaded_jsonl_path")
        if not submit_path or not os.path.exists(submit_path):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No uploaded JSONL file found. Upload files first."
            )
    else:
        submit_path = batch.get("input_file_path")
        if not submit_path or not os.path.exists(submit_path):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Batch has no input file"
            )

    try:
        print(f"[DEBUG] Submitting batch {batch_id} to Gemini with model {model}")
        provider_batch_id = await batch_service.submit_batch(provider, model, submit_path)
        print(f"[DEBUG] Batch job created: {provider_batch_id}")

        now = datetime.utcnow()
        await batch_jobs_collection.update_one(
            {"_id": bson.ObjectId(batch_id)},
            {
                "$set": {
                    "provider_batch_id": provider_batch_id,
                    "status": "submitted",
                    "submitted_at": now,
                    "upload_status": None,
                }
            }
        )

        await answer_sheets_collection.update_many(
            {"current_batch_id": bson.ObjectId(batch_id)},
            {"$set": {"status": "in_batch", "updated_at": now}}
        )

        updated_batch = await batch_jobs_collection.find_one({"_id": bson.ObjectId(batch_id)})

        return BatchJobResponse(
            id=str(updated_batch["_id"]),
            exam_id=str(updated_batch["exam_id"]),
            provider=updated_batch.get("provider", "gemini"),
            model=updated_batch.get("model", "gemini-2.5-flash"),
            provider_batch_id=updated_batch.get("provider_batch_id"),
            input_file_path=updated_batch.get("input_file_path"),
            uploaded_jsonl_path=updated_batch.get("uploaded_jsonl_path"),
            output_file_path=updated_batch.get("output_file_path"),
            uploaded_gemini_files=updated_batch.get("uploaded_gemini_files"),
            item_count=updated_batch.get("item_count", 0),
            completed_count=0,
            failed_count=0,
            status="submitted",
            upload_status=None,
            submitted_at=now,
            completed_at=updated_batch.get("completed_at"),
            last_polled_at=updated_batch.get("last_polled_at"),
            poll_error=updated_batch.get("poll_error"),
            created_by=str(updated_batch["created_by"]) if updated_batch.get("created_by") else None,
            created_at=updated_batch["created_at"],
        )

    except Exception as e:
        print(f"[ERROR] Failed to submit batch {batch_id}: {e}")
        await batch_jobs_collection.update_one(
            {"_id": bson.ObjectId(batch_id)},
            {
                "$set": {
                    "status": "failed",
                    "upload_status": {
                        "phase": "failed",
                        "current": 0,
                        "total": 0,
                        "message": f"Submit failed: {str(e)}",
                    },
                    "poll_error": str(e),
                }
            }
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to submit batch: {str(e)}"
        )


@router.get("/batches/{batch_id}/jsonl-final/")
async def download_final_jsonl(
    batch_id: str,
    current_user: UserResponse = Depends(get_current_user),
):
    batch = await batch_jobs_collection.find_one({"_id": bson.ObjectId(batch_id)})
    if not batch:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found")

    exam = await exams_collection.find_one({"_id": batch["exam_id"]})
    if not exam:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exam not found")

    if current_user.role == "teacher":
        cls = await classes_collection.find_one({"_id": bson.ObjectId(exam["class_id"])})
        if not cls or current_user.id not in cls.get("teacher_ids", []):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

    final_path = batch.get("uploaded_jsonl_path")
    if not final_path or not os.path.exists(final_path):
        if batch.get("status") == "files_uploaded":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Final JSONL file not found. Files may have been uploaded but JSONL not generated."
            )
        elif batch.get("provider", "gemini") == "openai":
            final_path = batch.get("input_file_path")
            if not final_path or not os.path.exists(final_path):
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="JSONL file not found")
        else:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Final JSONL not ready. Upload files first.")

    return FileResponse(
        path=final_path,
        media_type="application/x-jsonlines",
        filename=f"batch_{batch_id}_final.jsonl",
    )


@router.get("/batches/{batch_id}/upload-status/")
async def get_upload_status(
    batch_id: str,
    current_user: UserResponse = Depends(get_current_user),
):
    batch = await batch_jobs_collection.find_one({"_id": bson.ObjectId(batch_id)})
    if not batch:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found")

    upload_status = batch.get("upload_status")

    return {
        "batch_id": str(batch["_id"]),
        "status": batch.get("status"),
        "upload_progress": upload_status,
    }


@router.post("/batches/{batch_id}/cancel/", response_model=BatchJobResponse)
async def cancel_batch_endpoint(
    batch_id: str,
    current_user: UserResponse = Depends(require_roles("admin", "teacher")),
):
    batch = await batch_jobs_collection.find_one({"_id": bson.ObjectId(batch_id)})
    if not batch:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found")

    if batch["status"] not in ("submitted", "in_progress", "uploading"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Can only cancel submitted, in-progress, or uploading batches"
        )

    exam = await exams_collection.find_one({"_id": batch["exam_id"]})
    if not exam:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exam not found")

    if current_user.role == "teacher":
        cls = await classes_collection.find_one({"_id": bson.ObjectId(exam["class_id"])})
        if not cls or current_user.id not in cls.get("teacher_ids", []):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

    provider_batch_id = batch.get("provider_batch_id")
    if provider_batch_id:
        provider = batch.get("provider", "gemini")
        cancelled = await batch_service.cancel_batch(provider, provider_batch_id)
        if not cancelled:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to cancel batch with provider"
            )

    now = datetime.utcnow()
    await batch_jobs_collection.update_one(
        {"_id": bson.ObjectId(batch_id)},
        {
            "$set": {
                "status": "cancelled",
                "completed_at": now,
            }
        }
    )

    await answer_sheets_collection.update_many(
        {"current_batch_id": bson.ObjectId(batch_id)},
        {"$set": {"status": "jsonl_ready", "updated_at": now}}
    )

    updated_batch = await batch_jobs_collection.find_one({"_id": bson.ObjectId(batch_id)})

    return BatchJobResponse(
        id=str(updated_batch["_id"]),
        exam_id=str(updated_batch["exam_id"]),
        provider=updated_batch.get("provider", "gemini"),
        model=updated_batch.get("model", "gemini-2.5-flash"),
        provider_batch_id=updated_batch.get("provider_batch_id"),
        input_file_path=updated_batch.get("input_file_path"),
        uploaded_jsonl_path=updated_batch.get("uploaded_jsonl_path"),
        output_file_path=updated_batch.get("output_file_path"),
        uploaded_gemini_files=updated_batch.get("uploaded_gemini_files"),
        item_count=updated_batch.get("item_count", 0),
        completed_count=updated_batch.get("completed_count", 0),
        failed_count=updated_batch.get("failed_count", 0),
        status="cancelled",
        upload_status=updated_batch.get("upload_status"),
        submitted_at=updated_batch.get("submitted_at"),
        completed_at=now,
        last_polled_at=updated_batch.get("last_polled_at"),
        poll_error=updated_batch.get("poll_error"),
        created_by=str(updated_batch["created_by"]) if updated_batch.get("created_by") else None,
        created_at=updated_batch["created_at"],
    )


@router.post("/batches/{batch_id}/refresh/", response_model=BatchDetailResponse)
async def refresh_batch_endpoint(
    batch_id: str,
    current_user: UserResponse = Depends(require_roles("admin", "teacher")),
):
    batch = await batch_jobs_collection.find_one({"_id": bson.ObjectId(batch_id)})
    if not batch:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found")

    if batch["status"] not in ("submitted", "in_progress", "uploading"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Can only cancel submitted, in-progress, or uploading batches"
        )

    exam = await exams_collection.find_one({"_id": batch["exam_id"]})
    if not exam:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exam not found")

    if current_user.role == "teacher":
        cls = await classes_collection.find_one({"_id": bson.ObjectId(exam["class_id"])})
        if not cls or current_user.id not in cls.get("teacher_ids", []):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

    from workers.batch_poller import poll_single_batch
    await poll_single_batch(batch)

    batch = await batch_jobs_collection.find_one({"_id": bson.ObjectId(batch_id)})
    items = await batch_items_collection.find(
        {"batch_id": bson.ObjectId(batch_id)}
    ).sort("created_at", 1).to_list(length=None)

    item_responses = [
        BatchItemResponse(
            id=str(it["_id"]),
            batch_id=str(it["batch_id"]),
            sheet_id=str(it["sheet_id"]),
            custom_id=it["custom_id"],
            prompt_preview=it.get("prompt_preview"),
            status=it.get("status", "pending"),
            error=it.get("error"),
            raw_response=it.get("raw_response"),
            created_at=it["created_at"],
        )
        for it in items
    ]

    return BatchDetailResponse(
        id=str(batch["_id"]),
        exam_id=str(batch["exam_id"]),
        provider=batch.get("provider", "gemini"),
        model=batch.get("model", "gemini-2.5-flash"),
        provider_batch_id=batch.get("provider_batch_id"),
        input_file_path=batch.get("input_file_path"),
        uploaded_jsonl_path=batch.get("uploaded_jsonl_path"),
        output_file_path=batch.get("output_file_path"),
        uploaded_gemini_files=batch.get("uploaded_gemini_files"),
        item_count=batch.get("item_count", 0),
        completed_count=batch.get("completed_count", 0),
        failed_count=batch.get("failed_count", 0),
        status=batch.get("status", "draft"),
        upload_status=batch.get("upload_status"),
        submitted_at=batch.get("submitted_at"),
        completed_at=batch.get("completed_at"),
        last_polled_at=batch.get("last_polled_at"),
        poll_error=batch.get("poll_error"),
        created_by=str(batch["created_by"]) if batch.get("created_by") else None,
        created_at=batch["created_at"],
        items=item_responses,
    )


@router.delete("/batches/{batch_id}/", status_code=status.HTTP_204_NO_CONTENT)
async def delete_batch_endpoint(
    batch_id: str,
    current_user: UserResponse = Depends(require_roles("admin", "teacher")),
):
    batch = await batch_jobs_collection.find_one({"_id": bson.ObjectId(batch_id)})
    if not batch:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found")

    if batch["status"] not in ("draft", "cancelled", "failed"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Can only delete draft, cancelled, or failed batches"
        )

    exam = await exams_collection.find_one({"_id": batch["exam_id"]})
    if not exam:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exam not found")

    if current_user.role == "teacher":
        cls = await classes_collection.find_one({"_id": bson.ObjectId(exam["class_id"])})
        if not cls or current_user.id not in cls.get("teacher_ids", []):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

    await batch_items_collection.delete_many({"batch_id": bson.ObjectId(batch_id)})
    await batch_jobs_collection.delete_one({"_id": bson.ObjectId(batch_id)})

    if batch["status"] == "draft":
        await answer_sheets_collection.update_many(
            {"current_batch_id": bson.ObjectId(batch_id)},
            {"$set": {"status": "mapped", "current_batch_id": None}}
        )

