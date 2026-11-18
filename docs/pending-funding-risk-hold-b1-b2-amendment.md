# Pending funding hold：B1/B2 规则修订

状态：**SPEC_REVISION_2 / DOCS_ONLY / NOT_RUN / D2_BLOCKED**。这是对 `bac842516abc8f1e8af42f8624b5cf28f31b5972` 的提案修订，保留 [独立报告](pending-funding-risk-hold-independent-review.md) `ade10972b8044e3c753113970db34b3c85950ca4` 及原17例的原字节。报告的B1/B2仍是当时的否决记录；本修订只提出解决规则，须另一组重新独立审查，不把旧报告改为通过。未修改/导入/编译/运行目标、SQL、进程、worker、CI或服务。

根负责人选择本系统政策：资金费不得被**自身H**阻断，但不得穿透其它真实冻结backing或越过已确认成交。无可靠外部cancel-ack、持久outbox和优先履约opener的现有基线不满足D2；只可在独立规则审查后选择D1纯hold计算/状态模型子集，不能据本文启用金融能力。没有交易所事实归因、生产/真实资金/HA批准。

## 先列新增人工案例

[amendment-cases.json](../evidence/designs/pending-funding-risk-hold/amendment-cases.json) 先于本规则修订写出M18..M27十例。原 [manual-cases.json](../evidence/designs/pending-funding-risk-hold/manual-cases.json) 的M01..M17数值、文本和字节均不变；其未列出的其它冻结及未处理确认成交为零。M05/M16的负现金结论因此仍成立，不能推广到有真实冻结的账户。

| 新例 | 关键预期 |
| --- | --- |
| M18 | schedule与cut出现前可由固定自然字段算出同一duty_id；换cut/cap/claim不换duty。相同自然slot不同rule scope拒绝第二义务。 |
| M19 | 同一duty U6→P2.46，或U6→N2.46/零额，只有一个active阶段；旧cap只作历史。双resolver的过期revision拒绝，崩溃只能留下转换前或转换后完整状态。 |
| M20 | cash100/F95/P12先WAIT，effective risk=-7；取消请求不释放。真实确认释放10后F85，付款前有效风险3；付款到cash88/P0后仍3。应计权益始终88。 |
| M21 | 已确认spot成本4+fee1先按原权威履行，cash95/F91，资金费仍欠12；再真实取消10到F81，付款后cash83/F81，有效风险2。收币资产4在本合成例抵押因子0，应计权益87。 |
| M22 | 外部CANCELLED文本但此前fill watermark未知，不能释放任何锁或付款。 |
| M23 | 合成wait参数30s、5s查询间隔、最多4次只是测试输入；重启/换claim不重置首次wait起算的deadline，超时或预算用尽转DEFAULT_REVIEW，P不消失。 |
| M24 | 允许三个持久阶段：100/95/P12等待；100/85/P12确认释放；88/85/P0/APPLIED。禁止88/95或未付款先P0。 |
| M25 | F0时cash3付5→-2仍满足0≤max(-2,0)。若cash5/F1付12会穿透冻结，即使缺quote也必须WAIT；真实释放F1后才可走受限固定USD履约。 |
| M26 | 独立批准、真实来源过账的资本7可使cash107后付12至95/F95；权益0仍不安全。若是借款，principal7必须显式留账，不能伪称资本/自动借款。 |
| M27 | 完整本地period中一个payer被锁阻断，全period现金腿/APPLIED都等待，receiver20仍无现金信用；不能只付另一腿伪报整期完成。 |

## B1：稳定duty与阶段内容分离

`duty_id = funding-duty:v1:SHA256(canonical_duty_fields)`。exact字段是 `schema=1, authority_id, authority_generation, symbol, period_end, interval_seconds, settlement_asset, account_id, rule_scope_id`。duty由字段确定，不依赖已存在的schedule行；period注册后才遇到的新参与账户也按同一函数推导，不能靠更换caller obligation_id产生新权利。自然slot唯一约束为上述字段去掉schema、interval_seconds和rule_scope_id；相同slot只能绑定一个已批准rule scope。

标识符是受现有ASCII边界约束的精确稳定ID；authority_generation是稳定金融generation的规范ID文本，不是executor claim计数，不按display name、大小写折叠或别名猜测。period是UTC whole-second规范文本 `YYYY-MM-DDTHH:MM:SS+00:00`，interval是原产品周期正整数，bool不是整数。rule_scope_id指向不可变、经批准的资金费规则/版本、产品规则namespace、现金rounding和USD scale；其canonical payload也归档。若同一slot请求不同scope，拒绝并要求迁移/人工规则决议，不能新生成第二债权。

