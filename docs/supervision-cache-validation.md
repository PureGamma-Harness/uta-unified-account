# NORMAL 监督缓存独立正确性验收

本轮只新增 `tests/test_supervision_cache_validation.py` 与本报告，不修改运行实现、PR9、
既有 freeze，或 4471/8784 持续任务的源码、目录与数据库。所有数据均为本地合成数据。

候选为 `190aa9ba8e99da2306a6dec3d1cc62e2cb93b9d8`，基线 `5c53f92`。
独立工作树 `/workspace/uta-supervisor-cache-validation` 的候选映射为 `97c7899`。
只验证该候选；没有把后续 engine 测试提交或别的运行变更混进证据。

结论：下述 14 项正确性场景通过。优化启用仍为 **NO-GO**，默认 `normal_cache_size=0`
应保留；本组没有提供持续混合负载收益、监督最坏复访时延或生产上线批准。
减少监督调用次数本身不构成验收。本组保留对启用缓存的否决权。

## 事务证明与审查边界

候选在同一个真实 financial transaction 中读取依赖、调用原监督逻辑、再次读取依赖，
仅在返回 NORMAL、持久状态也是 NORMAL、经济输入未变化，且外层 COMMIT 成功返回后，
发布该事务产生的 post-key。传入连接还必须由相同数据库 authority 所有。

本组首先提出的反例为：监督事务证明 A 是 NORMAL；其提交后、事后只读取 key 前，
另一个真正账本 writer 把 A 改成 B。如果把 B 的 key 与旧 NORMAL 绑定，下轮会错误跳过 B。
前后分离观察相等也不能替代事务证明或假定所有未来输入都不可能 ABA。

独立用例实际在监督 financial transaction 内启动另一个线程的 `DurableLedger.post`：
先证实它不能在该事务持锁期间提交，再在真实 COMMIT 之后、上下文返回 worker 之前强制
等待其扣款完成。账户现金从 10 变为 -1，account version 不变。下一轮必须重新监督并
变为 BANKRUPT，不能将事后只读 key 当作刚才 NORMAL 的证明。

缓存命中的比较点是该轮一致的只读快照 t0，不能称为随后每个时刻的当前风险。
候选在执行命中时再次检查行情年龄；matching、资金与订单准入仍走各自原有当前状态检查。
之后的金融写入最迟应在后续轮次重新读取时被观察。周期与排队造成的实际时延必须另测，
不能把轮次数上界直接换算成未经测量的毫秒保证。

审查确认 key 使用完整市场字节、持久配置及实际运行政策、全局 ledger head、真实账户
余额、仓位、挂单、gross debt、现货占用和 liquidation row。它不只依赖 account version。
配置和代码仍须按原服务协议通过新 service/进程部署，不支持并发热 `setattr` 或把旧 worker
重新绑定到另一 authority。这是验收前提，不是任意宿主篡改防护。

## 原始版本与候选的双重 golden

不能只比较同一候选的 cache=0 与 cache=8，避免共同的 join 重构错误被双方同时继承。
本组另外用 `git archive 5c53f92 uta LICENSE` 安全提取真实原始包，并在 `python -I`
下执行完全相同的十个财务检查点，保存全量业务表数据与摘要。

原始包文件 SHA256：

- `service.py`：`b10dc52b3eb4bde476f4dabc805c16a49729026f03e668a6069eccb8a0c39242`。
- `supervisor.py`：`3ba0bd8058016524d75c42411ae73682294fae2f9311cf46cdf0eeae0368ecb3`。

原始执行器 `/tmp/uta-supervision-reference-golden.py` 的 SHA256 为
`067d6c9dded1762852d8cd1e677814c88ba5015abd4b8c17fe759de6e3a8fe7b`；
完整业务快照 `/tmp/uta-supervision-reference-5c53-checkpoints.json` 的 SHA256 为
`151e6d90fed9632c80e902d469f8a2ad8d83eb9a9a79a594f173438f58c1235d`，供集成组归档。

实际原始版本执行命令：

```sh
python -I /tmp/uta-supervision-reference-golden.py /tmp/uta-supervision-reference-5c53 /tmp/uta-supervision-reference-5c53-golden.sqlite3
```

