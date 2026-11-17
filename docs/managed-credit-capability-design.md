# Synthetic managed credit capability：待审设计

状态：**DESIGN / NOT IMPLEMENTED / NO-GO**。基线 `45818c0`，独立分支
`feat/managed-credit-capability`。本提交仅交付设计和人工标准案例；没有 runtime、DDL、
API、测试放行、服务启动或旧作业变化。A2 的 managed 新借款 501 继续有效。实现须先由
集成负责人、独立金融组和 SQL 契约组审阅本设计。

## 1. 第一切片与拒绝范围

仅在新的私有合成 managed layout 上显式初始化 `synthetic_managed_credit_v1`，默认不写
能力表、不改变现有 schema、不开放借款。要求完整目录及 `UTA-CROSS-LOAN-v1`、required
schema3 base audit、明确的同币资金池、每账户/每片额度及离线全局分配。币种仍是本系统
合成 USD/BTC；不声称真实 USD、USDT/USDC 或外部贷款授信。新借款是独立请求，不做
auto-borrow、信用委托或提现。借入资产仍按既有 gross 规则记账，不能先和负债净额化。

新政策 `SYNTHETIC-CREDIT-ZERO-v1`：新贷款利率为零，无周期计息、复利、费用或隐含时钟。
封存时已有本金/利息可作为已核验源义务保留并计入额度，记录 opening legacy obligations，
不补造其历史 audit。启用后拒绝新的 interest accrual、pool capital funding、债务调整和
经典账户写入；同币还款保留利息先于本金及断价/halt 时可执行。新增资金或分配变更需要
后续另审离线维护协议，本切片不支持。未知产品、模式、资产或预算一律拒绝。

只支持 fresh-layout 初始化。既有 managed layout 的在线/离线 promotion 均在本切片外；
不得通过调低 format、删 marker 或重跑初始化来伪装 fresh。全局控制和各片即使部分安装
成功也保持 HALTED/incomplete，按同一个 PREPARED 计划前滚，不能恢复旧软件写入。

## 2. 持久能力及预算

新增精确且不可变的 reserved marker `writer_fence_credit_capability(format=1, descriptor)`，
以及不可逆 `credit_enabled` fence event。descriptor 是以下规范配置的内容 hash：layout、
authority/shard、零利率政策、预算及 allocation IDs、required credit-audit format 和 source
funding claim 摘要。`_load` 明确允许 base、batch、credit、batch+credit 四种 inventory。
已启用事件存在而 marker/descriptor/schema 消失或不符时拒绝，禁止自动修复。

batch-aware `45818c0` 及更早代码的 exact reserved inventory 不认识 credit marker，理论上
会在成为 writer 前拒绝；这仍需实际旧源码进程测试。普通旧 SQL 连接还必须因缺少原生
writer/credit UDF 无法写资金，不能仅验证新代码中的 `if capability`。

离线全局 `router_credit_capability` 记录 PREPARED/READY 与规范预算全文/摘要。每个预算的
原始币种数量保存为整数最小单位字符串，asset/global_budget_id/version 固定，唯一分配到
确定 layout+shard+authority。所有片额度之和必须 <= 全局批准额；各片的 opening gross
principal+interest 必须 <= 分配额。已有 account/asset limits 仍分别生效，不混成一个量。

各片保存不可变 `credit_policy_history` 与 `credit_allocations`，同时保存完整全局 allocation
证书，不仅保存自己的数字。新 owner 启动及每次新借款重新核对 identity、完整证书、总和、
当前片额度、pool source claims 和本地已用 gross debt。金额不经 float/SQLite REAL/溢出
CAST。尚无预算、漏片或内容不一致不得借款；budget 文件不是外部真实资金证明。

没有跨 DB 借款原子扣额。静态分配把权威扣额限制在每片自己的金融事务。失联/UNKNOWN/
未结算时不回收或挪用该片额度；客户不能要求系统乐观读另一片空余后在本片使用。封存后
不得动态调额度。新增利息在此版本禁止，因此不会隐含把未来计息能力算成已实现。

