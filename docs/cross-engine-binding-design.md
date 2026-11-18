# Cross 估值引擎绑定与分阶段接入提案

状态：**DESIGN_ONLY，未实现、未运行、未激活、未获生产批准**。本提交只增加设计与规则契约；不修改金融运行时，不读取数据库或进程，不执行目标 import、编译、测试、CI、worker 或外部服务。规则均为本系统选择；这里没有把公开交易所行为推定为已验证事实。

## 1. 建议与边界

建议先交付固定可调用对象的执行绑定，再为**新建、合成数据、单机独占写入者**增加显式版本化的同步 shadow 契约。默认仍是 Fraction 参考实现；shadow 的权威结果仍来自参考实现，Decimal 候选只做逐字段验证。Decimal 权威接入必须使用另一个不可变契约，重新通过数值、账务、重启、故障和容量门槛，不能通过修改默认值或配置热更新启用。

本提案不是 PM、Isolated、借贷生产化、经典账户切换或多节点接入的批准。已有负债的**估值语义**需要保持；新的借款授权、Credit V2 能力安装、自动借币、归还借贷等金融操作不因估值候选存在而获得支持。现阶段不迁移任何已有 authority，不修改历史归档来使校验通过。

两种可实施方案：

| 方案 | 改动与收益 | 风险与代价 | 选择 |
| --- | --- | --- | --- |
| A：平面策略增加 engine 字段，并同步升级所有消费者 | 改动表面较少，估值器调用点容易替换 | 当前估值策略精确十字段、订单策略十一字段、Credit V2 两个缓存参数均会改变；遗漏 `_source_arguments`、历史回放或 worker 后会产生拒绝不一致。只有同时定义新版本和完整迁移才成立 | 不作为首次接入 |
| B：默认格式保留，实验风险策略及订单归档使用独立版本化 envelope | 保留默认十/十一字段语义，实验格式明确拒绝旧 parser；选中实现与信用模型版本分开 | 需要新增有限的版本分派和已有库打开路径；旧二进制排斥仍须实测，配置比较不是 writer fencing 证明 | **推荐** |

不引入插件系统、任意模块加载、注册外部函数或通用策略 DSL。只支持编译时封闭的两个 engine ID，以及列在本文的少量契约。

## 2. 静态证据与集成前置

本次读取的是 Git 不可变对象，未执行这些对象。逐文件 blob 与 SHA-256 在 [source-evidence.json](../evidence/designs/cross-engine-binding/source-evidence.json)。

| 证据 | 固定提交 | 可以证明的范围 |
| --- | --- | --- |
| PR49 | `c3e937a967711cd5cae7293ac3bf63c8260d8528` | ledger、startup、writer fence 等源代码 |
| PR52 | `e7fa6e41eff8dda28c9f4cd64d7e4df7ab45867c` | 十字段 valuation 与十一字段 order 分离后的源代码；相关 CODE 为 `5422095564ba19de9c04cd7888354c2f745acf94`，本次未复跑 |
| PR51 | `8262bb7226d0b110d2c89bb1c58293e7908fa420` | Decimal 候选交付源代码 |
| PR55 | `03dfa275def7ee6e5997894398f8f6de30b6f2f0` | 独立 oracle 交付源代码；本提案基线 |
| 已发布数值样本 | RAW `7de83651bc6cf9c6f1232af78839a432f4a45d59`；golden `866704` bytes，SHA-256 `17364d12847d5f118cc62f0e301a45180e8ccd353a38010e3cf3582a917afd97` | 仅引用公开有限 538 例证据；不是本次运行、完整域证明或服务接入证据 |

PR52 对 PR49 有六个 `uta/` 文件变化：`credit_audit_v2.py`、`decision_audit.py`、`ledger.py`、`service.py`、`startup.py`、`writer_fence.py`。PR55 对 PR49 的运行时变化只有 `cross_decimal_kernel.py`。所以不存在可直接假定已经包含两者的基线。实现前必须先合并并独立审查：保留 PR49 的 ledger/startup/fence 改进，合入 PR52 的 service/decision/credit 规则修复，再合候选。

