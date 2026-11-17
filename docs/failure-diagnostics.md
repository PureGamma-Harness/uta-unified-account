# 持久命令技术失败诊断

`QueueStore.record_failure` 现在在更新原 CID 的 `attempts`、`last_error`、退避或 QUARANTINED 的**同一个 fenced financial 事务**内，追加现有 immutable `uta_events` 中的 `COMMAND_EXECUTION_FAILED`。事件 `account_id=NULL`、payload `event_version=1`；没有新表、列、触发器、格式升级或启动时隐式迁移。旧 `last_error=technical_execution_failure` 与终态 generic error 完整保留，技术失败仍不能算成业务 REJECTED、接纳或成交。

## 实际异常路径

`process_one` 在 financial 事务选择原 inbox row，执行 SAVEPOINT 内业务操作、terminal receipt 与提交前校验。技术异常或 COMMIT 异常经 `CommandExecutionError(command_id, sequence, cause, attempt=...)` 向外传递，其中 `cause` 是原异常，`attempt` 是选择该 row 时已提交 `attempts+1`。业务拒绝的 savepoint 回滚与 REJECTED 路径保持原样。

真实 `_run_worker` 先检查直接 `WriterFenceError` 并停止，再按原 CID 查询已提交 receipt；已存在 SUCCEEDED / REJECTED / QUARANTINED 时不记失败。仍为 PENDING 时，持有原 control lock，把 `exc.cause` 和原 `exc.attempt` 传给 `record_failure`。后者在自己的事务再次检查 writer 与原终态，防止首次查询之后的变化。失租、SQLITE_FULL 或 failure-recording COMMIT 失败会向上传播，不能把未确认保存的诊断宣称为成功。

## v1 additive 内部事件契约

| 字段 | 含义 |
| --- | --- |
| `command_id`, `command_sequence`, `command_kind` | 原 inbox 身份与已支持的种类；不生成替代 CID。非法 persisted kind 为 null，`command_kind_sha256` 保留其原文本摘要，避免损坏输入使事件无界 |
| `attempt` | 本次提交的 failure-recording 序号，从 1 起；不是全部实际执行次数 |
| `canonical_payload_sha256` | 原 inbox 已存 canonical payload 文本 UTF-8 字节的 SHA-256；不重建/暴露 payload。若历史损坏导致 canonical 校验失败，仍只摘要该已存文本，不声称它通过校验 |
| `failure_class`, `receipt_state` | `technical_execution_failure` 与此次记录后的 PENDING / QUARANTINED |
| `diagnostic.status` | `captured` 或旧调用方未传 cause 时的 `cause_not_supplied` |
| `diagnostic.chain` | 最多 8 个原异常，跟随显式 `__cause__`，否则跟随 `__context__`；`relation` 标 root / cause / context，即使 context 被 Python traceback suppressed 仍记录其安全元数据 |
| chain node | `type`、reviewed allowlist 内 `public_code`、`sqlite_errorcode` / `sqlite_errorname`，以及最多 8 个 frame 的 module / function / lineno；缺失、未allowlist或非安全标识符为 null |
| bounds | `chain_truncated`、`chain_cycle` 与每节点 `frames_truncated` 明示保留边界；frame 按 traceback 外层向内层保留前 8 个。异常字段最多原生扫描 16 项，`attributes_truncated` 标记更多字段；class namespace / frame module 也最多扫描前 16 项，未观察到的 module 为 null |

不调用异常 `str`、`repr` 或自定义属性 hooks；不记录异常 message、args、notes、SQL、locals、文件路径、payload 或密钥。只从 BaseException native slots/dictionary 读取元数据，code 必须属于源码中明确 review 的公开 literal allowlist。SQLite code/name 只从真实 sqlite 异常的 native 字典取值，name 必须对应当前 sqlite 模块公开常量；旧 Python 没有该元数据时置 null，不通过 message 猜测。异常 type/module/function 标识符分别限制 128 ASCII 字符，frame、cause 数量有固定上限。

事件不记录行情引用。它不是失败执行事务的实际 snapshot，也不把失败后的当前行情冒充故障发生时的输入。今后若添加独立市场观察，必须显式标为“失败后观测”，并单独版本化。

旧调用方仍可不传 `cause` 或 `attempt`。新增 `attempt` 是可选幂等键：相同或更早已记录的序号返回当前 receipt，不重复追加；跳过下一序号拒绝；任何已提交终态先返回且绝不改写。无 `attempt` 的旧调用方保留每次调用增加计数的原行为。它只用于 trusted worker 的原观察序号，不是客户端可提交的新命令参数。

## 客户隔离与运维关联

