"""Application configuration using pydantic-settings."""

import os
from typing import List


class Settings:
    """Application settings loaded from environment variables with sensible defaults."""

    ENV: str = os.getenv("ENVIRONMENT", "development")
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "sqlite+aiosqlite:///./ai_learning.db",
    )
    SECRET_KEY: str = os.getenv("SECRET_KEY", "dev-secret-key-change-in-production")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(
        os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "480")
    )
    UPLOAD_DIR: str = os.getenv("UPLOAD_DIR", "./uploads")
    STORAGE_TYPE: str = os.getenv("STORAGE_TYPE", "local")  # local / minio / oss
    AI_BACKEND: str = os.getenv("AI_BACKEND", "mock")  # mock / openai / paddle
    TASK_BACKEND: str = os.getenv("TASK_BACKEND", "memory")  # memory / celery
    CORS_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://localhost:8080",
    ]

    def get_database_url(self) -> str:
        """Return the effective database URL."""
        if self.ENV == "production":
            return os.getenv(
                "DATABASE_URL",
                "postgresql+asyncpg://postgres:postgres@localhost:5432/ai_learning",
            )
        return self.DATABASE_URL


# Singleton settings instance
settings = Settings()

# Ensure upload directory exists
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
