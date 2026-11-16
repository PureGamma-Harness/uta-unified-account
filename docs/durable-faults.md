# 持久命令与写入者租约的独立故障验收

本组只修改独立测试与本报告，不修改运行实现，不复用生产保证金公式。
测试全部使用合成资金和本地临时 SQLite 数据库。测试通过不代表真实资金获准启用。

## 阶段与候选版本

基线为 `ad3f5b8`。第一批依赖：

- `c05e10ffc002b85206db043d6a879ec6a0309239`：存储层 managed fencing。
- `14237584150c2ec8bd94f6e46609bd0dedcc2b6f`：精确允许队列隐式索引与 sequence 初始化。
- `39157ad`：把行情与停机变更提取为可加入调用方事务的 helper。
- `a057362`：四种持久命令与原子终态回执。

第一批检查持久 ACK、资金事务、终态回执、旧写入者与恢复边界。
第二批检查真实分片子进程、部分行情发布、分片缺失、资金 claim 不一致及还款链路。
24 小时稳定性和容量测试由性能组单独安排，本组不以短故障测试替代这些门槛。

复跑第一批：

```sh
python -m unittest discover -s tests -p test_durable_faults.py -v
```

2026-11-16 UTC 独立执行，未跳过用例：

```text
Python 3.12.14: Ran 17 tests in 5.025s — OK
Python 3.10.22: Ran 17 tests in 4.883s — OK
```

上述时间仅为故障测试运行时间，不是延迟或吞吐性能结果。

## 必须保持的语义

`ack=durably_queued` 只证明命令已进入持久队列；`state=PENDING` 不证明订单被接纳，
也不证明保证金已预占。只有资金业务变更与 `SUCCEEDED` 回执在同一事务提交后，
查询才可报告业务成功。明确业务拒绝使用 `REJECTED`；存储错误、结果未知与毒命令
不能伪装成业务拒绝。结果未知时先按原命令 ID 查询，再决定是否重试。

每个账户内按命令序列处理。同账户的后续撤单不能绕过尚未解决的前序命令；
毒命令经过有限次技术重试后进入 `QUARANTINED`，随后撤单可继续。
其他账户不应被一个账户的退避阻断。不能把隔离误报为订单成功或资金已处理。

人工可复算的订单例子为：USD 8 位小数，标记价和限价均为 100，数量 1，
IM 为 10%，手续费率为 0.04%；独立预期预占为 `10 + 0.04 = 10.04`。
仅接纳订单不产生现金分录。测试分别核对订单、账户版本、逐笔事件、资金账本和终态回执。

## 第一批故障矩阵

以下函数均位于 `tests/test_durable_faults.py`，已在上述两个 Python 版本实际通过。

