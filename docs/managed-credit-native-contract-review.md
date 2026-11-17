# Managed credit native contract：第二轮只读审查

审查输入固定为 `7aa48202ddc4663a1e815609716c1a6b7110289f` 的
`docs/managed-credit-capability-design.md` 及十个手算 JSON 案例，运行时代码基线
`45818c0`。本提交只增加此审查记录及来源摘要；没有改设计、fixture 或运行时，没有
执行 SQL、服务、计算器、测试或负载。结论是 **设计补齐前不得进入 runtime 实现**，
不是发现一个已经上线的漏洞，也不是正式金融、安全或生产签字。

下面的行号均指固定输入 SHA；后续修订不能覆盖其原字节。

## 必须关闭的设计项

| 编号 | 固定输入位置 | 结论和最小先决条件 |
| --- | --- | --- |
| NC-01 | design:66–85，尤其 78 | 前两类 FK 明说 deferred，审计复合 FK 未明确时序；intent 在 effect 前，decision 在 post-risk 后的流程不能依赖默认 immediate FK。必须给出所有实际 CREATE TABLE/UNIQUE/FK 定义，BORROW 的 decision 四元组逐分量 NOT NULL，明确 `DEFERRABLE INITIALLY DEFERRED`；REPAY 的 nullable audit 分支须由 kind CHECK 限定。scope/account/asset/amount/hash/allocation/source 其余必需分量也须 NOT NULL，防止复合 FK 中 NULL 免检。constant terminal 必须 CHECK `SUCCEEDED`，不是任意调用方文本。 |
| NC-02 | design:66–99 | 只有 intent 的正向 FK 不会阻止整个 intent 被漏建。每个 debt/posting/credit-record/相关终态 effect gate 必须在同一连接实际 staged DB 中找到匹配 intent，不能只认 Python active flag。原生 intent INSERT 是独立 candidate-create 阶段，不能要求该行在 BEFORE INSERT 前已经存在；后续 effect 阶段必须要求真实行已存在。before_commit 从 DB 重建双向 obligation↔effect 集合，而不是只扫描“已经存在的 intents”。 |
| NC-03 | design:91–99 | Python UDF 的 observed-set、次数或 completion flag 不随 SQLite statement/SAVEPOINT rollback 撤销。它们不能证明 postings 已写入或已经回滚。scope 仅提供授权身份/期望值；完成与数量只能来自真实 staged 行。建议 native trigger 以 SQL EXISTS 选择实际 intent 并把其 digest/字段传 UDF，避免未经实测就依赖 Python UDF 递归执行 SQL。 |
| NC-04 | design:79、93–99 | journal FK 只证明 event 存在，不证明已 sealed、精确对侧或完整 posting 集合。必须冻结 native closing point：例如 borrowed/repaid credit-record INSERT 的受保护检查验证已 sealed journal 和实际完整 multiset，随后禁止向该 credit journal 追加 posting；intent 的 deferred credit-record FK 强制该检查发生。或给出等价方案。四条 BORROW legs 必须含 pool、customer、本金 liability、本金 receivable，不能只检查总和为零或 credit-owned accounts。 |
| NC-05 | design:59–70、83–99、148–152 | 作用域生命周期尚未足够精确：必须定义 owner thread/connection/guard identity、进入/退出、嵌套拒绝、异常 finally、statement rollback、ROLLBACK TO 后重试、连接关闭/ID 复用以及当前 token 失效。不得让旧作用域在 intent 已回滚后授权新写。合法同事务 BORROW→REPAY 需要独立 scope 和原 CID；不能把最终 DB 状态强行等同于先前 borrow audit 的中间 post-state。最终 projection 核验应按所有真实已提交的本次操作聚合。 |
| NC-06 | design:19、62、69、76、158；credit.py:369–388 | 当前 public `repay` 自行起金融事务，并没有 durable inbox。新设计却要求 REPAY scope 只能由 dispatcher 创建，且每个 intent FK 指向同 CID 的 SUCCEEDED inbox。这与“原 public repay 全部不变”不能同时成立。须明确 credit-cap 后的新 direct public repayment 是否 501，历史同 ID replay 是否仍先返回，或另审受控协议；不得偷偷制造 SUCCEEDED inbox。正常持久还款应保留 halt/断价、利息优先、资金权限。 |
| NC-07 | design:86–87；storage.py:144；writer_fence.py:508–512 | 当前连接执行 SET foreign_keys=ON，但没有读取实际返回值；authorizer 仅阻止装载后修改 PRAGMA。新 credit guard 在任何效果前必须读取并确认 FK 实际启用，提交前再确认，覆盖自定义连接工厂/错误配置。必须拒绝 `foreign_keys`、`defer_foreign_keys` 等修改以及 manual COMMIT，不能依赖 DDL 文字或“在事务中 OFF 通常无效”。无实际 SQL 测试前不宣称这些绕过已封闭。 |
| NC-08 | design:142–146；durable_batches.py:246–279；sharding.py:855–867 | 现选择器排除非 SUBMIT/CANCEL/REPAY head；其他账户持续提供 >=3 个成员时可一直形成 batch。即使返回 None，普通 process_one 的风险降低优先也不自动保证 BORROW 获得机会。必须冻结一个可测试的 normal opportunity 规则，明确包含 BORROW、backoff/FIFO、控制流假设和冷重启；或首切片明确拒绝 batch+credit 的运行组合。识别四类 marker inventory 不等于组合调度已经支持。 |
| NC-09 | design:52–55、89–99；writer_fence.py:547–563、574–590 | control exact DDL whitelist 不等于 financial role 不能临时删除 credit 操作保护。当前 financial 分支对非 `writer_fence_` 名称的 DDL 没有立即拒绝；交易末端只看到最终 schema。必须在 authorizer 当场拒绝 DROP/ALTER 受保护 table/index/trigger，捕获异常也使 guard.denied 永久中止本事务，并保持 immutable/no-replace 触发器。否则不能仅凭“先删 guard、裸写、再逐字恢复后最终 inventory 相等”声称原生 effect gate 一直有效。这里是静态可达权限路径与未来契约风险，未执行绕过。 |

