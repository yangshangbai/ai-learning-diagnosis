# AI学习诊断与个性化练习系统

面向培训机构的AI智能教学助手，支持试卷上传、AI批改诊断、学生档案、个性化练习生成。

## 快速开始

### 环境要求
- Python 3.11+
- Node.js 18+
- npm 9+

### 一键启动

**Windows:**
```bat
scripts\start.bat
```

**Linux/Mac:**
```bash
chmod +x scripts/*.sh
./scripts/start.sh
```

### 手动启动

1. 后端:
```bash
cd backend
pip install -r requirements.txt
python main.py
```

2. 前端:
```bash
cd frontend
npm install
npm run dev
```

### 访问地址
- 前端: http://localhost:5173
- 后端API: http://localhost:8000
- API文档: http://localhost:8000/docs

### 演示账号
| 角色 | 手机号 | 密码 |
|------|--------|------|
| 老师(李老师) | 13800001111 | demo123 |
| 管理员(王校长) | 13900001111 | demo123 |
| 教研员(赵教研) | 13900002222 | demo123 |
| 超级管理员 | 13900003333 | demo123 |

### 技术栈
- 前端: Vue 3 + Vite + Pinia + ECharts 5 + Axios
- 后端: FastAPI + SQLAlchemy + SQLite
- 认证: JWT
- 开发数据库: SQLite

### 项目结构
```
├── backend/           # FastAPI 后端
│   ├── api/           # API 路由
│   ├── models/        # SQLAlchemy 模型
│   ├── schemas/       # Pydantic 数据模型
│   ├── services/      # 业务逻辑 & AI Mock
│   ├── middleware/     # JWT 认证中间件
│   ├── main.py        # 应用入口
│   ├── database.py    # 数据库配置
│   ├── config.py      # 配置管理
│   └── seed_data.py   # 种子数据
├── frontend/          # Vue 3 前端
│   └── src/
│       ├── api/       # API 调用模块
│       ├── components/# 通用组件
│       ├── stores/    # Pinia 状态管理
│       ├── utils/     # 工具函数
│       └── views/     # 页面视图
│           ├── admin/ # 管理端页面
│           └── teacher/# 老师端页面
├── scripts/           # 启动/停止脚本
├── tests/             # 测试文件
│   ├── conftest.py    # Pytest 配置
│   ├── test_api/      # API 测试
│   └── test_manual/   # 手动测试清单
└── cloud_migration.md # 云端部署迁移指南
```

### 运行测试
```bash
cd tests
pytest -v
```

### 停止系统

**Windows:**
```bat
scripts\stop.bat
```

**Linux/Mac:**
```bash
./scripts/stop.sh
```

### 生产部署

参见 `cloud_migration.md` 了解云端部署方案。
