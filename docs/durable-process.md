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

processes = DurableProcessRouter.initialize(
    "/private/uta", 2, {"USD": 8}, managed=True,
    bootstrap=offline_bootstrap,
)
processes.start()
```

示例存款是合成 bootstrap 数据，不能替代真实外部资金证明。初始化先经既有 router 的账户、账本及全局资金证明检查完成离线准备，再创建 inbox 并不可逆启用各分片 fencing，最后封存控制配置。若中途崩溃而未封存，运行器拒绝启动，不会自动补建缺失财务状态或把旧库变为 managed。已经存在的旧布局必须另走显式接管流程，本版初始化不提供自动迁移。

正常重启直接使用 `DurableProcessRouter("/private/uta")`，随后 `start()`。使用当前存储代码构造并保留的旧无 token `ShardRouter` / `ExchangeService` 对象会被 Database 层拒绝写入。这项对象级验证不等于真实历史二进制防护：不认识 fencing 的旧源码需要持久 SQL 触发器/受控 UDF 格式门禁及独立旧进程验证，在该防护合入前不能宣称历史二进制已失效。只有子进程启动后才 acquire token，父进程不会把 token 传入 fork/spawn，也不能用父进程 token 冒充子进程 owner。

## 持久命令与真实后台工作

`submit_order(account_id, command_id, order_id, symbol, quantity, limit_price)`、`cancel_order(account_id, command_id, order_id)` 和 `repay(account_id, command_id, asset, amount)` 返回 `ack=durably_queued`。它只证明意图写入本地 WAL/FULL inbox，**不证明风险接纳或成交**。`status(command_id, account_id=...)` 以及 `wait(..., timeout=...)` 查询原 ID 的 PENDING、SUCCEEDED、REJECTED 或 QUARANTINED。SUCCEEDED 的下单回执是接纳时的快照；之后真实成交不会改写它。

每个 worker 在自身 fenced Database 事务内选命令，完成金融变更及 terminal receipt 后一起 COMMIT。崩溃前未提交的金融变更和回执一起回滚，原 PENDING 可由新 owner 重试；提交后失去响应先查询原 ID，不重复发明成功。技术异常有有界尝试和 QUARANTINED 记录，不能伪装为风险业务拒绝；同账户前序 PENDING 不被后序金融操作越过。

父进程自动监督真实子 PID，退出后重新 spawn。旧租约未到期时新 owner 等待，不能凭进程退出通知抢写；续租失败、租约过期或 PID 绑定不符，Database 在事务及提交边界拒绝。生命周期 Event/Pipe 只传停止信号和进程诊断，不承载任何需要恢复的命令、资金或回执。父进程死亡后子进程检测 PPID 变化并退出，避免永久孤儿续租。父进程还检查其自有子进程的持久租约：若 PID 对应当前 owner 但租约已到期，会 SIGKILL 该尚未回收的子进程，释放 SIGSTOP 可能持有的 shared flock/SQLite 锁，再启动新 PID。它不会仅凭一个任意外部 owner PID 去杀无关进程；父进程也已经死亡且旧子进程仍被 SIGSTOP 的组合故障需要独立的孤儿身份/接管协议，不能冒称已经自动处理。发布和 halt 的 exclusive flock 等待有显式 timeout，不会把等待锁的无限阻塞当成有限 receipt timeout。

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