这些是确定的契约欠缺/兼容性决策，不是声称一个不存在的 DDL 已被绕过。方案文字
可以选择不同实现，但必须在 runtime GO 前使义务、作用域及调度时序无歧义。

NC-09 的边界须准确区分：现有 `writer_fence_data_*` 与 reserved control 名称已经由
writer_fence.py:560–561 的 prefix 检查拒绝金融角色 DROP；本审查没有说这些现有 native
fence 触发器可被直接删除。新 credit 操作触发器、复合 FK 父 UNIQUE 索引及相关 immutable
保护若使用其他名称，就不能自动继承该权限。应冻结编译入的受保护对象/对象类型清单和
正确的 SQLite authorizer 参数语义；ALTER TABLE 的表名不是所有 action 的同一个参数。
REPLACE 也不是独立 authorizer action，需保留并保护真实 no-replace INSERT 触发器。
合法初始化由单独 exact control 路径完成；不能为方便重启构造 schema 而扩大 runtime DDL。

## 原生闭环所需的具体检查

intent、source、allocation、credit receipt 和 decision 的复合 UNIQUE 与 FK 必须是
真实父键，并包含被绑定的 account/asset/kind/原 CID/canonical amount/hash。只引用一个
存在的 ID 不能证明它属于本 authority、账户或币种；UDF/原生检查还须绑定当前 descriptor。
borrow 的 `BORROW_KIND`、credit 的 `borrowed` 和 audit 的 `CREDIT_BORROWED` 必须有显式
固定映射，不能靠相似字符串推断。所有货币比较保持整数文本/显式精度，不能用 SQLite
REAL、32/64 位 CAST 或金额字符串字典序推断本金增加。

