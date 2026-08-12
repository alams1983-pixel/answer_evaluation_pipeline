from fastapi import APIRouter, Depends
from models.auth import UserResponse
from core.deps import get_current_user
from db.database import (
    exams_collection,
    answer_sheets_collection,
    batch_jobs_collection,
    gradings_collection,
    users_collection,
)

router = APIRouter(
    prefix="/dashboard",
    tags=["dashboard"],
)


@router.get("/stats/")
async def get_dashboard_stats(
    current_user: UserResponse = Depends(get_current_user)
):
    stats = {}

    if current_user.role in ("admin", "teacher"):
        stats["total_exams"] = await exams_collection.count_documents({})
        stats["total_students"] = await users_collection.count_documents({"role": "student"})

        pending_filter = {"status": "pending"}
        graded_filter = {"status": {"$in": ["graded", "reviewed", "published"]}}

        stats["pending_sheets"] = await answer_sheets_collection.count_documents(pending_filter)
        stats["graded_sheets"] = await answer_sheets_collection.count_documents(graded_filter)

        active_filter = {"status": {"$in": ["pending", "processing", "submitting"]}}
        stats["active_batches"] = await batch_jobs_collection.count_documents(active_filter)

        stats["total_gradings"] = await gradings_collection.count_documents({})
    else:
        student_gradings = {"student_id": current_user.id}
        stats["total_exams"] = await gradings_collection.count_documents(student_gradings)
        stats["pending_results"] = await gradings_collection.count_documents({
            **student_gradings,
            "status": {"$in": ["pending", "processing"]},
        })
        stats["published_results"] = await gradings_collection.count_documents({
            **student_gradings,
            "status": "published",
        })

    return stats
