# 冻结 credit golden 的独立金融设计审阅

审阅对象固定为 `7aa48202ddc4663a1e815609716c1a6b7110289f`。本分支
`review/credit-golden-finance` 只新增独立参考计算、很小的 oracle 测试、原始结果和本文；
没有修改设计、原 JSON、`uta/`、DDL 或任何运行时。**结论：在下列公开条件下，48 个数值
字段无算术差异；原生事务、恢复和上线仍是 NOT EXECUTED / NO-GO。** 不能称为“10 个
生产案例通过”。15 个比较还依赖补充的输入或已提交分支条件；24 个 outcome、reason、
无副作用、回执及原生布尔字段保留为未执行，没有用 `assert true` 代替验证。

独立性：参考实现只导入 Python 标准库，以整数和 `Fraction` 重建输入快照。没有读取或
调用生产估值、credit、风险、rounding、ledger replay 函数，没有 SQL、连接、服务、压力或
长测。公式来源是冻结仓库已有的 [Cross 规则](margin-rules.md:15)，而不是根据 expected
反解公式。先根据 assumptions、request 和明确展开的 prose 输入计算，最后才比较 expected；
故意改 expected 和故意改原始 USD 输入的两个测试确认 oracle 会独立发现差异。

原字节 SHA256：

| 文件 | SHA256 |
| --- | --- |
| `docs/managed-credit-capability-design.md` | `3a8e70a261d8d11291f9cb634955e3ea6931037d5c8c13d6e0269b756efbd7dd` |
| `tests/fixtures/managed_credit_v1_golden.json` | `494a6a88397f9677cdb82bb1bcedf9338a0441cd5df6cd5acfe2fd28209be260` |

执行命令及完整 stdout/stderr/退出码在 [原始执行记录](../evidence/runs/credit-golden-finance/run.json)，
逐字段结果、所有中间风险值、报价各上界、明确的补充假设和未执行字段在
[原始计算 JSON](../evidence/runs/credit-golden-finance/review.json)。复算命令：

```bash
python scripts/review_credit_golden_finance.py --output evidence/runs/credit-golden-finance/review.json
python -m unittest discover -s tests -p test_credit_golden_finance_reference.py -v
```

单位与计算口径：USD/BTC cash、principal、interest、receivable、pool 和 allocation 都是各自
原币数量；资产 scale 都为 8。`0.4 BTC = 40000000` minor units，`.01 BTC` 数量步长为
`1000000` minor units；二者不是同一精度门槛。价格是 synthetic USD/BTC，风险、LTV 值和
IM/MM 均为 synthetic USD。本金/利息投影非负，客户本金 liability ledger 对应负数，system
principal receivable 对应正数。allocation 的 gross debt 仅为同一原币的 **principal+interest**；
它不限制现金亏空 `cash_deficits`，也不是全部经济风险的全局上限。现金亏空仍应按
[原规则](margin-rules.md:11)进入全额 USD 债务和权益；本十例没有该输入，参考实现显式取零。
account principal limit、account total debt USD limit、local asset limit、allocation 和 pool
分别校验，不能互换。

逐案结果和输入完整性：

