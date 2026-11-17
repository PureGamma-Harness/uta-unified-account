# Managed credit：设计审阅补充 v2

本文件追加解释和收窄 `7aa48202ddc4663a1e815609716c1a6b7110289f`，原设计及10例 JSON
字节保留。状态仍为 DESIGN / NO-GO，不是原生约束已实现或金融负责人签字。下列修改
由设计作者根据独立 native 审查及数值审阅提出，需独立金融和 SQL 契约组确认。

## 金融与单位补充

原数值按以下显式输入才成立：BTC-PERP 为合成 USD 线性永续，contract multiplier=1、
quantity step=.01、price tick=.01、min notional=1 USD，标记价及限价均为100 USD/BTC，
持仓初始为空，fee=0。案例004的8份挂单是该乘数下8 BTC等价数量，不是8 USD；
`8×1×100×.1=80 USD` 是未成交订单 IM 占用。该字段不是已支出的现金或 MM。

每个 `starting_after` 克隆指定案例的不可变已提交状态；案例彼此独立，不按文件次序
叠加。005 的两个账户分别有 USD100、无初始债务；它们共用一片 pool=BTC1、额度=.5。
006 先给定两片真实债务使用量，不代表观察者已能读取失联分片。008 是待验证的 native
性质，009 的静态数字仅针对已经真实 COMMIT 的分支；它们都不是数值计算通过即证明。

预算 D_s 明确只为该片该资产 `principal+interest` 原币数量，ΣD_s<=ΣA_s<=B 的归纳
需要：opening 符合分配、分配不可变、借款只在本片原子增加且不超 A_s、还款确认后才
减少、没有新计息/债务调整/未受控增量。预算不覆盖 cash deficits、合约亏损、USD 市值
变化、外部负债或所有经济债务。它们仍进入完整风险权益、LTV 与 USD 总债务规则。

同币还款释放预算的数量包含本金和利息，但 pool 只回收本金部分。新增必测 opening
利息例：USD100、BTC cash=.5、principal=.4、interest=.05、pool=.6，还款=.1；先偿利息
.05，再偿本金.05。还后 cash=.4、principal=.35、interest=0、pool=.65、interest cash
增加.05；额度使用量 .45→.35，而 pool 仅增加.05。该 opening 利息不是零利率政策新生
利息；不得丢弃、回填或将其现金错误注入 pool。完整独立计算另附原始输出。

## 拒绝与未知结果契约（供实现验收）

原 JSON 的 reason 是说明词，尚不是已实现 API code。第一实现须保持以下分类，不把技术
失败当业务拒绝；reason 可作为 credit 扩展的结构化字段，但不得依赖异常文本：

| 情况 | code / status | 终态及效果 |
| --- | --- | --- |
| 没有 credit cap | unsupported_credit_operation / 501 | 入口拒绝，不 enqueue；A2 保留 |
| cap 元数据/证书/预算缺失或损坏 | credit_capability_corrupt 或 credit_budget_unavailable / 503 | 失败关闭，不能当额度为零的普通业务拒绝 |
| opening/总分配超额 | invalid_credit_budget / 409，离线初始化错误 | 第一个不可逆 marker 前拒绝 |
| account/asset/allocation 超额 | credit_limit / 409，分别标明 reason | REJECTED，无资金/债务/成功 audit 副作用 |
| 保守 quote 超额 | credit_limit / 409，borrow_quote_exceeded | REJECTED；不能用实际留存借入现金绕过 quote |
| pool 不足 | credit_pool_empty / 409 | REJECTED，不借用其他片资金 |
| 数量不符精度/step | invalid_input / 400，quantity_step | 不舍入客户请求；无金融效果 |
| halt / account freeze | trading_halted 或 account_frozen / 409 | REJECTED，无新增信用 |
| 过期/不完整可信行情 | market_unavailable 或 market_incomplete / 503 | 明确的行情安全拒绝、无金融效果，与内部 storage retry 分列 |
| 无法确认 COMMIT/回执 | command_result_unknown / 503 | 状态 UNKNOWN；查询原 CID，不凭异常判定 rollback，不新建贷款ID |
| native/FK/audit/存储失败 | typed technical failure / 503 | 原 CID 先查询；不得伪造业务 REJECTED 或扣所有邻居 attempts |
| role/account/tenant 不符 | forbidden / 403 或原认证错误 | enqueue 前拒绝；nonce 元数据可能已消费，不代表金融效果 |
| credit cap + batch_size>0 | unsupported_credit_batch_combination / 409 | 启动前显式拒绝，不能静默关批处理 |

码名属于本次待实现契约，不能声称当前 API 已返回它们。既有 error code/status 不为方便
测试随意改名；新 credit 字段须有版本和兼容测试。

## 最小 runtime 边界收窄