现有 `ExchangeService.account_events` / `events(account_id=...)` 及 v2 `ManagedAccountViews.read(account, "events")` 均在 LIMIT 前用 `account_id=?` 过滤。因此 `account_id=NULL` 的全局诊断不会出现在客户账户 feed；v2 HTTP 没有全局事件路由，也不会 delegate 旧 `/v1/events`（各角色均 404）。`/v2/accounts/.../commands/...` 仍返回原 generic receipt，不附加这些内部元数据。

旧 v1 gateway 若由受信任部署单独挂载，`GET /v1/events` 对 **admin / risk** 角色返回全局事件，reader / trader 则转至自身 `account_events`。因此不能声称这些诊断“只有 ops 角色可见”：admin / risk、本机原始数据库、内部 `ExchangeService.events()` 和运维副本都属于既有受信任全局边界。真实 HTTP 测试验证这四种角色和 managed v2 对旧路由的拒绝；不在本补丁扩展或收窄现有角色权限。

先按原 CID 查询 inbox receipt，再在**同一分片**只读查 global event；保留 shard identity / authority、原 CID、command_sequence、attempt 与 digest 一起关联。以下仅查询，不写库；SQLite 构建启用 JSON1 时可运行参数化 SQL：

```sql
SELECT sequence, created_at, payload
FROM uta_events
WHERE event_type='COMMAND_EXECUTION_FAILED' AND account_id IS NULL
  AND json_extract(payload, '$.command_id')=?
ORDER BY sequence LIMIT 100;
```

不支持 JSON1 的旧 Python/SQLite 构建可用只读连接按 `event_type` 与 `account_id IS NULL` 查询，再用 Python `json.loads(row['payload'])['command_id']` 与原 CID 比较；禁止为运维查询写库升级。该字段无专用 JSON 索引，大历史查询需离线副本或按已有 event sequence watermark 分页，不能在生产 worker 上跑无界扫描。

只统计已提交 v1 事件能得到**已保存诊断的下界**。执行进程先死亡、失租、磁盘满、记录前失败、旧版本 worker 或旧 caller 缺 cause 都可能留下缺口；没有 event 不证明没有技术失败。failure-recording COMMIT 响应未知时先重查原 CID 的 attempts 和同一 attempt 的 event：二者同提交，重试同一 `attempt` 不重复写。执行的 financial COMMIT 响应未知时必须先查原终态，SUCCEEDED 不能被诊断或重试改写。不能拿诊断 event 数量声称全部实际 attempts、完整根因、金融事务实际输入或错误后自动恢复成功。

`20261117-managed-corrected-7200097` 原始 720 秒运行中真实 S1、CID `bench:684/shard0` 有一次技术 failure 记录，最终 REJECTED `market_unavailable` 503、3928ms、无订单金融效果。原版本没有保留实际 exception chain，本次补丁不能反推该次技术失败根因，也不回填虚构事件。该次故障仍是未解释的 release gate，当前没有新的负载 GO。

## 部署、消费者与回滚

1. 先审查全局事件消费者能忽略未知 event_type / event_version；本仓库财务 reconciliation 只处理自身认识的 financial event，新增 global 事件不产生资金、订单、仓位或账本变化。外部消费者若硬编码拒绝未知类型，应先升级其 additive 处理。
2. 依既有 managed 操作流程停下 producer / worker 并保留 HALTED，确认旧 owner 退出及租约要求。部署代码，再按既有恢复流程启动；不在线增加 schema、不修改行情 TTL 或任何金融公式、不借此自动激活或执行压测。
3. 回滚时同样先停止新 worker 并处理已有租约，再恢复兼容此既有数据库格式的原代码。现有事件表 schema 未改，新增 immutable 事件必须保留，不能删除来配合旧消费者。旧代码继续原 generic failure recording，回滚窗口不再有这些 structured cause，属于明确证据缺口。
4. 无论上线或回滚，都先按原 CID 查询 PENDING / terminal receipt，保留历史 attempts、退避、QUARANTINED 与财务事实。不得复制旧快照、改 CID 或重建失败历史。

## 小规模验证证据

`tests/test_failure_diagnostics.py` 验证真实 SQLite 异常链、原摘要/attempt、无金融变化、客户 feed 隔离、SQLITE_FULL 全回滚、失租、COMMIT 前后未知、同 attempt 恢复、终态不可改、deep chain/cycle/frame bounds、恶意异常访问及未知 code 隔离；现有真实 spawn poison 测试确认 `_run_worker` 传入原 StorageError → ServiceError 而非 generic wrapper。原有 durable-command 测试继续验证金融/receipt 同提交。

原代码的 red 证明与修改后 green 原始输出位于 [evidence/runs/failure-diagnostics](../evidence/runs/failure-diagnostics/)；全部只占 1 CPU，未运行 benchmark、soak 或大型 fixture。该验证只说明这条诊断/恢复路径，不构成生产性能或长期稳定性批准。
