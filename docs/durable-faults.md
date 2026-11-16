# 持久命令与写入者租约的独立故障验收

本组只修改独立测试与本报告，不修改运行实现，不复用生产保证金公式。
测试全部使用合成资金和本地临时 SQLite 数据库。测试通过不代表真实资金获准启用。

范围更正：前两批验证的是**当前 storage 版本创建、启用 managed 前已经存在的对象**，
不能用其 29 项通过结果证明真正旧二进制失效。第三批使用真实 `ad3f5b8` 旧源码，
在持久数据库 guard 修复前实际检出旧进程仍可写入，详见下文红态证据。

## 阶段与候选版本

基线为 `ad3f5b8`。第一批依赖：

- `c05e10ffc002b85206db043d6a879ec6a0309239`：存储层 managed fencing。
- `14237584150c2ec8bd94f6e46609bd0dedcc2b6f`：精确允许队列隐式索引与 sequence 初始化。
- `39157ad`：把行情与停机变更提取为可加入调用方事务的 helper。
- `a057362`：四种持久命令与原子终态回执。

第二批另依赖 `742ca91`（收紧租约 schema 控制）、`a175605`（真实分片进程）、
`7b1e432`（同事务还款 helper）、`ea9b12a`（持久还款）及 `5fced893`（暂停进程接管与
进程还款接线）。

第一批检查持久 ACK、资金事务、终态回执、旧写入者与恢复边界。
第二批已检查真实分片子进程、部分行情发布、分片缺失、资金 claim 不一致及还款链路。
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

第二批同样未跳过用例，完整重跑第一批与新增用例：

```text
Python 3.12.14: Ran 29 tests in 11.441s — OK
Python 3.10.22: Ran 29 tests in 11.511s — OK
```

预期的资金 claim 不一致用例会在子进程打印 `funding_registry_conflict` 异常栈；
该用例要求其同时持久化全局停机并保持财务状态，异常栈本身不是测试失败。

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
| `enabling_managed_mode_fences_existing_service_matcher_ledger_and_plain_database` | 用当前 storage 在启用前创建既有 `ExchangeService`、`Matcher`、`CreditService` 和账本对象；启用后这些对象和普通 `Database` 的真实资金写入都必须被存储层拒绝，逐表财务状态完全不变；当前合法写入者仍可完成双侧真实撮合与结算。此项不覆盖旧二进制。 |
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
这两项在四种命令候选上的独立运行已通过。分片子进程恢复、停机和还款的第二批结果如下。

## 第二批进程和还款矩阵

| 用例函数后缀 | 注入与验收 |
| --- | --- |
| `without_live_worker_ack_is_only_pending_and_has_no_financial_effect` | 未启动 worker 时下单和还款都只能返回 PENDING，无成功结果及财务变化。 |
| `ack_before_real_worker_kill_is_recovered_by_new_pid_and_generation_once` | 在事务外暂停实际 worker，入队收到 ACK 后强杀；supervisor 用新 PID 和更大 generation 处理原 ID，一笔订单、一笔接纳事件，不重复预占。 |
| `expired_sigstopped_shared_gate_owner_is_killed_so_publication_can_recover` | 用真实数据库写锁让 worker 持 SH 等待，确认锁归属后 SIGSTOP，释放数据库锁；租约过期后 supervisor 必须自行杀旧 owner、换 PID，发布恢复，测试不靠 SIGCONT 放行。 |
| `partial_publication_stays_halted_until_exact_publication_replay_completes` | 暂停一个事务外消费者，造成真实部分发布；全局保持 halted/publishing，新增风险被拒绝；换进程后重放同一发布，确认全部持久回执，再显式激活。 |
| `real_worker_quarantines_persisted_poison_and_then_processes_same_account_cancel` | 真正 worker 读取损坏的 PENDING kind，达到两次上限后隔离，再处理同账户撤单。 |
| `real_worker_quarantines_predecessor_then_repays_during_halt_without_quotes` | 全局停机且删除该分片所有报价后，真实 worker 先隔离毒命令，再完成利息 1、本金 3 的同币还款；重复原 ID 不增分录。 |
| `missing_managed_shard_is_not_recreated_and_persists_global_halt` | 活跃布局停止后删除分片；重开必须拒绝并持久化全局停机，不新建空金融库。 |
| `startup_with_missing_funding_claim_halts_instead_of_restarting_into_new_risk` | 控制库恢复为缺失资金 claim 的状态、保留真实分片资金回执；启动检测后持久化停机，不能靠反复换进程继续放量。 |
| `same_asset_repayment_is_available_during_halt_and_complete_quote_outage` | 合法 fenced writer 在停机、报价表为空时完成同币还款，利息优先，重复命令无影响。 |
| `repayment_postings_debt_cash_and_terminal_receipt_share_actual_commit` | 真正延迟外键在 COMMIT 失败，还款本金、利息、现金、分录和终态同时回滚；原 ID 重试只还一次。 |
| `missing_initialized_credit_is_technical_pending_and_never_fake_success` | worker 缺少绑定到同一 exchange 的已初始化 credit 服务时保持技术 PENDING，不返回虚假成功。 |
| `same_account_poison_quarantine_unblocks_repayment_without_funding_or_quote_dependency` | 同账户毒命令隔离后还款继续，停机与行情缺失不阻断用已结算同币现金还债；不允许无资金还款。 |