quantity、mark、rate、schedule_command_id、obligation_id、代码SHA、claim/nonce、exposure_cut_sha、cap_sha与final_cut_sha均**不进入经济主键**。代码/政策/阶段内容仍必须精确绑定与验证。`exposure_cut_sha`、`cap_sha`和`final_cut_sha`是分别typed的不可变内容refs；缺阶段用显式null/无此阶段，不能填占位hash当身份。

| active representation | U/P/N贡献 | 必须保留的内容与转换 |
| --- | --- | --- |
| REGISTERED_UNASSESSED | 无已评估值；完整性gate关闭，不能推断零欠款 | 稳定duty、scope、预期边界。 |
| EXPOSURE_RATE_PENDING | 仅U | 可信exposure_cut和cap，原quantity/mark/scale/max_rate。 |
| FINAL_PAYABLE | 仅P | final cut现金借记；旧U记录标consumed但内容不改。 |
| FINAL_RECEIVABLE | 仅N，H0 | final cut现金贷记；不给现金/风险抵押信用。 |
| FINAL_ZERO | U/P/N均0，但有完整final证据 | 不是漏task或未知rate。 |
| APPLIED | active U/P/N均0 | 保留原final与实际cash receipt/ledger refs；历史金额不删除。 |

经济representation与执行phase是两个轴。WAITING_ENCUMBRANCE_RELEASE、WAITING_DATA、WAITING_CAPITAL、DEFAULT_REVIEW、claim超时或cancel请求都不消费P。U→P/N/zero由一个authority事务完成：验证duty现revision/active_stage/expected cap ref，以CAS推进revision、保存不可变final内容、消费旧representation、建立唯一新active representation、更新basis/funding_version及命令结果。每duty唯一active记录/索引与自然slot唯一性是必须实现的约束，不可只靠内存if。相同command同内容重放原结果；不同内容409；不同command但旧revision拒绝，不再占用一次。旧exposure/cap/final事件按sequence保留，replay只选watermark前唯一active阶段。

## B2：真实backing优先，等待不免债

付款前，在同一受保护authority事务中重取cash、真实冻结allocation、账户/funding/encumbrance版本及已确认成交水位。所有影响该账户backing的未处理确认成交先由原权威幂等履行；在其现金/锁消耗和费用尚未确定前，资金费进入 `WAITING_ENCUMBRANCE_RELEASE(reason=PRIOR_CONFIRMED_SETTLEMENT_UNRESOLVED)`。不能把同一成交的原spot lock和后续结算占用同时加两份；必须有allocation lineage证明已消费哪个锁。不能用“将来收到的资产/资金费”虚增backing。

确认成交已落账后，令 `C_after=当前真实USD现金-本次固定付款D`，`F_after=本次付款后仍须保留的真实USD spot冻结`。backing必要条件是 **`F_after <= max(C_after,0)`**；不是强制 `C_after>=0`，也不是 `C_after>=H`。F0时允许原规格的负现金并显式cash deficit；F>0时不能让真实冻结超过gross正现金。其它币种原冻结/资金归属也不受资金费付款篡改。已知既有状态自身已违反backing或allocation不完整时先受限恢复，不弱化LoanAccount的frozen≤gross。

条件不满足时，同事务持久保存due payable/P、H、账户限制、首次wait时间/固定deadline、reason/阻塞allocation、版本化phase及幂等outbox取消/查询意图，返回**确定未支付**结果；不写cash腿、不消耗H、不APPLIED、不提前给予receiver N现金或风险信用。基线没有可靠实现，所以本段不是现有代码能力声明。

本地取消只有在权威真实取消未成部分并记录实际lock释放/期间成交后才生效；外部取消只有权威ack、截至确认水位的全部fill和分配lineage闭合后才生效。请求发出、socket超时、终态文本、缓存、查询pending、运营点击或worker重启均不释放。多个duty请求同一allocation的取消按稳定action identity去重，仍分别保留各自债权和wait期限；不能一份锁多次释放。

确认释放是一个可独立提交的真实订单状态变化，不是预先付款。之后重新取得最新版本、处理先行确认成交并重算backing，满足条件才按原完整period事务提交全部现金/资本/clearing、对应P/N消耗、receipt/APPLIED及风险restriction/recheck。没有任何付款之前发生的确认释放不保证下一次检查仍可付款；版本变化必须重算。完整period一个参与人等待时，全period不部分APPLIED，N不提前使用。

自身H不能自阻断只表示不用新增风险的cash≥H/available≥0/MM>门槛否定付款；它不授权挪用别人的真实冻结。仅缺实时quote时，独立受限固定USD履约也须先满足相同backing/先行确认成交条件；否则继续WAIT。可信cut/权威不完整仍不得fallback。付款后风险未知就持久限制并待重估，绝不伪报健康。