在 credit-record INSERT 作为 native closing point 的一种可选流程中：scope 验证当前
durable head → 写 intent → 原 full risk/ledger/debt → 写 credit decision → native 校验
完整 DB 证据后写 credit record → 同连接写 SUCCEEDED terminal → deferred FK 与 final
fence COMMIT。任何后置异常被吞掉时，缺少 receipt/decision/terminal 都必须使实际 COMMIT
失败。业务 SAVEPOINT 回滚则移除 intent、effect、decision，之后可写 REJECTED terminal。
这只是推荐时序，不是已存在的实现或实测保证。

counterparty 集合包括普通 customer leg；仅对 credit-owned account 设置 INSERT guard
不足以拒绝一个借款 journal 中追加的 customer-only/平衡 dummy leg。重复 ordinal、重复
同金额 leg、错资产、缺本金应收、sealed 后追加和恶意平衡额外腿都要成为实际反例。
repayment 的 pool 正 posting 与 interest-cash 正 posting 是合法资金归属，不应误认成
新 pool funding；旧利息减少也不应被“zero interest”规则错误拒绝。zero-rate policy
应禁止新应计增加，仍允许清偿 opening interest。

## cap、重放与 HMAC 边界

设计 28–36 已选择 additive reserved marker；当前 `_load` 的 exact inventory 确实不认识
credit marker。新实现必须用显式 base/batch/credit/both 集合，不得从“任意已知 prefix”
推断权限。事件声明启用而 marker、descriptor 或任一必要 schema 缺失应拒绝；global
PREPARED/READY 也须核对每片完全相同计划。完整旧快照回退的检测仍依赖被保留的全局
authority/水位；不能把这套本地门禁宣称外部反回滚证明。

应实际运行 **batch-aware 458** 与至少一个更早归档二进制：无 credit cap 的同配置
positive control 可正常成为 writer，有 credit cap 则不可成为 writer/写入；仅用已经
不支持当前 base format 的更老二进制失败不能独立证明 credit gate。四种 cap 组合、缺
UDF、错角色、marker 消失、捕获 SQL 异常和 COMMIT 未知分别测，不用同一错误替代。

历史 credit receipt 的原 CID replay 不新建 intent/decision/source，也不更改 opening
audit gap。新终态和 source 的 SQL 引用须以确切原 CID 为单位；fresh auth nonce 不得
改变业务 hash。HMAC `borrower` route 不得沿现 `gateway._permit` 的 admin 自动 bypass；
现方法在 gateway.py:333–335 明确允许 admin。borrower 是否可用同一 key 还款、或需另持
funding 权限，应明确写入接口合同；不由通用 reader/trader/admin 继承借款资格。

“source first receipt”是受控 gateway 的认证声明，不是 worker 独立复核 HMAC 密钥，
设计 168–171 已正确限定。还需冻结允许的 source kinds，synthetic_local 只能用于显式
合成路径；不能把缺认证元数据静默降级后算作 HMAC 借款。认证库成功、金融 enqueue
未提交时的 orphan auth receipt 是可解释中间状态，不得捏造金融 ACK。

## 最小后续验收输入

在新设计修订中先交 exact DDL、native/UDF 输入输出/生命周期表、BORROW/REPAY/public
兼容矩阵和 single-turn 调度规则。随后独立小规模实际 SQLite 反例至少覆盖：NULL 复合
FK、漏建 intent、漏 decision/terminal、错 parent identity、FK OFF、缺 UDF、错 role、
statement/SAVEPOINT 回滚后的 stale scope、同事务借还、重复 posting、缺 customer leg、
反向无 intent effect、late risk rejection、真实 lost-COMMIT query 原 CID、stale-market
还款及 batch 连续到达。全部原红保留。手算 fixture 数值由独立金融组复核，本 native
审查没有运行生产函数或宣布十个 JSON 用例通过。

本轮状态仍为 **DESIGN NO-GO / production_approved=false**。
