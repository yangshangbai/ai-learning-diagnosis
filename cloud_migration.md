# 云端迁移指南

## 前置条件
- [ ] 服务器已安装 Python 3.11+、Node.js 18+、PostgreSQL 16、Redis 7

## 迁移步骤

### 1. 数据库切换 (SQLite → PostgreSQL)

**修改 backend/.env:**
```
ENVIRONMENT=production
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/dbname
```

**创建数据库表结构:**
```bash
cd backend
alembic upgrade head
```

**导入种子数据:**
```bash
python seed_data.py
```

> 注意：SQLite 和 PostgreSQL 的 DDL 语法有差异，可能需要调整 seed_data.py 中的部分语句。Alembic 迁移脚本已考虑兼容性。

### 2. 文件存储切换 (本地 → MinIO/OSS)

**修改 backend/.env:**
```
STORAGE_TYPE=minio
MINIO_ENDPOINT=play.min.io
MINIO_ACCESS_KEY=your-access-key
MINIO_SECRET_KEY=your-secret-key
MINIO_BUCKET=training-files
```

`config.py` 已预留切换逻辑，根据 `STORAGE_TYPE` 自动加载对应配置。
文件路径前缀会从本地 `uploads/` 自动切换为 MinIO 对象路径。

### 3. 任务队列切换 (内存 → Celery+Redis)

**修改 backend/.env:**
```
TASK_BACKEND=celery
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
```

**启动 Celery Worker:**
```bash
cd backend
celery -A services.tasks worker --loglevel=info
```

**AI Mock 迁移:**
- 当前 `services/ai_mock.py` 使用 `asyncio.sleep` 模拟异步任务
- 切换到 Celery 后，AI 任务变为 `.delay()` 调用，Worker 异步执行
- 前端通过轮询任务状态接口获取结果

### 4. AI服务切换 (Mock → 真实API)

**修改 backend/.env:**
```
AI_BACKEND=openai
OPENAI_API_KEY=sk-xxxxx
OPENAI_MODEL=gpt-4o-mini
```

**代码调整:**
- 将 `services/ai_mock.py` 中的 mock 逻辑替换为真实 API 调用
- 或创建 `services/ai_real.py` 实现相同的接口协议
- 保持 API 返回格式不变，前端无需修改

**Prompt 工程:**
- 试卷批改 Prompt：图片识别 + 知识点匹配 + 判题逻辑
- 诊断分析 Prompt：薄弱点分析 + 趋势预测 + 教学建议
- 练习生成 Prompt：根据薄弱点 + 难度 + 知识点自动组卷

### 5. 前端构建

```bash
cd frontend
npm run build
# 产出在 frontend/dist/
```

**Nginx 配置示例:**
```nginx
server {
    listen 80;
    server_name your-domain.com;

    # 前端静态文件
    root /path/to/frontend/dist;
    index index.html;

    # SPA 路由 fallback
    location / {
        try_files $uri $uri/ /index.html;
    }

    # API 反向代理
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### 6. 部署

**使用 Gunicorn + Uvicorn workers:**
```bash
gunicorn main:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000 \
  --access-logfile /var/log/training/access.log \
  --error-logfile /var/log/training/error.log
```

**systemd 服务配置 (`/etc/systemd/system/training.service`):**
```ini
[Unit]
Description=AI Training Diagnosis System
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/path/to/backend
Environment=PATH=/path/to/venv/bin
ExecStart=/path/to/venv/bin/gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8000
Restart=always

[Install]
WantedBy=multi-user.target
```

**启动服务:**
```bash
systemctl daemon-reload
systemctl enable training
systemctl start training
```

### 7. HTTPS 配置

```bash
# 使用 certbot 获取免费证书
certbot --nginx -d your-domain.com
```

## 安全检查清单
- [ ] 关闭 DEBUG 模式
- [ ] 修改 SECRET_KEY 为随机字符串
- [ ] 数据库密码使用强密码
- [ ] API keys 通过环境变量注入（不提交到代码仓库）
- [ ] 配置 CORS 白名单
- [ ] 启用 rate limiting
- [ ] 文件上传大小限制
- [ ] 定期备份数据库

## 监控与日志
- 访问日志: Nginx access.log
- 应用日志: Gunicorn 日志
- 错误追踪: 集成 Sentry (可选)
- 性能监控: Prometheus + Grafana (可选)
