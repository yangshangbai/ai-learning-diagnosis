"""系统运行时设置（数据库版）。

设计：
- 数据库 system_settings 表是唯一事实来源；env（AI_ZHIPU_API_KEY）仅作为 key 未配置时的回退。
- AI 配置分两路：
    ai_vision_config  = {provider, model, api_key}   视觉识别（答题卡 OCR / 图片导入）
    ai_reason_config  = {provider, model, api_key}   文本推理（AI 选题拆解/选题）
- api_key 属敏感信息：GET 返回时只给掩码，写入时空值表示"保留原值"。
"""
from typing import Any, Optional

from sqlalchemy.orm import Session

from ..models import SystemSetting
from .config import settings

AI_VISION_KEY = "ai_vision_config"
AI_REASON_KEY = "ai_reason_config"


def get_setting(db: Session, key: str, default: Optional[Any] = None) -> Any:
    row = db.query(SystemSetting).filter(SystemSetting.skey == key).first()
    return row.svalue if row and row.svalue is not None else default


def set_setting(db: Session, key: str, value: Any) -> None:
    """幂等 upsert。调用方负责 commit。"""
    row = db.query(SystemSetting).filter(SystemSetting.skey == key).first()
    if row:
        row.svalue = value
    else:
        db.add(SystemSetting(skey=key, svalue=value))


def mask_key(key: str) -> str:
    """掩码显示：保留前4后4，中间 ****。过短则全掩码。"""
    k = (key or "").strip()
    if not k:
        return ""
    if len(k) <= 10:
        return "****"
    return k[:4] + "****" + k[-4:]


def get_ai_config(db: Session) -> dict:
    """读取 AI 配置（DB 优先，env 回退 api_key）。

    返回 {"vision": {provider, model, api_key}, "reason": {...}}；
    api_key 已解析（DB 为空时回退 env AI_ZHIPU_API_KEY），供服务端调用使用——不要原样返回给前端。
    """
    vision = dict(get_setting(db, AI_VISION_KEY, {}) or {})
    reason = dict(get_setting(db, AI_REASON_KEY, {}) or {})
    env_key = (settings.ai_zhipu_api_key or "").strip()
    for cfg in (vision, reason):
        if not (cfg.get("api_key") or "").strip() and env_key:
            cfg["api_key"] = env_key
    return {"vision": vision, "reason": reason}


def ai_config_public(db: Session) -> dict:
    """对外（前端）展示版：api_key 只返回掩码与是否已配置。"""
    env_key = (settings.ai_zhipu_api_key or "").strip()
    out = {}
    for name, key in (("vision", AI_VISION_KEY), ("reason", AI_REASON_KEY)):
        c = dict(get_setting(db, key, {}) or {})
        db_key = (c.get("api_key") or "").strip()
        k = db_key or env_key
        out[name] = {
            "provider": c.get("provider") or "zhipu",
            "model": c.get("model") or "",
            "api_key_masked": mask_key(k),
            "api_key_set": bool(k),
            "source": ("db" if db_key else "env") if k else "none",
        }
    return out
