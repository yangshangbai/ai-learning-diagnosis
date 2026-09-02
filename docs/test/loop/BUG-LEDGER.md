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

| BUG-L017 | R-QR | BF9 前端图表 | P2 | 任务详情逐题正确率图 backgroundColor 三元无短路,parsed undefined 读 .y 崩溃(Chart.js TypeError 阻塞页面) | 三元 else 分支未判空 | **FIXED v2.0.9**(类型守卫;回归navigate正常✓) |

| (L015) | R-QR后 | BF7/BF8 | ~~P2~~ | 组卷快照未存ques_type,删题后已有考试重判分失型 | PaperQuestion 无题型列 | **FIXED v2.1.0**(加ques_type列+幂等迁移回填+全链取快照;删题后重评分5/5满分0None✓) |

## 备份恢复模块(CX-BK-REV/DEV/QA 三Agent流水)

| ID | 级别 | 描述 | 状态 |
|----|------|------|------|
| DR-01~11 | P0×1/P1×5/P2×5 | 设计评审11项(恢复编排自杀P0/锁残留/.env归属/manifest校验/sudo链/PG属主/subprocess/磁盘/教研云运行态/路由) | 全部吸收进设计v1.1 |
| BQ-01 | **P0** | data/full恢复后db_grants必炸(两层根因: REASSIGN波及共享对象 + \gexec元命令在-c模式不执行 + grep前导空格误判),服务崩溃循环 | **FIXED**(REASSIGN弃用→DO块逐对象ALTER+精确GRANT+二次自修;回归: data恢复19步全绿,db_grants True,health ok,属主0异常) |
| BQ-02 | P1 | 恢复失败无自动回滚(依赖pre_backup人工指引) | OPEN(下迭代;BQ-01修复后失败面已大幅缩小) |
| BQ-03 | P3 | 恢复窗口status经主服务返回502,无法区分停机/故障 | OPEN(架构限制,记录) |

| L019 | 用户实测 | 学生/任务创建 | **P0** | 新增/创建假保存: 纯前端本地造数据+localStorage,从不调后端,"成功"刷新即消失 | demo CRUD 页未接线(mock 遗留) | **FIXED v2.1.2**(真实API+服务端确认为准+失败不更新列表;UI回归✓) |
| L020 | 用户实测 | 列表行操作 | **P0** | 上传/创建任务/详情/编辑/删除串行到最新一条(12处) | 行ID字符串与数字ID `===` 失配后回退 `DATA.*[0]` | **FIXED v2.1.2**(类型安全查找器全覆盖;复现场景回归✓) |
| L018b | 用户实测 | BF3 班级人数 | **P1** | 班级列表人数恒0(有2生显示0),与详情/任务页不一致 | class_router 列表取 class_statistics 僵尸表 | **FIXED v2.1.2**(实时计数同口径;A02班=2✓) |
| L026 | 用户实测 | BF1 会话 | **P1** | token 过期不跳登录,带死token静默进系统全空,写操作全 401 | boot /auth/me 401 被吞 | **FIXED v2.1.2**(清token回登录页;双向回归✓) |
| L024 | 用户实测 | BF8 上传识别 | **P1** | AI识别失败仍提示"已提交入库"(矛盾状态) | 结果横幅不区分成败 | **FIXED v2.1.2**(状态拆分: 成功N张/失败M张分开,全失败显式提示不入库) |
| L021 | 用户实测 | 展示口径 | P2 | 同班显示两种格式(名称 vs 编码+名称) | API学生与本地学生两条渲染路径 | **FIXED v2.1.2**(StudentOut补class_code+fmtClass统一) |
| L023 | 用户实测 | BF8 上传 | P2 | 上传控件未限制文件类型(提示JPG/PNG但可选任意) | input 无 accept | **FIXED v2.1.2**(accept+JS校验跳过) |
| L025 | 用户实测 | BF9 看板 | P3 | 看板题型出现空对象(快照题型NULL) | 旧卷无ques_type | 缓解 v2.1.2(标签"未知";v2.1.0快照列后新卷无此问题) |
| L022 | 用户实测 | 展示 | P3 | 创建时间显示原始ISO格式 | 前端未格式化 | **FIXED v2.1.2**(fmtDT;任务列表/试卷详情) |
| L012b | R-QR | 启动 | P3 | afterRender 水合失败后一次性闸门锁死,首屏空不再重试 | 闸门先置位后取数 | **FIXED v2.1.2**(全空不锁闸) |
