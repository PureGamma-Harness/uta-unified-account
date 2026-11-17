# 普通行情按片推进的设计候选与独立有界模型

本组基线为不可变提交 `21aa6510bafcce8383fc24ac2c35e671074b9baf`，工作分支 `design/market-epochs`。本提交只增加设计、独立模型、模型检查及原始结果，不修改 runtime、数据库 schema、金融政策或 benchmark。已验发布冻结仍是 `7200097`；本设计不替换该冻结。

**结论是有条件可设计，尚未批准实现或上线。** 当前账户固定属片，真实 paired matching/settlement 只在同一片内执行，没有找到需要普通每个 tick 都全片同价的跨片交易运行路径。但现有控制契约明确要求所有片统一市场摘要。让各片先后采用新报价会改变可接受金融决策的集合，必须作为新的行情可见性政策审查，不能称为“相同参数、相同金融行为的性能收益”。如果未来加入跨片撮合、跨片抵押、全局风险限额或按全局 mark 自动动用共享偿付资源，本候选必须重新评估；未取得这些依赖的证明时保留强全局 barrier。

本组没有复跑负载，也不推断性能提升比例。上级提供的 corrected 原始证据位于 `benchmarks/results/20261117-managed-corrected-7200097`，性能取证来源与本设计基线不同。B1/B2/B3 各 200 个计划金融结果为 163/166/171，均另有 18 个产品拒绝，其余为门控；S1 为 1,000 个计划、887 个 enqueue ACK、508 个金融成功、58 个产品拒绝、321 个门控及 113 个本地满，418 个成功超过 1 秒。CID684 仍有一次内部 technical retry，最终 market unavailable 503，根因未定。这不是“全技术错误为零”的证据。真实交易所接入、production、持续 10k、HA、真实资金均未达成。

## 当前路径及真正的 barrier

| 静态位置（均为基线行号） | 实际行为与设计影响 |
| --- | --- |
| `benchmarks/run_managed_benchmark.py:529-545` | 每个真实调用的合成 tick 先 `router.publish_market`，再独立 `set_kill_switch(False)`。不是仅替换内存行情。 |
| `uta/durable_process.py:1262-1307` | 取得 EX router gate，先持久 `halted=True,publishing=True`、目标摘要/版本/epoch、固定每片 CID，再 enqueue。部分成功保持全局关闭；相同 snapshot 重试复用 CID。成功回执齐全后重新读取各片实际 payload，完成发布但仍 halted。 |
| `uta/durable_process.py:1309-1361` | 另一个 halt transition fanout。打开前再次检查资金来源、片内 local halt、payload 摘要和原 observed_at 新鲜度。发布会使旧激活命令失效。 |
| `uta/sharding.py:275-300,789-831` | 活跃 `_state` 要求所有 watermarks 等于全局版本；managed SUBMIT 要求全局开放且本片版本和 digest 精确匹配。PUBLISH 在同一事务先置 local halt；控制命令必须属于当前 generation/CID/目标摘要。 |
| `uta/sharding.py:839-867` | `process_one` 与 `run_background_once` 持 SH gate。background gate 覆盖 supervisor 和实际匹配的所有内部事务，不只是 ingress。完整资金 claim 核对及片身份检查仍必需。 |
| `uta/durable_commands.py:308-369` | inbox 选择控制 lane 的 FIFO head；guard、金融变化、命令终态同一片事务。新订单终态写入后再检查行情；返回成功发生在外层 COMMIT 之后。 |
| `uta/sharding.py:368-371,580-586`; `uta/matching.py:108,151-164` | 明确拒跨片 paired settlement/transfers。matcher 只作用指定片，两腿 fill 与匹配 receipt 在该片的同一事务/savepoint。没有跨片资金提交协议。 |

所以“仅删 publishing/halt 判断”会同时破坏 generation 授权、payload 一致性、部分发布恢复和强冻结排他边界。本候选保留全局协调锁及 writer fencing，只把普通价格发布从“全片暂停、安装、重新激活”改为“认证候选、片内原子安装、分别前进”。普通认证仍短暂取得 EX gate 来持久化不可变证书；它仍可能等待在途 SH，是否仍为瓶颈必须以后测量。这里没有承诺无全局协调或锁饥饿自由。

