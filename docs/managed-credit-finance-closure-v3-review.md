# Credit v3 的独立金融设计关闭审阅

只读审阅冻结集成提交 `83d595f4eef4eb92203dc0d988fc4e36c121b453`，源目录
`/workspace/uta-managed-credit-capability`。本次仅新增独立关闭记录、小型标准库JSON/Fraction
核对和原始证据，没有合入运行时代码或复跑原36状态预算图，没有SQL、服务或生产测试。
原7aa设计与10例JSON的SHA256均与首轮完全一致。

**结论：首轮两项“缺少明确设计契约”的阻断已经关闭；原生实现及验收仍未关闭，保持
NO-GO。** 未在本轮新增材料中发现确定的金融公式矛盾。本文是独立设计判断，不是金融
负责人或实际人员签字，也不是native component或UTA runtime通过。

| 首轮问题 | v3关闭依据 | 仍需实际证明 |
| --- | --- | --- |
| 完整tuple后发生末端金融gate异常，FK齐备仍不足以禁止提交 | [v3第73行](/workspace/uta-managed-credit-capability/docs/managed-credit-native-contract-v3.md:73)要求closing前完成fullrisk/quote/limit/pool/末端行情；before_commit无条件从实际staged DB重核。第79行要求业务拒绝真实ROLLBACK TO或外层rollback，fatal poison不可被catch清除；即使tuple齐备，末端金融校验失败仍拒绝COMMIT。第84行保留已COMMIT但reply丢失的真实贷款，并承认无法从SQL推断无金融影响的任意Python异常。 | 完整tuple之后的freshness/risk失败、catch后尝试COMMIT、savepoint rollback及重开结果；持久触发器、guard、UDF和真实before_commit的准确实现。规格文字不能证明这些机制已经运行。 |
| 合法PENDING不应已有金融tuple，与缺tuple即HALT的笼统说法冲突 | [v3第93行](/workspace/uta-managed-credit-capability/docs/managed-credit-native-contract-v3.md:93)分别定义tuple完全不存在的PENDING、外部PENDING但旧事务活跃、可见部分金融tuple、SUCCEEDED完整/不完整、REJECTED/QUARANTINED有无金融效果及UNKNOWN。合法PENDING须先解决旧writer生命周期，UNKNOWN不回收allocation。第102行将opening legacy receipt单列。 | 原CID实际commit/rollback/丢reply、查询失败/缺片/矛盾tuple、owner重启及fence生命周期；不得用内存状态或仅查询到PENDING绕过活跃事务。 |

第二项只关闭恢复状态分类缺失，并未替设计作者决定所有HTTP旧数据兼容行为。
[v3第104行](/workspace/uta-managed-credit-capability/docs/managed-credit-native-contract-v3.md:104)
仍显式留下“旧credit receipt有、durable inbox无”的新POST处理方式。该路径在接线前必须
确定，例如拒绝新POST并保留只读原receipt查询；不能伪造inbox SUCCEEDED、重做贷款或把
opening历史补成新audit。这是明确的接线范围待定义项，不妨碍有界native组件审查。

canonical example补充程度：

- [catalog第13行](/workspace/uta-managed-credit-capability/tests/fixtures/managed_credit_v1_canonical_example.json:13)
  给出synthetic USD线性BTC-PERP、active、multiplier1、step/tick .01、min-notional1及risk tier。
  [v2第9行](/workspace/uta-managed-credit-capability/docs/managed-credit-capability-review-v2.md:9)
  明确004的8为8 BTC等价合约数量，reserve为 `8×1×100×.1=80 USD`，不是现金支出或MM。
  独立重算得到available4、保守quote `floor_.01(4/120)=.03 BTC`，与原golden一致。
- [initial state第196行](/workspace/uta-managed-credit-capability/tests/fixtures/managed_credit_v1_canonical_example.json:196)
  是明确的case001独立快照；[v2第14行](/workspace/uta-managed-credit-capability/docs/managed-credit-capability-review-v2.md:14)
  明确所有starting_after克隆不可变已提交状态，005两户各USD100、共享pool1/额度.5，008/009的条件性不变。
  canonical本身不是004完整订单行：其数量8、limit100仍须读原golden及v2，没有订单ID/side/
  filled quantity/version等机器输入；因此不宣称十例都已成为可直接提交的完整fixture。
- risk policy、credit policy、layout、global budget和market payload均有规范字节及内容ID。
  两片各50000000 allocation units，总和100000000等于global；opening p/i为0，source引用
  不同，identity与layout互相匹配。各片pool100000000总和为2 BTC与预算1 BTC不冲突。
  principal+interest原币预算排除cash deficits，零新interest/fee、禁止cap后funding及batch0
  均显式。原始case001风险再算为collateral132、loan66、debt40、equity92、IM8、MM4、available84。
- [市场与时间第75行](/workspace/uta-managed-credit-capability/tests/fixtures/managed_credit_v1_canonical_example.json:75)
  固定observed_at为00:00:00，selected_at为00:00:01，last_checked为00:00:02，max age5秒；
  本轮只按记录时刻比较1秒/2秒，不借今天时钟证明历史新鲜度。physical_commit_time为null，
  is_actual_execution为false；v3保留检查至物理COMMIT的checkpoint边界，没有虚构硬实时保证。
- [artifact第238行](/workspace/uta-managed-credit-capability/tests/fixtures/managed_credit_v1_canonical_example.json:238)
  的source manifest、loaded engine digest、Python/SQLite runtime均null，资格明确为
  `NOT_IMPLEMENTED_MUST_REJECT_AS_REAL_DECISION`；source为synthetic_fixture，明确不是实际认证
  回执，pool证明也明确不是外部到账确认。内容hash吻合只能证明设计字节一致，不能弥补这些缺失。
- canonical未提供独立持久account-credit/local-asset-limit文档、完整journal/intent/decision/
  source receipts和实际code artifact；不能单凭此模板批准真实贷款。本轮不将这些有意的
  design-only缺项误报成已完成的执行档案。

[proposed CSV](/workspace/uta-managed-credit-capability/evidence/rules-managed-credit-proposed-v1.csv)
四行均为`NOT_EFFECTIVE_DESIGN_ONLY`，将静态数量预算、小模型、48字段数值与待实现native/
artifact/多片效果分开。它是追踪提案，不是已生效规则、外部依据或负责人签字。

原始核对见 [closure-v3.json](../evidence/runs/credit-golden-finance/closure-v3.json)，包括6个
源文件SHA256、7份document canonical payload/hash、业务payload hash、引用关系、scale/
allocation、少量case001/004数值、时间和design-only标志，共68项一致。独立核对脚本为
[review_credit_design_closure.py](../scripts/review_credit_design_closure.py)，固定使用显式source cwd下的
`git show 83d595f:<path>`读取不可变blob，hash变化即停止；执行记录见
[closure-v3-run.json](../evidence/runs/credit-golden-finance/closure-v3-run.json)。审阅中集成worktree
发生推进，一次直接读取当前文件因hash改变正确停止，未将其混入83d595f结论；原始停止记录
保存在 [source-race记录](../evidence/runs/credit-golden-finance/closure-v3-source-race-run.json)。

此关闭只允许继续完成候选组件验证。真实native SQL、旧二进制四组合、完整tuple后末端失败、
同片争用、跨片并发/UNKNOWN不挪额、queued repayment及借款路由/权限/artifact replay仍缺
实际证据。wrapper的hook或Python标记均不能当已部署原生UDF。本轮没有运行或验收它们，
保持managed新借款501及runtime/production NO-GO。
