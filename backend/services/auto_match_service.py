from typing import List, Dict, Any, Optional
import bson
import re

from db.database import (
    exam_students_collection,
    users_collection,
    answer_sheets_collection,
)


def _normalize_name(name: str) -> str:
    """Normalize a name for comparison: lowercase, strip whitespace."""
    if not name:
        return ""
    return re.sub(r'\s+', ' ', name.strip().lower())


def _calculate_match_confidence(sheet_name: Optional[str], sheet_roll: Optional[str],
                                 student_name: str, student_roll: Optional[str]) -> float:
    """
    Calculate match confidence between a sheet and a student.
    Returns a score from 0.0 to 1.0.
    """
    score = 0.0
    max_score = 0.0

    if sheet_roll and student_roll:
        max_score += 0.6
        if str(sheet_roll).strip().lower() == str(student_roll).strip().lower():
            score += 0.6

    if sheet_name:
        max_score += 0.4
        norm_sheet = _normalize_name(sheet_name)
        norm_student = _normalize_name(student_name)
        if norm_sheet == norm_student:
            score += 0.4
        elif norm_sheet in norm_student or norm_student in norm_sheet:
            score += 0.25
        else:
            parts_sheet = set(norm_sheet.split())
            parts_student = set(norm_student.split())
            if parts_sheet & parts_student:
                overlap = len(parts_sheet & parts_student) / max(len(parts_sheet), len(parts_student))
                score += overlap * 0.15

    if max_score == 0:
        return 0.0

    return round(score / max_score, 2)


async def find_student_matches(exam_id: str) -> List[Dict[str, Any]]:
    """
    Find potential matches between pending answer sheets and enrolled students.
    Returns a list of proposed matches with confidence scores.
    """
    pending_sheets = await answer_sheets_collection.find({
        "exam_id": bson.ObjectId(exam_id),
        "status": "pending_mapping",
    }).to_list(length=None)

    if not pending_sheets:
        return []

    enrolled_students = await exam_students_collection.find({
        "exam_id": bson.ObjectId(exam_id),
        "status": "active",
    }).to_list(length=None)

    if not enrolled_students:
        return []

    student_ids = [e["student_id"] for e in enrolled_students]
    students = await users_collection.find({
        "_id": {"$in": student_ids},
        "is_active": True,
    }).to_list(length=None)

    students_by_id = {str(s["_id"]): s for s in students}

    matches = []
    for sheet in pending_sheets:
        sheet_name = sheet.get("student_name")
        sheet_roll = sheet.get("roll_no")

        best_match = None
        best_confidence = 0.0

        for enrollment in enrolled_students:
            student = students_by_id.get(str(enrollment["student_id"]))
            if not student:
                continue

            confidence = _calculate_match_confidence(
                sheet_name=sheet_name,
                sheet_roll=sheet_roll,
                student_name=student["full_name"],
                student_roll=student.get("roll_no"),
            )

            if confidence > best_confidence:
                best_confidence = confidence
                best_match = {
                    "student_id": str(student["_id"]),
                    "full_name": student["full_name"],
                    "roll_no": student.get("roll_no"),
                    "email": student["email"],
                }

        if best_match and best_confidence > 0.0:
            matches.append({
                "sheet_id": str(sheet["_id"]),
                "original_filename": sheet.get("original_filename", ""),
                "parsed_name": sheet_name,
                "parsed_roll": sheet_roll,
                "matched_student": best_match,
                "confidence": best_confidence,
            })

    return sorted(matches, key=lambda m: m["confidence"], reverse=True)


async def apply_student_matches(exam_id: str, matches: List[Dict[str, str]]) -> Dict[str, int]:
    """
    Apply confirmed matches to answer sheets.
    Each match dict: {"sheet_id": "...", "student_id": "..."}
    Returns { matched_count, failed_count }.
    """
    matched_count = 0
    failed_count = 0

    for match in matches:
        try:
            sheet_id = bson.ObjectId(match["sheet_id"])
            student_id = bson.ObjectId(match["student_id"])

            enrollment = await exam_students_collection.find_one({
                "exam_id": bson.ObjectId(exam_id),
                "student_id": student_id,
                "status": "active",
            })

            if not enrollment:
                failed_count += 1
                continue

            student = await users_collection.find_one({"_id": student_id})
            if not student:
                failed_count += 1
                continue

            update_data = {
                "student_id": student_id,
                "status": "mapped",
                "updated_at": None,
            }

            if not match.get("keep_parsed_name"):
                update_data["student_name"] = student["full_name"]
                if student.get("roll_no"):
                    update_data["roll_no"] = student["roll_no"]

            result = await answer_sheets_collection.update_one(
                {"_id": sheet_id, "exam_id": bson.ObjectId(exam_id)},
                {"$set": update_data}
            )

            if result.modified_count > 0:
                matched_count += 1
            else:
                failed_count += 1

        except Exception:
            failed_count += 1

    return {"matched_count": matched_count, "failed_count": failed_count}
