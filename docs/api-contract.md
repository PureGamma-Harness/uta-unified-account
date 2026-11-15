# UTA 内部 API 契约

0.3.0a1 保持原路由与资金契约。可选的两项纯计算缓存由服务启动配置控制，默认关闭；没有客户可设置缓存、跳过风控或清理持久预占的接口。`GET /metrics` 对 risk/admin 增加 `risk_cache.reserve` / `risk_cache.market` 诊断字段，不返回缓存键、订单内容或原始行情；其容量/命中/淘汰/解码失败属于进程指标，不是金融回执。

新增 `RouterAdmissionBatcher` 是本地主机 Python 接口，不在这里暴露分片 HTTP/WS；同实例片内 FIFO 与 COMMIT 回执语义见 [分片准入契约](shard-admission.md)。

这份契约对应 `uta.gateway` 与持久化交易服务。API 只监听 IPv4 loopback；远程访问必须经过 TLS 反向代理，并配置连接与速率限制。`python -m uta serve` 仍是独立的无认证演示接口，不属于这里的 `/v1` 交易接口。

当前支持线性 USD 结算合约的账户、保证金占用、订单、本地双边撮合及结算、风险监督和持久化事件查询；配置相应组件后还提供资金池借贷、利息记账、还款和 USD 报价现货撮合。完整 PM、期权保证金、外部交易所成交回报接入、WebSocket 推送、HMAC 请求签名及 nonce 防重放没有在此接口实现。行情新鲜度、交易开关与风险检查不等于真实交易所的生产验收。

## 认证与权限

除 `GET /healthz` 外，所有接口要求 `Authorization: Bearer <token>`。令牌用 `secrets.token_urlsafe(32)` 等密码学随机源单独生成，不出现在 URL、命令行参数或日志中。网关不设置 CORS，也不使用浏览器 cookie 认证。

凭据文件是 JSON 数组，必须由服务用户拥有、禁止组和其他用户访问，且是非符号链接的普通文件。推荐权限 `0600`：

```json
[
  {"token": "<independently-generated-admin-token>", "role": "admin"},
  {"token": "<independently-generated-risk-token>", "role": "risk"},
  {"token": "<independently-generated-funding-token>", "role": "funding", "account_id": "alice"},
  {"token": "<independently-generated-trader-token>", "role": "trader", "account_id": "alice"},
  {"token": "<independently-generated-reader-token>", "role": "reader", "account_id": "alice"}
]
```

这里的占位文本不能作为实际令牌使用。未知角色、未知配置字段、重复 JSON key、重复令牌和缺失账户绑定均在加载时拒绝。

| 角色 | 账户范围 | 允许的操作 |
| --- | --- | --- |
| `reader` | 必须绑定一个账户 | 读取自身账户、风险、订单、事件；读取 readiness |
| `trader` | 必须绑定一个账户 | reader 的操作，以及自身提交订单、撤单 |
| `funding` | 必须绑定一个账户 | 自身入金、借款、还款记账；读取 readiness；不具备账户查询、交易或行情修改权限 |
| `risk` | 不绑定单个账户 | 任意账户的只读诊断、事件、metrics、成交审计；发布行情、配置信用限额、设置全局交易开关、运行账户风险监督 |
| `admin` | 全部账户 | 所有接口，包括账户引导与本地成交授权；应减少日常使用 |

入金及资金池注资权限表示可信资金凭据的记账权限，不能用客户提供的未经核实记录代替真实资金对账。应用须显式挂载 `exchange.credit=CreditService(exchange)`、`exchange.matcher=Matcher(exchange)`；现货还需要 `exchange.spot=SpotExchange(exchange,catalog)`。未配置所需组件时，已授权的请求返回 `501 feature_unavailable`，不会临时创建组件或假造结果。越权请求先返回 `403`，不披露组件是否存在。

同一账户可以配置多个不同令牌。轮换时，先同时装载旧、新令牌，验证新令牌后移除旧令牌。Python 服务集成可调用 `server.replace_credentials(credentials)` 原子替换；无效替换保留原配置。已经完成认证的请求继续执行，后续认证采用新配置。HTTP 没有修改令牌的接口；仅修改配置文件不会自动热加载，CLI 部署需要按运维流程重启或显式接入加载器。

