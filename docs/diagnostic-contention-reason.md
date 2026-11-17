# 有界诊断的 SQLite 争用分类

本次修复的可复现缺陷是：诊断的 SQL `busy_timeout` 最多为 20ms，早于整个诊断预算耗尽的真实 `SQLITE_BUSY` 会被归为 `shard_unavailable`。只允许 `worker_unready` / `diagnostic_timeout` 的有限观察因此会立即失败。修复只改变已知诊断争用的原因分类；未观测到的 SQL 字段仍为 None / False，`ready` / `financial_ready` 仍为 False。

## 原始 CI 与证据边界

源为完整 SHA `4608ffeda0651f8dafd2cd151618a71ed99aa62e`。原 push run `44036919027` 的 Python 3.10 job `133881910052` 为 1096 tests、3 failures、0 errors、passed=False；其中本调查对应 `test_readiness_sampling.py:82,120` 两项。完整 SHA 对应的原始 artifact 在 `/workspace/uta-ci-4608-push-310/`，保留原样。同 SHA 的另一次 PR 四个 job 成功不能覆盖这次失败。

原失败记录的 global state 已激活，worker alive，部分 worker 已有 READY report；失败片的实际 SQL 字段为空或 False，reason 为 `shard_unavailable`。原 report 没有异常类型或原生 code，因此不能证明它来自 SQLite busy，也不能排除 I/O、schema、identity 或 guard 失败。本地重新通过以及下述受控复现均不补造原错误。

原 log SHA-256 为 `03ae4c27618fceb581499b415fc8c289c0a9dbf8f848938b750dd3e64aa6534e`；原 artifact.zip 为 `bd20e985bd53e58572b3a2f5dba0860799ba55750ce9c2e02c9fd20b271c366d`。原 `uta/durable_process.py` SHA-256 为 `5c1979d15f9dae3fa5aec96c7057df09fe9c3c593e6d5e9b92bc8bdff2466471`，与原 CI source manifest 一致。

## 真实 SQL 路径

`DurableProcessRouter.diagnostics()` 创建一份整体 deadline，依次取得 supervisor mutex、router gate、只读 control transaction，再读取每片的 lease / guard / identity / funding / market。`_DiagnosticDatabase` 在连接上安装整体 deadline progress handler，以及最多 20ms 的单条 SQL busy handler。`Database.read_transaction()` 在进入和退出事务时验证持久 guard。

测试用独立短命 Python 子进程在原 shard WAL 数据库上取得 `locking_mode=EXCLUSIVE` / `BEGIN EXCLUSIVE`，不修改金融数据。真实 spawned owners 仍使用原 1s lease；测试仅在短暂观察期间持有父 supervisor mutex，避免测试本来要测 SQL 时先被 monitor 抢占 mutex。真实 SQLite 在 `_DiagnosticDatabase.read_transaction()` 的 persistent-guard 首次 SQL 读取中抛出 builtin `OperationalError`。

未改 production 的 source4608ffe，在实际 Python 3.10.22 / SQLite 3.53.1 上，200ms 整体预算内约 31ms 即返回 `shard_unavailable`；实际 exception 没有 `sqlite_errorcode`，args 精确为 `("database is locked",)`。Python 3.13.5 / SQLite 3.46.1 也记录相同缺陷，原生 code 为 5。释放真实锁后，重新读取当前 SQL 的同组 worker PID 恢复 ready，无再次 publish / activation。

## 分类与保守条件

- 精确 builtin `sqlite3.OperationalError` 的有效原生 primary code 5 / 6（包括 extended codes）归为 `diagnostic_timeout`。
- 仅当没有 `sqlite_errorcode` 属性时，允许精确 builtin `OperationalError` 的单个字符串 args 为 `database is locked` 或 `database table is locked`。不做前缀、子串、表名后缀或其他异常类型匹配。
- 有原生 code 时原生值优先；IOERR、CORRUPT、schema 错误、无效 code 以及其他异常不能靠 lock 文本变为 transient。原生 INTERRUPT，或旧 Python 精确 `interrupted`，仅在共享 deadline 已到时归为 timeout。
- 已知 fence / identity / storage 等 fatal 原因不因后续 deadline 到达变为 transient；另一片 busy 也不能遮蔽已观测到的 fatal 原因。
- 新增 `observation_error` 只输出固定 type，以及 SQL error 的整数 native code / None。不输出 exception text、路径或 writer nonce。

没有扩大 helper 的 transient allowlist，没有增加生产内重试，没有延长业务 deadline、TTL 或 writer lease。调用方若决定再次观察，仍在原有限累计预算内发起完整的新诊断；旧的 True 不作缓存授权。

## 验证与保存记录

新增测试覆盖：真实 WAL busy 与释放后同 PID 恢复、两片真实 busy 共用同一 deadline、持续真实 busy 耗尽 helper 的单一观察预算、真实 shared-cache SQLITE_LOCKED、真实离线 DROP 持久 guard 与另一片 busy 同时发生时立即失败，以及注入的 typed IOERR_READ 立即失败。IOERR 用于分类边界验证，不宣称本机发生了真实磁盘故障。既有测试继续验证 future / stale / partial 不放行、guard exit 失败不放行、SQL progress interruption、HTTP 的 unknown/null 保留。

原始与修复后输出保存在 `evidence/20261117-ci-diagnostic-reason/`。两个 harness 调整也保留：第一轮累计 deadline case 被 monitor 抢先持有 mutex，未进入 SQL；之后固定父 mutex 调度。第一轮 shared-cache case 得到带表名的 LOCKED 文本，严格旧 Python fallback 正确拒绝；之后改用实际 `BEGIN IMMEDIATE` 冲突产生精确 canonical 文本。这些 harness 失败不算自然 CI 根因，也没有被覆盖。

验证均使用 `taskset -c 1`、`-W error::ResourceWarning` 和 focused tests，无 profile、大 cohort 或长测；没有操作旧 24h job。三 runtime 最终结果见同目录 manifest；focused 成功不等于重新证明原 CI 或完整 suite 成功。

独立只读交叉 review 未发现 runtime 放行问题，提出两个测试 harness 改进，均已采纳：外部耗时断言容纳调度/返回开销，配置的 200ms 诊断预算不变；锁子进程在 release pipe 提前关闭或等待退出超时时仍会 kill / reap。对最终测试文件重新执行 9 项新增测试，既有 29 项 focused 结果与其对应 production hash 一并保存。

Python 3.13 的两份早期输出虽然 unittest 为 OK、exit=0，但包含新离线 DROP 测试的 `ResourceWarning: unclosed database`；SQLite connection 的 context manager 只管理 commit / rollback，不会 close。两份 raw 均以 `harness-resource-warning` 保留且不计为 passed；测试改为 `closing()` 后重新执行。manifest 同时检查 unittest 结果及任何 ResourceWarning / Exception ignored，避免把解释器退出时忽略的资源错误当成通过。
