# Managed credit 设计验收与 SQLite 组件交付

基线 `45818c0`；本分支 `feat/managed-credit-capability`。当前只关闭算术/部分设计欠缺，
新增独立参考与真实 SQLite 约束组件。**没有修改 uta runtime，没有开放新借款；A2 的
501 保留，runtime/production NO-GO。** 这是自动工程组的审查记录，不是真实金融负责人
签字。原7aa设计与十例JSON字节保持不变。

## 可审查交付

- [原设计](managed-credit-capability-design.md)、[v2输入/错误/范围补充](managed-credit-capability-review-v2.md)、
  [v3关闭点及恢复矩阵](managed-credit-native-contract-v3.md)，以及
  [不可执行的完整设计模板](../tests/fixtures/managed_credit_v1_canonical_example.json)和
  [尚未生效的规则追溯提案](../evidence/rules-managed-credit-proposed-v1.csv)。
- [独立金融参考](managed-credit-golden-finance-review.md)：十例48个数值字段无算术差异，
  15个需补充输入/提交分支条件；24个native/policy字段未执行。独立标准库Fraction，不
  调生产核心；7个小测试。固定预算模型36状态/1152边成立，错误回收UNKNOWN片额度则
  出现真实模型债务6>预算4。它们不是SQL、容量、复制或客户借款成功证据。
- [独立原生契约NC-01–09](managed-credit-native-contract-review.md)及
  [金融设计关闭审阅](managed-credit-finance-closure-v3-review.md)。完整tuple后的金融
  终末gate和恢复矩阵在规格层面已澄清，实际runtime仍需实施及独立验收。
- [SQLite原始组件](managed-credit-obligation-component.md)与
  [canonical/跨Python后续](managed-credit-component-followups.md)。源码、原红、实际
  COMMIT/ROLLBACK、重开结果、SQLite代码/分类、旧源码与许可证/摘要全部保留。

## 实际运行边界

CPU3、私有全新临时库，两次短窗口累计 **7.997538秒**，均含在预注册30秒预算内。
首窗源码59a7b32：保留手工受信owner贷款真实COMMIT后的红态，候选10项3.12微测通过。
后窗源码daea681：仅必要的3.12 canonical reader正例1项，以及3.10微文件10项通过。
没有3.13结果、3.12后续全文件重复或冻结集成全量结果，不能捏造这些验证。

缺decision/terminal/credit/journal/source/allocation/policy的候选实际COMMIT被外键拒绝，
重开无效果；NULL/CHECK/RAISE逐类核验。3.12原生扩展码真实保留，3.10无native属性时
维持null，仅将builtin IntegrityError固定消息归类，绝不声称观察到不存在的787。
完整tuple后只推进本fixture合成时钟，原_market真实失效；组件wrapper重查并rollback。
真实ROLLBACK TO可清除义务并提交REJECTED。该wrapper不是已部署的生产before_commit。

每个测试运行时各有4个真正458旧源码子进程：base/batch阳性可acquire及deposit；离线
手工增加prototype credit marker后credit/both阴性。该prototype不是完整cap安装器。
所有自有临时authority已清理、子进程已wait，无listener/服务/压力/大历史，也没有改任何
现有NEXT、冻结763、原887或活动observer目录/时钟。共同宿主短功能测试不是吞吐测量。

## 后续最小实现与否决点

候选组件只证明typed/deferred引用、given-leg关闭检查及提交前hook的特定行为。expected
legs由fixture给定；同错的expected/actual不能证明权威经济语义。实际credit UDF、精确
dispatcher scope/生命周期、即时DDL权限、每CID唯一first-source、已有债务UPDATE/DELETE/
REPAY原生接线、真实global allocation及专用credit artifact/replay均未实现。

下一层应先实现默认关闭的持久cap/预算/typed intent/UDF/immutable schema，实际测试原
CID、完整tuple后末端失败、native role/token、回滚及旧码；再接专用credit audit/operation
replay，最后才接single durable BORROW及显式HMAC borrower权限。credit cap时batch=0，
不静默改变已验证无credit的batch配置。source/template的null code档案和synthetic来源
必须被真正客户执行路径拒绝，不能拿设计内容hash当认证/到账证据。

产品层还有独立否决：现贷款distress监督为 `BLOCKED/loan_liquidation_adapter_required`，
没有贷款抵押品兑换/自动违约偿付、完整保险/ADL、真实利息调度、外部贷款人/托管确认、
稳定币真实结算或金融签字。即使上述native工程完成，也不能称现货借贷达到生产闭环。

没有部署或数据迁移。组件回滚仅删除自己的已停止临时目录；对未来真实authority必须
保留marker、预算、原CID和资金/nonce水位，停入口并前滚修复，禁止删库、降级门禁或
回退备份抹去已确认贷款。
