import asyncio
import json
import bson
import os
import re
from datetime import datetime
from typing import List, Dict, Any
from db.database import (
    batch_jobs_collection,
    batch_items_collection,
    answer_sheets_collection,
    gradings_collection,
    result_schemas_collection,
    exams_collection,
)
from services import batch_service
from services import jsonl_service
from services.grading_service import validate_result_against_schema, upsert_grading
from core.config import settings


def _extract_json_from_text(text: str) -> str:
    stripped = text.strip()

    patterns = [
        re.compile(r"^```json\s*\n([\s\S]*?)\n```\s*$", re.DOTALL),
        re.compile(r"^```\s*\n([\s\S]*?)\n```\s*$", re.DOTALL),
    ]

    for pattern in patterns:
        match = pattern.match(stripped)
        if match:
            return match.group(1).strip()

    return stripped


def _try_parse_json(text: str) -> Any:
    if text is None:
        return None
    if isinstance(text, (dict, list)):
        return text
    if isinstance(text, str):
        cleaned = _extract_json_from_text(text)
        try:
            return json.loads(cleaned)
        except (json.JSONDecodeError, TypeError):
            pass
    return None


async def process_single_result(
    result_line: Dict[str, Any],
    batch_id: str,
    exam_id: str,
    result_schema_id: str,
    items_by_custom_id: Dict[str, Dict[str, Any]],
    sheets_by_id: Dict[str, Dict[str, Any]],
) -> None:
    key = result_line.get("key", result_line.get("custom_id"))

    item = items_by_custom_id.get(key)
    if not item:
        return

    sheet_id = item["sheet_id"]
    sheet = sheets_by_id.get(str(sheet_id))
    if not sheet:
        return

    if "error" in result_line and result_line["error"]:
        await batch_items_collection.update_one(
            {"_id": item["_id"]},
            {
                "$set": {
                    "status": "failed",
                    "error": str(result_line["error"]),
                    "raw_response": result_line.get("response", result_line.get("body")),
                }
            }
        )
        await answer_sheets_collection.update_one(
            {"_id": sheet_id},
            {"$set": {"status": "failed", "updated_at": datetime.utcnow()}}
        )
        return

    response_data = result_line.get("response", result_line.get("body", {}))

    grading_result = None
    if response_data:
        if isinstance(response_data, dict):
            candidates = response_data.get("candidates", [])
            if candidates:
                parts = candidates[0].get("content", {}).get("parts", [])
                for part in parts:
                    if "text" in part:
                        grading_result = _try_parse_json(part["text"])
                        if grading_result:
                            break
            elif "result" in response_data:
                grading_result = _try_parse_json(response_data["result"])
            elif "choices" in response_data:
                content = response_data["choices"][0].get("message", {}).get("content", "")
                grading_result = _try_parse_json(content)

    if not grading_result:
        await batch_items_collection.update_one(
            {"_id": item["_id"]},
            {
                "$set": {
                    "status": "failed",
                    "error": "Could not extract grading from response",
                    "raw_response": response_data,
                }
            }
        )
        await answer_sheets_collection.update_one(
            {"_id": sheet_id},
            {"$set": {"status": "failed", "updated_at": datetime.utcnow()}}
        )
        return

    is_valid, error_msg = await validate_result_against_schema(grading_result, result_schema_id)
    if not is_valid:
        await batch_items_collection.update_one(
            {"_id": item["_id"]},
            {
                "$set": {
                    "status": "failed",
                    "error": f"Schema validation failed: {error_msg}",
                    "raw_response": response_data,
                }
            }
        )
        await answer_sheets_collection.update_one(
            {"_id": sheet_id},
            {"$set": {"status": "failed", "updated_at": datetime.utcnow()}}
        )
        return

    await batch_items_collection.update_one(
        {"_id": item["_id"]},
        {
            "$set": {
                "status": "completed",
                "raw_response": response_data,
                "error": None,
            }
        }
    )

    grading_doc = await upsert_grading(
        sheet_id=str(sheet_id),
        exam_id=str(exam_id),
        batch_id=str(batch_id),
        result_schema_id=result_schema_id,
        result=grading_result,
    )

    await answer_sheets_collection.update_one(
        {"_id": sheet_id},
        {"$set": {"status": "graded", "updated_at": datetime.utcnow()}}
    )

    print(f"[Poller] Graded sheet {sheet_id}: {grading_doc.get('total_awarded', 0)}/{grading_doc.get('total_max', 0)}")


