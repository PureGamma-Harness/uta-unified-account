# D1 pure funding hold：最小子集协议

PROTOCOL_FIXED_BEFORE_CODE / NOT_RUN。公开基线ef7508bebd35cac71d9db8fdda896806ce4ade64与d1fd运行时字节相同，保留65py+1HTML的66文件。规则固定PR61 rev2 8008及独立446af，原规格、27例、审查及sourceplans不改。精确来源见 [proposal.json](../evidence/designs/funding-hold-pure-d1/proposal.json)。本协议先冻结，然后才实施CODE。

新模块提案uta/funding_hold_pure.py仅用dataclasses/datetime/hashlib/json/re等stdlib；datetime只校验给定文本，不读时钟。不import任何UTA模块，不接ledger/service/credit/撮合/actor/default策略。全部结果activation_permission=false，不授金融能力。

## API与精度

DutyKey按8008 exact canonical字段算duty_id与natural slot，不归一化时间/标识符；cut/cap是typed refs，不是经济主键。advance_stage只校纯数据revision/active-ref CAS并返回immutable representation/history，不是持久CAS或APPLIED。aggregate检查完整提供的同账户/同USD-scale集合、唯一duty/自然slot/active，输出gross P/U/N/H；N不抵H。

decompose要求给定base accounting/risk equity**明确未含P/N/H**。accrual=baseAccounting-P+N，risk=baseRisk-H，available=risk-baseIM-orderReserve；baseRisk已包括真实spotF，不再扣一次。另给raw cash-budget=cash-realSpotF-H及max(raw,0)。只作precondition分解，不是估值、健康/准入许可、新IM/MM或quote。

backing_precondition仅投影自身P付款：给定确认义务已清，且F<=max(cash-ownP,0)。WAIT时P/U/N/H不变；eligible只投影cash减自身P、其它H保留，不写现金/真实ACK/receipt/APPLIED。普通支出budget与强制义务backing分开，F0可投影负现金，财务能力/风险状态仍为D2。

preview_wait/validate_wait_records只用外部now/highwater与必填versioned policy/first-start/deadline/attempt记录。稳定shared action_id绑定同一policy与预算，未知查询结果按已dispatch一次保留计数，不得因新duty/claim重置或取更大政策。无读钟/outbox/ACK/持久去重。deadline或预算先耗尽即sticky DEFAULT_REVIEW，债权H不forfeit。

固定USD，scale原生int2..8且全体一致；没有scale转换/隐式rounding。金额输入exact int、abs<10^38，拒bool/float/Decimal/子类。P/U/N/F/IM/MM/reserve非负，cash与base权益可负。最多1000duties，P/U/N/H各≤1000*(10^38-1)，derived abs≤4000*10^38；精确Python int不是i64，不裁剪（唯可支出显示clamp0），越界拒绝。

## 支持与拒绝

未知/缺失base、不完整提供集合、重复自然slot、CAS冲突、未定阶段当零、跨账户/币种/scale、ref类型/链接错误、缺等待政策及时间回退均显式失败，不能当0。Refs只shape/link校验，不认证原cut或外部expected；输入事实不是已认证状态。

不支持qty/mark/rate生成cap或现金腿、全估值/IM/MM、多币、borrowable/新borrow、资本替代、资金/托管/模式、真实ACK/cancel/outbox/claim/ledger/apply/整期原子性。原M14 quote80不编作生产期望；M10只校给定U600→P246等unit切片。原17+10须逐项列支持/拒绝矩阵，不称27整例已覆盖。

## 门槛与回滚

后续CODE与测试仅定义、未运行；独立Fraction参考另组写且不复用生产helper。新增模块使候选66py/67runtime，normalCI_NOT_READY，需另审显式下一inventory，不改V3/default。当前0target import/compile/test/SQL/proc/worker/CI，D2无条件BLOCKED。回滚只移除未连接模块/测试/协议，无数据迁移，原经济历史和审查不变。
