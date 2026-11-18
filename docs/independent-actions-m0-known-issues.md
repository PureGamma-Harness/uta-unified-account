# M0 控制候选已知缺陷与资格边界

PR22 原 run [44162304965](https://github.com/PureGamma-Harness/uta-unified-account/actions/runs/44162304965) 的 Python3.11.18 / SQLite3.46.1 报告为1801测试、0 failures、1 error、0 skipped、passed=false。原merge commit为 `289ca5d05585ba5fd981a6e11ac2cf8b98d6672e`。没有重跑该run，原错误不能用别的成功jobs或后来重跑结果抹去。

原测试 `test_expired_stopped_owner_holding_shared_gate_is_killed_and_publication_recovers` 标记 ERROR，同时 `uta-process-supervisor` 线程出现 `_supervise → _spawn → _record_process → storage._connect` 栈，在 `PRAGMA journal_mode = WAL` 报 `sqlite3.OperationalError: locking protocol`。该消息被集成组归类为SQLITE_PROTOCOL；原stack未记录numeric sqlite_errorcode，不能伪称已测得错误码。这里记录共同观测，不将未经验证的根因猜测写成结论。独立组正在另分支修复与验证停止owner后的恢复缺陷。

安全摘录只保原559–591行，并将runner checkout/stdlib根路径替换为标记；没有发布private原件路径、完整原日志、artifact ZIP、plugin签名URL、数据库或密钥。原archive 92,276字节，SHA256 `9ea4bae56cd6c2697cd613972bbcbf56c0fc3bffbd3c720313fc740ca66eaffc`，CRC/provider digest由集成组核过；本候选只读取原summary/worker-result/unittest，不重跑测试。精确计数、原文件hash和摘录hash见 `docs/evidence/independent-actions-m0/known-pr22-311-selected-evidence.json`。

本候选仍用exact source909。其历史八个CI jobs成功属于原报告范围（push44132222411、PR44132321549），不是无限可靠性证明。PR22的新失败所涉运行时与source909逐文件相同；原报告348项测试源指纹与source909相同，不包括后来新增的10个benchmark JSON，不能将“348项相同”扩为所有仓库文件相同。source909的62个runtime、完整source tree及独立原报告关联另有精确指纹。

独立receipt、四流预算、strict CMS协议组件关闭只说明各自已验证范围，不解除此恢复缺陷，也不证明远端runner兼容、actual M0、artifact耐久、容量或HA。本地最终控制C只整理证据与审批合同，controller/module/workflow和source909字节保持已审版本。实际once marker仅为独立外部PROPOSED JSON；没有创建M、literal触发分支、push或dispatch。

如果集成负责人后来批准一次M0，也只允许合成低量单机本地SDK诊断：B/P各10秒、20/s、100账户、2shards、同1CPU、未启用PR20优化；不是真实撮合成交压测。该批准不能把原PR22 error改称通过。所有 `production_approved`、`capacity_10000_per_s_passed`、`ha_approved`、全产品上线资格始终false/NO_GO。不得通过重跑CI、改测试跳过或隐藏monitor异常获取资格。

回滚为不创建/不push实际M，保持旧source与所有长任务不变；本说明与原始失败证据永久保留，新修复另提交、另验收。
