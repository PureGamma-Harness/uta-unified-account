# Managed 新借款：前置事务工程与启用门槛

基线 `07d0a72`，工作分支 `feat/managed-credit-admission`。本阶段只整理既有
`CreditService.borrow` 的事务接口及合成验证，不接入 v2 enqueue、worker dispatcher
或 HTTP，不增加 managed 产品能力。新借款在 managed ingress 仍是
`501 unsupported_durable_operation`。金融、模型和真实资金上线审批均未完成。

## 已核实的当前边界

- `CreditService.borrow` 使用一个 SQLite writer transaction，借款现金、本金负债、
  系统本金应收、池现金、账户版本和 `credit_commands`/事件一同提交。本金与利息分别
  保存；同币现金和借款不先净额化。币种精度和限额使用整数最小单位。
- 显式 account/asset limit、当前数据库 asset limit、真实已入账的 pool cash 缺一
  不可借。`configure_credit_asset_limit(shard,...)` 明确按分片设置；
  `SUM(uta_liabilities)` 也只读取当前 shard。因此它**不是全局原子借款额度**。
- `router_pool_sources` 先将唯一外部资金业务引用绑定到一个确切 shard/command，再
  向该片记账。重试不可把结果未知的证明重新分配。它证明资金引用分配边界，不是全局
  授信预算、外部托管到账确认或外部贷款人的可用额度证明。
- 配置了目录和 `UTA-CROSS-LOAN-v1` 时，借款前按同一事务的 gross 资产、债务、冻结、
  仓位和挂单重新算保守 LTV 报价；不把新借款所得循环计入本次可借报价。借款后完整
  IM/MM 再检查，末端再次验证原服务端行情。`available_margin=0` 的 IM 边界保留，
  风险权益与 MM 相等不授予新增贷款。
- 原 borrow 的 `risk_evidence` 只有报价/部分版本和风险字段；schema3 capability
  明确将 new credit decisions 列入未捕获项。它不等于完整、可重放的行情内容、政策
  内容和实际 code/runtime artifact 证据。不能用现有字段冒称 managed audit 已齐备。
- 普通客户端不能从 managed v2 调用新借款；可信本地金融 owner 接口的能力边界须与
  后续启用格式共同审阅。新增内部 joined 函数不能成为跳过队列或 audit 的客户入口。

## A：本阶段提交范围

`borrow` 保留开 storage 前的 `_prepare` 输入验证和原 replay 顺序，委托一个
`_borrow(connection,...)`。后者只加入正确 authority 上的现存、可 join 的金融事务，
不开始第二个事务，不自行 COMMIT，不接收调用者余额或行情。现有金融公式、账本科目、
limit、pool 所有权、freshness、幂等键及错误契约保留。

验证使用真实 SQLite 与人工预期值：借款后终态回执失败须回滚所有现金/负债/分录及
幂等记录；同连接后续借款/下单须读取先前 staged 的债务、pool 与预占；失败不能留下
可重放的成功；原 ID 重开重试只有一笔实际影响。加入无事务、其他 DB 或只读 connection
的拒绝用例。原信用、gross、Cross 和共享监督测试需重新执行，保留原始结果。

这一步提供可组合的原子接口，不证明 online lending 资格或新的风险政策已经启用。

## B：后续设计，当前不实现

建议第一版 managed 新借款只接受预先离线分配的资产预算，不实现动态跨片借额度。
预算记录绑定全局 budget ID/version、asset、原始最小单位额度、authority/layout、
精确 shard 分配和资金证明引用；必须满足各片额度之和不超过批准的全局预算。
每片本地限额以 principal+interest 口径强制；利息可以超过额度继续确认，新增借款拒绝，
不能为满足额度丢弃已发生利息。多资产 LTV 报价共享抵押池，不可相加授权。

人工例：批准 BTC 总额度 10，分配 shard0=6、shard1=4，两片当前 gross debt 分别为
5 和 3。新借款本地最多分别 1 和 1，还须满足 account/LTV/pool 限制。shard0 拒绝借 2，
即使 shard1 尚有 1 空余；不通过跨 DB 读取后乐观扣减来声称原子执行。某片失联、结果
未知或待计息时，该片额度不回收。预算币种原始数量与 USD 风险限制分别保留。

预算变更必须 quiesce 全部相关写者、解析所有在途 CID、逐片确认债务与新 generation，
先持久不可逆全局分配记录，再完成各片能力升级，保持 HALTED，完整核对后显式激活。
部分失败只前滚原预算 ID，不把旧 allocation 删除或挪给另一片。旧 writer 必须由持久
格式门禁失效，不能仅依赖新代码内的布尔开关。旧备份的预算/nonce/债务水位也不可静默
回退。该协议尚未实现，不能用文档代替故障验证。

启用前还需：

1. 显式 immutable managed-credit capability 和兼容/迁移门禁，缺失则拒绝新增信用。
2. 逐笔 BORROW decision 的 content-addressed market、policy、actual artifact、账户
   pre/post、原 CID、资金/预算 allocation 引用；与 postings、debt 和终态同 COMMIT。
3. 独立金融权限和租户/账户 scope、签名与重放保护；客户端只请求金额，不提交资金证明、
   余额或价格。HTTP `202 PENDING` 仍仅表示耐久意图，不表示授信。
4. 409 业务拒绝、503 技术失败/UNKNOWN、幂等冲突、预算不齐和过期行情的独立契约；未知
   查询原 CID，不生成新的贷款 ID。新 borrow 属普通风险容量，不能占用还款保留容量。
5. 池/债务/本金应收逐币对账、跨片预算守恒、并发额度/挂单竞争、失去 COMMIT 回执、磁盘
   满、旧主/旧二进制、重启及过期行情测试；由另一组独立计算、反例和实际故障验收。

规则来源为本系统的 ACCT-002/004、RISK-003、DURABLE-002 与 AUDIT-001；公开交易所资料
不验证其内部额度分配或托管边界。外部真实资金证明、贷款利率、周期性利息调度、抵押品
兑换清算及贷款违约处置仍是明确证据/实现缺口。
