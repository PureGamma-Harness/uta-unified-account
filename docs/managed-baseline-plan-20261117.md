# 修复后 managed 接纳基线：预注册计划

状态：**PLANNED / NOT RUN**。本计划没有启动负载、改变运行中的 producer887 / observerf96，也没有选择尚未完成验收的候选作为基线。最终源码由集成负责人完成只读 mode=ro 修复、三组真实 runtime 和四组 CI 后给出完整 SHA，再明确 GO。

原7a06探针包含 I/O522，且存在已独立复现的 POSIX-close 应用锁缺陷，已被否决为稳定性证据。本轮是新的独立基线，不以它计算优化收益或“修复提升百分比”。原始200/171等记录和失败说明不改变。

## 五次有界执行

| 顺序 | run_id | 到达率 / 窗口 | 计划数量 | profile | 目的 |
|---|---|---:|---:|---|---|
| 1 | B1 | 20/s / 10s | 200 | 关闭 | 新候选普通接纳观察 |
| 2 | B2 | 20/s / 10s | 200 | 关闭 | 同配置重复 |
| 3 | B3 | 20/s / 10s | 200 | 关闭 | 同配置重复 |
| 4 | P1 | 20/s / 10s | 200 | 开启 | 附加诊断，不能并入普通基线 |
| 5 | S1 | 100/s / 10s | 1,000 | 关闭 | 较高到达率压力诊断，不是容量上界 |

固定顺序预先声明；OS 文件缓存、时段和同机负载可能影响重复结果，不声称随机试验、统计显著性或专属硬件。B1–B3分别报告全部结果及完成率中位数/范围；P1和S1单列，不将五次混为同一种负载。最多1,800次计划到达，不跑已知不满足门槛的30分钟任务。

每次都是新的合成 authority 和相同100个账户名、SHA-256账户分片规则。新的数据库仅用于独立短测重复，不冒充同一authority的长期稳定运行。账户/command_id在五次间重复时，完整关联键必须包括run_id和authority；不能将所有 `bench:0` 当成一次重试或去重成同一业务。

## 全部保持相同的输入和约束

- 同一个完整冻结 SHA、同一解释器/SQLite和金融/规则/生成器源码；每次前后确认HEAD及已跟踪文件干净。保存`uta/*.py`及三个实际依赖benchmark文件的摘要，不在两次之间修工具、换解释器或改参数。
- 100账户、2个真实独立spawn worker PID、2个dispatcher，benchmark及子进程继承相同两CPU affinity。宿主仍共享最多4CPU配额，原24h生产者和观察器照常运行；其他短计算按集成负责人安排窗口静默，不暂停长稳。
- 全局本地outstanding256、每片durable inbox128、cancel预留16、market lane4；lease5s、worker poll .02s、observer poll .02s、background interval .1s、account_batch25、matches_per_symbol10、max_attempts3。隐式SDK默认值在冻结前核对并记录，不悄悄改小后台批次或降低风控频率。
- required decision audit、schema3和SQL fencing必须开启；初始化后确认子PID与lease owner相同、generation有效、真实ready，不能用父进程或共享内存Future替代执行者。
- 每账户合成USD100,000,000。Configured Cross、BTC-PERP、mark/limit100、quantity step .001、IM .1/MM .05、fee .0004、USD scale8。全部单正向买入；每第十笔用 .0005，预设10%产品步长拒绝。其余 .001 为合法单。成功订单保持OPEN，不撤单、借用对手或生成假成交来释放额度。
- 每2秒从真实当前UTC生成新的合成tick和递增版本，走完整publish/activation barrier；max price age5s。发布失败不改旧snapshot时间、不重标为新鲜。不绕过全局halt来避免安全拒绝，也不把门控拒绝算成功。
- 软响应期限1s、terminal drain10s；SQLite busy timeout保持实际默认10s，control timeout3s。不同超时预算分开保存。静默窗口按每case最多约45s预留，实际结束立即释放；若额外排空/关闭超出预算，记录真实耗时而不是截掉。

冻结时确认这些值仍是候选真实合同。若新API或默认值不符，应在跑数前修订计划和配置来源，不能跑完再移动口径。

## 成功、拒绝、迟到与未知

`durably_queued`只计持久入队。金融成功必须是原CID的真实SUCCEEDED观察，随后能在终态存储中对应同一订单、预占和审计。入队ACK丢失时可用原CID查询；查询在测量窗口内确认terminal才可计观察成功，同时保留enqueue技术错误。仅在最终复开才找到的成功单列为unobserved success，不补进测量吞吐。

每个run保留全部计划到达，包括本地队列满、持久队列满、未派发超期、业务拒绝、router-halt/行情拒绝、QUARANTINED、pending/结果未知、已成功但超1s。拒绝和ACK不是容量完成量，迟到子集也不与成功数相加。关联/统计时区分互斥outcome与重叠诊断计数，不能把durably_enqueued再加入outcome总和。

端到端从原计划单调时间到COMMIT后的terminal观察，包含排队、SDK调用和polling。数据库completed_at是提交前事务内写入时间，不当作精确COMMIT时刻。分别报告全部请求、金融成功和仅ACK的P50/P95/P99/P99.9、样本数、最大值及超期数。200样本的P99.9本质接近样本最大值，不能据它推断生产尾部概率。