Bearer 本身不阻止令牌被盗后的请求重放。下文的业务幂等键可阻止同一业务事件重复生效，不能代替 HMAC、nonce、令牌过期机制和上游访问控制。

## 可选分组持久接纳

`exchange --batch-admission` 显式开启单个本地账户库的分组接纳。原有单订单和撤单路由、权限、十进制字符串及业务 ID 保持不变；没有新增可将一组客户订单视作原子多腿操作的 bulk 接口。多个独立 HTTP 命令可能共享一次 `WAL/FULL COMMIT`，每条命令仍按队列顺序重新检查最新权威状态。预期业务拒绝只回滚该条命令；存储、提交或未知程序故障会使整批回滚或进入结果未知处理。

服务不会在命令入队或事务尚未 COMMIT 时发送接纳/预占成功。HTTP 等待时间由 `--admission-timeout` 控制，默认 2 秒，范围 `.001..60` 秒；这不是数据库事务取消机制：

- `503 admission_queue_timeout`：等待截止时 Future 仍可取消，命令尚未开始执行，没有该次请求的业务影响。保留原 ID 重试。
- `503 command_result_unknown`：命令已经开始，等待超时不能取消已执行或将要提交的操作。通过原账户/订单 ID 查询或原 ID、原内容重试；不能用新 ID 重新下单，也不能把当时的 `404` 视作最终拒绝，因为原命令可能仍在提交。
- `503 admission_overloaded`：有界队列已满，该次调用未入队；上游退避并使用原业务 ID。
- `503 admission_closed` 或 `admission_batch_failed`：组件已关闭或批处理遇到技术故障。后者不保证事务未提交，例如 COMMIT 已完成但回执发布失败；核对原 ID，不能当作业务风险拒绝。

权限、账户边界、字段类型校验在入队前执行。被拒的跨账户请求不会占用批处理队列。spot、借贷、撮合和风险控制目前继续使用自己的权威事务，不会自动进入此订单/撤单队列。

待执行普通接纳最多 `queue_capacity` 条；撤单还有默认 16 个额外保留槽（`--admission-cancel-reserve 0..4096`），总待执行数不超过二者之和。保留槽不使撤单越过已经排队的命令，也不保证该负载下的固定撤单延迟。满普通队列时撤单仍可入队，满总队列时同样返回过载。

`GET /metrics` 的 risk/admin 结果增加 `admission` 聚合计数，不含完整命令或凭据。配置了批处理器而其 worker 不存活或不再接收时，`GET /readyz` 返回 `503`、`admission_reason=admission_unavailable`。队列过载由单次 `503` 表示，不将短暂队列满视为全部资金操作不可用。

## 请求与响应

- 所有 POST/PUT 使用 `Content-Type: application/json` 和 `Content-Length`，正文最大 64 KiB。撤单和监督操作也需要 JSON 空对象 `{}`。
- 金额、数量、价格均为十进制字符串，例如 `"0.01"`；禁止浮点 JSON 数字、NaN、Infinity、重复对象 key、未知业务字段及多份 JSON 文档。
- 数量带符号：正数买入、负数卖出；订单数量必须非零，价格和入金金额必须为正数。`reduce_only` 和 `enabled` 是 JSON boolean，不能用字符串或整数代替。
- 基础交易服务当前限制输入金额/数量/价格最多 8 位小数、绝对值不超过 `1e12`；资产记账还必须符合部署时配置的精度。USD scale 是 2 至 8。实际成交费用按订单累计成交金额计算并向 USD 最小单位向上取整，部分成交只记累计费用的差额；风险预留采用保守取整。
- 账户、订单、入金事件和成交 ID 是 1 至 128 个 ASCII 字符，第一位为字母或数字，其余可用字母、数字、`.`、`_`、`:`、`-`。路径 ID 不接受百分号编码。资产和合约代码可以额外含 `/`，在 JSON 字段中传入。
- `liq:` 开头的订单 ID 保留给风险监督器，客户不能提交该前缀；公共撤单接口也不能撤销这些订单，风险监督器在同一事务中管理其取消与重建。
- 响应直接返回 JSON 对象或数组，不额外包裹 `data`。财务数值仍是字符串，时间带时区，版本/序号是整数。响应带 `Cache-Control: no-store`，每次请求处理后关闭连接。

## 路由

