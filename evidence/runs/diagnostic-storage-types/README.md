# SQLite storage-class 诊断回归：真实 red / green

基线 `75240c14122948ddfb94a203eb6130c6136fbc24`，隔离 worktree `/workspace/uta-diagnostic-storage-types`，分支 `fix/diagnostic-storage-types`。所有 runner 绑定单 CPU，使用新的实际 UTC 目录与 `open('x')`，没有覆盖已有 raw；未运行 benchmark 或修改冻结全测失败目录。

`red-20261117T070746Z`：运行时代码保持原 `75240c1`，三个新坏行用例全部真实 ERROR；kind BLOB、payload BLOB、双字段 BLOB 均进入 `record_failure` 后在原 `_payload_digest(...).encode('utf-8')` 抛 AttributeError。raw 保留完整 traceback，invocation 保留命令、时间、基线与退出码。

`green-20261117T070957Z`：**45/45 通过，6.182 秒**。覆盖新 storage 类型 / HTTP / 同账户真实 cancel、新 failure diagnostics、原 durable commands 和完整 durable gateway。invocation 保留实际 UTC、完整 argv、单 CPU affinity、base head、被测源码 SHA-256 与退出码。没有把这次短测试等同吞吐或生产批准。

新测试通过内部 inbox role 直接 INSERT 损坏行，客户 JSON enqueue API 无该输入方式；持久 SQL guards 保留。它们核对原 BLOB 字节和 storage class、正常 TEXT hash兼容、原 CID HTTP JSON 表达、两次有界 attempt / immutable global event、重复记录幂等、隔离前全部原金融与客户事件相等、隔离后同账户旧挂单真实撤销、账本事件数量保持一笔初始资金。恶意未知对象不调用 str/repr/属性 hooks。

gateway 原 additive 预期遗漏已最小修正：唯一新增诊断的 CID、attempt、NULL account、v1、QUARANTINED 和 failure class 分别断言后，只排除该新增类型再比较全部原事件及全部原金融 rows。独立冻结版本全测的原 1FAIL raw 原地保留，不在此证据目录伪装为原 red。