还款人工例子：客户原有 USD 1000，借入本金 10 后现金为 1010，计提利息 1；偿还 4
先还利息 1、再还本金 3。结果现金 1006，本金 7、利息 0，原资金池 50 在借出后为 40，
收回本金后为 43，利息现金为 1。独立用例分别检查这些余额和对应应收应付，而不是调用
生产还款 helper 计算预期。

## 保留的首次失败与修复证据

最初对任意运行位置直接 SIGSTOP，实际捕获了 worker 持共享发布锁而暂停的情况。
父进程的发布调用在等待 EX flock 时不能被 receipt timeout 打断，原 supervisor 又只检查
PID 是否存活。手动 SIGCONT 后旧租约正确拒绝写入，但原行情已过期，首次 23 用例运行
以一项发布恢复失败结束，耗时 84.072 秒。该记录没有被当作验收通过。

随后把“暂停消费者造成部分发布”与“暂停正在持锁的 owner”拆成两项，后者使用数据库写锁
和非阻塞 flock 探测确定复现。修复前的独立工具输出节选如下（不是完整日志）：

```text
FAIL: test_expired_sigstopped_shared_gate_owner_is_killed_so_publication_can_recover
AssertionError: False is not true : expired live PID retained SH flock: supervisor did not kill and replace the paused owner
Ran 1 test in 5.524s
FAILED (failures=1)
```

实现组在 `5fced893` 中加入只针对 supervisor 自己子进程、且持久 owner PID 匹配的
过期租约 watchdog，以及发布锁的超时。上述持锁暂停测试保持原恢复断言，随后在
Python 3.12 和 3.10 的 29 用例重跑中通过。

## 第三批：真正旧二进制的独立红态

使用完整提交 `ad3f5b894f96ed6857a061b71290047ae1d4d0e7`，本地优先执行
`git archive` 提取当时的 `uta` 包及 LICENSE。浅克隆缺少该对象时，唯一允许的替代是
带原 LICENSE 的固定归档，SHA256 为
`af1ffcbdb78d4f2c789f049cb4f3c61e75724a10a1f8f55d0d1ed09af1cda265`；
还须核对 provenance 的原提交。缺失、摘要错误或内容不符均使测试失败，不跳过，
也不加载当前实现代替旧实现。

真正旧进程通过 `python -I` 启动，并显式把提取目录放入 `sys.path`。
子进程返回实际导入文件路径与 SHA256，独立断言还固定核对：

- `uta/storage.py`：`ad0c34e97be43fa3a0ba648a84664f37a9944524dd4ab2802f20bdf0686c8feb`。
- `uta/service.py`：`980dddc853f23dd12625a112ae1d9f192473e1fd213db985462f209d160d6397`。

测试确认该旧 `Database` 没有 `for_writer`，不 mock storage，也不把当前版本的旧对象
作为旧二进制。两个独立场景为：

1. 旧进程先建立真实 `ExchangeService`、`Matcher`、ledger 并报告 READY，父进程再启用
   managed mode，然后释放旧进程分别执行 deposit、order、ledger post 和 match。
2. 父进程先启用 managed mode，再启动旧二进制，要求其不能重新初始化或完成任何金融写入。

修复前，以 `2c9431c` 的运行候选执行，两种场景的四项操作全部返回 `wrote`，且独立
只读财务快照都得到 `financial_changed=True`。原始完整日志暂存为
`/tmp/uta-actual-legacy-before-guard.txt`，SHA256 为
`846d574f1d0f69c5cad5c69b46fc58bbd2788aa5b4fdaa7d599446fa22b36416`，
供集成组归档；其结束输出为：

```text
Ran 2 tests in 0.422s
FAILED (failures=2)
```

此时不得宣称旧二进制已被 fencing。存储实现组正在加入持久触发器/UDF 和完整 guard
清单；独立测试保持“每次写入被数据库拒绝且财务状态完全不变”的原断言，等待候选后复跑。

## 阶段范围与未完成门槛

第一版持久协议支持 `SUBMIT_ORDER`、`CANCEL_ORDER`、`PUBLISH_MARKET` 和 `SET_HALT`。
第一版 `REPAY` 明确返回 `unsupported_durable_command`，不能声称已经验证持久还款链路。
这是第一批保留的历史边界。第二批已补 `REPAY` 并完成上述独立验证；当前未支持的
`WITHDRAW` 仍明确拒绝，不回落到同步旧写入者。借入、自动借币和跨分片划转不因这批
还款变更而获得持久命令支持。

本报告不替代金融规则负责人签字、24 小时长稳、真实清算成交容量、跨节点容灾或上线审批。
缺失这些证据时保留对应生产门槛的否决。
当前 watchdog 只处理仍由活 supervisor 持有的子进程身份。“supervisor 已死且孤儿 child
同时处于 SIGSTOP”不在本次恢复通过范围内；不能靠任意 PID 识别后直接杀进程来补证据。

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