表中的 `{account_id}`、`{order_id}` 是实际 ID。`reader/trader` 的账户访问仅限凭据绑定账户；`risk/admin` 的诊断访问可选择任意账户。

| 方法与路径 | 请求正文或查询 | 权限 | 成功响应 |
| --- | --- | --- | --- |
| `GET /healthz` | 无 | 公开 | `200 {"status":"ok"}`，只证明进程可应答 |
| `GET /readyz` | 无 | 任意有效凭据 | `200` 或 `503`，对象含 `ready`、`reason`；正常行情存在时还含 `halted`、`market_version` |
| `GET /metrics` | 无 | risk/admin | `200`，网关请求、客户端错误、服务错误及连接拒绝计数；挂载自动化 worker 时附 `worker` 最近报告 |
| `POST /v1/accounts` | `{"account_id":"alice"}` | admin | `201`，账户对象 |
| `GET /v1/accounts/{account_id}` | 无 | reader/trader/risk/admin | `200`，账户对象 |
| `GET /v1/accounts/{account_id}/risk` | 无 | reader/trader/risk/admin | `200`，风险对象，要求新鲜行情 |
| `GET /v1/accounts/{account_id}/orders` | 无 | reader/trader/risk/admin | `200`，该账户订单数组，包含终态订单 |
| `GET /v1/accounts/{account_id}/orders/{order_id}` | 无 | reader/trader/risk/admin | `200`，原订单 ID 的当前对象；行情过期仍可重查 |
| `GET /v1/accounts/{account_id}/events` | `after=0&limit=100` | reader/trader/risk/admin | `200`，按该账户过滤的事件数组 |
| `GET /v1/events` | `after=0&limit=100` | reader/trader/risk/admin | reader/trader 只返回绑定账户事件；risk/admin 返回全局事件 |
| `POST /v1/accounts/{account_id}/deposits` | `{"event_id":"d1","asset":"USD","amount":"1000"}` | funding/admin | `200`，入金后的账户对象 |
| `POST /v1/accounts/{account_id}/loans` | `{"command_id":"loan1","asset":"BTC","amount":"1"}` | funding/admin | `200`，实际资金池放款及总负债结果 |
| `POST /v1/accounts/{account_id}/repayments` | `{"command_id":"repay1","asset":"BTC","amount":"1"}` | funding/admin | `200`，使用可用现货现金还款后的本金、利息及分配明细 |
| `POST /v1/accounts/{account_id}/interest` | `{"command_id":"interest1","asset":"BTC","amount":"0.001"}` | admin | `200`，明确利息事件记账结果；不会推断利率或自动复利 |
| `PUT /v1/accounts/{account_id}/credit-limits` | `{"asset":"BTC","limit":"10"}` | risk/admin | `200`，首次设置不可变账户总负债限额；修改已设值返回 409 |
| `PUT /v1/credit/asset-limit` | `{"asset":"BTC","limit":"100"}` | risk/admin | `200`，首次设置不可变资产合计总负债限额 |
| `POST /v1/credit/pool` | `{"command_id":"capital1","asset":"BTC","amount":"100","source_reference":"capital:line1"}` | admin | `200`，经过外部对账确认的池资金记账结果 |
| `POST /v1/accounts/{account_id}/orders` | `{"order_id":"o1","symbol":"BTC-PERP","quantity":"0.1","limit_price":"21000","reduce_only":false}` | trader/admin | `201`，原子保证金检查及占用后的订单对象 |
| `POST /v1/accounts/{account_id}/orders/{order_id}/cancel` | `{}` | trader/admin | `200`，订单当前对象；本地撤单只释放剩余占用 |
| `POST /v1/accounts/{account_id}/orders/{order_id}/fills` | `{"fill_id":"f1","quantity":"0.05","price":"20990"}` | admin | 仅 legacy reference 模式可返回 `200`；配置产品目录时返回 `409 paired_execution_required`，须用真实双边撮合 |
| `GET /v1/accounts/{account_id}/spot-orders` | 无 | reader/trader/risk/admin | `200`，账户现货订单数组 |
| `POST /v1/accounts/{account_id}/spot-orders` | `{"order_id":"s1","symbol":"BTC-SPOT","quantity":"1","limit_price":"100"}` | trader/admin | `201`，实际锁定现货资产后的订单对象；没有 reduce_only 参数 |
| `POST /v1/accounts/{account_id}/spot-orders/{order_id}/cancel` | `{}` | trader/admin | `200`，终止剩余现货订单并释放剩余资产锁 |
| `POST /v1/matching` | `{"symbol":"BTC-PERP","max_matches":100}` | admin | `200`，实际双边线性撮合结果及持久化成交回执 |
| `POST /v1/spot-matching` | `{"symbol":"BTC-SPOT","max_matches":100}` | admin | `200`，实际双边现货撮合及资产交割回执 |
| `GET /v1/trades` | `after=0&limit=100` | risk/admin | `200`，有界的全局线性撮合回执审计数组；不包含现货回执 |
| `POST /v1/accounts/{account_id}/supervise` | `{}` | risk/admin | `200`，风险监督结果；不接受客户端指定平仓数量、价格或风险结论 |
| `PUT /v1/market` | 下方完整行情对象 | risk/admin | `200 {"version":1,"observed_at":"..."}` |
| `PUT /v1/kill-switch` | `{"enabled":true}` | risk/admin | `200 {"enabled":true}` |

