# 单主机持久分片进程

`uta.durable_process.DurableProcessRouter` 把独立 `spawn` 子进程与同数据库持久 inbox 接起来。每个分片由一个绑定 PID、代次和租约的 writer token 写入；子进程只初始化自己的金融数据库，不初始化其他受管理分片。父进程重启只打开控制元数据、只读分片身份与租约、已有队列，不构造全量 `ExchangeService`。这仍是单主机 SQLite WAL/FULL，不是复制、跨区 HA 或跨分片原子结算。

## 显式初始化和恢复

```python
from decimal import Decimal
from uta.durable_process import DurableProcessRouter

# 只允许新空目录，必须显式 managed=True。
def offline_bootstrap(router):
    router.create_account("example")
    router.deposit("example", "synthetic-bootstrap", "USD", Decimal("1000"))

if __name__ == "__main__":  # spawn 入口必须有此保护
    with DurableProcessRouter.initialize(
        "/private/uta", 2, {"USD": 8}, managed=True,
        bootstrap=offline_bootstrap,
    ) as processes:
        # 随后明确发布有效行情、激活，再接受客户端业务请求。
        print(processes.diagnostics())
```

示例存款是合成 bootstrap 数据，不能替代真实外部资金证明。初始化先经既有 router 的账户、账本及全局资金证明检查完成离线准备，再创建 inbox 并不可逆启用各分片 fencing，最后封存控制配置。若中途崩溃而未封存，运行器拒绝启动，不会自动补建缺失财务状态或把旧库变为 managed。已经存在的旧布局必须另走显式接管流程，本版初始化不提供自动迁移。

正常重启直接使用 `DurableProcessRouter("/private/uta")`，随后 `start()`。使用当前存储代码构造并保留的旧无 token `ShardRouter` / `ExchangeService` 对象会被 Database 层拒绝写入。这项对象级验证不等于真实历史二进制防护：不认识 fencing 的旧源码需要持久 SQL 触发器/受控 UDF 格式门禁及独立旧进程验证，在该防护合入前不能宣称历史二进制已失效。只有子进程启动后才 acquire token，父进程不会把 token 传入 fork/spawn，也不能用父进程 token 冒充子进程 owner。

## 持久命令与真实后台工作

`submit_order(account_id, command_id, order_id, symbol, quantity, limit_price)`、`cancel_order(account_id, command_id, order_id)` 和 `repay(account_id, command_id, asset, amount)` 返回 `ack=durably_queued`。它只证明意图写入本地 WAL/FULL inbox，**不证明风险接纳或成交**。`status(command_id, account_id=...)` 以及 `wait(..., timeout=...)` 查询原 ID 的 PENDING、SUCCEEDED、REJECTED 或 QUARANTINED。SUCCEEDED 的下单回执是接纳时的快照；之后真实成交不会改写它。

每个 worker 在自身 fenced Database 事务内选命令，完成金融变更及 terminal receipt 后一起 COMMIT。崩溃前未提交的金融变更和回执一起回滚，原 PENDING 可由新 owner 重试；提交后失去响应先查询原 ID，不重复发明成功。技术异常有有界尝试和 QUARANTINED 记录，不能伪装为风险业务拒绝；同账户前序 PENDING 不被后序金融操作越过。

父进程自动监督真实子 PID，退出后重新 spawn。旧租约未到期时新 owner 等待，不能凭进程退出通知抢写；续租失败、租约过期或 PID 绑定不符，Database 在事务及提交边界拒绝。生命周期 FD/Pipe 只传启动/停止信号和进程诊断，不承载任何需要恢复的命令、资金或回执。父进程死亡后子进程检测 PPID 变化并退出，避免永久孤儿续租。父进程还检查其自有子进程的持久租约：若 PID 对应当前 owner 但租约已到期，会 SIGKILL 该尚未回收的子进程，释放 SIGSTOP 可能持有的 shared flock/SQLite 锁，再启动新 PID。它不会仅凭一个任意外部 owner PID 去杀无关进程。当前运行器另以持久的出生身份登记和 pidfd 处理“父进程已死、旧子进程仍 SIGSTOP”的已登记 worker 组合故障，具体证明与边界见下文。发布和 halt 的 exclusive flock 等待有显式 timeout，不会把等待锁的无限阻塞当成有限 receipt timeout。

