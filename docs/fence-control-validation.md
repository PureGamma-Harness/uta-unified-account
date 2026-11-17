# Control 事务隔离独立验收

本次只新增 `tests/test_fence_control_boundary.py` 与本报告，没有修改 runtime、root 工作树或
实际运行的 24 小时任务目录。本报告是独立工程回归，不引用未交付的人工审查或工具扫描结论。

生产状态保持 **NO-GO**。本次通过不能替代持续容量、跨节点恢复、金融审查或真实资金上线批准。

## 固定红绿版本

绿基线为 `915c52eb688f4e93c03e1644ecc2d5e816489b41`，包含 root 的 `62f4336`
（原修复 `19dd148`）。独立工作树为 `/workspace/uta-control-faults`，分支 `test/control-faults`。

红基线为 `f238104b9ae6ebad4f24f75c2e6b40c8b991fa7c`。使用真实
`git archive f238104 uta LICENSE` 安全提取到独立目录，再以 `python -I` 显式导入该版本包。
只复制相同测试文件，没有把当前 writer fence 或新的类替代旧实现。

两个运行位置测试文件的 SHA256 完全相同：

```text
43803b192af33a6f26947d6bac147e4175ef28adb79c55ca3af6b4fb155a3d5f
```

对应 `uta/writer_fence.py` 的 SHA256：

| 基线 | 摘要 |
| --- | --- |
| 红 `f238104` | `efbedca2d86436052e57aad477825dacd0e622a48835acab191a30aa7e0d002f` |
| 绿 `915c52e` | `6d375edf8165b8d6f989600bc933ffd45b11ed269c83993bf00e9149449902e5` |

## 防御用例

所有数据库均在本地临时目录，只有合成账户和资金。所有额外触发器的 body 都是
`SELECT 1`，不生成修改金融投影的触发器载荷、外部目标或可复用攻击工具。

| 测试后缀 | 独立断言 |
| --- | --- |
| `control_role_cannot_create_any_additional_main_or_temporary_schema_objects` | 受限 control 角色不能执行额外主表、索引、视图、临时表、临时视图、主触发器或临时触发器；无论是否使用 `writer_fence_` 前缀。必须在 SQL 语句执行时拒绝，不能仅依赖随后发现新对象回滚。 |
| `control_role_cannot_rewrite_official_schema_or_financial_projections` | 拒绝删除官方 guard、ALTER 官方表、DROP guard 元数据、直接执行官方表的 CREATE IF NOT EXISTS、修改账本/账户/仓位投影及开启 writable_schema。全部 schema 与数据不变。 |
| `swallowed_ddl_denial_does_not_commit_following_control_dml` | 调用方捕获内部 SQLite 拒绝后再修改控制记录，事务结束仍须拒绝并回滚；不能因为吞掉错误而提交部分控制变更。 |
| `unknown_attached_control_triggers_reject_at_begin_without_repair` | 分别在五张控制表上放入提前存在的、无特殊前缀的额外触发器；financial/control/read/inbox 四种角色均须在 BEGIN 后、调用方 body 执行前返回 `fence_control_corrupt`；不删除、不重建、不运行触发器。 |
| `weakened_official_control_trigger_and_extra_index_are_corruption_without_repair` | 官方触发器同名但弱化 SQL，以及额外附属索引，都必须拒绝 status/enable/upgrade，保留原损坏现场而不 repair。 |
| `changed_official_control_table_definition_is_rejected_before_any_caller_sql` | 官方表新增列造成 schema 字节变化，必须在 caller body 前拒绝，不能忽略未知列后继续使用。 |
| `legal_lease_lifecycle_preserves_finance_and_real_matching_remains_durable` | 合法 enable/acquire/renew/release 期间金融状态不变；新 generation 仍可完成真实双侧撮合。两客户现金各 999.96，费用账户合计 0.08，持久重开仍只有一笔匹配，ledger.verify 和严格匹配对账通过。 |
| `complete_published_format_zero_schema_upgrades_offline_without_financial_changes` | 独立按 `c05e10f` 原始 schema 创建格式 0，包含完整六个控制保护触发器及 enabled 事件；新 acquire 被明确拒绝，显式离线升级不改金融状态，随后合法新 writer 可写入和对账。 |

金融预期为人工值：客户原有 USD 1000，价格 100、数量 1、手续费率 0.04%，每侧费用 0.04；
没有调用生产计算器生成预期。元数据用受控租约时钟消除调度抖动，实际撮合、SQLite 提交和
账本验证没有替身。该测试时钟不构成真实进程选举、RTO 或系统时钟故障的验收证据。

## 实际命令与结果

绿版本：

```sh
python -m unittest discover -s tests -p test_fence_control_boundary.py -v
/tmp/uta-python310/cpython-3.10.22-linux-x86_64-gnu/bin/python3.10 -m unittest discover -s tests -p test_fence_control_boundary.py -v
```

```text
Python 3.12.14: Ran 8 tests in 0.475s — OK
Python 3.10.22: Ran 8 tests in 0.596s — OK
```

红版本在真实旧包目录导入同一测试：

```sh
python -I -c "import sys,unittest;sys.path[:0]=['/tmp/uta-control-f238104-reference','/tmp/uta-control-f238104-reference/tests'];suite=unittest.defaultTestLoader.loadTestsFromName('test_fence_control_boundary');result=unittest.TextTestRunner(verbosity=2).run(suite);raise SystemExit(not result.wasSuccessful())"
```

```text
Ran 8 tests in 0.442s
FAILED (failures=26)
```

26 是 unittest 子用例的失败数，不是 26 个顶层测试。旧实现允许额外的无副作用控制触发器、
未即时拒绝部分 DDL，且没有在 BEGIN 检出额外控制触发器或损坏官方定义。相同断言下，
旧格式升级及合法撮合正向对照仍通过，因此红态不是简单的不兼容导入或全部接口缺失。

没有 skip、预期失败标记或为旧版本改变断言。红版本只在独立合成目录运行，未安装回当前服务。

完整原始日志（待集成组归档）及 SHA256：

- `/tmp/uta-control-boundary-f238104-red-final.txt`：
  `4d3ddd8589972023cc1ea2274f5ab8ee955293b72e3eddc23d88b6e7ea3a2751`。
- `/tmp/uta-control-boundary-915c52e-green-py312.txt`：
  `777826e37e7e199216f3f2c16a91aaa1b943ca5df242fad3908cf2e3dbf0fbb6`。
- `/tmp/uta-control-boundary-915c52e-green-py310.txt`：
  `1109c2610f635284daed1ce642aaf391fc6f463aff580e1dd8ac92c5cca97a26`。

前七用例首轮输出另保留于 `/tmp/uta-control-boundary-f238104-red.txt` 和
`/tmp/uta-control-boundary-green-first.txt`，最终八用例覆盖并扩展这些边界。

## 运行与回滚

本轮没有数据迁移或部署操作。生产部署仍需保持 managed 模式和持久 guard，损坏时停止入口，
保留数据库与原命令 ID，并先只读导出、对账和调查。禁止以删除未知触发器、自动修补官方
schema、降低格式或启用旧 writer 的方式绕过拒绝。合法旧格式只走明确离线升级。

本机可信操作系统和数据库文件所有者仍是前提；本次没有证明恶意宿主隔离、跨主机 fencing、
任意历史整库恢复检测或高可用。控制权限边界通过，不改变生产 NO-GO。
