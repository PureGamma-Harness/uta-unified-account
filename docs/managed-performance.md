# Managed process inbox 接纳诊断

`benchmarks/run_managed_benchmark.py` 是最多 10 秒的独立开放环诊断工具。它使用真实 DurableProcessRouter、spawn 子 PID、PID-bound token、持久 SQL fencing、required 决策审计及默认后台风险监督/撮合。没有复制、网络撮合或真实资金；不能称为 30 分钟稳定容量或 10,000/s 验收。

默认 100 个合成账户、2 分片/独立 worker PID、2 个 dispatcher，计划 20/s 持续 10 秒。主命令进程及其线程/子进程默认只绑定两个可用 CPU，主机整体配额另外记录；现有 24 小时作业和观察器继续共享同一主机，不被暂停或修改。每账户初始 USD100,000,000，所有单均为正向买单、成功订单持续 OPEN，保证金没有通过即时撤单或虚构成交释放。

## 接纳口径

每个计划到达使用唯一 command_id 和 order_id。原始 JSONL 记录计划、实际发出、开始入队、ACK、调用结束和 terminal 观察时间，包含完整 terminal result/error。`ack=durably_queued` 仅证明本地 WAL/FULL inbox 持久写入，不代表金融成功。只有只读事务观察到 `SUCCEEDED` 才计入金融成功；存储复开后还必须对应真实订单、持久预占、账户版本和审计记录。首次 ACK 丢失后，原 command_id 查询若返回真实 SUCCEEDED 可以证明该次接纳，但 enqueue technical error 仍单独保留，不能因恢复查询抹掉。

分别报告业务拒绝、控制门/行情拒绝、QUARANTINED 技术终态、durable queue full、本地 outstanding full、未派发期限、结果未知及排空时间。预设每第十笔使用 `.0005` 数量，违反 `.001` 产品步长；它先通过原 inbox 协议，再由实际金融风控产生产品拒绝。其余 `.001@100` 为有效单。拒绝不计成功。P50/P95/P99/P99.9 分别输出全部到达、真实金融成功、仅 enqueue ACK 三组。

collector 使用批量内部只读 SQLite 快照观察持久状态，以减少逐 CID 查询本身的额外事务。它是工程观测入口，不是客户 REST/WebSocket 性能。时间从原计划到达到 COMMIT 后的 terminal 观察，包含排队和 polling 上界；数据库 completed_at 是事务内写入时间，不能当成精确 COMMIT 时刻。

到达窗口结束继续派发已接纳的本地工作和观察 terminal，直到 drain deadline。未开始派发的本地工作不在 deadline 后补发；正在执行的入队调用等返回。所有原始结果保留。关闭 worker 期间刚确认的 SUCCEEDED 在最终复开中单列为 unobserved successes，不补进测量吞吐；关闭本身不伪装为排空。原始 PENDING 与其 ID 留在本地存储供调查。CLI 成功只表示工具完成和对账通过，容量/生产字段始终 false。

## 行情与控制开销

每 2 秒生成实际当前 UTC、新版本的合成 tick，标记价固定 100，IM .1/MM .05，调用真实受控 `publish_market`、等待 fanout，再显式 `set_kill_switch(False)`。每个新 tick 都归档完整 payload，不修改旧观察时间。新价格年龄上限 5 秒。publish 关闭全局 gate，因此期间的安全拒绝和控制等待是实际结果，单独保留；不绕过 barrier 来提高数字。

发布失败保留该实际 snapshot 和错误，不用刷新它的时间或假装重新激活。初始化、所有 publication、真实子 PID/token generation、队列历史、polling 异常和阶段 telemetry 均保留。后台默认 interval .1、account_batch25、matches_per_symbol10，没有关闭循环或改内存成功。全买单没有可匹配卖方，最终若有 fills/positions 反而使工具对账失败。

## 剖析与复开核对

`--profile` 只包装 worker 生命周期入口为 cProfile，每个真正独立 Python PID 保存原始 `.prof` 和文本统计，不替换金融、审计、SQL guard 函数。在 CPython3.12 同一解释器不能并发启用两个 cProfile owner，所以父进程只剖析 dispatcher0；所有 dispatcher 均有完整原始入队墙钟时间。首次工具自检遇到这项解释器限制后已修正；不把空 profile 当证据。

