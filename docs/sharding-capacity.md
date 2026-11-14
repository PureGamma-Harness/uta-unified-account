# 实验性单机账户分片与容量边界

`uta.sharding.ShardRouter` 是单机账户路由实验。一个账户的余额、负债、利息、持仓、订单预留和风险计算都在一个 SQLite 数据库中提交。它没有实现跨分片撮合、跨分片资金转移、分布式事务或高可用主权租约，也不提供公网 API。

## 固定路由与重启

路由公式为 `int.from_bytes(sha256(account_id.encode('utf-8')).digest(), 'big') % shard_count`，版本为 `sha256-utf8-big-endian-mod-v1`。账户 ID 使用现有服务的 ASCII 校验规则，不作隐式归一化。同一 ID 总是落到同一分片；不同账户共享同一分片的数据库写锁。

私有目录保存 `router.sqlite3`、`router.lock` 和固定编号的分片数据库。不可变 layout descriptor 包括格式版本、分片数量、hash 版本、全部资产精度及风险政策 hash。政策 hash 覆盖手续费、行情最大年龄、产品目录和组合规则。重启时任何变化都被拒绝，不能把增加分片数当作在线扩容；重新分片需要独立的停机迁移与对账方案。已存在的分片缺失时停止并持久保持全局暂停，不会创建一个空库冒充恢复成功。

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
