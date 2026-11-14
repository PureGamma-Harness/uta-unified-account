# 实验性单机账户分片与容量边界

`uta.sharding.ShardRouter` 是单机账户路由实验。一个账户的余额、负债、利息、持仓、订单预留和风险计算都在一个 SQLite 数据库中提交。它没有实现跨分片撮合、跨分片资金转移、分布式事务或高可用主权租约，也不提供公网 API。

## 固定路由与重启

路由公式为 `int.from_bytes(sha256(account_id.encode('utf-8')).digest(), 'big') % shard_count`，版本为 `sha256-utf8-big-endian-mod-v1`。账户 ID 使用现有服务的 ASCII 校验规则，不作隐式归一化。同一 ID 总是落到同一分片；不同账户共享同一分片的数据库写锁。

私有目录保存 `router.sqlite3`、`router.lock` 和固定编号的分片数据库。不可变 layout descriptor 包括格式版本、分片数量、hash 版本、全部资产精度及风险政策 hash。政策 hash 覆盖手续费、行情最大年龄、产品目录和组合规则。重启时任何变化都被拒绝，不能把增加分片数当作在线扩容；重新分片需要独立的停机迁移与对账方案。已存在的分片缺失时停止并持久保持全局暂停，不会创建一个空库冒充恢复成功。

每个分片另存不可变的 layout hash 和 shard index。截为空文件、丢失 identity 或用另一片的数据库替换，都拒绝启动并保持暂停；不会通过自动建表把损坏的恢复点当作全新账户库。此前未带 identity 的实验布局也需要明确的离线迁移，不能隐式接纳。

```python
from decimal import Decimal
from uta.sharding import ShardRouter

router = ShardRouter('/private/uta-shards', 4, {'USD': 8})
router.create_account('alice')
router.deposit('alice', 'synthetic:funding:001', 'USD', Decimal('1000'))
# 需先通过管理员发布完整可信 MarketSnapshot，再明确解除暂停。
```

新 layout 默认暂停新增风险。创建账户、记账充值、查询、撤单和还款可在暂停时路由；新订单和借贷必须通过全局 gate。暂不开放仅减仓绕过 publication barrier，因为部分分片收到新行情时不能授权基于不同 generation 的执行。

## 全局行情与暂停屏障

所有 router 实例共享同机 `flock`。账户命令取得共享锁，读取持久控制状态，然后在目标分片内完成事务；全局行情和暂停操作取得排他锁，等待已接纳的路由操作完成。账户命令不会持有控制库的全局 SQLite 写事务跨越分片交易。此 OS 锁只能协调同一台主机、同一目录中的合作进程，不能当作网络分区时的 HA fencing。

`publish_market(snapshot)` 先持久记录 `halted=true, publishing=true`，再暂停本地分片、逐片发布并保存水位。任何一步失败或进程崩溃，global gate 都保持关闭；重启不会自动开放。全部发布成功后仍保持暂停，必须显式调用 `set_kill_switch(False)`。激活会核对各片行情新鲜度、版本和内容 hash，逐片解除本地暂停，最后才提交全局开放状态。半激活失败时，即使某些本地 flag 已解除，router gate 仍不接纳新增风险。

`diagnostics()` 返回控制状态及每片行情版本、事件序号和就绪状态。部分发布后可在保持暂停的条件下发布更高版本的完整快照，再重新激活。失败命令没有成功确认；如控制盘无法写入，调用方必须按未知结果处理并保留暂停/取证，而不是假定请求已生效。

这套屏障要求所有写者使用 router。直接创建 `ExchangeService`、`CreditService` 或 `Matcher` 写入分片会绕过 global gate，不在路由协议保证内。数据库 owner 和受控本地文件系统继续属于可信边界。

## 信用、撮合和事件

`borrow/repay/accrue_interest` 以及账户信用额度按同一账户 hash 路由，风险仍读取该账户在同一数据库内的总资产和总债务。资金池和资产信用上限是 **每分片独立** 的，不能把每片上限当作全局共享额度，也不能复制一份实际资金到所有分片。

`fund_credit_pool(shard, ...)` 先在控制库永久绑定外部资金来源 reference 到指定分片、命令、币种和金额，再执行该片的幂等入账。相同 reference 不能在另一片重复入账。中间崩溃只允许重试原分片的同一命令，不释放或改派来源；这不是两库原子事务，恢复必须保留来源 registry 与各片账本的一致历史。