逐片安装在一个无 live lease 的控制事务中完成：精确官方 schema/index/trigger、预算及
opening 内容、所有 native guards、marker/event 同提交。调用全局前先核验所有片；控制
whitelist 只允许编译入的确切对象和 typed bound values，不扩成 SQL prefix 许可。任何
资金、队列或历史核验失败在第一个不可逆步骤前拒绝。后续单片失败保持全局关闭。

## 3. 原生操作义务与权限

不能仅将 A2 的 `_load != None` 改成 Python capability flag。新增 `uta_credit_operation_v1`
原生 UDF，绑定真实 `_TransactionGuard` 的确切连接、financial role、同 token/PID/租约、
原 inbox CID/account/kind/canonical hash、操作、资产、整数金额和预期前后债务/分录。
只接受 dispatcher 对当前 due FIFO head 建立的私有执行作用域。public owner borrow 不能
自行创建这个作用域；即使有 credit cap 也不能绕过持久 inbox。缺作用域、错 CID/账户/
金额、别的连接/角色或过期 token 均令原生触发器拒绝。

在写任何贷款效果前，插入不可变 `credit_operation_intents`。BORROW 至少包含：原 CID、
account、scope、kind、asset、canonical amount text+整数 units、原 payload hash、allocation
ID、credit policy ID、journal event ID、`CREDIT_BORROWED` decision ID，以及常量 terminal
state `SUCCEEDED`。REPAY 使用相同义务框架，但 market_dependency=NONE、decision ID=null，
不能制造报价或塞入 base audit 的非空 market 字段。

拟采用以下原生 deferred FK，具体 DDL 先过 SQL 契约审查：

| 义务引用 | 精确 native 约束 |
| --- | --- |
| 原接纳回执 | `(CID,account,kind,'SUCCEEDED')` → inbox 对应复合 UNIQUE，DEFERRABLE INITIALLY DEFERRED |
| 信用结果 | `(scope,CID,credit_kind,asset,canonical_amount,journal_id)` → credit_commands 的确切复合 UNIQUE，同为 deferred |
| 借款审计 | `(decision_id,'CREDIT_BORROWED',account,CID)` → risk decisions 的确切复合 UNIQUE；BORROW 必需，REPAY 禁止伪造 |
| 分录及分配 | journal event、immutable allocation、policy 内容均有 FK；allocation 还须属于本 authority/asset |
| 认证来源 | intent 引用不可变 first-source receipt，绑定同 CID/account/payload hash，不能换掉首个来源 |

原 UNIQUE 主键继续保留，新 UNIQUE 索引只提供结构引用，不以 nonunique FK 或 JSON 子串
比较替代。原子义务必须在效果前出现；若 caller 吞掉 late risk/审计/回执异常，缺少任何
一侧仍不能 COMMIT。真实逐命令 SAVEPOINT rollback 必须同时移除义务、所有资金效果与
审计；REJECTED terminal 可随后在同外层事务提交。helper 不伪称自行拥有 caller rollback。
每个实际金融连接必须确认 `foreign_keys=ON`，原 authorizer 不允许关闭或替换 guard；
须实测 foreign-key 配置绕过、手动 COMMIT 和捕获异常后的事务状态，不能只检查 DDL 存在。

credit-enabled 库的 exact native triggers 进一步覆盖：

- 所有本金/利息 projection I/U/D 必须符合当前 sanctioned BORROW/REPAY 的精确前后值；
  BORROW 不改已有利息，零利率政策禁止正利息变化，DELETE 不用于免除债务。
- credit-owned ledger accounts（pool/capital/principal-interest receivable/liability/cash）
  的 posting 和 active credit journal 中所有 posting 必须属于作用域中精确预期集合，包含
  customer 对侧；缺少/额外/重复/错金额必须拒绝。普通非 credit 交易不借此获得新权限。
- 新 borrowed/repaid credit command、intent、关联终态必须互相匹配。pool_funded 和
  interest_accrued 新写在 cap 后禁止；历史读取、原 ID 重放不受影响。
