# 缓存内核性能实验与验收边界

当前交付是工具、测试和预先确定的实验方案，尚未运行本轮容量探针。正式测量等待集成负责人给出冻结提交及无其他压力任务的窗口。缓存正确性由独立验证组另行验收；本工具不修改交易、风险或存储实现。

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
python benchmarks/run_kernel_benchmark.py --expected-source <完整冻结SHA> --plan-only
python benchmarks/run_kernel_benchmark.py --expected-source <完整冻结SHA> --plan-only --hot-accounts 10 --hot-fraction .3 --order-distribution varied
python -m unittest discover -s tests -p 'test_kernel_benchmark.py' -v
python -m unittest discover -s tests -p 'test_group_benchmark.py' -v
```

获得调度窗口后，分别运行两个 cohort；不要并发执行：

```bash
python benchmarks/run_kernel_benchmark.py --expected-source <完整冻结SHA> --output /tmp/uta-kernel-primary
python benchmarks/run_kernel_benchmark.py --expected-source <完整冻结SHA> --output /tmp/uta-kernel-hot-varied --hot-accounts 10 --hot-fraction .3 --order-distribution varied
```

单次探针也可直接调用 `run_group_benchmark.py` 的 `--reserve-cache-size`、`--market-cache-size`、`--hot-accounts`、`--hot-fraction`、`--order-distribution`。旧运行时不支持非零缓存时明确报错，禁止悄悄退回未优化路径。缓存为零的旧参考运行时允许运行，并明确记录 counters unsupported；正式本轮 A/B 必须使用同时具备两类缓存 API 的冻结版本。

每个 run 留存 `arrivals.jsonl.gz`、environment、summary、manifest；cohort 额外保存 plan、逐 run UTC 开始结束时间、交替顺序、各对比率、median 和覆盖全部证据的 SHA256 manifest。硬件、CPU quota/affinity、Python/SQLite、文件系统、运行时代码和生成器摘要均保留。源数据库仅在本地保留以便再次检查，不发布合成数据库文件。

## 上线门槛、部署及回滚

此工具最多允许 10 秒到达窗口且没有持续行情 feeder。三次配对仅是短探针重复观测，不能证明统计显著性、最大容量、30 分钟稳定性、清算吞吐或生产验收。所有 run 的生产批准字段固定 false；cohort 退出成功仅表示工具完整执行及对账完成，不能作为容量门禁通过。未知、过载和晚到不因缓存收益而豁免。

工具部署无需数据库迁移或外部服务，只需该冻结提交和标准库 Python。启用非零缓存属于运行时配置变更，必须遵循集成后的运行时验收；工具支持立即用两个 size0 参数重测。回滚测量工具可回到上一提交；本轮不对已有生产数据库写入。失败时先保留 raw、manifest 和本地新建数据库，确认未知业务影响，禁止复用同一 output 目录覆盖原始证据或补写成功结果。

方案由性能组编写，独立验证组已审查同源码配对、全部订单 OPEN、含排空分母、未知不转 ack、热点订单上限和快照独立新鲜度的口径；该方法审查不构成真实资金或上线批准。