原 61/62 文件 source plan、已发布 CODE/RAW 及历史 scope 保持原有含义。新增运行时模块后应生成新的精确 inventory，不得把旧 inventory 改为新代码的验证证据。

### 2.1 实际调用与依赖

| 文件/函数 | 当前行为 | 实验接入缺口 |
| --- | --- | --- |
| `service.ExchangeService._risk` | 在同一账户事务中取账本、冻结、独立本金/利息、现金缺口、仓位与原 reserve，直接调用导入的 `calculate_cross_risk` | 没有 engine selector；修改一个新单路径不等于替换完整风险路径 |
| `DecisionAudit._loaded_engine` | 固定九个模块，记录函数及 unwrap 后 code object | 不覆盖候选模块、函数 defaults/kwdefaults/closure、运行常量、服务实际选中的 callable |
| `DecisionAudit.code_artifact` | 全部 `uta/**/*.py` 的在盘摘要 + 固定模块 loaded code + runtime 字符串 | 文件摘要不能证明选中了哪个函数，也不能证明 loaded class/constant 与文件一致 |
| `credit_artifact._loaded_modules` | 更完整地编码函数 defaults/kwdefaults/closure、模块/类常量；模块集合固定 | 候选不在集合；类对象主要按名字编码；不证明 dispatcher 的真实 alias。不能直接把 source SHA 当 live binding |
| `DecisionAudit.valuation_policy / policy` | valuation 精确十字段；order 在其上增加 admission，精确十一字段 | 不能把 order 字段重新塞给 Credit V2 |
| `DecisionAudit._replay_state / replay` | 参考实现重建；当前/归档 artifact 必须精确相等 | 新格式必须显式分派；旧格式始终参考，不能按当前默认 engine 重放 |
| `existing_services._source_arguments` | 风险策略仅允许 legacy 一字段或 Cross 三字段；审计缓存参数须唯一候选且精确两字段 | 必须精确解码实验格式、核对归档与持久策略，禁止歧义时猜测默认值 |
| `open_existing_services` | 总是打开 ExchangeService 与 CreditService | 实验格式不能意外安装/打开信用能力；需要明确的 exchange-only 打开路径 |
| `credit_audit_v2.audit_policy / _persisted_policy / replay_risk` | ten-field base、两缓存参数且均为零；独立匹配持久策略；参考估值 | Credit V2 本轮保持原格式并拒绝实验契约；不得删除 engine 字段冒充旧政策 |
| `durable_process._options / initialize / takeover`、`ShardRouter`、supervisor | 描述符、封印、接管和缓存证明传播现有配置 | 首次实验拒绝 managed/sharded/native 路径；后续单独升级所有传播与 precommit 验证 |

## 3. 执行身份：必须绑定实际调用

新增有限模块 `uta/risk_engine.py`，只负责本系统 Cross 估值器的固定解析、输入域验证、调用与精确比较。推荐函数：`resolve_valuation_contract`、`capture_engine_binding`、`assert_engine_binding`、`evaluate_cross_contract`。名称是实施提案，不是已经存在的 API。

`cross_fraction_v1` 固定到 `portfolio.calculate_cross_risk`；`cross_decimal_v1` 固定到 `cross_decimal_kernel.calculate_cross_risk_decimal`。默认参考路径不因读取归档内任意字符串而导入模块；实验 opt-in 才由固定代码导入候选。归档中的 engine ID 只选择封闭集合，模块路径、类名、函数名、callable 参数和动态 import 一律不作为执行输入。

### 3.1 新 binding artifact 的精确范围

另设 `RISK_ENGINE_BINDING_FORMAT = 1`，与现有 credit artifact format 分离。对实验决策增加新的 artifact envelope；legacy format 1 的解析语义不变。外层必须精确列出 `format`、`base_artifact`、`engine_binding`；`engine_binding` 精确列出 binding 格式、契约 ID、可调用对象图、常量与别名、类布局、runtime capsule 和摘要算法。不能接受未知 key、未知对象类型、无界递归、重复 JSON key 或丢失字段。

