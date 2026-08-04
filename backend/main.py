"""
FastAPI application entry point for the AI Learning Diagnosis System.

Creates the database tables on startup, seeds data if empty,
configures CORS middleware, and includes API routers.
"""

import os
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from config import settings
from database import init_db, engine

# ---------------------------------------------------------------------------
# Version — 从 VERSION 文件读取，用于自动修复时增量更新
# ---------------------------------------------------------------------------
_VERSION_FILE = Path(__file__).resolve().parent.parent / "VERSION"


def _read_version() -> str:
    try:
        return _VERSION_FILE.read_text().strip()
    except Exception:
        return "1.0.0"


APP_VERSION = _read_version()


# ---------------------------------------------------------------------------
# Application lifespan (startup / shutdown)
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: create tables and seed data
    await init_db()

    # Seed data if database is empty
    from seed_data import seed_all
    await seed_all()

    yield

    # Shutdown: dispose the engine
    await engine.dispose()


# ---------------------------------------------------------------------------
# FastAPI app instance
# ---------------------------------------------------------------------------
app = FastAPI(
    title="AI学习诊断系统",
    version=APP_VERSION,
    description="面向培训机构的AI学习诊断与个性化练习系统",
    lifespan=lifespan,
)


# ---------------------------------------------------------------------------
# CORS middleware
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------
@app.get("/api/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok", "version": APP_VERSION}


# ---------------------------------------------------------------------------
# Import and include API routers (added in Wave 2)
# ---------------------------------------------------------------------------
# Each router import is wrapped in try/except so the app can start
# even before all API modules are implemented.

try:
    from api.auth import router as auth_router
    app.include_router(auth_router, prefix="/api/auth", tags=["认证"])
except ImportError:
    pass

try:
    from api.users import router as users_router
    app.include_router(users_router, prefix="/api/users", tags=["用户"])
except ImportError:
    pass

try:
    from api.classes import router as classes_router
    app.include_router(classes_router, prefix="/api/classes", tags=["班级"])
except ImportError:
    pass

try:
    from api.students import router as students_router
    app.include_router(students_router, prefix="/api/students", tags=["学生"])
except ImportError:
    pass

try:
    from api.tasks import router as tasks_router
    app.include_router(tasks_router, prefix="/api/tasks", tags=["任务"])
except ImportError:
    pass

try:
    from api.knowledge import router as knowledge_router
    app.include_router(knowledge_router, prefix="/api/knowledge", tags=["知识点"])
except ImportError:
    pass

try:
    from api.questions import router as questions_router
    app.include_router(questions_router, prefix="/api/questions", tags=["题目"])
except ImportError:
    pass

try:
    from api.diagnosis import router as diagnosis_router
    app.include_router(diagnosis_router, prefix="/api/diagnosis", tags=["诊断"])
except ImportError:
    pass

try:
    from api.exercises import router as exercises_router
    app.include_router(exercises_router, prefix="/api/exercises", tags=["练习"])
except ImportError:
    pass

try:
    from api.audit import router as audit_router
    app.include_router(audit_router, prefix="/api/audit", tags=["审计"])
except ImportError:
    pass

try:
    from api.sources import router as sources_router
    app.include_router(sources_router, prefix="/api/sources", tags=["题源"])
except ImportError:
    pass

try:
    from api.admin import router as admin_router
    app.include_router(admin_router, prefix="/api/admin", tags=["管理"])
except ImportError:
    pass

try:
    from api.ai import router as ai_router
    app.include_router(ai_router, prefix="/api/ai", tags=["AI助手"])
except ImportError:
    pass

try:
    from api.upload import router as upload_router
    app.include_router(upload_router, prefix="/api", tags=["文件上传"])
except ImportError:
    pass

try:
    from api.logs import router as logs_router
    app.include_router(logs_router, prefix="/api/logs", tags=["错误日志"])
except ImportError:
    pass

try:
    from api.feedback import router as feedback_router
    app.include_router(feedback_router, prefix="/api/feedback", tags=["意见反馈"])
except ImportError:
    pass


# ---------------------------------------------------------------------------
# Error logging middleware — captures all unhandled exceptions
import traceback as tb_module
from models.error_log import ErrorLog
from models.chat_history import ChatHistory
from database import async_session_factory


@app.middleware("http")
async def error_logging_middleware(request: Request, call_next):
    try:
        response = await call_next(request)
        # Log HTTP errors (4xx, 5xx) even if they were handled
        if response.status_code >= 400:
            try:
                async with async_session_factory() as db:
                    log = ErrorLog(
                        timestamp=datetime.utcnow(),
                        endpoint=str(request.url.path),
                        method=request.method,
                        error_type=f"HTTP {response.status_code}",
                        error_message=f"HTTP {response.status_code} on {request.method} {request.url.path}",
                        status_code=response.status_code,
                        source="backend",
                        repair=False,
                    )
                    db.add(log)
                    await db.commit()
            except Exception:
                pass
        return response
    except Exception as exc:
        try:
            async with async_session_factory() as db:
                log = ErrorLog(
                    timestamp=datetime.utcnow(),
                    endpoint=str(request.url.path),
                    method=request.method,
                    error_type=type(exc).__name__,
                    error_message=str(exc)[:1000],
                    status_code=getattr(exc, "status_code", 500),
                    stack_trace=tb_module.format_exc()[:3000],
                    source="backend",
                    repair=False,
                )
                db.add(log)
                await db.commit()
        except Exception:
            pass

        return JSONResponse(
            status_code=getattr(exc, "status_code", 500),
            content={"detail": str(exc)[:200]},
        )


# ---------------------------------------------------------------------------
# Direct run (development)
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
