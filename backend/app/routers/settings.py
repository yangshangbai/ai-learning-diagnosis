"""系统设置接口：AI 模型配置（数据库持久化）。

端点（均限 admin）：
  GET  /api/v1/settings/ai        读取 AI 配置（api_key 只返回掩码）
  POST /api/v1/settings/ai        保存 AI 配置（api_key 留空 = 保留原值）
  POST /api/v1/settings/ai/test   真实调用模型做连通性测试
"""
import json
import time
import urllib.request

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..core.app_settings import (
    AI_REASON_KEY,
    AI_VISION_KEY,
    ai_config_public,
    get_setting,
    set_setting,
)
from ..core.db import SessionLocal
from ..core.errors import ValidationError
from ..core.security import Principal, require_admin

router = APIRouter(prefix="/api/v1/settings", tags=["settings"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class AiPartBody(BaseModel):
    provider: str = "zhipu"
    model: str = ""
    api_key: str = ""


class AiConfigBody(BaseModel):
    vision: AiPartBody
    reason: AiPartBody


class AiTestBody(BaseModel):
    kind: str = "vision"          # vision / reason
    provider: str = "zhipu"
    model: str = ""
    api_key: str = ""             # 留空 = 用服务端已保存配置


_PROVIDER_URLS = {
    "zhipu": "https://open.bigmodel.cn/api/paas/v4/chat/completions",
    "deepseek": "https://api.deepseek.com/chat/completions",
    "qwen": "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
    "openai": "https://api.openai.com/v1/chat/completions",
    "moonshot": "https://api.moonshot.cn/v1/chat/completions",
}


@router.get("/ai")
def get_ai_settings(principal: Principal = Depends(require_admin), db: Session = Depends(get_db)):
    return {"code": 0, "message": "ok", "data": ai_config_public(db)}


@router.post("/ai")
def save_ai_settings(body: AiConfigBody, principal: Principal = Depends(require_admin), db: Session = Depends(get_db)):
    """保存 AI 配置。api_key 传空 = 保留数据库原值；传新值 = 覆盖。"""
    for key, part in ((AI_VISION_KEY, body.vision), (AI_REASON_KEY, body.reason)):
        old = dict(get_setting(db, key, {}) or {})
        new = dict(old)
        new["provider"] = (part.provider or "zhipu").strip()
        new["model"] = (part.model or "").strip()
        new_key = (part.api_key or "").strip()
        # 掩码回显值（含 ****）不落库，视为"未修改"
        if new_key and "****" not in new_key:
            new["api_key"] = new_key
        elif not new_key and not old:
            new["api_key"] = ""
        set_setting(db, key, new)
    db.commit()
    return {"code": 0, "message": "saved", "data": ai_config_public(db)}


@router.post("/ai/test")
def test_ai_settings(body: AiTestBody, principal: Principal = Depends(require_admin), db: Session = Depends(get_db)):
    """真实调用一次模型（最小 prompt），验证 provider/model/key 可用。"""
    if body.api_key.strip():
        api_key = body.api_key.strip()
        source = "request"
    else:
        saved = get_setting(db, AI_VISION_KEY if body.kind == "vision" else AI_REASON_KEY, {}) or {}
        api_key = (saved.get("api_key") or "").strip()
        source = "db"
        if not api_key:
            from ..core.config import settings as app_settings
            api_key = (app_settings.ai_zhipu_api_key or "").strip()
            source = "env"
    if not api_key:
        raise ValidationError("未配置 API Key（请先在下方保存，或填写 Key 后测试）")

    url = _PROVIDER_URLS.get((body.provider or "").lower())
    if not url:
        raise ValidationError(f"不支持的 provider：{body.provider}")
    model = (body.model or "").strip() or ("glm-4v" if body.kind == "vision" else "glm-4-flash")

    payload = {
        "model": model,
        "messages": [{"role": "user", "content": "你好，请只回复两个字：正常"}],
        "max_tokens": 16,
    }
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
    )
    start = time.time()
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        raise ValidationError(f"连接失败（{type(e).__name__}）：{str(e)[:200]}")
    latency_ms = int((time.time() - start) * 1000)
    content = ""
    if data.get("choices"):
        content = (data["choices"][0].get("message") or {}).get("content") or ""
    if not data.get("choices"):
        raise ValidationError("模型返回异常：" + json.dumps(data, ensure_ascii=False)[:200])
    return {
        "code": 0, "message": "ok",
        "data": {"ok": True, "model": model, "provider": body.provider,
                 "source": source, "latency_ms": latency_ms,
                 "reply": content.strip()[:50]},
    }