必须覆盖以下事实，而不只是模块名：

1. 实际调用的函数对象必须与固定模块属性和固定 registry 的对象相同。记录服务 dispatcher、replay dispatcher、选中 ID 与函数对象关系；每次从受检 registry 取得 callable，不另存一个未受检的实例 alias。若实现选择保存 alias，alias 本身也须作 identity 检查。
2. 函数的 `__code__`、defaults、kwdefaults、closure、unwrap 链以及它们引用的可执行 helper；仅比对 `__qualname__` 不够。任何未定义的 wrapper、descriptor、可执行闭包或动态 registry 项拒绝。
3. Decimal 候选的 `_exact_type`、`_discounted`、`_Arithmetic` 所有执行方法、`calculate_cross_risk_decimal`；参考函数、输入校验、精确转换及其相关 helper；`CrossRisk`、`LoanAccount`、`LinearExposure`、产品/市场/规则模型及其校验路径。
4. `_ZERO`、`_ONE`、`_MAX_POWER=1000`、`_MAX_SCALAR_CACHE=2048`，使用中的数值边界、类常量、枚举及实际全局 alias。`Decimal`、模型类、helper 与 `_Arithmetic` 的引用必须指向固定预期对象，不能只记录其名字。`Amount` 类型别名由 source/annotation 范围覆盖，不能借此跳过任何执行期对象。
5. 自有类的精确 `type`、module、bases、slots、方法/属性槽及 dataclass 布局。未知 metaclass、动态 `__getattribute__`、反射分派、任意 `__call__` 对象拒绝。对受审标准库对象使用封闭身份规则，不对用户对象调用 `repr`、自定义序列化或属性 getter 来生成摘要。
6. 数值 runtime：固定发布镜像与解释器/`_decimal`/标准库制品摘要，字节序/实现/优化参数以及源文件摘要。仅 Python 版本字符串不足以声称 C 扩展相同。发布镜像和 runtime capsule 的验证应由部署层完成，不能让归档提供任意路径读取或执行。

候选的最小固定清单是：`_Arithmetic.__init__/power/read/nonnegative/positive/rate/negative/absolute/add/subtract/multiply/compare/floor_ratio/ceiling_ratio/decimal`，模块三个执行函数与 `DecimalKernelUnsupported`；其导入模型包括 `MarketSnapshot`、`AssetSpec`、`InstrumentSpec`、`BorrowLimits`、`CollateralRule`、`CollateralTier`、`CrossRisk`、`LinearExposure`、`LinearMarginRule`、`LoanAccount`、`PortfolioRules`、`AccountMode`、`ProductCatalog`、`ProductKind`、`ProductSpec` 及异常基类。该清单随代码变更必须显式复审，不能仅扫描大写名字后认为已完整覆盖。

还必须绑定实际函数的 globals/builtins 查找关系。候选使用的 `type/isinstance/len/abs/min/max/set/sorted/int/tuple/map/str` 等内建名称若被模块 global 或 `__builtins__` 遮蔽，也会改变计算；发布时应生成并复核封闭的执行名字清单，验证实际查找对象来自固定模块/受信 runtime。清单不认识的新 lookup、反射访问或运行时生成执行器均拒绝，不把标准库对象无限递归编码成通用对象图。编译时清单与静态源范围不一致属于独立阻断项。

可局部复用 `credit_artifact` 的有界静态编码方法，但不能放宽其 format 1、固定模块清单或 live-global 排除项。未知对象一律失败；不得为“hash 总能通过”添加通配排除。实例内部的 call-local arithmetic cache 与配置化 reserve/market cache 分开处理，前者不跨请求复用，不属于可热变更策略。

### 3.2 校验时点与威胁假设

构造器在打开/创建金融 authority **之前**解析并验证契约与 binding；只读打开再次验证。每个估值决策取得单次 `now`、同一 immutable account/market/rules/catalog 后校验，在提交接纳回执和预占前再次校验。发现函数、常量、类、registry 或 selected ID 漂移即阻断新风险并记录告警。不能只在启动计算一次，再永久信任缓存。

