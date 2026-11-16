# Durable command HTTP v2

`uta.durable_gateway` 提供独立的 `/v2` 命令入口与回执查询。它复用现有 HTTP 认证、账户范围检查、严格 JSON、framing 限制、socket 超时、有界并发和凭据轮换；没有回退到 v1 同步交易路径。旧 `uta.gateway` 的 `/v1` 接口与 `201` 语义不变。

**`202 durably_queued` 只表示本机命令 inbox 的事务 COMMIT 已返回，不表示订单通过风控、资金已预留、已成交或已完成还款。** 只有独立 fenced writer 提交的终态回执才带业务结果。当前仍是可信 Linux 主机上的 SQLite WAL/FULL 基础，不是复制日志、多机共识或真实资金生产许可；G7 未批准真实资金运行。

## 启动与权限边界

服务接受两种已有 producer：

- 单 authority：`QueueStore(database, initialize=False, ...)`，目标必须已经离线初始化 inbox 并启用 `WriterFence`。HTTP producer 的 Database 不得携带 writer token。
- 多 shard：`DurableProcessRouter(existing_directory)`。这个已有布局的 parent 构造路径只读取 control/queue 元数据；实际金融 service 由独立进程获取 PID 绑定 lease 后创建。

HTTP 入口不 bootstrap 账户或账本，不创建 `ExchangeService`，不创建或重建 inbox，不启动或获取 writer lease，不修复缺失 schema。不能用旧同步 `ExchangeService(...)` 构造器在 parent 重开 managed authority，也不能放宽 fence 的 schema/DML 权限来绕过这个限制。

单 authority 的集成示例，所有文件和持久化 queue 配置都必须已经存在并匹配：

```python
from uta.durable_commands import QueueStore
from uta.durable_gateway import make_server
from uta.gateway import load_credentials
from uta.storage import Database

producer = QueueStore(Database("/var/lib/uta/exchange.sqlite3"),
                      queue_capacity=1024, cancel_reserve=16,
                      market_capacity=4, initialize=False)
with make_server(producer, port=8081,
                 credentials=load_credentials("/etc/uta/credentials.json")) as server:
    server.serve_forever()
```

这个 factory 只构造服务器。调用方负责 worker 的独立启动/监管、信号处理、HTTP drain 和 producer 生命周期；它没有自动安装 SIGTERM handler 或宣称提供新 CLI 命令。多 shard 可把已有 `DurableProcessRouter` 直接作为 producer 传入同一 factory。parent HTTP 重启不需要重放 financial schema DML。

默认只监听 `127.0.0.1:8081`，只允许 IPv4 loopback。远程使用须经 TLS 反向代理，并配置代理的连接、总请求时限和请求速率。内置 worker cap 是并发上限，不是每账户/API key 的速率配额。原 Bearer 路径是开发 profile；新增的 [显式 HMAC profile](signed-api.md) 提供持久 nonce 防重放并默认要求 TLS。Bearer 开发模式不满足生产接入门槛，也没有 WebSocket 或互联网边缘服务器能力。

| 角色 | v2 能力 |
| --- | --- |
| trader | 只在绑定账户提交订单、撤单及查询该账户命令 |
| reader | 只查询绑定账户命令，不提交业务命令 |
| funding | 只在绑定账户提交 REPAY 并查询该账户 REPAY；查询其他 kind 返回 404 |
| risk | 查询任意账户命令、worker-health/metrics；单 authority 的 market/halt 控制命令 |
| admin | 上述全部操作；不因此获得绕过 durable writer 的同步金融路径 |

除公开 `GET /healthz` 外均要求 `Authorization: Bearer <token>`。跨账户路径先做 scope 检查，未授权返回 403；已授权账户内不存在的命令返回 404。查询不会搜索所有 shard：URL 中的账户决定 shard，避免同一个 command ID 在不同 shard 的歧义与信息泄漏。

## 请求与路由

正文必须为单份 UTF-8 JSON 对象，带 `Content-Type: application/json` 和唯一合法 `Content-Length`，最大 64 KiB。不接受 chunked、重复对象 key、NaN/Infinity、浮点 JSON 金额或未知业务字段。金额、数量和价格必须为十进制字符串；boolean 字段必须是真正 JSON boolean。ID 使用既有 path-safe ASCII 规则，长度 1..128；资产/合约 JSON 字段可以含 `/`。

