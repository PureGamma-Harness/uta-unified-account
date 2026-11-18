# Cross 估值引擎绑定与分阶段接入提案

状态：**DESIGN_ONLY，未实现、未运行、未激活、未获生产批准**。本提交只增加设计与规则契约；不修改金融运行时，不读取数据库或进程，不执行目标 import、编译、测试、CI、worker 或外部服务。规则均为本系统选择；这里没有把公开交易所行为推定为已验证事实。

本版为 D0 修订2，整合固定审查提交 [金融审查](cross-engine-binding-financial-review.md) `40bee5ff668c20e31492ea5b2964242a31ad9b40` 与 [独立验证审查](cross-engine-binding-independent-verification.md) `5b00e14b7eca382d7e9c8022437f0d5ced1fc38b`，审查原对象仍是 `53acece53d27fb118c89286c10e5be41bb2ca5e7`，不改写原审查结论。**D2 金融 shadow 明确 BLOCKED**：下述恢复、关闸、绑定及最终行情时点都是待实现/待证的契约；补充规格不等于关闭 EBD-FIN-001/002 或 EVG-001..008。D1 纯绑定可另行审代码和执行计划；本文不给任何目标执行 GO。

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

分阶段新增有限模块：D1 纯绑定提案使用 `uta/risk_engine_binding.py`，只产出固定图证据并检查/解析已知函数；D2 才考虑 `uta/risk_engine.py` 的契约解析、输入域验证、实际调用与精确比较。后者推荐 `resolve_valuation_contract/evaluate_cross_contract`，前者的 capture/assert/resolve API 随独立 D1 CODE 审查固定。名称是实施提案，不是已经存在或已授权接入的 API。

`cross_fraction_v1` 固定到 `portfolio.calculate_cross_risk`；`cross_decimal_v1` 固定到 `cross_decimal_kernel.calculate_cross_risk_decimal`。默认参考路径不因读取归档内任意字符串而导入模块；实验 opt-in 才由固定代码导入候选。归档中的 engine ID 只选择封闭集合，模块路径、类名、函数名、callable 参数和动态 import 一律不作为执行输入。

### 3.1 新 binding artifact 的精确范围

另设 `RISK_ENGINE_BINDING_FORMAT = 1`，与现有 credit artifact format 分离。对实验决策增加新的 artifact envelope；legacy format 1 的解析语义不变。外层必须精确列出 `format`、`base_artifact`、`engine_binding`；`engine_binding` 精确列出 binding 格式、契约 ID、可调用对象图、常量与别名、类布局、runtime capsule、摘要算法及 `trust_partitions`。这是尚未部署的 D0 草案修订，不是对已存在 format 1 的隐式兼容升级。不能接受未知 key、未知对象类型、无界递归、重复 JSON key 或丢失字段。

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

构造器在开放正常金融/新增风险 authority **之前**解析并验证契约与完整 binding；只读打开再次验证。既有实验库的启动恢复先经独立 authority/reference 验证与持久关闭新风险闸门，再做 candidate 检查，不走自动修表/安装的正常构造器；首建失败也不得产生可写资金账户。每个估值决策取得单次 `now`、同一 immutable account/market/rules/catalog 后校验，在提交接纳回执和预占前再次校验。发现函数、常量、类、registry 或 selected ID 漂移即阻断新风险并记录告警。不能只在启动计算一次，再永久信任缓存。

该机制检测受信进程中可观测的错误绑定或变更，**不保证防御可同时修改检查器和目标、或在两次检查间任意写内存的攻击者**。进程、OS、镜像和源码不可变是明确假设。Python 同进程 hash 不是沙箱、签名、远程证明或 writer 权限。单写者、fencing token、账户版本、事务和既有控制面验证仍须分别成立。禁止以这个提案绕过现存受阻的 AuthDB probe 或既有运行授权范围。

### 3.3 稳定图、真实查找 anchor 与信任分区

