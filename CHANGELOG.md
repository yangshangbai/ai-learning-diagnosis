# 修改清单 — 教研管理平台(AI学习诊断系统)

> 版本: v2.1.0 | 日期: 2026-08-30

---

## v2.1.0 — 自定义模板×每生QR合并 + L015快照题型 (2026-08-30)

- **新功能(用户自定义模板合并)**: 试卷答题卡模板 source=user 时,`print?format=docx` 返回 **zip(每生一份docx)**:以用户上传模板为底,页眉/正文自动回填 任务号/试卷号/学生号并注入个人二维码图片(payload tk/pp/cl/st);无占位的模板在文末追加机读带。无用户模板时维持系统版式单docx。前端按 content-type 自动命名 zip/docx;`_download_response` 支持 media_type
- **L015/P2 修复**: `paper_questions` 增加 `ques_type` 快照列(启动幂等迁移+存量回填,seed._ensure_paper_question_columns);组卷写入/判分定型/重评分/打印 全链路优先取快照题型。回归: 删题385后重评分 5/5 满分、0主观None行(旧行为为该行变主观判分丢失) ✓
- 验证数据: 任务24(QR班/每生Word)保留供用户复验;L015验证数据已清理
- 附带: zip 下载 Content-Type 修正(application/zip)

## v2.0.9 — 每生二维码答题卡 Word(用户需求直出) (2026-08-30)

- **新功能**: `GET /exam-tasks/{id}/answer-sheets/print?format=docx` 返回**每生一页的 Word 答题卡**,页顶机读带含**真实个人二维码图片**(qrcode 库),payload = `JY|tk=任务号|pp=试卷号|cl=班级号|st=学生号|pg=1/1`;支持 student_id 单生补打
- template_engine 新增 `generate_task_sheets_docx`/`build_sheet_qr_payload`;HTML 打印通道 payload 同构(加 cl=班级号);_task_students 补 classCode
- 前端任务详情页新增「⬇ 答题卡Word(每生二维码)」按钮
- **L017/P2 修复**: 任务详情逐题正确率图 backgroundColor 三元短路缺失,parsed undefined 时读 .y 崩溃——加类型守卫
- 视觉验证: zxing 实测解码两张 QR(任务/试卷/班级/学生四号逐生对应),主Agent读图确认图案清晰互异;HTML 通道 payload 同构 ✓;单生补打 1 页 1 码 ✓
- 说明: 每生 Word 采用系统默认版式;「用户自定义模板与每生 QR 占位合并」列入下一迭代
- 验证数据保留: TEST-QR班(15)/生19,20(A01,A02)/卷29/任务24 供用户自行下载验证

## v2.0.8 — LOOP R6-R7 收敛版 (2026-08-30)

- **L009/P2 修复**: 工作台首屏 KPI 恒 0——真根因为 `loadBackendData` 被两处调用但**从未实现**;补实现(启动装载六类列表)+ dashboard afterRender 水合钩子。回归: 新标签页首屏即显示 107题/2卷/1任务/5生 ✓
- **L012/P2**: 班级/教师/试卷/任务 name 加 max_length=255(超长名 500→422)
- **L013/P2**: 伪装 docx 500→400 友好提示
- **L014/P2**: 题干/答案/解析入库前剥离 `<script>` 块(存储型XSS护栏)
- **L016(修复引入,P0)当轮闭环**: L013 修复时把成功路径 return 落入 except 块致 import-docx 恒返回 null;重构 try/except/finally 后双分支回归 ✓
- **R7 收敛判定达成**: 连续2轮零新增P0/P1,P0回归集全过,P1全闭环;遗留 L015(P2,schema迁移)+豁免候选3项
- 测试数据全部清理归零(47题+6任务+3卷+5生+4师+2班),级联删除全程无孤儿
- 总报告: docs/test/loop/测试总报告.md

## v2.0.7 — LOOP R5: 级联删除两连修 (2026-08-30)

