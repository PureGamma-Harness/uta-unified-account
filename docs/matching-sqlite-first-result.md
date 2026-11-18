# 首次原生 SQLite 双模式功能链路：通过，独立原件审查待闭合

唯一实际调用固定源 `3b0c49a6df6773ea7cdb208945541480ea091ea8`，清单SHA256
`de3944988def848c59c98cb8c2ab02f048d53cab406d6dc20de0f02dea6c7ada`。
八个全新合成私有库完成四场景，真实订单、对手成交、仓位和资金分录已提交。
这不是容量或生产验收；snapshot仍默认关闭，worker/CLI未启用。

| 场景 | scan 匹配 / fill | snapshot 匹配 / fill | 关键实际断言 |
| --- | --- | --- | --- |
| FIFO / STP / partial | 2 / 4 | 2 / 4 | 撤新自成交单，按同价时间成交；四账户各9999.96，剩余预占20.08 |
| 普通减仓连带取消RO | 3 / 6 | 3 / 6 | 后RO零成交且撤销；剩余仓位+1、成本100、现金9996.8012 |
| 第二侧seller冻结 | 0 / 0 | 0 / 0 | 实际account_frozen，BUY第一侧账本/仓位随savepoint回滚，BUY预占保留，只撤seller |
| 无流动性 / halt / resume | 1 / 2 | 1 / 2 | 不成交阶段财务不变；恢复后真实成交，双方现金各9999.9208 |

每模式六个匹配、十二个双侧fill。两个独立authority刻意复用相同合成业务ID，
不能汇总为全局唯一成交吞吐。seller冻结使用原生状态写入作为明确测试故障，
不是完整清算流程验收。

八库均重开后财务投影相等，完整ledger哈希链/分录、仓位数量与成本、订单预占/
费用累计、成交/订单/fill业务ID等通过；`Matcher.verify(strict=True)` 和已有独立
现金流/成本回放均通过，unpaired fills为0。六个非空库各抽一条实际FILL做历史
数值回放，六条matches=true；这不是所有决策都已重放的证明。

两模式经济投影与新鲜风险逐项exact。只按冻结计划排除三类时间字段，并将时间
派生的market snapshot引用在各自原行情中核验；没有对金额、价格、费用或业务ID
做容差归一化。完整SQL行、原始JSON、关键中间状态均保留。

实际Python3.12.14，SQLite3.53.1，affinity[0]（一颗允许CPU）。本次走builtin
`_sqlite3`分支：ModuleSpec/BuiltinImporter/builtin_names一致，path/SHA为null；
动态扩展分支仅CODE审，未在本次执行。解释器实际SHA256为
`fa67443527ed9647f760d807e2a38f26340757123e643c4639cf273ed15d5ea7`。
loaded libraries为null/NOT_OBSERVED，不读proc/maps，不宣称完整运行时证明。

首stdout 76,270B，SHA256
`6bf03110cad36fc4607c03a3ed96dc742813a48cd084ae3bcfd89463344a025b`；
stderr 0B；472行JSON含470个checkpoint，实际exit0。结果JSON在最终库存之前记录
driver10.072730762010906s；最终END记录10.144206064011087s，属于同次调用的不同
阶段。外层只有两段tool等待及秒级UTC观察，没有完整外层monotonic生命周期计时，
不能拼接两段或把driver时长称为E2E性能。

END最大已观察逻辑长度8,602,820B，低于64MiB。该数字不证明未采样的C内瞬时峰值，
也不是kernel目录quota或阻塞I/O硬实时保证。源63项原件/只读mini副本前后完全一致；
实际加载18个UTA模块的origin均来自mini source，不把63份源清单说成加载了63模块。
应用源码无worker/子进程/线程启动，末态Python线程数1；没有kernel线程枚举结论。

[完整首证据](../evidence/reviews/matching-selection-snapshot/sqlite-first-3b0c49a-once01/first-result-summary.json)
包括完整stdout/stderr/实际exit、11份私有报告的逐字节安全副本（4,906,804B）、
63源绑定、实际二进制描述和82项原库存。封存时只读核对原库存全部长度/SHA，
未再打开SQLite连接、执行目标或重跑。DB文件仍留新私有目录，未公开DB二进制。
独立原件审查尚待另一个工作组签工程范围结论；此文不是金融负责人签字。

原d517因metadata CODE缺口未执行，原清单/计划/物化记录仍为NOT_RUN/0attempt。
纯组件037首源码与原件、公开PR40候选及本轮金融运行时代码全部未改。

本结果只覆盖单进程合成USD legacy策略的线性小型功能链路。现货借贷、真实USDT/
USDC、配置策略模型、managed writer/fencing、跨进程并发、复制/HA、极端负载、
30分钟开放环与万笔容量仍需独立验收。无真实资金、产品启用或性能批准。
部署/回滚仍按[冻结计划](matching-sqlite-once-plan.md)：保留新库、WAL及原raw，不
删除重建、不自动重跑，也不替换旧authority正在运行的writer。