候选 cache=0 与 cache=8 在每一步既逐表比较，也必须匹配这些原始版本摘要：

| 检查点 | SHA256 |
| --- | --- |
| 开仓、开仓后监督、未变化 NORMAL（三步相同） | `c7e8b3634b965f381a1b4ebc6b4bb1acabe39fed0f8c475b3860bae9679f385c` |
| 跳价、没有对手流动性 | `8555af8880f2f9bffc5eb89b0e4650638c775eb3f06c5a22f95cadd90f4894c8` |
| 实际部分清算成交 | `245968f0026553a73c4e3ae912d26a070c9bd34e9612d68b7fe051ff8e1d6087` |
| 剩余仓位重新规划 | `0b851b35010be2db3c2cc569c5b230cadcd809c41507c2830115b0005884775b` |
| 资金救助恢复、稳定恢复、未变化恢复（三步相同） | `52fe5c38fa9b27b085942d53044de90fa19b5e2edf9b0d3db31f7371be21234f` |
| 借款、利息与真实还款 | `352c45bb021766b09274c7185b631a1e5c3fd5072de99de28e82af31efd2778c` |

这不是只比较调用数。快照保留现金、仓位、订单、资金账本、liquidation、业务事件和游标，
未丢弃业务字段。此基线原先重复 NORMAL 监督没有新增业务事件，因而本轮没有为了通过
而忽略所谓重复事件。

人工例子：本金 1000，90 单位以 100 开仓，费用 3.6，现金为 996.4。标记价到 90 后，
实际清算成交 45 单位，实现亏损 450、费用 1.62，现金为 544.78，剩余仓位为 45。
没有对手方时成交数为零，不生成假成交。后续救助恢复和 gross debt/interest/repayment
保留原始版本的全部分量。预期没有调用候选风险计算器生成。

## 14 项独立验证

| 用例后缀 | 独立断言 |
| --- | --- |
| `enabled_cache_and_original_path_replay_identical_financial_liquidation_and_event_state` | 真实原版本十检查点、候选 0/8、手算现金与部分仓位三者一致，含恢复取消清算单及真实借贷还款。 |
| `real_ledger_write_without_account_version_invalidates_normal_proof` | 真正 `Ledger.post` 不 bump account version，但现金 10→-1 后不能继续复用 NORMAL。 |
| `market_bytes_and_full_config_changes_invalidate_even_when_versions_do_not` | 配置字节变更及同版本有效行情内容变更都必须重新监督；跳价到 90 的真实仓位进入 LIQUIDATING。 |
| `live_spot_economics_without_account_version_are_part_of_the_key` | 有效现货金额行的投影变化不改 account version 或 ledger head，仍重新监督；锁定 200.08 后风险权益手算 799.92。 |
| `unversioned_position_and_gross_debt_projection_changes_cannot_reuse_normal` | 无版本的仓位成本或 gross debt 投影变化仍能分别识别 LIQUIDATING/BANKRUPT，不被旧 NORMAL 遮蔽。 |
| `normal_with_actual_spot_cancellation_is_ineligible_until_a_stable_proof` | 合法现货单占用全部现金，监督取消后虽然返回 NORMAL，但经济输入已变，不得缓存为未变化证明；稳定下一轮才可缓存。 |
| `proof_is_bound_to_financial_transaction_not_a_later_read_only_key` | 真并发 writer 在 proof 事务内阻塞，COMMIT 后立即完成扣款；下一轮必识别 BANKRUPT。 |
| `same_connection_join_rejects_a_different_database_authority` | 同名账户的另一个数据库连接不能被错误加入，两个 authority 的全部业务数据不变。 |
| `failed_or_unknown_proof_commit_does_not_publish_a_cache_entry` | 真实 deferred-FK COMMIT 失败、或真实 COMMIT 后响应丢失，两种情况 cache size 都必须保持 0，之后重新证明。 |
| `expiry_between_snapshot_and_cached_account_never_reports_fresh_normal` | t0 后排在前面的未缓存账户耗时使报价过期，后续旧命中不能仍报 NORMAL；新单 fresh gate 拒绝，合法新 tick 后恢复。 |
| `fair_cursor_advances_on_cache_hits_and_bankrupt_account_is_never_skipped` | 每批一个账户，四个账户十二轮严格公平推进；BANKRUPT 三次实际监督，正常缓存命中不吞占高风险复访名额。 |
| `liquidating_and_loan_blocked_accounts_are_supervised_on_every_unchanged_visit` | LIQUIDATING 和 loan-only BLOCKED 即使输入不变，三次访问都调用原监督，不缓存跳过。 |
| `bounded_capacity_clear_and_cold_restart_are_not_persistent_risk_authority` | 容量 2 有真实逐出；清空缓存、冷 service 重开都不改金融状态，缓存不是持久权威。 |
| `default_zero_is_reference_path_and_cache_settings_reject_boolean_or_unbounded_values` | 默认关闭，容量类型和上界明确拒绝非法值。 |

