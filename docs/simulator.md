# 本地运行与 API

本页对应 `python -m uta lab` 的持久化模拟器。模块与事务边界见 [架构](architecture.md)，导入、成交、清算和回放图见 [关键业务流程](workflows.md)。`python -m uta serve` 的 `/risk`、`/order-check` 是另一套无状态固定费率示例，不能用来提交模拟账户命令。

## 产品与数据

模拟环境支持 USD、BTC、ETH 余额与负债，BTC-PERP 和 ETH-PERP 线性合约。资产以 USD 估值，USD 固定为 1。命令数值为十进制字符串，最多 12 位整数和 6 位小数，数量步长为 0.000001。资产价格与合约标记价由操作者或测试驱动提交，成交由命令显式注入，没有盘口撮合。行情年龄超过五分钟或在未来时标为 STALE，拒绝开单、成交及单独清算；可以撤单或刷新完整行情，也可以用 `mark_and_liquidate` 更新行情并清算。恰好五分钟仍在有效范围内。

假设配置随版本固定。首次导入经典账户时，输入应是完整一致的 spot、margin、futures 快照。适配器保留原始账户 ID、版本和摘要，拒绝旧快照、未来快照、未知产品和没有委托证据的冻结余额。导入只创建新模拟账户，经典快照 schema 缺少订单明细，不能推断原账户没有挂单。

## 运行接口

启动 `python -m uta lab --db data.sqlite3`。服务监听 `127.0.0.1:8765`，包含 Host/Origin/浏览器来源检查、64 KiB 请求体上限和默认最多 64 个活动请求。POST 使用 `Content-Type: application/json`，字段须与对应信封及命令完全匹配，重复 JSON 字段会被拒绝。服务没有用户身份认证，适用于本机模拟。

账户和命令 ID 为 1–64 个 ASCII 字母、数字、点、下划线或连字符，首字符须为字母或数字。`expected_version` 是 JSON 整数，金额和数量是字符串。新账户从版本 0 开始，每个成功的新命令递增一次；幂等重试与拒绝不会增加版本。

| 方法 | 路由 | 请求或结果 |
| --- | --- | --- |
| GET | `/` | 交易台 |
| POST | `/v1/bootstrap` | `{"account_id":"demo"}` |
| POST | `/v1/import-classic` | `{"account_id":"demo","snapshot":{...}}` |
| GET | `/v1/accounts/demo` | 当前状态、PM 明细、账户状态 |
| POST | `/v1/accounts/demo/commands` | `{"command_id":"my-command","expected_version":0,"command":{...}}` |
| POST | `/v1/commands/batch` | `{"items":[{"account_id":"demo","command_id":"c1","expected_version":0,"command":{...}}]}`。每条独立回执，最多 100 条。 |
| GET | `/v1/accounts/demo/events` | 审计事件与分录 |
| GET | `/v1/accounts/demo/replay` | 捕获一致版本的快照与历史，重算并比较每条回执 |

`replay` 的 `version` 是本次读事务捕获并核对的账户版本，`events_verified` 包含版本 0 创世事件。读取结束后其他命令可以继续提交，因此成功结果不承诺返回时仍是最新版本；后续提交由下一次回放核对。检查使用原命令的 `evaluated_at`，完整事务范围与不一致错误见 [审计回放](workflows.md)。

回放先核对创世事件的元数据、命令形状和回执，再校验并重算后续命令。后续事件复用提交入口的 `_prepare` 校验：未知或非字符串命令类型、多余或缺失字段、无效命令 ID 均拒绝，不会作为成交继续处理。命令类型或字段不符报 `unrecognized command or incorrect fields`，ID 不符报 `IDs require 1–64 ...`，均为 `SimulatorError`，HTTP 返回 400。版本 0 缺失、创世元数据不符、版本不连续、重算回执或最终快照不同也按 `SimulatorError` 拒绝。

