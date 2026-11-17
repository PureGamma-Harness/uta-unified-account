# Managed inbox 的持久金融批处理设计（未实现）

本提案基于 `21aa6510bafcce8383fc24ac2c35e671074b9baf`，独立分支
`design/durable-batches`。交付物只有本设计、逐入口追踪、独立有限状态枚举及其结果；
没有修改 runtime、schema、worker 配置，没有运行 benchmark、profile 或重压。
真实 runtime 实现与后续负载仍待单独授权。

结论是**值得验证 managed inbox 的真实 financial batch，但尚无性能收益结论**。
每批必须在同一个 router SH gate 内完成一次真正的本地 financial Wtxn，原 CID 对应的
效果、预占、既有要求的 audit/event 与 terminal 共用该 COMMIT。不能调用一个已有内存
batcher 就宣称 durable worker 已批处理，也不能因聚合而省略 SQL fence、full risk 或审计。

## 证据与可省成本的边界

唯一性能依据为修复后源码 `7200097ce9f92fa678907bee9a99933f60d65bc3` 的
[corrected raw evidence](../benchmarks/results/20261117-managed-corrected-7200097/README.md)，
尤其是实际子 PID 的
[worker0 profile](../benchmarks/results/20261117-managed-corrected-7200097/raw/P1/profiles/worker-0-pid-57001.txt)
和 [worker1 profile](../benchmarks/results/20261117-managed-corrected-7200097/raw/P1/profiles/worker-1-pid-57002.txt)。
完整 caller 边在同目录 `.prof`，hash 在 P1 `manifest.json`；文本只列 top45，表内额外 caller
拆分由二进制 profile 读取。源码行号以本设计基线为准，profile 自带行号属于 `7200097`。
不使用旧含 POSIX 锁问题的 `7a` profile 推导改进幅度。

| 观察项 | worker0 PID 57001 | worker1 PID 57002 | 对设计的含义 |
| --- | ---: | ---: | --- |
| `_connect` 次数 / cum 秒 | 1037 / 1.021442 | 959 / .954067 | 各类事务都重新连接；金融批只减少自己的部分 |
| COMMIT 次数 / self 秒 | 1037 / 1.199231 | 959 / 1.174614 | 1996 不是 161 笔金融各自独占的 COMMIT |
| transaction close self 秒 | .584437 | .522932 | 连接生命周期有成本，但此表无法按金融命令精确归属 |
| `before_commit` 次数 / cum 秒 | 1037 / 1.730493 | 959 / 1.615702 | 可随真实事务数摊薄，逻辑必须保留 |
| `_verify_data_guards` 次数 / cum 秒 | 2919 / 1.725316 | 2647 / 1.631021 | 嵌套于 guard/commit，不能叠加成收益 |
| `_verify_control_schema` 次数 / cum 秒 | 2068 / .642875 | 1912 / .633955 | 同上；不是批内关闭验证的理由 |
| `_TransactionGuard.__init__` cum 秒 | 1.123 | 1.118 | 包含下层保护工作 |
| `_guard_sql` 次数 / cum 秒 | 273951 / .972000 | 248383 / .872411 | 每条写 SQL 的 fence 仍需执行 |
| QueueStore `process_one` 次数 / cum 秒 | 187 / 1.877135 | 213 / 2.070623 | 包括空轮询、连接、保护、COMMIT；不是纯排队 CPU |
| `supervise_account` 次数 / cum 秒 | 711 / 5.847457 | 586 / 5.031561 | 背景事务密度的主要来源，金融 inbox batch 不会自动消除 |
| `_risk` 次数 / cum 秒 | 861 / .753060 | 758 / .695967 | 1297/1619 次来自 supervisor，322 次来自新接纳 |
| `calculate_cross_risk` cum 秒 | .224744 | .199942 | 保留完整计算，不能只算一次批前 risk |
| `DecisionAudit.market_ref` 次数 / cum 秒 | 1132 / .593758 | 1050 / .548734 | 元数据检查频繁，不能等同于生成 audit 的成本 |
| `DecisionAudit.validate` 次数 / cum 秒 | 1212 / .279658 | 1141 / .261997 | required audit 的校验仍需保留 |
| 实际 `audit.record` 次数 / cum 秒 | 75 / .039613 | 86 / .036685 | 合计 161 个金融成功对应的实际新决策记录 |

