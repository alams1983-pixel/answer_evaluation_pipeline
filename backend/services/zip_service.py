import zipfile
import os
import shutil
from typing import List, Optional
from dataclasses import dataclass


@dataclass
class ParsedFilename:
    """Result of parsing a PDF filename."""
    original_filename: str
    student_name: Optional[str] = None
    roll_no: Optional[str] = None
    class_label: Optional[str] = None
    section: Optional[str] = None


def parse_pdf_filename(filename: str) -> ParsedFilename:
    """
    Parse a PDF filename using the convention:
    `studentName_rollNo_class_section.pdf` or variations.

    Examples:
        - "RajKumar_23_10A.pdf" → name="RajKumar", roll="23", class="10A"
        - "RajKumar_23_10A_B.pdf" → name="RajKumar", roll="23", class="10A", section="B"
        - "RajKumar_23.pdf" → name="RajKumar", roll="23"
        - "unknown.pdf" → all fields None
    """
    base = os.path.splitext(filename)[0]
    parts = base.split("_")

    result = ParsedFilename(
        original_filename=filename,
        student_name=None,
        roll_no=None,
        class_label=None,
        section=None,
    )

    if len(parts) >= 3:
        result.student_name = parts[0]
        result.roll_no = parts[1]
        result.class_label = parts[2]
        if len(parts) >= 4:
            result.section = parts[3]
    elif len(parts) == 2:
        result.student_name = parts[0]
        result.roll_no = parts[1]
    else:
        result.student_name = base

    return result


def extract_pdf_files_from_zip(
    zip_path: str,
    extract_dir: str,
) -> List[str]:
    """
    Extract only PDF files from a ZIP archive.

    Args:
        zip_path: Path to the ZIP file.
        extract_dir: Directory to extract PDFs into.

    Returns:
        List of extracted PDF file paths (absolute).
    """
    os.makedirs(extract_dir, exist_ok=True)
    extracted_pdfs = []

    with zipfile.ZipFile(zip_path, "r") as zf:
        for entry in zf.namelist():
            if entry.lower().endswith(".pdf") and not entry.startswith("__MACOSX"):
                filename = os.path.basename(entry)
                dest_path = os.path.join(extract_dir, filename)
                with zf.open(entry) as src, open(dest_path, "wb") as dst:
                    shutil.copyfileobj(src, dst)
                extracted_pdfs.append(dest_path)

    extracted_pdfs.sort()
    return extracted_pdfs


def cleanup_extract_dir(extract_dir: str):
    """Remove a temporary extraction directory."""
    if os.path.exists(extract_dir):
        shutil.rmtree(extract_dir)