`/readyz` 在全局暂停、行情缺失/过期或存储不可用时返回 `503`。这不是禁止所有安全操作的总开关：撤单、资金补充和符合检查的只减仓仍可能允许。新数据库的全局交易开关默认开启，即暂停新增敞口；恢复后保持持久化开关状态。

若挂载 `exchange.worker`，其最近报告为 `not_started` 或全局 `worker_failure` 时 readiness 也返回 `503`，并通过 `worker_reason` 指明原因。单个账户或订单的 `blocked` 不单独导致全局不可用。客户 readiness 响应不包含其他账户的计划或阻断详情；完整最近报告仅在 risk/admin 的 metrics 中可见。未挂载 worker 时保持基础存储、行情和交易开关检查。

行情输入示例：

```json
{
  "version": 1,
  "observed_at": "2026-11-14T14:00:00+00:00",
  "assets": {"USD": {"price": "1", "collateral_factor": "1"}},
  "instruments": {
    "BTC-PERP": {"mark_price": "21000", "initial_margin_rate": "0.1", "maintenance_margin_rate": "0.05"}
  }
}
```

发送时必须替换成实际新鲜观测时间。基础交易服务默认最大行情年龄 5 秒、最大未来偏差 1 秒；版本和观测时间均不得倒退，同一版本不得更换内容。USD 价格和折扣因子必须均为一，合约保证金率必须为正。不能移除仍有余额、负债、持仓或挂单依赖的行情规格。

## 核心响应字段

账户对象包含 `account_id`、`version`、`balances`、`positions`、`open_order_margin`、`liabilities`。持仓按合约代码索引，包含带符号 `quantity`、展示用 `entry_price` 和用于精确盈亏计算的 `cost_basis`。负债按资产分开保存 `principal`、`interest`、`total`，不先与同资产余额净额化。

风险对象包含 `account_version`、`market_version`、`observed_at`、`equity`、`initial_margin`、`maintenance_margin`、`open_order_margin`、`available_margin` 和 `margin_ratio`。无维持保证金时 `margin_ratio` 为 `null`。账户与行情版本用于识别观测依据；先查询再提交不是事务，新订单仍由服务在数据库写事务中重算。

订单对象包含 `account_id`、`order_id`、`symbol`、`quantity`、`limit_price`、`reduce_only`、`filled_quantity`、`status`、`version`、`created_at`、`reserved_margin`。状态为 `OPEN`、`PARTIALLY_FILLED`、`FILLED` 或 `CANCELLED`。只有明确提交成功或重查确认才可认定订单已被接受；保证金占用不代表已经成交。

现货订单单独使用 `(account_id, order_id)` 命名空间，包含 `base_asset`、`quote_asset`、`reserved_asset`、`reserved_amount` 等资产锁字段。正数量买入、负数量卖出；买单锁定报价货币及预期费用，卖单锁定基础资产，匹配后实际交割两种资产。还款和其他现货订单不能重复使用已锁现金。撤单只能释放剩余锁，不能回滚已交割部分。

借款必须有实际已记账的资金池流动性、明确的账户与资产总限额，以及新鲜行情下通过的总负债风险检查；不会因为余额不足自动借款。本金与利息分开记账、按足额负债估值。还款优先支付利息，再偿还本金；不能超过欠款或使用已锁现金，交易暂停时仍可进行。信用配置限额允许零来禁用新借款，首次设置后只能相同值重试，不能用 PUT 静默覆盖。

