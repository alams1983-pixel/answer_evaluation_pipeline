"""
Cleanup script for broken pending sheets.

Usage: python cleanup_pending_sheets.py
"""

import asyncio
import os
import sys

# Ensure backend directory is in sys.path for standalone script execution
backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

try:
    from db.database import AsyncSessionLocal
    from db.models import AnswerSheet, SheetPage, UploadBatch
    from core.config import settings
except ImportError:
    from backend.db.database import AsyncSessionLocal
    from backend.db.models import AnswerSheet, SheetPage, UploadBatch
    from backend.core.config import settings

from sqlalchemy import select, delete


async def cleanup():
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(AnswerSheet).where(AnswerSheet.status == "pending_mapping"))
        pending_sheets = res.scalars().all()

        if not pending_sheets:
            print("[OK] No pending sheets found. Nothing to clean up.")
            return

        print(f"Found {len(pending_sheets)} pending sheets to clean up.\n")

        batch_ids_to_delete = set()
        total_pages_deleted = 0

        for sheet in pending_sheets:
            sheet_id = str(sheet.id)
            print(f"Cleaning sheet {sheet_id}...")

            pdf_path = sheet.original_pdf_path
            if pdf_path and os.path.exists(pdf_path):
                os.remove(pdf_path)
                print(f"  Deleted PDF: {pdf_path}")

            if sheet.batch_upload_id:
                batch_ids_to_delete.add(sheet.batch_upload_id)

            p_res = await db.execute(select(SheetPage).where(SheetPage.sheet_id == sheet_id))
            pages = p_res.scalars().all()
            for page in pages:
                image_path = page.image_path
                if image_path and os.path.exists(image_path):
                    os.remove(image_path)
                    print(f"  Deleted image: {os.path.basename(image_path)}")
                total_pages_deleted += 1

            await db.execute(delete(SheetPage).where(SheetPage.sheet_id == sheet_id))

        sheet_ids = [s.id for s in pending_sheets]
        await db.execute(delete(AnswerSheet).where(AnswerSheet.id.in_(sheet_ids)))

        if batch_ids_to_delete:
            await db.execute(delete(UploadBatch).where(UploadBatch.id.in_(list(batch_ids_to_delete))))

        await db.commit()

    answer_sheets_dir = os.path.join(settings.STORAGE_PATH, "answer_sheets")
    if os.path.exists(answer_sheets_dir):
        for entry in os.listdir(answer_sheets_dir):
            entry_path = os.path.join(answer_sheets_dir, entry)
            if os.path.isdir(entry_path) and not os.listdir(entry_path):
                os.rmdir(entry_path)

    print(f"\n[OK] Cleaned {total_pages_deleted} page records. You can now re-upload the zip file.")


if __name__ == "__main__":
    asyncio.run(cleanup())