- 外层 before_commit 独立复核完整 native schema、所有本次义务、typed audit/terminal
  内容、完整 postings 和 debt projection、预算及 pool 无负数，然后保留原 final fence。

SQL 能证明角色/结构/引用/提交约束，完整 LTV/组合风险数值仍由版本化计算和独立验证
负责。此方案不防恶意 OS owner 替换 Python、UDF、数据库文件或凭空捏造真实托管证明。
不能将代码中的私有作用域误称为单独安全边界；它由持久触发器和提交义务共同约束。

## 4. 完整借款审计与实际代码复算

独立 native 审查发现：现 `_loaded_engine()` 不含 credit/writer_fence；通用 replay 遇到
未知 kind 只重算 before/after risk，不能证明借款的 pool、principal、limits 或 quote。
因此不会仅调用 `record(kind='CREDIT_BORROWED')` 就宣称完整审计。

新增明确的 `credit-audit-v1` 扩展，复用 base 的不可变 market/code/policy archives 及 risk
decision 表，但使用专门 credit artifact manifest 和严格 operation replay。base audit
format1 的原声明、历史 gaps、原 ORDER/FILL 字节不改写；新 credit capability 单独声明
自己的覆盖和 format。既有线性 replay 仍只接受匹配的原 artifact/runtime。

每个新 BORROW decision 与金融效果同 COMMIT，至少绑定：

- 真实当前 `market_snapshot_id` 及完整原始 payload，原 observed_at、选价及末端检查时刻；
- catalog/risk/base policy 与 credit policy、global budget/allocation 规范全文内容 ID；
- 实际 source 文件和 loaded 函数指纹，含 credit、credit-cap/policy/audit、writer_fence、
  durable executor 和原风险依赖，Python/SQLite runtime。源/加载逻辑不匹配时拒绝复算；
- 账户 pre/post version、gross balances、本金、利息、冻结、仓位、挂单及 risk 前后分解；
- pool 前后、当前片 gross debt、account/asset/allocation 额度与使用量、保守 quote、数量
  step、零利率/零费率政策、原 CID/payload hash、完整 journal 与 actor source 引用。

专门 replay 不对 live DB 写入；从上述档案逐项验证 canonical IDs/hash/types、pool 与
本金/应收/现金的整数变动、额度/quote/freshness证据、risk 前后以及版本变化。历史数值
复算不拿今天时钟判断当时报价。当前新行情不会覆盖旧 SID；缺档、错 source/loaded code/
runtime 或 operation 字段有异议时显式报错，不能只输出 before/after 风险 matches=true。
独立金融参考实现不能复用生产 credit/风险核心，需单独验证手算 fixture。

历史 pre-cap credit replay 不创造新贷款、intent 或回填不存在的 decision；返回原结果并
显式保留 legacy audit gap，不把它计为一笔新有审计贷款。原 CID 异内容仍为409。

## 5. FIFO、batch 与未知结果

新增 BORROW_KIND 使用现 normal capacity，不占 cancel/repay reserved slots；按账户
FIFO，不能穿过本账户 backoff head。与订单/撤单/还款在同一实际金融连接读最新 staged
风险、债务、pool 与额度，仍用原 savepoint。PENDING ACK 不是授信；只在所有原子义务
提交后返回业务 SUCCEEDED。后置报价过期/存储/审计失败不能保留部分贷款。

第一实现选择 **BORROW 单条执行**，不把它放进现 batch manifest format1 成员。base+
batch+credit 同时存在时，已有 batch 成员/恢复规则保留；若最老 eligible normal head 是
BORROW，该轮回原 single path。其他 batch 仍须守 account FIFO，并保留已有 oldest-head
机会，不能因为没有 BORROW batch 成员而饿死它。否则保守拒绝该组合，不能静默跳过
BORROW、篡改 batch format1 或用未测调度声称兼容。多 borrower 批处理留待单独扩展。