后续回执和快照比较保留 JSON 类型差异：版本整数 `1` 改为 `true` 或 `1.0`、布尔 `liquidation_pending=false` 改为数字 `0`，均不能算作一致。对象键顺序和空白变化可接受。检查不修复记录、不写入账户或事件。

存储层读取快照、命令和回执时先拒绝重复字段（含嵌套对象和转义后相同的键）、`NaN`、正负 `Infinity` 及解析后溢出为无穷的数值。例如已存回执 `{"version":999,"version":0}` 不会按最后一个版本 0 接受。上述非法记录由 [_decode](../uta/store.py) 抛出 `StoreError`，HTTP 返回 503；不能编码为有限存储 JSON 的对象也按存储错误处理。金额字符串及合法有限值仍按原规则读取，不自动修复记录。错误映射见 [Handler._handle](../uta/server.py)。

以下每行分别是一条命令的 `command` 对象，调用 `/commands` 时还须提供命令 ID 和预期版本：

```jsonl
{"type":"place_order","symbol":"BTC-PERP","quantity":"0.9","limit_price":"60000","fee_rate":"0.001"}
{"type":"fill_order","order_id":"entry","quantity":"0.9","price":"60000"}
{"type":"cancel_order","order_id":"resting"}
{"type":"set_prices","prices":{"USD":"1","BTC":"40000","ETH":"2100"},"marks":{"BTC-PERP":"40000","ETH-PERP":"2100"}}
{"type":"liquidate"}
{"type":"mark_and_liquidate","prices":{"USD":"1","BTC":"40000","ETH":"2100"},"marks":{"BTC-PERP":"40000","ETH-PERP":"2100"}}
```

订单数量带方向。买单为正数，卖单为负数。成交数量为正数，方向继承订单。订单 ID 是下单命令 ID。版本冲突返回 409；须重新读取状态并重新评估新的业务请求。对于响应丢失的命令，使用原 ID、版本及请求重试，读取已提交的结果。过载时可收到 503 和 Retry-After。

在刚创建的空仓账户中，完整下单信封如下。下单只建立 OPEN 订单，不会自动成交：

```json
{
  "command_id": "entry",
  "expected_version": 0,
  "command": {
    "type": "place_order",
    "symbol": "BTC-PERP",
    "quantity": "0.01",
    "limit_price": "60000",
    "fee_rate": "0.001"
  }
}
```

回执版本为 1 时，可使用新的命令 ID 显式记录成交：

```json
{
  "command_id": "fill-entry",
  "expected_version": 1,
  "command": {
    "type": "fill_order",
    "order_id": "entry",
    "quantity": "0.01",
    "price": "60000"
  }
}
```

创建、下单和成交应在行情有效期内依次执行；账户已有命令时，先读取实际版本。完整执行校验位于 [Simulator._prepare / _transition](../uta/simulator.py)，HTTP 信封位于 [Handler._post](../uta/server.py)。

| 命令 | 主要条件和效果 |
| --- | --- |
| `place_order` | 健康且行情有效，数量非零、费用率 0–1%，最多 100 个 OPEN 订单；预占后可用保证金非负 |
| `fill_order` | 健康且行情有效，成交前全部预占充分，数量不超未成交量、价格不突破限价；FIFO 更新后再次检查 PM |
| `cancel_order` | 订单须仍为 OPEN；允许在 STALE、BREACH、INSOLVENT 时撤单 |
| `set_prices` | `prices` 和 `marks` 须完整覆盖已配置产品，数值为正、USD 为 1，时间不得倒退；更新本身不自动清算 |
| `liquidate` | 行情有效且低于健康门槛；先撤挂单，再在后续命令模拟减仓 |
| `mark_and_liquidate` | 完整更新行情并在同一账户事务中推进最多 8 次清算动作 |

## 状态、错误与重试

