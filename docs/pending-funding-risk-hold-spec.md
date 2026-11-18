# Pending funding 统一风险预占规格

状态：**PROPOSED / DOCS_ONLY / NOT_RUN / NO_GO FOR PRODUCTION**。基线为 PR53 公开提交 `92979e9b2cd719bfaa9d857e13c2b99239355330`。本轮先写人工例子，再写规则、追溯矩阵与验收编号；不修改运行时、不执行目标 import/编译/测试/SQL/进程/worker/CI。下述为本系统的明确政策选择，不是交易所行为断言。金融、账务和独立验证签字均待审。

## 1. 先确定人工例子

完整输入、期望与前置见 [manual-cases.json](../evidence/designs/pending-funding-risk-hold/manual-cases.json)，共17例；金额均为合成 USD，例中没有特别列出的资产、订单、债务、费用和待处理义务均为零。它们是纸面算术和状态预期，不是已运行 oracle。

| 例 | 人工结论 |
| --- | --- |
| M01 | cash100，IM20/MM10，订单30，付款12：有效权益88、可用38。新占用38可到IM等号，但MM仍须严格大于。 |
| M02 | 两笔付款12+7、待收20：付款占用19，不净成0；cash100时有效权益81，可用31。应计权益101不代表可用101。 |
| M03 | 两个原始 period 各精确借记.015、最小单位.01：现金义务各.01，hold合计.02；禁止跨period先求和变.03。 |
| M04 | cash100、本金20、利息2、贷款IM.1/MM.05、订单10、付款8：可用57.8。另收成交费1后56.8；资金费扣现金8并释放自身hold8后仍56.8，本金/利息不变。 |
| M05 | cash3、付款5：有效权益-2；支付后cash-2、cash deficit2、hold0，权益仍-2，不能再减5或生成本金。 |
| M06 | cash100、付款12+7、待收20：依次付款12、收款20、付款7，可用31→31→51→51；只有已提交收款20增加额度。 |
| M07 | 执行 claim 超时、重领或自动状态改变：hold12始终12；旧claim拒绝，经济身份不随claim generation变。 |
| M08 | cash100、IM20/MM10、原挂单60、付款30：可用-10先关闸；撤单确认前仍-10，确认全部未成交撤销后50，不能假释放。 |
| M09 | cash25、MM5、付款20：有效权益5等于MM，进入清算风险态；资金费仍须履行，付款后cash5/hold0，不得被自身hold挡住。 |
| M10 | 可信固定q2、mark100、rate未定但max_abs_rate=.03：cap6。rate=.012345后精确2.469、现金2.46，原子把cap6替成hold2.46，释放3.54。 |
| M11 | M01下出金或划转38：投影可用0、权益50>MM10；38.01拒绝。逐币现金预算88不是最终批准额。 |
| M12 | USD100+BTC2@100，BTC首100折.8、其余.5，付款12：BTC抵押130。移除.5BTC后抵押105；必须全量投影阶梯，hold只减一次。 |
| M13 | 原付款12不能取消；另批纠错待收2不提前抵消。原付款后cash88，纠错收款提交后才cash90。纠错能力本批不启用。 |
| M14 | USD100、付款12，LTV1、借款IM.1/MM.05、步长1且其他限额不约束：保守proceeds-leave quote80，不能沿用原quote90；quote仍不是借款授权。 |
| M15 | 资金费支付的提交状态只能是cash100/hold12/pending，或cash88/hold0/APPLIED；禁止cash100/hold0或cash88/hold12。 |
| M16 | cash5、两笔付款12/10、当前行情缺失：可信第一笔付款后cash-7、剩余hold10；持久限制新增风险并待重估，不声称风险恢复。 |
| M17 | scale2，q+.5/+.5/-1，mark1/rate.015：付款两腿都round到0，收款.01，需要真实隔离资本.01；不能铸造资金或提前给予收款信用。 |

## 2. 固定基线与真实缺口

