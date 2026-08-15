import asyncio
import json
import os
import re
from datetime import datetime
from typing import List, Dict, Any
from sqlalchemy import select, update

from db.database import AsyncSessionLocal
from db.models import BatchJob, BatchItem, AnswerSheet, Exam, Grading
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
    items_by_custom_id: Dict[str, Any],
    sheets_by_id: Dict[str, Any],
) -> None:
    key = result_line.get("key", result_line.get("custom_id"))

    item = items_by_custom_id.get(key)
    if not item:
        return

    sheet_id = str(item.sheet_id)
    sheet = sheets_by_id.get(sheet_id)
    if not sheet:
        return

    async with AsyncSessionLocal() as db:
        if "error" in result_line and result_line["error"]:
            await db.execute(
                update(BatchItem)
                .where(BatchItem.id == item.id)
                .values(
                    status="failed",
                    error=str(result_line["error"]),
                    raw_response=result_line.get("response", result_line.get("body")),
                )
            )
            await db.execute(
                update(AnswerSheet)
                .where(AnswerSheet.id == sheet_id)
                .values(status="failed", updated_at=datetime.utcnow())
            )
            await db.commit()
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
            await db.execute(
                update(BatchItem)
                .where(BatchItem.id == item.id)
                .values(
                    status="failed",
                    error="Could not extract grading from response",
                    raw_response=response_data,
                )
            )
            await db.execute(
                update(AnswerSheet)
                .where(AnswerSheet.id == sheet_id)
                .values(status="failed", updated_at=datetime.utcnow())
            )
            await db.commit()
            return

        is_valid, error_msg = await validate_result_against_schema(grading_result, result_schema_id)
        if not is_valid:
            await db.execute(
                update(BatchItem)
                .where(BatchItem.id == item.id)
                .values(
                    status="failed",
                    error=f"Schema validation failed: {error_msg}",
                    raw_response=response_data,
                )
            )
            await db.execute(
                update(AnswerSheet)
                .where(AnswerSheet.id == sheet_id)
                .values(status="failed", updated_at=datetime.utcnow())
            )
            await db.commit()
            return

        await db.execute(
            update(BatchItem)
            .where(BatchItem.id == item.id)
            .values(
                status="completed",
                raw_response=response_data,
                error=None,
            )
        )

        grading_doc = await upsert_grading(
            sheet_id=sheet_id,
            exam_id=exam_id,
            batch_id=batch_id,
            result_schema_id=result_schema_id,
            result=grading_result,
        )

        await db.execute(
            update(AnswerSheet)
            .where(AnswerSheet.id == sheet_id)
            .values(status="graded", updated_at=datetime.utcnow())
        )
        await db.commit()

        print(f"[Poller] Graded sheet {sheet_id}: {grading_doc.get('total_awarded', 0)}/{grading_doc.get('total_max', 0)}")


async def poll_single_batch(batch_job: BatchJob) -> None:
    batch_id = str(batch_job.id)
    provider = batch_job.provider or "gemini"
    provider_batch_id = batch_job.provider_batch_id

    if not provider_batch_id:
        return

    try:
        status_info = await batch_service.poll_batch(provider, provider_batch_id)

        completed_count = status_info.get("completed_count", 0)
        failed_count = status_info.get("failed_count", 0)
        new_status = status_info.get("status")

        async with AsyncSessionLocal() as db:
            res = await db.execute(select(BatchJob).where(BatchJob.id == batch_id))
            b_obj = res.scalar_one_or_none()
            if not b_obj:
                return

            b_obj.last_polled_at = datetime.utcnow()
            b_obj.poll_error = status_info.get("error")

            if new_status and new_status != b_obj.status:
                b_obj.status = new_status

            if new_status == "completed":
                output_path = os.path.join(
                    settings.STORAGE_PATH,
                    "batches",
                    batch_id,
                    "output.jsonl",
                )

                if status_info.get("output_file_name") or status_info.get("output_file_id"):
                    await batch_service.download_output(
                        provider,
                        provider_batch_id,
                        output_path,
                    )
                    b_obj.output_file_path = output_path
                elif new_status == "completed":
                    b_obj.completed_count = completed_count
                    b_obj.failed_count = failed_count
                    b_obj.completed_at = datetime.utcnow()
                    await db.commit()
                    return

                output_lines = jsonl_service.parse_batch_output(output_path)

                bi_res = await db.execute(select(BatchItem).where(BatchItem.batch_id == batch_id))
                items = bi_res.scalars().all()
                items_by_custom_id = {item.custom_id: item for item in items}

                sh_res = await db.execute(select(AnswerSheet).where(AnswerSheet.exam_id == b_obj.exam_id))
                sheets = sh_res.scalars().all()
                sheets_by_id = {str(sheet.id): sheet for sheet in sheets}

                ex_res = await db.execute(select(Exam).where(Exam.id == b_obj.exam_id))
                exam = ex_res.scalar_one_or_none()
                result_schema_id = str(exam.result_schema_id) if (exam and exam.result_schema_id) else None

                for line in output_lines:
                    await process_single_result(
                        result_line=line,
                        batch_id=batch_id,
                        exam_id=str(b_obj.exam_id),
                        result_schema_id=result_schema_id,
                        items_by_custom_id=items_by_custom_id,
                        sheets_by_id=sheets_by_id,
                    )

                b_obj.completed_at = datetime.utcnow()

            b_obj.completed_count = completed_count
            b_obj.failed_count = failed_count
            await db.commit()

        print(f"[Poller] Batch {batch_id}: status={new_status}, completed={completed_count}, failed={failed_count}")

    except Exception as e:
        async with AsyncSessionLocal() as db:
            res = await db.execute(select(BatchJob).where(BatchJob.id == batch_id))
            b_obj = res.scalar_one_or_none()
            if b_obj:
                b_obj.last_polled_at = datetime.utcnow()
                b_obj.poll_error = str(e)
                await db.commit()
        print(f"[Poller] Error polling batch {batch_id}: {e}")


async def run_poller():
    while True:
        try:
            async with AsyncSessionLocal() as db:
                res = await db.execute(
                    select(BatchJob).where(BatchJob.status.in_(["submitted", "in_progress"]))
                )
                active_batches = res.scalars().all()

            if active_batches:
                print(f"[Poller] Polling {len(active_batches)} active batches...")
                for batch_job in active_batches:
                    await poll_single_batch(batch_job)
            else:
                print("[Poller] No active batches to poll")

        except Exception as e:
            print(f"[Poller] Poller loop error: {e}")

        await asyncio.sleep(settings.BATCH_POLL_INTERVAL_SEC)