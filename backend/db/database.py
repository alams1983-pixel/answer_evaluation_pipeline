import motor.motor_asyncio
from core.config import settings

client = motor.motor_asyncio.AsyncIOMotorClient(settings.MONGODB_URL)
db = client[settings.DATABASE_NAME]

# Auth collections (Phase 1 only)
users_collection = db.get_collection("users")
password_resets_collection = db.get_collection("password_resets")

# School collections (Phase 2)
classes_collection = db.get_collection("classes")
subjects_collection = db.get_collection("subjects")
enrollments_collection = db.get_collection("enrollments")

# Exam & Answer Sheet collections (Phase 3)
exams_collection = db.get_collection("exams")
answer_keys_collection = db.get_collection("answer_keys")
result_schemas_collection = db.get_collection("result_schemas")

# Question Paper collections (Phase 4)
question_papers_collection = db.get_collection("question_papers")
extraction_tasks_collection = db.get_collection("extraction_tasks")
question_paper_crops_collection = db.get_collection("question_paper_crops")
additional_pdfs_collection = db.get_collection("additional_pdfs")

# Answer Sheet collections (Phase 4)
answer_sheets_collection = db.get_collection("answer_sheets")
sheet_pages_collection = db.get_collection("sheet_pages")
upload_batches_collection = db.get_collection("upload_batches")

# Batch collections (Phase 6)
batch_jobs_collection = db.get_collection("batch_jobs")
batch_items_collection = db.get_collection("batch_items")

# Grading collections (Phase 7)
gradings_collection = db.get_collection("gradings")

# Exam-Student Enrollment collections (Phase 12)
exam_students_collection = db.get_collection("exam_students")
