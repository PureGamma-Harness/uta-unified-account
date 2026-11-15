# 缓存内核性能实验与验收边界

已完成同源码三对 primary 和三对 hot-varied 短探针，全部 300,000 条到达保留并通过复开对账。primary 持久接纳速率中位数从 708.20/s 到 992.63/s，hot-varied 从 615.67/s 到 856.38/s；仍有大量过载和晚到，生产容量门槛未通过。以下保留预先确定的实验方案与完整实测；缓存正确性由独立验证组另行验收，本工具不修改交易、风险或存储实现。

## 相同源码与实验顺序

`benchmarks/run_kernel_benchmark.py` 在同一完整提交 SHA 内比较两种显式配置：base 的 `reserve_cache_size=0, market_cache_size=0`，optimized 的默认容量分别为 `4096, 8`。两者使用同一运行时、数值模型、诊断计数路径、数据库配置及生成器。不能将本轮 size0 与历史不同源码的同步或 group commit 成绩拼成 A/B。容量为零时仍可能承担缓存包装、锁和未命中统计的成本；这是同源码基线的一部分。

默认三对，执行顺序为 `base/optimized, optimized/base, base/optimized`。每次使用全新数据库和服务对象，账户设立、合成资金入账不计入到达窗口；每次分别发布一个新生成的真实当前时间戳快照，清空服务缓存后保存计数起点。窗口结束并排空后记录命中、未命中、淘汰差值以及缓存起止大小。不会通过修改观测时间制造行情新鲜度或缓存命中。

运行前、每次运行前后均检查完整提交 SHA、已跟踪文件是否干净及 `uta/*.py`、`benchmarks/*.py` 的内容摘要。中途源码变化即终止比较，保留已产生的原始文件和失败日志。生成结果产生的未跟踪文件不属于源码污染；运行时和生成器摘要仍必须完全相同。

固定主要配置：到达窗口 5 秒、计划到达率 5,000/s、100 个账户、1 个 SQLite 分片、batch64、4 个 dispatcher、全局 1,024 个 outstanding 名额、最大 batch delay 2ms。所有模式均使用 SQLite WAL/FULL、busy timeout 2s；服务默认 busy timeout 为 10s，本实验明确统一为 2s。端到端软响应期限 1,000ms，独立于 busy timeout。最多排空预算 10 秒，实际始终等待在途工作结束；超预算保留记录并失败。

## 预先声明的负载

| 独立 cohort | 账户分布 | 订单经济条款 | 地位 |
|---|---|---|---|
| primary | 100 账户均匀轮转 | `quantity=.001, limit_price=100` | 首先执行三对；明确只有一个经济 key |
| hot-varied | 前 10 账户接 30% 到达，其余 90 接 70% | 40 种合法经济 key，确定性循环 | 待 primary 正确性与资源情况评估后单独执行 |

hot-varied 的每个热账户恰有 750 次计划到达；冷账户每个 194 或 195 次。工具按确定性的整数调度分配到达，不用结果反馈调低下一次到达率。生成前验证每账户最多 900 次计划到达，保留距离运行时 1,000 个挂单上限的余量。所有成功订单持续 OPEN；无撤单、撮合、成交或保证金释放。两边等待入队和实际接受的数量可以不同，原计划到达序列及其哈希必须完全相同。

varied 的经济 key 为笛卡尔组合：正、负两个方向；数量绝对值 `.001/.002/.005/.01`；限价 `99/99.5/100/100.5/101`。数量步长 `.001`、价格步长 `.01`，最小名义均合法。完整 40 笔循环包含所有组合。这仍是有限 key 的合成负载，不代表真实交易分布或缓存容量对抗实验；报告不得只展示理想同 key 命中。原始记录保存每请求的数量和限价，summary 保存各组合的计划数量及完整账户、订单条款调度哈希。

## 计时、统计与持久性核对

延迟起点始终是计划到达时间，终点为 COMMIT 后调用者观察到结果的时间。分别保存全请求与持久接纳请求的 P50/P95/P99/P99.9；直方图上界相对桶宽不超过 0.1%，每条原始纳秒时间可以精确重算。主吞吐分母包括实际排空时间，不把到达窗口内发出的尝试数称为完成量。另报按期限完成的持久接纳速率和 late 数量。

每次请求保留唯一 sequence、账户/订单 ID、原计划到达、发出、dispatch、worker 开始、回执发布及观察完成时间。业务拒绝、行情安全拒绝、overload、技术失败、unknown、未执行取消分别记录；底层 SQLite 错误码和名称沿异常因果链提取。unknown 在重新打开存储后分别报告是否发现业务影响，找到账面订单也不会增加已确认接纳吞吐。

