# Native 首次失败：封存、SAFE 派生与静态定位

结论：**FIRST_FAIL，未重试，未通过功能门槛，未完成重开对账，未获容量或生产批准。** 本提交只读取已经结束的一次运行及固定源代码，封存原件并生成公开摘要；不修改目标源、不启动目标、不执行 SQL、目标 import、编译、测试、进程探测、网络或复跑。

原运行源提交为 `be373acef9f54db6acbc223011d81ee0b0c53b66`，code origin 为 `c29da8040c0c5b1ed24b23f10edae5462d40b983`，plan SHA-256 为 `a844eb613147ac52a65cc648f59c9cc408b8507e6459ad5d485695f5b2e41dbf`。保留的 host 源字节与该固定提交相同；这项静态比较不替代运行中完整源证明。

## 原件与退出证据

完整原件共 **48 个文件、1,272,533 bytes、6 个目录**，包含根授权记录、外部实际退出见证、两侧运行记录、到达/行情/清理记录、标准输出/错误和存储文件。原路径保留，原有文件内容没有重写；所有原文件权限为0400，目录为0500，权限封存前后逐文件 SHA-256 相同。存储文件仅按原始字节计算摘要，没有打开数据库或执行查询。

私有完整 seal index 的 SHA-256 为 `a334abe3fbf563b0fc551b77e44d9f9288bfd947b3424d462874c80d8e6a78c6`；seal 记录的 SHA-256 为 `e27f4fc0dc7af6750cf25e4060cccd2d71841a19c9d47e1eb6f15f54d04c8611`。公开 [seal-inventory.json](../evidence/reviews/cross-open-loop-pilot/native-first-c29da80-safe/seal-inventory.json) 逐项保留原文件序号、大小和摘要，完整位置映射留在私有原件索引。

内部 host 记录的 `actual_host_exit` 为 null，并明确要求外部见证；没有把这个 null 改成成功或自行补写退出结果。根代理外部工具见证记录实际 host exit=1、工具会话已结束、未自动重试；parent 的实际 wait exit=1 且已回收。两个 worker 的原始 wait 结果均为0、已回收，原持有句柄记录均观察到死亡，未使用强制清理信号，未记录清理错误。这里仅对已经存在的记录做静态关联，没有重新观察运行中的进程。

## 有限结果，不能称为对账成功

| 项目 | 记录值 | 含义 |
| --- | --- | --- |
| 计划 cohort | 2 | 仅第0组写出报告，第1组未启动 |
| 第0组计划到达 | 96 | 实际仅 offered 34，终止后未 offered 62 |
| `accepted_persistent` | 25 | 观察到25条 SUCCEEDED 持久终态回执；未完成重开逐笔验证 |
| `business_rejected` | 8 | 均为预设 `product_rejected/409` |
| `control_market_rejected` | 1 | 非预设业务拒绝；`router_halted/503` |
| 观察到终态 | 34 | 不表示全部计划96条已执行 |
| 生产者线程 | 已 join | 本地待派发队列计数为0、0 |
| 超时/未知、enqueue/query 技术事实 | 记录均为0 | 仅限实际 offered 的有限观察范围 |
| `reopened` | null | 重建步骤抛出断言，没有返回完整对账报告 |
| 功能、官方容量、生产门槛 | false | 原运行及本派生均不批准 |

`cohorts_completed=1` 是主程序已收集一份 cohort 报告的计数，不是“第一组功能验收通过”。25 条接纳也不能表述为25条订单、风险审计、预占及账本已完成重开对账。

## 事件顺序与明确错误类别

以下时间均相对第0组计划起点，不公开绝对时钟或执行身份。

| 相对时间 | 事件 |
| --- | --- |
| 2.031250000s | 第一笔固定行情计划发布时间 |
| 2.035696719s | feeder 开始，start lateness=4.446719ms，未超过15.625ms限制 |
| 2.035847942s | 调用 `publish_market` |
| 2.062500000s | ordinal33 订单计划到达，预期应通过 |
| 2.067767455s | ordinal33 开始 enqueue |
| 2.086351720s | ordinal33 取得 enqueue ack |
| 2.112185351s | 观察到 ordinal33 的 REJECTED / `router_halted/503` |
| **2.112196307s** | **首个 fault：`unexpected_terminal` / RuntimeError** |
| 2.126235475s | `publish_market` 返回；publication call=90.387533ms |
| **2.126251038s** | **随后 fault：`fixed_market_feed` / AssertionError** |
| 清理后 | `readonly_reconcile` 因同一非预期终态拒绝抛出 AssertionError；`reopened=null` |

