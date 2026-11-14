# 分组持久准入：交付与验收记录

本轮在 M1 与分片实验之上优化单个权威交易库的订单/撤单提交，交付可选的有界 group commit、真实 HTTP 集成、独立故障与金融不变量验证，以及真实双侧清算测量工具。它没有把分片路由器和批提交器自动组合，也没有扩展产品许可。**生产、持续万笔、HA 和真实资金门槛继续 BLOCKED。**

## 候选、兼容性与分工

最终验收代码为 `d0bb68261f1e165307ee1d223f60cf14e98e57ea`，包含远端 `main@02549e5` 的文档更新、已有研究能力、此前两个交付分支及跨 Python 版本修复。后续本报告与证据归档提交不改变本次已验运行模块，内容 SHA-256 可逐项比较。首次集成的 `4794142` / 503 项结果另行保留，不冒充最终版本。

实现、API、故障、独立金融验证、准入性能和真实清算负载六个并行工作流分别提交代码，由集成负责人归并。此前的账户/账本、风险、迁移和分片交付继续保留。独立组的验证与否决结论见 [金融验证](grouped-validation.md) 和 [故障验证](grouped-faults.md)；这是工程 Agent 审查，未冒充具名金融负责人或外部审计签字。

未新增数据库 schema 或更改保证金公式。默认仍逐命令同步提交，`--batch-admission` 显式启用；原订单/撤单 URL、账户权限、十进制字符串和业务 ID 契约保持兼容。支持范围仍为现有合成 Cross、已实现的限价与累计 reduce-only；市场单、条件单、改单、多腿原子交易、Isolated/生产 PM、USDT/USDC 实际规则及其他未实现产品仍拒绝，不能用参数开启。现货、借贷和其他资金操作继续走原权威事务，并不进入本次批队列。

## 实现与正确性门槛

- 一个有界 FIFO writer 将多个独立命令置于同一 `BEGIN IMMEDIATE` / WAL / FULL 事务；逐命令 savepoint、账户版本与持久预占继续复用原金融路径。组不是客户多订单原子请求。
- 只有显式声明的业务错误可以隔离；SQL、账本/配置损坏、未知 409 和程序异常停止整组。COMMIT 返回前不投递该组成功或排队业务拒绝。
- 有新订单时在 COMMIT 前最后应用检查点复核行情；已过期则整组回滚。纯撤单/无写入幂等重试保持降级能力；不保证之后任意 OS 暂停和 fsync 时长。
- 撤单有额外有界保留槽，保持 FIFO。排队超时只有在取消 Future 成功时才可报告本次未执行；已运行超时报告结果未知，原 ID 查询/重试收敛。
- 启停、readiness、队列指标和 SIGTERM 排空接入真实 HTTP。回调重入、同 worker 等待尚未发布的回执及异常不能悄然丢失其他已提交回执。

首次集成 **503 项通过，0 failures/errors/skips，37.35 秒**，比当时分片候选增加 75 项：引擎 19、独立故障 14、独立金融不变量 12、真实 HTTP/CLI 12、准入工具 9、实际清算工具 9。后续补充 3 项公共游标兼容回归，最终 **506 项**在本地 Python 3.10 与 3.12、远端 Python 3.10–3.13 均通过。完整记录包含每条测试、源码哈希、解释器/SQLite 版本和执行时间：

- 最终 [Python 3.10 结果](../evidence/runs/grouped-portability/python310-final/summary.json) / [逐项输出](../evidence/runs/grouped-portability/python310-final/unittest.txt) 与 [Python 3.12 结果](../evidence/runs/grouped-portability/python312-final/summary.json) / [逐项输出](../evidence/runs/grouped-portability/python312-final/unittest.txt)：506 项各通过，40.23 / 39.01 秒，无失败或跳过。
- [GitHub CI 矩阵原始元数据及选取日志](../evidence/runs/grouped-portability/github-ci.json)：PR #3 在 `d0bb682` 上的四个版本全部完成成功；[实际运行](https://github.com/PureGamma-Harness/uta-unified-account/actions/runs/43649548467)涵盖编译、参考模型、真实合成纵向验收和源码目录之外的 wheel 安装验收。PR #1 / #2 的回补版本各 405 / 431 项也在四版本矩阵全过。
- 首次 [503 项结果](../evidence/runs/grouped-final/summary.json) 与 [历史逐项输出](../evidence/runs/grouped-final/unittest.txt)，以及 [测试夹具清理后的中间结果](../evidence/runs/grouped-portability/summary.json)均保留，不能替代上述最终候选。
- [独立有界组提交模型](../evidence/runs/grouped-final/group-model.json)：85 状态、166 转换；四个故意不安全变体均找到反例。另复跑已有预占/双侧结算模型。枚举不证明实现等价、任意规模、硬件耐久性或活性。
- [最终安装记录](../evidence/runs/grouped-portability/final-package.json)：在源码目录之外安装 wheel，37 个运行模块/dashboard 文件与最终源码全部匹配，复跑完整合成纵向验收、研究 scenario、CLI 及空游标行为。最终 wheel SHA-256 为 `bc39659e83723a762991a54c0838faf838026c644a3f1dbbcae1806269b721d3`；这是 d0bb682 评审构建，不是稳定发行。首次安装与模型执行历史见 [原记录](../evidence/runs/grouped-final/package-and-models.json)。
- [规则追溯矩阵](../evidence/rules.csv) 新增 `GROUP-001..006`，明确这些是本系统本地政策，没有声称交易所内部行为已经验证。