该机制检测受信进程中可观测的错误绑定或变更，**不保证防御可同时修改检查器和目标、或在两次检查间任意写内存的攻击者**。进程、OS、镜像和源码不可变是明确假设。Python 同进程 hash 不是沙箱、签名、远程证明或 writer 权限。单写者、fencing token、账户版本、事务和既有控制面验证仍须分别成立。禁止以这个提案绕过现存受阻的 AuthDB probe 或既有运行授权范围。

## 4. 持久策略与历史版本

### 4.1 默认契约：保持精确旧格式

未指定 engine 时：现有 legacy/Cross `risk_policy` 格式不变；`DecisionAudit.valuation_policy` 仍是十字段，`DecisionAudit.policy` 仍是增加 `admission_contract` 的十一字段。`execution_options` 仍仅包含 `reserve_cache_size`、`market_cache_size`。不向现有字段注入 engine selector，也不重用风险模式、catalog version、rule version 来表示执行器版本。

新增源码必然改变 source artifact ID，因此“格式保持”**不表示新二进制可以冒充旧 code artifact**。历史 archive 不改写；需要旧代码的重放仍要求固定旧制品。当前 replay 的精确 code/runtime 不匹配拒绝语义保持。新二进制能解析旧格式，也不能据此宣称它已获得执行旧历史代码的授权。

### 4.2 实验持久风险策略

仅显式 `valuation_contract="UTA-CROSS-SHADOW-v1"` 可请求实验模式。初次只允许新数据库、新 authority generation、合成账户。配置全部不可变，catalog/rules 原格式继续使用。

```json
{
  "format": 2,
  "mode": "phase1_cross",
  "catalog": "<existing canonical catalog object>",
  "rules": "<existing canonical portfolio-rules object>",
  "valuation_contract": {
    "format": 1,
    "id": "UTA-CROSS-SHADOW-v1",
    "authoritative_engine": "cross_fraction_v1",
    "shadow_engine": "cross_decimal_v1",
    "numeric_contract": "UTA-CROSS-LOAN-v1",
    "input_domain": "UTA-CROSS-DECIMAL-DOMAIN-v1",
    "comparison": "exact_value_and_canonical_text_v1",
    "failure_policy": "freeze_new_risk_preserve_settlement_v1",
    "dispatch_contract": "fixed_callable_binding_v1"
  }
}
```

上面 catalog/rules 的字符串只为文档占位，**真正持久化必须是现有 canonical object**。其余 key 集合、值、类型固定于 [contract.json](../evidence/designs/cross-engine-binding/contract.json)。`true` 不能作整数版本，重复 key、未知版本/engine/字段、未知 mode、旧代码均拒绝。契约 ID 是固定编译规则的名字，不是用户可自由拼装的可变参数。source SHA、runtime binding digest 进入 artifact；不把 SHA 塞入 valuation policy 后通过“忽略字段”打开旧格式。

实验订单 archive 使用新的精确 envelope：

```json
{
  "format": 2,
  "valuation_policy": "<exact existing ten-field format-1 object>",
  "valuation_contract": "<exact fixed shadow contract above>",
  "admission_contract": "UTA-LINEAR-ADMISSION-v1"
}
```

此处 `valuation_policy` 必须是 object。它表示相同金融规则的十字段描述，不能单独证明实验引擎契约；完整 envelope 必须与持久风险策略一致。Credit V2 不接受这个 envelope，也不能只取 inner base 当作一次成功的实验信用决策。

### 4.3 初始化、打开、重放和旧 writer

