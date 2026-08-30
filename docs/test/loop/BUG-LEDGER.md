# BUG-LEDGER — 缺陷台账(LOOP 唯一真源)

> 维护: 主Agent | 格式: `BUG-nnn | 轮次 | 模块 | 级别 | 描述 | 根因 | 状态`
> 状态机: OPEN → FIXING → FIXED(回归通过) / 豁免(用户确认) / 延期

| ID | 轮次 | 模块 | 级别 | 描述 | 根因 | 状态 |
|----|------|------|------|------|------|------|
| BUG-L001 | R1 | BF8 考试判分 | **P0** | docx 导入题标准答案为富文本(`<p>D</p>`),识别答案为纯文本,客观题答对判 0 分(16题全错) | `exam.py _normalize_answer` 未剥离 HTML 标签/未还原实体 | **FIXED v2.0.3**(剥离标签+双重unescape;回归: 7客观题全5分,合计35 ✓) |
| BUG-L002 | R1 | BF5 导入转义 | P2 | 部分题干/答案双重转义(`&` → `&amp;lt;`) | 表格路径两层escape叠加(_read_doc_blocks + _html_keep_img) | **FIXED v2.0.4**(_html_keep_img先还原再转义;回归Q404单层✓) |
| BUG-L003 | R1 | BF4/组卷 | P3 | docx 无分值时导入题 score=0,组卷总分依赖快照分值 | 源文件无分值,导入默认 0 | 观察项:组卷时可设分值,暂不改 |
| EXC-001 | — | 反馈功能 | 豁免候选 | 反馈页无后端端点(旧架构断链) | — | 待用户豁免确认 |
| EXC-002 | — | 操作审计 | 豁免候选 | audit_logs 无表无端点 | — | 待用户豁免确认 |
| EXC-003 | — | 旧Vue SPA | 豁免候选 | frontend/src 调旧端点全失效(非生产前端) | — | 待用户豁免确认 |

## 测试环境笔记(非缺陷)

- Windows Git Bash 内联中文 JSON 会转义损坏 → 统一用 `--data-binary @file`(测试方法,非产品问题)
- 教师创建需显式 username/password(设计如此,schema 注释必填);teacher_code 自动 T+id
- 教师关联班级契约: `[{class_id,role,subject_id}]`(非裸 id 数组)
- 生产现存旧班级 id=8"浏览器验证班2"(browser-verify 备注),测试数据均 TEST- 前缀便于清理

| BUG-L004 | R2 | BF5/题库 | **P1** | 4份docx题码 `MAT-G6-IMP-序号` 按文件内序号生成,跨文件碰撞互相覆盖(导入3文件后总量不变,前文件题被顶掉) | `_gen_code` 无文件级唯一命名空间 | **FIXED v2.0.4**(文件md5前6位注入题码;回归4文件46题id各异✓,同文件重导去重✓) |
| BUG-L005 | R2 | BF4 检索 | ~~P1~~ | ~~keyword 过滤失效~~ | **撤销**: 后端检索参数为 `q`,用例参数名写错;q=无理数→3条 ✓ | 撤销(用例修正) |

| BUG-L006 | R3 | BF1 权限模型 | **P1** | 查看类端点只挂require_auth未挂模块权限,零权限教师可读全部试卷/学生/班级/看板(15+端点泄露,实证审计发现) | 列表GET端点未挂 require_permission(view) | **FIXED v2.0.5**(9 router 22端点补view权限;零权限探测全403✓,恢复200✓,admin✓) |
| BUG-L007 | R3 | BF3 用户权限 | P2 | `PUT permissions:{}` 空字典被 `or default` 吞掉,无法清零用户模块权限 | user.py update 的 `raw_perms or default` falsy 兜底 | **FIXED v2.0.5**(空dict=清零;回归✓) |
| BUG-L008 | R3 | BF1 展示层 | P3 | 零权限时 /auth/me 与 login 兜底展示全量权限,与403执行不一致,误导前端菜单 | auth.py/security.py 的 `or all_permissions()/or default` 展示兜底 | **FIXED v2.0.5**(展示与执行同源;回归✓) |

| BUG-L009 | R4 | BF9 工作台 | P2 | 登录后首屏 KPI 全 0、最近任务表空(异步加载竞态),二次进入数据正确(108/2/1/5/4/2+任务行) | 首屏渲染与数据加载时序 | OPEN(待复测,疑仅首屏竞态) |

| BUG-L010 | R5 | BF7/BF4 级联 | **P1** | 删题后 GET /papers/{id}/questions 500,试卷快照丢失(设计=置NULL保留) | PaperQuestionOut.question_id 非可选int,校验NULL失败 | **FIXED v2.0.7**(改Optional;回归2行含删题行✓) |
| BUG-L011 | R5 | BF3 级联 | **P1** | 删教师500(先删users违反teachers_user_id_fkey),账号未注销仍可登录 | 服务器版删除顺序错误 + Teacher/User无relationship致ORM删除乱序 | **FIXED v2.0.7**(教师本体命令式批量删除后再删账号;回归删除200+登录401✓) |
