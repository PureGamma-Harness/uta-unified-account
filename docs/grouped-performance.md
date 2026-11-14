# 持久批准入：独立开放环测量

`benchmarks/run_group_benchmark.py` 比较同一真实 `ExchangeService` 的同步持久准入和 `AdmissionBatcher` 组提交。它不使用研究模拟器，不生成成交，不在 arrival 内撤单或释放预占。**每个成功订单在结束后仍为 OPEN，账户保证金仍被占用。** 因此不能与早先“接单并撤单”的 308/549 等结果直接比较。

## 口径

- 独立生成器按固定 monotonic 计划到达，不等待前一个结果。调度落后仍保留原计划时间，不把计划改成实际派发时刻。
- sync 与 batch 使用相同共享 outstanding 上界，包含派发队列、运行命令、批准入队列和结果收集。每片 batch queue 不是额外可无限放大的缓冲。
- 所有账户预先拥有合成 USD 100,000,000；单一 BTC-PERP，数量 0.001、限价/mark 100、IM .1、MM .05、费用 .0004。全部有效订单在充足抵押下应被接纳；业务拒绝、技术失败、过载、未知及迟到各自保留，不计作成功吞吐。
- 默认 `--policy configured_cross`：持久化版本 1 产品目录与 PortfolioRules，USD 全额抵押/LTV1、无可借币配置、总借款上限0，BTC-PERP 单乘数、quantity step .001、tick .01、最小名义 .01、tier-1 IM/MM .1/.05。此数据的数值与基础参考模型相同，但实际通过 `_check_product`、统一 Cross `_risk` 路径。只有显式 `--policy legacy_reference` 才使用旧路径，结果标签不同，不能混合比较。
- 轮转账户分配固定，不用热点策略变化掩盖比较。配置限制每账户最多 900 个计划存活订单，防止 1000 挂单限制污染此短测。
- 输出按计划到达至成功 COMMIT 后 Future/函数可观察完成计时。内部 `admission_started_ns` 与 receipt 发布时刻仅是诊断；后者是 COMMIT 后上界，不能叫硬件刷盘的精确时间。
- batch 的 Future callback 只把结果放入 collector，不在 writer 内提交其他命令。同步模式采用相同 dispatcher 数；批准入每片一个 writer。报告完整记录这两种线程拓扑，不将单进程线程结果推广为多节点容量。
- 只支持 arrival/drain 各不超过 10 秒的探针，初始合成价格有效期 30 秒，无运行中行情 feeder。软 drain 预算超时不会杀死可能写入的线程；必须等所有承诺命令有最终结果，实际超额使 gate 失败。
- 所有模式的 SQLite busy timeout 固定为 **2 秒**，与服务默认 10 秒有区别；它不是 1000ms 软响应期限。出现 503 或未知结果不能事后通过调大超时将原数据改为成功。可取得的底层 SQLite 错误码/名称单独保留；没有记录的历史错误不能仅凭耗时推断其准确原因。

## 持久性核验

结束后重新打开数据库，逐个确认成功业务 ID 与 `ORDER_ACCEPTED` 一一对应，无重复或额外业务效果；全部订单仍存活、未成交。独立手算每单预占为 `.001×100×.1 + .001×100×.0004 = .01004 USD`，核对每账户总占用、现金不变和版本。最后验证逐币账本。数据库不是公开结果的一部分，报告只保留合成请求原始时间、计数、源码哈希、环境及 manifest。

成功响应丢失或 `admission_batch_failed/storage_unavailable` 保守地标记为结果未知，不计入已确认接纳吞吐。重新打开数据库后单列未知 ID 中已存在订单的数量和未见订单的数量；不能把事后找到的订单重新包装成及时成功回执。技术失败但不属于未知集合时，出现额外已提交订单则使工具完整性检查失败。每片还实际读取 `PRAGMA journal_mode=wal`、`synchronous=2(FULL)`，而非只相信配置说明。

短探针无论多快都不能通过持续 1800 秒、10,000 唯一持久准入/秒门槛；也不覆盖真实撮合清算、复制或金融签核。100ms P99 是待审批的临时工具目标，并非用户已经给定的正式 SLO。`--smoke` 只允许工具正确完成时返回 0，不修改 JSON 的失败容量门槛。

```sh
python benchmarks/run_group_benchmark.py --mode sync --duration 5 --rate 1000 \
  --accounts 100 --workers 4 --queue-capacity 1024 --smoke --output /tmp/admit-sync
python benchmarks/run_group_benchmark.py --mode batch --batch-size 32 --batch-delay-ms 2 \
  --duration 5 --rate 1000 --accounts 100 --workers 4 --queue-capacity 1024 \
  --smoke --output /tmp/admit-group32
```

每次输出 `arrivals.jsonl.gz`、summary、环境/资源及所有运行模块 hash、manifest。`unique_durable_accepted_per_s` 分母包含排空；按时成功率另列。端到端 P50/P95/P99/P99.9 为相对宽度不超过 0.1% 的直方图上界，逐请求纳秒值保持原始精度。没有逐笔数据库核验就不返回成功报告。

## 实测状态

工具与实际引擎联验后另行记录同配置重复运行的原始结果。没有将预计收益填作已发生结果；在硬件、源码与参数未固定前不宣称达到容量门槛。
