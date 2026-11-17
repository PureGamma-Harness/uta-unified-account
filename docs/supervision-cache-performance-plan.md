# Optional NORMAL cache：独立审查与下一阶段对照计划

状态 **PLANNED / NOT RUN**。本文件没有授权或启动性能负载。默认
`normal_cache_size=0` 保持不变；生产、10,000/s 和持续稳定性验收均未通过。
执行前由集成负责人冻结完整 SHA、完成最终正确性/安装/CI 门槛并明确 GO。
原7a06探针含 I/O522，不能充当收益基线或与新源码计算提升百分比。

## 审查对象与结论边界

本次只读检查运行候选 `190aa9ba8e99da2306a6dec3d1cc62e2cb93b9d8`、实现组真实
managed 生命周期测试 `cb85d6896ada7319c81bebd3a67db72da2cd10d8`、独立验证
`639a2db24991b2b6b8ca61215a3939b1d0c4a9be`。独立测试工作树基于根
`e033c43142d4ca70dc1076de68683a40990fa385`，分别复制前两项为
`2af9283`、`c745dad`；这些是依赖，不能当成本组的运行实现贡献。

独立639的14项测试覆盖同事务 pre/post 证明、真实并发扣款、COMMIT失败/响应丢失、
完整风险输入、过期报价、公平游标及真实原版5c53的十个财务检查点。
cb85另有真实子PID开仓、两笔部分清算和owner替换。它们是有界正确性证据，
没有证明吞吐收益、最坏监督年龄或缓存启用适合所有产品。

证明只有在原监督返回且持久状态为 NORMAL、前后经济输入一致、外层 COMMIT 成功返回后
才发布。未命中时原事务内调用监督；命中只省略重复的 NORMAL 监督，不授权新单、资金、
成交或清算完成。`supervise_account(connection=...)` 经 `_using` 检查事务、数据库和
writer角色；匹配、准入和资金写入保留其当前事务内 SQL fencing、行情与审计检查。
`run_once` 的只读快照也经持久 control/data guard 验证，不是裸 SQLite 读后直接信任缓存。

缓存完整包含 liquidation row（state/cycle/revision/plan字段）、账户、余额、仓位、
gross本金/利息、所有live线性/现货订单、市场完整字节、配置及运行政策；核心表的
`sqlite_master` 表定义与 `uta_schema` 版本行也在依赖中。ledger head 属于同一分片
共用依赖。SHA256抗碰撞及 worker 生命周期内配置/代码不可变是前提；新产品、表、
风险模型或读取依赖变化必须重新审查，不支持热 monkey-patch 后继续使用旧证明。
这不是完整 journal/audit 校验的替代，也不证明任意宿主越权篡改安全。

## 必须实测的成本与失效来源

一次有缓存的批次先取一份 RO 快照，构造公共依赖，再逐户加载live业务行、生成字典、
排序序列化 JSON 并哈希。一次 miss 还在真正监督事务前后各重新构造完整依赖。
按当前实现、不含原风控和guard内部SQL，公共依赖至少6次SELECT，每户6次SELECT，
存在现货订单表时为7次；miss两遍因此额外至少24/26次SELECT及相应JSON/SHA工作。
这些是静态查询数，不是耗时测量。不得删掉安全依赖来获得命中或降低这项成本。

风险状态和余额小的账户可能重新计算更便宜。持续OPEN订单使每户扫描/序列化随live订单数
增长；LRU容量有界不等于瞬时扫描内存、RO事务占用时间和WAL增长已经有充分容量保证。
每轮仍有游标写入及真实matching，缓存没有使整个worker变成只读。

同分片任意现金journal追加（别的账户也一样）改变全局ledger head，使此前证明保守失效；
每个新行情tick亦改变全片key。单向OPEN接纳通常不追加现金journal，只改变该账户订单和
版本；因此它可能比真实成交/费用/借贷流量更利于命中。静止NORMAL样本只能是机制上限
诊断，不能代表活跃交易收益。reserve/market数学缓存在本次对照两臂均保持0，避免混淆。

## t0、公平与故障资格

命中在每轮一致RO快照的逻辑时点t0成立，`snapshot_started_ns/completed_ns`只是其观察
区间。t0后提交的风险变化可以要到后续访问才被监督；缓存不是随后所有时刻的当前风险。
命中消费前仍用实际时钟复查报价年龄，不能刷新旧tick或跳过过期拒绝。

固定N账户、批次B时，`ceil(N/B)+1`是从任意游标开始的保守复访轮数上界；它既不是
毫秒SLO，也不覆盖账户不断增长、进程暂停或存储阻塞。记录实际每轮选中账户、t0区间、
轮次完成、下一次选择年龄与风险发现时间。不得用 `bound * background_interval` 代替
测量，因为本轮执行时间在配置interval之外，且miss/真实撮合会增加工作量。

启用前还需独立warm-cache故障证据：确认真实hit后撤销/接管SQL lease，旧owner不得写；
真实lease过期不能renew复活；持久guard缺失/变弱及required审计guard损坏不能被缓存掩盖；
warm miss的真实COMMIT失败/响应丢失不能发布新证明。所有隔离合成故障保留故障前manifest、
故障后原样状态和原ID核对，不自动修回后隐去故障。专项测试范围与结果另记，不能把测试
耗时当性能证据。当前实际24小时旧producer及observer不在该候选覆盖范围内。

## 开跑前的工具准备门