每次报告实际terminal观察排空时间、worker关闭时间、尚未清空的原CID和关闭后新增terminal。关闭worker不等于已排空，SDK关闭期间刚提交的业务不得回填为按期完成。若不能清空，则没有“积压清空时间”成功值，只保留未完成事实。

## 不省略的最终只读核对

先停止新输入并按原ID查询/排空，再正常关闭本次受控workers；未完成保留在原authority。重新以SQLite mode=ro/query_only连接，不构造会创建或修schema的金融服务，不读取/复制活动金融DB的原始字节。

逐CID检查canonical payload、account/shard、order_id、数量、价格及reduce_only；已确认ACK历史不能消失。SUCCEEDED必须对应唯一OPEN订单、唯一ORDER_ACCEPTED和required admission decision；非SUCCEEDED不得已有订单效果。缺失audit、版本或关联为正确性失败，不降格为业务拒绝。

独立手算每笔合法订单`.01004 USD`预占，逐账户汇总并与订单/事件/receipt核对。账户版本应为资金入账版本1加实际成功数，订单版本连续；余额保持原USD现金，未成交时不得有费用、仓位或fill。预期背景处于NORMAL不会增减版本；若候选有新的合法版本行为，必须先解释合同和事件，不能放宽断言使数据过关。

保持required schema/guard和audit引用检查、integrity_check、foreign_key_check、逐币整数posting/hash链及余额投影重算。最终RO通过只确认终态事实，不能替代独立kernel锁、fencing、并发及崩溃验收；新的短测也不能证明24小时稳定性或复制RPO。

## 本轮需要防止的对账和诊断风险

1. **只读连接暗中写库。** 等mode=ro最小修复及独立测试完成后才冻结；不能用一次最终RO核对掩盖此前read_transaction对空库或DELETE-mode文件的修改。缺失路径不能被观察器创造。
2. **同一SDK调用返回ACK却被误算接纳。** 保留planned、enqueue started/ACK/call finished和post-COMMIT terminal observed，分别汇总；任何未被观察的terminal不事后算快。
3. **门控拒绝改变预设拒绝比例。** invalid数量可能先遇到router_halted，不能硬补到10%产品拒绝；按输入合法性和实际错误码交叉报告。每次publish和activation耗时/版本也保留。
4. **关闭与未知竞态。** 最后一个正在运行的事务可能在collector截止后提交。保留其CID，复开认清金融事实但不改变原观察时间；pending/QUARANTINED不删除后重发新ID。
5. **后台或价变改变订单/账户。** 当前全部单向、无仓位、巨大现金，预期无成交或清算。任何取消、fill、额外版本或现金变动都要追溯，不将其当成“自动清理”忽略。新snapshot实际时间必须保持原样。
6. **poll I/O根因上下文不足。** 首轮522缺分片和FD/WAL证据；下一轮若再发生，立即保留错误和当时文件的非跟随stat元数据、路径/分片、SQLite版本与日志。禁止为诊断直接open/read/close活动金融inode，重新引入已修缺陷。当前工具若缺这些字段，应通过受控外部只读取证并标明范围，不能伪造追溯字段。
7. **profile失真。** 父profile可能混线程，原始profile全留但不据其精确分摊。P1只对独立worker生命周期做描述性分析，并检验internal/cumulative异常；嵌套累计时间不相加为CPU百分比。profile和非profile结果不混合求收益。
8. **短样本和未饱和输入。** 20/s无积压只能表明这一低输入观察，不是上界。100/s若队列满或客户端outstanding受限，也不能把局部峰值叫系统最大容量。没有30分钟/混合负载/真实清算确认量证据，所有生产和10k容量字段保持false。

## 执行、停止和归档

现在只保存本计划，尚无最终SHA、GO或执行结果。获GO后从实际冻结SHA建独立工作树，输入/输出目录各次唯一；每次开始/结束记录命令、父PID、子PID和出生/lease证据、UTC、原计划时刻、source hash、硬件/配额、存储及同机流量。

每次前后只读检查原887/观察器PID、source和heartbeat；从其已有证据中留探针区间的真实heartbeat，必要时暂停本轮新负载而不停止长稳。不得声称专属主机。每case预留不超过250MiB、整个cohort不超过1GiB输出预算、至少2GiB剩余空间；触限停止后续case，保留已产生的金融义务和原始记录。

任何新I/O异常、确认命令丢失、订单/预占/账本/audit错误、source变更或长稳异常，当前case保留全部结果，停止余下case并报告。预设产品拒绝和100/s压力下的queue-full可作为诊断结果，仍不算通过。不要通过重跑覆盖失败目录或删unknown使矩阵变绿。

每次归档raw JSONL.gz、每片queue/market telemetry、完整控制回执、source/environment、失败stderr和SHA256 manifest，公开数据均为合成。金融DB保留本地，不提交Git。下一阶段优化优先在正确性证明下减少后台重复监督和事务密度，不跳过新鲜度、账本、required审计或fencing。真正优化改前改后另行预注册同配置重复配对；本轮只建立修复后新基线。
