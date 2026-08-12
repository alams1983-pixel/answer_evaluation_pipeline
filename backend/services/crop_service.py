import os
import base64
import time
import bson
from typing import List, Dict, Any, Optional

from PIL import Image
import io

from core.config import settings
from db.database import (
    question_paper_crops_collection,
    question_papers_collection,
    exams_collection,
)


async def save_crop(
    exam_id: str,
    question_index: int,
    q_no: str,
    page_no: int,
    source_pdf: str,
    bbox: Dict[str, int],
    image_data_base64: str,
) -> str:
    """
    Save a cropped image attachment for a question.

    The frontend sends a base64-encoded PNG of the cropped region.
    We decode it, save to storage, and create a DB record.

    Returns: crop_id
    """
    crop_dir = os.path.join(settings.STORAGE_PATH, "question_papers", exam_id, "crops")
    os.makedirs(crop_dir, exist_ok=True)

    timestamp = int(time.time() * 1000)
    crop_filename = f"q{q_no}_{page_no}_{timestamp}.png"
    crop_path = os.path.join(crop_dir, crop_filename)

    image_bytes = base64.b64decode(image_data_base64)
    with open(crop_path, "wb") as f:
        f.write(image_bytes)

    qp = await question_papers_collection.find_one({"exam_id": exam_id})
    qp_id = str(qp["_id"]) if qp else ""

    crop_doc = {
        "exam_id": exam_id,
        "question_paper_id": qp_id,
        "question_index": question_index,
        "q_no": q_no,
        "image_path": crop_path,
        "source_pdf": source_pdf,
        "page_no": page_no,
        "bbox": {
            "x": bbox.get("x", 0),
            "y": bbox.get("y", 0),
            "width": bbox.get("width", 0),
            "height": bbox.get("height", 0),
        },
        "created_at": time.time(),
    }

    result = await question_paper_crops_collection.insert_one(crop_doc)
    return str(result.inserted_id)


async def delete_crop(crop_id: str) -> bool:
    """Delete a crop record and its image file."""
    crop = await question_paper_crops_collection.find_one({"_id": bson.ObjectId(crop_id)})
    if not crop:
        return False

    image_path = crop.get("image_path")
    if image_path and os.path.exists(image_path):
        os.remove(image_path)

    await question_paper_crops_collection.delete_one({"_id": bson.ObjectId(crop_id)})
    return True


async def get_crops_for_question(
    exam_id: str,
    question_index: int,
) -> List[Dict[str, Any]]:
    """Get all crop images attached to a specific question."""
    crops = question_paper_crops_collection.find({
        "exam_id": exam_id,
        "question_index": question_index,
    }).sort("created_at", 1)

    result = []
    async for crop in crops:
        result.append({
            "id": str(crop["_id"]),
            "exam_id": crop["exam_id"],
            "question_paper_id": str(crop["question_paper_id"]),
            "question_index": crop["question_index"],
            "q_no": crop["q_no"],
            "image_path": crop["image_path"],
            "source_pdf": crop["source_pdf"],
            "page_no": crop["page_no"],
            "bbox": crop["bbox"],
            "created_at": crop["created_at"],
        })
    return result


async def get_all_crops_for_exam(exam_id: str) -> List[Dict[str, Any]]:
    """Get all crop images for an exam."""
    crops = question_paper_crops_collection.find({
        "exam_id": exam_id,
    }).sort("created_at", 1)

    result = []
    async for crop in crops:
        result.append({
            "id": str(crop["_id"]),
            "exam_id": crop["exam_id"],
            "question_paper_id": str(crop["question_paper_id"]),
            "question_index": crop["question_index"],
            "q_no": crop["q_no"],
            "image_path": crop["image_path"],
            "source_pdf": crop["source_pdf"],
            "page_no": crop["page_no"],
            "bbox": crop["bbox"],
            "created_at": crop["created_at"],
        })
    return result


async def extract_crop_from_pdf(
    pdf_path: str,
    page_no: int,
    bbox: Dict[str, int],
    output_path: str,
    dpi: int = 150,
) -> bool:
    """
    Extract a region from a PDF page and save as PNG.
    Used when the frontend sends bbox coordinates instead of a pre-cropped image.

    Returns: True if successful
    """
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