`_connect` 直接 caller 下的 PRAGMA execute 为 4134/3822 次，self .865928/.815898 秒。
QueueStore `process_one` 直接 execute 为 634/669 次、cum .059989/.049747 秒；
`durable_commands.py` 模块 Python self 总计仅 .011214/.012989 秒。
因此不能把队列入口约四秒累计时间称为调度本身的成本。`_market` 的 1057/964 次调用中，
supervisor 就有 1297 次；`run_background_once` 的 cum 为 6.560713/5.868 秒。
事务保护、审计元数据、计算、队列与背景路径应分别计数，不能把所有成本写成 JSON 序列化。

profile 覆盖启动、等待和关闭，cum 相互包含，不能相加为 CPU 百分比。父 dispatcher profile
有 self 大于 cum 的已知计时异常，只用于识别入口活动；两个独立 worker profile 没有该异常。
总 COMMIT 不能除以金融成功数后叫作“每笔金融 COMMIT 密度”。

P1 是 200 arrivals：161 金融成功、18 产品拒绝、21 控制/市场拒绝；采样 pending 峰值每片
仅 4，不能假设较大批的填充率。B1/B2/B3 在 20/s 下金融成功为 163/166/171。
S1 在 100/s 下为 508 金融成功、58 产品拒绝、321 控制/市场拒绝、113 local full；
`bench:684` 的 `attempts=1` 内部技术 retry 必须保留，不能因最终安全拒绝而消掉。
这些是短探针，不是撮合吞吐或 24h 连续性验收；当前稳定性/生产仍 NO-GO。

## 当前逐入口追踪

下面的引用均指 `21aa651`，没有把其他入口的 batching 当作 managed 现状。

