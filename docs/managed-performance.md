# Managed process inbox 接纳诊断

`benchmarks/run_managed_benchmark.py` 是最多 10 秒的独立开放环诊断工具。它使用真实 DurableProcessRouter、spawn 子 PID、PID-bound token、持久 SQL fencing、required 决策审计及默认后台风险监督/撮合。没有复制、网络撮合或真实资金；不能称为 30 分钟稳定容量或 10,000/s 验收。

默认 100 个合成账户、2 分片/独立 worker PID、2 个 dispatcher，计划 20/s 持续 10 秒。主命令进程及其线程/子进程默认只绑定两个可用 CPU，主机整体配额另外记录；现有 24 小时作业和观察器继续共享同一主机，不被暂停或修改。每账户初始 USD100,000,000，所有单均为正向买单、成功订单持续 OPEN，保证金没有通过即时撤单或虚构成交释放。

## 接纳口径

每个计划到达使用唯一 command_id 和 order_id。原始 JSONL 记录计划、实际发出、开始入队、ACK、调用结束和 terminal 观察时间，包含完整 terminal result/error。`ack=durably_queued` 仅证明本地 WAL/FULL inbox 持久写入，不代表金融成功。只有只读事务观察到 `SUCCEEDED` 才计入金融成功；存储复开后还必须对应真实订单、持久预占、账户版本和审计记录。首次 ACK 丢失后，原 command_id 查询若返回真实 SUCCEEDED 可以证明该次接纳，但 enqueue technical error 仍单独保留，不能因恢复查询抹掉。

分别报告业务拒绝、控制门/行情拒绝、QUARANTINED 技术终态、durable queue full、本地 outstanding full、未派发期限、结果未知及排空时间。预设每第十笔使用 `.0005` 数量，违反 `.001` 产品步长；它先通过原 inbox 协议，再由实际金融风控产生产品拒绝。其余 `.001@100` 为有效单。拒绝不计成功。P50/P95/P99/P99.9 分别输出全部到达、真实金融成功、仅 enqueue ACK 三组。

collector 使用批量内部只读 SQLite 快照观察持久状态，以减少逐 CID 查询本身的额外事务。它是工程观测入口，不是客户 REST/WebSocket 性能。时间从原计划到达到 COMMIT 后的 terminal 观察，包含排队和 polling 上界；数据库 completed_at 是事务内写入时间，不能当成精确 COMMIT 时刻。

到达窗口结束继续派发已接纳的本地工作和观察 terminal，直到 drain deadline。未开始派发的本地工作不在 deadline 后补发；正在执行的入队调用等返回。所有原始结果保留。关闭 worker 期间刚确认的 SUCCEEDED 在最终复开中单列为 unobserved successes，不补进测量吞吐；关闭本身不伪装为排空。原始 PENDING 与其 ID 留在本地存储供调查。CLI 成功只表示工具完成和对账通过，容量/生产字段始终 false。

## 行情与控制开销

每 2 秒生成实际当前 UTC、新版本的合成 tick，标记价固定 100，IM .1/MM .05，调用真实受控 `publish_market`、等待 fanout，再显式 `set_kill_switch(False)`。每个新 tick 都归档完整 payload，不修改旧观察时间。新价格年龄上限 5 秒。publish 关闭全局 gate，因此期间的安全拒绝和控制等待是实际结果，单独保留；不绕过 barrier 来提高数字。

发布失败保留该实际 snapshot 和错误，不用刷新它的时间或假装重新激活。初始化、所有 publication、真实子 PID/token generation、队列历史、polling 异常和阶段 telemetry 均保留。后台默认 interval .1、account_batch25、matches_per_symbol10，没有关闭循环或改内存成功。全买单没有可匹配卖方，最终若有 fills/positions 反而使工具对账失败。

## 剖析与复开核对