- `ExchangeService.__init__` 在金融 DDL/写入前校验 opt-in 与支持域；实际持久风险策略必须完全等于编译契约产生的 canonical 值。已有格式不匹配返回迁移要求，不创建替代 archive 或修复字段。
- `existing_services._source_arguments` 按明确版本读取；持久风险契约、order archive、base valuation、artifact、cache options 和 engine binding 必须唯一且一致。零个或多个候选均拒绝，禁止按最近时间或默认配置猜测。新增 exchange-only 打开路径，实验库的旧 `open_existing_services` 明确拒绝，不能意外构造 CreditService。
- `DecisionAudit` 构造时机须在契约解析后；实验 artifact 只能在新 envelope 下写入。`_replay_state` 由 archive 版本明确分派：v1 固定参考；v2 固定 shadow，完整重算两侧。未知版本、缺失 candidate artifact、runtime/code 不匹配拒绝，不导入 archive 指定的模块，不重算后改写旧结果。
- 实验决策输入新增严格的 `valuation_evaluation` 记录，精确字段为 `format=1/evaluated_at/max_age_us/market_snapshot_id/contract_id/binding_id`，记录本次唯一 UTC 估值时间、原 market snapshot 与 binding identity；max age 必须与政策一致。v2 重放按这个时间做 freshness 检验。现有 v1 数值重放使用 `market.observed_at`，不能凭数值匹配宣称已复核历史行情新鲜度、历史 lease 或撮合；保留这个限制，不补造旧时间。
- Credit V2 的 `BASE_POLICY_FIELDS` 十字段、两缓存参数和受审 format 不变。`audit_policy`、`_persisted_policy`、安装和新 borrow 入口在实验契约下提前拒绝；必须发生在资金池、借贷账、能力或权威状态变化之前。未来信用候选需单独新模型/政策版本和独立审查，不偷升级现有 V2 authority。
- 受管 worker、sharded/native router、takeover、descriptor seal、supervisor cache proof 在未完整传播新契约前显式拒绝实验。不能只增加 API 参数而在接管时回落到参考或丢失 selector。
- PR52 的完整持久风险策略字符串比较说明旧普通构造器具有静态不匹配拒绝路径；这**不是所有旧写入者已失效的证明**。必须用固定旧二进制覆盖构造、只读打开、worker 接管、直接金融入口，比较金融表/账本/预占前后。允许的控制租约尝试须单独记录。若任何入口可越过契约执行金融写入，需先追加 schema/capability fence；不得启用 shadow authority。
- 热更 engine、改 source 文件、换 class/constant、修改 catalog/rules 或跨契约恢复均拒绝。配置回滚和历史 replay 是不同操作，不得用一个布尔开关重新解释旧决策。

## 5. 首次支持域与拒绝行为

| 维度 | 首次实验范围 | 明确拒绝 |
| --- | --- | --- |
| 权威/部署 | 新建合成数据；单机独占 writer；Cross；Fraction 权威 + 同步 Decimal shadow | 已有 authority 原地升级、真实资金、自动切换、managed/sharded/native 路由 |
| 产品 | 已有 phase1 服务支持的 USD 报告/结算、multiplier=1 线性永续；既有多资产抵押估值 | USDT/USDC 的真实交易所同名等价假设、交割、反向、期权、PM、Isolated、多结算币 |
| 数值 | 精确现有模型类型、finite Decimal；候选当前边界 80 digits、abs exponent≤100、非零 abs adjusted≤100；最多 64 tiers/每个 model map 4096 项 | bool/float、子类、NaN/Inf、未知类型、超域；不得压缩/四舍五入输入以“适配”候选 |
| 抵押/负债 | gross assets、frozen、principal、interest、cash deficit 分量独立，tier haircut/LTV 保持；现有负债仅用于估值与合成重放 | 无依据资产负债净额；新信用授权/自动借币/信用能力安装；抵押变化被视为自动获准 |
| 新订单 | 原服务已经支持且经过审查的线性限价与 reduce-only 规则、数量步长、单腿部分成交；原持久预占与接纳 | 本提案未验证的市场单、条件单、批量/多腿、隐式换币或新订单类型；不凭候选能力扩展 API |
| 既有义务 | 撮合确认后的成交、费用、预占释放按原参考权威和幂等规则履行；撤单确认前保留预占 | 用 shadow 失败丢弃已确认成交、提前释放在途预占，或把未成交当处置完成 |
| 清算/借贷/资金 | 可以离线估值风险样本，不授予新产品能力 | 候选权威清算、保险/ADL、借贷变更、资金划转/提币/模式转换及其他未独立验收路径 |

