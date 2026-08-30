# 备份恢复模块 QA 报告(依据台账/提交记录/在线复核整理)

> 模块: 系统设置→「💾 备份与恢复」 | 版本: v2.1.1 | 整理日期: 2026-08-30
> 质量流水: CX-BK-REV(方案评审) → CX-BK-DEV(实现) → CX-BK-QA(测试) → 主Agent回归
> 说明: 原测试批在独立会话执行,本报告由 BUG-LEDGER/CHANGELOG/提交记录/在线复核整理归档

## 一、能力清单(6 端点 + 编排脚本)

| 端点 | 功能 | 在线状态 |
|------|------|---------|
| GET /api/v1/system/backup/list | 备份列表(manifest 校验,坏包标 damaged) | ✅ 2026-08-30 复核 |
| POST /api/v1/system/backup/create | 创建备份(program/data/full) | ✅ program 393KB 实测 |
| GET /api/v1/system/backup/download | 下载(?filename=,白名单防穿越) | ✅ 实测 + 越权 422 |
| POST /api/v1/system/backup/delete | 删除 | ✅ 实测 |
| POST /api/v1/system/restore | 触发恢复(异步 202,systemd-run + restore_helper.sh;恢复前自动安全备份默认开) | ✅ QA 19 步回归 |
| GET /api/v1/system/restore/status | 进度轮询(backups/restore_<id>.log JSON 行) | ✅ 未知 id 404 复核 |

备份类型: 程序(代码/脚本/文档,排可重建物)/ 数据(PostgreSQL+uploads+题图+.env+教研云凭证)/ 整体。
安全机制: 白名单文件名(防穿越)、sha256+manifest 完整性、flock 全局互斥、磁盘<2GB 拒绝、.env 默认跳过恢复、独立恢复确认界面。

## 二、QA 16 用例结果(首轮 13 过 / 2 失败 / 1 跳过)

- 2 个失败均指向 **BQ-01/P0**: data/full 恢复后 db_grants 必炸(三层根因: REASSIGN 波及共享对象 + \gexec 元命令 -c 模式不执行 + grep 前导空格误判),服务崩溃循环
- **BQ-01 修复**: 弃 REASSIGN → DO 块逐对象 ALTER + 精确 GRANT + 二次自修(-t -A 修正 grep 误判)
- **修复后主Agent回归**: data 恢复 19 步全绿(db_grants True / 属主 0 异常 / health ok)→ 2 失败用例闭环
- 1 跳过: 破坏性全量恢复演练(需停机窗口,列维护期执行)

## 三、遗留(OPEN)

| ID | 级别 | 描述 | 状态 |
|----|------|------|------|
| BQ-02 | P1 | 恢复失败无自动回滚(当前依赖恢复前自动安全备份 + 人工指引;BQ-01 修复后失败面已大幅缩小) | OPEN,下迭代 |
| BQ-03 | P3 | 恢复窗口内 status 经主服务返回 502,无法区分停机/故障 | OPEN(架构限制,记录) |

## 四、2026-08-30 在线 E2E 冒烟(本报告附录,主Agent执行)

创建(program,393KB)→ 列表 → 下载(HTTP 200,gzip 完整)→ 越权路径探测 422 → 删除 → 列表归零。全绿。
恢复(破坏性)不在线重演,以 QA 19 步回归为准。
