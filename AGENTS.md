# 项目全局规则 — AI学习诊断系统

> 版本: v1.1.0 | 更新: 2026-07-31

---

## ⚠️ 强制规则：代码变更 = 本地 + 云端同步 + 服务重启

**每次修改程序代码，必须同步完成以下三步：**

1. **本地代码修改** — 前端/后端/数据库模型等
2. **云端代码同步** — 调用部署脚本推送到生产服务器
3. **服务重启验证** — 确保新代码生效且服务正常

### 部署脚本

| 脚本 | 用途 | 适用场景 |
|------|------|---------|
| `bash scripts/quick-sync.sh` | 仅后端代码变更 | API修改、Model变更、Service改动 |
| `bash scripts/quick-full.sh` | 前后端都变更 | 页面改动+接口改动同时发生 |
| `bash scripts/deploy.sh` | 完整部署(带选项) | 全量部署、首次部署 |
| `scripts/deploy.bat` | Windows CMD 版本 | 无法使用 Git Bash 时 |

### 部署目标

```
SSH:  ubuntu@175.178.29.97
密钥: YunServerMG.pem
目录: /opt/ai-learning/
后端: systemctl ai-learning (Gunicorn + Uvicorn, port 8001)
前端: Nginx → /opt/ai-learning/frontend/dist/
```

### 操作流程示例

```bash
# 1. 修改代码 (如: 修复 backend/api/tasks.py 的DELETE逻辑)
vim backend/api/tasks.py

# 2. 同步到云端 + 重启服务
bash scripts/quick-sync.sh

# 3. 验证
curl -s http://175.178.29.97/api/docs | head
```

---

## 技术栈速查

| 层 | 本地开发 | 云端生产 |
|---|---------|---------|
| 后端 | Uvicorn :8000 | Gunicorn+Uvicorn :8001 |
| 前端 | Vite :5173 | Nginx → dist/ |
| 数据库 | SQLite (ai_learning.db) | PostgreSQL |
| 文件 | ./backend/uploads/ | /opt/ai-learning/uploads/ |
| AI | Mock (ai_mock.py) | Mock (待接入真实API) |

---

## 项目结构速查

```
培训管理系统调研/
├── backend/                    # FastAPI 后端
│   ├── api/                    # 路由 (11个文件)
│   ├── models/                 # 数据模型
│   ├── schemas/               # Pydantic验证
│   ├── services/              # 业务逻辑
│   ├── middleware/             # JWT + RBAC
│   └── main.py                # 入口
├── frontend/                   # Vue 3 + Vite
│   └── src/
│       ├── api/                # Axios封装
│       ├── stores/             # Pinia状态
│       ├── views/teacher/      # 老师端 (8页)
│       └── views/admin/        # 管理端 (13页)
├── scripts/                    # 部署脚本
└── tests/                      # 测试用例
```

---

## 常见问题速查

| 问题 | 原因 | 修复 |
|------|------|------|
| 登录闪退 | auth store双重解包 `res.data.access_token` | `res.data \|\| res` |
| API 307→401 | FastAPI尾部斜杠重定向丢Authorization | `@router.get("")` 去掉斜杠 |
| 空白页 | `{items:[]}` 整体当数组 | `.items \|\| .data \|\| raw \|\| []` |
| 图片预览裂开 | `<img>` 无法带Auth header | 预览端点移除认证 |
| RBAC阻断 | research角色无知识库写权限 | `require_research_admin` |

---

## 角色-权限矩阵

| 角色 | 学生 | 班级 | 任务 | 知识库 | 题库 | 题源 | 诊断 | 练习 | 系统 | 日志 |
|------|------|------|------|--------|------|------|------|------|------|------|
| teacher | RW | R | RW | R | R | - | RW | RW | - | - |
| research | R | R | R | RW | RW | RW | R | R | - | - |
| admin | RW | RW | RW | RW | RW | RW | RW | RW | RW | R |
| super | RW | RW | RW | RW | RW | RW | RW | RW | RW | RW |

R=读 W=写 -=无权限