[source-pins.json](../evidence/designs/pending-funding-risk-hold/source-pins.json) 固定源码 blob、字节数、SHA-256 和受审位置。PR53 `FundingObligations` 类明确声明 pending cash 不是 admission/withdrawal hold；`service._risk` 只看账本、原冻结、本金/利息、现金缺口、仓位与订单reserve；`_available_asset` 只减现货锁。`credit._borrow` 使用原quote并复算原风险，故仅向API返回待付款金额不能堵住支出路径。

当前 cut 固定现金腿，apply 在一个本地事务内记账、监督账户并保存APPLIED，但当前行情/风险不可用会回滚现金。新设计需要改变这种语义，必须用新契约重新验收，不能继承旧测试的通过结论。该基线 `DecisionAudit.policy()` 是旧十字段；没有 PR52 的 valuation10/order11 分离。未来若组合 PR52 或 engine-binding，先做独立集成设计，不能把本规格当已组合基线。

契约暂名 **`UTA-FUNDING-RISK-HOLD-v1`**，仅新建合成 authority generation、USD 单结算、Cross、multiplier1线性永续、同库独占写入者。保留原 funding per-account/per-period toward-zero 与 waived-subunit 政策。现货抵押、限价/RO、借款、划转/提币/抵押移除是必须检查的准入类别，不等于本提交启用这些接口；未集成或未验收的操作须在写金融状态前明确拒绝。PM/Isolated、USDT/USDC真实等价、多结算币、managed/native/sharded/HA、在线迁移、自动借币、保险/ADL、客户与托管接入均不获启用。

## 3. 权威身份、边界与逐笔占用

每条经济义务使用 `(authority_id, authority_generation, obligation_id, account_id, settlement_asset, final_cut_sha)` 唯一身份；`obligation_id` 对产品/period唯一。executor owner、nonce、claim generation、lease期限不是经济身份。claim超时、WAITING_DATA、WAITING_CAPITAL、REVIEW_REQUIRED、重领和重启都不释放占用。risk聚合不能使用客户端分页列表或只读第一页；完整闭合的相关任务集合与事件watermark是准入前置。

可信 final cut 一旦提交，付款方金额为 `D=max(-cash_units,0)*10^-scale`，收款为 `C=max(cash_units,0)*10^-scale`。D只取原固定现金腿，不重算当前仓位、不把精确未取整数ceil为新债、不跨task/资产/period/账户/母子账户净额。子最小单位按现有规则逐期豁免，不累计隐藏债务。关仓或减少当前仓位不改变历史cut的D。

final cut、各账户新hold、funding_version、完整集合摘要、账户风险限制及相关事件在同一金融事务提交。即使hold超过现金或权益，也必须记录真实义务，不能以风险不足拒绝形成cut后假装无欠款。容量、盘满、archive上限或缺边界导致不能完整提交时，新增风险保持关闸；不得只保存cut或只保存hold、跳过账户或裁剪任务。

仅查询已注册任务不足以证明没有漏期。新契约必须从不可变产品period日历、位置事件序列和最后完整边界推出应有任务集合。在到期边界的统一排序点，先纳入此前已确认并完成结算的成交，再固定边界持仓；之后的成交属于下一段。未结算确认成交会影响边界而归属不明时，先持久保留义务并阻止新增风险，不能用稍后的当前仓位补造历史cut。本地单库以受审单写者事务序列定义这一边界；没有生产定时器、跨分片水位或完整writer fence证据前不宣称精确生产cut。

## 4. 资金分量与有效风险公式

令 `P=sum(未APPLIED固定付款D)`、`N=sum(未APPLIED固定收款C)`、`U=sum(有可信固定exposure cut、尚未确定rate的保守buffer)`，`H=P+U`。同一身份只处于 U 或 P/N，一次转换不能同时计两份。

原 cash ledger、gross assets、frozen assets、贷款本金、利息、已结算费用、负现金、PnL、订单reserve继续原样保存。**hold不是本金、利息、现金过账、现货锁或虚构抵押冻结**；不得塞入 `LoanAccount.frozen_assets`，也不得借此绕开frozen≤gross校验。冻结资金费请求也不是新贷款，不收贷款IM/利息。若将来付款显式由借款融资，必须另行授权并保留两种原始事件。