| case | 独立重算 | 输入、条件及证据边界 |
| --- | --- | --- |
| 001 | gross cash USD100/BTC.4；principal .4、interest0、pool .6、receivable .4、liability -.4。资产市值140、会计权益100；抵押132、loan value66、债务40；risk92、IM8、MM4、available84。next portfolio quote .26，含 allocation/pool 后 .1。 | 从 baseline 全新构造。缺机器字段 shard，按 prose 的 shard0；假设没有其他客户债务、冻结、负现金或未结算。资金证明、市场 SID/时间、instrument/catalog/policy 内容、CID/source/versions 未提供，不能据此授权执行。 |
| 002 | 从独立001快照，`.4+.11=.51>.5`，而 portfolio quote `.26` 足够；local allocation 单独导致拒绝。 | 不在003或后续动作之后执行。`shard_budget_exceeded` 是设计标签；真实 reason 优先级/HTTP契约和 no-financial-effect 未验证。 |
| 003 | 从独立001再借 `.1`：cash/principal/receivable .5、pool .5、interest0；risk90、IM10、MM5、available80、allocation headroom0。 | 它是001的另一分支，不是002之后的串行脚本；数字是借款所有门槛允许并原子提交后的预期，不是实际成功回执。 |
| 004 | reserve `8×100×1×.1=80`；available `92−8−80=4`。四界中 margin bound `4/120=1/30 BTC`，向下 `.03`。`.04` 违反本次保守报价；`.03` 后 principal/cash .43、pool .57、risk91.4、IM8.6、MM4.3、available2.8。 | `reserved_margin_USD=80` 没有当作计算输入。乘数1未在原JSON显式给出；symbol、side、产品 ACTIVE、quantity unit、tick/min-notional、完整订单状态缺失，因此 reserve 与后风险有条件成立。挂单 reserve 不作为仓位IM或冻结重复扣减；挂单并非已成交。即便 `.04` 的到账现金使 projected available 仍为正，也不能绕过原保守报价。 |
| 005 | 两个各有 USD100 的新账户、共同 shard0/pool1、初始 shard debt0：第一借 .3 后 pool .7、shard debt .3；第二请求 .3 会使 shard debt .6 而拒绝；它的最大可借 `.2`。若改借 .2，则 pool .5、合计 principal/receivable .5。 | 原case只给自然语言，没有 request/initial structured fields。第二账户资金具体数量、开场债务、执行顺序及 pool 值均须补全；本报告明确补为每户 baseline、先后执行、共享 pool/receivable/debt，不能把这项数值吻合当成并发串行化证据。 |
| 006 | shard0 gross debt .5、shard1 0；allocations `.5+.5=1`。本片借 `.01` 产生 `.51>.5`，即使全局总债务 `.51<=1` 仍拒绝。 | 只足以重算本地预算谓词。客户、principal/interest拆分、各片pool/receivable、risk缺失，不能构造完整金融后态。另一片未用额度不是本片的权限。此例没有 UNKNOWN 或跨片同步提交。 |
| 007 | 从独立001偿还 .1：customer BTC .3、principal/receivable .3、interest0、pool .7；还息0、还本.1，allocation headroom .2。 | 偿还分配仅用原币现金及 p/i，不调用 price/risk；断价/halt 下的真实授权、guard 和 receipt仍未执行。若按固定历史价展示风险，则risk94、IM6、MM3、available88，但不能误说还款需要这个行情。 |
| 008 | 无可独立计算的数值输入。 | amount/asset、完整初态、失败位置、transaction状态、实际持久tuple均缺失。全部四个 expected 布尔值只能由真实 native/deferred FK、COMMIT、rollback/reopen 验证，当前不通过也不失败，状态为未执行。 |
| 009 | 仅在001原贷款已真正 COMMIT 的分支，同 canonical CID 重试是数值恒等：additional loan0、principal .4、pool .6。 | 没有实际 CID/source/hash/nonce/receipt store。original receipt复用及first-source不可覆盖未验证。丢 COMMIT reply 不等于已证明 COMMIT；读失败继续 UNKNOWN，不能认定零债务、新建CID或回收额度。原事务实际rollback时须先权威确认PENDING，不能沿用已提交001快照。 |
| 010 | `.00000001 BTC` 恰为1 minor unit，但仅为数量step的 `1/1000000`；应按step谓词拒绝，不做数量取整。 | 数量精度有效不能代替产品step。reference未改amount；真实入口拒绝顺序、API reason和无资金效果仍须验证。 |

以001为例，报价来自四界 `min(9.6, 99.6, .26, .7)=.26 BTC`，再分别取 pool `.6`、
local asset headroom `99.6`、allocation headroom `.1` 得 `.1 BTC`。折扣先作用于 gross BTC
`.4×100×.8=32 USD`，再全价扣 debt40；先净额BTC会错误得到risk100而非92。001借款的
symbolic BTC postings 为 customer `+.4`、pool `−.4`、principal receivable `+.4`、principal
liability `−.4`，逐币和为零；这验证参考分录算术，不证明真实科目、不可变日志或托管真实性。

