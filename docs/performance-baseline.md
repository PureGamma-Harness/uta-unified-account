# 性能证据与开放环基准

当前没有通过「持续 30 分钟、每秒 10,000 个成功持久化交易操作」的验收。下面的短测只建立工具与瓶颈基线，不能替代撮合、端到端结算或故障恢复压测。

## 原有数字的证据缺口

本轮读取的原始 `main` 为 `30deff6`。该提交的完整文件清单不含性能脚本、原始逐请求记录、硬件配置或性能报告，下面的检索没有找到 `10809`、`10,809`、`625` 或 `359`：

```sh
git ls-tree -r --name-only 30deff6
git grep -n -e 10809 -e '10,809' -e 625 -e 359 30deff6 -- . ':!LICENSE'
```

第二条命令退出码为 1，仅表示该提交中无匹配。无法从这些材料复现所称的 10,809 / 625 / 359，也不能确定它们是否指纯计算、接单、成交、清算，是否包括拒单和持久化，或用了何种硬件和时间窗口。这里不把缺少证据当作数字为假的证明，也不把它们作为本次优化的对照组。

## 工具口径

`benchmarks/run_benchmark.py` 使用一个独立的主进程产生预定到达时刻，多个进程执行工作，工作与结果队列均有容量上限。请求排队或生成器落后时保留原来的 `scheduled_ns`，不会在前一请求完成后才产生下一请求，从而避免封闭环压测漏掉排队时间。

三种场景分开记录：

| 场景 | 每个到达执行的工作 | 不包含的工作 |
| --- | --- | --- |
| `compute` | 一个具有 USD 抵押及三个线性持仓的风险快照计算 | 持久化、HTTP、接单或撮合 |
| `order` | 可信新鲜行情下，持久化接纳唯一限价订单，然后执行独立事务本地撤单 | 成交、撮合、资金结算和外部交易所 |
| `liquidation` | 内存清算状态机的撤单、确认与减仓建议 | 持久化清算执行、真实减仓与风险恢复 |

`order` 的撤单成本包括在吞吐和延迟中，使 live orders 数量受控；这不是只测一条 SQL。行情发布进程每 0.5 秒更新一次合成行情，服务沿用实际时钟和时效校验。产品按 BTC/ETH/SOL 三个合成线性合约轮转，保证金率为 10%/5%，美元资金完全合成。`--shards` 使用独立数据库，不能把多分片结果称作单个数据库吞吐。`--account-skew` 把指定比例流量集中到第一个账户；实际分布也可从逐请求记录复算。

每次运行输出一个新目录：

- `arrivals.jsonl`：逐到达的唯一序号、预定/开始/完成纳秒时间、产品、账户、worker、结果和持久化确认。工作队列满记录 `overload`，未取得最终结果记录 `unknown`，不会用拒单或重复响应增加成功吞吐。
- `summary.json`：p50/p95/p99/p99.9、唯一结果计数、拒单/技术故障/软超时/未知/过载、吞吐分母、产品分布，以及数据库中唯一订单和接纳事件数量。
- `environment.json`：源码 commit、dirty 标记、关键模块及生成器 SHA-256、Python、CPU 型号/数量/affinity、cgroup CPU/内存限制、SQLite 版本、WAL/FULL 配置与文件系统。
- `--profile` 额外产生 worker 的 cProfile 文件。性能分析本身有开销，不能把带 profile 的短测视作最大容量。

`latency_ms.all` 从预定到达时间计算到最终完成，包括排队；`service` 从 worker 开始执行计算，不包括排队。`durable` 包含迟到的成功接单；`successful` 只包含在 `--timeout-ms` 软期限内完成的成功操作。超时不会取消已提交事务：`deadline_exceeded` 与 `durable_committed` 可以同时为真。完整成功接单率、按时接单率和已确认持久化率分别报告。吞吐分母包括排空时间，避免把窗口结束后的完成计入短窗口来抬高吞吐。

百分位是相对桶宽 0.1% 的直方图上界，整数纳秒取整另有最多 1ns 误差。逐请求原始纳秒值保持精确，可离线计算精确分位数。原始记录按唯一序号去重计数；队列满和未知结果不会从 offered 数量中消失。

## 重现与门槛

工具 smoke 可执行：

```sh
python benchmarks/run_benchmark.py --scenario compute --duration 2 --rate 100 \
  --workers 1 --smoke --output /tmp/uta-compute-smoke
python benchmarks/run_benchmark.py --scenario order --duration 2 --rate 100 \
  --workers 2 --accounts 20 --shards 1 --smoke --output /tmp/uta-order-smoke
```