async def poll_single_batch(batch_doc: Dict[str, Any]) -> None:
    batch_id = batch_doc["_id"]
    provider = batch_doc.get("provider", "gemini")
    provider_batch_id = batch_doc.get("provider_batch_id")

    if not provider_batch_id:
        return

    try:
        status_info = await batch_service.poll_batch(provider, provider_batch_id)

        completed_count = status_info.get("completed_count", 0)
        failed_count = status_info.get("failed_count", 0)
        new_status = status_info.get("status")

        update_fields = {
            "last_polled_at": datetime.utcnow(),
            "poll_error": status_info.get("error"),
        }

        if new_status and new_status != batch_doc.get("status"):
            update_fields["status"] = new_status

        if new_status == "completed":
            output_path = os.path.join(
                settings.STORAGE_PATH,
                "batches",
                str(batch_id),
                "output.jsonl",
            )

            if status_info.get("output_file_name") or status_info.get("output_file_id"):
                await batch_service.download_output(
                    provider,
                    provider_batch_id,
                    output_path,
                )
                update_fields["output_file_path"] = output_path
            elif new_status == "completed":
                await batch_jobs_collection.update_one(
                    {"_id": batch_id},
                    {
                        "$set": {
                            **update_fields,
                            "completed_count": completed_count,
                            "failed_count": failed_count,
                            "completed_at": datetime.utcnow(),
                        }
                    }
                )
                return

            output_lines = jsonl_service.parse_batch_output(output_path)

            items = await batch_items_collection.find(
                {"batch_id": batch_id}
            ).to_list(length=None)

            items_by_custom_id = {item["custom_id"]: item for item in items}

            sheets = await answer_sheets_collection.find(
                {"exam_id": batch_doc["exam_id"]}
            ).to_list(length=None)

            sheets_by_id = {str(sheet["_id"]): sheet for sheet in sheets}

            exam = await exams_collection.find_one({"_id": batch_doc["exam_id"]})
            result_schema_id = exam.get("result_schema_id") if exam else None

            if result_schema_id:
                result_schema_id = str(result_schema_id)

            for line in output_lines:
                await process_single_result(
                    result_line=line,
                    batch_id=batch_id,
                    exam_id=batch_doc["exam_id"],
                    result_schema_id=result_schema_id,
                    items_by_custom_id=items_by_custom_id,
                    sheets_by_id=sheets_by_id,
                )

            update_fields["completed_at"] = datetime.utcnow()

        update_fields["completed_count"] = completed_count
        update_fields["failed_count"] = failed_count

        await batch_jobs_collection.update_one(
            {"_id": batch_id},
            {"$set": update_fields}
        )

        print(f"[Poller] Batch {batch_id}: status={new_status}, completed={completed_count}, failed={failed_count}")

    except Exception as e:
        await batch_jobs_collection.update_one(
            {"_id": batch_id},
            {
                "$set": {
                    "last_polled_at": datetime.utcnow(),
                    "poll_error": str(e),
                }
            }
        )
        print(f"[Poller] Error polling batch {batch_id}: {e}")


async def run_poller():
    while True:
        try:
            active_batches = await batch_jobs_collection.find(
                {"status": {"$in": ["submitted", "in_progress"]}}
            ).to_list(length=None)

            if active_batches:
                print(f"[Poller] Polling {len(active_batches)} active batches...")
                for batch_doc in active_batches:
                    await poll_single_batch(batch_doc)
            else:
                print("[Poller] No active batches to poll")

        except Exception as e:
            print(f"[Poller] Poller loop error: {e}")

        await asyncio.sleep(settings.BATCH_POLL_INTERVAL_SEC)


def start_poller(app):
    @app.on_event("startup")
    async def startup_poller():
        asyncio.create_task(run_poller())
        print(f"[OK] Batch poller started (interval: {settings.BATCH_POLL_INTERVAL_SEC}s)")