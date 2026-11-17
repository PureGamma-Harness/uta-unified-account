# Credit obligation SQLite component：实际提交证据

此组件固定源码 `59a7b32f69bf4797d64c1584b79523657a2974c9`，基于待审设计
`33737dc`。**COMPONENT ONLY / runtime NO-GO / production_approved=false**。
没有修改 `uta/`、冻结设计7aa/十例 JSON、现有 NEXT 或任何长稳目录。

CPU3 实际窗口为 **2026-11-17 10:46:52.989589–10:46:56.961173 UTC**，两次顺序
子命令累计3.971800秒。baseline红断言0.366696秒、候选微测进程3.604480秒；unittest
报告10项通过、3.446秒、无skip。没有 listener、服务、压力或大历史。详见[原始记录](../evidence/runs/credit-obligation-component-59a7b32/execution.json)。

## 原始红态

真实 `ExchangeService`、`DurableLedger`、`CreditService`、`QueueStore`、schema3 父表和
有效 writer token。测试手工构造未来 `kind=BORROW` 的 PENDING 行：现有 SDK **不支持**
这个 enqueue，因此它不是线上接纳、HMAC 或 FIFO 验收。

无新增 obligation 组件时，受信 owner 手动写四条贷款 postings、本金 projection、credit
receipt 和 SUCCEEDED 终态，实际 COMMIT 成功。独立重开确认：BTC customer现金=.4、
本金=.4、pool=.6，ledger3条event（opening现金、pool、loan），loan恰有四条真实legs，
但 decision=0、没有 intent。随后原断言失败、exit1，完整原红未被覆盖。
这说明未来原生义务的组件需求，**不是当前 public managed borrow 成功或普通 HTTP 漏洞**；
A2 的公开方法501仍未改。

## 实际候选结果

| 组件用例 | 实际结果 |
| --- | --- |
| 完整 given tuple | 实际 COMMIT，原CID SUCCEEDED，四条legs、cash/debt/pool及core ledger/credit重开验证通过 |
| 缺decision/terminal/credit/journal/source/allocation/policy | 七案均实际尝试COMMIT，SQLite `SQLITE_CONSTRAINT_FOREIGNKEY(787)`，随后ROLLBACK，重开金融状态与开始相同 |
| decision NULL | `SQLITE_CONSTRAINT_NOTNULL(1299)`，不是模糊SQL错误 |
| 错terminal、负units、sealed=0 | `SQLITE_CONSTRAINT_CHECK(275)` |
| 无intent、错customer | 实际SQL effect trigger `SQLITE_CONSTRAINT_TRIGGER(1811)` |
| 单独关闭检查，故意不装posting gate | 平衡的错customer legs仍在credit-record INSERT被1811拒绝；该错误被catch后，真实COMMIT因缺credit receipt再次787失败 |
| 错decision account | 复合FK实际COMMIT787，不把同ID其他账户decision当成功证据 |
| 完整tuple后合成clock推进6秒 | 原`_market`真实报market_unavailable，caller catch后wrapper再次检查；无native COMMIT，有ROLLBACK，重开无效果 |
| 上例真实ROLLBACK TO | 移除intent/effects/decision，外层REJECTED实际COMMIT；无借款效果 |

所有预期约束失败分别核SQLite扩展码，不把缺表、错误DDL或 `SQLITE_ERROR(1)` 当安全通过。
trace只记录实际COMMIT/ROLLBACK语句，用于区分“请求退出外层事务”和实际native提交尝试，
不将trace或Pythoncounter作为资金授权/完成证明。18个候选临时authority加baseline均已
删除；core只读重开和逐项状态在每案cleanup前完成。

## 真正旧源码进程

归档固定 `45818c0fb1712b3d1daec1323bba9cf35e532992` 的实际 `uta/` 与原LICENSE，
带SHA/provenance，离开 `.git` 也能复跑。四个独立旧Python子进程都使用原tempDB的
canonical path；base及batch阳性对照实际 acquire、deposit 并release，journal1→2。
离线手工加入 prototype `writer_fence_credit_capability` 后，credit及both两案均在旧
`_load`/fence阶段以 `fence_guard_corrupt` 拒绝，journal保持1。stdout没有token/nonce。
所有子进程均由实际wait完成，未留下listener或后台任务。

这个 prototype marker **不是完整能力安装器**，没有新descriptor/全局计划的正式校验。
它只验证真实batch-aware旧代码对新reserved inventory的行为；不替代新binary四组合
运行兼容、权限、资金或恢复验收。

## 剩余否决条件

- 候选只有SQL EXISTS/typed FK/sealed given-leg closing primitive。没有真实 credit
  operation UDF、dispatcher上下文、FIFO、角色/HMAC、全局预算/完整source证书或应用级
  before_commit接线；现有writer UDF则始终是真实core实现。
- given expected legs由fixture提供。实际行匹配它们并不证明该集合由权威借款参数正确
  生成；若expected本身与actual一起错填，组件不能证明canonical经济含义。units与amount
  的完整换算一致性亦留给真正typed operation实现，当前SQL只检查形状/引用。
- probe source的复合PK证明父身份匹配，**没有强制每CID唯一first-source**。组件未实现
  即时DDL authorizer；不能阻止可信owner临时drop/restore候选保护，也不能宣称已通过
  NC-09。这些缺口不能因10项微测通过而关闭。
- 该版本`decision:component-credit:1`是SQL身份占位符，未采用base canonical decision
  hash，现`DecisionAudit.decision()`会拒绝；因此它**不是可查询/可复放credit audit**。
  这个已知片段边界保留原raw，后续改canonical ID必须新源码/新结果。
- freshness wrapper是独立组件提交前hook；合成clock仅本fixture，没有改系统或任何长稳
  job时钟。未声称nativeFK本身能验证行情，亦未证明物理COMMIT瞬间的硬实时保证。
- 这里只跑Python3.12/SQLite3.53.1；跨版本、实际安装包、CI、完整借款模型及上线审批均未
  完成。没有新借款运行时GO，没有数据迁移或部署；回滚为停止组件并删除其自有临时目录，
  不允许对真实authority删库、降级marker或抹去确认资金。
