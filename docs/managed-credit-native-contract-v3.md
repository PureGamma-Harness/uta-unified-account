# Credit 原生提交契约 v3：关闭点与恢复矩阵

追加至冻结设计7aa和[v2](managed-credit-capability-review-v2.md)，不改其原字节。
来源为独立 [NC-01–09](managed-credit-native-contract-review.md) 与
[金融参考审查](managed-credit-golden-finance-review.md)。仍无 runtime GO；下列是需要由
临时 SQLite 组件反例验证的精确候选契约，不是已实现能力。

## 操作作用域与关闭点

作用域只能由真实 single dispatcher 在其金融 transaction 内为已重读的原 due account
head 建立；绑定 guard 对象、connection 对象、owner thread、真实 token、原 CID、kind、
canonical hash。禁止嵌套/跨连接/跨线程，关闭或异常后 finally 清空授权；连接 ID 数值
相同不能代替对象 identity。原 CID 的纯 replay 不创建新 intent、journal 或 decision。

| 阶段 | 真实数据库事实及允许动作 |
| --- | --- |
| CANDIDATE | 精确原 inbox/source/policy/allocation 已核验；还不能写信用资金 |
| INTENT | typed immutable intent 已实际 INSERT；后续 effect 的 SQL EXISTS 必须逐项匹配这行 |
| EFFECTS | 只有所声明的债务前后变化和 canonical postings 可写，所有其他信用变化拒绝 |
| JOURNAL | 原 ledger 已完整封存；BORROW 必须恰好四条 pool/customer/liability/receivable legs |
| DECISION | BORROW 已有完整 credit-audit decision；REPAY 为 NONE，不制造 market/decision |
| CREDIT_RECORD | 实际 credit_commands INSERT 是 native closing point，核 sealed journal、完整有序集合及全部关联内容 |
| SCOPE_CLOSED | 私有授权清空；业务返回仍是 staged，尚无耐久 ACK |
| TERMINAL | 同原 CID 的 inbox SUCCEEDED 已写，FK 仍在同外层事务待检查 |
| COMMIT | before_commit 重核下述终末门槛、原 final fence，再由真实 SQLite 提交 |

BORROW 四个角色为：pool −q、customer +q、该账户 principal liability −q、principal
receivable +q，币种及 event/ordinal 全匹配。实际 ordinal 由 `DurableLedger._normalize`
的 `sorted(normalized)` 决定，不能把这里列举角色的顺序当作 journal 顺序；当前 alice/BTC
例为 customer:alice=0、liability:principal:alice=1、system:credit-pool=2、
system:credit-principal-receivable=3。
仅总和为零不够；重复腿、额外平衡 dummy 腿、错 customer/asset、缺应收、错 ordinal 均
须拒绝。REPAY按实际 interest-first 列表核验，pool只收本金，interest cash只收利息。

credit-record INSERT 的受保护检查必须从实际 DB 读取已 sealed event 及完整 postings。
必须保留原 ledger 的 sealed 后禁止追加保护，并将其及信用关联 UNIQUE/FK/index/trigger
加入即时 DDL 保护，不能临时删除再恢复。单独 journal ID FK 不是完整性证据。

作用域内可回滚的状态只存在于 SQLite。Python context是授权身份/预期值，不是完成日志；
statement失败、ROLLBACK TO、整个rollback后，不能凭observed counters复用已消失的 intent。
每个 effect SQL触发器先确认实际intent，再传digest给纯UDF。完成及最终对账从staged
DB重建。支持同事务多操作时，每个原CID各有独立scope，按实际journal sequence聚合；
较早borrow的audit post-state是中间状态，不强行与后续repay后的最终projection相等。
第一运行切片仍只开放单命令dispatcher，不由此声明批处理/多腿借贷已支持。

## FK 的字面量、NULL 与时序

所有 BORROW 复合外键都是 `DEFERRABLE INITIALLY DEFERRED`，父键必须是确切 UNIQUE。
候选列声明的关键形式如下；它不是可直接部署的完整 schema：

```sql
terminal_state TEXT NOT NULL CHECK(terminal_state = 'SUCCEEDED'),
credit_kind TEXT NOT NULL,
operation_kind TEXT NOT NULL CHECK(operation_kind IN ('BORROW','REPAY')),
decision_id TEXT,
decision_kind TEXT,
CHECK((operation_kind = 'BORROW' AND credit_kind = 'borrowed'
       AND decision_id IS NOT NULL AND decision_kind IS 'CREDIT_BORROWED')
   OR (operation_kind = 'REPAY' AND credit_kind = 'repaid'
       AND decision_id IS NULL AND decision_kind IS NULL)),
FOREIGN KEY(command_id,account_id,inbox_kind,terminal_state)
 REFERENCES uta_command_inbox(command_id,account_id,kind,state)
 DEFERRABLE INITIALLY DEFERRED,
FOREIGN KEY(decision_id,decision_kind,account_id,command_id)
 REFERENCES uta_risk_decisions(decision_id,kind,account_id,business_id)
 DEFERRABLE INITIALLY DEFERRED
```