既有managed工具目前没有 `normal_cache_size` 对照开关；本文件没有提供可运行的A/B命令。
须先单独提交工具及测试，显式传参、记录两个cache容量与真实runtime默认值、支持成对
schedule hash和每次独立authority复开核对，并纳入最终冻结。预注册的修复后普通基线
[五次计划](managed-baseline-plan-20261117.md)继续独立保持PLANNED。

managed父pipe目前没有后台cache counters，不能把诊断ready或监督调用减少量冒充命中率。
主性能结果先用未插桩真实managed路径；若要收集child round/stats，必须新增并测试有界的
独立诊断适配器，两臂同源码、相同适配器设置，成本单列。仅可记录原 `run_once` 返回后
的报告/计数，不改其结果、金融函数、依赖、gate、租约或后台调度。不把插桩样本混进
未插桩主结果。独立PID cProfile另列，禁止用父线程混合profile做精确成本分摊。

## 相同源码的分层对照

所有case固定同一已验收SHA、Python/SQLite、WAL/FULL、required audit、真实PID/SQL fence、
2分片、100账户、account_batch25、background .1s、lease5s、worker/observer poll .02s、
两CPU affinity和同机长稳背景。A为cache0，B为每worker cache128；实际每分片账户数先记录，
超过128应改计划后重冻结，不能跑后改容量。新service cache初始为空，控制准备期间可能
已实际监督，首arrival时的warm程度必须记录；不加隐藏预热或删掉慢的冷启动样本。

每个cohort三对次序预定为 **A/B、B/A、A/B**。每run使用新合成authority及同样相对计划
到达schedule；到达时间仍从原planned时刻算，含队列和terminal观察。fresh feed保存实际
UTC/版本，不为了两个hash一致伪造相同旧观察时间。报告全部run、每对差值和范围；
三对短样本不声称统计显著性或最大容量。先20/s×10s，不达正确性门不加压。

| cohort | 输入及目的 | 与接纳成功分开的计数 |
|---|---|---|
| C1 primary | 原单向OPEN接纳与10%非法步长，20/s×10s，2s真实新tick。 | 200planned、ACK、金融terminal、业务/门控拒绝、unknown/late、最终OPEN和预占。 |
| C2 ledger churn | 相同接纳，加真实独立产品、独立对手账户的低频双向roundtrip；必须同一目标分片。 | 每roundtrip预先定义4order、2唯一match、4fill腿与实际账本费用；未成交不补假fill。 |
| C3 many live orders | 离线/预窗口通过正常准入预建每户100个同向OPEN订单；两臂相同payload和reserve。 | 预建10000单单列setup，不算到达或完成量；新单后RO逐单手算累计reserve。 |
| D1 supervision age | 独立确定性诊断，在warm hit的t0之后以真实资金命令提交风险变化。 | 资金COMMIT、后续t0/访问轮、首次实际非NORMAL持久状态、所有实际排队/发现时延。 |

C2在同100户中预留两户作对手，新增接纳轮询其余98户，单列该cohort的分布；对手与
独立产品不能侵入C1挂单盘口，避免把原本应持续OPEN的订单意外成交。
若独立产品两次均以100成交`.001`、费率`.0004`，每roundtrip应有4order/2match/4fill腿，
每户费用`.00008 USD`、合计`.00016 USD`、实现PnL为0且最终仓位归零；没有成交就保留
在途义务，不能凭计划数量填写这组golden。
须在开跑前固定完整新catalog、settlement、账户→分片和所有command IDs，独立手算费用/
PnL/双分录；仅适配器准备完成后才能执行。所有baseline/opt配置完全相同，唯一变量为
normal_cache容量。先一对C2正确性短测，再由集成负责人按实际结果决定余下两对是否值得跑。
C3亦须预先验证每户订单上限/有界内存；它是序列化成本诊断，不是长期稳定性。
D1不能通过重标行情或直接编辑生产余额制造风险；若公开资金路径无法表达所选合法冲击，
就保留独立故障测试语义，不冒充客户路径延迟。

## 报告、停止与回滚

主报告分别列所有计划请求与金融成功P50/P95/P99/P99.9、数量、最大值、迟到；ACK、
业务/技术/门控拒绝、队列满、QUARANTINED、timeout/unknown、排空/关闭和复开才发现的成功
分开。超期是成功的子集；enqueue ACK、拒绝或关闭后发现的成功不回填按期吞吐。
性能归因另列每PID CPU、RSS、读写/COMMIT次数、WAL/DB大小、queue、market age、实际feed
publication时间、依赖查询/JSON/SHA、原监督/风控/审计/fence、matching、真实hit/miss/
eviction/ineligible和snapshot/round年龄。原始profile、stderr和负收益全部保留。

逐CID复开mode=ro核对订单/预占/账户版本/required decision、整数ledger/hash链；C2还要
逐unique match/fill/position/费用/PnL对应。任何I/O、guard/audit/fence失效、原ID重复作用、
失联heartbeat、风险延期超预定可接受阈值或不能解释的金融差异，停后续case并保留authority。
剩余时延阈值需由金融规则与独立验证组在执行前签定，不跑后挑选。

主机仍共享旧长稳，所有额外短计算按根负责人窗口一次一组；不得暂停或改写其历史计时。
没有复制/RPO证明。禁用缓存需停止入口、查询/排空原CID、正常关闭并以新owner cache0重开；
无需schema迁移、改账、释放订单预占或恢复缓存。实际负收益或检测时延不合格时维持默认0。
