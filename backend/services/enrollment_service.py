from datetime import datetime
from typing import List, Dict, Any, Optional
import bson

from db.database import (
    exam_students_collection,
    users_collection,
    exams_collection,
    classes_collection,
    answer_sheets_collection,
    gradings_collection,
)


async def populate_exam_students(exam_id: str, class_id: str) -> int:
    """
    Auto-populate exam_students with all active students from the exam's class.
    Returns the number of students enrolled.
    """
    students = await users_collection.find({
        "role": "student",
        "class_id": bson.ObjectId(class_id),
        "is_active": True,
    }).to_list(length=None)

    if not students:
        return 0

    enrollments = []
    for student in students:
        enrollments.append({
            "exam_id": bson.ObjectId(exam_id),
            "student_id": student["_id"],
            "enrolled_at": datetime.utcnow(),
            "status": "active",
            "removed_at": None,
        })

    if enrollments:
        await exam_students_collection.insert_many(enrollments)

    return len(enrollments)


async def sync_exam_students(exam_id: str, class_id: str) -> Dict[str, int]:
    """
    Sync exam_students with the current class enrollment.
    - Adds new students (in class but not in exam_students) as "active"
    - Marks removed students (in exam_students but not in class) as "removed"
    Returns { added_count, removed_count, total_active }.
    """
    current_class_students = await users_collection.find({
        "role": "student",
        "class_id": bson.ObjectId(class_id),
        "is_active": True,
    }).to_list(length=None)

    current_student_ids = {str(s["_id"]) for s in current_class_students}

    existing_enrollments = await exam_students_collection.find({
        "exam_id": bson.ObjectId(exam_id),
    }).to_list(length=None)

    existing_student_ids = {str(e["student_id"]) for e in existing_enrollments}

    added_count = 0
    removed_count = 0

    students_to_add = current_student_ids - existing_student_ids
    if students_to_add:
        new_enrollments = []
        for sid in students_to_add:
            new_enrollments.append({
                "exam_id": bson.ObjectId(exam_id),
                "student_id": bson.ObjectId(sid),
                "enrolled_at": datetime.utcnow(),
                "status": "active",
                "removed_at": None,
            })
        if new_enrollments:
            await exam_students_collection.insert_many(new_enrollments)
        added_count = len(students_to_add)

    students_to_remove = existing_student_ids - current_student_ids
    if students_to_remove:
        student_object_ids = [bson.ObjectId(sid) for sid in students_to_remove]
        await exam_students_collection.update_many(
            {
                "exam_id": bson.ObjectId(exam_id),
                "student_id": {"$in": student_object_ids},
                "status": "active",
            },
            {
                "$set": {
                    "status": "removed",
                    "removed_at": datetime.utcnow(),
                }
            }
        )
        removed_count = len(students_to_remove)

    total_active = await exam_students_collection.count_documents({
        "exam_id": bson.ObjectId(exam_id),
        "status": "active",
    })

    return {
        "added_count": added_count,
        "removed_count": removed_count,
        "total_active": total_active,
    }


async def get_exam_students(exam_id: str, include_sheet_status: bool = False) -> List[Dict[str, Any]]:
    """
    Get all enrolled students for an exam, with their user details and enrollment status.
    If include_sheet_status is True, also includes the mapping status of answer sheets.
    """
    enrollments = await exam_students_collection.find({
        "exam_id": bson.ObjectId(exam_id),
    }).sort("enrolled_at", 1).to_list(length=None)

    if not enrollments:
        return []

    student_ids = [e["student_id"] for e in enrollments]
    students = await users_collection.find({
        "_id": {"$in": student_ids},
    }).to_list(length=None)

    students_by_id = {str(s["_id"]): s for s in students}

    sheet_status_map = {}
    if include_sheet_status:
        sheets = await answer_sheets_collection.find({
            "exam_id": bson.ObjectId(exam_id),
            "student_id": {"$in": student_ids},
        }).to_list(length=None)

        for sheet in sheets:
            sid = str(sheet.get("student_id"))
            if sid:
                current = sheet_status_map.get(sid)
                if not current or sheet["status"] in ("graded", "reviewed", "published"):
                    sheet_status_map[sid] = {
                        "status": sheet["status"],
                        "sheet_id": str(sheet["_id"]),
                        "student_name": sheet.get("student_name"),
                        "roll_no": sheet.get("roll_no"),
                        "original_filename": sheet.get("original_filename"),
                    }

    result = []
    for enrollment in enrollments:
        student = students_by_id.get(str(enrollment["student_id"]))
        if student:
            entry = {
                "id": str(student["_id"]),
                "email": student["email"],
                "full_name": student["full_name"],
                "role": student["role"],
                "class_id": str(student["class_id"]) if student.get("class_id") else None,
                "roll_no": student.get("roll_no"),
                "is_active": student.get("is_active", True),
                "enrollment_status": enrollment["status"],
                "enrolled_at": enrollment["enrolled_at"],
                "removed_at": enrollment.get("removed_at"),
            }

            if include_sheet_status:
                sid = str(student["_id"])
                sheet_info = sheet_status_map.get(sid)
                if sheet_info:
                    entry["sheet_status"] = sheet_info["status"]
                    entry["sheet_id"] = sheet_info["sheet_id"]
                    entry["sheet_filename"] = sheet_info.get("original_filename")
                else:
                    entry["sheet_status"] = "no_sheet"
                    entry["sheet_id"] = None
                    entry["sheet_filename"] = None

            result.append(entry)

    return result


async def get_exam_students_summary(exam_id: str) -> Dict[str, int]:
    """
    Get summary counts for an exam's enrolled students.
    """
    active_count = await exam_students_collection.count_documents({
        "exam_id": bson.ObjectId(exam_id),
        "status": "active",
    })

    removed_count = await exam_students_collection.count_documents({
        "exam_id": bson.ObjectId(exam_id),
        "status": "removed",
    })

    mapped_sheets = await answer_sheets_collection.count_documents({
        "exam_id": bson.ObjectId(exam_id),
        "student_id": {"$ne": None},
        "status": {"$in": ["mapped", "graded", "reviewed", "published", "overridden"]},
    })

    unmapped_sheets = await answer_sheets_collection.count_documents({
        "exam_id": bson.ObjectId(exam_id),
        "student_id": {"$eq": None},
        "status": "pending_mapping",
    })

    return {
        "active_students": active_count,
        "removed_students": removed_count,
        "mapped_sheets": mapped_sheets,
        "unmapped_sheets": unmapped_sheets,
    }


async def get_enrolled_students_for_dropdown(exam_id: str) -> List[Dict[str, Any]]:
    """
    Get active enrolled students for a dropdown selector.
    Returns minimal data: id, full_name, roll_no.
    """
    enrollments = await exam_students_collection.find({
        "exam_id": bson.ObjectId(exam_id),
        "status": "active",
    }).to_list(length=None)

    if not enrollments:
        return []

    student_ids = [e["student_id"] for e in enrollments]
    students = await users_collection.find({
        "_id": {"$in": student_ids},
        "is_active": True,
    }).to_list(length=None)

    result = []
    for student in students:
        result.append({
            "id": str(student["_id"]),
            "full_name": student["full_name"],
            "roll_no": student.get("roll_no"),
            "email": student["email"],
        })

    return sorted(result, key=lambda x: x.get("roll_no", "") or "")