候选纯模型可支持 multiplier 不等于 1；**不能据此放宽当前服务的执行域**。公开 538 样本不证明全域，也不覆盖撮合、入账和吞吐。

### 5.1 同步 shadow 的原子语义

先在原账户事务里捕获一份现有逻辑生成的 LoanAccount（含原 reserve）、同一 market snapshot/catalog/rules 与单次 `now/max_age`。参考和候选读取相同值，不二次查询账户、不取新行情、不改 fees/reserve/仓位投影。比较 CrossRisk 全部金额、borrowable 键/值、status、rule/catalog/market 版本与 market ID；要求精确数值及既有 canonical text 一致，不使用容差、浮点或当前 Decimal context。未知输出类型、少字段或额外字段拒绝。差异报告保留输入摘要与字段，不把客户敏感数据写入公共仓库。

新增风险路径遇到 unsupported、mismatch 或 binding drift，原接纳与预占事务回滚，返回确定错误并用独立可审计控制记录冻结新增风险。冻结记录如何与金融回滚保持关联须实现并故障测试，不能在已回滚事务中声称告警已持久化。未取得接纳回执的命令仍按原命令 ID 查询结果，不能盲目重提。

**已确认成交及其他必须履行的结算义务不能因 shadow 失败被丢弃。** 此时参考一直是声明的权威，不存在从候选临时切换；照原规则持久结算，同时记录 candidate 失败、停止新增风险并进入人工调查。撤单等不增加风险且无需新估值的路径继续执行。若当前服务无法区分新增风险与必须结算义务，首次同步 shadow 只能用于只读/离线验证，直到这一区分经过独立验收。

建议错误契约（未实现）：未知 opt-in 参数/engine 为 400 `valuation_contract_unsupported`；已有库不匹配为 409 `valuation_migration_required`；runtime/binding/持久 archive 缺失或不一致为 503 `valuation_binding_unavailable`；新风险 shadow 数值差异为 503 `valuation_shadow_mismatch`；超出实验支持域为 422 `valuation_domain_unsupported`。不得将这些错误转成成功的零结果、旧模式成功结果或无日志 fallback。业务已有错误契约须在实现 PR 中逐项映射，不能悄悄改变 409/超时/结果未知的重试语义。

## 6. 人工可复算案例

下面是本系统固定测试规则，不是外部交易所保证金政策。第一至三例沿用已公开人工样例，第四例是服务集成必须人工验证的合成费用/预占例；全部要求独立验证组复算。

1. **Gross debt 与折扣，M02。** BTC=2，价格100，抵押因子0.8，LTV0.5；本金1.25 BTC、利息0.05 BTC；borrow IM/MM=0.1/0.05。原始资产200，债务130；会计权益70；抵押160；风险权益30；loan value80；IM13，MM6.5，可用17，可借0。不能先净成0.7 BTC再折扣；利息不能被藏入本金。
2. **冻结、分层与组合，M01（纯模型，不是 multiplier=1 服务用例）。** USD1000+BTC2@100；冻结BTC0.5；BTC首100抵押0.8、其后0.5，故 BTC 抵押105、总抵押1105；USD/BTC LTV分别0.8/0.5，loan value852.5。本金USD100+BTC0.1=110，利息USD1+BTC0.01=2。线性 q2、multiplier2、mark110、cost400，PnL40。会计权益1128，风险权益1033。USD borrow IM/MM0.1/0.05、BTC0.2/0.1、线性0.1/0.05，IM=101×0.1+11×0.2+440×0.1=56.3，MM28.15。order10，可用966.7。总债务上限500时单独 USD quote388、BTC quote3.88；**二者不是可叠加的同时授权**。
3. **MM 等号，M09。** USD11，抵押/LTV=1，借款IM=MM=0.1，step1，上限100。借10后权益1等于MM1，故拒绝，最大quote9。USD11.01 时借10后1.01>1，可以通过这一边界；其他限额仍要独立满足。零权益/零MM同样是清算边界，不能因分母零返回安全。
4. **费用与存量预占，EBD-M04。** USD100，线性数量1、limit100、multiplier1，IM0.1/MM0.05，fee0.0004，USD最小单位0.01。成交0.5收0.02，现金99.98、仓位0.5/cost50。剩余原单预占5.02；新 reduce-only0.5在同价位还须保留fee0.02，合计order margin5.04。当前IM5、MM2.5、available89.94。投影该reduce-only完全成交后现金99.96、仓位0、原单reserve5.02，可用94.94。实际测试必须使用现有 cumulative-fee 和 reserve 函数的受审规则并由独立组复算；若前置假设不成立则拒绝此 fixture，不能改期望迎合实现。