进程内身份和持久身份分开。可信启动时从固定、受审模块建立对象 anchor：每个函数必须是预定模块/registry 指向的函数，其 `__globals__` 必须是该模块受检的实际 globals dict；其自身 `__builtins__` 实际查找映射及每个使用的 builtin 必须匹配受信 runtime anchor。只比较模块 `__builtins__` 不够，另一个 FunctionType 可以持有不同 builtins。沿 helper 的执行边重复相同检查；已变更对象本身不能在重启时自动成为新的可信 expected 值。预期制品/binding 由另行受审发布输入固定，不从历史归档提供的函数名加载。

持久 graph 使用固定逻辑节点名 `(module, qualified_name, object_kind)`，边记录来源节点、静态成员/lookup 标签、目标节点；同一共享对象使用同一逻辑节点。节点和边按规范 UTF-8 字节排序。primitive 使用显式类型标签，区分 bool/int、finite Decimal tuple、字节和字符串；code object 使用固定 runtime 下的规范字段编码。字符串不通过 repr、内存地址或隐式 Unicode 归一化改变。canonical JSON 使用 sort_keys、紧凑分隔符、allow_nan=False，再加固定格式域前缀计算 SHA-256。`id()`/is 可以用于本进程临时去重或身份断言，绝不能进入持久 ID、manifest、名字或排序依据；绝对路径、时间和缓存插入顺序也不进入 ID。

D1 必须先固定数字上限与规范字节，与当前纯绑定 CODE 提案对齐的待审预算为 nodes2048、edges32768、depth24、每容器2048项、canonical4MiB、unwrap8。它们不是实际覆盖或性能通过结果，装不下须明确新 schema 修订而非自动扩容。任何改变须连同 encoding version 明确评审。已知逻辑节点间的共享边/回边只能来自固定已审清单；未知环、wrapper、default_factory、descriptor 或越界图有界失败。类方法/property accessor/dataclass default/default_factory 的执行边不能因“生成代码”被统称排除。跨两次干净可信启动相同制品须得相同 digest，同时 mutation 负例证明 actual identity 漂移会拒绝。各分区先对不含自身 `binding_id` 的规范 payload 求摘要，再把派生 ID 纳入外层；禁止摘要自引用。

上述 D1 提案精确固定为 `f34644bd8300e94d39d8782b04bcca0673023da1`，基线 `d1fd381bde923dc4010977058b76e34d6162e9a9`；提案文件为 `docs/cross-engine-binding-d1-protocol.md` 和 `evidence/designs/cross-engine-binding-d1/proposal.json`，其不可变摘要另列于 source evidence。该提交本身只有文档/JSON，未合入此分支，也没有新模块实现或目标运行。它提出2个 engine、23个 named own functions、22个 own classes及更小 scalar/code 上限；外部 runtime capsule 不由纯 binding 自认证。D1 evidence format 与这里未来 D2 的完整 audit/recovery envelope 不是同一对象，不能互相冒充；返回一个固定 callable 也不证明 service 最终实际调用它。新模块使现行 V3 inventory65py/66runtime 变为未来66py/67runtime，仍需另行新版本清单审查，不能复用旧 normal CI GO。

`trust_partitions` 在 D2 必须精确区分 `authority` 和 `candidate`。authority 闭包覆盖参考计算、共享模型/runtime、账户/订单/费用/预占/资金/仓位、fencing、控制、结算与参考审计；candidate 仅包含候选专属函数、类、常量和文件，引用共享节点时指向 authority 的固定节点。两分区都列出逻辑节点/边和精确 source scope 并有独立稳定 digest；任一未知依赖或跨分区边不明确，按共享/未知故障处理。resolver、实际权威 selector 和恢复审计逻辑属于 authority，不能归入可忽略的候选分区。

