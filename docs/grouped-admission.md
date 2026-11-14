# 权威交易路径的有界批提交

本模块对已实现的本地权威订单准入与撤单做 group commit，不调用研究模拟器，不计算一套新的风险公式，也不扩展账户模式或产品权限。它是单一 SQLite 数据库内的提交优化，不是跨分片事务、复制日志或生产容量验收。

## 使用与边界

```python
from decimal import Decimal
from uta.admission import AdmissionBatcher

with AdmissionBatcher(exchange, max_batch_size=32,
                      max_delay_ms=2, queue_capacity=1024) as batcher:
    future = batcher.submit_order("alice", "client-order-1", "BTC-PERP",
                                  Decimal("0.01"), Decimal("100"))
    receipt = future.result(timeout=2)
```

构造完成即启动一个非 daemon worker；必须使用 context manager 或 `close(wait=True)`。批大小为整数 1..256，收集等待为有限 0..1000ms，pending queue 为整数 1..65536。队列中的业务按同一 FIFO 顺序处理，同一账户不乱序。每批最多 `max_batch_size` 条，队列与当前批次均有上界；队列已满立即返回 `admission_overloaded` 503，不阻塞调用者等空位。

`cancel_reserve` 额外保留撤单入队槽，默认 16、允许整数 0..4096。普通新单在总队列长度达到 `queue_capacity` 后即拒绝；撤单可继续使用最多 `queue_capacity+cancel_reserve` 的总上界。只有一条 FIFO，撤单不会越过前面尚未执行的同账户新单；它不是优先调度，也没有实时撤单 SLO。总内存命令上界为上述队列总上界加当前最多一个批次。统计明确输出两个容量及总容量。

`submit_order()` 与 `cancel_order()` 返回 `concurrent.futures.Future` 的子类。共享原服务的输入校验、产品目录、行情时效、暂停/账户冻结、风险/订单预占及幂等检查。保留 `liq:` ID 的伪造和客户撤单限制。输入不合法、队列已满或 worker 关闭属于未入队错误，立即返回失败 Future；入队不表示已接纳或预占成功。

## 事务与确认协议

一个批次使用原 `exchange._transaction()` 的 `BEGIN IMMEDIATE`、WAL/FULL 和外层 COMMIT。每个命令有独立 SAVEPOINT；其状态变更、版本和事件复用原 `_admit_order` / `_cancel_order`，不复制金融计算。

- 预期业务错误只回滚该 SAVEPOINT，后面的命令继续以之前已成功命令产生的状态计算。
- 业务错误使用显式 code allowlist，不以“所有 409 都是客户错误”推断；未知 ServiceError code 归整批技术失败，新增业务 code 需要审查并补测试。
- 缺失/过期行情的预期 503 单列为 `market_rejected`，不计业务拒绝或成功；同组不需要行情的撤单仍可提交。
- SQLite、Ledger、Storage 错误链、配置/存储损坏以及未知程序异常均使整个批次退出。不会因 SQLite FULL 自动回滚后已丢失 SAVEPOINT 而继续接纳后续命令。
- 固化规则与持久行情参数矛盾的 `margin_rule_conflict` 即使是 HTTP 409 也属于配置/数据损坏，整批失败，不能伪装成客户业务拒绝。
- 外层 COMMIT 返回之前，不发布该组任何成功回执或排队业务拒绝。约束失败不能让前几个 Future 误报接纳。

有真正新接纳（包括 reduce-only 新挂单）的组，在最后一个命令处理完毕、退出事务体前再次检查行情时效；若处理期间行情已过期，则整个组不提交并返回技术不可用回执。纯撤单和原 ID 无写入重试不强求新鲜行情。这个检查仅保证 COMMIT 前最后一个应用检查点仍有效；操作系统暂停、落盘或网络返回耗时没有绝对上界，不能宣称收到回执时行情绝不过期。

发生技术异常时所有该组 Future 返回 `admission_batch_failed` 503，提示按原业务 ID 查询或重试。**这个代码不无条件承诺“确定未提交”**：事务已知回滚时没有副作用；若真实 COMMIT 后回执通道或数据库包装层才报错，则结果未知，持久状态可能已经生效。重新用原账户/订单 ID 查询、提交相同内容可以得到原状态；不得换一个新 ID 盲目重发。

一个批次不是客户端的原子多腿/多订单业务请求。某一命令的业务拒绝不会撤销其他命令，且同批 `submit→cancel` 可以在一个落盘点提交，第一条接纳回执表示其处理时点，查询接口表示当前终态。不能用这种零寿命订单序列代替真实撮合性能。

## 取消、关闭和调用约束

排队 Future 的 `cancel()` 成功时，该命令不会执行。worker 已将 Future 设为 running 后，`cancel()` 返回 false；HTTP 等待超时或连接丢失不能据此撤销业务，必须用原 ID 恢复结果。

`close(wait=False)` 停止新入队并唤醒 worker，已入队任务仍排空；`close(wait=True)` 等待排空与回执发布后返回，可以重复调用。`wait` 必须是 bool。CLI/HTTP 关闭应先停止接收新请求、排空已接收的 HTTP 请求，再关闭批提交 worker。

Future 回调必须短而非阻塞；同一 worker 内递归 submit 返回 `admission_reentrant`，递归 close 抛错，避免自等待死锁。回调调用同一 worker 尚未发布的 Future 的 `result()` / `exception()` 时，潜在阻塞等待直接抛 `RuntimeError`；`timeout<=0` 仍保持标准非阻塞 `TimeoutError`，已完成结果和普通线程等待保持标准语义。即使回调抛 `SystemExit`，也不会阻断其他已提交回执或杀掉 writer；该异常计入 `callback_failures`。调用者不得直接手工完成返回的 Future。

## 诊断与验证

`stats()` 提供 `worker_alive/accepting/queued/running`、`committed_batches/committed_commands`、业务/行情拒绝、技术失败、过载和 pending cancellation。`committed_commands` 是返回了命令结果的处理次数，含幂等重试，不是唯一新订单数，不能拿它直接充当持久成功吞吐。

Future 的只读 `admission_enqueued_ns/admission_started_ns/admission_completed_ns` 是进程内单调时钟诊断，不进入财务回执。started 是设为 running 后、取得批事务前，因此包含写锁等待。成功和排队业务/行情拒绝的 completed 在外层 COMMIT 后；技术异常、预校验及队列拒绝也有异常完成时间，因此不能仅凭时间戳推断已落盘。跨进程不能直接比较这些时间，客户端/负载工具的观察完成时间是更保守上界。

批提交器属于一个明确的 `ExchangeService` 本地权威，不会自动把命令经过 `ShardRouter` 的全局屏障。不能将私有分片 service 直接接入它后声称仍受 router 协议保护。多节点、跨分片组提交、账户优先队列和复制协议仍需独立实现与验收。

`tests/test_admission.py` 验证共享提交、真实提交前不可见回执、预期业务隔离、技术整批失败、原 ID 恢复、同组顺序、pending cancellation、队列上界、关闭排空、同 ID 并发、只减仓 ID 保护、低 Decimal 上下文及回调隔离。独立故障组另测真实 SQLite FULL、deferred FK COMMIT 失败、进程退出及结果未知。所有资金与订单均为合成数据；不由此授予生产、HA 或万笔容量资格。