## 行情身份、父子 epoch 与事务边界

保留现有 `market_snapshot_id = "market:" + SHA256(canonical_payload)` 内容身份（`uta/decision_audit.py:263-285`）。内容身份不包含采用它的片、worker 或控制生命周期。新增的 epoch 是独立授权身份，不能用递增版本代替内容 hash。

- 全局父 `G` 是不可变 governance descriptor：前一父、layout/authority 身份、catalog/risk/config hash、行情来源及异常分类政策 hash、发布格式和显式 activation 身份。强 freeze、配置变更、脱锚、异常/可疑行情、撤销来源、控制/资金/身份完整性错误均创建或进入一个全局关闭的新父；即使参数不变，也不能复用旧 activation。
- 普通子 `E=(G,n)` 指向唯一 `parent_market_epoch=(G,n-1)`、准确 `market_snapshot_id`、payload digest、feed sequence、原始 observed_at、发布者权限及不可变普通分类结果。`n=0` 是该父强 barrier 激活所核对的起点。不得以相同 E 或 source sequence 携带不同内容；相同内容重试必须回查原 E/CID。更高 n 的候选只在其完整父证书链已耐久存在时授权。
- 全局证书及完整 snapshot 先耐久，再向片 inbox 投递。父进程死亡后不能要求外部重新拼出“差不多同一个 snapshot”。全局证书 append、强 barrier、资金 registry 更新使用明确锁序；保留 SH/EX 对强 barrier 与账户 COMMIT 的排他性。
- 片内 `installed_market=(G,n,market_snapshot_id,certificate_digest)` 是唯一当前指针；安装者也必须在 SH gate 内核对当前 G，并持有至本地 COMMIT。archive、证书链证据、精确目标 CID 的安装 receipt、指针及 publication event 在同一个持 writer token 的本地事务中提交。指针不能先于 archive/receipt；回执不能先于 COMMIT。无需普通每 tick 切 local halt。
- 账户价格敏感事务在 `BEGIN IMMEDIATE` 后选择本片当前指针，绑定其 archive 内容和当前 G/config，在事务全程固定该引用。同片行情安装也需要同一片 SQLite writer，因此不能在这个写事务中途换价。不同片互不阻塞地决定采用哪个已授权普通子。

本设计允许片跳过尚未采用的普通 tick，前提是完整全局证书链已存在、该子在当前 G 下有效、时间和版本均不回退、完整 snapshot 独立包含所有必需输入，并记录跳过范围。父链是授权连续性，不要求每片为每个价格都执行一次金融安装。是否允许这种 coalescing 也是新政策的一部分，不能偷偷加入基线 benchmark。没有上述条件时按顺序安装或拒绝，不能随意丢控制命令。

## 旧 quote 接受规则是新金融政策

建议候选名称 `rolling_shard_v1`，当前尚未写入配置或宣称实现。授权了更新 tick 不会立即使其他片当前正常 quote 失效。新增风险或执行仅在以下条件同时成立时使用旧 quote：

1. 本片指针是该片最近一次**已提交**的安装，拥有完整 archive、精确内容及当前 G 的有效证书，不能选择任意历史“更有利”报价。
2. 全局当前 G 已显式开放，无强 freeze、来源撤销、异常/脱锚事件；账户/产品冻结和 reduce-only 等原风险规则仍适用。
3. 原 observed_at 与最终 freshness checkpoint 比较满足现有 `max_price_age` 和 1 秒 future tolerance；不刷新时间戳、不放宽 age、不延 TTL。完整性、USD settlement、活跃持仓/订单/资金/负债输入和政策检查仍全部成立。
4. 新候选属于已事先批准的“仅价格/时间/正常 feed sequence 改变”分类；资产/工具集合、collateral factor、margin rate、catalog、risk tier、settlement、来源规则等语义改变一律走强 barrier。价格冲击、脱锚或质量异常阈值也必须是先批准、可回放的政策，不能在本组凭空选择。未有可靠分类政策之前不得启用 rolling。

