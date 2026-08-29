# 项目逆源文档 (docs/reverse/)

> 生成方式: `codebase-reverse` Skill(复刻自 CodeX 生态 reverse-engineering-business-logic 方法论)
> 分析基线: git `main` @ `ff622a7`(v2.0.0 Workbuddy 重设计版基线) | 生成日期: 2026-08-29
> 证据规则: 所有结论带 `文件:行号`;密钥/凭证一律不入档。

## 文档导航(current/ = 当前真实状态)

| 文档 | 内容 |
|------|------|
| [01-设计思路与开发框架](current/01-设计思路与开发框架.md) | v2 重设计目标、分层架构、认证权限体系、前后端技术栈、部署拓扑 |
| [02-功能需求与角色权限](current/02-功能需求与角色权限.md) | 角色-模块-动作权限模型、按域功能清单、页面清单、断链功能 |
| [03-业务流程BL](current/03-业务流程BL.md) | 6 大业务域的 11 节 BL 文档(主流程/决策规则/状态迁移/副作用) |
| [04-接口规范](current/04-接口规范.md) | 18 个 router / 95 个端点全表(方法/路径/权限/模型) |
| [05-数据模型](current/05-数据模型.md) | 24 张表字段、关系总图、状态枚举 |
| [06-技术债与风险](current/06-技术债与风险.md) | 16 项遗留问题: 现象→影响→建议 |

## 快速事实卡

- **生产真身前端**: `frontend/demo/index.html`(原生 JS 单文件 SPA,33 路由) —— `frontend/src/` Vue SPA 是旧架构遗留,**未接入新后端**
- **后端**: FastAPI,入口 `backend/app/main.py`,所有业务路由挂 `/api/v1/*`(95 端点)
- **数据库**: 生产 PostgreSQL 16(`backend/.env`),开发 SQLite(`backend/app/core/config.py:17-59`)
- **角色**: 仅 `admin` / `teacher` 两种(旧四角色模型已废弃)
- **教研云**: `jiaoyanyun/` 三件套(CDP 看护 + 同步爬虫 + :8787 代理),独立于 FastAPI 进程
- **AI 评分**: 当前为满分占位桩(`backend/app/routers/exam.py:312-355`)