统计列出队列处理、金融风险、JSON/账务、writer_fence、decision_audit、storage 及 background 的函数调用次数、内部时间和累计时间。累计时间存在嵌套，不能相加为 CPU 百分比；profile 包含初始化、等待和停止，且有探针自身开销。首轮只用于识别瓶颈，后续优化必须同配置多轮、保留无 profile 对照，不与不同源码/硬件的历史 744/s 等数字拼接。

worker 真正退出后，独立 RO 重新打开每片：

- 原 CID canonical payload 与原 account/order/数量/价格一致；已 ACK 的入队历史不能消失。
- SUCCEEDED 与唯一 OPEN 订单、ORDER_ACCEPTED 事件、admission_decision_id 一一对应；REJECTED/PENDING/QUARANTINED 不得具有订单金融效果。
- 每笔预占手算 `.001*100*.1 + ceil(.001*100*.0004, USD1e-8) = .01004 USD`，逐账户求和；账户版本为初始资金入账版本1加实际接纳数。
- USD 现金不变，所有已接受订单保持预占，没有 fills/positions。required schema3、审计 identity 和 pre/post version 校验。
- 不调用生产 ledger 计算函数，独立按整数 posting 重算逐币平衡、事件 fingerprint/hash 链和余额投影；同时做 integrity_check、foreign_key_check 和 WAL 检查。

SQLite financial/metadata busy timeout 保留实际服务默认 10 秒，没有为探针改短。响应期限默认 1 秒，与 busy timeout/control timeout 独立。durability 是单主机本地 WAL/FULL；不提供复制确认或 AZ 容灾证明。

## 复跑、部署与回滚

```bash
python -m unittest discover -s tests -p 'test_managed_benchmark.py' -v
python benchmarks/run_managed_benchmark.py --output /tmp/uta-managed-profile-unique --duration 10 --rate 20 --accounts 100 --shards 2 --cpu-limit 2 --profile
```

每次使用新的合成 authority，保留实际源码 SHA、全部 Python 源 hash、环境、原始到达/telemetry gzip、完整控制结果、原始 profiles、manifest 和重开核对。长稳生产者 887 与只读观察器不变 source、不变 PID、不改其资金库或历史起点。测试控制台退出后必须核验这些已运行作业的 heartbeat，没有将其饥饿作为提速手段。

部署仅需固定 checkout 和标准库；回滚是停止本次独立探针并保留其 authority/原 ID，不能删除 PENDING 后宣称没有未完成。工具不升级既有 authority、不改变 lease 控制 schema、不改经济 layout 或生产默认。运行中源码必须保持不可变；没有达到正确性与持续容量门槛之前，生产批准为 false。

## 887 长稳起止锚的只读分析

实际 job.started_ns 为 1794864973820942405，首 session.started_ns 为 1794864973825199889，两者差 4,256,484ns（4.256484ms）。单调 active 起点在 session INSERT 前，和原 wall deadline 存在初始化毫秒差。原实现到 wall deadline 后还执行 worker/feed join、完整只读最终验证，最终 heartbeat 将这些真实执行时间计入 active，通常会覆盖几毫秒差，但没有保证。

因此理论上可能出现 wall 已满 86400 秒、strict active 略少而 false-negative。当前 source/job 一字未改，也不能加 epsilon、回填暂停或改 start 来硬判通过；若实际终态短缺，应原样未通过。下一版可统一实际单调起点/截止，并分开报告生成器、持续 feed、排空和终检的运行时间；新版本需要新候选，不套用本次历史计时。


## 首个固定源码的真实诊断结果