`match_once(shard, symbol)` 使用现有同库 `Matcher`，两条成交腿仍在同一分片事务中结算。不同分片的对手订单不会互相成交，因此它不是一个跨片共享的交易所订单簿。`require_same_shard` 和跨片 transfer 返回 `cross_shard_unsupported`；同片 transfer 也尚未实现。不能把每片吞吐相加后声称实现全局价格时间优先。

事件游标是 `{shard, sequence}`，每片独立递增，返回项带对应 cursor。消费者必须分别保存每片水位并按业务 ID 去重；没有虚构的全局 sequence 或全局事件总序。

## 持久化与测量门槛

本地提交继续使用 SQLite WAL / FULL。成功确认只表示本机持久提交；分片不增加副本，也不改变现有 RPO/RTO。备份和恢复必须覆盖 control descriptor/state、来源 registry 和全部分片：在全局暂停并停止所有写者后保存同一受控恢复点，禁止混用不同时期的控制库与分片。不能独立恢复一个分片后立即接单。

性能实验须使用相同源码、硬件、worker 数量、账户和产品分布、负载率、持久化设置与延迟统计，对 1/2/4 片顺序运行。只计算唯一成功持久化接单，拒单、过载、重复和未知结果分别报告。现有 benchmark 的独立多库模式可测理想分片上限；若未经过本 router 的 hash 和 barrier，必须明确说明它不是 router 的吞吐。

真实撮合加原子双边结算的 10k/s、30 分钟验收仍然阻塞。短测容量变化只决定下一项工程方向，不构成生产能力或 HA 认证。

## 2026-11-14 真实 router 短测

源码提交 `1a2beb9`，实跑包含 SHA-256 路由、每次控制库查询、共享 flock 和目标分片的接单/本地撤单事务。全部使用 4 workers、100 个账户、均匀账户分布、三个合成产品、1000 arrivals/s、5 秒到达窗口、1024 队列、5 秒最大排空，关闭 profile；1/2/4 片依次运行。协调窗口记录在 `benchmarks/results/20261114-router-shards/run-window.json`，root 在这段时间没有并发运行重测试，但共享宿主机没有资源隔离。

为了只测路由与准入容量，`--router-mode` 使用统一的 30 秒合成行情有效期，只发布初始新鲜快照，不在测量中运行 fanout。该 mode 限制 duration/drain 各不超过 10 秒，并明确排除行情发布吞吐；不能用它执行 30 分钟验收。原来的独立多库 benchmark mode 保留，不回写历史结果。

| 分片 | 唯一持久接纳 | 过载丢弃 | 超过 1 秒软期限 | 含排空接纳/秒 | 相对 1 片 | scheduled p99 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 2,840 | 2,160 | 2,309 | 353.92 | 基准 | 2,938.31ms |
| 2 | 3,161 | 1,839 | 2,465 | 432.32 | +22.15% | 2,398.72ms |
| 4 | 3,757 | 1,243 | 2,634 | 555.07 | +56.84% | 1,873.97ms |

每轮 offered 为 5000，完成加过载恰好等于 offered。没有业务拒单、技术失败或未知结果，唯一订单数量与 `ORDER_ACCEPTED` 事件数量逐片相等。超过软期限的提交仍保留为持久接纳，但另行计数，不冒充按时响应。吞吐分母分别为 8.024/7.312/6.768 秒，包含排空成本；按时接纳率仅为 66.17/95.19/165.92 每秒。

三轮的 gates 都失败，Phase 1 matching acceptance 都为 false。增加分片在这一次短测中有改善，但远未达到 10k；一轮/配置不足以给出统计置信区间或证明扩展率。当前最多只有四核 cgroup CPU 配额，控制路径、进程 IPC、磁盘同步和同片竞争都会限制进一步增益。此结果支持继续检查路由成本和固定风险组布局，不支持上线 HA 或跨片交易。

原始 `arrivals.jsonl.gz`、summary/environment、SHA-256 manifest 和源码校验保存在上述结果目录。SQLite 测试库留在本地并从版本库排除；提交的 raw 记录可复算所有唯一结果、延迟和产品/分片分布。运行目录本身会让 `git status` 显示 untracked dirty，因此另有 `source-verification.json` 将关键模块及生成器 hash 与固定提交逐一比较，不能只根据 dirty 布尔值猜测源码是否被改过。

```sh
python benchmarks/run_benchmark.py --scenario order --duration 5 --rate 1000 \
  --workers 4 --accounts 100 --shards 4 --queue-capacity 1024 \
  --timeout-ms 1000 --drain-seconds 5 --router-mode --smoke \
  --output /tmp/uta-router-shards4
```