例：同一个存量 long 在旧 mark 下尚有保证金余量，新 mark 下不足。新 tick 已认证但只有片 A 安装，片 B 可能仍按年龄合格的旧 mark 接受一个订单；当前全局发布协议此时不会开放任何片。fee、IM、age 参数数值全部不变，金融接受集合仍不同。反过来，新 mark 也可能让某片更早允许原本会拒绝的决策。因此以后需分开给出“原政策基线”“新可见性政策结果”，记录版本差、quote age、拒绝集合和金融差异；不能把减少的门控直接记为相同政策的吞吐收益。

新 tick 被判异常时，先取得 EX gate、耐久强 freeze 并使旧 activation 失效，再做下游 fanout；全局关闭确认不能早于此前 SH 事务结束及 freeze 耐久。分类发现到 EX 生效之间的等待必须可观测；“检测到异常”不是已完成冻结。若要求在原始 feed 事件发生的物理瞬间阻止所有已在途交易，该更强实时性质目前没有证明。

## 账户 decisions、撮合、还款与审计缺口

每个价格敏感的账户 decision 应原子引用：`market_snapshot_id`、E、G/config/policy/artifact 身份、account pre/post version、业务 ID、选价时刻、最后 freshness-check 时刻和实际金融结果。一个同片 paired settlement 的两腿使用同一个 E、execution price 和 transaction receipt；admission 的旧 E 不授权未来 fill。执行必须重新选择当时本片 snapshot、重新做产品/风险检查。supervisor 的冻结与清算计划亦需绑定 snapshot ID、E、政策及 position digest，不能只靠 `plan_market_version` 复用。

现有 provenance 不应被误称为已经全面满足。订单 admission/fill 在 `uta/service.py:791-807,955-993` 及 `uta/decision_audit.py:290-296` 已记录内容身份、policy/artifact、账户版本与 operation。`uta/decision_audit.py:228-230` 明确排除 business rejections、spot、新 credit、cancel、repay；credit borrow 目前主要存 version/observed_at（`uta/credit.py:321-327`），spot match 主要存 market/catalog versions（`uta/spot.py:357-371`）。新增 epoch 与覆盖缺口需要显式 schema/capability 升级和旧 reader 兼容设计，本提交未实现。

还款与取消无需为了统一字段而创造假报价。`uta/credit.py:350-396` 的 repay 在同资产 settled cash 与 debt 等额减少前提下，先利息后本金，不读取价格；金融分录、debt projection 和命令 receipt 同事务，原本就可在 halt/断价时执行。它应记录 `market_dependency=NONE`、snapshot ID 为 null、policy 身份及原因，不能挂上一个不存在的“决策依据”。cancel 同理。若以后某还款变成跨币兑换或新增 credit，它便成为价格敏感路径，必须重新分类。全局资金/身份损坏仍可拒绝所有写，不能把价格独立理解成绕过存储完整性检查。

## 最后 freshness checkpoint 与物理 COMMIT 的边界

`uta/service.py:392-405` 在 `_market(fresh=True)` 验证当时价格。managed 新 SUBMIT 在 `uta/durable_commands.py:366-367` 有末端检查；同片 batch 在 `uta/sharding.py:526-527`、borrow 在 `uta/credit.py:317-318` 有末端检查。一般同步 admission/fill、matcher 没有统一的数据库 price-age callback。`uta/storage.py:194-201` 的 `guard.before_commit()` 检查 writer fence/schema（`uta/writer_fence.py:526-542`），不是通用价格检查。不能把这些路径全说成物理 COMMIT 瞬间保证 age。

