"""一次性/可重复执行：把智谱 GLM 的 API Key 写入数据库 system_settings 表。

用法（backend/ 目录下）：
    python set_ai_settings.py                 # 使用下方默认 Key
    python set_ai_settings.py <api_key>       # 命令行传入 Key

写入键：
    ai_vision_config = {provider: zhipu, model: glm-4v,     api_key: ...}
    ai_reason_config = {provider: zhipu, model: glm-4-flash, api_key: ...}
幂等：重复执行只覆盖这两个键，不影响其它设置。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.app_settings import AI_REASON_KEY, AI_VISION_KEY, set_setting  # noqa: E402
from app.core.db import SessionLocal  # noqa: E402
from app import models  # noqa: E402

API_KEY = os.environ.get("ZHIPU_API_KEY") or (
    sys.argv[1] if len(sys.argv) > 1 else
    "1d408737aa344760a2b194b36e7ed725.ROhKgrTF6eFmLXhE"
)


def main():
    db = SessionLocal()
    try:
        set_setting(db, AI_VISION_KEY, {"provider": "zhipu", "model": "glm-4v", "api_key": API_KEY})
        set_setting(db, AI_REASON_KEY, {"provider": "zhipu", "model": "glm-4-flash", "api_key": API_KEY})
        db.commit()
        rows = (
            db.query(models.SystemSetting)
            .filter(models.SystemSetting.skey.in_([AI_VISION_KEY, AI_REASON_KEY]))
            .all()
        )
        for row in rows:
            v = row.svalue or {}
            masked = (v.get("api_key") or "")
            masked = masked[:4] + "****" + masked[-4:] if len(masked) > 10 else "****"
            print(f"[OK] {row.skey}: provider={v.get('provider')} model={v.get('model')} key={masked}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
