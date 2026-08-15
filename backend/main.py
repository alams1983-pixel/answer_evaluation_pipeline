from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from core.config import settings
from db.database import init_db, AsyncSessionLocal
from db.models import User
from sqlalchemy import select
from routers import auth, users, classes, subjects, students, exams, sheets, files, batches, gradings, question_papers, dashboard
import os
import asyncio

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
    """Initialize MySQL tables and bootstrap admin user on startup."""
    try:
        await init_db()
        print("[OK] MySQL Database schemas initialized.")
    except Exception as e:
        print(f"[WARN] MySQL database init warning: {e}")

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

    # Bootstrap admin user
    try:
        from core.security import get_password_hash
        from datetime import datetime

        admin_email = settings.BOOTSTRAP_ADMIN_EMAIL
        admin_password_hash = get_password_hash(settings.BOOTSTRAP_ADMIN_PASSWORD)

        async with AsyncSessionLocal() as db:
            result = await db.execute(select(User).where(User.email == admin_email))
            admin = result.scalar_one_or_none()

            if not admin:
                new_admin = User(
                    email=admin_email,
                    password_hash=admin_password_hash,
                    full_name="System Admin",
                    role="admin",
                    class_id=None,
                    roll_no=None,
                    is_active=True,
                    created_by=None,
                    created_at=datetime.utcnow(),
                    updated_at=None,
                )
                db.add(new_admin)
                await db.commit()
                print(f"[OK] Bootstrap admin user created: {admin_email}")
            else:
                admin.password_hash = admin_password_hash
                await db.commit()
                print(f"[OK] Bootstrap admin already exists (password updated): {admin_email}")
    except Exception as e:
        print(f"[WARN] Bootstrap admin creation error: {e}")

    # Start background workers
    try:
        from workers.batch_poller import run_poller as run_batch_poller
        asyncio.create_task(run_batch_poller())
        print(f"[OK] Batch poller started (interval: {settings.BATCH_POLL_INTERVAL_SEC}s)")
    except Exception as e:
        print(f"[WARN] Batch poller start error: {e}")

    try:
        from workers.extraction_worker import run_poller as run_extraction_poller
        asyncio.create_task(run_extraction_poller())
        print("[OK] Extraction task monitor started")
    except Exception as e:
        print(f"[WARN] Extraction monitor start error: {e}")


@app.get("/")
async def root():
    return {"message": "AI Document Processing API - MySQL Engine"}
