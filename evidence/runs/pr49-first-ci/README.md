# PR49 首次整合 CI 安全证据

新整合源 `7665253ced0888e8204b9806b63c4163f2cafe42` 的首次 push `44284378478` 和首次 PR `44284677670` 均 completed **SUCCESS**，attempt 均为 1。这里只记录这个新源的结果；旧组件首 RED、条件见证、pure PASS 和旧 CI 失败仍属于各自来源。独立 RAW 复核状态保持 **PENDING**。

| event | Python3.10 | Python3.11 | Python3.12 | Python3.13 |
|---|---|---|---|---|
| push | SUCCESS，metadata only | SUCCESS，metadata only | SUCCESS，metadata only | SUCCESS，2126 tests / 0F / 0E / 0skip |
| pull_request | SUCCESS，metadata only | SUCCESS，metadata only | SUCCESS，metadata only | SUCCESS，2126 tests / 0F / 0E / 0skip |

指定 push3.13 job 为 `134733127596`，PR3.13 job 为 `134734149665`。只下载这两个 unit；其余六个 unit 未下载，不宣称其具体测试数。两份报告实际 runtime 均为 Python3.13.18 / SQLite3.46.1。worker 为严格九字段，native int 计数和 bool 状态已核对，worker/summary 的观测字段均是 native `[]`、`lease_observations_truncated is False`。没有执行 qualification，结果为 null。

两份原始 unit 各自逐 canonical ID 定位 26 项 `ok`：6 个 MM boundary、4 个 ledger sequence、6 个 credit lease tag、8 个 SH protocol pure 和两项原 native SH 恢复测试。后两项是 `test_durable_process.DurableProcessTests.test_expired_stopped_owner_holding_shared_gate_is_killed_and_publication_recovers`、`test_durable_faults.ManagedProcessFaultTests.test_expired_sigstopped_shared_gate_owner_is_killed_so_publication_can_recover`。后一项的进度行含 helper profile，真实绑定没有导出；只记录其后紧邻 plain `ok` 的行号。测试通过不是一般性 RTO 硬上界，也不证明旧失败原因已解决。

- [metadata.json](metadata.json)：八 job 的实际 25 steps 状态均为 success，包含 runtime 记录、unit、compile、demo、research replay、transactional acceptance、七项 bounded formal、build 和 installed。未获取各阶段完整输出，metadata 不能替代那些未采集的原件。首次读时两 run 已终态，没有重复 polling 或 rerun。
- [unit-projections.json](unit-projections.json)：两份指定原件的有限计数、类型、runtime、W9/S9 与源码摘要收据。
- [selected-test-outcomes.json](selected-test-outcomes.json)：每份 26 项方法实际结果及原件行号，不复制 profile 进度行。
- [source-bindings.json](source-bindings.json)：两份各 379 项 before/after source maps 相等并对应精确 C；548 项 Git/物理 regular 文件逐字节一致；相对 PR44 base 的全部 179 delta。
- [package-report-projection.json](package-report-projection.json)：同 push3.13 的小型 package 报告。七 checks、installed 八 tests 和八 command 返回码均报告成功。runtime 62 files 是 61 Python + dashboard；7344 required paths 选择了全部 179 delta、73 项组件输入路径并集及 548 项当前交付闭包。只处理两份报告 JSON，没有下载 wheel/sdist payload、约 51MB 容器或执行 full qualification。
- [deployment-boundaries.json](deployment-boundaries.json)：C 中 D2 export 的 AST 默认值为 False；当前权威实例只能按新的合成、code-bound 环境验证。没有启用 phase2 credit read admission、funding/audit 新内核、cache/snapshot 产品扩展或 STOPv2。两份 unit 报告不提供本轮独立观测的 image/executable binary digest；不宣称已完成该类二进制审验。
- [download-ledger.json](download-ledger.json)：三 ZIP 共 267269B，provider SHA/长度一致，25 个 member CRC 全通过。各引用及 payload 只取一次，没有 joblog 或其他成功 unit 下载。
- [administrative-release-facts.json](administrative-release-facts.json)：按首次捕获 PR49 body 保留 root 的 literal scanner 误报、shell 续 commit/push 及更正时源未变化的原陈述，明确是行政事实，不是 CI 失败或目标执行。本采集的稀疏文档读取、缺失可选路径搜索和 tag inventory 相对路径命名空间假设停止也分别保留，没有改测试或源码。
- [privacy-review.json](privacy-review.json) 与 [private-inventory.json](private-inventory.json)：原件保密边界及初次派生清单。后续封存清单另列，原记录不回写。
- [final-status.json](final-status.json)：新 C 首 CI 成功与独立 RAW PENDING、qualification null、生产/资金/容量 false 分开表示。

base 为 PR44 `9b6299af78e3f55055b6c297f6aa4a23da7f0415`。实际 merge `e0372c0a08d98d87b96ef6faccceff3cea1f91be` 的 parents 为 base、head，tree `67c5ee075f2fe96e3a7022db619f5aab53a0c3d5` 与 head 相同。package 报告来自 exact push C，PR unit 来自实际 merge。两者摘要都绑定相同 tree 的当前字节。

历史计划没有改 pin 或借签：SH 旧 69 输入相对 C 在 ledger/service/startup/writer_fence 四处不同；MM 旧 63 在 ledger/startup/writer_fence 三处不同；ledger 旧 3 在 ledger.py 不同。这些旧计划继续对应其历史源。当前 CI 的 379 项摘要和 canonical source inventory 61 项独立绑定新 C；包内保留旧文件不是批准其对新源重跑。相对 PR44，runtime 只变 ledger/service；CI/build 配置未变。PR35 基线的四模块整合设计和旧 source-bound authority 限制仍保留，不能给旧 authority 热换二进制或改 marker。

所有原 ZIP、unit member、helper profile、完整日志、真实 PID/boot/nonce 绑定、下载引用与 connector 原响应均留 `/workspace/pr49-ci-first-private`，目录 0700、文件 0600。每个指定 unit 原文各有 UUID-like 候选，候选值与绑定对象没有导出。provider 公开可见不改变其交付边界。此目录公开内容仅为有限投影和 hash 收据，不含原件 ZIP、DB/WAL/SHM 或私有 capsule。

采集器没有执行 UTA import、compile、SQL、native probe、PID/proc 查询、信号、benchmark 或 CI rerun，也未启动 child agent。新 CI 绿色不会将旧失败洗绿，亦不等于万笔容量、持续 30 分钟、复制持久化、灾备或真实资金批准。