多次部分成交的累计费用进位、signed cost dust、负现金、同币资产/债务、冻结原因与 reserve 取整必须分别保留。候选只替换估值计算，不重写资金最小单位、成交费用累计进位或原 admission 投影。

## 7. 精确实施位置与验收分期

| 阶段 | 最小改动位置 | 验收后可以做什么 |
| --- | --- | --- |
| D0 静态设计（本提交） | 本文、machine contract、source evidence | 仅审查，不运行目标 |
| D1 绑定与纯计算 | 新 `uta/risk_engine.py`；`DecisionAudit` 新 artifact envelope；新 bounded binding tests；独立 oracle 保持独立，不复用生产核心函数 | 在单独批准的源范围运行纯计算/变更负例，不能写金融 authority |
| D2 新建库同步 shadow | `ExchangeService.__init__/_risk/_policy_versions`；`DecisionAudit` policy/install/replay；`existing_services._source_arguments` 与 exchange-only opener；Credit V2 显式拒绝 | 仅新建合成单机账户，完整新风险/既有结算区分验证通过后才可用 |
| D3 系统集成 | managed options/config/descriptor/takeover、sharding、supervisor/cache/precommit、信用新版本的各自独立 PR | 各路径单独验收；不能因 D2通过就启用 |
| D4 候选权威 | 新 `UTA-CROSS-DECIMAL-AUTH-v1` 固定契约；只读到小批新 generation；业务/金融/独立组共同批准 | 仅明确批准的产品和账户，默认仍不变；真实资金还需明确上线审批 |

`UTA-CROSS-DECIMAL-AUTH-v1` 只是保留名称，本提交不定义可接受 JSON，也不把它加入允许列表。新增纯模块意味着 inventory/loaded artifact 需要新版本；先审查源范围，再做可运行 CODE，绝不继承其他 source plan 的旧 GO。

### 7.1 最小有意义的测试门槛

详细编号见 [contract.json](../evidence/designs/cross-engine-binding/contract.json)。以下全部**未运行**：

- **EBD-001..004 执行身份：** 同名同输出 callable 替换、code/default/kwdefault/closure 变更、常量/类布局/global alias 变更、未知 registry/动态 import/反射输入，均拒绝；在盘 SHA不变但 loaded对象变更仍应拒绝。受信进程假设必须随结果声明。
- **EBD-005..009 版本：** 默认十/十一字段保持；新策略每个未知/缺失/重复字段和错误类型拒绝；Credit V2 原正例保持且实验拒绝无金融写入；固定旧二进制拒绝所有实验入口；只读打开无DDL；新旧归档分别按原代码/规则精确重放，不修改旧 archive。
- **EBD-010..012 数值与事务：** 同份输入、单次时间；新风险差异回滚；已确认成交仍幂等结算且锁新风险；gross debt、frozen、deficit、cost dust、原fee/reserve、撤单与部分成交；独立人工案例、已公开有限样本、边界与样本外生成。差分 oracle 不得调用候选或参考核心函数。
- **EBD-013..015 系统与容量：** 真实独立撮合、订单/成交/仓位/分录四侧关联、重启和结果未知恢复；独立开放环的持久接纳/完整清算成交门槛；灰度与回滚演练。纯计算、单机持久链路、多节点链路分开报告。

任何数值差异、重复占用、重复分录、旧 writer 可写、历史被重新解释、结果未知被重试产生第二影响、未确认成交被算作处置，独立验证组可以否决后续阶段。代码作者不能代签独立数值和金融规则审查。