- **BUG-L010/P1 修复**: 删题后试卷快照端点 500(`PaperQuestionOut.question_id: int` 不接受 NULL,而删题设计即置 NULL 保留快照)。修复: schema 改 Optional。回归: 快照2行(删题行stem空+存活行完整) ✓
- **BUG-L011/P1 修复**: 删教师 500(先删 users 违反 teachers_user_id_fkey)。根因两层: ①服务器版删除顺序错误 ②Teacher/User 无 relationship(),ORM unit-of-work 不感知表级外键,调整顺序仍乱序。修复: 教师本体改命令式批量删除(立即发SQL,顺序确定)后再删账号。回归: 删除200+账号注销401 ✓
- R5同时通过: 浏览器线学生/教师/班级/试卷/用户管理/AI配置6页, M4级联 C05(409/200)/C07(409)/C08(标签清洗)
- 台账: L001-L004/L006-L008/L010/L011 全部FIXED; L003观察; L009竞态OPEN(R6修); 豁免候选×3

## v2.0.6 — LOOP R4: L2浏览器人手线首轮 (2026-08-30)

- 主Agent亲测 Chrome 真实操作: 登录→工作台→题库列表→任务列表→任务详情,5页全绿(数据与API层一致: 108题/任务1/已上传1/5/均分33)
- **BUG-L009(改判P2)**: 登录后工作台首屏 KPI 显示 0(异步加载竞态),二次进入数据正确(108题/2卷/1任务/5生/4班/2师全部正确);待复测
- 测试环境说明: IAB 截图受限,UI 证据以 DOM 快照留存;SPA 菜单点击需用应用内 navigate() 路由
- 无代码变更,版本号随快照递增

## v2.0.5 — LOOP R3: 权限模型系统性修复 (2026-08-30)

- **BUG-L006/P1 修复**: 查看类端点只挂 require_auth 未挂模块权限,零权限教师可读全部试卷/学生/班级/看板(15+端点数据泄露)。修复: 9个router 22个GET端点补 `require_permission(模块,"view")`。回归: 零权限全探测403 ✓,恢复后200 ✓,admin不受影响 ✓
- **BUG-L007/P2 修复**: `PUT permissions:{}` 空字典被 `or default` 吞掉,无法清零用户权限。修复: user.py 显式区分空dict(清零)/未传(不动)。回归: 清零→me={}→403 ✓
- **BUG-L008/P3 修复**: 零权限时 /auth/me 与 login 展示层兜底全量权限(`or all_permissions()`),与执行不一致误导前端菜单。修复: 展示层如实返回(`{}`),与 require_permission 同源。回归 ✓
- R3同时通过: BF1-05/06/08/09、BF3-06唯一性、权限矩阵实证审计(零权限探测法)

## v2.0.4 — LOOP R2: 导入管线双修复 (2026-08-30)

- **BUG-L002/P2 修复**: docx导入双重转义(表格路径 `_read_doc_blocks` escape + `_html_keep_img` escape 叠加 → `&amp;lt;`)。`_html_keep_img` 提为模块级并改为"先实体还原再转义"(恰好一层),段落路径同步套用。回归: 新预览0双层,落库Q404=`&lt;`单层 ✓
- **BUG-L004/P1 修复**: docx题码 `MAT-G6-IMP-序号` 按文件内序号生成,多文件导入跨文件碰撞互相覆盖(4文件仅存1份)。修复: import-docx 计算文件内容 md5 前6位注入题码(`MAT-G6-{HASH}-序号`),同文件重导哈希相同保去重。回归: 4文件落库46题id各异 ✓,文件①与④md5相同(内容重复)自动去重 ✓
- 测试说明: 题库检索参数为 `q`(非keyword),用例BF4-04已修正;测试文件①与④内容完全相同(md5 ccbbcb64)
- 台账: BUG-L001 FIXED / L002 FIXED / L004 FIXED / L003 观察项 / 豁免候选×3

## v2.0.3 — LOOP R1: 判分HTML归一化修复 (2026-08-30)

