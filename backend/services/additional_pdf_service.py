import os
import time
import bson
from typing import List, Dict, Any, Optional
from fastapi import UploadFile

from core.config import settings
from db.database import (
    additional_pdfs_collection,
    exams_collection,
)
from services.pdf_service import rasterize_pdf_to_pngs


async def upload_additional_pdf(
    exam_id: str,
    file: UploadFile,
    label: str,
    pdf_type: str = "reference",
) -> Dict[str, Any]:
    """
    Upload a supplementary PDF for an exam.

    pdf_type: one of "instructions", "answer_key", "reference"
    Returns: dict with pdf_id, filename, total_pages
    """
    pdf_dir = os.path.join(settings.STORAGE_PATH, "question_papers", exam_id, "additional")
    os.makedirs(pdf_dir, exist_ok=True)

    original_filename = file.filename or "upload.pdf"
    safe_name = original_filename.replace(" ", "_")
    file_path = os.path.join(pdf_dir, safe_name)

    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)

    page_infos = rasterize_pdf_to_pngs(file_path, pdf_dir, dpi=150)
    total_pages = len(page_infos)

    pdf_doc = {
        "exam_id": exam_id,
        "source_file": file_path,
        "label": label,
        "type": pdf_type,
        "total_pages": total_pages,
        "filename": safe_name,
        "created_at": time.time(),
    }

    result = await additional_pdfs_collection.insert_one(pdf_doc)
    pdf_id = str(result.inserted_id)

    return {
        "id": pdf_id,
        "exam_id": exam_id,
        "source_file": file_path,
        "label": label,
        "type": pdf_type,
        "total_pages": total_pages,
        "filename": safe_name,
        "created_at": pdf_doc["created_at"],
    }


async def list_additional_pdfs(exam_id: str) -> List[Dict[str, Any]]:
    """List all supplementary PDFs for an exam."""
    pdfs = additional_pdfs_collection.find({"exam_id": exam_id}).sort("created_at", 1)

    result = []
    async for pdf in pdfs:
        result.append({
            "id": str(pdf["_id"]),
            "exam_id": pdf["exam_id"],
            "source_file": pdf["source_file"],
            "label": pdf["label"],
            "type": pdf["type"],
            "total_pages": pdf["total_pages"],
            "filename": pdf["filename"],
            "created_at": pdf["created_at"],
        })
    return result


async def delete_additional_pdf(pdf_id: str) -> bool:
    """Delete a supplementary PDF and its files."""
    pdf = await additional_pdfs_collection.find_one({"_id": bson.ObjectId(pdf_id)})
    if not pdf:
        return False

    source_file = pdf.get("source_file")
    if source_file and os.path.exists(source_file):
        os.remove(source_file)

    pdf_dir = os.path.dirname(source_file) if source_file else ""
    if pdf_dir and os.path.exists(pdf_dir):
        for f in os.listdir(pdf_dir):
            if f.endswith(".png"):
                os.remove(os.path.join(pdf_dir, f))
        if not os.listdir(pdf_dir):
            os.rmdir(pdf_dir)

    await additional_pdfs_collection.delete_one({"_id": bson.ObjectId(pdf_id)})
    return True


async def get_additional_pdf(pdf_id: str) -> Optional[Dict[str, Any]]:
    """Get a single supplementary PDF record."""
    pdf = await additional_pdfs_collection.find_one({"_id": bson.ObjectId(pdf_id)})
    if not pdf:
        return None

    return {
        "id": str(pdf["_id"]),
        "exam_id": pdf["exam_id"],
        "source_file": pdf["source_file"],
        "label": pdf["label"],
        "type": pdf["type"],
        "total_pages": pdf["total_pages"],
        "filename": pdf["filename"],
        "created_at": pdf["created_at"],
    }
