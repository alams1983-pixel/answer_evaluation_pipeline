"""
Cleanup script for broken pending sheets (ObjectId mismatch bug).

Run this BEFORE re-uploading the zip file. It will:
1. Find all sheets with status "pending_mapping"
2. Delete their image files and PDF files from disk
3. Remove all related DB records (pages, sheets, batches)

Usage: python cleanup_pending_sheets.py
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from motor.motor_asyncio import AsyncIOMotorClient
from core.config import settings


async def cleanup():
    client = AsyncIOMotorClient(settings.MONGODB_URL)
    db = client[settings.DATABASE_NAME]
    sheets_col = db.get_collection("answer_sheets")
    pages_col = db.get_collection("sheet_pages")
    batches_col = db.get_collection("upload_batches")

    pending_sheets = await sheets_col.find({"status": "pending_mapping"}).to_list(length=None)

    if not pending_sheets:
        print("[OK] No pending sheets found. Nothing to clean up.")
        return

    print(f"Found {len(pending_sheets)} pending sheets to clean up.\n")

    batch_ids_to_delete = set()
    total_pages_deleted = 0

    for sheet in pending_sheets:
        sheet_id = str(sheet["_id"])
        print(f"Cleaning sheet {sheet_id}...")

        # Delete original PDF
        pdf_path = sheet.get("original_pdf_path")
        if pdf_path and os.path.exists(pdf_path):
            os.remove(pdf_path)
            print(f"  Deleted PDF: {pdf_path}")
        elif pdf_path:
            print(f"  PDF not found: {pdf_path}")

        if sheet.get("batch_upload_id"):
            batch_ids_to_delete.add(sheet["batch_upload_id"])

        # Find pages by sheet_id and delete their images
        pages = await pages_col.find({"sheet_id": sheet["_id"]}).to_list(length=None)
        for page in pages:
            image_path = page.get("image_path")
            if image_path and os.path.exists(image_path):
                os.remove(image_path)
                print(f"  Deleted image: {os.path.basename(image_path)}")
            total_pages_deleted += 1

        if pages:
            await pages_col.delete_many({"sheet_id": sheet["_id"]})

        # Also find orphan pages whose image_path references this sheet's directory
        if pdf_path:
            dir_name = os.path.splitext(os.path.basename(pdf_path))[0]
            escaped = dir_name.replace("\\", "\\\\")
            orphans = await pages_col.find({
                "image_path": {"$regex": escaped, "$options": "i"}
            }).to_list(length=None)
            for page in orphans:
                if str(page.get("sheet_id")) != sheet_id:
                    image_path = page.get("image_path")
                    if image_path and os.path.exists(image_path):
                        os.remove(image_path)
                        print(f"  Deleted orphan image: {os.path.basename(image_path)}")
                    await pages_col.delete_one({"_id": page["_id"]})
                    total_pages_deleted += 1

    # Delete sheet records
    sheet_ids = [s["_id"] for s in pending_sheets]
    await sheets_col.delete_many({"_id": {"$in": sheet_ids}})
    print(f"\nDeleted {len(sheet_ids)} sheet records.")

    # Delete batch records
    if batch_ids_to_delete:
        await batches_col.delete_many({"_id": {"$in": list(batch_ids_to_delete)}})
        print(f"Deleted {len(batch_ids_to_delete)} batch records.")

    # Clean up empty answer_sheets directories
    answer_sheets_dir = os.path.join(settings.STORAGE_PATH, "answer_sheets")
    if os.path.exists(answer_sheets_dir):
        for entry in os.listdir(answer_sheets_dir):
            entry_path = os.path.join(answer_sheets_dir, entry)
            if os.path.isdir(entry_path) and not os.listdir(entry_path):
                os.rmdir(entry_path)
                print(f"Removed empty dir: {entry}")

    print(f"\n[OK] Cleaned {total_pages_deleted} page records. You can now re-upload the zip file.")


if __name__ == "__main__":
    asyncio.run(cleanup())