worker 不仅处理挂单。它在同一个受控循环中调用真实 `ExchangeWorker.run_once()`，执行账户风险监督、持久清算规划和 `Matcher` 双腿撮合；没有额外模拟 tick 成交或假填单。已接纳订单可在新 owner 重启后继续匹配。后台工作每个金融事务同样受 token fencing，整个工作轮次还持有 router shared gate，校验资金证明、固定分片和行情 barrier。停止或不完整 publication 时不运行后台撮合。

## 行情、停机和全局部分发布

`publish_market(snapshot, timeout=...)` 先在 exclusive router gate 下持久化全局 HALTED/PUBLISHING、目标版本/摘要和每分片确定命令 ID，再把市场控制命令放到各分片 inbox。worker 的同事务 guard 只允许当前目标版本、摘要及命令 ID；本地 halt、行情写入和回执处于同一事务。部分完成仍全局关闭，重启后用**同一份 snapshot**重试会复用原命令 ID。更新到更高版本也不能把旧代次或不同内容冒充当前发布。

收齐成功回执后，父进程以只读方式核对实际各分片 payload，完成 watermarks，保持 HALTED。只有显式 `set_kill_switch(False)` 才经独立 SET_HALT 控制命令及完整、当前、新鲜行情检查打开全局 gate。停机先持久全局 HALTED，再尝试本地 fanout；未完成不会假报开放。发布新行情会使旧激活命令失效，不能在市场切换期间靠旧回执重新开放。

业务写入和后台匹配都不能裸用底层服务绕过 router：`ShardWorkerView` 在整个交易及 receipt COMMIT 期间持有 shared gate，并检查 account 的固定 SHA-256 分片、控制状态、当前行情摘要、本分片身份和全局资金证明。缺分片、错误身份及证明不一致会保留全局 stop。

当前运行期支持下单、撤单、还款、行情和 halt 控制。还款使用 worker 启动时、同一个 token Database 初始化的 CreditService，与金融分录和 inbox receipt 同事务提交；先付利息再付本金。全局停机或行情中断仍允许按同账户 FIFO 处理还款，并与撤单共享预留容量。开户、存款、新借款、资金池注资及其他未接线行政操作必须拒绝或保持离线，不能偷偷改成父进程无 token 写入。本版也不提供跨分片对手成交或转账。

## 小规模过程验证

`tests/test_durable_process.py` 使用真实独立 PID 验证两个分片、两对手账户下单和真实双腿成交，强杀 owner 后由新 PID/代次恢复，再真实成交平仓，核对仓位、FILL_APPLIED、实际匹配记录及逐资产账本平衡。它还验证父进程重启时不初始化金融服务、PENDING/terminal 保留、部分 publication 恢复、旧无 token writer 拒绝、错误分片 inbox 触发全局 stop，以及单 worker 不打开其他 managed 分片。

这些用例是故障/恢复与金融事实验证，不是吞吐压测或生产迁移验收。

新增过程用例还验证实际 SIGSTOP 持 shared gate 的 owner 在租约到期后被监督器清理、发布继续，以及新 PID 下的真实本金/利息还款。手算初始现金 1000、借本金 10、应计利息 1，先还 4 再还 2：现金 1004、本金 5、利息 0；资金池本金现金 45、利息现金 1，逐资产分录总和仍为零。

## 显式既有布局接管

`inspect_takeover(directory)` 只读返回既有 layout hash、分片数量、是否 managed、是否存在 inbox，以及逐片账本 head、账户/订单/仓位计数。它是接管计划，在线运行时不是跨片财务快照，也不是人的签字。