`--smoke` 只让工具检查成功时退出 0，不会修改报告中的验收结果。默认 capacity 门槛是接单成功率每秒 10,000、到达窗口至少 1800 秒、无技术故障/未知/过载/软超时，以及 p99 不超过 100ms。100ms 是本轮工具的临时目标，用户尚未给出正式延迟 SLO，不能把它描述成已确认的业务要求。参数可显式调整，但报告记录实际门槛。

不加 `--smoke` 时，门槛不满足退出 2；运行失败退出 1。纯计算和内存清算场景不满足持久化交易验收口径。即使 durable admission capacity 门槛满足，`phase1_exchange_acceptance_passed` 仍为 false，因为此工具没有真实撮合工作负载。

```sh
python benchmarks/run_benchmark.py --scenario order --duration 1800 --rate 10000 \
  --workers 4 --accounts 100 --shards 1 --queue-capacity 4096 \
  --timeout-ms 1000 --output /srv/uta-bench/order-30min
```

正式性能验收需要先实现并固定真实撮合/结算场景、产品和账户分布、时效与故障策略、正式延迟 SLO 和目标硬件，再在隔离资源上运行 30 分钟。此示例仅演示参数，本文未执行该长测。

## 本轮短测与 profile

原始结果保存在 `benchmarks/results/20261114-v1-*`，压缩的 `.jsonl.gz` 保留逐请求记录。各目录的 `manifest.json` 记录文件 SHA-256；`summary.json` 是完整结果。两个场景顺序执行，均开启 cProfile，使用共享执行环境而非专用性能机器。

本轮生成器代码为提交 `1fc126a`，SHA-256 为 `532e903df0f24f202fbd7ed92e40366ea466cbde8d6afec41bb01de2638fb277`，通过 `PYTHONPATH=/workspace/uta-unified-account` 引用集成工作区。各关键源码 hash 已保存。后续版本的工具默认固定到脚本所在 checkout；开发者可用 `UTA_BENCH_SOURCE_ROOT` 显式选择其他 worktree，实际加载路径和 hash 始终进入报告。

| 5 秒到达场景 | offered | 完成/接纳 | 队列满 | 含排空吞吐 | 预定到达到完成 p99 |
| --- | ---: | ---: | ---: | ---: | ---: |
| 三持仓纯风险计算 | 50,000 | 39,016 次计算 | 10,984 | 7,079.68 次计算/秒 | 647.65ms |
| 单分片接单并本地撤单 | 5,000 | 2,722 个唯一接纳 | 2,278 | 345.54 个接纳/秒 | 3,030.78ms |

订单短测的数据库中恰有 2,722 个唯一订单和 2,722 条 `ORDER_ACCEPTED` 事件。2,242 个接纳完成超过 1 秒软期限，按时接纳率只有 60.93/秒；没有业务拒单、技术失败或未知结果。worker 内执行的 p99 为 81.89ms，明显小于包括排队的 3,030.78ms，说明仅报告函数执行时间会掩盖过载。以上数字都未满足正式门槛。

计算 profile 中 `calculate_risk` 累计 7.56 秒，其中 Fraction 构造累计 2.45 秒。订单 profile 中 SQLite `execute` 函数内累计 9.506 秒，`commit` 2.815 秒，风险计算累计 0.753 秒、行情 JSON 反序列化 0.587 秒；时间是多个 worker 的累计值，不能与单个墙钟窗口直接相除作为 CPU 利用率。下一步优先检查事务数量、连接创建和写锁/同步路径，在不改变一致性和 FULL durability 的条件下再测。

短测命令：

```sh
python benchmarks/run_benchmark.py --scenario compute --duration 5 --rate 10000 \
  --workers 2 --queue-capacity 4096 --timeout-ms 1000 --drain-seconds 10 \
  --profile --smoke --output /tmp/uta-compute-baseline
python benchmarks/run_benchmark.py --scenario order --duration 5 --rate 1000 \
  --workers 2 --accounts 20 --shards 1 --queue-capacity 1024 \
  --timeout-ms 1000 --drain-seconds 10 --profile --smoke --output /tmp/uta-order-baseline
```

性能结论只适用于各 `environment.json` 所记录的版本与环境。硬件型号为 AMD EPYC 9V74，但进程只看到 5 个 affinity CPU，cgroup CPU 配额是 4 核，内存上限 16GiB；不能按宿主机型号上的 80 核解释结果。源码工作区可能同时有未提交集成文件，报告保留 dirty 标记及各模块 hash，因此这些结果用于诊断而不作为固定发布版本的容量认证。

Profile 可指出 Fraction 转换/精确算术、JSON、SQLite execute 与连接开销的占比，但 cProfile 不能把 SQLite 内部锁等待、SQL 执行和内核 fsync 时间完全分开。需要额外的 syscall/块设备观测才能声称 fsync 是唯一主因；不能为了得到更高数字关闭 FULL durability、跳过 journal 或把拒单计作成功。
