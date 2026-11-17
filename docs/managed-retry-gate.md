# Managed probe：所有持久CID的技术诊断与停止门

原7200097的S1最终有321个门控拒绝，其中 `bench:684` 曾发生内部技术重试1次。
其最终 `market_unavailable(503)` 是安全拒绝，不能抹去 `attempts=1` 与
`last_error=technical_execution_failure`。原summary只计enqueue/poll错误，实际runner因此
漏过该诊断。本修复只改benchmark工具、测试和文档；不修改金融runtime，也不修复尚无
原异常取证的内部故障。原720源码、私有DB和全部已测raw/manifest保持不变。

最终只读复开现在读取每分片**所有**inbox CID，包含SUBMIT_ORDER、PUBLISH_MARKET和
SET_HALT。`command_technical_diagnostics`单独输出内部attempt总数、受影响CID数、
last_error、QUARANTINED、未终态和未成功控制命令；同一命令的重叠诊断不相加成新的业务
outcome。`terminal_error_code/status`仅描述最终结果，不冒称原内部异常原因。

`outcome_counts`每个计划到达恰好一个结果，其总数等于offered。已有`counts`保持兼容，
其中ACK和financial_success_late仍是重叠字段。技术诊断不将已提交的金融成功改成业务拒绝，
也不将安全拒绝重分配成“技术失败笔数”；两类证据分别可审查。

`probe_qualification`是技术停止门。任何内部attempt、last_error、quarantine、未终态CID、
未成功行情/控制CID、enqueue/poll/feed错误、unknown/timeout或复开pending差异都使其
失败并要求停止后续case。缺少全CID诊断的旧summary亦不能默认为通过。控制命令的REJECTED
不能按客户普通router_halted拒绝放行。1秒金融迟到另有financial_soft_deadline_passed，
技术门通过也不等于延迟、稳定性或生产通过；三个生产/容量/稳定性字段始终false。

CLI在完整summary、raw、manifest保存后，技术门失败以退出码2结束。直接调用`run()`的
使用者仍得到可审查summary，应检查该门后再启动下一case。异常中断仍保留原authority，
不换新CID补业务效果。回滚旧工具会重新引入已知漏报，应暂停后续负载或保留独立全CID
审计，不能只以旧CLI退出0判断资格。

固定证据测试锁定原S1 gzip SHA256
`689ab5d8fe261b75b0cb57d18f37e676d5977cc8e059862df5984e2801ab2a53`，
字面验证1000请求的508/58/321/113和418迟到，唯一bench:684/attempt1/原错误；
不调用生产分类器产生这些期望。补充用例覆盖成功后重试、控制lane、无attempt但有last_error、
未终态/终态失败控制CID、诊断重复输入和CLI非零退出。既有真实spawn/审计/只读对账与
ACK丢失断言继续保留；新单到达时钟、排空、TTL及风控参数没有改动。

独立静态peer指出未终态控制CID原可漏过，本次补全全CID状态门和对应测试。
本轮没有启动新的B/P/S负载。进一步性能执行仍须原异常取证方案、新固定源码资格及GO。

最终18项focused在单CPU顺序通过：Python3.10.22/SQLite3.53.1为1.604秒，
3.12.14/3.53.1为1.556秒，3.13.5/3.46.1为1.630秒。原始日志、源码hash与纯RO事后
重放在 [evidence](evidence/managed-retry-gate-20261117/manifest.json)。
原五case总持久CID数含控制lane分别220/220/220/216/907；新门对B1/B2/B3/P1通过，
对S1拒绝且仍保留1次内部attempt、1个带last_error的原CID和原互斥业务分类。
这只是用新工具评价旧事实，没有更改原summary或产生新的性能结果。