完整 shadow artifact 仍需全量一致才能批准新风险。仅 candidate 分区失败时，正常 constructor/opener/audit 的全量校验不能被偷偷放宽；必须另有固定、受限的 reference-settlement opener 和新的恢复审计种类（5.2）。参考/共享分区、runtime、契约或 writer 权限无法确证时，该入口也拒绝。D1 纯绑定不要求实现这些金融恢复入口；在 D2 实现并独立证明之前，它们保持 BLOCKED。

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
- 同一 valuation time 只固定参考/候选及同一决策 before/after 的数值，不替代最终准入时效检查。实验新风险在双算、审计和排队之后，原账户与 market 版本未变、原 fencing/precommit guard 仍成立的最终准入点，再采集 `admission_checked_at` 并用同一 snapshot 复核：`age <= max_age`、`age >= -max_future_skew`；当前参考 `MarketSnapshot.validate` 的 future-skew 默认1秒，等号允许。新契约归档 `admission_freshness={format:1,checked_at,market_snapshot_id,max_age_us,max_future_skew_us,check_result}`，版本/值精确固定。新契约另要求 checked_at 不早于本命令 captured evaluated_at；越界时钟回退或超过明确 future-skew 的报价拒绝。最终检查后仅完成其证据写入、原最终 writer guard 与 COMMIT，不再执行新计算或换市场；不能用重新取行情、重置 valuation time 或延长 TTL 修复已过期决策。记录的 checked_at 是 guard 时点，不是物理 COMMIT 证明。双算后超时拒绝新增风险，历史数值重放与时效验证结果分报。
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

新增风险路径遇到候选 unsupported、mismatch 或 binding drift，立即关闸并按5.3的持久顺序回滚原接纳/预占，完成冻结后才返回确定失败。不得使用“先回滚，随后尽力写冻结”的窗口。未取得确定回执的命令仍按原命令 ID 查询结果，不能盲目重提。

**已确认成交及其他必须履行的结算义务不能因 shadow 失败被丢弃。** 此时参考一直是声明的权威，不存在从候选临时切换；照原规则持久结算，同时记录 candidate 失败、停止新增风险并进入人工调查。撤单等不增加风险且无需新估值的路径继续执行。若当前服务无法区分新增风险与必须结算义务，首次同步 shadow 只能用于只读/离线验证，直到这一区分经过独立验收。

### 5.2 D2 阻断：操作可信来源、结算与重开矩阵

固定 PR52 `service.apply_fill`（923行）明确是**尚未对外执行的本地授权并结算**，不是外部确认成交摄入；其 projected risk（979附近）、audit-before（994附近）和 audit-after（1033行）都可能抛错。`storage._role_transaction` 对任意异常回滚；`matching.match_once` 将两侧 `_apply_fill` 与 match receipt 放在同一事务，整笔 COMMIT 后才返回确认，异常可回滚两腿和此前 batch。上述现有代码不能证明候选错误时已确认外部义务仍会入账，不能把本地返回名称 `FILL_CONFIRMED` 当独立撮合已先确认的证据。

新操作分类只能来自可信调用链和持久撮合义务，不接受客户 `mandatory=true`、运维临时 flag 或任意 fill ID 升权。未来 `settle_confirmed_obligation(obligation_id)` 必须只消费受 fencing/权限保护、不可改条款的持久义务；唯一来源成交 ID、两侧结算责任、费用/预占与完成状态在本地事务恰好一次关联。现有本地 matching 继续在确认前拒绝失败；要接受确认已先发生的义务，必须先实现新义务/摄入契约并独立验收，不能复用 `apply_fill` 冒充。

