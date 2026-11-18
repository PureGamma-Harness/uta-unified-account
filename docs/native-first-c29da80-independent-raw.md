# Native 首次运行独立 RAW 验收

结论：**独立确认首次功能验收失败；原件及 SAFE 失败记录可接受。没有 native 功能、容量或生产批准，也没有重跑许可。**

审阅对象为源码 origin `c29da8040c0c5b1ed24b23f10edae5462d40b983`、外部见证 checkout `be373acef9f54db6acbc223011d81ee0b0c53b66` 的唯一首次运行，以及 SAFE 提交 `75fe3a16f7482a88e72b76f9a7801de5ef14aa83`。本审阅只读取封存字节、JSON、公开源码与 Git 对象，另写独立报告；未执行目标 import、编译、测试、SQL、worker、网络、进程探测、pidfd 或信号操作。

## 原件和源码绑定

独立逐项验证48个原文件、1,272,533 bytes、6个目录的完整集合、SHA-256、普通文件类型及0400/0500权限。数据库、WAL和SHM只按原始字节读取，没有作为数据库打开。审阅结束再次验证，原件内容和权限均保持一致。

完整私有索引 SHA-256 为 `a334abe3fbf563b0fc551b77e44d9f9288bfd947b3424d462874c80d8e6a78c6`，seal SHA-256 为 `e27f4fc0dc7af6750cf25e4060cccd2d71841a19c9d47e1eb6f15f54d04c8611`。匿名48项摘要与该索引逐项对应。

70项源码共1,490,898 bytes，其物理字节、origin与checkout两份Git字节、host和parent运行前记录均一致。保留的实际host源码副本也一致。固定plan SHA-256为 `a844eb613147ac52a65cc648f59c9cc408b8507e6459ad5d485695f5b2e41dbf`，manifest为 `e3c62d9ee7f2aac50eb1335835c60d45ca5fdd5eef71fb0d5a62150f10559c4e`；原记录的前后源码一致标志成立。当前静态比较不能补成完整加载模块、扩展或运行期内存证明。

## 退出与已出生 worker 的收口

外部工具终态明确记录host实际exit=1；内部host的 `actual_host_exit=null` 保持原值。host内实际parent wait exit=1、reaped=true、管道EOF完整、cleanup_errors为空。两个不同层级的退出事实没有混合。

本次只有cohort0的两个worker。两者的birth、注册held记录、host held记录与ACK在session、cohort、shard、nonce及稳定出生身份上逐项匹配；均有真实ready记录、parent实际wait exit=0/reaped、host所持pidfd死亡观察，parent清理记录均无强制kill或清理错误。死亡观察与实际wait分别核验。上述结论仅覆盖这两个已出生worker，不能扩展为计划四个worker的完整生命周期或所有异常路径均已验证。

## 功能拒绝门槛

| 项目 | 独立核验结果 |
| --- | --- |
| 计划两批，每批96条 | 仅第0批提供34条连续到达，第1批未启动 |
| 实际终态 | 25条SUCCEEDED、8条预设product_rejected/409、1条非预设router_halted/503 |
| 未提供负载 | 第0批终止后62条未offered；不得计作处理完成 |
| 原命令关联 | 34条回执与原CID、账户、条款及固定到达计划相符 |
| 25条接纳回执的预占 | 每条0.1004，合计2.51；仅回执核验，未完成存储重开验证 |
| 本地线程和队列 | 全部join，队列计数0、0 |
| 实际34条的超时/未知、enqueue/query技术事实 | 原记录均为0；不能外推到未执行负载 |
| 原件完整重开对账 | 固定混合断言失败，reopened=null，未完成 |

独立按16/s、62,500,000ns间隔及固定账户混合重建前34条预期，没有调用生产计算函数。异常为ordinal33的有效订单，其REJECTED回执明确记录 `router_halted/503`。它不能并入预设业务拒绝，也不能通过重新提交或查询后改写首次测量结果。

## 失败顺序与定位边界

相对cohort计划起点，行情发布调用从2.035847942s开始，到2.126235475s返回，调用跨度90.387533ms。ordinal33的503终态于2.112185351s被观察到；首个 `unexpected_terminal` fault为2.112196307s。随后 `fixed_market_feed` fault为2.126251038s。

行情发布返回比固定计划晚94.985475ms，超过原31.25ms完成门槛63.735475ms；启动延迟4.446719ms则仍在15.625ms门槛内。发布记录显示fanout回执SUCCEEDED、publishing=false、error=null，但halted=true，未到达后续activation。

固定源码的新行情发布先设置全局halt，成功fanout不解除halt；订单guard在halted或publishing时产生同一503错误。该路径和记录顺序支持发布屏障拒绝的定位。没有逐笔内部提交时间，不能断言完全排除其它因素，也不能把90.387533ms归因到锁、队列、计算或存储某一组件。

清理后确实进入只读对账调用；它遇到同一非预期拒绝后抛出固定混合AssertionError，因而没有返回完整报告。不能宣称26字段风险、订单、预占、审计、FIFO及账本均已核对，也不能把null解释成“没有差异”。

## 预算和 SAFE

host与parent记录的实际CPU affinity均为[1]；最后内部结果采样距host起点3.981060359s，处于原80+2s期限内。该内部采样不是外部实际退出完成时间，不能据此补成端到端硬实时保证。六份stdout/stderr原件均为空；结合工具输出、外部见证及每个已出生执行单元512-byte预留的保守计数为3,195 bytes，低于128KiB。原文件总量低于64MiB逻辑预算。以上不证明内核磁盘配额、任意C I/O可中断性、复制或故障恢复目标。

SAFE提交仅新增7个文件、53,353 bytes。其Git与物理字节、库存、34条逐字段白名单派生、行情相对时间、报告计数与故障顺序、两份wait、48项匿名摘要及源码定位均与原件一致。检查未发现原始运行身份、随机凭据、私有位置或绝对时钟进入公开文件。原SAFE的PENDING状态保留；本独立报告补充审阅结论，不修改既有提交。

两次独立元数据reader先后误判root授权字段的schema：count70被当成布尔值、NOT_RUN_AT_DECISION被当成null。两份失败reader及工具返回均保留，修正后完整reader返回0。它们是审阅工具的断言错误，不是目标重试；原件始终未修改。

独立reader、两次失败版本、核验结果与最终原件复核已另存私有17文件、116,148 bytes，seal SHA-256为 `a3f7abbb5ac6007579f79a228a70fe5c0daea2b5f502f2ecd23314b400908af6`。机器可读结论见[RAW-first-c29da80.json](../evidence/reviews/native-c29-first-independent/RAW-first-c29da80.json)。

## 后续门槛

当前一次性执行授权已经使用，原scope不得直接复跑。后续代码方案须明确行情发布期间订单的排队或拒绝契约，保留首次控制拒绝及计划到达延迟口径，解决发布完成预算，并通过新的CODE审阅、固定计划及独立原件验收。两批完整负载、四个实际worker生命周期和完整重开对账仍是未完成门槛；生产启用保持否决。
