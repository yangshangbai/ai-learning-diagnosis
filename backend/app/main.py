"""FastAPI 应用入口：中间件顺序、全局异常、路由装配、生命周期。

中间件顺序（参考 fullstack 规范）：
  RequestID → Logging → CORS → Auth(依赖内) → Validation → Handler → ErrorHandler

全局异常：
  - AppError → 结构化返回（业务可预期）
  - 未捕获 Exception → 记日志 + 落 system_logs(backend/ERROR) + 返回通用 500
"""
import traceback
import uuid
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .core import logging as app_logging
from .core.config import settings
from .core.db import Base, SessionLocal, engine
from .core.errors import AppError
from . import models
from .routers import auth_router, health_router, system_log_router
from .routers.basic import router as basic_router
from .routers.teacher import router as teacher_router
from .routers.class_router import router as class_router
from .routers.student import router as student_router
from .routers.question import router as question_router
from .routers.paper import router as paper_router
from .routers.exam import router as exam_router
from .routers.meta import router as meta_router
from .routers.user import router as user_router
from .routers.import_log import router as import_log_router
from .routers.import_export import router as import_export_router
from .routers.draft import router as draft_router
from .routers.ai import router as ai_router
from .routers.ai_select import router as ai_select_router
from .routers.tag import router as tag_router
from .routers.backup import router as backup_router
from .routers.settings import router as settings_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 所有环境：幂等迁移（建缺失表 tags / ALTER 补 questions.tags 列 / 默认标签）
    from .seed import ensure_schema_migrations

    ensure_schema_migrations()
    if settings.app_env in ("dev", "test"):
        Base.metadata.create_all(bind=engine)
        from .seed import seed_admin, seed_basic_data

        seed_admin()
        seed_basic_data()
    yield


app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    rid = request.headers.get("X-Request-Id") or uuid.uuid4().hex[:16]
    token = app_logging.request_id_var.set(rid)
    request.state.request_id = rid
    try:
        response = await call_next(request)
    finally:
        app_logging.request_id_var.reset(token)
    response.headers["X-Request-Id"] = rid
    return response


@app.exception_handler(AppError)
async def handle_app_error(request: Request, exc: AppError):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "code": exc.status_code,
            "message": exc.message,
            "data": exc.details,
            "request_id": getattr(request.state, "request_id", None),
        },
    )


@app.exception_handler(Exception)
async def handle_unexpected(request: Request, exc: Exception):
    rid = getattr(request.state, "request_id", None)
    app_logging.logger.error(
        "unexpected_error",
        extra={"path": str(request.url), "err": str(exc), "trace": traceback.format_exc()},
    )
    # 自动落库：后端未捕获错误 → system_logs（带 repaired 标记默认 false）
    try:
        db = SessionLocal()
        db.add(
            models.SystemLog(
                level="ERROR",
                source="backend",
                module="global",
                message=str(exc)[:4000],
                traceback=traceback.format_exc(),
                url=str(request.url),
                request_id=rid,
            )
        )
        db.commit()
        db.close()
    except Exception:
        pass
    return JSONResponse(
        status_code=500,
        content={"code": 500, "message": "服务器内部错误", "data": None, "request_id": rid},
    )


app.include_router(health_router)
app.include_router(auth_router)
app.include_router(system_log_router)
app.include_router(basic_router)
app.include_router(teacher_router)
app.include_router(class_router)
app.include_router(student_router)
# import/export 须在 question 之前注册，避免 /questions/export-template 被 /questions/{qid} 抢先匹配
app.include_router(import_export_router)
app.include_router(question_router)
app.include_router(paper_router)
app.include_router(exam_router)
app.include_router(meta_router)
app.include_router(user_router)
app.include_router(import_log_router)
app.include_router(draft_router)
app.include_router(ai_router)
app.include_router(ai_select_router)
app.include_router(tag_router)
app.include_router(backup_router)
app.include_router(settings_router)


# 仅非生产环境存在：用于自测「后端未捕获异常 → 全局 handler 自动落库」
if settings.app_env != "prod":

    @app.get("/api/v1/_dev_raise")
    def _dev_raise():
        raise RuntimeError("dev forced error for self-test")


if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=False)
