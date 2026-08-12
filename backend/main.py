from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from db.database import (
    users_collection, password_resets_collection, classes_collection, subjects_collection,
    enrollments_collection, exams_collection, answer_keys_collection, result_schemas_collection,
    question_papers_collection, extraction_tasks_collection,
    answer_sheets_collection, sheet_pages_collection, upload_batches_collection,
    batch_jobs_collection, batch_items_collection, gradings_collection,
    exam_students_collection,
)
from core.config import settings
from routers import auth, users, classes, subjects, students, exams, sheets, files, batches, gradings, question_papers, dashboard
import os

app = FastAPI(title="AI Document Processing API")

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(classes.router)
app.include_router(subjects.router)
app.include_router(students.router)
app.include_router(exams.router)
app.include_router(question_papers.router)
app.include_router(sheets.router)
app.include_router(files.router)
app.include_router(batches.router)
app.include_router(gradings.router)
app.include_router(dashboard.router)


@app.on_event("startup")
async def startup_event():
    """Create indexes and bootstrap admin user on startup."""
    # Users collection indexes
    await users_collection.create_index("email", unique=True)
    # Drop old index if it exists (causes dup key errors for null values)
    try:
        await users_collection.drop_index("class_id_1_roll_no_1")
    except Exception:
        pass
    # Create partial unique index only for students
    await users_collection.create_index(
        [("class_id", 1), ("roll_no", 1)],
        unique=True,
        partialFilterExpression={"role": "student"}
    )

    # Password resets: TTL index on expires_at
    await password_resets_collection.create_index("expires_at", expireAfterSeconds=0)

    # Classes indexes (Phase 2)
    await classes_collection.create_index("name")
    await classes_collection.create_index("section")

    # Subjects indexes (Phase 2)
    await subjects_collection.create_index("class_id")
    await subjects_collection.create_index("name")

    # Enrollments indexes (Phase 2)
    await enrollments_collection.create_index("student_id")
    await enrollments_collection.create_index("class_id")
    await enrollments_collection.create_index([("class_id", 1), ("roll_no", 1)], unique=True, sparse=True)

    # Exams indexes (Phase 3)
    await exams_collection.create_index("class_id")
    await exams_collection.create_index("subject_id")
    await exams_collection.create_index("status")

    # Answer keys indexes (Phase 3)
    await answer_keys_collection.create_index("exam_id", unique=True)

    # Result schemas indexes (Phase 3)
    await result_schemas_collection.create_index("name")

    # Question papers indexes (Phase 4)
    await question_papers_collection.create_index("exam_id", unique=True)
    await question_papers_collection.create_index("status")

    # Extraction tasks indexes (Phase 4)
    await extraction_tasks_collection.create_index("exam_id", unique=True)
    await extraction_tasks_collection.create_index("status")
    await extraction_tasks_collection.create_index("completed_at", expireAfterSeconds=86400)

    # Answer sheets indexes (Phase 4)
    await answer_sheets_collection.create_index("exam_id")
    await answer_sheets_collection.create_index("status")
    await answer_sheets_collection.create_index("batch_upload_id")

    # Sheet pages indexes (Phase 4)
    await sheet_pages_collection.create_index("sheet_id")
    await sheet_pages_collection.create_index([("sheet_id", 1), ("page_no", 1)], unique=True)

    # Upload batches indexes (Phase 4)
    await upload_batches_collection.create_index("exam_id")
    await upload_batches_collection.create_index("status")

    # Batch jobs indexes (Phase 6)
    await batch_jobs_collection.create_index("exam_id")
    await batch_jobs_collection.create_index("status")
    await batch_jobs_collection.create_index("provider_batch_id")

    # Batch items indexes (Phase 6)
    await batch_items_collection.create_index("batch_id")
    await batch_items_collection.create_index("sheet_id")
    await batch_items_collection.create_index("custom_id")

    # Gradings indexes (Phase 7)
    await gradings_collection.create_index("sheet_id", unique=True)
    await gradings_collection.create_index("exam_id")
    await gradings_collection.create_index("batch_id")
    await gradings_collection.create_index("status")
    await gradings_collection.create_index("student_id")

    # Exam-Students indexes (Phase 12)
    await exam_students_collection.create_index([("exam_id", 1), ("student_id", 1)], unique=True)
    await exam_students_collection.create_index("exam_id")
    await exam_students_collection.create_index("student_id")
    await exam_students_collection.create_index("status")

    # Create storage directories
    storage_dirs = [
        settings.STORAGE_PATH,
        os.path.join(settings.STORAGE_PATH, "original_pdfs"),
        os.path.join(settings.STORAGE_PATH, "answer_sheets"),
        os.path.join(settings.STORAGE_PATH, "question_papers"),
        os.path.join(settings.STORAGE_PATH, "answer_keys"),
        os.path.join(settings.STORAGE_PATH, "samples"),
        os.path.join(settings.STORAGE_PATH, "batches"),
        os.path.join(settings.STORAGE_PATH, "temp_uploads"),
    ]
    for dir_path in storage_dirs:
        os.makedirs(dir_path, exist_ok=True)
    print(f"[OK] Storage directories created at: {settings.STORAGE_PATH}")

    # Bootstrap admin user if not exists
    from core.security import get_password_hash
    from datetime import datetime

    admin_email = settings.BOOTSTRAP_ADMIN_EMAIL
    admin = await users_collection.find_one({"email": admin_email})
    if not admin:
        admin_doc = {
            "email": admin_email,
            "password_hash": get_password_hash(settings.BOOTSTRAP_ADMIN_PASSWORD),
            "full_name": "System Admin",
            "role": "admin",
            "class_id": None,
            "roll_no": None,
            "is_active": True,
            "created_by": None,
            "created_at": datetime.utcnow(),
            "updated_at": None,
        }
        await users_collection.insert_one(admin_doc)
        print(f"[OK] Bootstrap admin user created: {admin_email}")
    else:
        print(f"[OK] Bootstrap admin already exists: {admin_email}")

    # Start batch poller (Phase 7)
    from workers.batch_poller import run_poller as run_batch_poller
    import asyncio
    asyncio.create_task(run_batch_poller())
    print(f"[OK] Batch poller started (interval: {settings.BATCH_POLL_INTERVAL_SEC}s)")

    # Start extraction worker (Phase 4)
    from workers.extraction_worker import run_poller as run_extraction_poller
    asyncio.create_task(run_extraction_poller())
    print("[OK] Extraction task monitor started")


@app.get("/")
async def root():
    return {"message": "AI Document Processing API - Phase 4"}