发现并修复的实际问题包括：固化风险参数损坏被误归为普通 409、组处理跨越行情有效期仍可接纳、满新单队列挤掉撤单，以及 Future 回调自等待。独立测试保留原预期，没有用放宽断言换通过。

跨版本 CI 另暴露两项真实失败，原错误日志在 [兼容性证据](../evidence/runs/grouped-portability/)保留：Python 3.13 标准库对 `init=False` 字段的 `dataclasses.replace` 改抛 TypeError，测试接受明确的两种标准库拒绝类型并继续断言 PM 不可启用；Python 3.10 严格 `parse_qsl` 拒绝空查询，API 现在只为空查询显式使用 `(after=0, limit=100)`，非空的 19 类非法查询仍拒绝，原 HTTP 的 200/501 预期不变。这两项通用修复已回补前两个 PR。

同时为 9 个测试文件中的 19 个 SQLite 观察连接增加显式关闭，保留原事务上下文的提交/回滚语义。生产连接拥有者已有 finally.close，未把延迟 GC 警告的触发行误认成生产创建位置。最终候选 3.13 CI 没有 unclosed database 警告；前两个分支仅回补兼容修复，其旧夹具警告仍在所存日志保留，不代表已经修复或验证整个生产环境的所有资源问题。

## 性能证据与未通过项

最终配对使用不可变测量源码 `c527face784c420202d64b63dd2f8c6f46ab33c9`。其最终 AdmissionBatcher 内容与当前候选一致；完整运行模块哈希及命令保存在 raw 中。单进程/单库、100 账户、4 dispatcher、共享 outstanding 上界 1024、SQLite busy timeout 2s，两者均计划 5000/s、持续 5 秒。成功订单始终 OPEN 并保留全部预占，不通过即时撤单提高计数。

| 模式 | 唯一持久接纳 | 含排空 ack/s | 过载 | 未知 | 全部响应 P99 / P99.9 | 成功接纳 P99 / P99.9 |
| --- | ---: | ---: | ---: | ---: | --- | --- |
| 同步 | 3503 | 463.76 | 21496 | 1 | 2327.87 / 2377.24ms | 2370.13 / 3617.31ms |
| batch64 | 4939 | 744.11 | 20061 | 0 | 1807.74 / 1836.88ms | 1833.22 / 1840.56ms |

全部响应包含快速过载拒绝，不能用其尾延迟替代成功接纳尾延迟。两种口径都包含从计划到达开始的排队时间。

该单次配对 ack/s 提高约 **60.5%**；共享主机、顺序短样本不足以证明稳定增益。batch64 的 78 次外层提交承载 4939 个唯一命令，仍有 3473 个成功超过 1000ms 软期限。同步未知保留真实 `SQLITE_BUSY`，重开未见该 ID；不能抹掉技术失败或改写为业务拒绝。每个成功 ID、事件、账户版本和独立手算 `.01004 USD/单` 占用均在重开后核对。

完整 [准入测量口径、raw 和 profile](grouped-performance.md) 还包含五种批大小探索。该路径不是此前 router 的“接单+撤单”口径，不能把 744 与 549 直接相除。profile 提示下一瓶颈为已有预占的重复精确重估与行情解析；未在本轮引入未经差分验证的风险缓存。

[真实清算探针](matched-liquidation-performance.md) 从真实对手开仓开始，20 个账户完成 **40 笔唯一清算成交、80 条结算腿**，逐笔匹配资金和仓位，重开后余额均为 93.16 USD、仓位为零。无流动性探针保留 4 个未完成账户、360 单位残余风险，无虚构成交。38.92 笔/秒是受任务泵限流的短诊断，不是最大清算容量；两类探针都没有通过 10,000/s、1800 秒门槛。

## 部署、回退与故障处理

按 [部署恢复手册](operations.md) 从审查过的 commit 构建 wheel，核对 SHA-256；同名 `0.2.0` 评审构建须靠该摘要区分，尚未发布稳定发行版。先在合成环境使用原配置和同一个本地权威库；评估批提交时增加：

```sh
--batch-admission --admission-batch-size 32 --admission-delay-ms 2 \
--admission-queue-capacity 1024 --admission-cancel-reserve 16 --admission-timeout 2
```

批长 64 是本次测量参数，没有据单次结果修改默认值。监控 admission 队列/运行数/技术失败/过载、行情年龄、磁盘、最老未处理命令和端到端尾延迟。非 daemon writer 必须排空；服务管理器的停止期限须覆盖已接收 HTTP 等待、SQLite 锁等待和剩余队列的实测时间，示例 30s 不能作为所有队列/60s HTTP 配置的通用上限。

回退前暂停新增风险，停止接收请求，排空 HTTP 与队列、停止其他写者，对已确认及结果未知 ID 逐笔核对，并做一致备份。关闭 `--batch-admission` 可回到相同 schema 的同步路径；需要代码回退时使用已审查的前一分支并保留现有完整数据库，不恢复一份遗漏新成交的旧快照。禁止仅因超时换新业务 ID 或删预占。

强杀恢复以数据库 COMMIT 为准：未 COMMIT 的整组由 SQLite 回滚；已经 COMMIT 但响应丢失的命令用原 ID 恢复。尚在内存排队、未收到持久接纳回执的命令可能未执行，应在旧写者确认失效后原 ID 重试；队列本身不是持久任务日志。仅 WAL/FULL 未承诺跨 AZ 复制或机器级掉电 RPO。

多节点租约/fencing、跨片撮合结算、复制与恢复水位、正式行情扇出、30 分钟混合/热点/极端行情长稳、完整权限签名和金融模型校准继续按独立关卡推进。此里程碑允许合成环境继续工程审查，**不批准真实资金启用**。