测量源码 `7a06c0532ba510653b1feccd7e80030d3cb19f8a`（62f4336 + dacf3fe 的等价本地 cherry 0b7d2ac + 工具），已推到可检出分支：<https://github.com/PureGamma-Harness/uta-unified-account/tree/experiment/managed-inbox-profile-20261116>。实际驱动运行 UTC 2026-11-16 22:48:59.167507–22:49:11.000714，总 11.833067 秒；真正计划到达窗口 10 秒，含 terminal 观察排空为 10.101954 秒。
CPU 为 AMD EPYC 9V74，可见 benchmark affinity **2**，宿主 cgroup 配额为4 CPU/16GiB；Python3.12.14、SQLite3.53.1、overlay本地文件系统。两个真实 worker PID 为18157/18158、各 generation1；PID与lease owner相同、required audit ready。其他协作组暂停新的短测试，887低频长稳与8784只读观察器继续同机，因此不声称独占硬件。
| 到达与终态 | 实际数量 |
|---|---:|
| 原计划到达 | 200 |
| durable enqueue ACK | 200 |
| 金融 SUCCEEDED / 持久 OPEN 订单 | 171 |
| 产品规则 REJECTED | 18 |
| 发布门关闭 router_halted REJECTED | 11 |
| QUARANTINED / deadline unknown / 未完成 | 0 / 0 / 0 |
| worker技术重试 attempts | 0 |
| 观察器轮询技术错误 | **1** |
| 成功回执超过1秒 | 1 |
金融完成速率是 **16.927418/s**，另列 ACK19.798149/s。20/s是设定到达率，负载没有饱和，不能把16.93解释成最大容量。预设20个非法数量中有2个先被发布门拒绝，故产品拒绝是18而非20；业务策略检查顺序及安全拒绝均原样保留。全部171成功原CID、订单、ORDER_ACCEPTED、账户版本、手算预占、required decision和逐币ledger/hash链复开核对通过；未发现未观察到的额外成功，pending0，无 fills/positions。
| 延迟（毫秒，计划到达起点） | P50 | P95 | P99 | P99.9 |
|---|---:|---:|---:|---:|
| 全部200次 | 118.061 | 291.123 | 393.309 | 1196.361 |
| 171次金融成功 | 125.107 | 294.048 | 686.302 | 1196.361 |
| 仅ACK，非金融成功 | 15.336 | 143.753 | 240.529 | 1155.233 |

最慢 seq8 实际端到端1195.702ms，其中本地开始前 .151ms、enqueue 调用 **1154.504ms**、ACK至金融terminal观察41.048ms。不能归因于纯风险计算；锁/元数据写入等待需下一次更细的阶段证据，当前父profile不支持可靠分摊。
4次真实新 tick 的完整 publication+activation 耗时609.692/471.790/779.054/600.254ms，全部完成并重新激活。每片观测的 pending峰值为4/3，无本地/持久queue full。此开关过程使11条原命令得到明确安全拒绝，不进行改写或重报成功。
### 独立 worker PID 的剖析

| 函数 | worker0 调用数 / 累计秒 | worker1 调用数 / 累计秒 |
|---|---:|---:|
| worker生命周期 | 1 / 10.756409 | 1 / 10.730257 |
| 真实background | 36 / 6.474565 | 40 / 6.010610 |
| 账户监督 | 760 / 5.838574 | 611 / 5.224251 |
| _admit_order | 93 / 0.387944 | 96 / 0.411761 |
| _risk | 922 / 0.767319 | 791 / 0.717859 |
| _verify_data_guards | 3130 / 1.791906 | 2751 / 1.632122 |
| _verify_control_schema | 2226 / 0.661278 | 1988 / 0.606006 |
| audit.validate | 1298 / 0.290346 | 1194 / 0.298254 |
| audit.record | 81 / 0.033741 | 90 / 0.034003 |

这些是单PID完整生命周期的累计墙钟，包含初始化、等待和停止，函数嵌套不能相加为CPU百分比。后台1371次账户监督对应大量重复风险/事务/guard校验；与171条有效金融接纳相比，先研究有正确性约束的后台调度与事务密度，比预设计算核瓶颈更有依据。随后可评估durable批量入队/有界金融批事务，但必须保留FIFO、required审计、SQL fencing、事务末新鲜度与控制门响应。没有关闭当前后台来凑性能，也没有跨事务盲缓存guard。
父 dispatcher0 的 .prof **实际混入其他父线程函数**，且5项 internal_seconds>cumulative_seconds。原始数据完整保留并标记为诊断限制，不能据它计算精确入队/guard阶段占比。两个独立worker PID .prof该异常均为0；上述结论只使用这两份profile及每条原始请求墙钟时间。CPython3.12 initial多profiler自检失败也保留为明确的开发转录记录，不冒充原始性能日志。
### 原样保留的I/O事件与共机证据