| 方法与路径 | 正文 | 权限 | 结果 |
| --- | --- | --- | --- |
| `POST /v2/accounts/{aid}/orders` | `{"command_id":"c1","order_id":"o1","symbol":"BTC-PERP","quantity":"1","limit_price":"100","reduce_only":false}` | trader/admin | 排队或已有命令回执 |
| `POST /v2/accounts/{aid}/orders/{oid}/cancel` | `{"command_id":"cancel1"}` | trader/admin | 撤单命令回执；入队不代表已经释放预留 |
| `POST /v2/accounts/{aid}/repay` | `{"command_id":"repay1","asset":"USD","amount":"1"}` | funding/admin | REPAY 命令回执；入队不代表已扣现金或减少债务 |
| `GET /v2/accounts/{aid}/commands/{cid}` | 无 | 账户范围内 reader/trader/funding，或 risk/admin | 该 shard/账户的稳定命令回执 |
| `POST /v2/control/market` | `{"command_id":"market1","snapshot":{...完整MarketSnapshot对象...}}` | risk/admin | 仅单 authority QueueStore 支持 |
| `POST /v2/control/halt` | `{"command_id":"halt1","enabled":true}` | risk/admin | 仅单 authority QueueStore 支持 |
| `GET /v2/control/commands/{cid}` | 无 | risk/admin | 仅单 authority 控制 lane 的回执 |
| `GET /v2/worker-health` | 无 | risk/admin | 只读 lease/process/control 观测，HTTP 200 不代表账户可交易 |
| `GET /v2/metrics` | 无 | risk/admin | 原 HTTP counters 加 `durable` 诊断 |
| `GET /healthz` | 无 | 公开 | 进程可应答，不证明 writer 正常或金融状态安全 |

`reduce_only` 可省略，默认 false。相同 numeric Decimal 的 `"1.0"`、`"1.00"` 使用规范值比较。客户端在首次发送前必须持久化 `aid`、`command_id` 与完整操作内容；queue 的字段/数值/资产精度校验通过，也不等于运行时风控通过。

多 shard parent 的 market/halt 控制采用独立的持久化 generation/fanout/barrier 协议，目前没有稳定的外部 client command-ID 契约。因此这些 HTTP 控制路由在多 shard producer 上明确返回 `501 unsupported_durable_operation`，不会调用其同步 `publish_market()` 或 `set_kill_switch()` 充当替代。单 authority 控制 lane 也不能当作跨 shard 发布屏障。

没有 durable 协议的操作不会偷偷使用 v1 路径：账户/风险快照读取、入金、借款、计息、现货订单、成交摄入、撮合、提现、条件单等不在这里支持。已识别的 v2 账户下不支持操作返回 501，未知路径及 v1 路径返回 404；不会伪造账户或风险结果。不得把这个较窄的接口能力解释为整个交易所已生产化。

## 两阶段回执

首次入队或查询到 PENDING 时，HTTP 为 `202`：

```json
{
  "command_id": "c1",
  "sequence": 1,
  "account_id": "alice",
  "kind": "SUBMIT_ORDER",
  "state": "PENDING",
  "ack": "durably_queued",
  "result": null,
  "error": null,
  "status_url": "/v2/accounts/alice/commands/c1"
}
```

实际响应还包含排队/完成时间、技术尝试次数与重试时间等 inbox 字段。这个 ACK 不改变余额、仓位、订单占用或债务。

worker 终态回执存在时，重复 POST 或 GET 返回 HTTP `200`、`ack: "terminal_receipt"`。**程序必须检查 `state`，不能把 200 当作交易成功。**

| state | result/error | 含义 |
| --- | --- | --- |
| `SUCCEEDED` | `result` 为 worker 提交的实际业务结果，`error` 为 null | 业务修改与回执同一次金融事务提交；订单入场仍不等于成交 |
| `REJECTED` | `result` 为 null，`error` 含业务 `code/message/status` | worker 提交了明确业务拒绝；该命令没有留下部分金融修改 |
| `QUARANTINED` | `result` 为 null，`error.code` 为 `command_quarantined` | 技术失败达到 worker 的隔离策略；不是风险接受，也不是普通业务拒绝，需调查 |

命令回执保存原始转换结果。订单后来撤销或成交，不会把原来 SUBMIT_ORDER 的终态结果改写成今天的订单投影；同一终态命令重试返回已存事实。

## FIFO、幂等与结果未知

