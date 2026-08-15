from datetime import datetime
from typing import List, Dict, Any
from sqlalchemy import select, func, update, delete

from db.database import AsyncSessionLocal
from db.models import ExamStudent, User, AnswerSheet


async def populate_exam_students(exam_id: str, class_id: str) -> int:
    async with AsyncSessionLocal() as db:
        res = await db.execute(
            select(User).where(
                User.role == "student",
                User.class_id == class_id,
                User.is_active == True,
            )
        )
        students = res.scalars().all()
        if not students:
            return 0

        enrollments = []
        for student in students:
            enrollments.append(
                ExamStudent(
                    exam_id=exam_id,
                    student_id=student.id,
                    created_at=datetime.utcnow(),
                    status="active",
                )
            )

        db.add_all(enrollments)
        await db.commit()
        return len(enrollments)


async def sync_exam_students(exam_id: str, class_id: str) -> Dict[str, int]:
    async with AsyncSessionLocal() as db:
        res = await db.execute(
            select(User).where(
                User.role == "student",
                User.class_id == class_id,
                User.is_active == True,
            )
        )
        current_class_students = res.scalars().all()
        current_student_ids = {str(s.id) for s in current_class_students}

        res = await db.execute(select(ExamStudent).where(ExamStudent.exam_id == exam_id))
        existing_enrollments = res.scalars().all()
        existing_student_ids = {str(e.student_id) for e in existing_enrollments}

        students_to_add = current_student_ids - existing_student_ids
        added_count = 0
        if students_to_add:
            for sid in students_to_add:
                db.add(
                    ExamStudent(
                        exam_id=exam_id,
                        student_id=sid,
                        created_at=datetime.utcnow(),
                        status="active",
                    )
                )
            added_count = len(students_to_add)

        students_to_remove = existing_student_ids - current_student_ids
        removed_count = 0
        if students_to_remove:
            await db.execute(
                update(ExamStudent)
                .where(
                    ExamStudent.exam_id == exam_id,
                    ExamStudent.student_id.in_(list(students_to_remove)),
                    ExamStudent.status == "active",
                )
                .values(status="removed", updated_at=datetime.utcnow())
            )
            removed_count = len(students_to_remove)

        await db.commit()

        res_active = await db.execute(
            select(func.count(ExamStudent.id)).where(
                ExamStudent.exam_id == exam_id,
                ExamStudent.status == "active",
            )
        )
        total_active = res_active.scalar() or 0

        return {
            "added_count": added_count,
            "removed_count": removed_count,
            "total_active": total_active,
        }


async def get_exam_students(exam_id: str, include_sheet_status: bool = False) -> List[Dict[str, Any]]:
    async with AsyncSessionLocal() as db:
        res = await db.execute(
            select(ExamStudent).where(ExamStudent.exam_id == exam_id).order_by(ExamStudent.created_at.asc())
        )
        enrollments = res.scalars().all()
        if not enrollments:
            return []

        student_ids = [e.student_id for e in enrollments]
        res = await db.execute(select(User).where(User.id.in_(student_ids)))
        students = res.scalars().all()
        students_by_id = {str(s.id): s for s in students}

        sheet_status_map = {}
        if include_sheet_status:
            sh_res = await db.execute(
                select(AnswerSheet).where(
                    AnswerSheet.exam_id == exam_id,
                    AnswerSheet.student_id.in_(student_ids),
                )
            )
            sheets = sh_res.scalars().all()
            for sheet in sheets:
                sid = str(sheet.student_id)
                current = sheet_status_map.get(sid)
                if not current or sheet.status in ("graded", "reviewed", "published"):
                    sheet_status_map[sid] = {
                        "status": sheet.status,
                        "sheet_id": str(sheet.id),
                        "student_name": sheet.student_name,
                        "roll_no": sheet.roll_no,
                        "original_filename": sheet.original_filename,
                    }

        result = []
        for enrollment in enrollments:
            student = students_by_id.get(str(enrollment.student_id))
            if student:
                entry = {
                    "id": str(student.id),
                    "email": student.email,
                    "full_name": student.full_name,
                    "role": student.role,
                    "class_id": str(student.class_id) if student.class_id else None,
                    "roll_no": student.roll_no,
                    "is_active": student.is_active,
                    "enrollment_status": enrollment.status,
                    "enrolled_at": enrollment.created_at,
                    "removed_at": enrollment.updated_at if enrollment.status == "removed" else None,
                }

                if include_sheet_status:
                    sid = str(student.id)
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
    async with AsyncSessionLocal() as db:
        r_act = await db.execute(select(func.count(ExamStudent.id)).where(ExamStudent.exam_id == exam_id, ExamStudent.status == "active"))
        active_count = r_act.scalar() or 0

        r_rem = await db.execute(select(func.count(ExamStudent.id)).where(ExamStudent.exam_id == exam_id, ExamStudent.status == "removed"))
        removed_count = r_rem.scalar() or 0

        r_map = await db.execute(select(func.count(AnswerSheet.id)).where(AnswerSheet.exam_id == exam_id, AnswerSheet.student_id != None, AnswerSheet.status.in_(["mapped", "graded", "reviewed", "published", "overridden"])))
        mapped_sheets = r_map.scalar() or 0

        r_unmap = await db.execute(select(func.count(AnswerSheet.id)).where(AnswerSheet.exam_id == exam_id, AnswerSheet.student_id == None, AnswerSheet.status == "pending_mapping"))
        unmapped_sheets = r_unmap.scalar() or 0

        return {
            "active_students": active_count,
            "removed_students": removed_count,
            "mapped_sheets": mapped_sheets,
            "unmapped_sheets": unmapped_sheets,
        }


async def get_enrolled_students_for_dropdown(exam_id: str) -> List[Dict[str, Any]]:
    async with AsyncSessionLocal() as db:
        res = await db.execute(
            select(ExamStudent).where(ExamStudent.exam_id == exam_id, ExamStudent.status == "active")
        )
        enrollments = res.scalars().all()
        if not enrollments:
            return []

        student_ids = [e.student_id for e in enrollments]
        res = await db.execute(select(User).where(User.id.in_(student_ids), User.is_active == True))
        students = res.scalars().all()

        result = [
            {
                "id": str(s.id),
                "full_name": s.full_name,
                "roll_no": s.roll_no,
                "email": s.email,
            }
            for s in students
        ]

        return sorted(result, key=lambda x: x.get("roll_no", "") or "")