| 用例函数后缀 | 注入与验收 |
| --- | --- |
| `enabling_managed_mode_fences_existing_service_matcher_ledger_and_plain_database` | 在启用前创建旧 `ExchangeService`、`Matcher`、`CreditService` 和账本对象；启用后旧对象和普通 `Database` 的真实资金写入都必须被存储层拒绝，逐表财务状态完全不变；当前合法写入者仍可完成双侧真实撮合与结算。 |
| `managed_ledger_rejects_a_raw_unguarded_sqlite_transaction` | 把未受管的原始 SQLite 事务传入公开账本接口，必须拒绝，不能借用 connection 绕过租约。 |
| `token_bound_writer_cannot_fall_back_to_legacy_after_restoring_pre_enable_database` | 原路径恢复启用前的整库备份后，已有 token 的写入实例不能因为 managed marker 缺失退回 legacy 写入。 |
| `two_real_processes_cannot_share_live_lease_and_expired_owner_cannot_resume_writes` | 两个真实 PID 争用租约；第二进程先收到 busy，过期后取得更大 generation；旧进程继续运行时资金写入失败，当前新 generation 可写。 |
| `lease_expiring_after_financial_dml_rolls_back_at_commit_checkpoint` | 在真实财务 DML 后把受控租约时钟推进至过期边界；COMMIT 检查必须回滚整个事务。 |
| `same_owner_nonce_cannot_reuse_released_generation_and_pid_bound_token_cannot_transfer` | 同 owner nonce 重取租约仍必须提高 generation；已释放旧 token 和传给另一个 PID 的 token 都不能写入。 |
| `enqueue_ack_survives_real_process_exit_and_never_claims_risk_acceptance` | 子进程收到持久排队 ACK 后执行 `os._exit`；恢复仍能查原序列，期间无订单、预占或资金变更；合法 worker 后续只处理一次。 |
| `enqueue_ack_is_not_published_before_actual_metadata_commit` | 暂停真实队列 COMMIT；生产者不能提前返回 ACK，另一个只读连接也看不到暂存记录。 |
| `real_worker_exit_after_dml_before_commit_and_after_commit_retries_original_id_once` | 分别在完整财务 DML 后、COMMIT 前及 COMMIT 后执行 `os._exit`；前两种恢复为 PENDING，后一种恢复为 SUCCEEDED；重启按原 ID 收敛且不重复预占、事件或分录。 |
| `lost_commit_response_cannot_be_overwritten_as_retry_or_business_rejection` | SQLite 已提交后抛出连接回执异常；失败记录逻辑必须先查终态，不能把已成功命令改为重试或业务拒绝。 |
| `real_sqlite_full_after_financial_dml_leaves_pending_then_recovers_once` | 用真实 `max_page_count` 和 blob 分配触发 SQLite FULL，要求异常链包含真正 SQLite 错误；财务状态回滚、原命令仍 PENDING，解除容量限制后原 ID 只处理一次。 |
| `real_deferred_constraint_commit_failure_rolls_back_financial_and_terminal_receipt` | 真实延迟外键在 COMMIT 时失败；财务 DML 与已暂存 SUCCEEDED 回执必须同时回滚。 |
| `unavailable_database_cannot_ack_more_work_or_lose_existing_ack` | 暂时把数据库路径替换为目录，真实打开失败；不能 ACK 新命令，原库保持不变；恢复原路径后旧 ACK 可继续处理。 |
| `poison_is_bounded_other_accounts_progress_and_same_account_cancel_waits_for_quarantine` | 技术毒命令退避期间其他账户继续，原账户撤单等待前序隔离；达到上限后毒命令为 QUARANTINED，撤单成功且无毒订单残留。 |
| `unsupported_commands_and_capacity_are_explicit_and_never_fall_back_to_sync` | 未实现 kind 明确拒绝且不写队列；普通容量与撤单保留容量有界，满载返回技术过载，所有 PENDING 命令均不产生资金影响。 |
| `producer_metadata_role_cannot_forge_replace_or_update_terminal_receipts` | 直接使用生产者元数据事务插入伪造终态、更新或 REPLACE 真实终态及 REPLACE 配置，都必须在存储层被拒绝；原回执和财务状态不变。 |
| `restart_with_missing_inbox_or_guard_refuses_to_recreate_history` | 重启遇缺失 inbox 或保护触发器时拒绝；不得自动 CREATE 修补后把丢失历史误认为空队列。 |

静态交叉审查提出了两项边界：生产者 INSERT/REPLACE 不能伪造终态，
以及 token 绑定实例遇缺失 managed marker 不能退回 legacy。实现由对应工作组修复，
本组保留独立断言，只有实际运行通过后才关闭该项。
这两项在四种命令候选上的独立运行已通过；分片子进程上的相同恢复边界仍待第二批验证。

## 未完成门槛与还款范围

第一版持久协议支持 `SUBMIT_ORDER`、`CANCEL_ORDER`、`PUBLISH_MARKET` 和 `SET_HALT`。
第一版 `REPAY` 明确返回 `unsupported_durable_command`，不能声称已经验证持久还款链路。
集成负责人正在补同事务还款与保留容量；完成后本组须独立验证：毒命令隔离后还款继续、
停机或行情中断时同币还款、利息优先顺序、本金与利息冲销分录和队列终态原子提交，
以及没有活 worker 时只能返回排队状态。

本报告不替代金融规则负责人签字、24 小时长稳、真实清算成交容量、跨节点容灾或上线审批。
缺失这些证据时保留对应生产门槛的否决。

## 部署与回滚边界

启用 managed mode 是持久的权限切换，不能通过删除租约表、撤掉 schema guard 或
把应用切回普通 `Database` 实现回滚。先停止新入队，按原命令 ID 查询所有未知结果，
保存完整数据库及队列快照，停止旧 worker，待租约明确释放或到期，再让新进程取得
更大 generation 后恢复；对账通过后才恢复客户流量。

恢复须使用一致的财务、队列、控制面、资金 claim 和分片身份备份，禁止单独恢复旧控制库、
删除未决队列或更换新业务 ID 掩盖未知结果。出现 marker、schema、身份、claim 或行情
发布屏障不一致时保持停机，经过调查和明确激活后继续。

覆盖的故障模型是同一 Linux 主机、同一 boot identity、可信单调租约时钟及本地 SQLite
WAL/FULL。子进程退出验证进程崩溃恢复，不证明硬件断电、复制共识、跨主机 fencing、
任意历史整库回滚检测或 HA/RPO/RTO。普通无 token 实例面对完全恢复到启用前的整库，
若没有外部授权记录，无法仅凭该库推断过去曾启用 managed mode；运行部署必须保留
独立的模式与恢复授权边界，不能把该假设隐去。
