# 项目全局规则 — 教研管理平台(AI学习诊断系统)v2

> 版本: v2.0.0 | 更新: 2026-08-29 | 架构基线: git `main` @ `ff622a7`(Workbuddy 重设计版)
> 逆向分析全套文档: **[docs/reverse/](docs/reverse/README.md)** ← 接手项目先读这个

---

## ⚠️ 强制规则 1:代码变更 = 本地修改 + 云端部署 + 重启验证

**每次修改程序代码,必须同步完成三步:**

1. **本地代码修改** — 后端 `backend/app/`、前端 `frontend/demo/`、模型等
2. **云端代码同步** — 部署脚本推送到生产服务器(tar+ssh)
3. **服务重启验证** — `systemctl is-active ai-learning` + curl 探活

### 部署脚本(已验证兼容 backend/app 新架构)

| 脚本 | 用途 | 适用场景 |
|------|------|---------|
| `bash scripts/quick-sync.sh` | 仅后端代码变更 | API/Model/Service 改动 |
| `bash scripts/quick-full.sh` | 前后端都变更(服务器端 npm build) | 页面+接口同时改动 |
| `bash scripts/deploy.sh` | 完整部署(带 --sync-only 等选项) | 全量、首次部署 |

### 部署目标(项目记忆·云端访问信息)

```
SSH:  ubuntu@175.178.29.97        密钥: YunServerMG.pem(项目根,已 gitignore)
目录: /opt/ai-learning/           服务: systemctl ai-learning (active)
后端: Gunicorn+Uvicorn 127.0.0.1:8001,入口 backend/app/main.py
网关: Nginx 80/443 → /api 反代 8001(带 /v1 映射),静态+SPA兜底
数据库: PostgreSQL 16 ai_training@127.0.0.1:5432(生产) | SQLite backend/dev.db(开发)
凭证: backend/.env(DATABASE_URL/JWT,已 gitignore,不得入库入档)
```

## ⚠️ 强制规则 2:用户测试通过 = 自动同步 Git

**每轮程序修改 → 用户在云端测试通过后,必须立即自动执行:**

```bash
git add -A && git commit -m "feat/fix: vX.Y.Z — 变更摘要" && git push origin main
```

- 分支只有 `main`(GitHub: yangshangbai/ai-learning-diagnosis);直接推 main,快进合并
- ⚠️ 本机到 github.com 的 443 有间歇性阻断:推送失败时用 `curl -s -m 5 https://github.com` 探测,窗口打开立即重试(实测几十秒~几分钟内恢复;api.github.com 通常可达,可先经 API 验证 token)
- 服务器 `/opt/ai-learning` 也是同一 origin 的 git 仓库,可作为中转
- 敏感文件永不入库: *.pem、backend/.env、jiaoyanyun_token.json、jiaoyanyun_credentials.json、uploads/、backend/uploads/、*.db(已入 .gitignore)

---

## 技术栈速查(v2 现状)

| 层 | 本地开发 | 云端生产 |
|---|---------|---------|
| 后端 | Uvicorn :8000(CWD=backend) | Gunicorn+Uvicorn :8001 |
| 前端(生产真身) | `frontend/demo/index.html` 原生JS单文件SPA,API 直连 127.0.0.1:8000 | Nginx 兜底 + `/api/v1` 反代 |
| 前端(遗留) | `frontend/src` Vue3 SPA — **未接新后端,仅参考** | 同左,未部署价值 |
| 数据库 | SQLite `backend/dev.db` | PostgreSQL 16 |
| AI | 视觉=智谱GLM-4V,文本=deepseek 等(**api_key 前端传入**);考试AI评分为满分桩 | 同左 |
| 教研云 | jiaoyanyun/ 三件套(CDP :9222 + 同步爬虫 + 代理 :8787),独立进程 | 同机运行 |

## 项目结构速查(v2 新架构)

```
├── backend/
│   ├── app/                    # ← 新架构本体(旧 backend/api/ 已删除)
│   │   ├── main.py             # 入口:18个router挂载+CORS+request_id+异常落库
│   │   ├── core/               # config/db/errors/logging/security(JWT+模块化RBAC)/permissions
│   │   ├── models/             # 24 张表 SQLAlchemy 2.0
│   │   ├── routers/            # 18 个路由模块 = 95 端点(全部挂 /api/v1/*)
│   │   ├── schemas/            # Pydantic
│   │   ├── template_engine.py  # 试卷/答题卡 Word 模板引擎
│   │   └── answer_sheet_renderer.py # 答题卡打印HTML(四角定位+二维码)
│   ├── question_import_export.py    # 题库导入导出引擎(注意 sys.path 依赖 CWD=backend)
│   └── venv/ requirements.txt  # ⚠️ 需补 python-docx、qrcode(见技术债#4)
├── frontend/demo/index.html    # 生产前端(33路由,api-bridge.js 封装 /api/v1)
├── frontend/src/               # 旧 Vue SPA(遗留)
├── jiaoyanyun/                 # 教研云对接(凭证已 gitignore)
├── docs/reverse/               # v2 逆向文档(设计/需求/BL/接口/数据模型/技术债)
├── scripts/                    # 部署 + auto_repair(cron 4次/日自动修错误+自动提交)
└── tests/                      # ⚠️ 指向旧架构,不可运行(技术债#2)
```

## 角色-权限模型(v2:模块×动作勾选)

- 角色仅两种: **admin**(恒全量)/ **teacher**(默认=非敏感模块 view+add+edit,存 `users.permissions` JSON)
- 11 个权限模块: question/paper/exam/student/class/teacher/user/ai/ai_select/sync/system(user、system 为敏感模块)
- 教师数据域 = `teacher_classes` 关联班级(班主任每班唯一);各 router 逐条校验越权 403
- ⚠️ 旧四角色(teacher/research/admin/super)已废弃

## 常见问题速查(v2)

| 问题 | 原因 | 处置 |
|------|------|------|
| 接口 404 | 路由前缀:业务端点全部在 `/api/v1/*`(旧版无 /v1) | 用 docs/reverse/current/04-接口规范.md 核对 |
| /api/docs 404 | 生产关闭了 FastAPI docs | 本地起服务看 openapi.json |
| /health 外网 404 | health 挂应用根,被 nginx SPA 兜底 | 服务器内 `curl 127.0.0.1:8001/health` |
| 登录失败 | 新后端是 `{username,password}`;旧 Vue SPA 还在发 `{phone,password}` | 以 demo SPA 为准 |
| 新环境启动 SystemExit | requirements 缺 python-docx/qrcode | 先补依赖(技术债#4) |
| 题库导入失败 | import_export 的 sys.path 依赖 CWD=backend | 从 backend 目录启动 |
| 推 GitHub 认证失败/超时 | 远程 URL 含 token,网络间歇阻断 | 探测窗口重试;URL 格式 `https://用户名:token@github.com/...` |
| 教研云选题拿不到题 | :8787 代理未起/Chrome 未登录 | 上层自动回退本地题库;运维走 proxy /api/chrome/start |
| 服务不生效 | 忘了 reload/restart | `sudo systemctl reload ai-learning` 失败则 restart |

## 工作循环(每个迭代)

```
本地修改 → bash scripts/quick-sync.sh(或 quick-full.sh)→ 云端验证
        → 用户测试 → 通过后 git commit+push origin main(强制规则2)
```

版本号:根 `VERSION`(当前 2.0.0);⚠️ app/main.py:57 与 package.json 尚未联动(技术债#11)
