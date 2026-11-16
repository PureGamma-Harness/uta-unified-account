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

正常重启直接使用 `DurableProcessRouter("/private/uta")`，随后 `start()`。保留的旧无 token `ShardRouter` / `ExchangeService` 对象会被 Database 层拒绝写入。只有子进程启动后才 acquire token，父进程不会把 token 传入 fork/spawn，也不能用父进程 token 冒充子进程 owner。

## 持久命令与真实后台工作

`submit_order(account_id, command_id, order_id, symbol, quantity, limit_price)` 和 `cancel_order(account_id, command_id, order_id)` 返回 `ack=durably_queued`。它只证明意图写入本地 WAL/FULL inbox，**不证明风险接纳或成交**。`status(command_id, account_id=...)` 以及 `wait(..., timeout=...)` 查询原 ID 的 PENDING、SUCCEEDED、REJECTED 或 QUARANTINED。SUCCEEDED 的下单回执是接纳时的快照；之后真实成交不会改写它。

每个 worker 在自身 fenced Database 事务内选命令，完成金融变更及 terminal receipt 后一起 COMMIT。崩溃前未提交的金融变更和回执一起回滚，原 PENDING 可由新 owner 重试；提交后失去响应先查询原 ID，不重复发明成功。技术异常有有界尝试和 QUARANTINED 记录，不能伪装为风险业务拒绝；同账户前序 PENDING 不被后序金融操作越过。

父进程自动监督真实子 PID，退出后重新 spawn。旧租约未到期时新 owner 等待，不能凭进程退出通知抢写；续租失败、租约过期或 PID 绑定不符，Database 在事务及提交边界拒绝。生命周期 Event/Pipe 只传停止信号和进程诊断，不承载任何需要恢复的命令、资金或回执。父进程死亡后子进程检测 PPID 变化并退出，避免永久孤儿续租。

worker 不仅处理挂单。它在同一个受控循环中调用真实 `ExchangeWorker.run_once()`，执行账户风险监督、持久清算规划和 `Matcher` 双腿撮合；没有额外模拟 tick 成交或假填单。已接纳订单可在新 owner 重启后继续匹配。后台工作每个金融事务同样受 token fencing，整个工作轮次还持有 router shared gate，校验资金证明、固定分片和行情 barrier。停止或不完整 publication 时不运行后台撮合。

## 行情、停机和全局部分发布

`publish_market(snapshot, timeout=...)` 先在 exclusive router gate 下持久化全局 HALTED/PUBLISHING、目标版本/摘要和每分片确定命令 ID，再把市场控制命令放到各分片 inbox。worker 的同事务 guard 只允许当前目标版本、摘要及命令 ID；本地 halt、行情写入和回执处于同一事务。部分完成仍全局关闭，重启后用**同一份 snapshot**重试会复用原命令 ID。更新到更高版本也不能把旧代次或不同内容冒充当前发布。

收齐成功回执后，父进程以只读方式核对实际各分片 payload，完成 watermarks，保持 HALTED。只有显式 `set_kill_switch(False)` 才经独立 SET_HALT 控制命令及完整、当前、新鲜行情检查打开全局 gate。停机先持久全局 HALTED，再尝试本地 fanout；未完成不会假报开放。发布新行情会使旧激活命令失效，不能在市场切换期间靠旧回执重新开放。

业务写入和后台匹配都不能裸用底层服务绕过 router：`ShardWorkerView` 在整个交易及 receipt COMMIT 期间持有 shared gate，并检查 account 的固定 SHA-256 分片、控制状态、当前行情摘要、本分片身份和全局资金证明。缺分片、错误身份及证明不一致会保留全局 stop。

第一版运行期只支持下单、撤单、行情和 halt 控制。开户、存款、新借款、资金池注资及其他未接线行政操作必须拒绝或保持离线；不能把它们偷偷改成父进程无 token 写入。只减风险的还款通道由后续同事务 helper 集成。本版也不提供跨分片对手成交或转账。

## 小规模过程验证

`tests/test_durable_process.py` 使用真实独立 PID 验证两个分片、两对手账户下单和真实双腿成交，强杀 owner 后由新 PID/代次恢复，再真实成交平仓，核对仓位、FILL_APPLIED、实际匹配记录及逐资产账本平衡。它还验证父进程重启时不初始化金融服务、PENDING/terminal 保留、部分 publication 恢复、旧无 token writer 拒绝、错误分片 inbox 触发全局 stop，以及单 worker 不打开其他 managed 分片。

这些用例是故障/恢复与金融事实验证，不是吞吐压测或生产迁移验收。