撮合调用的 `max_matches` 是 `1..1000` 的 JSON 整数，可省略，默认 100。结果包含 `confirmed_trades`、`trades`、`cancelled_orders`、`blocked`；只有实际对手方订单同时通过检查、双边结算和回执一起提交后，才增加成交数。单边或未交叉订单簿不会按标记价造出成交；瞬时风险门禁可能通过 `200` 结果中的 `blocked` 报告。全局回执包含对手账户身份，仅 risk/admin 可查询；客户从自身事件读取成交。`/v1/trades` 的 `after/limit` 按撮合回执自己的递增 `sequence` 分页，与事件 cursor 相互独立。

监督结果包含 `account_id`、`state`、`cycle`、`revision`、`created_orders`、`cancelled_orders`、`replanned`；新鲜行情下还返回 `market_version` 和账户版本依据。`state` 为 `NORMAL`、`LIQUIDATING`、`BLOCKED` 或 `BANKRUPT`。行情不可用时返回 `BLOCKED`，并保留已有计划。`created_orders` 是本地只减仓订单，不是成交证明；后续撮合和账务事件才证明执行。`BANKRUPT` 状态本身不代表已完成保险基金赔付或 ADL。

事件对象包含 `sequence`、`event_type`、`account_id`、`payload`、`created_at`。`after` 为排他的全局序号，允许 `0..2^63-1`；`limit` 为 `1..1000`。客户查询在数据库中先按账户过滤，再应用 limit；序号存在间隙是正常行为，不会包含其他账户或全局控制事件。处理完一页后保存最后一条的 `sequence`；空页保持原 cursor 并稍后重试。当前是 HTTP 拉取，没有 WebSocket 或推送交付保证。

## 幂等、重试与响应丢失

幂等键是业务正文中的 ID，不是一个通用的 `Idempotency-Key` HTTP header。客户端在首次发送前持久化 ID 与完整业务内容，重试时保持两者不变。

| 操作 | 幂等身份 | 相同身份重试的行为 |
| --- | --- | --- |
| 新建账户 | `account_id` | 返回该账户当前状态，不重复开户 |
| 入金 | `(account_id, event_id)` | 相同资产、相同规范数值不重复记账；内容不同返回 `409 idempotency_conflict` |
| 提交订单 | `(account_id, order_id)` | 同合约、数量、限价、reduce_only 返回该订单当前状态；终态 ID 不重新打开；内容不同返回 409 |
| 本地成交授权 | `(account_id, fill_id)` | 同订单、数量、价格不重复成交、扣费或记盈亏；换订单或内容返回 409 |
| 现货订单 | 现货命名空间的 `(account_id, order_id)` | 同合约、数量、限价返回当前状态；终态不重开；不同内容返回 409 |
| 借款、还款、计息 | 共享的 `(account_id, command_id)` | 同一操作类型及规范内容返回已存记账结果；换类型或内容返回 409，不得跨方法复用 ID |
| 资金池注资 | 全局池 `command_id`，另对 `source_reference` 唯一约束 | 同内容重试不重复注资；换命令 ID 复用同一外部凭据行仍返回 409 |
| 信用限额设置 | 账户/资产或全局资产配置身份 | 同值重试不增加事件；不同值返回 `configuration_conflict` |
| 双边撮合批次 | 每次实际成交的持久化 trade ID | 不重放已结算双边成交；再次调用可以撮合剩余或新到订单，不保证返回同一批次结果 |
| 撤单 | `(account_id, order_id)` 的当前状态 | 重复撤单返回当前终态，不重复释放占用，也不撤销已成交部分 |
| 行情发布 | 全局 `version` | 同版本同规范内容不重复发布；不同内容返回 `market_conflict`；过期或倒退输入仍拒绝 |
| 交易开关 | 目标 boolean | 重复设置同一状态不产生额外状态变化 |
| 风险监督 | 服务持久化的 cycle/revision/账户与行情依据 | 同一已存在计划不重复建仓；行情、持仓或风险变化可触发重新评估和新计划 |

同一数值的 `"1.0"` 和 `"1.00"` 按服务规范化后比较。订单、入金和成交的已成功重试不依赖新鲜行情重新产生副作用；查询响应可以反映后续状态，并非原始响应字节的缓存。