管理员明确停止旧入口后，可以调用：

```python
plan = DurableProcessRouter.inspect_takeover("/private/existing-uta")
processes = DurableProcessRouter.take_over(
    "/private/existing-uta", managed=True,
    expected_layout_hash=plan["layout_hash"],
)
```

这条显式路径保留原账户映射、费用和保证金政策，不能重分片或自动重绑定文件路径/旧快照。它先取得独立 supervisor flock 和全局 exclusive gate，持久 HALTED，然后写入未封存的接管清单；逐片按 inbox-before-fence 顺序封存，用当前管理员进程的临时 PID token 检验账本、信用投影、资金证明与固定路由。所有已验证分片的租约持有到最终封存，防止验证与启用之间出现另一个合作 writer。原有已接纳挂单、成交、账户和回执均保留，接管不会假造成交或转移托管资金。

`router_durable_takeover_events` 追加 PREPARED、逐片 SHARD_FENCED（包含原账本 head、数量和 writer generation）及 COMPLETED 证据。它是本机审计记录，不是外部审计封条。完成仍 HALTED，随后启动 worker 并显式激活。

若接管中断，未封存清单使普通启动拒绝；管理员可用相同 layout hash、政策和 inbox 容量再次显式调用 `take_over`。已 managed 的前缀不通过旧 Router 构造函数重开，不重建缺失 inbox/history，不接管活跃 lease，也不恢复旧快照。无法核验身份、账本、债务或资金证明时保留 stop，要求调查。当前函数使用有界的 60 秒临时租约；大型离线校验超时会拒绝封存而不是在失去租约后宣称成功。

新增测试从真实既有非 managed layout 接管两张挂单，验证新 PID 后沿用原单真实撮合、当前代码的无 token 旧对象不能写；还注入第二片封存失败，验证显式重试不重复存款、不丢原账本。真实旧二进制门禁另行验证，不能由这两个用例替代。

## 已登记孤儿进程的可信回收

每个 coordinator 先独占独立 supervisor flock；该描述符不传入 spawn 子进程。启动 worker 前，父进程将目标 authority、shard、随机 nonce、PID、Linux `/proc` start_ticks、boot_id 与 coordinator ID 追加到 `router_process_owners`。子进程在这条 SPAWNED 事实提交前被生命周期启动管道挡住，不能 acquire token 或碰金融状态。取得 token 后再追加含真实 generation 的 OWNED 记录，然后才打开自己的金融服务。

新 coordinator 获得 supervisor flock 后，先读取这些历史事实。对于仍存活的旧注册进程，匹配相同 authority、nonce、PID、start_ticks、boot_id 和 OS 用户；若它仍有有效 lease，必须等待到期或正常退出。PID 已复用、boot 改变、nonce 已变成另一身份、不认识的外部 owner 都不会被猜测性终止。发信号前使用 `pidfd_open` 锚定准确进程，再复核出生信息，最后使用 `pidfd_send_signal(SIGKILL)`；不以裸 PID 重用风险作为授权。旧注册子进程若尚未取得 token，也不能因 coordinator 已死而继续尝试进入金融服务。

回收后追加 ORPHAN_KILLED 证据，新 PID 仍需自行取得更高 token generation，不能继承旧 token。缺 Linux pidfd 或无法验证身份时拒绝自动回收；旧版本没有登记出生身份的孤儿也不在自动终止范围。`start(recovery_timeout=10)` 对仍有效的旧 lease 等待有界，超时要求重试或调查，不能缩短旧 lease 来强行接管。

新增真实过程测试使用一个独立 coordinator，保留已成功接纳的原挂单；把两个子进程 SIGSTOP，其中一个确认持有 router SH，再 SIGKILL coordinator。新父进程不发人工 SIGCONT，以持久出生事实回收两个旧进程，启动新 PID、重新发布/激活，再由新对手单与原挂单真实成交，原 command 回执保持不变。生命周期信号改用 FD 管道，避免该破坏性测试依赖父进程清理命名 semaphore。它不把这些 IPC 当作持久命令来源。