- **BUG-L001/P0**: docx导入题标准答案为富文本(`<p>D</p>`),服务端判分未剥HTML标签导致客观题答对判0分。修复: `_normalize_answer` 剥离标签+双重实体还原。回归: 7客观题全5分(合计35),主观题正确留教师,重复上传superseded/调分保分/看板口径全部通过
- 遗留: BUG-L002(P2 双重转义) R2 修复;台账见 docs/test/loop/BUG-LEDGER.md

## v2.0.2 — AI 服务端统一密钥 (2026-08-30)

> 用户指示:视觉/推理两个 AI 模型统一使用智谱 Key;落实 D3(密钥不经浏览器)

- **服务端密钥托管**: `AI_ZHIPU_API_KEY` 写入服务器 `backend/.env`(不入 Git、不经前端传输)
- **ai_select.py**: AI 选题推理模型服务端密钥回退;无前端 key 时自动切换 provider=zhipu + glm-4-flash
- **import_export.py**: OCR 导入(import-ocr/import-smart)视觉模型服务端密钥回退
- **前端清理**: 删除 demo/index.html 中**硬编码的旧智谱视觉 Key 与旧 DeepSeek Key**(安全雷);推理模型默认从 DeepSeek 改为智谱 GLM-4-Flash;AI 模型配置页 Key 改为"可留空=服务端兜底",取消前端强制校验
- ⚠️ 提醒: 旧两个 Key 已存在于 Git 历史中,建议在各自平台作废轮换
- 注: 用户浏览器若存有旧配置(localStorage),到 AI模型配置页清空 Key 保存一次即可切到服务端密钥

## v2.0.1 — 任务闭环最小修复 (2026-08-29)

## v2.0.1 — 任务闭环最小修复 (2026-08-29)

> 依据: `docs/reverse/current/07-任务闭环审查报告.md`(design-review 对抗审查,基于 v2.0.0 标签快照)
> 备份: tag `v2.0.0` = 修复前快照;本次修复 = 该报告 D1-D9(P0×3/P1×6 全修)

- **D1/P0 闭环贯通**: 前端识别结果不再只存浏览器内存——`POST /exam-tasks/{id}/answer-sheets` 持久化(含识别答案),后端服务端判分;虚假"已入库"文案更正
- **D2/P0 错误归因**: 学号不匹配改为跳过+人工指认,废除"按上传顺序落到某学生"的兜底
- **D3/P0 密钥**: 后端新增 `AI_ZHIPU_API_KEY` 服务端密钥回退(core/config.py),前端仍兼容传入;建议生产配置后清空前端 key
- **D4+D5/P1 评分重写**: 满分桩删除;新增确定性判分(客观题归一化比对标准答案,多答案/多选/判断适配;主观题留教师);重评分改 upsert,教师已接管分数保留
- **D7/P1 越权**: upload/score/list_scores/adjust 四端点补 `_ensure_task_owner`(教师仅限本人任务);教师调分加 0~满分校验
- **D8/P1 重复上传**: 同生同任务旧卡置 superseded,列表/看板只认 active(修复 upload_rate>100% 与双卡重复累加)
- **D6/P1 状态机**: status 加六态枚举校验;关键节点推进(assign→pending / 上传→in_exam / 判分→scoring)
- **D11/P2**: 前端批量评分去除 mock 答案伪造,改调服务端重判分
- **部署脚本**: quick-sync.sh 同步范围加入 `frontend/demo/index.html + api-bridge.js`
- 未修项(D10/D12/D15/D16/D17/D18 等)见 07 报告"未修项建议排序"

## v2.0.0 — Workbuddy 重设计版基线 (2026-08-29)

