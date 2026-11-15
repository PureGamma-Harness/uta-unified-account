# 风险计算缓存的运维与 API 独立审查

审查日期：2026-11-15。结论：在下述冻结代码和本机实测范围内，没有尚未关闭的集成阻断；**本报告未批准真实资金生产部署，也未批准默认启用缓存**。本次工作只审查运维/API 接线及回退边界，没有修改运行时代码。

## 审查对象与证据身份

报告工作树从 `92086bd` 独立建立。运行时检查覆盖以下新增实现及接线：

| 对象 | 代码身份 |
| --- | --- |
| 精确预留计算缓存及服务接线 | `eb016db`，`uta/reserve_kernel.py`、`uta/service.py` |
| 不可变行情解码缓存 | `064dc5e`，`uta/market_cache.py`；同时核对了行情 agent 工作树的同一候选实现 |
| 服务行情解码接线 | `e20e3a6`，每次读取数据库行后解码，并重新验证时效与产品策略 |
| CLI、metrics 和边界测试 | 最初为根工作树未提交改动，后提交为 `a129fac`；CLI/gateway 文件哈希与冻结候选一致 |

为避免滚动集成改变被测对象，独立验证先导出 `e20e3a625760b1fd39e0dc2dd76f0fd3b6cd4aea`，再覆盖当时的 CLI、gateway 与新测试，构建冻结候选。覆盖文件 SHA-256：

```text
uta/__main__.py             f562209d05967e0dc344dfa846bf7c493c47866f1515cd7198e2e9a1111f3131
uta/gateway.py              8793376c615ed371eab852c6696b7f6c3f8d5161619b040bf833a9b1251a9ab7
tests/test_kernel_gateway.py 8bde953e22a48f774b6629f8a033e796d32a5f6b9509e8132883d4f4a073be1d
```

最终又读取根分支 `a60e462`：上述两个运行时接线文件哈希相同，三个缓存实现/服务文件相对 `e20e3a6` 没有变化；根测试已补齐 trader/funding/无效凭据不得调用 stats 的断言，测试文件哈希更新为 `f398f08b63a8d5c2a495e274d239bf090aeae167cdab319b043f0375e95efd9e`。再次运行该测试的 3 项检查全部通过。本报告不据此批准同期 router 改动。

## 阻断项与核对结果

初次静态检查时，CLI 已传 `market_cache_size`，但服务尚未接收该参数，默认启动也会发生参数不匹配。这是集成中的临时阻断；`e20e3a6` 接线后，真实 CLI 默认启动、显式启用及 SIGTERM 检查均通过，问题已关闭。

| 检查 | 结果与边界 |
| --- | --- |
| 默认关闭 | CLI 与 `ExchangeService` 均为 reserve `0`、market `0`。reserve 为零时使用保留的原始 Fraction 公式；market 为零时每次执行原解析器。独立构造 `ReserveKernel()` 的类默认值为 4096，不是 CLI/服务默认值。 |
| 参数早拒 | CLI 在读取凭据、构造 Database 和启动服务之前检查 reserve `0..65536`、market `0..64`；非 exchange 命令拒绝非零缓存配置。服务构造也在首次数据库事务前检查整数类型与边界，拒绝 bool。 |
| 真实传参 | 实际启动子进程并读取 `/metrics`，默认 `0/0` 与显式 `32/2` 均与实际实例一致。缓存开启后，真实重复订单预留产生两个缓存的 hit。 |
| 权限 | `/metrics` 在读取任何 cache stats 之前执行 risk/admin 权限检查。reader、trader、funding 返回 403，无凭据/错误凭据返回 401，两个 stats 方法均未被调用。 |
| 缓存与决策分离 | reserve key 包含完整经济输入，产品/保证金规则仍逐次解析。market key 是当前事务读取的完整 payload，而不是版本号；命中后仍检查当前时间及 `_validate_policy_market`。 |
| 金融事务与诊断分离 | 在 warm cache 后故意使 `ORDER_ACCEPTED` 事件步骤抛异常，账户版本、余额、订单、账本、事件及风险结果完全回滚；纯计算 miss 可以增加。清缓存或重置 counters 不改变这些金融结果。 |
| 关闭回退 | 在同一金融数据库以 `0/0` 重建服务，账户、风险、订单、账本和事件与开启时一致；原订单 ID 重试没有新增副作用。没有新增缓存数据库表。 |
| 服务退出 | 安装版 CLI 的 `0/0` 模式和 `32/2 + --batch-admission + --automate` 模式均等待已接收、正文未完成的 HTTP 请求处理完毕，再以退出码 0 结束。 |
| 包分发 | 实际构建并安装 wheel，在新 venv 中以 `-I`、从仓库外导入两个新模块，并通过安装版 CLI 执行上述参数、API 和退出检查。 |

服务启动之外的底层缓存类不直接接受 HTTP 业务输入。缓存结果也不是可持久化的下单许可：不能跳过数据库写事务、资金与仓位读取、当前行情、产品规则或成交验证。

## 实测范围

环境为 Linux、Python 3.12.14，全部使用临时数据库、合成账户和 loopback HTTP。没有调用真实交易所或使用客户资金。