### 7.2 容量与模型准入

先分别测 Fraction、Decimal、同步双算、artifact binding 检查、序列化、日志/账本持久化、队列、撮合往返；同步 shadow 是双算验证，不应宣称性能优化。binding 检查开销单独报告，不得为了 TPS 移除它或未经验证缓存可变关系。

系统生产门槛沿用户标准执行：开放环、同硬件/存储/复制/流动性配置、至少30分钟及额外长稳；订单每秒≥10,000完成持久接纳与预占；清算每秒≥10,000**唯一真实撮合确认、仓位和资金账都持久提交**的成交；通过/业务拒绝/技术失败/超时/结果未知分报。混合负载、双倍突发、热点、跳变、脱锚、深度下降、行情过期与故障恢复必须覆盖。P50/P95/P99/P99.9 从计划到达计时，保留原始量、队列、积压清空、撮合可执行量、重开存储对账和抽样完整回放。

公开有限 538 样本、原 10,809 次纯计算判断、625 次持久订单和359笔模拟清算历史数字均不能满足这些系统门槛。本提交不报告新的吞吐、执行成功、独立签字、RPO/RTO或生产通过。

## 8. 部署、迁移、灰度与回滚

1. 固定组合源码与新 inventory；部署不可变制品，归档镜像/runtime/source/binding/policy/model/market 版本；独立审查后先 D1，禁止启动真实资金服务。
2. D2 只新建合成库与 generation；账户 allowlist 固定并可审计。启动前证明旧写入者排斥及新 writer lease；只有完整参考权威、实验契约与 archive 一致才接流量。未支持路径在接触金融状态前返回拒绝。
3. 灰度以明确账户 generation 切分，不随机按请求选择 engine。同一账户始终单一契约；不跨两个 writer 双写。只读影子与金融写入权限隔离，灰度比例不是上线授权。
4. 差异/超域/binding drift：冻结新增风险，继续撤单、必须结算和查询；记录失败输入摘要、command/decision/trade/ledger IDs。先查询原命令结果，再重试或恢复；不自动换引擎继续下单。
5. 回滚服务时保持新库停新风险；保留新制品处理在途确认成交。旧二进制应拒绝实验库，不能通过删键、改 schema/version、改 archive 或复制余额强行打开。没有新增金融事件时，可销毁合成实例并由受审参考制品新建；已有事件则导出完整事件、对账并以新 generation 做明确迁移/补偿，不能假装历史未发生。
6. 恢复/升级时重新核验 binding、存储、policy、账本与未完成命令，保留 fencing 与序列连续性。数据迁移有单独 PR、映射、余额/仓位/订单/逐分录校验、暂停窗口和失败处置；本设计不授权旧 authority 切换。

## 9. 尚未闭合的证据

- 尚未有合并后的可运行基线、真实旧二进制排斥验证、执行 binding 负例、同步 shadow 金融原子性测试或新策略回放结果。
- 首次新建库能否在不激活 Credit V2 的情况下导入带本金/利息的合成快照，必须有受审导入契约；不可直接写负债表。未实现前，带债测试仅为纯估值/离线重放，不宣称完整借贷纵向链路。
- 现有 API 与撮合状态能否完整区分新增风险、撤单和必须结算义务，需代码路径复核；不满足时只能只读 shadow。
- 运行时制品、旧 writer、managed descriptors、控制租约副作用、原 H1 AuthDB probe 的授权与验证范围均未因本文扩大。
- 候选的有限 exact-domain 数值证据不是 PM 校准、市场事故回放、流动性清算、复制/RPO/RTO 或容量准入证据。
- 外部交易所 haircut、净额、PM 风险单元、API 生命周期等规则未经本轮一手证据验证，不归因给任何交易所。这里选择 gross debt、严格 MM 等号、封闭 selector 与不可变账户契约，理由是保持现有可审计模型并避免隐式授权。

金融规则负责人、独立验证组和上线批准人均未签字；本提交不会生成伪签名或把文档评审标作生产验收。
