# 本地 USD 线性永续资金费原型

本交付以 `9b61e5f35dd2196ef2fdddfa03559eca3f1322ec` 为基线，只新增可显式调用的
`perpetual_funding.py` 精确计划器及 `funding_local.py` 本地事务适配器。现有服务、
REST、WebSocket、worker、CLI、撮合和模式门禁均不自动接入。当前为 **CODE / NOT_RUN**；
金融规则负责人、独立验证和真实上线审批均待签字，不具备生产启用资格。

## 已核实范围与证据缺口

原产品规格把 `funding_interval_seconds` 明确标为元数据。原服务没有永续资金费 API；
已有 `funding` 提交和恢复用例针对借贷池注资，不能拿来证明永续资金费。

第一手资料在 `evidence/reviews/perpetual-funding-local/source-and-rule-matrix.json`
归档定位信息及有限事实摘要，不冒称完整网页或授权客户流水归档：

- [Bybit Funding Fee Calculation](https://www.bybit.com/en/help-center/article/Funding-fee-calculation)
  当前页面标示更新于 2026-05-12。正费率由多方向空方支付，负费率相反；线性金额基于
  持仓量、标记价与资金费率。该平台明确在结算前后若干秒的持仓归属可能不确定。
- [Bybit v5 funding history](https://bybit-exchange.github.io/docs/v5/market/history-fund-rate)
  提供产品、费率及毫秒时点；具体间隔需另查产品接口，不能把示例八小时硬编码为统一规则。
- [Binance funding history](https://developers.binance.com/docs/derivatives/usds-margined-futures/market-data/rest-api/Get-Funding-Rate-History)
  当前重定向至官方市场数据目录，字段含费率、时点与该次费用对应的 mark。

这些资料不证明本系统的舍入、资本归属、精确切点、授权或恢复行为。下列政策为本系统
明确选择，不声称复刻 Bybit、Binance 或其 UTA/PM。

## 本系统有限规则

仅单一本地 authority、已配置 Cross、USD 报告和结算、乘数为 1 的线性永续。
所有本地持仓的带符号数量总和必须为零；不完整对手方、跨 authority 净仓、反向、交割、
PM、Isolated、多结算币和股息等特殊资金费均不支持。产品资金费间隔必须存在，且本地
原型只处理 1..86400 秒的间隔。费率为可信运维输入的已批准值，原型不生成溢价指数或预测
费率。默认绝对上限 `.03` 只是可审查的合成参数，未经历史校准或真实人员批准。

`BEGIN IMMEDIATE` 的单一事务在有界准时窗口内冻结事件水位、账户版本、全部本地持仓及
完整行情 payload/SHA；这些逻辑状态才是权威。`period_end` 只是对齐产品间隔的调度标签。
默认最迟两秒；未来或迟到而没有可信边界快照时拒绝，不能用现在仓位补收过去周期。
这与外部平台对时点附近持仓的不确定说明不同。固定标签不是历史快照证明。

每个客户的精确现金变化为 `-signed_quantity × mark × rate`，全程 Fraction。
USD 现金按资产最小单位向零截断，原始精确值、实际现金和当期豁免的亚单位差分别展示。
亚单位差为本地规则下当期豁免的定价调整，不伪装已入账应收或欠款；该政策须真实金融
负责人审核。现金差额不能当任意收入：

| 科目 | 归属与约束 |
| --- | --- |
| `customer:{account}` | 已结算 USD，强制资金费可形成负现金，不能伪装借款本金 |
| `system:perpetual-funding-clearing` | 本次逐客户分录的桥接科目，事务结束必须为零 |
| `system:funding-rounding-reserve` | 隔离的合成舍入资本，亏差先检查足额，不记营业费用收入 |
| 固定配置的运维 treasury 客户科目 | 只能使用既有可信 deposit 已确认的 USD 和正可用余额；资本转移必须真实扣减它 |

三客户手算：USD2、mark=1、rate=.015、数量 `(.4,.6,-1)`，精确现金
`(-.006,-.009,.015)`、实际现金 `(0,0,.01)`；reserve 必须承担 `.01`，不足则整个周期拒绝。
镜像数量 `(1,-.4,-.6)` 的实际现金 `(-.01,0,0)`，产生的 `.01` 仍留隔离 reserve，
不转入 `system:fees`。需要资本时必须引用固定 treasury 已确认的 deposit：核对原
`uta_deposits` 与已封存的入金双分录、可用现金、无持仓/借贷历史/挂单/现货锁和风险冻结。
仅自动转入本周期必要差额，客户不能传入任意 source 账户或充值金额。原 deposit 引用
在 period 中另有 UNIQUE，不能换 ID 重复作为注资证明。该转移与全部资金费分录一起提交。
没有本金为负的 system 科目造 reserve；没有 reserve 提取接口，未完成事务也不会释放
资本给其他周期。真实托管和运维鉴权仍是独立未完成门槛。

## 事务、幂等与风险

`funding_local_periods` 以 `(symbol, canonical UTC period_end)` 为主键，command ID
另有全局唯一约束。更换费率、规则或 command ID 不能重收同产品同周期。相同命令先查原
receipt，内容不同时 409；重复不要求当前行情仍新鲜，不当作最新账户快照。

客户逐币双分录、reserve 转移、账户版本、`supervise_account(connection=...)` 的真实
冻结/撤单/RO 计划、funding receipt 与业务事件在同一原生 writer 事务内提交。监督器不会
制造成交。若失鲜只返回未持久化 BLOCKED，则整个资金费事务回滚；不能宣称已自动冻结。
负现金通过现有 `cash_deficits` 计入风险，不增加借款本金或利息。正常还款与既有风险状态
机的授权规则没有放宽。本组件不要求依赖尚未集成的 MM402c 修复才冻结费用造成的窘迫；
未来合并仍须按完整组合重新验收普通准入。

返回 receipt 必须经过原 context manager 的 COMMIT。异常或超时不等于已失败或已成功，
调用方使用原 command ID 查 `receipt()`，不得换 ID 重试收费。receipt 以哈希和不可变
触发器保护，但数据库文件所有者仍可信；这不是外部签名或恶意 OS 用户隔离。

失鲜或窗口缺失时异常明确表示该周期未完成，不产生成功 receipt，调用方必须把原
product/period/command 与失败原因留在运维待处理记录。当前没有持久 scheduler/待处理义务
登记表，不能把失败后 `receipt=None` 当作免除费用或已经结算；这是一项明确验收缺口。

核对包括完整账本哈希链、精确资金费分录、period/command/journal 引用、孤立保留 ID、
clearing 为零及 reserve 余额。原型重放成本随历史增长，尚无容量验收。既有
DecisionAudit 是数值风险重放，不据此宣称验证新的 funding eligibility。

## 安装、部署与回滚

默认不安装。仅明确调用 `FundingLocal.install_synthetic_fresh(...)` 才创建两个专属表
及不可变触发器；安装时必须没有账户、仓位、订单、成交、存款、负债、账务事件或业务事件。
已有任意 `writer_fence_*` 对象或 writer token 即拒绝；不修改其 catalog、角色门禁、租约、
源版本绑定或旧 authority。管理进程、复制、跨分片资金费、运维鉴权、审批和客户路由均待接入。

重开 `FundingLocal(service, policy)` 只验证精确 schema/config/artifact，不 CREATE 修复
funding 存储。source/runtime/rule 变化拒绝隐式升级。部署仅使用全新私有合成目录，保留原
测试 authority、源码、规则、原始结果与 ledger。不得将此原型接到真实入金。

回滚先停止本组件的新命令，保留完整原 release/runtime 及原数据。用相同代码和规则重开，
先以原 ID 查询 UNKNOWN，再核对分录与风险状态。已收费 authority 不得直接降至无 funding
的旧版本；此迁移尚未实现。不能删除 period/账本、恢复旧快照后二次收费或改 ID 抹平错误。
显式冲正、补资、迟到快照恢复、真实审批和多节点灾备均为独立未通过门槛。

## 验证计划与明确门槛

仅新增六个方法：前三个纯计算；后三个必须另获 root 的全新 SQL scope。
尚未编译、导入目标、执行方法或创建数据库。CLI/REST/worker 均无启用变更。

计划分别验证双边正负零费率，三账户正负 reserve、低 Decimal 精度与拒绝边界，
fresh 安装/幂等/重开/周期全局唯一，强制费用后真实持久风险状态，以及脏保留 ID 的原子
拒绝和迟到边界。脏 ID 会在预核对时拒绝，不冒称已经注入第二分录或 COMMIT 故障。
实际 COMMIT 失败、并发重复、进程终止、真实 scheduler 准时性及 long-run 仍未验证。

资金费专属 archive 除核心 artifact 外，调用既有严格的
`credit_artifact._loaded_modules(("perpetual_funding", "funding_local"))`
捕获新增模块的函数、默认值、闭包和模块/类常量。既有 `_MODULES`、格式及未知常量拒绝
不变。完整交易目录、风险规则、费率和尺度以及参与账户的前后全量估值输入也被归档；
内置 reconciliation 不冒充独立参考模型或风险准入重放。配置及 receipt 分别有 1MiB、4MiB
逻辑内容上限，不是 kernel 配额或容量验收。SQL 计划使用固定合成参考时钟，不能证明
生产调度准时性或行情生命周期。
