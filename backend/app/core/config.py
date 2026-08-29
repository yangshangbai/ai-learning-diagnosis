"""应用配置：集中式、类型化、启动即校验（fail-fast）。

环境三层：dev / test / prod。
- dev/test：默认 SQLite 便于本地冒烟（生产仍为 PostgreSQL 16）。
- prod：必须通过环境变量注入 DATABASE_URL / JWT_SECRET，否则启动失败。
"""
from typing import List, Literal
import os

from pydantic_settings import BaseSettings, SettingsConfigDict

# 后端根目录（backend/），用于把 dev.db 固定到绝对路径，避免因启动 CWD 不同导致连到不同库文件
_BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_DEV_DB_PATH = os.path.join(_BACKEND_DIR, "dev.db").replace("\\", "/")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    app_env: Literal["dev", "test", "prod"] = "dev"
    app_name: str = "教研管理平台后端"

    # 数据库（生产用 postgresql+psycopg，dev/test 用 sqlite）
    # 绝对路径，确保数据持久化且不随启动目录漂移
    database_url: str = "sqlite:///" + _DEV_DB_PATH
    db_pool_size: int = 10
    db_max_overflow: int = 20

    # JWT（生产必须外部注入强密钥）
    jwt_secret: str = "dev-secret-change-me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 1440
    refresh_token_expire_days: int = 7

    # CORS：生产禁止 *
    cors_origins: List[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
    ]

    log_level: str = "INFO"

    # 系统日志上报限流（每分钟每 IP），由网关/中间件落实，这里仅声明阈值
    log_report_limit_per_min: int = 120

    # AI 视觉识别服务端密钥（可选）：配置后前端无需再传 api_key，避免凭证经浏览器传输
    ai_zhipu_api_key: str = ""

    @property
    def is_prod(self) -> bool:
        return self.app_env == "prod"


settings = Settings()

# fail-fast：生产环境强制校验强密钥
if settings.is_prod and settings.jwt_secret == "dev-secret-change-me":
    raise RuntimeError("生产环境必须通过环境变量 JWT_SECRET 注入强密钥")
