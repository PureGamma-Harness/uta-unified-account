# PR58 rev2：独立金融 delta 复审

对象为 `a2e5db45620f9dbf6c34d4262cdbd50f359e8065`，原金融审查为 `40bee5ff668c20e31492ea5b2964242a31ad9b40`。**FIN-001/002 的作者回应足以作为 D0 规格澄清；两项实现/故障门槛仍 OPEN，D2 继续 BLOCKED。** 本次不改原规格、原审查或运行时，不授任何目标执行或生产许可。

[机器记录](../evidence/reviews/cross-engine-binding-rev2-financial/review.json) 核对原21个source pin记录与53ace完全相同、21项Git/blob/bytes/SHA吻合；新增15个引用全部吻合；已集成的四份原审查文件保持原字节。默认valuation10/order11/两缓存字段契约与原设计exact相等。D1文档引用只核固定字节，不代表其实现/目标运行通过。

## FIN-001：受限参考结算边界已澄清

修订3.2/3.3/5.2明确authority包含参考与共享模型/runtime、resolver、账务/仓位/费用/预占/fencing和恢复审计。仅candidate专属故障且这些权威条件独立可信时，才能走新的固定reference-only settlement opener。未知contract/分区、共享或reference失败、义务来源/权限不可证时，该入口也拒绝；不取inner十字段默认参考，不放宽原普通构造器和完整shadow审计。

客户mandatory标记或任意fill ID不能制造强制义务。原apply_fill仍是撮合确认前的本地授权，paired matcher整笔提交后才返回确认；原FILL_CONFIRMED名称不代表外部成交已先发生。新持久义务、两侧结算责任、幂等账务、原reserve和reference-only before/after恢复审计均需另行实现。candidate audit-after不得再次阻断此路径，reference-only replay也不能冒充完整shadow replay。

共享输入无报价/过期明确不算candidate-only，本文没有授予未审查的无行情结算降级能力。这些说明回应了原风险；它们尚非真实受限opener、分区anchor和恢复/故障证据，故FIN-001继续阻断D2。

## FIN-002：持久关闸顺序已澄清

每条新增风险在candidate检查/双算前先独立持久EVALUATING，同一account lane及本地latch阻止下一条风险穿插。成功的receipt、预占、账户影响与EVALUATING→OPEN在同一金融COMMIT。已知失败金融事务回滚后，EVALUATING仍持久存在，再以受信事务提交FROZEN、失败摘要与关联NOT_ADMITTED，确认后才返回确定shadow拒绝。

冻结存储失败或结果未知不捏造已冻结成功；HTTP503不等于业务REJECTED，更不能偷改旧inbox的PENDING/技术重试协议。正常可信业务拒绝在无金融影响时，以原拒绝终态与OPEN同事务提交。重启先经authority-only持久关闸，不先尝试候选；未完成EVALUATING/FROZEN不自动重开。必要结算与确认撤单有独立可信类别，客户不能自标。

这是对“金融回滚后才尽力冻结”窗口的有效规格回应。gate表权限/CAS、队列savepoint/receipt融合、Credit/直接服务旁路排斥、重启和每个崩溃边界均未实现或执行，FIN-002继续阻断D2。

## D2 实现前仍须落实的精确约束

1. **按原命令的历史gate revision恢复。** A成功曾以revision10同时写receipt和OPEN；之后B可合法进入revision11 EVALUATING或运营冻结。A回执丢失后的查询应返回A的唯一历史成功，保留B/控制的当前关闸。5.3.5的“成功与OPEN一致”应落实到A当时的原子transition，不能要求当前可变gate仍OPEN、把后续合法关闸当损坏或重开它。须有不可变关联证据，而不是只读当前row。
2. **金融提交未知不等于已知回滚。** FROZEN+确定NOT_ADMITTED只适用于已证没有提交影响的原命令。若COMMIT/ROLLBACK或freeze/stop写结果未知，保留关闸，查询原receipt/预占/账户影响及历史gate，再确定成功或未接纳；不把best-effort rollback、HTTP状态或单独冻结确认当作无金融影响证明。相同EVALUATING owner/revision的CAS与原命令核对必须覆盖此分支。
3. **恢复入口不成为信用或直调旁路。** 所有不支持的credit安装/borrow、资金/模式操作、旧构造器、直接service、worker/managed路径须在金融/能力影响前拒绝。恢复入口只消费可信既有义务和确认撤单，不能因shadow故障临时升权。本文不做通用security scan，也没有验证这些实际入口。

这些是已有D2开放门槛内的实现约束，不是已复现运行时缺陷；边界写清不等于验收关闭。需单独固定源和故障计划，包括成功后丢回执、后续gate变化、未知COMMIT、freeze写失败、排队与重开，且确认义务不丢、不重复。

## 人工例与验收范围

M09已明示proceeds-leave保守quote：USD11的quote10使压力权益1=MM1，严格边界拒绝；USD11.01时1.01>1。它不是借款现金留账后的实际权益或借款许可。

M04用独立stdlib Fraction从字面值复算：half fee.02、cash99.98、原reserve5.02、RO费reserve.02，当前IM5后available89.94；RO确认全成且自身reserve终结后cash99.96、available94.94；仍保留自身RO reserve的投影为94.92。不同逻辑时点已明确，差.02不是计算容差。

本次只有Git/文档/JSON与上述独立手算；目标import/compile/SQL/proc/CI/服务/生产计算执行均0。23个设计测试门槛没有由本审查运行。D1纯绑定另审源/计划，D2仍BLOCKED，D3/D4/生产/真实资金没有批准。

本提交只加两份review，revert即可回滚；不改变原spec、原21pins、四份旧review或任何金融数据。
