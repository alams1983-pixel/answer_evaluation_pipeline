from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from models.auth import UserResponse
from core.deps import get_current_user
from db.database import get_db
from db.models import Exam, User, AnswerSheet, BatchJob, Grading

router = APIRouter(
    prefix="/dashboard",
    tags=["dashboard"],
)


@router.get("/stats/")
async def get_dashboard_stats(
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    stats = {}

    if current_user.role in ("admin", "teacher"):
        r_exams = await db.execute(select(func.count(Exam.id)))
        stats["total_exams"] = r_exams.scalar() or 0

        r_students = await db.execute(select(func.count(User.id)).where(User.role == "student"))
        stats["total_students"] = r_students.scalar() or 0

        r_pending = await db.execute(select(func.count(AnswerSheet.id)).where(AnswerSheet.status == "pending"))
        stats["pending_sheets"] = r_pending.scalar() or 0

        r_graded = await db.execute(select(func.count(AnswerSheet.id)).where(AnswerSheet.status.in_(["graded", "reviewed", "published"])))
        stats["graded_sheets"] = r_graded.scalar() or 0

        r_batches = await db.execute(select(func.count(BatchJob.id)).where(BatchJob.status.in_(["pending", "processing", "submitting", "submitted", "in_progress"])))
        stats["active_batches"] = r_batches.scalar() or 0

        r_gradings = await db.execute(select(func.count(Grading.id)))
        stats["total_gradings"] = r_gradings.scalar() or 0
    else:
        r_exams = await db.execute(select(func.count(Grading.id)).where(Grading.student_id == current_user.id))
        stats["total_exams"] = r_exams.scalar() or 0

        r_pending_res = await db.execute(select(func.count(Grading.id)).where(Grading.student_id == current_user.id, Grading.status.in_(["pending", "processing"])))
        stats["pending_results"] = r_pending_res.scalar() or 0

        r_pub_res = await db.execute(select(func.count(Grading.id)).where(Grading.student_id == current_user.id, Grading.status == "published"))
        stats["published_results"] = r_pub_res.scalar() or 0

    return stats
