# Grouped HTTP 结果未知与测试契约

原提交 `4608ffe` 的 push CI `44036919027` / Python 3.10 job
`133881910052` 在首笔 HTTP 下单返回 `503 command_result_unknown` 时，
测试直接要求 `201` 并失败。同一 SHA 的其他 CI 成功不能覆盖这次失败。
该测试统一配置的服务等待为 **50ms**，用于验证 queued cancellation 和 running
unknown；它没有给普通下单声明可靠的 50ms 完成 SLO。原失败没有该次队列/存储
快照，因此无法证明当时究竟是调度、存储或其他延迟。

本次未改服务、队列、等待、业务 timeout 或租约。正常链路测试将同一 order ID
和完全相同内容在有限客户端观察循环中重试，仅允许两种明确结果：

- `admission_queue_timeout`：尚未开始的 Future 成功取消，没有金融效果。
- `command_result_unknown`：已经开始，可能提交；按原 ID 和内容查询或重试。

其他 503、业务拒绝或权限错误不能冒充接纳。只有得到实际 201/200 后才断言成功，
并保留原订单查询、幂等回执、事件不重复、撤单、预占释放和存储重开的全部断言。
另核对恰好一笔接纳、一笔撤单、原现金与两笔初始入金分录。客户端循环在每次完成
请求后检查三秒观察预算；原单次 socket timeout 四秒和服务 50ms 均不变，
这不构成三秒物理端到端保证。

确定性反例使用原版测试文件的原字节，实际阻塞 running admission，收到真实 HTTP
UNKNOWN 后才释放 worker。原测试确实失败，而批事务随后真正提交一张 OPEN 订单、
一笔接纳事件。新测试走完整原 ID 重试、查询及撤单链路，不以 UNKNOWN 当已接纳。
这是原测试前提错误的可复现反例，不是原 CI 唯一延迟根因的取证。

原 gateway 各项 timeout/队列满/权限/业务拒绝测试仍独立执行。新增真实 HTTP
UNKNOWN 完整链路与修正用例共 13 项，在 Python 3.10/3.12/3.13 上实际通过；
原运行时没有变更。最初附加断言误用了不存在的 `account.cash` 字段，产生的
KeyError 日志也保留，随后改用真实 ledger balance 验证。相应日志、原版反例脚本
与 SHA 见 `evidence/runs/grouped-unknown-contract/`。

部署只更新测试/文档，不迁移数据库。回滚测试不修改权威状态，保留已有 CID
和未完成命令。生产容量、长稳、HA 与真实资金批准仍未由此验证。
