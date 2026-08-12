import fitz
import os
from typing import List
from PIL import Image


def rasterize_pdf_to_pngs(
    pdf_path: str,
    output_dir: str,
    dpi: int = 150,
) -> List[dict]:
    """
    Rasterize a PDF file into PNG images, one per page.

    Args:
        pdf_path: Path to the PDF file.
        output_dir: Directory to save PNG images.
        dpi: Resolution for rendering.

    Returns:
        List of dicts with keys: page_no, image_path, width, height.
    """
    os.makedirs(output_dir, exist_ok=True)

    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")

    try:
        doc = fitz.open(pdf_path)
    except Exception as e:
        raise ValueError(f"Failed to open PDF file. The file may be corrupted, not a valid PDF, or password-protected. Details: {e}") from e

    if doc.is_encrypted:
        doc.close()
        raise ValueError("PDF file is password-protected. Please provide an unprotected PDF.")

    page_infos = []

    scale = dpi / 72.0

    try:
        for page_idx in range(len(doc)):
            page = doc[page_idx]
            mat = fitz.Matrix(scale, scale)
            pix = page.get_pixmap(matrix=mat)

            page_no = page_idx + 1
            image_filename = f"page_{page_no:03d}.png"
            image_path = os.path.join(output_dir, image_filename)

            pix.save(image_path)

            page_infos.append({
                "page_no": page_no,
                "image_path": image_path,
                "width": pix.width,
                "height": pix.height,
            })
    except Exception as e:
        raise ValueError(f"Failed to render PDF page {page_idx + 1}. The file may be corrupted. Details: {e}") from e
    finally:
        doc.close()

    return page_infos