### 历史二进制及格式升级

当前候选已接入存储组的持久 SQL guard 格式 1：实际旧 `ad3f5b8` 源码包无受控 UDF 时也会由金融表触发器拒绝。`tests/test_writer_fence_legacy.py` 的七项实际历史进程验证在本分支通过；最终合入仍以独立组与整体回归为准。运行器遇到 guard 格式 0 会 fail closed 要求显式离线 `upgrade_guards()`，不会自动升级、重新绑定路径或把旧 snapshot 当作当前 authority。出生登记解决的是本机相关进程回收，不替代持久 SQL guard，也不提供 OS 所有者之外的安全隔离。

## 新 authority 的 required 决策审计配置

新的 `initialize(managed=True)` 默认明确使用 `decision_audit=True`，创建 required 审计 schema 3。`take_over(...managed=True,expected_layout_hash=...)` 也是显式离线升级入口，默认 True；原有 schema 2 挂单不会补造历史审计，真实 legacy gap 和原数量保存在每片 `uta_audit_capability`，之后确认的真实成交必须产生新执行审计。

这个布尔值固化在 control 的 service 配置，bootstrap `ShardRouter` 和子进程 `_options` 都显式透传，不依赖父进程对象或 monkeypatch 被 spawn 继承。它不改变经济 layout hash、账户分片或保证金公式。显式 `decision_audit=False` 只标记 `managed_development_legacy_gap` 开发/参考 profile，不能作为 required 候选证据；没有该字段的第一波 managed 配置在正常 `start()` 时拒绝，要求单独、显式离线升级，不会改写其不可变配置。

`diagnostics()` 返回 `decision_audit_required` 与 profile；当前 supervisor 的 ready 还要求该 PID 已完成真实服务初始化的握手，不只看它取得了 lease。诊断仍不是金融授权，命令和每个确认成交必须在事务内做完整校验。

### 行情与金融就绪的只读诊断

`diagnostics(*, timeout=1.0)` 的参数为有限秒数，范围 `0 < timeout <= 5`，不接受布尔值。一次预算覆盖 supervisor mutex、router shared gate、控制库、全局资金证明以及各分片读取；SQLite 锁争用最多单次等待 20ms，VM progress handler 在 guard 验证和查询过程中检查同一 deadline。达到预算或遇到异常返回未就绪，不使用无限 flock/SQLite 等待。这个预算不保证操作系统调度、故障磁盘 I/O 或任意 Python 扩展调用的硬实时上界。

诊断不构造金融服务，不初始化数据库，不执行金融写入，也不切换 journal mode。它在 shared gate 内读取已验证的控制状态、完整发布 watermarks 和资金证明，再在每片的同一个只读事务内读取分片身份、持久 SQL guard、writer lease、local halt、required 审计 capability 与完整行情 payload。实际 payload 的 SHA-256、canonical 编码和版本必须匹配当前全局 barrier，不能只相信版本、早先握手或缓存。缺失、损坏、超限、缺 USD settlement、缺活跃持仓/挂单或已入账资产/负债的输入都不能就绪。

所有分片和证明读完后，重新用快照**原始** `observed_at` 与配置的 `max_price_age` 检查时效，未来容忍仍沿用 `MarketSnapshot.validate` 的 1 秒界线；不刷新或改写时间戳。租约也在返回前再次检查到期时间。部分发布、全局/本地停机、代次握手不符、过期报价和未来报价均为未就绪。

返回值区分这些事实：