第一版识别 base/batch/credit/batch+credit 四种持久 inventory，但 credit cap 有效时要求
worker batch_size=0。base/batch、无 credit 的原行为保留；同时存在两个 marker 且 batch=0
可使用 single dispatcher。正数 batch+credit 的执行和 BORROW 调度公平留待后续单独验收。
这替代原设计对最老 BORROW head 的条件性调度建议，避免把未证明的 fallback 当兼容。

credit cap 后，新的 direct public owner borrow **及 repay** 都不创建金融作用；要求真实
持久 inbox 操作作用域。原 receipt replay 保留。当前客户 v2 queued repay 仍须保留其原有
金额、利息优先、halt/stale 可还款及原 CID 行为；只是 cap 库中的实际写入增加原生义务。
cap 前的 bootstrap 与无 credit cap 的受测还款不改变。不能同时声称所有 owner repay 调用
语义完全未变。还款的 market_dependency=NONE，不创造 fake market/borrow decision。

## 原生提交契约细化

BORROW 的所有 receipt/audit/ledger/allocation/source FK 均 `DEFERRABLE INITIALLY DEFERRED`。
所有必需 ID/hash/account/asset/units 和预期 terminal/credit kind 是 NOT NULL；所谓常量
`SUCCEEDED`/`CREDIT_BORROWED` 必须存为带 CHECK 的列，不可在 FOREIGN KEY 列表里写
SQL 字面量。条件 CHECK 必须排除 SQL NULL 三值逻辑绕过。REPAY 的 decision 列只能是
明确 NULL，并仍须 journal/credit receipt/inbox SUCCEEDED/source/allocation 引用。

不能只从 intent 正向检查 FK。每个 effect 的持久触发器先用 SQL EXISTS 确认同连接实际
staged intent 完整匹配，再把其 immutable digest 及实际 OLD/NEW 字段传给纯验证 UDF。
intent INSERT 是独立 candidate-create 模式，不能要求自身已存在；它不能提前放行资金
效果。UDF 不递归查询数据库，不用 Python observed-set/counter 证明已经完成的写入。
SQLite statement/savepoint rollback 不回滚这些 Python 内存副作用。

before_commit 从实际 staged DB 双向重建 intent↔credit command↔journal/postings↔gross
debt↔terminal↔decision/source/allocation。opening legacy prefix 明确记录且不可改写。
所有 cap 后 credit-owned postings 必须有恰好一个原 intent/credit journal；所有 BORROW
intent 必须有完整且唯一的四条原始贷款 postings 和匹配本金变化；REPAY 按 interest-first
精确集合核验。不能仅遍历“内存里本次登记过的 intent”或只验证存在的那几个 intent。
数量/方向/金额/asset/account/journal 内容也须匹配，单独 FK 只证明身份，不证明资金变化。

financial actor 还须即时拒绝 DROP/ALTER/REPLACE 或移除/替换 credit/audit/FK/index/guard
保护对象。不能允许“临时移除→裸写→恢复原 SQL”后仅因最终 schema 相等而提交。control
安装仍限明确官方对象及无 live writer 的一次原子步骤；捕获 schema 权限拒绝不能清除
guard 的 fatal 状态。foreign_keys 必须开启且金融 actor 无关闭权限。

## 缺失场景及下一步门槛

- 两片同时借各自剩余额度，真实 Σ本金+利息仍不超总分配；误分配总和>global 必须在
  marker 前拒绝。允许未分配 global 余额，但不能自动给任一片使用。
- 一片 reply UNKNOWN，真实可能已 COMMIT；原 allocation 全额保留，既不能释放已用额
  也不能转给另一片。是否全局暂停仍服从原 control/funding 完整性政策，本设计不承诺
  其他片可用性。失联不能成为调宽全局 barrier 的理由。
- 同片还款 PENDING/UNKNOWN 时不能预支其未来 pool 或预算回收；只有同一金融事务已
  staged 且同 COMMIT 受约束的变化或已确认的独立 COMMIT 才能用于后继风险计算。
- late exception 被吞、ROLLBACK TO、RELEASE、整个外层 rollback、COMMIT 已完成而回复
  丢失必须分别验证；不能将 savepoint RELEASE 当 durability ACK。
- 重试使用新 auth nonce/key、同一业务 payload，first-source 保持原样；新的认证记录不
  改贷款幂等身份。既有 pre-cap replay不生成新借款/新decision，也不能计入新贷款吞吐。

下一步只允许独立金融及 SQL 契约审阅、小规模纯整数/Fraction参考；审阅后可在自有临时
DB 验证候选 native obligation 的红/绿组件反例和实际旧码四组合。组件 SQL 证明不能冒称
完整 UTA runtime 已实现。完整 borrow/权限/路由接线仍须另行授权及独立验收。
