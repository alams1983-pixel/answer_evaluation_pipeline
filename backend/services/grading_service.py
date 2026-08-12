import json
import os
import bson
from datetime import datetime
from typing import Optional, Dict, Any, List
from db.database import (
    gradings_collection,
    batch_items_collection,
    answer_sheets_collection,
    result_schemas_collection,
    exams_collection,
)
from core.config import settings


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

    schema_doc = await result_schemas_collection.find_one({"_id": bson.ObjectId(result_schema_id)})
    if not schema_doc:
        return True, None

    schema_definition = schema_doc.get("schema_definition", {})
    if not schema_definition:
        return True, None

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

    existing = await gradings_collection.find_one({"sheet_id": bson.ObjectId(sheet_id)})

    student_id = None
    try:
        sheet = await answer_sheets_collection.find_one(
            {"_id": bson.ObjectId(sheet_id)},
            {"student_id": 1}
        )
        if sheet and sheet.get("student_id"):
            student_id = sheet["student_id"]
    except Exception:
        pass

    grading_doc = {
        "sheet_id": bson.ObjectId(sheet_id),
        "exam_id": bson.ObjectId(exam_id),
        "batch_id": bson.ObjectId(batch_id),
        "student_id": student_id,
        "result_schema_id": bson.ObjectId(result_schema_id) if result_schema_id else None,
        "result": result,
        "total_awarded": total_awarded,
        "total_max": total_max,
        "status": "auto",
        "reviewed_by": None,
        "reviewed_at": None,
        "published_at": None,
        "override_log": [],
        "created_at": datetime.utcnow(),
    }

    if existing:
        await gradings_collection.update_one(
            {"_id": existing["_id"]},
            {
                "$set": {
                    "result": result,
                    "total_awarded": total_awarded,
                    "total_max": total_max,
                    "status": "auto",
                    "published_at": None,
                    "student_id": student_id,
                }
            }
        )
        grading_doc["_id"] = existing["_id"]
        grading_doc["created_at"] = existing.get("created_at", grading_doc["created_at"])
        grading_doc["reviewed_by"] = existing.get("reviewed_by")
        grading_doc["reviewed_at"] = existing.get("reviewed_at")
        grading_doc["override_log"] = existing.get("override_log", [])
        grading_doc["published_at"] = None
    else:
        insert_result = await gradings_collection.insert_one(grading_doc)
        grading_doc["_id"] = insert_result.inserted_id

    return grading_doc


async def update_grading(
    grading_id: str,
    update_data: dict,
    updated_by: str,
) -> Optional[Dict[str, Any]]:
    grading = await gradings_collection.find_one({"_id": bson.ObjectId(grading_id)})
    if not grading:
        return None

    override_entry = {
        "by": bson.ObjectId(updated_by),
        "at": datetime.utcnow(),
        "patch": update_data,
    }

    set_fields = dict(update_data)
    set_fields["override_log"] = grading.get("override_log", []) + [override_entry]

    if "result" in update_data:
        new_total_awarded, new_total_max = _compute_totals(update_data["result"])
        set_fields["total_awarded"] = new_total_awarded
        set_fields["total_max"] = new_total_max

    set_fields["reviewed_by"] = bson.ObjectId(updated_by)
    set_fields["reviewed_at"] = datetime.utcnow()

    await gradings_collection.update_one(
        {"_id": bson.ObjectId(grading_id)},
        {"$set": set_fields}
    )

    return await gradings_collection.find_one({"_id": bson.ObjectId(grading_id)})


async def publish_grading(
    grading_id: str,
) -> Optional[Dict[str, Any]]:
    grading = await gradings_collection.find_one({"_id": bson.ObjectId(grading_id)})
    if not grading:
        return None

    await gradings_collection.update_one(
        {"_id": bson.ObjectId(grading_id)},
        {
            "$set": {
                "status": "published",
                "published_at": datetime.utcnow(),
            }
        }
    )

    await answer_sheets_collection.update_one(
        {"_id": grading["sheet_id"]},
        {"$set": {"status": "published", "updated_at": datetime.utcnow()}}
    )

    return await gradings_collection.find_one({"_id": bson.ObjectId(grading_id)})


async def publish_all_gradings_for_exam(
    exam_id: str,
) -> int:
    result = await gradings_collection.update_many(
        {
            "exam_id": bson.ObjectId(exam_id),
            "status": {"$in": ["auto", "reviewed", "overridden"]},
        },
        {
            "$set": {
                "status": "published",
                "published_at": datetime.utcnow(),
            }
        }
    )

    await answer_sheets_collection.update_many(
        {
            "exam_id": bson.ObjectId(exam_id),
            "status": {"$in": ["graded", "reviewed", "overridden"]},
        },
        {
            "$set": {
                "status": "published",
                "updated_at": datetime.utcnow(),
            }
        }
    )

    return result.modified_count
