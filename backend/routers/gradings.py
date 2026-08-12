from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
import bson

from models.auth import UserResponse
from models.gradings import GradingResponse
from core.deps import get_current_user, require_roles
from db.database import (
    exams_collection,
    classes_collection,
    gradings_collection,
    batch_jobs_collection,
    answer_sheets_collection,
    result_schemas_collection,
)
from services.grading_service import (
    update_grading as svc_update_grading,
    publish_grading as svc_publish,
)

router = APIRouter(
    prefix="/exams",
    tags=["gradings"],
)


async def _check_exam_access(exam, current_user: UserResponse) -> None:
    if current_user.role == "teacher":
        cls = await classes_collection.find_one({"_id": bson.ObjectId(exam["class_id"])})
        if not cls or current_user.id not in cls.get("teacher_ids", []):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")


def _build_grading_response(g: dict) -> GradingResponse:
    return GradingResponse(
        id=str(g["_id"]),
        sheet_id=str(g["sheet_id"]),
        exam_id=str(g["exam_id"]),
        batch_id=str(g["batch_id"]),
        student_id=str(g["student_id"]) if g.get("student_id") else None,
        result_schema_id=str(g["result_schema_id"]) if g.get("result_schema_id") else None,
        result=g.get("result", {}),
        total_awarded=g.get("total_awarded", 0),
        total_max=g.get("total_max", 0),
        status=g.get("status", "auto"),
        reviewed_by=str(g["reviewed_by"]) if g.get("reviewed_by") else None,
        reviewed_at=g.get("reviewed_at"),
        published_at=g.get("published_at"),
        override_log=g.get("override_log", []),
        created_at=g["created_at"],
    )


@router.get("/batches/{batch_id}/gradings/", response_model=List[GradingResponse])
async def list_batch_gradings(
    batch_id: str,
    current_user: UserResponse = Depends(get_current_user),
):
    batch = await batch_jobs_collection.find_one({"_id": bson.ObjectId(batch_id)})
    if not batch:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found")

    exam = await exams_collection.find_one({"_id": batch["exam_id"]})
    if not exam:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exam not found")

    await _check_exam_access(exam, current_user)

    gradings = await gradings_collection.find(
        {"batch_id": bson.ObjectId(batch_id)}
    ).sort("created_at", 1).to_list(length=None)

    return [_build_grading_response(g) for g in gradings]


@router.get("/sheets/{sheet_id}/grading/", response_model=GradingResponse)
async def get_grading_by_sheet(
    sheet_id: str,
    current_user: UserResponse = Depends(get_current_user),
):
    grading = await gradings_collection.find_one({"sheet_id": bson.ObjectId(sheet_id)})
    if not grading:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Grading not found for this sheet")

    exam = await exams_collection.find_one({"_id": grading["exam_id"]})
    if not exam:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exam not found")

    if current_user.role == "teacher":
        await _check_exam_access(exam, current_user)

    if current_user.role == "student":
        if grading.get("status") != "published":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Grading not published")

    return _build_grading_response(grading)


@router.get("/exams/{exam_id}/gradings/", response_model=List[GradingResponse])
async def list_exam_gradings(
    exam_id: str,
    status_filter: str | None = None,
    current_user: UserResponse = Depends(get_current_user),
):
    exam = await exams_collection.find_one({"_id": bson.ObjectId(exam_id)})
    if not exam:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exam not found")

    if current_user.role == "teacher":
        await _check_exam_access(exam, current_user)

    query: dict = {"exam_id": bson.ObjectId(exam_id)}
    if status_filter:
        query["status"] = status_filter

    gradings = await gradings_collection.find(query).sort("created_at", 1).to_list(length=None)
    return [_build_grading_response(g) for g in gradings]


@router.get("/gradings/{grading_id}/", response_model=GradingResponse)
async def get_grading(
    grading_id: str,
    current_user: UserResponse = Depends(get_current_user),
):
    grading = await gradings_collection.find_one({"_id": bson.ObjectId(grading_id)})
    if not grading:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Grading not found")

    exam = await exams_collection.find_one({"_id": grading["exam_id"]})
    if not exam:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exam not found")

    if current_user.role == "teacher":
        await _check_exam_access(exam, current_user)

    if current_user.role == "student":
        if grading.get("status") != "published":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Grading not published")

    return _build_grading_response(grading)


@router.patch("/gradings/{grading_id}/", response_model=GradingResponse)
async def update_grading(
    grading_id: str,
    update_data: dict,
    current_user: UserResponse = Depends(require_roles("admin", "teacher")),
):
    grading = await gradings_collection.find_one({"_id": bson.ObjectId(grading_id)})
    if not grading:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Grading not found")

    exam = await exams_collection.find_one({"_id": grading["exam_id"]})
    if not exam:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exam not found")

    if current_user.role == "teacher":
        await _check_exam_access(exam, current_user)

    if grading.get("status") == "published":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot update published gradings"
        )

    updated_grading = await svc_update_grading(grading_id, update_data, current_user.id)
    if not updated_grading:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Grading not found")

    return _build_grading_response(updated_grading)


@router.post("/gradings/{grading_id}/publish/", response_model=GradingResponse)
async def publish_grading(
    grading_id: str,
    current_user: UserResponse = Depends(require_roles("admin", "teacher")),
):
    grading = await gradings_collection.find_one({"_id": bson.ObjectId(grading_id)})
    if not grading:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Grading not found")

    exam = await exams_collection.find_one({"_id": grading["exam_id"]})
    if not exam:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exam not found")

    if current_user.role == "teacher":
        await _check_exam_access(exam, current_user)

    published_grading = await svc_publish(grading_id)
    if not published_grading:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Grading not found")

    return _build_grading_response(published_grading)


@router.post("/{exam_id}/publish-all/", response_model=dict)
async def publish_all_gradings(
    exam_id: str,
    current_user: UserResponse = Depends(require_roles("admin", "teacher")),
):
    from services.grading_service import publish_all_gradings_for_exam

    exam = await exams_collection.find_one({"_id": bson.ObjectId(exam_id)})
    if not exam:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exam not found")

    if current_user.role == "teacher":
        await _check_exam_access(exam, current_user)

    published_count = await publish_all_gradings_for_exam(exam_id)

    return {"published_count": published_count}