未来实现应统一所有价格敏感 writer 的最后 freshness checkpoint，确保它校验事务已经固定的同一个 snapshot，且金融 receipt/audit 不会在检查失败后泄漏。但任何 Python 前置检查之后，都可能发生进程暂停、SQLite COMMIT、fsync 尾延迟。没有可强制执行的暂停/IO 上界，就不能绝对保证“落盘瞬间报价仍在 TTL 内”。检查失败必须事务回滚；COMMIT 后发现时延超界不能把已发生资金结果改写成未发生，也不能用新的 CID 重做。

记录 quote observed_at、decision 选价、最终检查、COMMIT 调用开始/返回、客户端 ACK 的 UTC/monotonic 时刻和原始不确定性。SQLite WAL 的准确持久线性化时刻通常只知处于调用区间，不能把函数返回时刻伪称准确 fsync 时刻；跨进程 monotonic 还要绑定同一 boot 身份。若业务要更强实时限制，需要先定义保守年龄余量、执行/IO 假设和越界后的强冻结/审计策略；这也是新风险政策，不是延长 TTL。本提交没有制定该余量或把最后检查能力限制称为客户漏洞。

writer lease 同样区分“最后 fence 检查通过”与“物理 COMMIT 时 lease 必然未过期”。SQLite 实际 writer 锁使新 generation 的片内写入必须等旧事务释放；这支持没有重叠实际 writer，却不等价于旧事务 COMMIT 时 lease 一定活跃。本设计保留原 ownership、token、SQL/native guard 和真实锁约束，不用市场模型代替它们的实现证据。

## 部分发布、乱序、重试和恢复

| 情况 | 候选处理及可见结果 |
| --- | --- |
| 只有部分片安装普通 E | 已安装片可用 E，其他片继续当前合格 quote；全局返回 `ANNOUNCED/PARTIAL` 和片版本向量，不能返回“所有片已采用”。不能修改 `ready=true` 的含义而无 API 版本升级。 |
| E2 先于 E1 到达 | 验证当前 G、完整授权链、内容和本片单调性；符合 coalescing 规则可安装 E2。迟到 E1 只查历史 receipt 或记录 SUPERSEDED/SKIPPED，不回退指针，不伪称本片安装过 E1。 |
| 相同 E/CID 重投 | 必须匹配原 hash/parent/payload；已有成功 receipt 时读原结果，不重复事件/安装。不论 timeout 与否，不生成新 CID 掩盖结果。 |
| 返回 ACK 丢失 | 结果为 `UNKNOWN`；只读查询本片精确 CID、receipt、archive 与指针。已提交且随后被更新的 E 仍有历史 receipt，不能要求当前指针仍等于旧 E 才认成功；历史成功也不表示当前正在使用 E。 |
| COMMIT 前 worker 死亡 | 未提交安装/金融/receipt 全部回滚。新 owner 在既有 birth/lease/fence 协议下恢复，查询原 CID 后继续；不能根据内存 ACK 推断成功。 |
| COMMIT 后 worker 死亡 | 已提交 snapshot、archive、decision 和 receipt 保留；新 owner 重新核对 authority、资金、G 和证书，恢复当前指针。发现旧父、损坏、同身份异内容则强 freeze；只是 quote 过期则拒绝新风险并等待新报价，repay/cancel 仍按既有条件。 |
| 父进程死亡 | 先按现有持久 ownership 协议恢复 worker，再从证书存储重投原 snapshot/CID。父 ACK cache 不具有金融权威；结果查询不要求 worker 仍活着。旧 coordinator/旧 activation/旧父子命令不得修改新父。 |
| 完整性错误或来源撤销 | 全局强 freeze 后修复；普通片局部重试不能自行解除。强新父的起始 snapshot 必须完整 fanout、实际 payload 与 receipt 全核对、资金证明/owner/age 全检查后再显式 activation。 |

普通 lag 超过原 age 时只限制该片新风险；若运营政策另要求“任意片 lag 都全局暂停”，需单独批准并报告，这会恢复一种全局可用性耦合。queue overload、内部 technical retry、QUARANTINED 与 UNKNOWN 必须分列，不能当业务拒绝或成功率分母外噪声。

## 跨片可见性与全局资金证明