| 执行内容 | 结果 |
| --- | --- |
| `python -m unittest discover -s tests -p test_kernel_gateway.py -v` | 冻结候选 3 项通过；根最终增强版相同 3 项再次通过 |
| `python -m unittest discover -s tests -p test_reserve_kernel.py -v` | 14 项通过，包括 invalid size 不建库、原公式路径、warm policy、行情变更及回退对账 |
| `python -m unittest discover -s tests -p 'test_market_cache*.py' -v` | 13 项通过，包括 exact payload、不可变模型、解析失败、时钟、并发与驱逐边界 |
| 独立安装版运维/API 探针 | 3 项复合场景通过，内容见下文；不是新增的仓库长期回归测试 |

独立探针的具体检查：

1. 在不存在的数据库目标上发送 6 类无效 CLI 参数，包括负数、越界和非整数；均退出 2，没有数据库、WAL 或 SHM。对 demo、serve、acceptance、lab、scenario、replay 六个命令显式设置非零缓存也均早拒，临时工作目录保持为空。
2. 用真实服务与 HTTP 核对全部角色，使用方法 spy 确认拒绝请求未调用 stats；强制晚期事务失败后逐项对比金融状态；清空缓存并重开同一数据库为 `0/0`，复核原订单幂等与账本重放。
3. 用实际安装版 CLI 启动默认服务和同时开启缓存、分组入场、自动化 worker 的服务；通过 REST 开户、入金、发布行情、提交重复经济输入订单；验证 metrics 的容量/hit，随后发送 SIGTERM，确认它没有提前终止已接收的 HTTP handler。

wheel 文件为 `uta_reference_exchange-0.2.0-py3-none-any.whl`，此次构建 SHA-256：

```text
9bd6f6dee11943518524d199200b516ffe221a47215a74e0235e4aa19ac9a813
```

安装后 `uta`、`uta.market_cache`、`uta.reserve_kernel` 的模块路径均位于新 venv 的 `site-packages`，没有引用仓库或候选源码目录。`pyproject.toml` 的 `packages = ["uta"]` 实际包含了两个新增 `.py` 文件。

冻结候选、安装环境和独立探针保存在本次会话的 `/tmp/uta-kernel-ops-review-1lyuwcyt/`；它们是临时执行材料，不是仓库承诺保留的长期证据。独立探针脚本 SHA-256 为 `294d98b49bfb235ef22593023d0d0e992bc8827fad0b0d8067a5068468412cbb`。本文件记录的是已观察结果，不宣称原始 stdout 或临时 wheel 会持续可下载。

## 运维使用与回退约束

保留默认 `0/0`，只在需要核验的环境显式设置：

```bash
python -m uta exchange \
  --database /var/lib/uta/exchange.sqlite3 \
  --credentials /etc/uta/credentials.json \
  --reserve-cache-size 32 \
  --market-cache-size 2
```

现有部署若使用产品目录、风险规则、资产精度、分组入场或自动化参数，须继续提供同一配置；上例没有授权更换金融规则或省略原有配置。risk/admin 可读取 `/metrics` 的 `risk_cache.reserve` 和 `risk_cache.market`。这些字段只包含实例内计数与容量，不包含账户、订单、价格或余额。

- 命中、miss、error、eviction 均为进程内诊断，不是交易回执、入场次数或已提交笔数。拒绝和回滚的计算也可能改变它们；两个缓存的统计读取不是一个金融快照。
- 关闭 reserve 时走原公式而不调用 kernel，因此它的零 hit/miss 不能解释为没有进行预留计算；关闭 market 时原解析器仍被调用并计入 miss。两者的关闭模式计数不能直接作为业务量比较。
- 容量限制的是条目数，不是 RSS。market 每个成功 payload 最多 1 MiB UTF-8，至多 64 个条目，但解析后的模型、字典和 Python 对象还有额外开销；reserve 的 key/result 同样占内存。本审查没有给出可生产套用的内存预算或吞吐容量。
- `clear_*_cache()` 及 `reset_stats=True` 只影响进程内优化状态。reserve 在清空时已有的纯计算可能随后重新填入条目；清空不是暂停交易或重置资金的手段。
- 命中行情解码并不证明行情仍新鲜。操作员不能用高命中率替代时钟、市场发布、风险拒绝和真实账务的监控。

回退采用正常停止并重启相同服务，保留金融数据库、金融政策、凭据及业务 ID，只把两个缓存容量设为零或移除显式启用参数。对退出前结果未知的请求，仍按原命令/订单 ID 重查或重试。**不要通过还原旧数据库、清余额、释放真实挂单预留或删除幂等记录来“回滚缓存”。**

本次小型本机 SIGTERM 检查验证了顺序和已接收 handler 的排空，没有验证最坏队列、存储阻塞、机器故障下的生产退出时限，也没有提供 HA/多机一致性保证。

## 建议保留的后续回归

完整权限矩阵已进入根 `test_kernel_gateway.py`。本次没有发现必须修改 runtime 才能继续本地评估的问题；建议把独立探针中的两类检查纳入长期自动化：安装版 wheel 的缓存 CLI/metrics 与分组/worker 联合退出，以及 warm cache 后晚期失败再同库切回 `0/0` 的全金融状态对比。

现有 CI 会构建 wheel、在仓库外安装并运行 demo、acceptance 和 scenario，但没有直接把“安装版显式启用缓存后读取 metrics 并 SIGTERM”作为发布检查。此处只完成了 Python 3.12.14 的独立实测，不能替代 3.10/3.11/3.13 CI、其他 agent 的算术/并发复核、性能实验及完整发布验收。缓存开关带来的性能收益、真实资金运行资格和整条分支的生产批准均不在本报告结论中。
