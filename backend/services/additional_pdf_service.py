import os
import time
from datetime import datetime
from typing import List, Dict, Any, Optional
from fastapi import UploadFile
from sqlalchemy import select, delete

from core.config import settings
from db.database import AsyncSessionLocal
from db.models import AdditionalPdf
from services.pdf_service import rasterize_pdf_to_pngs


async def upload_additional_pdf(
    exam_id: str,
    file: UploadFile,
    label: str,
    pdf_type: str = "reference",
) -> Dict[str, Any]:
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

    async with AsyncSessionLocal() as db:
        pdf_obj = AdditionalPdf(
            exam_id=exam_id,
            source_file=file_path,
            label=label,
            type=pdf_type,
            total_pages=total_pages,
            filename=safe_name,
            created_at=datetime.utcnow(),
        )
        db.add(pdf_obj)
        await db.commit()
        await db.refresh(pdf_obj)

        return {
            "id": str(pdf_obj.id),
            "exam_id": exam_id,
            "source_file": file_path,
            "label": label,
            "type": pdf_type,
            "total_pages": total_pages,
            "filename": safe_name,
            "created_at": pdf_obj.created_at,
        }


async def list_additional_pdfs(exam_id: str) -> List[Dict[str, Any]]:
    async with AsyncSessionLocal() as db:
        res = await db.execute(
            select(AdditionalPdf)
            .where(AdditionalPdf.exam_id == exam_id)
            .order_by(AdditionalPdf.created_at.asc())
        )
        pdfs = res.scalars().all()
        return [
            {
                "id": str(pdf.id),
                "exam_id": pdf.exam_id,
                "source_file": pdf.source_file,
                "label": pdf.label,
                "type": pdf.type,
                "total_pages": pdf.total_pages,
                "filename": pdf.filename,
                "created_at": pdf.created_at,
            }
            for pdf in pdfs
        ]


async def delete_additional_pdf(pdf_id: str) -> bool:
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(AdditionalPdf).where(AdditionalPdf.id == pdf_id))
        pdf = res.scalar_one_or_none()
        if not pdf:
            return False

        source_file = pdf.source_file
        if source_file and os.path.exists(source_file):
            os.remove(source_file)

        pdf_dir = os.path.dirname(source_file) if source_file else ""
        if pdf_dir and os.path.exists(pdf_dir):
            for f in os.listdir(pdf_dir):
                if f.endswith(".png"):
                    os.remove(os.path.join(pdf_dir, f))
            if not os.listdir(pdf_dir):
                os.rmdir(pdf_dir)

        await db.delete(pdf)
        await db.commit()
        return True


async def get_additional_pdf(pdf_id: str) -> Optional[Dict[str, Any]]:
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(AdditionalPdf).where(AdditionalPdf.id == pdf_id))
        pdf = res.scalar_one_or_none()
        if not pdf:
            return None

        return {
            "id": str(pdf.id),
            "exam_id": pdf.exam_id,
            "source_file": pdf.source_file,
            "label": pdf.label,
            "type": pdf.type,
            "total_pages": pdf.total_pages,
            "filename": pdf.filename,
            "created_at": pdf.created_at,
        }