- **架构重设计**: 后端从旧 `backend/api/` 扁平结构迁移到 `backend/app/{core,models,routers,schemas}` 分层;18 个 router / 95 个端点,统一挂 `/api/v1/*`
- **新功能域**: 考试任务六态状态机+答题卡渲染打印(四角定位+二维码)+AI识别(GLM-4V);题库 docx/OCR/智能三路导入;AI 选题四步流水线对接教研云(:8787 代理);试卷/答题卡 Word 模板引擎;三级实时看板(任务/班级/学生)
- **权限重设计**: 角色收敛为 admin/teacher,11 模块×4 动作勾选式 RBAC,教师数据域按 teacher_classes 隔离
- **教研云对接**: `jiaoyanyun/` 三件套(Chrome CDP 看护/同步爬虫/查询代理)
- **运维**: system_logs 错误闭环 + auto_repair cron 自动修复/自动提交;生产 PostgreSQL 16
- **工程**: 本地全量重建(自云端拉取 1830 文件逐字节校验),v2.0.0 基线提交 `ff622a7` 推送 GitHub
- **文档**: 新增 `docs/reverse/` 逆源文档六件套(设计思路/功能需求/业务流程BL/接口规范/数据模型/技术债16项);AGENTS.md 重写为 v2
- **已知债务**: 16 项见 `docs/reverse/current/06-技术债与风险.md`(含: AI 评分为满分桩、requirements 缺 python-docx/qrcode、旧 Vue SPA 未退役、密码无盐 sha256)

---

## v1.1.0 — 历史版本 (2026-07-22)

> 版本: v1.1.0 | 会话ID: sess_8592fa6d

---

## 一、Bug修复 (10项)

### 1. 登录闪退 → 修复 [CRITICAL]
- **文件**: `frontend/src/stores/auth.js`
- **原因**: axios拦截器已返回`response.data`，但auth store又做`res.data.access_token`（双重解包），导致TypeError，回退到mock登录存`demo-token`，后续API全部401
- **修复**: `const data = res.data || res` 兼容两种解包

### 2. 307→401重定向链 → 修复 [CRITICAL]
- **文件**: `backend/api/*.py` (10个路由文件)
- **原因**: FastAPI `@router.get("/")` 创建的路由带尾部斜杠，前端调用无斜杠URL触发307重定向，跨域丢Authorization header
- **修复**: `@router.get("/")` → `@router.get("")`，路由不再有尾部斜杠，直接200

### 3. 空白页 → 修复 [CRITICAL]
- **文件**: `frontend/src/views/teacher/StudentList.vue`, `TaskList.vue`, `UploadPaper.vue`, `ExercisePlan.vue`
- **原因**: API返回`{items:[], total:N}`，前端直接用整个对象当数组调`.filter()` → TypeError → 页面崩溃
- **修复**: `raw?.items || raw?.data || raw || []`

### 4. 上传列表为空 → 修复 [HIGH]
- **文件**: `backend/api/auth.py`, `frontend/src/views/teacher/UploadPaper.vue`
- **原因**: 登录API没返回老师的`classes`字段，上传页过滤匹配不到任务；且class_ids类型不一致(字符串/整数)
- **修复**: 登录增加`classes: [1,2]`返回；前端过滤统一`Number()`转换

### 5. 图片预览裂开 → 修复 [HIGH]
- **文件**: `backend/api/upload.py`
- **原因**: 预览端点`/api/upload/{id}/preview/{path}`要求认证，`<img>`标签无法发送Authorization header
- **修复**: 预览端点移除`Depends(get_current_user)`

### 6. 空名任务可创建 → 修复 [MED]
- **文件**: `backend/schemas/task.py`, `auth.py`
- **原因**: TaskCreate/TeacherCreate的`name`字段无`min_length`验证
- **修复**: `name: str = Field(..., min_length=1)` → 空名返回422

### 7. Research角色无权编辑知识库/题源 → 修复 [MED]
- **文件**: `backend/middleware/auth_middleware.py`, `backend/api/knowledge.py`, `backend/api/sources.py`
- **原因**: 知识库/题源只允许admin+super，教研员应有写权限
- **修复**: 新增`require_research_admin = require_role("admin", "research", "super")`

### 8. 图片上传不持久 → 修复 [HIGH]
- **文件**: `backend/api/upload.py`, `frontend/src/views/teacher/UploadPaper.vue`
- **原因**: 图片只在浏览器内存(`URL.createObjectURL`)，刷新消失
- **修复**: 选图即上传到服务器，重进页面`GET /api/upload/{id}/files`恢复

