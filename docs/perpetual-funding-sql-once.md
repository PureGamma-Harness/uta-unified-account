# 三个资金费 SQL 方法的单次验收提案

本变更仅为 CODE，SQL 尝试0、目标 compile/import0。独立 CODE 复审与 root 的完整
源码/plan SHA/唯一 argv GO 均待定。原 `f3410774` 两个金融模块和六个测试的字节未变；
原49407计划和d7e0 manifest仍为原字节 NOT_RUN0。独立 RAW `b9aabc07` 只闭合此前
三个纯算术方法，不能当作本提案的 SQLite、资金费适配器或生产资格。

新入口 `tools/run_funding_sql_once.py` 沿用已审 pure-once 的 retained capsule、
父级双 pipe/shared cap、真实 host wait/reap/EOF/TAIL 结构。新 plan 精确列出67个输入：
63个 UTA 源文件、原测试、旧纯算控制文件（保留出处）、新 SQL 控制及人工 oracle。
目标 UTA imports 仅通过 retained FrozenUTA/FrozenLoader；原金融模块不打补丁，
不替换 `sqlite3.connect`，不降低配置归档的1MiB上限或既有 catalog/fencing 断言。
金融 artifact 仍按原代码读取不可变物化 UTA 源并检查实际 loaded functions/constants；
所有物化源及 plan 前后复核。此处依赖可信不可变部署和 stdlib，不是敌意代码沙箱。

固定顺序、固定三条 `FundingLocalSQLTests`，failfast；没有 discover、额外预热或重试：

1. `test_fresh_period_retry_reopen_and_period_uniqueness`
2. `test_mandatory_debit_uses_cash_deficit_and_real_risk_state`
3. `test_corrupt_reserved_id_rejects_atomically_and_late_freeze_is_not_backdated`

原三个方法保持原字节；控制显式包装原 fixture 一次，在 distress 返回前用原服务接纳
`synthetic-pending-ro`：a卖`.1@100`、reduce-only，不调用撮合。它是新声明的业务设置，
不能描述成原测试原样行为。当前 a 现金1、仓位+1、MM .5，假设成交后的现金 .99、
MM .45，surplus .54不低于 .5，且累计RO .1不超过仓位1，所以原准入应允许。
后续仍运行原资金费和原风险状态机。oracle须核旧单实际 CANCELLED/未成交，实际
LIQUIDATING cycle1/revision1，新建全量`-1@100`只减仓单为 OPEN/filled0，且原回执
引用的撤单及新单ID与数据库一致。政策若与这些手算不符则失败，不能改断言凑通过。

## 五库人工基线

每库初始撮合`1@100`，两侧手续费各`ceil(.04, USD cents)=.04`，原始资金来源是
授权合成入金，逐币双分录对应 custody。资本库追加`.6@100`，两侧费用各
`ceil(.024, cents)=.03`。完整逐例输入、账务、仓位成本和理由在 `sql-once-oracle.json`。

| 新库 | 客户期末 USD | 资金费/拒绝 | 撮合/侧成交 | journal |
| --- | --- | --- | --- | --- |
| period | a999.95、b999.97、treasury0 | a-.01/b+.01；相同ID查原回执，变参数或换ID同period拒绝 | 1/2 | 6 |
| distress | a-1、b1001.96、treasury0 | a-2/b+2；cash deficit1、principal0，实际撤单与RO计划 | 1/2 | 6 |
| rollback | a999.96、b999.96、treasury0 | 故意孤立但平衡的保留ID分录；settle无回执，原快照全等 | 1/2 | 5 |
| late | a999.96、b999.96、treasury0 | 无可信过去边界快照，整期拒绝 | 1/2 | 4 |
| capital | a999.93、b999.97、c999.97、treasury.99 | mark1/费率.015；a0/b+.01/c0，真实treasury转入.01承担差额 | 2/4 | 11 |

合计5新库、6个唯一撮合、12侧成交、32 journal、3期已提交资金费；费用`.46`，
custody `-10002.04`。各库 clearing及reserve最终0；孤立故障分录为test-source -1/
test-sink +1，不是资本注入。capital原treasury先真实deposit1，最终扣至.99；无证明
拒绝且下一周期复用证明拒绝，不允许负system资本科目凭空注资。