| 字段/约束 | 规则、单位与风险方向 |
| --- | --- |
| `cash_ledger_accounting_equity` | 原账本模型会计权益，USD；明确其尚未包含pending funding应计分量。原历史字段不可静默改义。 |
| `recognized_funding_payable/receivable` | P/N，USD，逐笔gross展示；不可拿N抵P。固定cut定义本系统应收应付权利，须与账务组确认独立义务子账及会计映射，不预先写客户现金账。 |
| `accrual_equity` | cash-ledger会计权益-P+N，仅会计/对账视图；U是prudential buffer而非确定应付，不在应计权益扣除。该视图不授权可用信用。 |
| `risk_equity_effective` | 原risk_equity-H；不增加N。下降表示风险恶化；H只在此扣一次。 |
| `available_margin_effective` | risk_equity_effective-原IM-原order reserve；不得再次减H。新增风险须≥0。 |
| MM条件 | risk_equity_effective严格大于原MM才满足新增风险安全边界；等号、MM=0且权益≤0均不安全。资金费不凭本规格新增贷款MM，风险由一比一扣权益承担。 |
| USD逐币可支出 | raw=已结算USD现金-原USD spot locks-H；对外可支出显示max(raw,0)，审计保留raw负数。原永续reserve仍由投影账户风险约束，不能又在原risk_equity里重复扣。 |
| 其他币种可支出 | 原逐币现金/锁约束，加移除资产后的完整阶梯抵押与有效风险投影；不把USD hold隐式换成某币种锁，不假设自动换币。 |
| 借款风险头寸 | 固定资金费P与保守U计入prudential total-debt/LTV headroom，保持贷款本金/利息限额分量原样；不能复用未调整base borrowable。 |

对币种价格p、贷款IM率b、MM率m、step s，保守borrow quote仍假设借款所得离开抵押品。上限依次包含：本币本金限额、`(max_total_debt-(base_debt+H))/p`、`(base_loan_value-(base_debt+H))/p`、`available_margin_effective/[p*(1+b)]`；取非负最小值再floor到s，并检查 `risk_equity_effective-q*p > base_MM+q*p*m` 的严格边界。这里的 `base_debt+H` 是风险头寸，不是把H记成贷款。实际borrow还必须有账户/资产限额、真实借贷池、权限、幂等和同事务post-state验证；pending收入不能作借贷池资金。Credit V2不可沿用旧格式安装到此新契约，需单独新信用政策/回放审查，未完成前新borrow明确拒绝。

## 5. 一个准入依据覆盖所有新增风险

所有新单、改单、触发单、批量腿、自动借币、borrow、出金、跨账户划出、抵押移除、模式转换及撮合前本地授权，都必须引用同一 `(account_version, funding_version, market_snapshot_id, rules_id, code/artifact_id, funding_basis_id, evaluated_at)`，在持有金融写入者事务时读取完整H。入账确认前持久预占和接纳回执一起提交；未知/过期/不完整集合、版本冲突、缺行情、缺契约或缺边界均不默认为H=0。

新操作投影同时保留未终态订单最坏成交/费用/滑点、改单重叠和原只减仓累计数量规则。资金费H在所有投影相同，不能因为投影关仓或计划支付就提前清掉。多挂单或资金操作必须持久竞争同一剩余额度。撤单未确认不释放，已确认部分成交照账务义务处理；RO或清算指令自身的费用不能漏算。

划出和提币还须满足逐币可支出及完整投影风险；收款子账户只在真实划转提交后获得现金，pending receiver或母账户盈余不能跨隔离账户抵欠款。出金给托管前需不可重复的持久资金handoff和明确确认/冲正边界；本批没有托管实现，接口拒绝。抵押资格移除重算完整分层抵押而非按旧平均haircut线性扣。所有未实现路径在金融/能力写入前返回 `funding_risk_operation_unsupported`，不能走旧无hold服务。

允许风险降低或义务履行的独立类别包括查询、有效撤单、真实入金和已确认结算。自愿用原有现金还贷款也与资金费争用现金，不能通过旧 `_available_asset` 绕开USD hold；保留interest-first分配，采用完整受审非恶化规则或显式拒绝，不自动授权新还贷/换币能力。强制利息、确认费用和真实确认成交须履行且保留各自成分，不能当作新借款或因hold不足而丢弃。