行情完成相对其计划时间的 lateness 为 **94.985475ms**，超过31.25ms限制 **63.735475ms**。原 fixed-feed 记录表明 publication 已不再 publishing、返回 error=null，但仍 halted=true；没有记录后续 activation。不能把完成 fanout 等同于已经开放订单准入。

### NFF-001：发布屏障拒绝订单

固定源码 `uta/durable_process.py:1546` 在每次新行情发布时持久设置 `halted=True, publishing=True`；`1566` 的成功 fanout 分支只清除 publishing，并不解除 halt。重新开放由后续 `set_kill_switch(False)` 完成。

`uta/sharding.py:803` 的 `ShardWorkerView._command_guard` 对 SUBMIT_ORDER 检查该状态；`809` 在 halted 或 publishing 时抛出 `router_halted/503`，错误消息与 ordinal33 原始回执一致。该订单的 enqueue 与终态观察均在本次 publication 调用窗口内。这构成**观察到的发布屏障拒绝及直接代码路径定位**；不需要也没有打开存储去重新推断内部提交时刻。

`benchmarks/cross_open_loop_pilot.py:172` 把状态码≥500的终态归入 control_market_rejected；`178` 对非预定业务混合发出 fatal。正确保留了首次控制故障，没有把它改成预设25%业务拒绝或补发同一逻辑订单。

### NFF-002：固定行情完成超时

`benchmarks/cross_open_loop_checks.py:73` 的 `require_feed_timing` 对 after_publish/after_activation 使用31.25ms限制，`82` 严格比较计划到达时间。pilot 在 `230` 于 publication 返回后立即检查；本次94.985475ms已超过限额，因此 `232` 的 reactivation 尚未执行就进入 fixed_market_feed fault。

这项超时发生在首个 unexpected_terminal **之后**，不能替换最先失败的事件，也不能把有限证据改写为“只有 feed 超时”。现有记录不能再细分90.387533ms由账务、队列、锁、调度或存储哪一部分造成；本提交不作这些归因。

### NFF-003：重开对账未完成

`benchmarks/cross_open_loop_reconcile.py:73` 只允许预设业务拒绝 `product_rejected/409`；遇到 router_halted 时在 `74` 抛出固定断言。pilot 捕获后记录 readonly_reconcile fault，保留 `reopened=None`。调用路径可能已经执行部分只读检查，但没有返回完整结果；不能推断所有 shard、订单、风险审计、预占、账务、FIFO 与来源验证都完成。

## 公开文件与派生规则

- [report.json](../evidence/reviews/cross-open-loop-pilot/native-first-c29da80-safe/report.json)：有限计数、失败顺序、退出/清理与证据限制。
- [arrivals.json](../evidence/reviews/cross-open-loop-pilot/native-first-c29da80-safe/arrivals.json)：34条逐项 ordinal、合成条款、有限错误类别及相对时间；不含完整回执身份。
- [fixed-feed.json](../evidence/reviews/cross-open-loop-pilot/native-first-c29da80-safe/fixed-feed.json)：相对时间、deadline计算和经过白名单选择的 publication 布尔事实。
- [source-map.json](../evidence/reviews/cross-open-loop-pilot/native-first-c29da80-safe/source-map.json)：固定公开源文件摘要、定位行及未证明范围。
- [seal-inventory.json](../evidence/reviews/cross-open-loop-pilot/native-first-c29da80-safe/seal-inventory.json)：全部原件的匿名摘要索引。

JSON 逐字段白名单派生，没有复制整份 intent、receipt、quote、control state、设置或清理对象。原始执行标识、随机凭据、账户/订单/命令标识、私有位置、绝对时钟及权威代际均不进入公开派生。公共仓库内的源文件名仅用于定位固定代码。原件和派生之间通过不可逆摘要关联，原件保持完整并交独立验证组审阅。

## 处理范围与下一门槛

本提交执行的只有数据读取/摘要/权限封存、公开源字节静态读取、派生文件写入和 Git 提交；没有目标重启、补跑、存储修复、阈值放宽、预设业务比例变更或源码修复。当前结论保持 FIRST_FAIL，原 source/plan 不获得第二次执行许可。

下一步先做独立 RAW 审阅：核对外部退出见证、48文件 seal、两个 worker 的原始 wait 与持有句柄记录、34条原始回执、feed/首次 fault 顺序和未完成重开限制。若审阅认可定位，再单独提出代码方案与新验收计划，明确行情发布期间的订单排队/拒绝契约及可达的完整发布时间预算；不得靠隐藏控制拒绝、延迟重置到达时间或改成功计数来通过门槛。

独立 RAW 审阅状态：**PENDING**。没有签字，没有上线批准。