### 9. DELETE无FK保护 → 修复 [HIGH]
- **文件**: `backend/api/classes.py`, `students.py`, `tasks.py`, `users.py`, `knowledge.py`
- **修复**: 6个删除端点增加FK依赖检查，返回409+中文说明

### 10. FastAPI/Starlette版本冲突 → 修复 [CRIT]
- **文件**: `backend/requirements.txt`
- **修复**: `fastapi>=0.111.0` + `starlette>=0.37.0`

---

## 二、新增功能 (7项)

### 1. 错误日志系统
- **后端**: `models/error_log.py` + `api/logs.py` + main.py错误中间件
- **前端**: `views/admin/LogWeb.vue` + axios/Vue错误自动上报
- **特性**: `repair`字段标记修复状态，Agent可查询未修复错误

### 2. AI模型配置
- **后端**: `models/ai_config.py` + `api/admin.py` AI配置端点
- **前端**: `views/admin/AISettings.vue` (超管专属)
- **特性**: 6个AI服务商配置，AppKey明文显示，可编辑保存

### 3. 错误日志Web查看
- **前端**: `views/admin/LogWeb.vue`
- **路由**: `/admin/logs` (超管专属)

### 4. 下拉选项统一常量
- **文件**: `frontend/src/utils/constants.js`
- **修复**: 9个Vue文件的硬编码下拉改为import常量

### 5. 导航栏统一
- **文件**: 7个admin页面BottomNav定义
- **修复**: 超管导航统一为5标签(dashboard/org/system/diagnosis/me)，匹配Demo设计

### 6. 删除保护完整性
- **文件**: `backend/api/*.py` (6个文件)
- **修复**: 所有DELETE端点增加FK依赖检查

### 7. 权限配置页
- **文件**: `frontend/src/views/admin/PermissionConfig.vue`
- **路由**: `/admin/permissions` (超管专属)

---

## 三、文件变更汇总

### Backend (修改22个文件)

| 文件 | 变更类型 | 说明 |
|------|:---:|------|
| `main.py` | 修改 | 错误中间件 + datetime导入 |
| `requirements.txt` | 修改 | 版本兼容 |
| `api/auth.py` | 修改 | 登录返回classes |
| `api/classes.py` | 修改 | 路由斜杠 + DELETE保护 |
| `api/students.py` | 修改 | 路由斜杠 + DELETE保护 + RBAC |
| `api/tasks.py` | 修改 | 路由斜杠 + DELETE保护 + 所有权检查 |
| `api/knowledge.py` | 修改 | 路由斜杠 + RBAC(research) |
| `api/questions.py` | 修改 | 路由斜杠 |
| `api/diagnosis.py` | 修改 | 路由顺序修复 |
| `api/exercises.py` | 修改 | 路由斜杠 |
| `api/audit.py` | 修改 | 路由斜杠 |
| `api/users.py` | 修改 | Pydantic schema + 手机唯一性 |
| `api/sources.py` | 修改 | 路由斜杠 + RBAC(research) |
| `api/admin.py` | 修改 | AI配置 + 远程协助 + RBAC |
| `api/ai.py` | 新增 | AI建议端点 |
| `api/upload.py` | 重写 | 文件列表+预览+免认证 |
| `api/logs.py` | 新增 | 错误日志CRUD |
| `models/ai_config.py` | 新增 | AI配置表 |
| `models/error_log.py` | 新增 | 错误日志表 |
| `models/__init__.py` | 修改 | 注册新模型 |
| `schemas/auth.py` | 修改 | TeacherCreate/Update schema |
| `schemas/task.py` | 修改 | name min_length验证 |
| `middleware/auth_middleware.py` | 修改 | 新增require_research_admin |
| `seed_data.py` | 修改 | AI配置种子 + 扩展数据 |

### Frontend (修改20个文件)

