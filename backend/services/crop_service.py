import os
import base64
import time
from datetime import datetime
from typing import List, Dict, Any
from PIL import Image
from sqlalchemy import select, delete

from core.config import settings
from db.database import AsyncSessionLocal
from db.models import QuestionPaperCrop, QuestionPaper


async def save_crop(
    exam_id: str,
    question_index: int,
    q_no: str,
    page_no: int,
    source_pdf: str,
    bbox: Dict[str, int],
    image_data_base64: str,
) -> str:
    crop_dir = os.path.join(settings.STORAGE_PATH, "question_papers", exam_id, "crops")
    os.makedirs(crop_dir, exist_ok=True)

    timestamp = int(time.time() * 1000)
    crop_filename = f"q{q_no}_{page_no}_{timestamp}.png"
    crop_path = os.path.join(crop_dir, crop_filename)

    image_bytes = base64.b64decode(image_data_base64)
    with open(crop_path, "wb") as f:
        f.write(image_bytes)

    async with AsyncSessionLocal() as db:
        res = await db.execute(select(QuestionPaper).where(QuestionPaper.exam_id == exam_id))
        qp = res.scalar_one_or_none()
        qp_id = str(qp.id) if qp else ""

        crop_obj = QuestionPaperCrop(
            exam_id=exam_id,
            question_paper_id=qp_id,
            question_index=question_index,
            q_no=q_no,
            image_path=crop_path,
            source_pdf=source_pdf,
            page_no=page_no,
            bbox={
                "x": bbox.get("x", 0),
                "y": bbox.get("y", 0),
                "width": bbox.get("width", 0),
                "height": bbox.get("height", 0),
            },
            created_at=datetime.utcnow(),
        )
        db.add(crop_obj)
        await db.commit()
        await db.refresh(crop_obj)
        return str(crop_obj.id)


async def delete_crop(crop_id: str) -> bool:
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(QuestionPaperCrop).where(QuestionPaperCrop.id == crop_id))
        crop = res.scalar_one_or_none()
        if not crop:
            return False

        image_path = crop.image_path
        if image_path and os.path.exists(image_path):
            os.remove(image_path)

        await db.delete(crop)
        await db.commit()
        return True


async def get_crops_for_question(
    exam_id: str,
    question_index: int,
) -> List[Dict[str, Any]]:
    async with AsyncSessionLocal() as db:
        res = await db.execute(
            select(QuestionPaperCrop)
            .where(
                QuestionPaperCrop.exam_id == exam_id,
                QuestionPaperCrop.question_index == question_index,
            )
            .order_by(QuestionPaperCrop.created_at.asc())
        )
        crops = res.scalars().all()
        return [
            {
                "id": str(crop.id),
                "exam_id": crop.exam_id,
                "question_paper_id": str(crop.question_paper_id),
                "question_index": crop.question_index,
                "q_no": crop.q_no,
                "image_path": crop.image_path,
                "source_pdf": crop.source_pdf,
                "page_no": crop.page_no,
                "bbox": crop.bbox,
                "created_at": crop.created_at,
            }
            for crop in crops
        ]


async def get_all_crops_for_exam(exam_id: str) -> List[Dict[str, Any]]:
    async with AsyncSessionLocal() as db:
        res = await db.execute(
            select(QuestionPaperCrop)
            .where(QuestionPaperCrop.exam_id == exam_id)
            .order_by(QuestionPaperCrop.created_at.asc())
        )
        crops = res.scalars().all()
        return [
            {
                "id": str(crop.id),
                "exam_id": crop.exam_id,
                "question_paper_id": str(crop.question_paper_id),
                "question_index": crop.question_index,
                "q_no": crop.q_no,
                "image_path": crop.image_path,
                "source_pdf": crop.source_pdf,
                "page_no": crop.page_no,
                "bbox": crop.bbox,
                "created_at": crop.created_at,
            }
            for crop in crops
        ]


async def extract_crop_from_pdf(
    pdf_path: str,
    page_no: int,
    bbox: Dict[str, int],
    output_path: str,
    dpi: int = 150,
) -> bool:
    try:
        import fitz

        doc = fitz.open(pdf_path)
        if page_no < 1 or page_no > len(doc):
            doc.close()
            return False

        page = doc[page_no - 1]
        pix = page.get_pixmap(dpi=dpi)

        x = bbox.get("x", 0)
        y = bbox.get("y", 0)
        width = bbox.get("width", 0)
        height = bbox.get("height", 0)

        if width <= 0 or height <= 0:
            doc.close()
            return False

        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        cropped = img.crop((x, y, x + width, y + height))
        cropped.save(output_path, "PNG")

        doc.close()
        return True

    except Exception as e:
        print(f"[CropService] Failed to extract crop from PDF: {e}")
        return False