`baseline_shard_pool_cash_BTC=1` 与每片 allocation `.5` 并不矛盾：pool 是可用资金，allocation
是贷款债务上限。若两片各套用 baseline，pool 合计可以为2而预算总额为1；它们不能相等推断。
但原JSON没有唯一资金source claims，不能证明两个pool没有复用同一外部资金来源。所有成功
数值均以已核对 opening pool/receivables 为条件，预算证书不证明真实资金到账。

额外历史利息还款的独立推导：任务另给了完整新输入而没有 expected；它不改原十例。开场为
USD100、BTC cash .5、principal .4、interest .05、pool .6、principal receivable .4、interest
receivable .05、interest cash0。按 [.16–19 的 opening 规则](managed-credit-capability-design.md:16)，
cap后零新利率不会抹除历史利息。同币 repay .1 先还息 `.05`，再还本 `.05`：

| 指标 | before | after | 单位 |
| --- | ---: | ---: | --- |
| customer cash | .5 | .4 | BTC |
| principal / principal receivable | .4 / .4 | .35 / .35 | BTC |
| interest / interest receivable | .05 / .05 | 0 / 0 | BTC |
| pool cash / interest cash | .6 / 0 | .65 / .05 | BTC |
| loan gross debt / allocation headroom | .45 / .05 | .35 / .15 | BTC |
| gross asset value / debt value | 150 / 45 | 140 / 35 | USD |
| accounting equity | 105 | 105 | USD |
| collateral / loan value | 140 / 70 | 132 / 66 | USD |
| risk equity | 95 | 97 | USD |
| IM / MM / available | 9 / 4.5 / 86 | 7 / 3.5 / 90 | USD |

`pool increase=.05 BTC`，`interest cash increase=.05 BTC`，而预算释放为消灭的
`principal+interest=.1 BTC`；不能把利息付款全部当成pool本金现金，也不能只按本金变化释放
gross debt预算。参考 repay postings：customer `−.1`，principal liability `+.05`，interest
liability `+.05`，principal receivable `−.05`，interest receivable `−.05`，pool `+.05`，interest
cash `+.05`，逐币和为零。opening 的 BTC.5 不是原baseline发放 .4 后所得 .4，必须作为独立
已核验源快照保留；该算术没有证明其历史来源真实性。

极小预算图只验证一个有明确假设的预算命题。两片静态 `A=(2,2)`，`B=4`，原币整数单位，
从 debt `(0,0)` 出发，borrow/repay各0..2；每个动作分别覆盖实际commit/rollback和已知/未知
回执，得到36个truth/observation状态、1152条边。每个truth状态均满足 `0<=D_s<=A_s`，因此
`ΣD_s<=ΣA_s<=B`。假设包括：opening debt符合分配、完整不可变身份绑定证书、没有新interest/
adjustment/transfer、所有本地commit按staged principal+interest检查额度、没有旁路writer。
UNKNOWN只改变观察，不改变实际债务或分配；repay只有真正commit才减少债务。模型中的0数量
是无操作边，不赋予生产零额请求权限。该图没有模拟SQL/FIFO/lease/时钟/持久事务/HA。

unsafe对照明确删除了一条必要前提：两片真实借满至 `(2,2)`，shard0回执UNKNOWN；错误地把
其allocation2回收给shard1，改成 `(0,4)`，随后shard1再借2，真实债务变 `(2,4)`、总额6>4。
这个错误实现即使保存 allocation总和4也会超贷，因为它已将未知的真实债务2当成零。正确的
opening/current debt检查在allocation变更时就会拒绝，且本切片本来禁止该变更。它是纯模型
反例，不是对现实现已复现的漏洞。