三个方法成功后，先证明所有观察到的 SQLite handles 已经关闭，再逐库新建 Database
并以 `mode=ro`/query-only 的 guarded read snapshot重开。原 existing-only 构造器核对
真实 schema/config/current artifact；不自动建表、不修 guards、不安装资金费或credit。
新真实服务账本、`Matcher(initialize=False)` 及原资金费实例的 verifier 共同加入该新
只读快照；资金费实例只保留同版本policy/artifact，不能把这种新连接核对称为进程崩溃恢复。
核完整非零逐币余额集合、全部仓位/成本、每笔数量/价格/费用/PnL、订单/撮合/分录对应、
period现金与资本归属、真实风险状态及资金费完整核对。rollback库账本和撮合应通过，
资金费 verifier 必须因那个故意orphan拒绝；不笼统宣称所有库健康。无第二腿/COMMIT
故障注入、schema篡改注入或完整历史准入重放的主张。

## 待审资源边界

单解释器/CPU1；无子任务、线程、网络、外部进程/PID读取或真实服务。审计连接只允许
plan所列5库的10个rw/ro URI，最多1024次；固定fixture根覆盖继承环境变量。每库必须是
新私有子目录0700，文件0600。实际 SQLite connect/handle 成对记录，对所有own handle
的 `in_transaction` 访问抛已关闭 ProgrammingError 才算闭合；不以GC或connection上下文
管理器推测close。泄漏使验收失败，即使随后为资源安全仅关闭本次own handle，也不改绿。
只在这些连接关闭后读取DB字节摘要；不读取或关闭其他authority，不扫描PID或做清理探针。

提出 OS target20s + parent22s分类/drain窗口：SQL比先前纯算多5次完整 schema/audit/funding
安装、6次双侧提交、多次63源/loaded-function artifact构造及5次完整新只读核对。此为源码
工作量下的有限时限提案，没有预热计时或保证通过；要由独立CODE与root GO明确批准。
父级22秒检查不能中断阻塞fsync/read，外部caller仍须记录实际outer退出和完整墙钟。
inner、target/drain、caller三个时间口径分别报告，不当作性能或容量结果。

父级所有目标/native/bootstrap/taskset/timeout FD1/2 共享32KiB，预留512 trailer；先扣后写，
短写/溢出sticky UNKNOWN125，不截后PASS。capsule/control逻辑8MiB与SQL DB边界分开。
每文件 `RLIMIT_FSIZE=4MiB`，20个固定DB/sidecar名（5库各主文件、-wal、-shm、-journal）
形成源码约束下80MiB逻辑上界。原发布器的`.uta-create-*`只允许对应库父目录、私有、空，
并仅删除自己的空发布临时名。SQLite连接前、fixture后、每库重开后及最终发布前做元数据
观察，记录实际文件数/字节、峰值观察数/字节及闭合后摘要。它不是连续native写监控、
总容量硬quota、物理块分配或敌意native保证。每文件上限是实际native写限制，不冒称总额
硬隔离；异常文件/大小/模式、I/O或FSIZE异常、剩余临时名、超时、泄漏均不能PASS。

## 部署、失败与回滚

当前不部署、不执行SQL，不接REST/worker/default route。未来只有独立CODE复审闭合后，
root另行给出完整C/plan SHA/新目录/唯一argv才能运行首轮。caller另建
`<OUTPUT>-host-once01`，O_EXCL/0700记录literal argv、意图、实际Popen wait/reap/exit、
单调起止和完整launcher stdout/stderr。PASS还需双方EOF、原BEGIN/END、及时TAIL、
3方法和5库oracle均完整、源前后相同、实际runtime/CPU、调用者观察的outer exit0。
END或inner不能证明未来outer成功退出。

首次FAIL/UNKNOWN停止保第一原件，不自动重试、查询修复或补跑；OS结束own target后由OS
释放其FD，但UNKNOWN不能用来宣称账务通过。所有DB/WAL/SHM、详细oracle/resources与
完整source capsule保留私有，独立RAW组只读复核须在相应授权边界内。公开交付仅经审的
explicit raw allowlist、有限投影及长度/SHA清单；不导出完整DB或capsule。回滚停止本入口，
保留首轮证据，不删除库/sidecar、不更改旧authority、不得热换金融代码。

产品仍仅本地单authority/USD/Cross/乘数1线性永续，原拒绝规则不扩大。现货、借贷本金、
调度/DUE未完成义务、opsAuth/审批/托管、managed fencing/HA、多authority、故障与容量、
金融独立验证和真实资金启用仍OPEN。第一手来源/日期仅沿用原规则矩阵的有限验证摘述，
本计划不新增或冒称交易所资金费精度、边界时刻、舍入或保险政策的外部证据。