## 必填版本化等待政策

新能力必须绑定严格的 `wait_policy`：`format=1, policy_id, clock_policy, max_wait_us, min_query_interval_us, max_query_attempts, expiry_action`。时间参数是正原生整数、不是bool；`min_query_interval_us<=max_wait_us`，query预算有限，所有数值经过部署容量/风险审查，**无默认值**。本文不规定交易所等待时限或生产秒数，M23仅给合成值。

clock_policy固定为受信UTC及持久observed high-watermark；首次阻塞在提交时捕获wait_started_at，`deadline_at=wait_started_at+max_wait_us`。重试、换claim、换query ID、重启、控制面灰度均不延长；时钟回退显式受限。epoch/policy hash和首次时间一并归档，不能在活跃wait中热换政策重起计时。expiry_action固定 `DEFAULT_REVIEW_PRESERVE_DEBT_FREEZE_AND_OUTBOX`。

到deadline或query预算先用尽，原子推进DEFAULT_REVIEW、保留P/H、限制、blocking refs与outbox结果，并输出可告警的残余风险。不得无限静默WAIT、删除债权、无限自动重试或改APPLIED。后到有效ack可作为新事实持久保存，但不能自动清除DEFAULT_REVIEW；再付款/解锁需受审运营权限和独立恢复协议。资本/换币/清算/保险/ADL升级均单独授权，不因超时自动借款或减免。

## 崩溃、重启与未知结果

| 边界 | 恢复要求 |
| --- | --- |
| wait/outbox事务前后 | 未提交不声称outbox持久；已提交从原action ID投递/查询，P与限制不丢。每次尝试仍先backing检查。 |
| 外部取消已执行但ack未存 | 查询原命令/订单及fill水位，不从内存或“应当取消了”释放F。 |
| 真实ack提交后、付款前 | F可真实下降，P仍在；重开重取版本及先行成交，再决定付款。 |
| U→final中途 | 只能完整旧U或完整新P/N/zero，不能两阶段同时active、短暂零占用或更换duty。 |
| 付款事务中/回执丢失 | cash、P/N消耗、APPLIED及风险restriction/outbox同commit；查原receipt，绝不第二次借记。 |
| deadline与ack交错 | 同一writer序列决定版本；到期先写review则ack不自动解锁，未知提交先查结果。 |

反复失败不得更换action或duty规避预算。恢复逐duty核对自然slot、active representation、内容refs、phase、wait policy/deadline、outbox/确认事件、现金/义务子账/receipt；不直接改materialized hold迎合模型。原样保留历史stage与独立失败记录。

## P/N/H与资本只计一次

确定cut在义务子账确认P/N；H=P+U只是风险占用，**不是又一份会计负债**。应计权益=原cash-ledger会计权益-P+N；U不是确定负债，N不作risk collateral。wait不新增本金、利息或时间费用。实付D让cash减少D且P减少D，应计权益不再第二次减少；实收C让cash增加C且N减少C，应计权益也不重复增加。风险对N的改善仅在现金真实提交时发生。冻结真实释放会影响risk collateral，却不凭空改变会计财富；M20应计88与risk -7→3→3的时点分别保留。

若第三方资本将来代付/注资，必须独立授权、真实来源ledgerproof、明确资金归属和受偿权，不能挪用客户锁或把原rounding reserve当免费补贴。原资金费P只有实际清偿证明后才消除；若转换为贷款/受偿债务，新的principal/利息政策、对手方应收及风险必须同事务明确记录，不能隐藏本金或同时把同一经济债务按P和新principal双扣。当前没有该能力，操作提前拒绝。

## 复审与实施门槛

新增规则/状态/案例/测试见 [amendment-contract.json](../evidence/designs/pending-funding-risk-hold/amendment-contract.json) 和更新后的 [规则矩阵](../evidence/designs/pending-funding-risk-hold/rule-traceability.json)。B1/B2状态仅为 **PROPOSED_SPEC_RESOLUTION_PENDING_INDEPENDENT_RE_REVIEW**。D1只能先选纯函数计算/规则模型，并另行源范围/执行审查；D2无条件保持BLOCKED，直到真实cancel-ack/outbox、先行履约opener、唯一写入者与旧入口fence、完整period事务、deadline/restart和逐笔账务证据全部独立通过。

此次回滚只revert修订文档/JSON，不改变资金、原17例、原独立报告或历史源pin。没有部署/数据迁移/试跑授权；任何未来金融回滚仍须保留due payable、hold、确认成交、cash和完整审计历史。