尚阻断 runtime GO 的规格与验收缺口：

1. **完整tuple后的late exception尚缺明确提交门槛。** [设计83–99行](managed-credit-capability-design.md:83)
   已明确缺一侧不能提交、必须savepoint rollback，也列出before_commit；但没有给出“所有
   intent/decision/SUCCEEDED/完整分录都已存在后，末端risk或freshness抛错且caller吞异常”的
   精确操作状态和native提交规则。deferred FK只能发现引用缺失，不能自行证明末端gate已完成。
   必须定义最后成功封口/提交证明与逐命令失败状态，或before_commit独立重做所有终末门槛；
   仅检查引用、typed内容、预算、pool不足以描述该路径。此处是设计待补，不是声称已实现漏洞。
2. **恢复状态矩阵不完整。** [148–151行](managed-credit-capability-design.md:148)允许确认PENDING后
   重调度，同时说任何credit row/intent/decision/ledger缺失均失败关闭。合法未执行PENDING
   本就不应有这些金融rows，须明确按terminal/PENDING/REJECTED分别验证哪些应存在、哪些
   必须不存在；query失败为UNKNOWN，局部tuple为corruption，原canonical hash冲突为409。
   009只覆盖已commit快照，未覆盖实际rollback、查询未知、缺片、相互矛盾或重启新owner。
3. **跨片总额度规范已有，golden验收覆盖不足。** [40–50行](managed-credit-capability-design.md:40)
   已要求sum<=global和UNKNOWN不回收，不能报告成“没有规范”。006没有UNKNOWN，005只有同片；
   缺两个真实片同时借至各片上界、某片COMMIT未知而另一片继续、global超额/漏片/错identity/
   不一致证书、opening interest使gross超cap、repay释放后的新借款等实际验收。上述纯图仅检验
   在固定分配和真实本地检查前提下的数学结论，没有验证这些前提。
4. **输入与审计内容仍未落成可执行契约。** 004乘数/产品、005结构化多账户输入、006完整状态、
   008失败窗口、009实际CID tuple不足；new credit policy/budget/source claims/canonical IDs/
   时间/版本未给规范实例。`reason`字符串尚无route状态码、重试性和优先级契约。旧二进制门禁、
   native guard、专用artifact/replay及HMAC的全部义务仍是设计，本文数值匹配不能替代它们。

最小 runtime 验收边界应继续保持新借款501，直到在**新的合成临时目录**中具备真实native
能力、完整typed档案和逐命令savepoint后，再由独立组执行下列有界实际路径：

- 从明确快照执行001/002/003/004/007/010和历史息repay，逐客户现金、p/i、全部system
  receivable/pool/interestcash、逐币完整postings、account versions及credit/audit/receipt重开核对。
- 单连接两账户争用同片`.5`，以及两个真实片各至`.5`；检查完整证书错误和opening gross超额
  在第一笔资金写入前拒绝。禁止把UNKNOWN片额度释放或搬迁；不要求跨DB原子扣总额度。
- 每个真实late failure窗口分别覆盖：缺decision、缺terminal、完整tuple之后末端freshness/risk
  失败；caller捕获异常后尝试COMMIT不能保留贷款。再验证真实ROLLBACK TO清掉intent、资金、
  audit和成功记录，外层可以只提交REJECTED；重开核对不得只观察临时内存状态。
- 实际COMMIT成功但回执丢失、实际rollback、原CID查询失败/矛盾、重启新owner逐项查询恢复；
  原CID同内容不重复放款、异内容409、first-source不覆盖。对有未知债务的另一片操作仍只消费
  自己固定额度，不能挪用。另测缺native UDF/错role/失效writer/旧二进制及精确schema拒绝。

这些是待实现、待另授权执行的native/集成边界，本次没有运行。7个纯参考测试通过只验证oracle
独立性、gross口径、历史息分配、坏证书拒绝、静态预算图和step/独立分支，不是金融负责人真实
签字、运行时安全、生产放行或长期容量证据。