| 故障类别 | 新风险/未确认本地执行 | 已持久确认义务 | 查询、撤单与重开 |
| --- | --- | --- | --- |
| 完整可信、两算一致 | 仅通过全部原有门槛及最终行情检查后接纳 | 按原权威幂等入账 | 正常；完整重放仍匹配完整 artifact |
| **仅 candidate** 数值差异、超域、缺失或 binding 漂移；authority/shared/runtime/契约及权限独立确证 | 立即关闸；拒绝/回滚；本地尚未确认 matching 不得先宣布成交 | 固定参考权威处理；原费用、仓位、资金和预占一次性提交；独立恢复审计记录候选失败，不调用候选 audit-after 阻断入账 | reference-only 受限 opener 只提供确定义务、已确认撤单及标明 degraded 的查询；不提供新单/借款/划转/模式切换；不自动解冻 |
| reference、shared 模型/账务/runtime、authority binding 或 writer 权限不可信 | 拒绝，不能选择默认参考 | 保留义务/预占和结果未知状态，停止不可信金融写入；用受审精确参考制品恢复后查询原义务再履行，不能伪报已结算 | 受限 opener 也拒绝；仅可信读取层可报告“待恢复”，不得修复源或隐式升级 |
| 未知 contract/version、分区不清、来源义务不可信、无法证明只坏 candidate | 按未知权威拒绝 | 不把客户请求转成强制义务；保留已有可信义务，不释放预占、不宣称完成 | 不 fallback，不用 inner十字段绕过完整契约；需要明确恢复审查 |
| 控制/金融存储不可用、冻结提交失败或结果未知 | 持续关闸；不得把未落盘冻结称成功 | 保存已存在的持久义务；不能写账时保持 pending/unknown，恢复后按原 ID 查询 | 本地闸门不开放，重启默认关闭；不盲目重投业务影响 |

已知共享风险输入无报价/过期不属于 candidate-only；本阶段也不因此获得未经审查的结算降级能力。确认条款与结算账务不依赖当前行情的独立路径，必须单独明确其 risk-audit-pending 语义后验收；在此之前保留义务待恢复，不能宣称生产可用或强制结算完整性已过关。

新增 `open_existing_settlement_services` 是**待实现的封闭入口提案**：仅已知 shadow 契约、原 authority 分区与 fencing/schema/义务均可信时打开，绝不调用普通构造器去补表/补 archive/安装信用能力。candidate 单独不可用不要求伪造完整 artifact 相等；新恢复审计必须明确 scope 为 `reference_settlement_recovery_v1`，固定原契约、原完整 artifact 引用、authority digest、候选失败类别、义务 ID、原始/结果状态和账务关联。before/after 使用参考权威，不再进入会因候选失败回滚的原 audit-after。无法可靠执行参考审计则保持 pending，不能跳过全部审计后声称成功。

此类恢复记录的 replay 分别输出 reference 数值/账务结果、shadow 未复算/失败与 freshness/权限证据范围；不得把 reference-only replay 标为完整 shadow replay 成功。修复候选后仍须匹配完整原代码/规则/时间才能复算原候选结果。**这些入口、分区及恢复审计目前均未实现，EBD-FIN-001/EVG-006 继续 OPEN，D2 BLOCKED。**

### 5.3 D2 阻断：先持久关闸，再进入可失败的金融计算

为消除回滚到冻结的崩溃窗口，建议在同一账户数据库增加有限 `uta_valuation_gate` 状态（`OPEN/EVALUATING/FROZEN`），以已知 authority/account、fencing token、命令 ID、expected account version、gate revision 和失败摘要关联。不是另建服务；其写入必须受同一唯一 writer 和原控制/金融权限审查。D2 只支持单机，不声称跨分片原子性。

