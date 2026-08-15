from typing import List, Dict, Any, Optional
import re
from sqlalchemy import select
from datetime import datetime

from db.database import AsyncSessionLocal
from db.models import AnswerSheet, ExamStudent, User


def _normalize_name(name: str) -> str:
    if not name:
        return ""
    return re.sub(r'\s+', ' ', name.strip().lower())


def _calculate_match_confidence(sheet_name: Optional[str], sheet_roll: Optional[str],
                                 student_name: str, student_roll: Optional[str]) -> float:
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
    async with AsyncSessionLocal() as db:
        res = await db.execute(
            select(AnswerSheet).where(
                AnswerSheet.exam_id == exam_id,
                AnswerSheet.status == "pending_mapping",
            )
        )
        pending_sheets = res.scalars().all()
        if not pending_sheets:
            return []

        res = await db.execute(
            select(ExamStudent).where(
                ExamStudent.exam_id == exam_id,
                ExamStudent.status == "active",
            )
        )
        enrolled_students = res.scalars().all()
        if not enrolled_students:
            return []

        student_ids = [e.student_id for e in enrolled_students]
        res = await db.execute(
            select(User).where(
                User.id.in_(student_ids),
                User.is_active == True,
            )
        )
        students = res.scalars().all()
        students_by_id = {str(s.id): s for s in students}

        matches = []
        for sheet in pending_sheets:
            sheet_name = sheet.student_name
            sheet_roll = sheet.roll_no

            best_match = None
            best_confidence = 0.0

            for enrollment in enrolled_students:
                student = students_by_id.get(str(enrollment.student_id))
                if not student:
                    continue

                confidence = _calculate_match_confidence(
                    sheet_name=sheet_name,
                    sheet_roll=sheet_roll,
                    student_name=student.full_name,
                    student_roll=student.roll_no,
                )

                if confidence > best_confidence:
                    best_confidence = confidence
                    best_match = {
                        "student_id": str(student.id),
                        "full_name": student.full_name,
                        "roll_no": student.roll_no,
                        "email": student.email,
                    }

            if best_match and best_confidence > 0.0:
                matches.append({
                    "sheet_id": str(sheet.id),
                    "original_filename": sheet.original_filename or "",
                    "parsed_name": sheet_name,
                    "parsed_roll": sheet_roll,
                    "matched_student": best_match,
                    "confidence": best_confidence,
                })

        return sorted(matches, key=lambda m: m["confidence"], reverse=True)


async def apply_student_matches(exam_id: str, matches: List[Dict[str, Any]]) -> Dict[str, int]:
    matched_count = 0
    failed_count = 0

    async with AsyncSessionLocal() as db:
        for match in matches:
            try:
                sheet_id = match["sheet_id"]
                student_id = match["student_id"]

                res = await db.execute(
                    select(ExamStudent).where(
                        ExamStudent.exam_id == exam_id,
                        ExamStudent.student_id == student_id,
                        ExamStudent.status == "active",
                    )
                )
                if not res.scalar_one_or_none():
                    failed_count += 1
                    continue

                res = await db.execute(select(User).where(User.id == student_id))
                student = res.scalar_one_or_none()
                if not student:
                    failed_count += 1
                    continue

                res = await db.execute(
                    select(AnswerSheet).where(
                        AnswerSheet.id == sheet_id,
                        AnswerSheet.exam_id == exam_id,
                    )
                )
                sheet = res.scalar_one_or_none()
                if not sheet:
                    failed_count += 1
                    continue

                sheet.student_id = student_id
                sheet.status = "mapped"
                sheet.updated_at = datetime.utcnow()

                if not match.get("keep_parsed_name"):
                    sheet.student_name = student.full_name
                    if student.roll_no:
                        sheet.roll_no = student.roll_no

                matched_count += 1

            except Exception:
                failed_count += 1

        await db.commit()

    return {"matched_count": matched_count, "failed_count": failed_count}