部分无版本投影变更是独立故障注入，用来检查完整依赖，不代表新增了公开修改仓位、债务或
现货订单的接口，也不声称这些故障行已通过完整迁移对账。

## 实际运行与原始记录

```sh
python -m unittest discover -s tests -p test_supervision_cache_validation.py -v
/tmp/uta-python310/cpython-3.10.22-linux-x86_64-gnu/bin/python3.10 -m unittest discover -s tests -p test_supervision_cache_validation.py -v
/usr/bin/python3.13 -m unittest discover -s tests -p test_supervision_cache_validation.py -v
```

```text
Python 3.12.14 / SQLite 3.53.1: Ran 14 tests in 1.476s — OK
Python 3.10.22 / SQLite 3.53.1: Ran 14 tests in 1.351s — OK
Python 3.13.5 / SQLite 3.46.1: Ran 14 tests in 1.270s — OK
```

首次 13 用例跑出五个 snapshot 子断言失败，原因是测试把 `sqlite3.Row` 按包含内存地址的
repr 排序，造成无意义顺序差异。只改为保留全部列的 tuple 内容排序，没有改风险预期或
忽略财务字段；原始首跑日志仍保留，不把这个 fixture 问题归因给运行实现。

完整记录及 SHA256，供集成组归档：

- 测试文件：`1718082319a5596ffd0af22acbe54fd6093ed3eb2a2e7ba1b5c49a46898afb22`。
- `/tmp/uta-supervision-cache-independent-first.txt`：
  `9804d2fb0f280a847a2bc1351b79abccea0b15f6a0f55bc4d452038ed34253de`。
- `/tmp/uta-supervision-cache-independent-golden-py312.txt`：
  `5bd802774bd40c99853ce30a8b84eb5f5d7a10800045037fae53b3ee6a3df4f6`。
- `/tmp/uta-supervision-cache-independent-golden-py310.txt`：
  `c30d18cbf63e9a952be778ad34c71d11822de8664ad3dc5f842aec74b94fe871`。
- `/tmp/uta-supervision-cache-independent-golden-py313.txt`：
  `9d68796af5d5ebaae8978b5948cd5c98f9f6f7d1691a3f37ce8e89d8ce27fae1`。

这些秒数只是正确性测试运行时间，没有 skip 或预期失败，不是性能提升证据。

## 启用门槛与回滚

14 项通过只覆盖该版本、上述线性 USD 场景与相关现货占用/借贷状态。新增产品、模式和
真实 managed 子进程启用仍需其独立产品验收；实现组自己的集成测试不能冒充本组独立结果。

启用前至少需要在真实混合账户、行情更新、成交和 ledger-head 持续变化的流量下，保存
吞吐、尾延迟、快照时长和风险实际复访年龄。全局 ledger head 变化会保守失效所有账户，
不能把完全静止的 NORMAL 工作负载命中率外推为活跃交易的收益。

默认 0 可作为原路径回滚方式。停止入口、保留并对账在途动作后，以新 worker/进程禁用
缓存即可，不需要改账、释放预占或删除风险状态。不得热改现有 service 配置、共享跨 authority
缓存，或把缓存 NORMAL 当作金融接纳、清算完成、当前行情或租约权限凭证。