## 6. 已确认资金费的结算、释放与恢复

第一批仍是完整本地period的原子应用：所有客户现金腿、真实舍入资本转移、clearing归零、账本分录、每条hold从active到consumed、P/N移除、账户/funding版本、receipt、task APPLIED、风险限制/后续风险检查事件在**同一 authority 金融事务**提交。没有部分账户APPLIED、分片中间成功或先释放hold再异步记钱。

结算路径不能使用新增风险的 cash≥H、available≥0或strict-MM准入来拒绝自身付款。金额、产品/period、cut完整性、固定制品/政策、单写者与幂等必须仍成立。对付款D先按真实现金减少D，同时移除且只移除自身holdD；在相同价格/仓位下，结算前后有效风险连续。其他task的hold保留。已结算现金变负时记录原cash deficit，不能再保留已支付的P，也不能悄悄转本金、铸造资本或免除欠款。

已确认收款只有现金账、receipt、APPLIED和N移除共同提交后才增加可用。rounding reserve只来自真实隔离资本和已有余额，不能用pending receivable或另一客户hold融资；不足则WAITING_CAPITAL，所有未付义务/hold仍在。任务/command/leg ID去重，旧claim不能应用，新claim不重复加hold。超时或响应丢失先查原command与cut/receipt/journal，不以新业务ID重做；同ID不同内容409，确定未提交与结果未知分开。

当前PR53 `_cash` 依赖当前行情并可能回滚，不能直接宣称满足新契约。新版本应把**可信固定USD现金履约**与**实时风险是否可算**分开：若仅当前行情缺失，现金+自身hold消耗+APPLIED+持久 `RESTRICTED_RISK_RECHECK_REQUIRED`/可重试风险outbox一起提交，不发出“风险已算/已恢复”结果。quote恢复后再由受审supervisor重新计算、撤单/清算。若cut、参考权威、共享模型/制品或账本完整性不能证明，则保持义务/hold与关闸，恢复精确受审权威；未知引擎/政策不fallback，也不伪造支付成功。

cash commit前崩溃：所有金融变化回滚，原H保留；commit后回执丢失：原receipt可查、重复不记账。cut创建前后也遵循同样原子性。重开存储先从不可变cut/状态事件/APPLIED receipt/账本重建active holds，与物化视图逐条比较；少项、多项、坏hash、orphan receipt、APPLIED仍hold、pending却现金已付均关闸并对账，不用“重算当前任务列表”静默修复历史。claim超时永不等于金融释放。旧观察UTC不保证physical COMMIT早于lease，继续明确0HA/单机故障模型。

## 7. 挂单不足、清算与人工处置

cut或cap导致 `available_margin_effective<0` 时，记录欠款与限制新增风险，先请求取消原增加风险的未成挂单；本地取消与外部取消确认语义分开。确认前保留reserve，期间真实确认成交仍幂等结算，按新持仓/手续费/剩余reserve重算。仅负available而有效权益仍大于MM不等于已达到MM清算线；撤单后仍不足则保持限制，不能用原supervisor NORMAL忽略funding冻结。

有效权益≤MM（含相等）需触发持久风险处置；候选减仓重新比较扣H后的权益、MM、费用、滑点与缺口。减少当前仓位不减少已固定资金费D，不能靠清算计划把历史欠款抹掉。无真实流动性保持排队与残余风险，不能把标记价生成的测试成交当实处置。

P超过权益、付款造成负现金或无仓可减时，持久标注distress/残余债务与人工处置，禁止自动免债或提前使用保险/ADL。若仍有其他抵押品，转换/偿债需要独立受审适配器；没有适配器则BLOCKED。恢复须满足完整数据、无未解决重大对账差异、原恢复缓冲、H仍正确且独立批准的解锁规则；不得仅因claim过期、任务REVIEW或重启自动解锁。

## 8. 未定rate、未知数据与纠错