1. 调度器在账户 lane 中取得独占权，先检查全局/账户闸门。新风险只有 OPEN 可选择；结算义务与确认撤单使用不同可信队列类别，客户不能自标。已存在实验库重启/接管先经 authority-only 路径持久关闭新风险，再检查 candidate；未完成 EVALUATING 或已有 FROZEN 不能自动恢复 OPEN，不能把启动内存 latch 当持久关闭。未知库或 authority 不可信时完全拒绝，不能借恢复开新库。
2. **任何本次新增风险命令的 candidate 检查/双算前**，先用受信 authority 路径将该命令的 EVALUATING 意图独立持久提交，并 latch 本地新风险闸门；未持久成功不得开始金融事务。这个意图即使后续金融回滚也存在；不是回滚事务里的日志。账户 lane 不得在中间选择另一条新风险。
3. 金融事务校验 gate/command/account version/fencing 完全匹配，再捕获输入、计算、审计、检查最终 freshness。成功时，接纳回执、预占、账户变化和该命令 EVALUATING→OPEN **在同一金融事务提交**，提交确认后才释放本地 latch 并选择下条新风险。控制面另行冻结/版本变化必须使 CAS 或 precommit guard 失败。
4. 发现失败即保持 latch 关闭，然后回滚金融事务。原持久 EVALUATING 仍在，故进程即使此时终止也不会在重启漏掉关闸。再在独立受信事务将同一命令 EVALUATING→FROZEN，写入失败摘要及原命令的确定 `NOT_ADMITTED` 关联结果；两者提交确认后才返回确定 shadow 拒绝。这不等于现有 durable inbox 的业务 REJECTED，不能只因HTTP503就改写其 PENDING/技术重试协议；新实验契约的查询与队列阻断必须显式整合。冻结存储不可用时继续 fail-closed，返回可查询 UNKNOWN/服务不可用，不能返回“持久冻结成功”。
5. 恢复先查原命令、gate、接纳/预占及义务。原成功事务已提交应同时见到唯一成功与 OPEN；失败回滚或未开始事务则残留 EVALUATING，转换为受审冻结/恢复状态，不自动重算并批准。若成功与 gate 状态不一致，作为损坏拒绝；同 ID 永不生成第二影响。响应丢失只查原 ID。
6. 清理、必要结算和确认撤单不能被新风险 latch 一并丢弃；按5.2的可信类别恢复处理。解冻是独立受审控制操作，需完整 binding/存储/账务/未完成命令校验并记录操作者，不能因为候选下一次算对就自动开放。

上述冻结针对 shadow/绑定/未知技术失败；已明确完成完整可信估值的正常业务拒绝仍遵守原业务契约。它必须在无金融影响的已回滚状态下，将该命令的业务拒绝终态与 EVALUATING→OPEN 放在同一受信事务确认后，才选择下一条新风险。不能仅凭HTTP状态码把 engine故障当业务拒绝释放闸门；异常分类、CAS及回执丢失也须同等故障测试。未能确定类别的残留意图保持关闭。

崩溃边界必须逐一验收：意图写入前后、金融 BEGIN/比较/最终 guard 前后、成功 COMMIT 前后、失败回滚前后、FROZEN 提交前后、响应丢失、重启/接管与下一条排队新风险。断电/存储失败后重开验证无额外接纳、失败预占残留、重复分录或遗漏确认义务。`EVALUATING` 的存储/事务角色、幂等结果与既有 durable command savepoint/终态写入如何兼容尚未实现，不能把此处顺序当故障验证。**EBD-FIN-002/EVG-007 保持 OPEN；D2 BLOCKED。**

建议错误契约（未实现）：未知 opt-in 参数/engine 为 400 `valuation_contract_unsupported`；已有库不匹配为 409 `valuation_migration_required`；runtime/binding/持久 archive 缺失或不一致为 503 `valuation_binding_unavailable`；新风险 shadow 数值差异为 503 `valuation_shadow_mismatch`；超出实验支持域为 422 `valuation_domain_unsupported`。不得将这些错误转成成功的零结果、旧模式成功结果或无日志 fallback。业务已有错误契约须在实现 PR 中逐项映射，不能悄悄改变 409/超时/结果未知的重试语义。

## 6. 人工可复算案例

下面是本系统固定测试规则，不是外部交易所保证金政策。第一至三例沿用已公开人工样例，第四例是服务集成必须人工验证的合成费用/预占例；全部要求独立验证组复算。