- `workers_alive`：本 supervisor 所拥有的每个 child PID 都已观察到存活；不说明有新鲜行情或已完成金融初始化。mutex 不可读时为 False，含义是无法确认全部存活。
- `financial_ready`：完整发布且已激活，所有必需的身份、租约、初始化握手、资金证明、审计 capability 和行情检查通过。兼容字段 `ready` 与它完全相同。
- `state_observed`：是否成功读取并验证控制状态。失败时 `state=None`，不会捏造一个已持久 HALT 的状态。成功时 `state` 只包含控制标志、代次、行情版本/摘要、watermarks 与受控错误码。
- `reason` 与各 `workers[*].reason`：受控诊断码，例如 `market_stale`、`market_future`、`market_invalid`、`market_missing`、`market_barrier_mismatch`、`publication_incomplete` 或 `diagnostic_timeout`。不返回数据库路径、完整价格 payload、writer nonce 或异常正文；分片报价成功读取时另给原 `market_observed_at`、版本和摘要。

这是同主机的就绪观察，不是外部行情源真实性、独立价格证明、跨片账户财务快照或执行授权。行情失效时 `workers_alive=True` 与 `financial_ready=False` 可以同时成立；风险降低的撤单/还款仍由各自事务规则决定，不能由此诊断一律禁止。

`tests/test_process_readiness.py` 用真实两个 spawn PID 验证自然过期、新行情恢复、同版本内容变更、部分发布恢复与只读原时间戳；损坏/缺失/超限注入采用明确 development profile 的离线合法 test token，不移除 required 历史 guard。另以诊断时钟回退、最后一片读取后跨过时效界线、有界 mutex/flock 和真实 SQLite 长查询验证未来/延迟/超时失败及路径隐藏。这些小规模故障用例不构成 feed trust 或负载验收。

## 既有 managed authority 的显式离线审计提升

第一波 managed authority 的不可变配置不能被重写成 True。先停止 coordinator 和所有 writer，读取只读计划：

```python
plan = DurableProcessRouter.plan_decision_audit_upgrade("/private/managed")
required = DurableProcessRouter.upgrade_decision_audit(
    "/private/managed", managed=True,
    expected_layout_hash=plan["layout_hash"],
)
```

计划包含原 layout/config hash、目标 schema 3、各片账本 head/数量和当前 schema，以及 promotion capability 状态。执行先全局 HALT；仍有 coordinator 会被 `supervisor_busy` 拒绝，未过期租约也不会被抢夺。所有 financial 数据库仍只由临时 PID token 访问。

提升在控制库创建绑定原配置 hash 的 `router_decision_audit_capability` PREPARED 清单，普通 constructor/start 在该状态拒绝。逐片明确使用 `decision_audit=True`，核对账本/信用/资金证明，保存前后相同的财务 heads 与原始 legacy gap；所有 temporary lease 保持到最终 READY。`router_decision_audit_events` 追加 PREPARED、SHARD_REQUIRED 和 READY 证据，旧 `router_durable_config` 的字节完全不变。

READY 后，新 parent 才按经过验证的 capability marker 读取 effective required=True；旧 facade 若缓存了 False 必须重开。没有 marker 就不能猜测提升。中断后可按同一计划明确续接，已提升分片只验证，不补造旧决策；同一 READY 计划可再次确认。完成仍 HALTED，需启动并显式激活。

required 控制与财务 schema 必须相符。把旧的、提升前 schema 2 快照恢复到原路径也不会让 constructor/worker 自动再升级；它会保留 stop 并报 `decision_audit_capability_mismatch`。这项检查针对 capability/schema 不一致，不宣称能替代复制、受信备份恢复或发现所有同代次文件回滚。

过程测试覆盖：原配置 byte-for-byte 保留、legacy 挂单缺口不补造、提升后原挂单与新对手单的两条真实成交 FK、第二片失败后普通启动拒绝及显式续接、活 coordinator 不提升、第一波缺 flag 配置明确拒绝，以及恢复旧快照后不默默修复。暂停窗口和 legacy gap 是证据的一部分，不应从生产候选报告中删掉。