只有已可信冻结原边界quantity、mark、USD scale及有效 `max_abs_rate`，才能记录 `EXPOSURE_CUT_RATE_PENDING`。这与现有PR53缺rate时不生成cut不同，需要独立不可变exposure记录和新状态版本。保守buffer `U=ceil_minor(abs(q)*mark*max_abs_rate)`，即使最后可能收款也先按最大付款方向占用；不是确定债务，不进本金/利息或应计P。rate确定且在cap内后生成关联final cut，同事务以P/N替换U；rate为0时也保留完整完成证据，不通过丢任务释放。

缺可信qty/mark/cap、超rate cap、边界不完整、时钟回退、行情不可用于固定cut或数学溢出时，保留已有hold并明确拒绝新增风险；不能按rate0或当前持仓近似。有限“当前mark×冲击”不是任意跳价的保证上界；本批不把它叫保守上界，也不实现未来所有period的预测授信。边界之前如需估算未来资金费，须另行模型/参数/价格保护审查。

已固定cut不得取消。客户取消请求、运营review或原定时任务取消不免除产品日历下的已发生义务。首版禁止post-cut void/supersession；错误cut冻结并人工审查。纠错须新不可变补偿契约、授权/双人审批和逐笔关联，不能编辑原记录：补偿借记增加自己的H，补偿贷记APPLIED前不抵原H。任何将错误cut和反向分录成对应用的方案需单独审查，不能先释放原hold等待未来补偿。未发生period的调度修正也必须保持日历覆盖，不得使尚存仓位跳过period。

## 9. 归档、版本、权限与实施顺序

新risk decision envelope应明确kind/format、原base valuation policy、funding hold契约、完整active P/U/N条目、canonical集合摘要、cut/receipt引用、截至事件watermark、单次UTC evaluation时间、market/artifact、账户和funding版本。摘要不能替代原数据；历史replay按当时watermark应用事件，不能用今天APPLIED状态改变昨天的H。解释输出分开P/U/N、原借贷/费用/现金缺口/订单占用、effective equity/available/MM、拒绝原因、业务ID和缺行情风险态。

不得给旧十字段策略直接添key后称兼容，也不冒充已合PR52。新authority capability/schema、funding配置与base/credit/audit/managed consumers的精确版本映射先由独立组审；任何未知/缺失契约、旧writer或无hold入口必须在金融/能力写入前拒绝。单纯比较一条config字符串不是全入口fencing证据。新增risk引擎模块或绑定策略亦不因本文获准。source inventory、loaded artifact与运行权限需新精确版本。

建议顺序：P0独立规则/人工例子审查；P1纯数学与独立oracle（不复用生产核心）和有界状态模型；P2新合成单库完整hold/准入/结算/replay与负例；P3真实撮合、故障/旧writer排斥、恢复与容量；最后才考虑新产品/信用/托管/HA。所有阶段目前NOT_RUN。测试编号见 [规则追溯矩阵](../evidence/designs/pending-funding-risk-hold/rule-traceability.json)，没有签字或生产GO。

部署只允许未来经审查的新合成generation，账户allowlist、不可变策略、权限、唯一写入者、磁盘/archive容量和完整period水位为前置。停机/回滚先停新增风险，保留已知良好新制品履行义务；不删hold/cut/config让旧二进制写新库。没有金融事件可销毁合成环境重建；有事件则对账并新generation显式迁移/补偿，不复制余额抹历史。节点崩溃后重开校验、旧主恢复、disk-full和结果未知均需实测，0HA不得承诺跨AZ RPO/RTO。

验收仍服从用户生产门槛：独立开放环持久接纳≥10k/s、真实撮合且仓位/资金账都提交的唯一清算成交≥10k/s，≥30分钟+长稳、混合/热点/突发/脱锚/流动性/故障、计划到达时间尾延迟、重开逐笔对账。此次只交规格，无新性能数字。监控需新增hold总额/最老pending、due-cut缺口、cap未定rate年龄、risk冻结原因、claim重领、cash/hold/APPLIED差异、风险重算积压、残余债务，原金额与状态不能被dashboard净额隐藏。