`inbox_kind`还需NOT NULL/CHECK与operation_kind固定映射。asset/scope/canonical amount/
units/hash/allocation/source/journal等全部必需分量须NOT NULL、typed及有界。REPAY audit
NULL 是有意分支，不能让 BORROW 利用复合FK任一NULL跳过约束。`SUCCEEDED`不是FK列表
中的SQL常量，它必须是带CHECK的真实列。完整候选DDL及实际组件测试仍需独立审。

## 完整 tuple 后的终末门槛

FK齐备不是风险检查已完成的证明。每个BORROW在credit-record关闭点前完成原fullrisk/
quote/limit/pool/末端行情检查，before_commit还必须无条件从实际staged DB重核：
native schema与权限、FK实际ON、typed/bidirectional tuple、完整sealed postings、gross
projection与预算/pool、code/policy/source版本、该事务实际引用原SID的当前freshness及
原final fence。时间检查不能用较早的Pythonsuccess flag代替，也不刷新observed_at。

已观察到金融gate失败：业务拒绝必须由caller真实ROLLBACK TO移除整个命令，或异常
传播使外层rollback；integrity/权限/lease等fatal必须poison外层guard。捕获异常不能清除
这个状态。即使intent/decision/terminal已经齐备，before_commit发现末端行情或金融校验
失败仍必须拒绝实际COMMIT。组件测试须专门覆盖“完整tuple之后才失败”，不能只漏FK。

另一方面，完整且通过所有金融gate的tuple若实际COMMIT后仅回复丢失，已发生贷款必须
保留。SQL不能推断一个被上层吞掉、未影响任何金融验证的任意Python异常。不得笼统承诺
“所有late exception都等于rollback”；其业务结果由原CID的实际耐久状态决定。
检查到物理COMMIT之间仍有暂停/IO窗口，保留现有freshness checkpoint边界，不宣称硬实时。

## 查询恢复矩阵

| 耐久可见状态 | 验证与动作 |
| --- | --- |
| PENDING，金融tuple完全不存在 | 合法未执行/已rollback；先解决旧writer生命周期和原CID的可读状态，再重调度同一CID，不创造新loanID |
| 活跃旧事务内部有staged tuple，外部只见PENDING | 不能从外部读到的absence断言未执行；不启动竞争writer或越过原owner/fence |
| PENDING但可见新credit/journal/intent部分或全部 | 正确native协议不应产生；HALT/corruption，不重做或补造缺失结果 |
| SUCCEEDED，完整且匹配的tuple | 复用原receipt；无论前次reply是否丢失，不重复借款/增加attempt |
| SUCCEEDED但缺/错tuple | HALT，保留原始事实；不能删除终态后重试 |
| REJECTED，无本CID借款intent/effect/成功decision | 合法业务拒绝；返回原错误，不因后来余额变化复活 |
| REJECTED/QUARANTINED却有本CID金融效果 | 不变量失败，HALT；不能把它计为普通技术拒绝 |
| 结果读失败、缺片或无法确认 | UNKNOWN，停止依赖动作；不把读不到当PENDING或债务零，不回收allocation |

pre-cap历史credit receipt不适用“新借款必须有新tuple”的要求：其opening legacy身份/
摘要单独固定，只允许既有只读查询/replay，不能补造CREDIT_BORROWED审计或冒充新增
有审计贷款。新v2 POST如何处理“旧credit receipt有、durable inbox无”的CID必须单独
定义（优先要求既有receipt只读查询）；不能伪造一个不存在的inbox SUCCEEDED回执。

## 组件 SQL 验证的最小边界

仅在全新临时DB复用真实基本账本/命令父表并安装明确候选DDL。先保留无新约束时的真实
红态：credit tuple不完整却可提交；然后逐项验证candidate FK/closing point。错误类型、
`in_transaction`、实际COMMIT/rollback与重开后的逐币效果都记录。再用真正旧源码进程
核base/batch/credit/both inventory positive/negative controls。这个组件不会接入runtime、
开启HTTP借款、修改现有authority或代替独立生产验收。
