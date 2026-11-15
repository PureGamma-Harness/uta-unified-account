# 已实现交易路径：架构、流程与时序

本页核对基线为 PR #3 `92086bd8fbd1d41427a614dfdd60dce183396258`，描述该候选分支，不代表已合并 main、已部署或获准实盘。旧研究模拟器见 [architecture.md](architecture.md)，未来目标见 [target-architecture.md](target-architecture.md)。三者不可混用。以下均为本地合成资金工程验证，不包含真实交易所或托管接入。

## 1. 实现架构与原子边界

```mermaid
flowchart TB
    C["客户端：凭据、账户、原业务 ID"] --> G["gateway.py：认证、角色与账户校验"]
    G --> S["service.py：ExchangeService 同步命令"]
    G --> B["admission.py：可选有界 FIFO / 单 worker"]
    B --> S
    P["固化产品和风险规则 / 版本行情"] --> S
    W["supervisor.py：有界账户扫描"] --> S
    W --> M["matching.py：本地双侧撮合"]
    W --> SP["spot.py：独立现货撮合路径"]
    M --> S
    subgraph Authority["单个本地 SQLite 权威：WAL / FULL"]
        T["storage.py：BEGIN IMMEDIATE / COMMIT"]
        D["账户、订单、预占、仓位、分录、成交及 outbox"]
        T --> D
    end
    S --> T
    SP --> T
    D --> O["worker.py：OutboxConsumer"]
    O --> E["外部消费者：按 sequence 去重"]
    R["sharding.py：实验 ShardRouter"] -. "独立路由和屏障；不能将私有 shard 直接接入 batcher" .-> S
```

源码入口：[网关](../uta/gateway.py)、[服务](../uta/service.py)、[存储](../uta/storage.py)、[批提交](../uta/admission.py)、[监督器](../uta/supervisor.py)、[撮合](../uta/matching.py)、[现货](../uta/spot.py)、[outbox](../uta/worker.py)。图中共享一个本地权威不代表跨库原子性、跨区域复制或 HA。Outbox 的租约约束 checkpoint，不能 fence 外部回调；外部投递是至少一次。

## 2. 分组准入流程

```mermaid
flowchart TD
    Request["submit_order / cancel_order"] --> Validate["输入检查、队列容量、关闭状态"]
    Validate -->|拒绝| Reject["未入队失败；不能记作成功接纳"]
    Validate -->|入队| Queue["FIFO；撤单有保留槽但不插队"]
    Queue --> Collect["收集有界批次"]
    Collect --> Running["set_running_or_notify_cancel；跳过已取消命令"]
    Running -->|非空批次| Begin["BEGIN IMMEDIATE"]
    Begin --> Save["每命令 SAVEPOINT"]
    Save --> Check["原风险、幂等、预占及版本逻辑"]
    Check -->|预期业务错误| Undo["回滚当前 savepoint，保存拒绝结果"]
    Check -->|成功| Keep["保留当前命令变更，暂不发布回执"]
    Undo --> Next["下一命令"]
    Keep --> Next
    Next -->|还有命令| Save
    Next -->|结束| Fresh["有新接纳时再次核对行情时效"]
    Fresh --> Commit["外层 COMMIT"]
    Commit --> Publish["发布各 Future 的成功或业务拒绝结果"]
    Begin -->|技术异常| Unknown
    Save -->|技术异常| Unknown
    Check -->|技术或未知错误| Unknown["整组技术失败；按原 ID 查询 / 重试"]
    Fresh -->|失败| Unknown
    Commit -->|异常| Unknown
```

依据 `AdmissionBatcher._commit_batch`。业务错误有明确 allowlist；未知错误不是可忽略客户拒绝。提交前的行情检查不是对 COMMIT 后延迟的绝对保证。批次不是客户端原子多腿请求：一个命令业务拒绝不撤销同批其他有效命令。`committed_commands` 包含重试，不能替代唯一订单吞吐。

## 3. 回执与超时恢复时序

```mermaid
sequenceDiagram
    participant C as 客户端
    participant G as Gateway
    participant B as AdmissionBatcher
    participant D as SQLite
    C->>G: 原账户 / 订单 ID / 相同内容
    G->>B: submit_order，等待 Future
    alt 等待超时且 Future 尚未 running
        G->>B: cancel 成功
        G-->>C: admission_queue_timeout（未开始）
    else 等待超时且命令已 running
        B->>D: BEGIN IMMEDIATE + 逐命令 SAVEPOINT
        G-->>C: command_result_unknown（可能提交）
        B->>D: 完成事务并 COMMIT
        D-->>B: COMMIT 返回
        B->>B: 发布结果（连接可能已消失）
        C->>G: 查询或用原 ID、原内容重试
        G->>D: 经服务查询持久状态 / 幂等回执
        D-->>G: 持久结果（经服务）
        G-->>C: 返回查询或重试结果
    else 截止前完成
        B->>D: BEGIN IMMEDIATE + 逐命令 SAVEPOINT
        B->>D: COMMIT
        D-->>B: 成功
        B-->>G: Future 结果
        G-->>C: 成功或业务拒绝结果
    end
```

该图表示互斥情形而非每个请求都会提交。取消成功的命令不执行；批次仍可包含其他命令。技术异常的 `admission_batch_failed` 也不无条件意味着未提交。依据 `gateway._Handler._order_command` 与 `admission.py`；恢复时不能换新 ID 盲目重发。

## 4. 撮合、清算与失败边界

`ExchangeWorker.run_once` 先有界扫描账户并调用 `supervise_account`，再按产品调用 matcher。清算计划不是成交；无对手流动性时不能假造平仓。`Matcher.match_once` 在本地事务内读取订单、按价格/序号排序，执行双侧 `_apply_fill`，写唯一成交和审计事件，再提交。单侧拒绝回滚配对 savepoint；意外存储错误中止事务。它没有先发外部订单再回填本地状态的协议。现货走独立 `SpotExchange` 路径，不能把线性合约图当成全部产品实现。

分片撮合只在单片内执行，跨片转账未实现；借贷清算有明确阻断，不能把线性清算路径推广到所有负债。Cutover 回执的 `source_fence_verified` 为 false，不证明真实来源已停止写入。行情时间新鲜也不等于来源、价格或金融参数已独立认证。

## 5. 如何证伪这些图，以及仍然缺少什么

| 主张 | 对应证据入口 | 不覆盖的结论 |
| --- | --- | --- |
| 回执在 COMMIT 后 | `tests/test_admission.py`、`tests/test_admission_faults.py` | 网络收到成功前后不会发生任何故障 |
| 双侧本地结算 | `tests/test_matching.py`、`formal/explore_settlement.py` | 跨分片 / 外部交易所结算安全 |
| 结果未知可恢复 | 批提交与网关测试、独立进程故障测试 | 客户端换新 ID 后仍可去重 |
| 有界协议安全 | `formal/explore_group_commit.py` | 无限状态数学证明、生产金融签字 |

复跑命令和签核条件见 [acceptance-gates.md](acceptance-gates.md)。生产仍需闭合持续容量、混合负载、真实产品校准、复制与旧主 fencing、灾备 RPO/RTO、安全审计及真实责任人批准。不得把本页图示、模拟验收或 CI 绿灯当作实盘许可。
