# BUG-LEDGER — 缺陷台账(LOOP 唯一真源)

> 维护: 主Agent | 格式: `BUG-nnn | 轮次 | 模块 | 级别 | 描述 | 根因 | 状态`
> 状态机: OPEN → FIXING → FIXED(回归通过) / 豁免(用户确认) / 延期

| ID | 轮次 | 模块 | 级别 | 描述 | 根因 | 状态 |
|----|------|------|------|------|------|------|
| BUG-L001 | R1 | BF8 考试判分 | **P0** | docx 导入题标准答案为富文本(`<p>D</p>`),识别答案为纯文本,客观题答对判 0 分(16题全错) | `exam.py _normalize_answer` 未剥离 HTML 标签/未还原实体 | **FIXED v2.0.3**(剥离标签+双重unescape;回归: 7客观题全5分,合计35 ✓) |
| BUG-L002 | R1 | BF5 导入转义 | P2 | 部分题干/答案双重转义(`&` → `&amp;lt;`),影响题8显示与判分 | docx 源文件含实体文本 + 导入管线二次转义 | OPEN(R2 修,需审 question_import_export.py 转义链) |
| BUG-L003 | R1 | BF4/组卷 | P3 | docx 无分值时导入题 score=0,组卷总分依赖快照分值 | 源文件无分值,导入默认 0 | 观察项:组卷时可设分值,暂不改 |
| EXC-001 | — | 反馈功能 | 豁免候选 | 反馈页无后端端点(旧架构断链) | — | 待用户豁免确认 |
| EXC-002 | — | 操作审计 | 豁免候选 | audit_logs 无表无端点 | — | 待用户豁免确认 |
| EXC-003 | — | 旧Vue SPA | 豁免候选 | frontend/src 调旧端点全失效(非生产前端) | — | 待用户豁免确认 |

## 测试环境笔记(非缺陷)

- Windows Git Bash 内联中文 JSON 会转义损坏 → 统一用 `--data-binary @file`(测试方法,非产品问题)
- 教师创建需显式 username/password(设计如此,schema 注释必填);teacher_code 自动 T+id
- 教师关联班级契约: `[{class_id,role,subject_id}]`(非裸 id 数组)
- 生产现存旧班级 id=8"浏览器验证班2"(browser-verify 备注),测试数据均 TEST- 前缀便于清理