本候选仅为片内决策提供线性化 snapshot，跨片读取返回 `[{shard,account_version,ledger_watermark,E,market_snapshot_id,observed_at,checked_at}]`。异步 watermarks 是观测向量，不是同时读取所有片的原子全局快照。readiness/health 至少区分强父已开放、每片 owner/funding/data ready、行情新鲜度、当前 E、已观测安装 E、未知结果与 lag；`latest announced` 不能替代 `locally installed`。现有 `_diagnostic_market` 和 `financial_ready`（`uta/durable_process.py:158-184,1166-1245`）要求全局单一摘要，必须版本化替换，不能单删校验。

资金守恒的已有证明不依赖 mark：`uta/storage.py:337-355` 每个 journal event 按 asset minor units 平衡，`:465+` 重放链/balances；`uta/reconciliation.py:265-266` 按 symbol 检查 paired quantity 净零。全局 credit funding 的 `source_reference` 必须永久唯一分给精确 shard/command，`uta/sharding.py:559-578,419-457` 的 exact claim 核对及其协调锁仍保留。rolling 不能移除恢复、来源登记、layout/authority 和完整性冻结所依赖的共享/排他 gate。

这些事实只支持单位资金/交易数量对账，不等于 external custody、统一 USD 估值或偿付能力。把各片不同 E 算出的 equity 相加，不是统一时点的全局风险证明。若需要总风险，必须给账户状态 consistent cut 和单独统一 mark 的离线/受控重估；不得把重估 snapshot 冒充实际当时 decision snapshot。若这样的总风险决定实时新风险额度或保险/偿付资源，本候选尚无跨片原子风险预算协议，应否决直接启用，继续强 barrier 或先完成新的预算/结算设计。

## 独立有界状态枚举

源码 [formal/explore_market_epochs.py](../formal/explore_market_epochs.py) 只导入 `collections/dataclasses/json`，不复用 UTA 函数、既有 formal 模型、SQLite 或风险计算器。原始输出 [formal/results/market-epochs-design-20261117.json](../formal/results/market-epochs-design-20261117.json) 包含源码 SHA256、Python 版本、资源记录、每个反例逐步完整状态。三张安全图是**独立抽象**，不是组合、代码精化、金融正确性、HA、活性、无锁饥饿或实现已满足本设计的证明。

边界为两片、两个普通子 tick、每片至多两代 owner、一个账户决策、四个离散时刻、一次强父更换。市场数值/摘要/配置是可信身份抽象，不枚举真实 payload、数值价格、feed 欺诈或风险公式。`archive/receipt` 用 bit 集合表示；授权序列先后、安装和耐久性均作为模型原子动作的前提。没有 SIGSTOP/PIDbirth/native SQLguard/真实 lease/ns 时钟/物理fsync 的实现等价证明。

1. **Delivery 图**：全局顺序授权子1/2，任意片可先采用2；原子 archive/pointer/receipt，ACK独立丢失/查询，worker死亡/下一代恢复，迟到tick不回退。显式覆盖片间不同版本、已提交但ACK未知和恢复后仍有历史。
2. **Checkpoint 图**：显式区分 global authorized head 和本片 pointer；新head已授权时可按新政策使用尚合格旧local quote。事务固定引用，安装不能越过片内写事务；SH覆盖决定和抽象提交，强freeze在持有者退出后耐久。接受 witness 保存当时quote/audit ID/time/open/head，不用后来状态追溯误判合法历史。
3. **HardBarrier 图**：强freeze并更换父，片分别安装和核对，新父全片完整才可显式thaw；正常授权只能指向当前开放父。它不与前两图组合，因此不证明任意强freeze/普通tick/金融提交的全程交错。

另有 **PhysicalGap 反例图**，允许最后用户态检查后时间继续走、再物理提交。它预期找到年龄超界的历史提交witness，明确展示无暂停上界时不能证明的性质，不被当作安全模型失败或真实客户漏洞复现。

运行方式：