`--profile` 只包装 worker 生命周期入口为 cProfile，每个真正独立 Python PID 保存原始 `.prof` 和文本统计，不替换金融、审计、SQL guard 函数。在 CPython3.12 同一解释器不能并发启用两个 cProfile owner，所以父进程只剖析 dispatcher0；所有 dispatcher 均有完整原始入队墙钟时间。首次工具自检遇到这项解释器限制后已修正；不把空 profile 当证据。

统计列出队列处理、金融风险、JSON/账务、writer_fence、decision_audit、storage 及 background 的函数调用次数、内部时间和累计时间。累计时间存在嵌套，不能相加为 CPU 百分比；profile 包含初始化、等待和停止，且有探针自身开销。首轮只用于识别瓶颈，后续优化必须同配置多轮、保留无 profile 对照，不与不同源码/硬件的历史 744/s 等数字拼接。

worker 真正退出后，独立 RO 重新打开每片：

- 原 CID canonical payload 与原 account/order/数量/价格一致；已 ACK 的入队历史不能消失。
- SUCCEEDED 与唯一 OPEN 订单、ORDER_ACCEPTED 事件、admission_decision_id 一一对应；REJECTED/PENDING/QUARANTINED 不得具有订单金融效果。
- 每笔预占手算 `.001*100*.1 + ceil(.001*100*.0004, USD1e-8) = .01004 USD`，逐账户求和；账户版本为初始资金入账版本1加实际接纳数。
- USD 现金不变，所有已接受订单保持预占，没有 fills/positions。required schema3、审计 identity 和 pre/post version 校验。
- 不调用生产 ledger 计算函数，独立按整数 posting 重算逐币平衡、事件 fingerprint/hash 链和余额投影；同时做 integrity_check、foreign_key_check 和 WAL 检查。

SQLite financial/metadata busy timeout 保留实际服务默认 10 秒，没有为探针改短。响应期限默认 1 秒，与 busy timeout/control timeout 独立。durability 是单主机本地 WAL/FULL；不提供复制确认或 AZ 容灾证明。

## 复跑、部署与回滚

```bash
python -m unittest discover -s tests -p 'test_managed_benchmark.py' -v
python benchmarks/run_managed_benchmark.py --output /tmp/uta-managed-profile-unique --duration 10 --rate 20 --accounts 100 --shards 2 --cpu-limit 2 --profile
```

每次使用新的合成 authority，保留实际源码 SHA、全部 Python 源 hash、环境、原始到达/telemetry gzip、完整控制结果、原始 profiles、manifest 和重开核对。长稳生产者 887 与只读观察器不变 source、不变 PID、不改其资金库或历史起点。测试控制台退出后必须核验这些已运行作业的 heartbeat，没有将其饥饿作为提速手段。

部署仅需固定 checkout 和标准库；回滚是停止本次独立探针并保留其 authority/原 ID，不能删除 PENDING 后宣称没有未完成。工具不升级既有 authority、不改变 lease 控制 schema、不改经济 layout 或生产默认。运行中源码必须保持不可变；没有达到正确性与持续容量门槛之前，生产批准为 false。

## 887 长稳起止锚的只读分析

实际 job.started_ns 为 1794864973820942405，首 session.started_ns 为 1794864973825199889，两者差 4,256,484ns（4.256484ms）。单调 active 起点在 session INSERT 前，和原 wall deadline 存在初始化毫秒差。原实现到 wall deadline 后还执行 worker/feed join、完整只读最终验证，最终 heartbeat 将这些真实执行时间计入 active，通常会覆盖几毫秒差，但没有保证。

因此理论上可能出现 wall 已满 86400 秒、strict active 略少而 false-negative。当前 source/job 一字未改，也不能加 epsilon、回填暂停或改 start 来硬判通过；若实际终态短缺，应原样未通过。下一版可统一实际单调起点/截止，并分开报告生成器、持续 feed、排空和终检的运行时间；新版本需要新候选，不套用本次历史计时。