如果请求超时、连接断开或响应丢失，结果是未知状态。用原 ID 和原内容重试；也可通过账户、订单及事件查询核对，不能改用新 ID 再提交一次。对于取消与成交并发，数据库事务决定本地先后：已取消的剩余订单不再接受新成交，已成交部分保留。

配置产品目录时，REST `fills` 被 `paired_execution_required` 拒绝，即使持有 admin 令牌也不能通过它建立单腿成交；真实撮合器在同一事务内检查和结算双方。仅 legacy reference 兼容模式中的 `fills` 是**本地执行之前的原子授权及结算命令**，会再次检查订单终态、数量、限价、只减仓约束、行情和风险。它不是接收“外部交易所已经不可逆成交”的回报接口。不能先在外部执行，再期待该命令一定成功。对外交易需要独立的持久化发送、未知结果对账和回报接入协议。

## 错误

常规错误结构为 `{"error":{"code":"insufficient_margin","message":"..."}}`。程序按 HTTP status 和 `code` 处理；`message` 只供诊断，不能解析其文本作业务判断。内部异常固定为 `500 internal_error`，不返回堆栈或存储路径。并发连接已满时可直接返回空正文 `503`，客户端不能假设所有失败均有 JSON 正文。

| HTTP status | 主要 code | 含义与客户端处理 |
| --- | --- | --- |
| `400` | `invalid_json`、`invalid_fields`、`invalid_decimal`、`invalid_identifier`、`invalid_input`、`invalid_market`、`invalid_query` | 修正输入；不要无限重试同一无效内容 |
| `400` | `invalid_framing`、`duplicate_header`、`invalid_host`、`unexpected_body`、`truncated_body`、`invalid_path`、`invalid_http` | 请求协议无效；禁用 chunked/重复长度并检查代理转发 |
| `400` | `unknown_asset`、`unknown_instrument` | 资产未配置或合约不在可信行情中 |
| `401` | `unauthorized` | 令牌缺失或不匹配；不得在错误日志中打印令牌 |
| `403` | `forbidden` | 角色或账户范围不允许操作 |
| `404` | `not_found`、`account_not_found`、`order_not_found` | 路由或已授权账户资源不存在 |
| `408` | `request_timeout` | 请求正文读取超时；已送出的业务请求须按原 ID 核对 |
| `409` | `idempotency_conflict`、`market_conflict`、`market_regression`、`configuration_conflict`、`duplicate_external_reference` | 身份内容冲突、重复注资凭据、限额配置冲突或行情倒退，需调查来源 |
| `409` | `trading_halted`、`account_frozen`、`insufficient_margin`、`unsafe_reduction`、`reduce_only_violation` | 风险或运营门禁拒绝；重算状态，避免绕过门禁改大权限重试 |
| `409` | `order_closed`、`invalid_fill`、`paired_execution_required`、`liquidation_order_protected`、`order_limit`、`position_limit`、`precision_error`、`ledger_rejected` | 订单状态、执行、数量或账务精度不满足约束；配置产品使用真实双边撮合，受保护清算单由风险监督器管理 |
| `409` | `credit_disabled`、`credit_limit`、`credit_pool_empty`、`insufficient_cash`、`no_principal`、`repayment_exceeds_debt` | 信用门禁、流动性、可用现金或债务余额不满足要求 |
| `411` / `413` / `415` / `417` / `431` | `length_required`、`body_too_large`、`unsupported_media_type`、`unsupported_expectation`、`headers_too_large` | 修正 HTTP framing、长度、正文类型或请求头 |
| `500` | `internal_error` | 服务故障，保存业务 ID 并核对结果；不要根据内部错误猜测请求未生效 |
| `501` | `feature_unavailable` | 该部署没有挂载请求所需的信用、现货或撮合组件 |
| `503` | `storage_unavailable`、`market_unavailable`、`market_incomplete`、`schema_version`、`invalid_clock` | 可用性或可信输入不满足条件；退避、修复依赖并保留原业务 ID |

未支持的 HTTP 方法通常返回 `501 invalid_http`。`503 /readyz` 的对象结构和过载连接的空正文是上述错误结构的例外。新增服务能力可以扩展业务 code；客户端须对未知 code 保持失败处理，不能默认为成功。