每次重开同一持久数据库、相同配置的产品和规则，明确关闭两个缓存。逐笔核对请求、订单和持久 ORDER_ACCEPTED 事件：BTC-PERP、原请求数量/限价、OPEN、无成交、无已收费、非 reduce-only。账户资金保持 USD100,000,000，无仓位，版本等于资金入账后的版本加唯一接纳数。逐账户计算预占，并验证账本、WAL/FULL、唯一事件及未知影响。

逐笔参考核对不调用生产 `_reserve`、估值或舍入函数。设有符号数量为 `q`、限价为 `p`，快照标记价 100、IM=1/10、手续费率=1/2500、USD 最小单位为 1e-8：

```text
im   = abs(q) × max(100, p) / 10
loss = max(0, q × (p - 100))
fee  = ceil(abs(q) × p / 2500 × 100000000) / 100000000
reserve = im + loss + fee
```

常量负载每笔为 `.01004 USD`；varied 按每个成功或已产生未知业务影响的请求分别求值、求和，禁止以平均值或固定乘数替代。

## 可复跑命令

先准备完整冻结 SHA；`--plan-only` 只打印计划，不创建数据库或启动负载：

```bash
python benchmarks/run_kernel_benchmark.py --expected-source <完整冻结SHA> --market-cache-size 4 --plan-only
python benchmarks/run_kernel_benchmark.py --expected-source <完整冻结SHA> --market-cache-size 4 --plan-only --hot-accounts 10 --hot-fraction .3 --order-distribution varied
python -m unittest discover -s tests -p 'test_kernel_benchmark.py' -v
python -m unittest discover -s tests -p 'test_group_benchmark.py' -v
```

获得调度窗口后，分别运行两个 cohort；不要并发执行：

```bash
python benchmarks/run_kernel_benchmark.py --expected-source <完整冻结SHA> --market-cache-size 4 --output /tmp/uta-kernel-primary
python benchmarks/run_kernel_benchmark.py --expected-source <完整冻结SHA> --market-cache-size 4 --output /tmp/uta-kernel-hot-varied --hot-accounts 10 --hot-fraction .3 --order-distribution varied
```

单次探针也可直接调用 `run_group_benchmark.py` 的 `--reserve-cache-size`、`--market-cache-size`、`--hot-accounts`、`--hot-fraction`、`--order-distribution`。旧运行时不支持非零缓存时明确报错，禁止悄悄退回未优化路径。缓存为零的旧参考运行时允许运行，并明确记录 counters unsupported；正式本轮 A/B 必须使用同时具备两类缓存 API 的冻结版本。

每个 run 留存 `arrivals.jsonl.gz`、environment、summary、manifest；cohort 额外保存 plan、逐 run UTC 开始结束时间、交替顺序、各对比率、median 和覆盖全部证据的 SHA256 manifest。硬件、CPU quota/affinity、Python/SQLite、文件系统、运行时代码和生成器摘要均保留。源数据库仅在本地保留以便再次检查，不发布合成数据库文件。

## 上线门槛、部署及回滚

此工具最多允许 10 秒到达窗口且没有持续行情 feeder。三次配对仅是短探针重复观测，不能证明统计显著性、最大容量、30 分钟稳定性、清算吞吐或生产验收。所有 run 的生产批准字段固定 false；cohort 退出成功仅表示工具完整执行及对账完成，不能作为容量门禁通过。未知、过载和晚到不因缓存收益而豁免。

工具部署无需数据库迁移或外部服务，只需该冻结提交和标准库 Python。启用非零缓存属于运行时配置变更，必须遵循集成后的运行时验收；工具支持立即用两个 size0 参数重测。回滚测量工具可回到上一提交；本轮不对已有生产数据库写入。失败时先保留 raw、manifest 和本地新建数据库，确认未知业务影响，禁止复用同一 output 目录覆盖原始证据或补写成功结果。

方案由性能组编写，独立验证组已审查同源码配对、全部订单 OPEN、含排空分母、未知不转 ack、热点订单上限和快照独立新鲜度的口径；该方法审查不构成真实资金或上线批准。


## 2026-11-15 实测归档

