# 不可变行情解析缓存

`uta.market_cache.MarketDecodeCache` 只省略相同持久化 JSON 的重复 `MarketSnapshot.from_json` 解析。默认容量为 **0，关闭缓存**；显式设置 4 可保留最近四份完整文本及其不可变模型。合法容量为整数 `0..64`，不接受布尔值、浮点值或隐式字符串转换。

缓存不保存风险计算、时钟检查、策略校验或交易授权结果，也不会跳过 SQLite 读取。实际服务集成应只替换解码这一行：

```python
row = connection.execute(
    "SELECT payload FROM uta_market WHERE singleton=1"
).fetchone()
# 缺失记录必须沿用服务原有拒绝逻辑，不能回退到上一份缓存。
snapshot = market_decode_cache.parse(row["payload"])
if fresh:
    snapshot.validate(now=self._now(), max_age=self.max_price_age)
self._validate_policy_market(snapshot)
```

`fresh` 的既有语义由服务保持。要求新鲜数据的路径必须每次执行当前时钟检查，不能把上一次验证通过当成这次通过。策略也必须每次按当前服务配置重新校验。一个已经通过结构解析的缓存对象可能随后因过期、未来时间或策略不一致被服务拒绝；这些拒绝和通过的判断都不进入缓存。

## API 与并发

- `MarketDecodeCache(capacity=0)` 创建独立实例。服务接线约定使用 `market_cache_size=0`，显式 `market_cache_size=4` 才开启。
- `parse(payload: str) -> MarketSnapshot` 使用当前 SQLite 事务实际读出的完整、原样 payload 字符串作为键。不使用版本号、摘要、时间戳或数据库文件名替代内容键。同版本内容发生变化仍必须重新解析；即使两个文本表示相同 JSON 值，不同拼写也是不同键。
- `stats()` 返回独立字典：`capacity`、`size`、`hits`、`misses`、`errors`、`evictions`。调用方修改这个字典不会改变内部状态。
- `clear(reset_stats=False)` 清空条目，默认保留累计计数；`clear(reset_stats=True)` 同时清零计数。`reset_stats` 必须是布尔值。

`misses` 计数实际解码尝试，包括容量 0 的参考路径以及失败的尝试；`errors` 只记录解码异常，不代表服务层风险拒绝次数。失败的解析保留原异常，不缓存异常、失败结果或不完整模型，也不驱逐已有条目。

实例内部使用锁保护 LRU、计数与解码过程。多个线程同时读取同一份冷行情时，成功解析一次，其余获得同一个不可变模型；不同冷行情的解析也依次执行。模型的资产和合约映射是只读副本，嵌套规格是 frozen dataclass，金融金额是不可变 `Decimal`。更新行情必须产生新的 payload，不能修改缓存对象。

模块没有全局缓存。每个服务实例应创建自己的 `MarketDecodeCache`，不同服务、数据库或重启之间不复用缓存实例。缓存本身没有数据库读取、版本提升、行情回退或自动刷新权限。SQLite 返回普通字符串；非字符串输入仍由参考解析器拒绝，字符串子类绕过 LRU，避免自定义 hash/equality 改写内容身份。

## 容量与内存边界

LRU 最多保存 `capacity` 组文本和模型。参考解析器把每份文本限制为 **1 MiB UTF-8**，并分别把资产、合约映射限制在最多 4096 项，同时约束标识符和 Decimal 精度。因此容量 4 的缓存最多保留四份、合计不超过 4 MiB UTF-8 内容的文本键，容量 64 对应最多 64 MiB UTF-8 内容。

上述数值不是 Python 堆或进程 RSS 上限。Python 字符串、字典、Decimal、规格对象和 LRU 的内存开销要另计，解码还会创建临时对象，SQLite 当前结果及调用方持有的对象也不属于缓存容量。`clear()` 或驱逐不会收回调用方仍持有的模型。容量 0 不保留任何文本或模型，仅保留锁及统计计数。

## 验证证据

`tests/test_market_cache.py` 验证默认关闭、完整文本键、同版本实际 SQLite 内容变更及损坏、LRU 顺序、异常不缓存或驱逐、深不可变、跨实例隔离、过期与未来时钟重新拒绝、容量及 1 MiB 边界、并发首次解析以及统计清理。它没有进行吞吐压测，不能据此宣称性能收益；服务级别的每次 SQL 读取、新鲜度和策略检查由集成与独立故障测试验证。
