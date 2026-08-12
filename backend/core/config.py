from pydantic_settings import BaseSettings
import os

class Settings(BaseSettings):
    MONGODB_URL: str = "mongodb://localhost:27017"
    DATABASE_NAME: str = "ai_document_db"
    GEMINI_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    STORAGE_PATH: str = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "storage"))

    # JWT settings
    JWT_SECRET_KEY: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 1440  # 24 hours

    # Bootstrap admin
    BOOTSTRAP_ADMIN_EMAIL: str = "admin@school.edu"
    BOOTSTRAP_ADMIN_PASSWORD: str = "admin123"

    # CORS
    FRONTEND_URL: str = "http://localhost:3000"

    # Batch processing
    BATCH_PROVIDER_DEFAULT: str = "gemini"
    BATCH_POLL_INTERVAL_SEC: int = 300
    GEMINI_BATCH_MODEL: str = "gemini-2.5-flash"
    OPENAI_BATCH_MODEL: str = "gpt-4.1-mini"

    # Complexity tier model mapping
    GEMINI_EXTRACTION_MODEL: str = "gemini-2.5-flash"
    GEMINI_SIMPLE_MODEL: str = "gemini-2.5-flash"
    GEMINI_STANDARD_MODEL: str = "gemini-2.5-flash"
    GEMINI_COMPLEX_MODEL: str = "gemini-2.5-pro"

    # Extraction task timeout (seconds)
    EXTRACTOR_TASK_TIMEOUT_SEC: int = 3600

    class Config:
        env_file = ".env"

settings = Settings()

COMPLEXITY_MODEL_MAP = {
    "simple": settings.GEMINI_SIMPLE_MODEL,
    "standard": settings.GEMINI_STANDARD_MODEL,
    "complex": settings.GEMINI_COMPLEX_MODEL,
}

COMPLEXITY_EXTRACTION_MODEL = settings.GEMINI_EXTRACTION_MODEL