实际测量提交为 `146fe74d3006d39b5ecb3fb3b2d1cbf2e133ad6a`，全部 12 次运行的 tracked 工作树干净，前后运行时与生成器内容摘要一致。早先候选 `13e8b31` 未测量，没有将其作为 baseline。两类缓存实测容量分别为 **4096 / 4**，同源码 baseline 为 **0 / 0**；工具默认 market=8 未用于本次实验。
primary 驱动执行时间为 07:13:44.109017–07:14:29.403540 UTC，hot-varied 为 07:14:48.679113–07:15:35.855436 UTC。协调参与的其他 Agent 在窗口内停止本地计算；这不是专用主机隔离证明。12 次独立运行各含 25,000 个计划到达，以 `(run, arrival)` 标识唯一记录；A/B 使用同一计划但各建新库，共保留 300,000 条到达记录，61,852 个有持久回执的订单全部保持 OPEN，238,148 个 overload，38,025 个成功回执超过 1 秒期限；unknown、技术失败、业务拒绝、行情安全拒绝均为 0。每次均独立重新打开存储并逐单、逐事件、逐账户和账本核对。
环境：Python 3.12.14、SQLite 3.53.1、Linux x86_64、AMD EPYC 9V74；可见 affinity 5 CPU，cgroup `cpu.max=400000 100000`（4 CPU 配额），内存上限 16 GiB。存储为本地 overlay 文件系统上的 SQLite WAL/FULL，单进程、单分片、没有复制或网络撮合。完整型号、配额、文件系统与源文件哈希见每个 environment.json。与前一天不同环境或不同源码的 744/s 数字不作收益比较。

| 独立 cohort | baseline 三次中位 ack/s | optimized 三次中位 ack/s | 各对 optimized/base 比率 |
|---|---:|---:|---|
| primary | 708.20 | 992.63 | 1.4616/1.4016/1.3991 |
| hot-varied | 615.67 | 856.38 | 1.4047/1.3623/1.4063 |

这些是三次交替配对的短观察，全部容量门禁 false。高缓存命中仍伴随大量过载和晚到；不能据此宣称 10,000/s、长期稳态、最大容量或上线通过。hot-varied 的 40 种经济 key 各计划 625 次到达，仍是有限 key 合成样本，未覆盖真实市场频繁改价、曲面更新或容量对抗分布。
### 每次完成量与排空

| cohort / run | 接纳数 | ack/s（含排空） | 期限内 ack/s | overload | 接纳超期 | 排空秒 |
|---|---:|---:|---:|---:|---:|---:|
| primary / pair-01-base | 4491 | 672.77 | 193.10 | 20509 | 3202 | 1.675 |
| primary / pair-01-optimized | 5960 | 983.30 | 539.66 | 19040 | 2689 | 1.061 |
| primary / pair-02-optimized | 6144 | 992.63 | 574.18 | 18856 | 2590 | 1.190 |
| primary / pair-02-base | 4748 | 708.20 | 183.16 | 20252 | 3520 | 1.704 |
| primary / pair-03-base | 4875 | 733.52 | 219.68 | 20125 | 3415 | 1.646 |
| primary / pair-03-optimized | 6271 | 1026.26 | 549.22 | 18729 | 2915 | 1.111 |
| hot-varied / pair-01-base | 4299 | 609.65 | 155.85 | 20701 | 3200 | 2.052 |
| hot-varied / pair-01-optimized | 5515 | 856.38 | 382.15 | 19485 | 3054 | 1.440 |
| hot-varied / pair-02-optimized | 5383 | 854.17 | 275.31 | 19617 | 3648 | 1.302 |
| hot-varied / pair-02-base | 4294 | 626.99 | 159.74 | 20706 | 3200 | 1.849 |
| hot-varied / pair-03-base | 4363 | 615.67 | 173.14 | 20637 | 3136 | 2.087 |
| hot-varied / pair-03-optimized | 5509 | 865.84 | 322.67 | 19491 | 3456 | 1.363 |

### 全请求延迟（毫秒）

| cohort / run | P50 | P95 | P99 | P99.9 |
|---|---:|---:|---:|---:|
| primary / pair-01-base | 0.280 | 1795.138 | 1964.105 | 1989.792 |
| primary / pair-01-optimized | 0.220 | 1283.062 | 1350.161 | 1361.001 |
| primary / pair-02-optimized | 0.221 | 1295.951 | 1410.864 | 1439.351 |
| primary / pair-02-base | 0.279 | 1714.471 | 1773.735 | 1787.975 |
| primary / pair-03-base | 0.286 | 1614.677 | 1742.110 | 1770.193 |
| primary / pair-03-optimized | 0.225 | 1192.779 | 1232.777 | 1242.674 |
| hot-varied / pair-01-base | 0.342 | 1952.362 | 2070.956 | 2125.479 |
| hot-varied / pair-01-optimized | 0.234 | 1511.599 | 1598.618 | 1606.627 |
| hot-varied / pair-02-optimized | 0.227 | 1356.926 | 1420.770 | 1450.906 |
| hot-varied / pair-02-base | 0.338 | 1894.689 | 1999.761 | 2009.780 |
| hot-varied / pair-03-base | 0.335 | 2034.031 | 2181.438 | 2207.760 |
| hot-varied / pair-03-optimized | 0.217 | 1402.428 | 1465.481 | 1480.201 |

