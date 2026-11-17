# 损坏 SQLite storage class 的失败诊断

`75240c1` 的新增诊断摘要假设 `kind` / `payload` 总是 Python str。SQLite TEXT affinity 允许原列保存 BLOB；内部坏行若包含 bytes，执行正确地进入技术失败，但 `record_failure` 中的 `.encode('utf-8')` 再抛 AttributeError，连 attempts / event 一起回滚，因而可能反复重启且无法隔离队头。这是已实际复现的诊断回归，不解释历史 `7200097` S1 根因。

本补丁只修复存储元数据、坏行 receipt 表达和一项遗漏的 additive 测试预期。客户 enqueue API 仍只接收规范 kind 和 JSON payload。测试通过内部 inbox append role 构造损坏行；它不代表客户 HTTP 可以提交 BLOB，也不绕过持久 SQL guards 或修改旧行 identity。

## 摘要与 receipt 契约

现有 TEXT 的 UTF-8 SHA-256 完全保持：`canonical_payload_sha256` / `command_kind_sha256` 不变。新增全局事件 v1 additive 字段说明原存储类型与摘要编码：

| 原 SQLite primitive | storage_type | digest_encoding | 摘要输入 |
| --- | --- | --- | --- |
| exact str | text | utf8 | 原文本 UTF-8，分块编码 |
| exact bytes | blob | raw_bytes | 原 bytes，直接分块摘要，不 decode |
| exact int，signed 64-bit 范围 | integer | signed_be64 | 8 字节有符号大端 |
| exact float | real | ieee754_be64 | 8 字节 IEEE 754 大端 |
| None | null | empty | 空字节；用 storage_type 区别于空 TEXT/BLOB |
| 其他对象 / 范围外 int | unsupported / integer | null | 摘要 null，不调用任何 coercion / str / repr / 属性 hook |

`stored_payload_sha256` 保存原存储 primitive 的上述摘要，配套 `payload_storage_type` / `payload_digest_encoding`。`canonical_payload_sha256` 对非 TEXT 为 null，不能把 BLOB 摘要或坏存储声称为 canonical JSON。TEXT 仍只证明已存原字节的摘要，不证明 canonical 校验通过。kind 配套 `command_kind_storage_type` / `command_kind_digest_encoding`，已知 TEXT enum 仍展示原值，其他种类在事件中为 null。

原 CID 的 `QueueStore.status` 和 managed HTTP receipt 对非 TEXT kind 返回 `kind=null`、`kind_status=typed_corrupt`、`kind_storage_type`。它是可 JSON 表达的坏行状态，不能解释为合法 command kind；PENDING 和 QUARANTINED 都能查询。正常 TEXT receipt 的字段集合和含义保持不变。库中原 kind / payload 的 storage class 和 bytes 完整保留，不自动修复、decode 或重入队。

失败诊断、attempt、退避/隔离仍在同一个 fenced COMMIT 内。坏行保持技术失败，达到既有上限才 QUARANTINED，同账户后续真实 cancel 随后 SUCCEEDED。金融公式、报价 TTL、风险拒绝分类和租约政策没有改变；异常前已提交订单、原资金/账本以及隔离前全部金融事实保持。

## 验证与回滚

真实 red 位于 [evidence/runs/diagnostic-storage-types](../evidence/runs/diagnostic-storage-types/)：从原 `75240c1` 运行 kind BLOB、payload BLOB、两字段 BLOB 三例，均在真实 `record_failure` 的 bytes `.encode()` 处失败。修复后同组验证原 BLOB 字节未改、两次失败各有唯一 event、同 attempt 重复记录幂等、隔离前全部金融/客户事件不变、HTTP 原 CID 可查，以及同账户真实挂单最终被后续 cancel 撤销。独立 helper 例验证公开编码、TEXT hash 兼容和恶意对象不触发 hooks。

原 gateway 隔离测试先严格核验唯一新增 global event 的 NULL account、v1、原 CID、attempt=1、QUARANTINED 与 failure class，再仅去掉该已核验类型比较原来全部金融表和全部原事件。保留原订单/预占/分录/仓位断言，不宽泛忽略 events。原冻结版本全测失败 raw 不在此工作树修改或覆盖。

没有新 schema / format 变更。部署回滚沿用 [failure diagnostics 的停机与原 CID 恢复流程](failure-diagnostics.md)：保留 immutable 新事件，旧全局消费者容忍 additive 字段。回滚至 `75240c1` 会重新暴露坏行诊断阻塞及 BLOB kind HTTP 表达缺口，不能声称该问题已在旧代码安全恢复。没有运行 benchmark、soak、旧 24h 作业或生产修复操作。
