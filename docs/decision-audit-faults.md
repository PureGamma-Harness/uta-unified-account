# 历史决策审计独立故障验收

本轮只增加 `tests/test_decision_audit_faults.py` 和本报告，不修改运行实现。
全部测试使用独立临时目录和合成资金，不读取或修改真正运行的 24 小时任务目录或源码。

## 固定版本及红态证据

起点为 root `f1f3e89`，依次摘入 `254bd33`、`40faaa6`、`ec94ce4`。
本工作树对应提交为 `fec9b81`、`3c57e22`、`4d97e9f`，路径为
`/workspace/uta-audit-faults`。没有接入同期 HMAC、控制面 DDL 或离线审计升级的新候选，
避免不同阶段结果混用。

复跑命令：

```sh
python -m unittest discover -s tests -p test_decision_audit_faults.py -v
```

固定候选的独立结果：

```text
Ran 12 tests in 1.262s
FAILED (failures=1)
```

真实失败为 `test_valid_names_with_weakened_required_reference_guard_fail_closed_without_repair`：
把 `audit_order_requires_decision` 保留原名和对象类型，但把内容换成 `BEGIN SELECT 1; END`，
再以 required audit 构造服务时没有拒绝。`DecisionAudit.validate` 当时只核验名字与类型，
因此没有证明必要引用 guard 的实际约束仍存在。

完整原始日志为 `/tmp/uta-decision-audit-faults-fixed-red-12-final.txt`，SHA256 为
`c092c12ff459b86b80cffeacc206cb0c264fd36c47effdcca3a40e64336855a6`。
较早八用例的同一缺口日志为 `/tmp/uta-decision-audit-faults-fixed-red.txt`，SHA256 为
`c7ca7201d6562ab288219385390386b5b6f53ac28095768cbe1570eecb1d3977`。

两个初次测试适配问题也保留在 `/tmp/uta-decision-audit-faults-fixed-first.txt` 和
`/tmp/uta-decision-audit-faults-fixed-red-12.txt`：市场故障 wrapper 最初遗漏 `payload`
关键字；真实旧 fill 还会因为 schema-3 新列造成 SQLite 列数拒绝，而不只触发
IntegrityError。修正仅透传原参数并接受真实 SQLite 拒绝链；仍要求旧进程全部操作被拒绝、
新引用不能缺失且完整财务状态不变，未降低业务预期。

## 独立矩阵

| 用例后缀 | 注入与独立断言 |
| --- | --- |
| `failed_explicit_upgrade_rolls_back_schema_columns_archives_and_capability` | 真正延迟外键在 schema-2→3 COMMIT 失败；schema 标记、ALTER 新列、档案和能力记录全部回滚；随后明确升级成功，默认旧模式不能重开 schema 3。 |
| `partial_audit_metadata_does_not_trigger_automatic_upgrade_or_repair` | schema 2 已出现部分档案表时拒绝，完整 schema 与数据保持不变，不推断为空系统后自动修补。 |
| `real_commit_failure_rolls_back_order_and_decision_then_original_id_converges_once` | 真实订单和审计行已暂存后制造延迟外键失败；全部回滚。原业务 ID 重试只有一笔订单、一条决策，预占人工值为 10.04。 |
| `paired_match_commit_failure_rolls_back_two_sides_ledger_and_all_decision_refs` | 双侧真实撮合、资金分录和两条成交决策完成后在 COMMIT 失败；整批回滚。恢复后只有一笔匹配、两笔成交和四条接纳/成交决策，两客户现金分别为 999.96。 |
| `match_commit_response_loss_reopens_with_exact_receipts_and_no_duplicate_audit_or_cash` | 真实 COMMIT 后丢失响应；冷重开查询匹配及原 fill ID，不能重复现金、仓位、匹配回执或审计行。 |
| `market_publication_commit_failure_rolls_back_full_history_current_quote_and_event` | 归档完整行情并更新当前报价后制造真实 COMMIT 失败；历史、新当前价和事件一起回滚。 |
| `valid_names_with_weakened_required_reference_guard_fail_closed_without_repair` | 同名、同类型但弱化的必要引用 guard 必须明确拒绝，不自动重建；固定版本首先检出红态。 |
| `historical_market_code_and_policy_body_corruption_never_returns_replay_matches` | 分别改变历史行情、代码 manifest、政策原始字节并恢复原 guard，再回放必须拒绝摘要不一致，不返回成功匹配。 |
| `real_sqlite_full_after_decision_insert_never_commits_an_order_without_its_audit` | 使用真实页数上限和 blob 分配，确认审计行已插入后触发真正 SQLITE_FULL；异常链保留 SQLite 原因，完整状态回滚，原 ID 仅恢复一次。 |
| `identical_math_from_a_different_real_source_release_is_not_an_authoritative_replay` | 将候选包复制到新发布目录，只追加不改变数学的源码注释；真实隔离子进程必须返回 `replay_engine_mismatch`，不能凭相同数值公式宣称权威回放。 |
| `same_source_under_an_actual_optimized_interpreter_cannot_replay_unoptimized_artifact` | 相同源码用真实 `python -I -O` 启动，必须拒绝未优化解释器记录的严格 artifact，不计算并返回 matches。 |
| `actual_ad3_process_held_before_upgrade_cannot_insert_orders_or_fills_without_required_refs` | 用带 LICENSE、固定 SHA256 的真实 ad3 源码包启动隔离旧进程，先构造对象后 READY，再升级 schema 3；旧下单、fill 和匹配都须有真实 SQLite 拒绝链，且包括新审计表的全库快照完全不变。 |

最后一项刻意不启用 managed writer fencing，用来单独验证 schema-3 必需引用与旧协议
边界，不把“另一个 fencing 层拒绝”冒充成 audit guard 自身的证明。它也不宣称审计
能力覆盖存款、现货或新借款决策；实际 managed 产品仍必须同时启用持久 writer guard。

人工财务例子使用 USD 8 位精度、单价 100、数量 1、IM 10%、手续费率 0.04%。
订单预占为 `10 + 0.04 = 10.04`，每侧一次成交手续费为 0.04，原现金 1000 后为 999.96。
独立断言使用这些人工值与逐表快照，没有调用生产计算器生成金融预期。

## 修复复测及交付边界

集成负责人已提供 `f8d96e8`，将安装和验证使用的 guard 定义统一，并核验 SQL、所属表和
完整 `audit_*` inventory；本组将在保留原断言下摘入后重新验收，结果在完成后补充。

升级属于明确的数据能力切换。失败时保持 schema 2；成功后不能删除引用、降低标记或启动
旧金融 writer 作为回滚。事故回滚须停止入口，保留原命令和证据，以兼容审计版本只读导出、
对账或从一致备份恢复后再决定激活。

本轮只验证已覆盖的线性接纳/成交历史证据及故障事务边界；回放是数值重估，不是重新提交
历史交易。摘要和严格代码身份是本机无签名证据，不是外部签名或对恶意宿主的证明。
容量、24 小时稳定性、跨节点恢复、未覆盖产品和真实资金启用审批仍需独立门槛。
