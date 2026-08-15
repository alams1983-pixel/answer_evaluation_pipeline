import json
from datetime import datetime
from typing import Optional, Dict, Any
from sqlalchemy import select, update

from db.database import AsyncSessionLocal
from db.models import Grading, ResultSchema, AnswerSheet


def _compute_totals(result: dict) -> tuple:
    total_awarded = 0.0
    total_max = 0.0

    if "total_awarded" in result:
        total_awarded = float(result["total_awarded"])
    if "total_max" in result:
        total_max = float(result["total_max"])

    questions = result.get("questions", [])
    if questions:
        q_awarded = sum(float(q.get("awarded", 0)) for q in questions if isinstance(q, dict))
        q_max = sum(float(q.get("max", 0)) for q in questions if isinstance(q, dict))
        if q_max > 0:
            total_awarded = q_awarded
            total_max = q_max

    return total_awarded, total_max


async def validate_result_against_schema(
    result: dict,
    result_schema_id: Optional[str],
) -> tuple[bool, Optional[str]]:
    if not result_schema_id:
        return True, None

    async with AsyncSessionLocal() as db:
        res = await db.execute(select(ResultSchema).where(ResultSchema.id == result_schema_id))
        schema_doc = res.scalar_one_or_none()
        if not schema_doc or not schema_doc.schema_definition:
            return True, None

        schema_definition = schema_doc.schema_definition

    try:
        import jsonschema
        jsonschema.validate(instance=result, schema=schema_definition)
        return True, None
    except jsonschema.ValidationError as e:
        return False, str(e.message)


async def upsert_grading(
    sheet_id: str,
    exam_id: str,
    batch_id: str,
    result_schema_id: Optional[str],
    result: dict,
) -> Dict[str, Any]:
    total_awarded, total_max = _compute_totals(result)

    async with AsyncSessionLocal() as db:
        res = await db.execute(select(AnswerSheet).where(AnswerSheet.id == sheet_id))
        sheet = res.scalar_one_or_none()
        student_id = str(sheet.student_id) if (sheet and sheet.student_id) else None

        g_res = await db.execute(select(Grading).where(Grading.sheet_id == sheet_id))
        existing = g_res.scalar_one_or_none()

        if existing:
            existing.result = result
            existing.total_awarded = total_awarded
            existing.total_max = total_max
            existing.status = "auto"
            existing.published_at = None
            existing.student_id = student_id
            await db.commit()
            await db.refresh(existing)
            grading_obj = existing
        else:
            grading_obj = Grading(
                sheet_id=sheet_id,
                exam_id=exam_id,
                batch_id=batch_id,
                student_id=student_id,
                result_schema_id=result_schema_id,
                result=result,
                total_awarded=total_awarded,
                total_max=total_max,
                status="auto",
                reviewed_by=None,
                reviewed_at=None,
                published_at=None,
                override_log=[],
                created_at=datetime.utcnow(),
            )
            db.add(grading_obj)
            await db.commit()
            await db.refresh(grading_obj)

        return {
            "id": str(grading_obj.id),
            "sheet_id": str(grading_obj.sheet_id),
            "exam_id": str(grading_obj.exam_id),
            "batch_id": str(grading_obj.batch_id),
            "student_id": str(grading_obj.student_id) if grading_obj.student_id else None,
            "result_schema_id": str(grading_obj.result_schema_id) if grading_obj.result_schema_id else None,
            "result": grading_obj.result or {},
            "total_awarded": grading_obj.total_awarded or 0.0,
            "total_max": grading_obj.total_max or 0.0,
            "status": grading_obj.status or "auto",
        }


async def update_grading(
    grading_id: str,
    update_data: dict,
    updated_by: str,
) -> Optional[Dict[str, Any]]:
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(Grading).where(Grading.id == grading_id))
        grading = res.scalar_one_or_none()
        if not grading:
            return None

        override_log = list(grading.override_log or [])
        override_log.append({
            "by": updated_by,
            "at": datetime.utcnow().isoformat(),
            "patch": update_data,
        })
        grading.override_log = override_log

        if "result" in update_data:
            grading.result = update_data["result"]
            new_awarded, new_max = _compute_totals(update_data["result"])
            grading.total_awarded = new_awarded
            grading.total_max = new_max
        if "status" in update_data:
            grading.status = update_data["status"]

        grading.reviewed_by = updated_by
        grading.reviewed_at = datetime.utcnow()

        await db.commit()
        await db.refresh(grading)

        return {
            "id": str(grading.id),
            "sheet_id": str(grading.sheet_id),
            "exam_id": str(grading.exam_id),
            "batch_id": str(grading.batch_id),
            "student_id": str(grading.student_id) if grading.student_id else None,
            "result_schema_id": str(grading.result_schema_id) if grading.result_schema_id else None,
            "result": grading.result or {},
            "total_awarded": grading.total_awarded or 0.0,
            "total_max": grading.total_max or 0.0,
            "status": grading.status or "auto",
            "reviewed_by": str(grading.reviewed_by) if grading.reviewed_by else None,
            "reviewed_at": grading.reviewed_at,
            "published_at": grading.published_at,
            "override_log": grading.override_log or [],
            "created_at": grading.created_at,
        }


async def publish_grading(
    grading_id: str,
) -> Optional[Dict[str, Any]]:
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(Grading).where(Grading.id == grading_id))
        grading = res.scalar_one_or_none()
        if not grading:
            return None

        grading.status = "published"
        grading.published_at = datetime.utcnow()

        await db.execute(
            update(AnswerSheet)
            .where(AnswerSheet.id == grading.sheet_id)
            .values(status="published", updated_at=datetime.utcnow())
        )

        await db.commit()
        await db.refresh(grading)

        return {
            "id": str(grading.id),
            "sheet_id": str(grading.sheet_id),
            "exam_id": str(grading.exam_id),
            "batch_id": str(grading.batch_id),
            "student_id": str(grading.student_id) if grading.student_id else None,
            "result_schema_id": str(grading.result_schema_id) if grading.result_schema_id else None,
            "result": grading.result or {},
            "total_awarded": grading.total_awarded or 0.0,
            "total_max": grading.total_max or 0.0,
            "status": grading.status or "published",
            "reviewed_by": str(grading.reviewed_by) if grading.reviewed_by else None,
            "reviewed_at": grading.reviewed_at,
            "published_at": grading.published_at,
            "override_log": grading.override_log or [],
            "created_at": grading.created_at,
        }


async def publish_all_gradings_for_exam(
    exam_id: str,
) -> int:
    async with AsyncSessionLocal() as db:
        g_res = await db.execute(
            update(Grading)
            .where(Grading.exam_id == exam_id, Grading.status.in_(["auto", "reviewed", "overridden"]))
            .values(status="published", published_at=datetime.utcnow())
        )

        await db.execute(
            update(AnswerSheet)
            .where(AnswerSheet.exam_id == exam_id, AnswerSheet.status.in_(["graded", "reviewed", "overridden"]))
            .values(status="published", updated_at=datetime.utcnow())
        )

        await db.commit()
        return g_res.rowcount