| HTTP 状态 | 语义与处理 |
| --- | --- |
| 200 / 201 | 查询或命令成功；经典账户导入返回 201，普通建户返回 200 |
| 400 | 请求形状或业务条件不满足；检查错误信息，已拒绝命令没有成功回执 |
| 403 | Host、Origin 或浏览器来源校验失败 |
| 404 | 路由或账户不存在 |
| 409 | 账户已存在、版本不匹配，或已用命令 ID 与原载荷/预期版本冲突 |
| 413 / 415 | 请求体超过 64 KiB / Content-Type 不符合要求 |
| 503 | 活动请求已满或存储不可用；活动请求已满时附 `Retry-After: 1`，存储错误未承诺该响应头 |

响应丢失或结果不确定时，保留原 `command_id`、`expected_version`、`command` 原样重试。服务器在比较当前版本前先查询已提交回执，因此账户版本已推进也可恢复原结果。若要提交根据新状态重新评估的业务请求，则使用新的命令 ID 和最新版本；不要给未知结果的同一操作直接换 ID。交易台遇到网络异常只提示重新加载，不提供自动持久化的重试队列。

批量 HTTP 接口一次接受 1–100 条，返回 200 时仍须检查 `results` 中每项的 `ok` 和 `status`。Python `Simulator.execute_batch` 与存储层上限为 256 条。返回顺序对应输入顺序；同一账户的后续命令须考虑前一成功项的版本，业务拒绝不会消耗版本。各分片独立提交，部分成功是正常的接口语义，详见 [批量事务](architecture.md)。

## 保证金与预占

模型 `linear-pm-v1` 对六组现货与合约相对价格冲击计算风险权益。负债按全额价格重估，正资产应用抵押折扣。组合最大压力损失取最差情景，且至少为零。未实现损益使用精确 FIFO 成本。订单保证金为账户已有仓位要求之外的资金占用。

完整场景、公式与手算案例见 [六场景组合保证金](risk-model.md)。`health=HEALTHY` 只说明权益高于 MM 且行情有效；此时可用保证金仍可能为负，不能据此跳过下单或成交的 IM 检查。

各仓位对 IM 的变化上界为当前标记价乘该合约的 IM 底线率和最大绝对场景跌涨幅二者中的较大值。每张订单对剩余数量保守计入该上界，再加最不利限价与手续费造成的权益损失。组合保证金以各情景最大值为准，取最大值不会放大这一变化上界。因此在固定报价下，可将每张挂单的最高影响相加，为任意成交组合作保守预占。重新报价后重新评估全部未成交量，发现预占不足时阻断新的成交。该余量计算可能拒绝能降低风险的普通挂单。

## 清算事务与恢复

当权益低于或等于 MM，或权益为非正时，账户进入清算区间。一次 `liquidate` 先撤单，或在挂单清空后实际写入模拟只减仓成交。每次以当前标记价为基准施加 0.5% 滑点和 0.2% 清算费，比较各仓位半平或全平后的权益减 MM，选剩余风险较低的候选。各单腿平仓都无法改善时，以一笔模拟事务关闭剩余组合，可能留下欠账。回执含成交及资金分录。

`mark_and_liquidate` 在单账户同一次事务中更新报价并推进最多八个清算动作。仍待处置时回执标记 `liquidation_pending`。批量请求按分片分组，不同分片可以独立成功或失败。同一分片的已接受写入和回执一起提交，已知业务拒绝使用保存点隔离。出现不确定返回时用原请求重试。

`user_net_usd` 分录表示账户 USD 资产减负债的变化。平仓结果与费用分配给模拟清算对手方及费用科目。负现金形成 USD 债务，重放从创世快照和已提交命令重算这些变动。原始报价与费率、模型及规则版本的历史兼容性需在引入新模型时显式维护。

SQLite WAL 使用 FULL 同步。分片数量在首次启动固定。清算队列、全局行情扇出、跨主机高可用、真实流动性验证和连续压力验收见 [性能测试](performance.md)。
