# PR43 首轮 CI：两矩阵成功，原日志范围限定为两个 job

结论：**首轮普通 CI 证据复核通过，仅限参考实现范围。** PR43 的 source C 为 `d8a6c7b4a150c7bd2fa07ce28272840089e47dfc`，base 为当前 main `02549e5d662caa7156dc30e95f1d5e2dce18215c`。预期 merge `95f37509541c0a4a5a21f7a97e2e2fa2a61436be` 的 parents 正是 base/C，tree `36a7270fbd0dfe724a98ad6481f9c411aa93b689` 与 C 相同；两个 commit 的资格仍分别记录。

| 首轮 attempt1 | run | Python 3.10 / 3.11 / 3.12 | 已取原日志 |
| --- | --- | --- | --- |
| push exact C | 44256882640 | 三个 job 均 success | 仅3.12 job134640582592 |
| PR expected merge | 44256926391 | 三个 job 均 success | 仅3.12 job134640732015 |

已保存的 provider metadata 中，六个 job 的 unit、demo、四分片 scenario 重开回放及 bounded reservation model 四个步骤均 success。没有为本次复核重新查询 API、下载、触发或重跑 CI。其余四个 job 仅有 metadata；本文不声称已检查全部六份日志或已逐项核对其测试数量。

两份已取日志分别为45331字节/SHA256 `d21fa1bf5cccc9bc2066214a10eb6d579b71040e7db9158663a50f5fa6d725c8` 与46195字节/SHA256 `500dc445c7a4d70b00794631506fa38bb3779764c06e90634a134ca285a41b64`。它们与私有 connector 解码内容的 UTF-8 字节完全相同，包含原 BOM/换行，不冒称 HTTP wire bytes。公开副本不截断、不重排或修改原文。

两份日志的 git log -1 输出分别确认实际 checkout 为 C 和预期 merge。每份原日志均有73个实际 ok、73tests/0FAIL/0ERROR/0skip，四个新增 LedgerSequenceIntegrityTests 方法各出现一次 ok；unit 原始时间分别0.683s、0.901s。日志的 setup-python 记录 CPython3.12.16；没有采集完整 sys.version、SQLite或可执行文件指纹，不能用本地3.12.14的结果代签。此简单 workflow 也未采集独立的 source 前后哈希图。

demo 原样声明 Illustrative only; no real orders or exchange connection。两份 scenario 日志均执行 --shards4，并返回重开后 replay 的 demo/version6/events_verified7，scenario共6步；源代码对应重新构造 Simulator 并校验记录事件与当前状态。两份 formal 输出均为 Safe abstraction:2628 reachable states, invariants hold。这是有界模型和合成参考模拟的结果，不能提升为生产结算、分布式故障恢复或无界财务证明。

仅对这两份拟公开原日志做了定向隐私检查：GitHub token、私钥 PEM、签名 URL、JSON nonce/secret/signature/凭据值和 secret 环境赋值五类匹配均为0；各自唯一 Authorization 值均仅为已掩码的 basic***。这是限定范围的检查，不是任意秘密不存在或全量安全审计的证明。七份原 connector JSON 保持私有，仅公开最小状态投影和九份原件的长度/SHA256。没有公开 headers、实际 token/nonce、数据库二进制或下载签名引用。

本次只读九份原件共271148字节，目录0700、文件0600，通过 NOFOLLOW/NOATIME 与稳定元数据核对。复核只做 Git/text/JSON/AST/字节检查，没有执行目标、测试、SQL、proc/PID、探针或网络。CI 中参考 scenario 的运行与本次本地复核动作分开记录；前者不能替代生产账本验收。

回滚沿用现有 [ledger-sequence-integrity.md](ledger-sequence-integrity.md) 的边界：只回退这次校验代码，无数据迁移或历史分录重写；回退会恢复旧版更宽松的序列处理，不能据此批准损坏历史。本文只补充首 CI 证据，不改既有代码、参数、原始计划或前序结果。此前4方法/14个源码关联案例与本次普通 CI 是不同结果；没有真实资金、生产或完整 UTA 平台验收授权。

原日志中的11处行尾空格按原字节保留（push两处、PR九处），不为样式检查改写首原件；其余新增文档与JSON单独通过diff检查。