超时或 COMMIT 回执丢失查询原 CID。已 terminal 返回原结果；只有确认 PENDING 才可在新
金融事务重调度。结果读失败是 UNKNOWN，阻断依赖动作；不得换 loan/CID 再贷。原 CID
receipt、credit row、intent、decision、ledger 任一缺失或矛盾都失败关闭。重启/新 owner
从持久原义务和回执恢复，不能根据内存“已借”重做。batch unknown 仍 query-all，不能将
credit 技术异常计到邻居 attempts。

## 6. HMAC 权限及来源

新增显式 account-scoped `borrower` role，只授予借款及自己的回执/必要只读查询。普通
reader/trader/funding/risk/admin 不因旧角色自动获得借款权限；全局 admin 也不能借通用
`_permit` bypass 冒用客户信用。还款继续由已有资金权限执行，风险配置和资金证明仍是
离线受控动作。新 route 必须先通过真实 TLS/HMAC、audience/tenant/account/时钟/nonce
核验，再检查独立角色，失败不得 enqueue。

业务幂等键只由原 account/CID/asset/amount 决定。另存 immutable first-source receipt，
与第一次 inbox INSERT 同 producer COMMIT，绑定业务 payload hash、实际认证 key ID、
role/account/tenant、请求与 auth receipt 摘要，不存密钥/签名 secret。重试的新 nonce 不
改变业务 hash 或覆盖 first-source；认证库继续记录新的认证尝试。SQL producer role 仅
可插入这类固定 source 元数据，不能写 audit/资金/terminal。

worker 验证 immutable source 与其 capability/账户一致；信任边界仍是已有受控 authenticated
gateway，不能冒称跨认证库/金融库原子提交或 worker 独立验证了 HMAC 密钥。冷核对能从
业务 ID 关联认证 receipt；缺少实际 auth 来源不得标为客户 HMAC 借款。低层合成测试来源
需明确 `synthetic_local`，不可伪装实际签名接入通过。

## 7. 手算、实现顺序及验收

标准数值见 [人工 fixture](../tests/fixtures/managed_credit_v1_golden.json)。这是手算预期，
尚无生产实现或通过测试；USD100、BTC100、BTC haircut .8、LTV .5、借款IM/MM .2/.1、
step .01、fee/rate0。新借BTC .4 后 equity92、IM8、MM4、available84、pool .6，本金/应收
各 .4；每片额度 .5 时下一笔上限还须被剩余额度 .1 限制。已有8份线性挂单占用80时，新
quote向下取整 .03，.04 即使实际借入现金留在账户也按既有保守报价拒绝。

拟按以下独立 OWN commits 递交，每步可否决后继：

1. 独立审计划/原生 DDL/FK/手算；先写实际旧 binary、缺证据提交、原 repay/preseal 控制
   的红测试。尚无 runtime GO。
2. native capability、精确 schema/intent/预算及本地只读诊断，默认全部关闭；实际四组合
   old binary 与缺 UDF/错角色/吞异常/commit/rollback 反例通过才进入借款接线。
3. credit operation 与专用 artifact/replay，独立金融逐字段验证；SOURCE/loaded monkey
   patch、档案损坏、gross/limit/pool/舍入/临界值/后置失败均保留原证据。
4. 单条 durable BORROW FIFO/终态/未知恢复及显式 HMAC role/source，验证 batch cap 组合
   的原功能、调度、公平和重启，不以单条通过冒称批处理借贷通过。
5. 固定源码三运行时完整测试、真实 installed package、CI、部署与回滚演练。独立审查
   完成前不跑压力、不启动长服务，也不改变目前长稳 source、参数或预算。

部署到全新合成目录，先 HALTED/preflight/完整封存，再固定 artifact 启动、核验全部预算/
source/marker、发布真实新鲜完整行情并显式激活。失败保留 PREPARED/HALTED 原 CID 与
nonce/资金水位，只前滚；不能删 obligation、降级 marker、重新分配未知贷款预算或用旧
备份抹掉确认成交。停用借款只停入口；cap/预算/历史不可移除，还款和原结果查询按原安全
条件保留。无复制 RPO/RTO、容量、真实贷款人、真实签字或生产批准。
