# Pure funding hold D1 CODE candidate

**CODE_ONLY / NOT_RUN / NOT_QUALIFIED**。本候选先冻结protocol/proposal `e53d8d98024da3e8a5c34f5f6ac481f2ad00e951`，再写模块与测试。基线公开PR57 ef7508bebd35cac71d9db8fdda896806ce4ade64，65个原Python模块及HTML均原字节保留；规则/数值输入固定PR61 rev2 8008与独立446af。原规格、审查、27例和旧sourceplans没有修改。

## 实际支持

新uta/funding_hold_pure.py没有UTA import，仅用stdlib与exact native整数。DutyKey严格匹配8008 canonical字段/UTC whole-second文本，不规范化别名或另造经济主键；natural slot排除schema/interval/rule_scope，stage refs为typed EXPOSURE/CAP/FINAL_CUT及同duty/scope链接。它们只校shape/link，不认证原cut或外部发布期望。

DutyState只接受REGISTERED、已给定U、已给定P/N/zero的有限单active链，history保留旧阶段；advance_stage核expected revision/ref并返回新immutable数据。不能转APPLIED、取消final或突破已给U上限。CAS只是对当前提供数据的前提检查，真正持久唯一性/命令幂等仍是D2。

aggregate要求调用者显式声明完整提供集合，最多1000同账户同USD-scale记录；检查重复duty/自然slot，拒unassessed而不当0，gross P/U/N/H不净收入。这个complete参数不证明源系统无遗漏，输出不是已认证存储快照。

decompose要求base明确EXCLUDED P/N/H。base accounting/risk/既有IM/MM/order reserve都是外部给定值：只算accrual=accounting-P+N、risk=baseRisk-H、available=risk-IM-reserve；baseRisk已含真实spotF，不再扣F。普通可支出raw=cash-F-H，显示max(raw,0)，是额外现金约束而非withdraw/borrow/order许可。不存在估值、计算IM/MM或把旧borrowable减H的API。

backing_precondition另行检查：外部给定的先行确认义务已清，且F<=max(cash-ownP,0)。WAIT投影保留所有P/U/N/H；eligible仅给cash-ownP与自身P移除、其他H保留的**条件投影**，不修改原DutyState或实际付款。F0允许原负现金算术；F>0不得穿透真实backing。缺quote可标risk_recheck_required，绝不代表已授无行情结算能力或风险恢复。未知prior-confirmation/basis/scale等不会按0或通过处理。

WaitPolicy没有默认值。ActionKey由authority/generation/account/allocation与固定CANCEL_QUERY目标形成，不含duty/claim/policy，从而同action的第二预算记录会被提供集合校验拒绝。WaitRecord固定policy digest/首次start/deadline/highwater与revision；preview_wait仅在给定now与expected revision/policy正确时产生新数据。dispatch_query是**执行前的查询计数投影**：允许时query_counted=true，未来D2应先持久计数和outbox再dispatch，未知结果不能refund；过期/预算用尽时不投影新query。它不观察已发生的late dispatch，也不签发actor权限。

达到deadline或query预算先转sticky DEFAULT_REVIEW，H始终不动；后续观察不重置deadline/attempts。不会截断或饱和变化中的revision：超界拒绝，已review状态同一highwater观察可返回原record，后来观察只推进highwater/revision而不重置或解冻。真实clock/outbox/全局存储CAS、共享action政策审批和防调用者丢弃历史后伪造新record均尚未实现；D1没有认证这些输入事实。

## 单位、测试与拒绝矩阵

USD scale2..8一致，不做scale转换。所有unit输入exact int（拒bool/float/Decimal/int子类），abs<10^38；P/U/N/F/IM/MM/reserve非负。1000条各一active的总P+U+N≤1000*(10^38-1)，H=P+U，conditional derived abs≤4000*10^38；精确Python int，不声称i64，不隐式round/clamp（唯可支出显示0）。时间为外部给定0..2^63-1整数微秒；deadline加法检查，不读钟。query预算1..10000，参数仍须独立风险/容量批准，测试30s不是生产默认。

22个测试方法仅定义、未运行。它们覆盖27例中的支持切片和负例，逐项见 [manual-subset.json](../evidence/designs/funding-hold-pure-d1/manual-subset.json)。例如M10只用给定U600→P246，M12只用给定USD base值230/205；没有算rate或BTC tier。M14 quote80、M15 crash、M17资本和M27整期事务明确UNSUPPORTED，没有把拒绝请求叫整例通过。独立Fraction参考由另一组开发，不复用本模块核心。

## 门槛、部署与回滚

模块无默认策略入口，不接ledger/service/credit/matching。所有转换/聚合/分解/付款或等待投影结果的activation_permission为false；typed key/ref与可构造DTO也不是capability。没有签名、外部expected认证、real ACK/cancel/claim/outbox、APPLIED、borrow/资金/模式/多币/HA/生产能力。

新增模块使候选66py/67runtime，V3仍保留65py/66runtime含义，normalCI_NOT_READY；本分支不更新allowlist或默认金融政策。CODE须另一组独立审查；root随后才选新纯scope和独立producer/执行预算。当前0target import/compile/test/SQL/clock/proc/actor/native/CI，不获生产或金融批准，D2无条件BLOCKED。

回滚只移除未连接模块、测试及本候选资料，无数据迁移；不要用旧计划试跑新源码，也不改原8008/446/ade/旧sourceplans/经济历史。