```sh
taskset -c 0 python formal/explore_market_epochs.py
taskset -c 0 python -m unittest discover -s tests -p test_market_epoch_model.py -v
```

每张图 BFS 队列清空才报 `complete=true`；100,000状态上限触发异常，不能将资源上限当通过。每个badvariant只放宽指定条件，须发现指定违反、真实重放完整路径，并含区别于正常图的边。未知model/mutation拼写直接失败。模型测试检查非空正向覆盖、未知ACK恢复/迟到旧tick、明确的新政策旧quote路径、源码仅用标准库、资源上限失败和每个JSON-roundtrip反例。下节结果在最终源码上重新生成。

## 本次实际结果

单 CPU 0（`taskset`）、Python 3.12.14，最终模型源码 SHA256 为 `60df96b838e112e587812d8458e92dac39a12071ae416aeb84bcef662c04ce28`。模型枚举 wall time 0.021899 秒，整个解释器累计 user CPU 0.056427 秒、system CPU 0.004246 秒；没有超过一 CPU/10秒的授权边界。原始结果包含具体资源记录，时间仅是这次有界枚举耗时，不是服务性能。

| 完整安全图 | 可达状态 | 动作边 | 结果 |
| --- | ---: | ---: | --- |
| Delivery | 819 | 4,260 | 全部不变量保持 |
| Checkpoint | 148 | 275 | 全部不变量保持 |
| HardBarrier | 23 | 31 | 全部不变量保持 |

非空覆盖包括396个片间不同版本状态、630个已提交但ACK未知状态、400个下一代owner仍保留历史状态；checkpoint的28个状态明确记录“当时全局已授权head1、决策仍用local0”，不以提交后才安装新tick伪造该覆盖；hard barrier有12个合法当前父授权witness状态。这些是有限状态计数，不是金融成功次数或生产容量。

| 故意破坏的约束 | 首反例动作数 | 被检测性质 |
| --- | ---: | --- |
| 指针先于archive/receipt提交 | 2 | 安装原子性 |
| 迟到tick回退指针 | 4 | 本片单调性 |
| 仅投递就报告成功 | 2 | ACK必须有耐久receipt |
| 下一代恢复后旧token仍安装 | 4 | 写者generation必须匹配 |
| 仅入口检查age | 4 | 最后checkpoint必须检查age |
| 未提交即释放SH | 3 | 强freeze不能越过受保护提交 |
| 决策中途替换/重绑snapshot | 4 | audit引用必须是实际计算所用snapshot |
| 只一片新父回执就thaw | 4 | 新父全片完整后才开放 |
| 配置换父后仍授权旧父子 | 2 | 子epoch必须属于授权时当前父 |

9个坏变体全部产生指定反例且重放成功；另一个4步PhysicalGap反例为“时间走至1→末次check合格并进入COMMIT→暂停至2→物理提交”，TTL抽象为1。它保存提交时刻2作为历史witness，后来时间流逝不会让原本合格的历史提交被误报。8个模型单元检查通过（0 failures/errors/skips），最后一轮实跑0.105秒；只运行本组模型检查，没有把全仓历史测试数列为本次证据。

## 后续实现前的可审查门槛

先审查新旧政策的接受集合及异常分类，确认不存在需要全片统一mark的实时资金/风险依赖。随后才可设计版本化 schema/capability、控制API/health的向量语义和最终checkpoint覆盖矩阵。运行时代码仍须独立评审，至少用真实进程/SQLite验证部分安装、同E异内容、乱序、ACK未知、旧父/旧token、强freeze等待在途COMMIT、死亡前后原CID查询、repay/cancel保持可用和资金registry一致性。

只有金融等价测试已明确哪些结果应相同、哪些是批准的新政策差异后，才能跑新负载：固定年龄和金融参数，分别报告每片E/lag/quote age、拒绝种类、未知/重试、commit/ACK延迟、实际成交和资金对账。不能仅靠减少gate、延TTL或隐藏technical retry达成容量指标。当前所有production/10k/HA/真实交易所/真实资金结论仍未获得本设计批准。