| 文件 | 变更类型 | 说明 |
|------|:---:|------|
| `src/stores/auth.js` | 修改 | 双解包修复 |
| `src/main.js` | 修改 | Vue错误捕获 |
| `src/api/request.js` | 修改 | 错误上报 + 斜杠处理还原 |
| `src/api/diagnoses.js` | 修改 | /diagnoses→/diagnosis |
| `src/api/classes.js` | 修改 | /grades→/classes/grades |
| `src/api/dashboard.js` | 修改 | /dashboard/stats→/admin/stats |
| `src/api/knowledge.js` | 修改 | /knowledge/tree→/knowledge |
| `src/api/teachers.js` | 修改 | /teachers→/users |
| `src/api/sources.js` | 新增 | 题源API |
| `src/api/aiConfig.js` | 新增 | AI配置API |
| `src/utils/constants.js` | 新增 | 共享常量 |
| `src/router/index.js` | 修改 | 新路由 |
| `src/views/teacher/StudentList.vue` | 修改 | items提取修复 |
| `src/views/teacher/TaskList.vue` | 修改 | items提取修复 |
| `src/views/teacher/UploadPaper.vue` | 修改 | 即时上传+恢复+items修复 |
| `src/views/teacher/ExercisePlan.vue` | 修改 | 编辑Modal+items修复 |
| `src/views/admin/Dashboard.vue` | 修改 | 导航统一+researchNav |
| `src/views/admin/Organization.vue` | 修改 | 导航统一 |
| `src/views/admin/TaskManage.vue` | 修改 | 导航统一 |
| `src/views/admin/TaskDetail.vue` | 修改 | 导航+researchNav |
| `src/views/admin/DiagnosisBoard.vue` | 修改 | 导航修复 |
| `src/views/admin/AdminProfile.vue` | 修改 | superNav |
| `src/views/admin/SystemManage.vue` | 修改 | 菜单图标+AI配置入口+日志入口 |
| `src/views/admin/QuestionSources.vue` | 重写 | API接入 |
| `src/views/admin/AISettings.vue` | 新增 | AI配置页 |
| `src/views/admin/LogWeb.vue` | 新增 | 错误日志页 |
| `src/views/admin/PermissionConfig.vue` | 新增 | 权限配置页 |
| `src/views/admin/AuditLog.vue` | 修改 | API接入 |
| `src/views/admin/RemoteHelp.vue` | 修改 | API接入 |
| `src/views/admin/AIAssistant.vue` | 修改 | API接入 |

### 测试文件

| 文件 | 说明 |
|------|------|
| `tests/ai_agent_test_cases.json` | 205个测试用例，24套件 |

---

## 四、部署提示词

```
你需要在服务器上部署AI学习诊断系统 v1.1.0。

## 1. 代码同步
将整个项目目录复制到服务器，覆盖所有文件。

## 2. 后端部署
cd backend
pip install -r requirements.txt
# 清除旧数据库(首次部署)
rm -f ai_learning.db
rm -rf uploads/
# 启动 (生产环境用 --workers 4)
python -m uvicorn main:app --host 0.0.0.0 --port 8001

## 3. 前端部署
cd frontend
npm install
npm run build
# 将 dist/ 目录部署到 Nginx
# Nginx配置:
#   location /api/ { proxy_pass http://127.0.0.1:8001; }
#   location / { root /path/to/dist; try_files $uri /index.html; }

## 4. 验证清单
- [ ] curl /api/health → {"status":"ok"}
- [ ] 登录API返回 access_token + user (含classes字段)
- [ ] GET /api/knowledge?flat=true → 200 (非307)
- [ ] GET /api/students → 200 + 30 records
- [ ] DELETE /api/classes/1 → 409 (有学生不能删)
- [ ] 图片上传 → 关闭重进 → 图片仍在
- [ ] 空名创建任务 → 422
- [ ] Research角色可编辑知识库/题源
- [ ] 前端登录不闪退

## 5. 关键修复提醒
- auth.js store 已修复 token 双解包问题
- 所有路由 @router.get("/") → @router.get("") 避免307
- 上传图片即时保存到 uploads/ 目录
- 预览端点免认证 (img标签无法发header)

## 6. 测试账号
李老师 13800001111 / demo123 (老师)
王校长 13900001111 / demo123 (管理员)  
赵教研 13900002222 / demo123 (教研员)
超级管理员 13900003333 / demo123 (超管)
```