1. **Gross debt 与折扣，M02。** BTC=2，价格100，抵押因子0.8，LTV0.5；本金1.25 BTC、利息0.05 BTC；borrow IM/MM=0.1/0.05。原始资产200，债务130；会计权益70；抵押160；风险权益30；loan value80；IM13，MM6.5，可用17，可借0。不能先净成0.7 BTC再折扣；利息不能被藏入本金。
2. **冻结、分层与组合，M01（纯模型，不是 multiplier=1 服务用例）。** USD1000+BTC2@100；冻结BTC0.5；BTC首100抵押0.8、其后0.5，故 BTC 抵押105、总抵押1105；USD/BTC LTV分别0.8/0.5，loan value852.5。本金USD100+BTC0.1=110，利息USD1+BTC0.01=2。线性 q2、multiplier2、mark110、cost400，PnL40。会计权益1128，风险权益1033。USD borrow IM/MM0.1/0.05、BTC0.2/0.1、线性0.1/0.05，IM=101×0.1+11×0.2+440×0.1=56.3，MM28.15。order10，可用966.7。总债务上限500时单独 USD quote388、BTC quote3.88；**二者不是可叠加的同时授权**。
3. **MM 等号，M09。** USD11，抵押/LTV=1，借款IM=MM=0.1，step1，上限100。这是**借款所得立即离开抵押品的保守 quote**：quote10对应压力权益1等于MM1，故拒绝，最大quote9；USD11.01 对应1.01>1，quote10可以通过这一边界。它不是借款现金仍记到账内时的实际 post-borrow equity，也不是借款授权；其他限额仍要独立满足。零权益/零MM同样是清算边界，不能因分母零返回安全。
4. **费用与存量预占，EBD-M04。** USD100，线性数量1、limit/mark/fill均100、multiplier1，IM0.1/MM0.05，fee0.0004，USD最小单位0.01，且无其他资产、债务、订单、义务或费用。成交0.5收0.02，现金99.98、仓位0.5/cost50。剩余原单预占5.02；新 reduce-only0.5在同价位还须保留fee0.02，合计order margin5.04。当前IM5、MM2.5、available89.94。**RO已确认完全成交、其自身fee reserve终结后**现金99.96、仓位0、原单reserve5.02，可用94.94；若某个成交前投影仍保留该RO fee reserve0.02，则可用94.92，不能标成同一逻辑时点。实际测试必须使用现有 cumulative-fee 和 reserve 函数的受审规则并由独立组复算；若前置假设不成立则拒绝此 fixture，不能改期望迎合实现。

多次部分成交的累计费用进位、signed cost dust、负现金、同币资产/债务、冻结原因与 reserve 取整必须分别保留。候选只替换估值计算，不重写资金最小单位、成交费用累计进位或原 admission 投影。

## 7. 精确实施位置与验收分期

| 阶段 | 最小改动位置 | 验收后可以做什么 |
| --- | --- | --- |
| D0 静态设计（本提交） | 本文、machine contract、source evidence | 仅审查，不运行目标 |
| D1 纯绑定 CODE（可另审，无执行GO） | 提案 `uta/risk_engine_binding.py` 与 bounded pure contracts；不接 service/DecisionAudit/DB；后续数值验证保持独立 oracle 不复用生产核心 | 先独立审源与新 inventory/执行计划；本文不批准目标 import/测试或金融 authority |
| D2 新建库同步 shadow：**BLOCKED** | `ExchangeService.__init__/_risk/_policy_versions`；`DecisionAudit` policy/install/replay及受限恢复审计；`existing_services._source_arguments`、exchange-only/settlement opener；持久gate与可信义务入口；Credit V2 显式拒绝 | 规格已细化但未实现/未验收；EBD-FIN-001/002、EVG-003..007与EBD-001..012全部取得所需证据前只读/离线，不授GO |
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

金融组与独立组已对原53ace的 D0 边界作静态审查；这不是新实现数值签字、D2缺口关闭或上线审批。修订2的新增规格尚待再次审阅。没有伪签名、目标执行 GO 或生产验收。