### 成功持久接纳延迟（毫秒）

| cohort / run | P50 | P95 | P99 | P99.9 |
|---|---:|---:|---:|---:|
| primary / pair-01-base | 1442.231 | 1966.069 | 1985.819 | 1993.774 |
| primary / pair-01-optimized | 943.087 | 1348.813 | 1358.283 | 1363.724 |
| primary / pair-02-optimized | 909.756 | 1408.046 | 1433.608 | 1443.673 |
| primary / pair-02-base | 1326.088 | 1773.735 | 1786.189 | 1789.763 |
| primary / pair-03-base | 1293.363 | 1742.110 | 1766.658 | 1771.964 |
| primary / pair-03-optimized | 991.416 | 1230.315 | 1238.954 | 1246.406 |
| hot-varied / pair-01-base | 1556.054 | 2079.252 | 2121.235 | 2129.732 |
| hot-varied / pair-01-optimized | 1057.964 | 1597.021 | 1605.022 | 1609.842 |
| hot-varied / pair-02-optimized | 1207.172 | 1419.350 | 1448.009 | 1453.809 |
| hot-varied / pair-02-base | 1511.599 | 1999.761 | 2007.772 | 2013.802 |
| hot-varied / pair-03-base | 1443.673 | 2185.803 | 2205.554 | 2209.968 |
| hot-varied / pair-03-optimized | 1121.108 | 1464.017 | 1478.723 | 1481.682 |

全请求 P50 包含快速 overload，不能用它代替成功接纳的延迟。上表均从计划到达计时，原始纳秒值保存在 raw；显示值为已声明上界直方图的分位数。
### 缓存观测

| cohort / optimized run | reserve hit | reserve miss | market hit | market miss |
|---|---:|---:|---:|---:|
| primary / pair-01-optimized | 186829 | 1 | 6053 | 1 |
| primary / pair-02-optimized | 198236 | 1 | 6240 | 1 |
| primary / pair-03-optimized | 206306 | 1 | 6369 | 1 |
| hot-varied / pair-01-optimized | 228584 | 40 | 5601 | 1 |
| hot-varied / pair-02-optimized | 218152 | 40 | 5467 | 1 |
| hot-varied / pair-03-optimized | 226873 | 40 | 5595 | 1 |

所有 run 的两类缓存淘汰计数均为 0。baseline 的 reserve capacity0 直接执行原始完整 Fraction 公式，缓存 hit/miss 计数均为 0，不能把该 0 理解为未执行预占计算；market capacity0 每次真实解析 JSON 并记录 miss。setup 计数与 timed delta 分开保存，复开核对的计算不计入 timed cache 统计。
### 复跑、证据和后续

公开证据位于 `benchmarks/results/20261115-kernel-cross/{primary,hot-varied}/`，各含 plan、run-window、每次 raw gzip/environment/summary、实际命令与 UTC 起止和完整 SHA256 manifest。300,000 条到达及每条数量、限价、结果、计划/执行/回执/完成时间均保留，未删除 overload 或晚到。原始数据库仍留在 `/tmp/uta-kernel-primary-20261115`、`/tmp/uta-kernel-hot-varied-20261115`，发布归档排除数据库。命令 stdout 与 run-window 内容一致，invocation 记录其哈希；stderr 单独留存。
`tests/test_kernel_benchmark.py` 的归档测试校验所有证据摘要、固定源 SHA、交替顺序、两种容量、每次 25,000 条唯一到达、账户分布、结果构成、全量接纳对账数量和生产门槛 false。重放完整运行应检出上述冻结提交，按 invocation 命令更换新的 output 路径，在有记录的安静窗口重测；不能覆盖本次证据。
下一步应在该新内核上重新剖析逐账户挂单扫描与精确聚合、SQL 和序列化占比，再评估有独立正确性证明的增量聚合或进程/分片扩展。此轮没有新源码 profile，不能用旧版本 profile 百分比证明新的剩余瓶颈。持续行情 feeder、多节点真实撮合、30 分钟开放环和故障恢复容量仍须独立工程与验收。

独立验证组另对本次 12 个 summary 与两个 run-window 做只读复核：同源码、各 cohort 双调度哈希一致、完成量与过载总数、含排空吞吐和 median 重算、初始缓存空、复开禁缓存标志及门禁 false 均通过，未发现测量口径阻断项。该复核没有独立重扫 raw 或数据库，不构成上线签字；详见归档 independent-review.json。
