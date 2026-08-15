from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional

from models.auth import UserResponse
from models.gradings import GradingResponse
from core.deps import get_current_user, require_roles
from db.database import get_db
from db.models import Grading, Exam, BatchJob, AnswerSheet, Class
from services.grading_service import (
    update_grading as svc_update_grading,
    publish_grading as svc_publish,
    publish_all_gradings_for_exam,
)

router = APIRouter(
    prefix="/exams",
    tags=["gradings"],
)


def _build_grading_response(g: dict) -> GradingResponse:
    return GradingResponse(
        id=str(g["id"]),
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
    db: AsyncSession = Depends(get_db)
):
    res = await db.execute(
        select(Grading).where(Grading.batch_id == batch_id).order_by(Grading.created_at.asc())
    )
    gradings = res.scalars().all()

    return [
        GradingResponse(
            id=str(g.id),
            sheet_id=str(g.sheet_id),
            exam_id=str(g.exam_id),
            batch_id=str(g.batch_id),
            student_id=str(g.student_id) if g.student_id else None,
            result_schema_id=str(g.result_schema_id) if g.result_schema_id else None,
            result=g.result or {},
            total_awarded=g.total_awarded or 0,
            total_max=g.total_max or 0,
            status=g.status or "auto",
            reviewed_by=str(g.reviewed_by) if g.reviewed_by else None,
            reviewed_at=g.reviewed_at,
            published_at=g.published_at,
            override_log=g.override_log or [],
            created_at=g.created_at,
        )
        for g in gradings
    ]


@router.get("/sheets/{sheet_id}/grading/", response_model=GradingResponse)
async def get_grading_by_sheet(
    sheet_id: str,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    res = await db.execute(select(Grading).where(Grading.sheet_id == sheet_id))
    g = res.scalar_one_or_none()
    if not g:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Grading not found for this sheet")

    if current_user.role == "student" and g.status != "published":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Grading not published")

    return GradingResponse(
        id=str(g.id),
        sheet_id=str(g.sheet_id),
        exam_id=str(g.exam_id),
        batch_id=str(g.batch_id),
        student_id=str(g.student_id) if g.student_id else None,
        result_schema_id=str(g.result_schema_id) if g.result_schema_id else None,
        result=g.result or {},
        total_awarded=g.total_awarded or 0,
        total_max=g.total_max or 0,
        status=g.status or "auto",
        reviewed_by=str(g.reviewed_by) if g.reviewed_by else None,
        reviewed_at=g.reviewed_at,
        published_at=g.published_at,
        override_log=g.override_log or [],
        created_at=g.created_at,
    )


@router.get("/{exam_id}/gradings/", response_model=List[GradingResponse])
async def list_exam_gradings(
    exam_id: str,
    status_filter: Optional[str] = None,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    query = select(Grading).where(Grading.exam_id == exam_id)
    if status_filter:
        query = query.where(Grading.status == status_filter)

    res = await db.execute(query.order_by(Grading.created_at.asc()))
    gradings = res.scalars().all()

    return [
        GradingResponse(
            id=str(g.id),
            sheet_id=str(g.sheet_id),
            exam_id=str(g.exam_id),
            batch_id=str(g.batch_id),
            student_id=str(g.student_id) if g.student_id else None,
            result_schema_id=str(g.result_schema_id) if g.result_schema_id else None,
            result=g.result or {},
            total_awarded=g.total_awarded or 0,
            total_max=g.total_max or 0,
            status=g.status or "auto",
            reviewed_by=str(g.reviewed_by) if g.reviewed_by else None,
            reviewed_at=g.reviewed_at,
            published_at=g.published_at,
            override_log=g.override_log or [],
            created_at=g.created_at,
        )
        for g in gradings
    ]


@router.get("/gradings/{grading_id}/", response_model=GradingResponse)
async def get_grading(
    grading_id: str,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    res = await db.execute(select(Grading).where(Grading.id == grading_id))
    g = res.scalar_one_or_none()
    if not g:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Grading not found")

    if current_user.role == "student" and g.status != "published":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Grading not published")

    return GradingResponse(
        id=str(g.id),
        sheet_id=str(g.sheet_id),
        exam_id=str(g.exam_id),
        batch_id=str(g.batch_id),
        student_id=str(g.student_id) if g.student_id else None,
        result_schema_id=str(g.result_schema_id) if g.result_schema_id else None,
        result=g.result or {},
        total_awarded=g.total_awarded or 0,
        total_max=g.total_max or 0,
        status=g.status or "auto",
        reviewed_by=str(g.reviewed_by) if g.reviewed_by else None,
        reviewed_at=g.reviewed_at,
        published_at=g.published_at,
        override_log=g.override_log or [],
        created_at=g.created_at,
    )


@router.patch("/gradings/{grading_id}/", response_model=GradingResponse)
async def update_grading(
    grading_id: str,
    update_data: dict,
    current_user: UserResponse = Depends(require_roles("admin", "teacher")),
    db: AsyncSession = Depends(get_db)
):
    res = await db.execute(select(Grading).where(Grading.id == grading_id))
    g = res.scalar_one_or_none()
    if not g:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Grading not found")

    if g.status == "published":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot update published gradings")

    updated_grading = await svc_update_grading(grading_id, update_data, current_user.id)
    if not updated_grading:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Grading not found")

    return _build_grading_response(updated_grading)


@router.post("/gradings/{grading_id}/publish/", response_model=GradingResponse)
async def publish_grading(
    grading_id: str,
    current_user: UserResponse = Depends(require_roles("admin", "teacher")),
    db: AsyncSession = Depends(get_db)
):
    published_grading = await svc_publish(grading_id)
    if not published_grading:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Grading not found")

    return _build_grading_response(published_grading)


@router.post("/{exam_id}/publish-all/", response_model=dict)
async def publish_all_gradings(
    exam_id: str,
    current_user: UserResponse = Depends(require_roles("admin", "teacher")),
    db: AsyncSession = Depends(get_db)
):
    published_count = await publish_all_gradings_for_exam(exam_id)
    return {"published_count": published_count}