在到达起点后 .725336s，RO polling曾出现一次 **SQLITE_IOERR_SHORT_READ(522)**。工具保留原错误并重试，此后全部terminal和复开数据一致。当前证据没有该次SQLite FD/syscall、WAL身份和受影响分片，不能断言根因无害或已修复，也不能把这轮称为无技术错误。后续可记录连接/WAL生命周期与分片上下文复现，不能事后删除此行。
887原正式作业与8784观察器未重启或改源码。探针周围实际持久 heartbeat 为22:48:57.764591、22:49:02.815317、22:49:07.886762、22:49:12.934797 UTC，约5.05秒间隔，记录的market age为 .506–.555秒；前后原PID出生匹配、无观察告警。它们是该窗口观测，不是所有资源情况下无干扰的证明。原24小时稳定性仍待真实截止和最终审计。
### 证据与后续门槛

原始证据 `benchmarks/results/20261116-managed-inbox-profile/raw/` 包含200条gzip到达、每片telemetry、完整fresh tick/control回执、environment、独立PID及父profile原文件/文本、manifest和实际命令。`analysis.json` 保存剖析限制、子PID函数计数和原始尾部拆解，cohost文件保留实际长稳检查。原SQL数据留在 `/tmp/uta-managed-profile-20261116-first/authority`，不提交Git。
`startup_seconds_excluded=.458328s` 是spawn/初次publication/activation区间，未单独测量更早的离线开户资金setup；两者均在计划到达起点之前。wrapper总时间、arrival-window和原始setup来源均保留，不能把该字段称为全部初始化时长。关闭耗时 .024675s另外报告。
四项原冻结工具自检通过，集成后新增归档测试核验200唯一到达、全部摘要、实际171/18/11分类、I/O522和profile限制。无profile对照、重复配对、更高到达率、持续半小时、复制与撮合容量尚未完成；capacity_10000_per_s_passed和production_approved均为false。下一轮先固定同一新source做受控改前改后，不把当前单次低速instrumented观察当作收益百分比。

## 2026-11-17 补充：已复现的应用层 POSIX 锁缺陷

首轮含 SQLITE_IOERR_SHORT_READ(522)，即使最终只读对账通过，也不能标为稳定性绿或并发安全验收通过。其原始200/171/18/11结果、原profile及所有26个既有证据文件均不改写；这次只追加来源和归因边界，完整说明见 [ROOT-CAUSE-NOTICE.md](../benchmarks/results/20261116-managed-inbox-profile/ROOT-CAUSE-NOTICE.md)。当前历史候选仍为 **NO-GO**。

SQLite 官方 [How To Corrupt An SQLite Database File §2.2](https://sqlite.org/howtocorrupt.html#posix_close_bug) 明确说明：同一进程中对同一数据库文件执行 `close()`，会取消该进程所有线程/描述符持有的该文件 POSIX advisory locks。绕过 SQLite 打开再关闭已发布的数据库文件，即使只是辨识文件类型，也可能破坏其他活动 SQLite 连接的锁。SQLite 3.51.0 以后新增的多进程 WAL 防御不是完整替代；这不能靠降低完整性检查或简单更换 SQLite 版本解决。

测量源码7a06的 `Database._private_file` 和 `_BoundShardDatabase._private_file` 与独立红基线57d776c的两个同名方法，归一化 AST 完全相同，均存在直接 `os.open/fstat/close` 已发布数据库 inode 的路径。独立组用真实 SQLite 活跃事务和另一个 PID 的 kernel 锁探测复现：第二线程的文件检查使外部排他锁从被阻塞变为可取得，而原连接仍报告 in_transaction。修复路径和只读 existing-only 补强后的有界测试在 SQLite3.53.1、3.46.1 上通过；原红态及初次修复剩余失败也完整保留。这些是锁协议正确性证据，不是新的吞吐结果。

原始第一手 HTML 的 SHA256 为 `e00709e3f37e95332d8e6df243510665e9cab1d7938d4fd85cbf5f47648a50bf`，压缩原字节、§2.2文本摘录、独立报告和实现说明均归档在 `posix-close-review/`。旧26文件的原manifest另存 `manifest-before-posix-review.json`，逐文件复核均未改变。

应用层锁破坏机制已经独立确认，但首轮单个522事件没有对应的分片、FD/syscall和WAL inode轨迹，因此其精确事件因果仍不得冒称已完成取证。最终 RO 平衡、订单和审计匹配只能确认终态事实，不能反证运行期间从未丢锁。修复后的性能、恢复和稳定性仍需新的冻结提交与同配置复测；本轮没有启动新负载，也没有更改正在运行的887/观察器源码、数据库或任何历史开始时间。