同一账户内按 pending sequence FIFO 处理。技术失败/退避中的账户头命令可能阻塞该账户后续命令；控制 lane 有单独有界容量与处理优先级，不能推断为整个系统的单一全局 FIFO。cancel 与 REPAY 可用额外风险减少保留容量，但仍不能越过自己账户未完成的队头。

inbox 的 `queue_capacity`、`cancel_reserve`、`market_capacity` 限制的是 PENDING 记录，不限制已保留的历史回执、数据库字节或停机期间累计历史。容量耗尽返回 `503 durable_queue_overloaded`，新的该命令 ID 不产生排队记录；重复已有命令的查询/幂等重试仍可取回原记录。不能用删除终态回执来清理幂等历史。

同一个 inbox 内 command ID 唯一，跨 kind、账户或不同规范内容复用返回 `409 idempotency_conflict`。不同 shard 可存在相同 ID，所以查询与客户端重试必须保留账户定位；推荐使用高熵 ID 避免同一 inbox 意外冲突。`order_id` 与 `command_id` 是不同身份，不应相互替代。

连接断开、HTTP 客户端超时、503 `command_outcome_unknown` 或通用服务器故障之后，客户端可能不知道入队 COMMIT 是否完成。**保留原账户/command ID，先查询或用原内容重试，不能换新 ID 再提交。** 服务器不会根据异常猜测“未排队”或伪造一个拒绝结果。`command_outcome_unknown` 的响应没有业务结果；真实已提交的 pending/terminal 事实仍通过同一查询 URL 找回。

worker 执行发生异常时，金融修改与终态回执可能一起回滚而保持 PENDING；若异常发生在已成功 COMMIT 之后，worker 应先查询已有终态，再决定是否记录重试，不能覆盖已提交事实。QUARANTINED 是技术终态，重复原 ID 不自动重开；调查结果与后续处理应有独立审计记录。

父 HTTP 进程停止不删除 inbox。正常 HTTP shutdown 会排空已接收 handler，但不承诺排空所有持久化 pending 命令。writer 停止后队列 ACK 仍可能成功，命令等待下一位合法 owner；失去 lease 的旧 PID 不能继续金融提交。重启 parent 读取已有 QueueStore/DurableProcessRouter，不应再次用 bootstrap 或金融构造器初始化 authority。

## 只读诊断与错误

单 authority health 包含 `managed`、writer 的 `lease_active/generation`、pending 数量及队列容量；不返回数据库路径、owner nonce 或 writer token。多 shard health 包含过滤后的 PID/owner PID/lease/generation 与控制态观测，`dispatch_available` 只是控制/进程条件，不是任意账户的风控结论。统计不属于金融快照，不构成还款、订单或资金安全回执。

一般协议/鉴权错误继续使用原 JSON 错误结构 `{"error":{"code":"...","message":"..."}}`。主要新增项：

| HTTP | code | 处理 |
| --- | --- | --- |
| 400 | 原有 invalid_json/invalid_fields/invalid_decimal 等 | 修正输入，不能用浮点金额或丢弃幂等 ID |
| 401 / 403 | unauthorized / forbidden | 修复认证或账户/角色范围；不打印 token |
| 404 | command_not_found / not_found | 该授权账户范围内无回执或路由不存在；不要搜索其他账户猜测状态 |
| 409 | idempotency_conflict | ID 与已有规范内容冲突，调查原请求 |
| 503 | durable_queue_overloaded | 新命令容量不足；退避并保留原 ID |
| 503 | command_outcome_unknown | 入队结果不确定，查询/重试同一账户与 ID |
| 503 | command_query_unavailable / invalid_command_receipt | 暂时不能提供可信回执，不推断金融结果 |
| 501 | unsupported_durable_operation | 此 durable 入口未支持该操作；不能改走未 fenced 的同步通道 |

HTTP 并发槽耗尽可以返回空正文 503。技术内部异常保持脱敏；消息文本不是稳定程序协议。此版本没有真实资金生产批准。

## 验证范围

`python -m unittest discover -s tests -p test_durable_gateway.py -v` 使用真实 loopback HTTP、临时 WAL/FULL 数据库与 `spawn` 独立 PID，覆盖 queued/terminal 的区别、真实风控拒绝/撤单/还款、隔离状态、响应丢失后原 ID 恢复、角色/账户边界、严格 framing/超时、队列保留容量、parent 重开不构造金融 service，以及双 shard 的同 ID 正确定位和真实 worker 生命周期。这些小型合成回归不是生产吞吐或 HA 验收。