| 入口 | 当前调用链和事务事实 |
| --- | --- |
| HTTP NEW | [durable_gateway.py:271](../uta/durable_gateway.py#L271) → `DurableCommandAPI.call` :183 → `_RouterProducer.submit_order` :93 → [durable_process.py:913](../uta/durable_process.py#L913) → `QueueStore.enqueue_submit` :217 |
| HTTP CANCEL | gateway :282 → `_RouterProducer.cancel_order` :96 → durable_process :917 → QueueStore :221 |
| HTTP REPAY | gateway :288 → `_RouterProducer.repay` :99 → durable_process :920 → QueueStore :230 |
| 持久 enqueue | [durable_commands.py:233](../uta/durable_commands.py#L233) 校验 canonical，:238–242 对同 CID 比较 kind/account/payload；单独 inbox metadata COMMIT 后返回 queued ACK |
| managed 执行入口 | [durable_process.py:459](../uta/durable_process.py#L459) → [ShardWorkerView.process_one:839](../uta/sharding.py#L839) → [QueueStore.process_one:307](../uta/durable_commands.py#L307) → :316 每次一个 `exchange._transaction()` |
| NEW 效果 | QueueStore :340–343 → [ExchangeService._admit_order:752](../uta/service.py#L752)，同连接内 live-order reserve、完整 risk、reduce-only 累计与 projected risk、audit 与 event |
| CANCEL 效果 | QueueStore :344–345 → [service._cancel_order:842](../uta/service.py#L842)，同连接更新订单/版本与 `ORDER_CANCELLED` event；当前没有独立 decision `audit.record` |
| REPAY 效果 | QueueStore :348–352 → [CreditService._repay:361](../uta/credit.py#L361)，原 CID 是信用幂等键；interest-first postings、debt、version、credit receipt、event 同连接 |
| terminal | QueueStore :335–365：command savepoint；白名单业务拒绝 rollback savepoint，再更新 REJECTED；成功为 SUCCEEDED；同一 outer COMMIT，technical exception 撤销整个事务 |
| post-COMMIT 不确定 | [durable_process.py:461](../uta/durable_process.py#L461)–476 现在只查单个原 CID，再决定是否 `record_failure`；不能原样套到多 CID 批 |
| retry/quarantine | QueueStore :373–400 再读 terminal，已 terminal 不改写；技术 quarantine 没有接纳订单结果 |

`ShardWorkerView.process_one` 在同一个 SH flock 内读 router state、funding claims，并持锁到
QueueStore 的 COMMIT 返回（sharding :839–846）。SH/EX 锁实现为 :246–271。
每 command guard 当前在 :801–805 重做 reconcile；NEW 在 :806–809 检查 global halt、
publication barrier、本地 market digest/version。控制命令在 :810–829 校验当前 transition
拥有的 CID/target，旧控制返回 `control_superseded`。资金 claims 读取必须已经持 gate；
不能持本片 writer 再拿其他 shard writer（:419–425）。

`_BoundShardDatabase.transaction` 校验不可变 shard/layout 身份（sharding :62–80）。
[Database._role_transaction:181](../uta/storage.py#L181) 每次连接 → `BEGIN IMMEDIATE` →
`_TransactionGuard` → `before_commit` → COMMIT，异常 rollback；read 和 inbox 角色权限不同。
inbox 角色不允许 financial/terminal DML（storage :169–172）。
[writer_fence.py:436](../uta/writer_fence.py#L436)–447 的 SQL guard 检查 PID/boot/generation/expiry；
:526–542 在提交前再次验证控制 schema、token/lease/guard 并记录 observed 高水位。
一次 Python 批前检查不能替代这些检查。

当前只有 PUBLISH/HALT 获得执行优先（QueueStore :319–324）。CANCEL/REPAY 只获得
额外入队容量（:257–263），还没有金融执行优先。FIFO 的 earlier-head 查询覆盖**全部更早
PENDING**，包括尚未到 `next_attempt_at` 的行（:321–323）；先过滤 due 再选账户内最早行
会错误跳过 backoff head。

现树没有 `GroupOrderWriter` / `ExchangeService.admit_batch` 符号。相应现有路径是
[AdmissionBatcher._commit_batch:237](../uta/admission.py#L237) 和
[RouterAdmissionBatcher._commit_batch:215](../uta/shard_admission.py#L215) →
[ShardRouter._admit_order_batch:460](../uta/sharding.py#L460)。它们使用内存 Future 队列，
后者没有 durable inbox 原 CID/terminal，不能直接替换 managed 路径。

managed HTTP router adapter 对市场发布/global halt/control-status 返回 unsupported
（gateway :115–124）。operator 的 `DurableProcessRouter.publish_market`（:1262–1307）和
`set_kill_switch`（:1309–1357）通过 EX gate 设置 barrier/确定各片 child CID，释放 EX 后等待
各片回执，再 EX 核对 fanout。它们不是跨片原子 COMMIT。

## 候选协议与事务密度账本

新增入口仅为设计名：`ShardWorkerView.process_batch(store, budget)` 和
`QueueStore.process_batch(exchange, manifest, guard, credit)`。worker 必须明确接到该入口，
其 financial Wtxn 内继续调用 `_admit_order`、`_cancel_order`、`credit._repay` 的 join-transaction
形式，不能调用会自开事务的 public 方法。旧单条入口保留为低占用和故障隔离路径。

为覆盖**进程真的死去、内存原 CID 列表丢失**，本方案选择一个同库持久 attempt manifest：

1. 等待/coalescing 在 gate 和 financial Wtxn 外进行。读取候选只作 hint，不 dequeue、不产生
   接纳；不得依赖该 snapshot 的余额、risk、market 或 due 状态。
2. 由 fenced worker 的**专用 metadata 权限**写入 manifest，包含 shard、layout hash、
   owner token identity、attempt ID、所有原 CID/sequence/account/kind/canonical payload hash。
   membership 不可改写。attempt ID 只作审计/恢复索引，不替换任何业务 CID，不制造一个
   batch-level order ID。新 role/schema/guard 需单独审查，不能扩展 producer inbox 权限。
3. 获得一次 router SH gate，读取当前 state/claims；开启一次实际 financial Wtxn，重新读取
   并校验 manifest 内所有原 CID。已 terminal 的行只返回其 immutable receipt，不再执行；
   非 due、非 eligible head、配置/身份不一致则本批不执行并按实际状态解决 manifest。
4. 共同的 shard 身份/funding reconcile 可在同一 gate+Wtxn 内做一次，前提是证明批内操作
   不改这些依赖；每 command 的 kind/account/barrier 判断仍执行。初版保留已有所有 SQL
   fence、required audit validate、完整风险计算，不引入保护校验缓存。
5. 每个 command 一个 savepoint；效果/预占/其 audit 或 event 写入后，使用原 CID 以
   `WHERE state='PENDING'` 更新 terminal，并断言恰好更新一行。所有 SUCCEEDED、业务
   REJECTED、manifest 的 committed 标记同一次 outer COMMIT。只有 COMMIT 返回后发布
   本批 Future/worker 回执；queued ACK、尝试计数、拒绝均不能算金融成功。
6. 释放 Wtxn 和 SH，再交付结果、让控制和 background 调度推进。禁止持锁收集下一批，
   禁止把 manifest 写成功或 ACK 当成 financial COMMIT。

manifest 是明确的安全/性能取舍：正常批增加一次 metadata COMMIT。它不改变原 enqueue
的 durability ACK，也不把 financial terminal 拆到第二次事务。manifest 完成状态和 financial
terminal 同 financial COMMIT；失败/恢复 disposition 可以后续 metadata 追加，历史身份保留。
该 metadata 也要 fence，旧 owner 不能改新 owner 的恢复结论。

| 对 n 个命令的事务 | 当前单条 | 候选一批 | 不应计入的虚构收益 |
| --- | ---: | ---: | --- |
| 原 enqueue metadata 写事务 | n | n | 不减少 ACK durability |
| dispatch financial Wtxn | n | 1 | 必须真的只开一个，不是批 API 内循环 n 个 COMMIT |
| attempt manifest metadata 写事务 | 0 | 1 | 新增成本，不能藏掉 |
| 已知成功路径 dispatch 写事务合计 | n | 2 | n=2 不能声称总 COMMIT 下降，n>=3 才有摊薄机会 |
| 查询、lease、background、控制 | 原有 | 原有，另有 manifest 读取 | 金融批不自动消除这些事务 |

低占用时继续原单条路径，不为单条多写 manifest。候选资格要求至少 3 个可执行金融命令，
最大批 8、每账户最多 2，最多等待 2ms 的 coalescing、SH 内软预算 5ms；这些仅为后续实验
起点，不是已测配置或 SLA。有限模型故意只用批长 2 来覆盖跨命令交互，不能证明批长 8。
不采用持久 manifest 的替代方案必须给出同等强度的 crash/restart 原 CID membership 恢复；
只说“catch 中还有一个 list”覆盖不了进程消失。

## FIFO、优先、热账户与控制

金融 eligible 集合先对每个 account 查全体 PENDING 的最早 head，再要求 head 已 due。
之后在这些 head 之间优先 CANCEL/REPAY；不能让取消/还款穿过本账户更早 NEW，也不能
跳过 backoff head。处理一个 head 后，才允许在同一 Wtxn 中纳入它的下一条；上一条的
成功或业务拒绝都要先 staged，再执行后继。不同账户之间可以重排，同账户 sequence 必须递增。

需要持久/可重建的 age 与轮转游标：至少每 4 个有生产力批次给一个已 aged 的普通 head
机会；每批每账户最多 2，防止热账户占满。优先不是饥饿许可。时间/数量达到预算就停止
纳入更多 command，已执行 prefix 做最后检查后提交，未执行的原 CID 仍 PENDING；manifest
区分 selected/executed/outcome。若一次 command 已超过预算，不继续下一条；暂停或慢 I/O
可能仍使这一次超过软预算。批不足、poison/backoff、control wait 时使用短事务/单条模式。

PUBLISH/HALT 不混入金融 batch，仍是短单条事务并维持既有 transition CID/barrier 协议。
不等待市场 fanout 时持 SH。每批后主动释放 SH、重新进入调度，coordinator 的 stop/control
通知只作“停止收批/让出 gate”提示，不能作为新的授权或绕过 EX。现有 flock 没有可证明的
公平队列；若后续需要严格控制响应 SLA，必须实现并验证 writer-preference gate 或 ticket
协议。模型只有 SH/EX 排他和让出机会，不证明现实 EX 等待上界。

背景 `run_background_once` 目前在一个 SH 下运行多笔内部事务。本提案不修改它，也不
宣称总 control 响应时间因金融批有界而自动有界。未来必须分别测金融 gate hold 和背景
gate hold；不能用金融批模型替整个 worker 调度背书。

## 各类失败与结果规则

| 情况 | 本地事务规则 | 原 CID 与计数规则 |
| --- | --- | --- |
| 一条成功、另一条业务拒绝 | 白名单 business error `ROLLBACK TO` 该 savepoint；清理 result/new-order 标记，再 staged REJECTED；其他成功继续 | 最终同一 COMMIT 可有成功和拒绝；拒绝不产生预占/financial effect，保留 error terminal |
| savepoint/DDL/guard/审计损坏、非白名单异常 | 整个 Wtxn rollback，禁止拿 savepoint 掩盖 integrity failure | 未提交成功不能发布；integrity 类进入既有 freeze/HALT，无自动豁免 |
| 真正 COMMIT rollback | 全批 staged effect/terminal/manifest committed 标记都没有 | 原 CID 仍 PENDING；不能给所有邻居虚增 command attempt |
| COMMIT 成功后异常/超时/断管 | 调用方先假定 unknown；不凭 exception 判 rollback | 查询 manifest **全部原 CID**，已 terminal 直接复用；未全部查询成功前不得 retry、quarantine 或换 CID |
| 单个 status 查询失败 | 保持未解决；不把读不到当 PENDING | 继续只读恢复，必要时停 worker/暴露 unknown；不得盲重放 |
| 进程消失/重启 | 新 fenced owner 先恢复未解决 manifest；不能只靠内存 list | 全体原 CID 重新查询并验证归属/hash，terminal immutable；只重新调度确认 PENDING 的原 CID |
| 确定命令 poison | 先整批 rollback并 query-all，再用原单条路径隔离重现 | 只给可归因 culprit 记录 bounded technical attempts；达到阈值仅它 QUARANTINED，无 accepted order result |
| COMMIT/磁盘/lease 等无确定 culprit | 批级故障+bounded backoff，停止扩批或故障退出 | 不把所有选中 CID 当 poison；邻居没有业务尝试失败就不增加 command attempt |

错误对象需携带 immutable manifest ID、全部原 CID、当时 executing CID（若有）、失败阶段，
不能只带最后一个 CID。`record_failure` 仍必须在 fenced 事务中再次读该原 CID terminal，
防止 recovery 与 post-COMMIT receipt 竞争。查询全体结束后，即使全是 PENDING，也只是
允许重新调度；每次执行仍须在新 Wtxn 内检查 terminal 和业务幂等键。
清单 membership 本身不是 exactly-once 原语；最后一道防线仍是原 CID immutable terminal、
业务幂等与效果原子 COMMIT。技术 retry、quarantine、business reject、ACK、late 与金融
成功分别计数，不能互相抵消。

## 幂等、风险和审计契约

同 CID 同 canonical payload 重入只返回原 queued/terminal；同 CID 异 payload 在 enqueue
冲突，不覆盖历史。同一 shard inbox 的 CID 唯一性不是全路由跨片全局唯一性；查询仍需
account ownership，禁止用 batch ID 跨账户探测 receipt。

order ID 仍是 `(account_id, order_id)`。不同 CID 对同 OID 同内容是既有订单 replay，只
链接原 effect/audit，不再预占或生成新订单；同 OID 异内容按现有规则拒绝（service :756–761）。
同批内的重放也要读取当前 transaction 的订单表，不能只查批前快照。REPAY 始终保留
原 CID 的信用幂等记录，不允许用 attempt ID 重新还款。

每条 NEW/reduce-only 都在当前连接读取账户、live orders、positions、debt、audit 状态，
完整执行 `_admit_order`。同账户前序 staged 写入会改变后续 available margin 与累计
reduce-only 剩余量（service :769–782）；不能把批前 capacity/risk 复制给每条并行批准。
取消释放、还款记账也必须影响本批后续完整 risk。既有 liquidation/freeze/halt/产品限制
不因类型是 reduce-only 而跳过。

每个新接纳都继续生成 required `ORDER_ACCEPTED` audit，包括 before/after、market ref、
risk summary 与 event。CANCEL/REPAY 保留各自原有 event/credit/ledger evidence，不能假称
当前已经有不存在的 cancellation decision audit。拒绝 error terminal 与没有 effect 的状态
同 COMMIT；本提案不新增一个“拒绝也算成功”的 audit。批级 manifest 不能替代逐业务证据。

NEW 写入前 fresh quote 检查仍执行；若本批有真正新接纳，全部 terminal staged 后再做
market freshness/version/digest checkpoint，再交给 SQL `before_commit` 检查实际 owner
token、PID/boot/generation/lease/clock 高水位。最终检查失败则**整批 rollback**，包括之前
本可单独成功的 CANCEL/REPAY；之后可单独重调度降低影响。任何 lease 续期等待、控制
变化或 quote aging 都不能通过 cached Python “已检查”标记绕过。

这些检查紧邻提交，但 OS pause/fsync 可发生在最后检查之后。独立模型把 fence/quote
checkpoint 与 COMMIT 抽象成一个原子动作；它没有证明真实进程在物理 COMMIT 时刻仍
未过期，也没有证明 quote age 能限制暂停/落盘延迟。实际实现需保留既有 fence 语义，
单独解释/测量这种间隙，不能把有限模型升级成墙钟保证。

## 独立有限模型与反例

[explore_durable_batches.py](../formal/explore_durable_batches.py) 只用标准库，不导入 runtime、
reference calculator 或既有枚举器函数。状态图是独立设计规格，不是生产实现的 refinement
proof。包括 durable book、单独 staged savepoints、持久原 CID manifest、易失执行列表、
SH gate、final lease/freshness checkpoint、actual COMMIT known/unknown、整批 rollback、
重启恢复 membership、逐 CID query-all、只重调度 PENDING、poison 单条隔离。预算可以在
处理 prefix 后 seal，提交已执行 prefix、保留同一 manifest 中未执行原 CID 为 PENDING；
actual-COMMIT unknown 因而也覆盖同 manifest 混合 terminal/PENDING 的状态。仅用于覆盖
统计的 `unknown_actual_commit` 是模型观察者的物理事实标签，协议分支不能读取它。

每个场景 3 个命令、2 个账户、最多 2 条/批、最多 3 次 attempt；最多 1 次普通技术故障、
1 次 poison failure、1 次进程 crash、1 次环境变化，单 writer/单 shard。failed query 是停滞步，
不会推进 query bitmap；不建模网络读回的虚假数据。recovery 从 durable manifest 重建原 CID
是显式状态转换，但 manifest 的本地原子耐久性和权威 CID 查询正确性仍是前提。

复现命令只执行小模型，单 CPU、硬限时 10s：

```sh
timeout 10s python -c 'import os, runpy; os.sched_setaffinity(0, {min(os.sched_getaffinity(0))}); runpy.run_path("formal/explore_durable_batches.py", run_name="__main__")'
```

本次同命令输出保存于
[durable-batches-design-20261117.json](../formal/results/durable-batches-design-20261117.json)。
最终运行 wall 约 .56 秒，user .54 秒；没有跑负载。五个 safe 场景合计 18411 个状态、
41426 条转换，无 invariant violation；场景覆盖 FIFO CANCEL/REPAY、同批累计 reduce-only
拒绝、同 OID replay、同 OID 异内容冲突、业务拒绝与 poison。覆盖标记要求至少存在所有
原 CID terminal、实际 commit 后 unknown、rollback 后 unknown、重启恢复和控制让出路径；
可达完成状态不是 liveness 证明。

模型断言 terminal→effect/replay 和 effect→terminal/evidence 双向关系、exact active reserve、
还款 ledger amount、no duplicate effect、FIFO、风险容量/累计 reduce-only、quarantine 只
影响 poison、每批数量/抽象 work 上限。16 个 ingress identity 组合另外枚举 same/different
CID 与 canonical payload。模型 evidence 按 kind 抽象为 audit/event/replay link 或拒绝 error，
不代表每种业务都有同一套 decision audit。

13 个故意 unsafe 的变体必须各命中其**指定** violation，完整最短反例在结果 JSON：

| 变体 | 捕获的反例 |
| --- | --- |
| `split_terminal` | financial effect 已提交而原 CID terminal 仍 PENDING |
| `skip_same_account_head` | reserved CANCEL 越过同账户 earlier NEW |
| `skip_final_lease` | lease 过期后仍走抽象 commit 动作 |
| `skip_final_quote` | quote-age 最后检查失败却提交新 effect |
| `release_gate_early` | financial COMMIT 不再受同一 SH gate 保护 |
| `retry_before_query_all` | 尚未查询全部原 CID 就 retry/isolate（协议禁用事件） |
| `replay_committed_unknown` | 实际提交 unknown 后盲执行，原 CID effect 变成两次 |
| `stale_reduce_only` | 后续条用批前 reducible position，累计预占超过 1 |
| `reject_leaks_effect` | business savepoint reject 遗留金融效果 |
| `terminal_only_success` | SUCCEEDED 没有效果，也没有原效果 replay link |
| `missing_reservation` | NEW effect 已记而 active reserve 丢失 |
| `missing_repayment` | REPAY terminal/effect 与实际 ledger amount 不符 |
| `forged_replay_link` | 把自身伪装成原 effect；link 必须指向更早、同 canonical OID、真正已提交的 effect |

`retry_before_query_all` 检查的是恢复协议禁止的动作，不单独声称少查一次必然重复资金；
实际重复作用由 `replay_committed_unknown` 的另一反例说明。所有 unsafe variants 是设计
negative controls，不是对现 runtime 的漏洞指控。

当前模型在 manifest 准备时只有 PENDING，依赖单 local writer，不枚举准备后其他写者把同
CID 变为 terminal 的竞争；设计要求的 Wtxn 内 recheck/跳过既有 terminal 是实现契约，不能
说已由此图验证。模型只保存一个 active manifest slot，`clear` 抽象恢复 disposition/归档，
不验证永久 append-only history、schema/hash、专用 role 权限或其 metadata COMMIT 次数。
全局 `attempts<=3` 是展开上界，不是 runtime 每 CID technical-attempt 计费实现。年龄公平、
热账户持续到达、真实 elapsed-time budget、控制 barrier 内容和 token 换代也没有细化进图；
保留这些边界才可把模型用作实现 review 的输入。

模型不证明 liveness、公平调度、真实 timeout/flock 排队、完整金融公式、SQL/trigger 实现、
全部异常类、任意规模、replication/HA、真实 RPO 或 production readiness。WAL/FULL、本地
原子 COMMIT、文件系统/fsync 正确性、权限/token 身份和本地存储幸存都是假设；没有做
断电/盘损/恢复点测试。ACK 已落盘不意味着可在磁盘永久丢失后 RPO=0，没有复制保证。

## 后续实现审查所需材料（本轮不执行）

reviewer 可先复查 [独立审阅记录](durable-financial-batches-review.md)、模型与反例、上述
逐入口引用，并核对 git diff 只涉及 docs/formal。真正实现前应明确 manifest migration/guard
权限、worker 接入、failure object/query-all/restart、budget/公平调度及最坏控制等待契约。
所需功能验收包括：同批 success/reject、所有 savepoint/COMMIT 前后故障、真实 post-COMMIT
unknown、每个 CID 查询失败、重启失去易失列表、duplicate CID/OID、累计 reduce-only、
quote/lease 最后检查、poison 单条隔离、control EX 和 background gate 竞争。

性能验证应先按 source-qualified cache0/opt 对照增加因果计数：每角色 connect/BEGIN/COMMIT、
manifest 与 financial batch 尺寸/填充率、new effect/replay/reject、guard/audit/full-risk 次数、
每 CID ACK→start→terminal 延迟、SH 等待/持有、EX 等待、background gate hold、unknown
查询与 retry，保留全部 raw 和内部技术异常。只在这些材料证明真实 financial Wtxn 密度
下降且所有正确性 gate 通过后，才有资格提出负载实验或收益数字。
