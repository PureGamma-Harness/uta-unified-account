# PR47 首轮 CI 有限安全证据

源提交 `05ebc17f5a2a4934a2ee27f14ecdfe0a7067bd45`。首 push `44279325039` 为 **FAILURE**，首 PR `44279599639` 为 **SUCCESS**，均为 attempt 1。本记录不能作为整轮通过或生产启用证明。独立 RAW 复核状态保持 **PENDING**，后续复核应新增记录。

| event | Python 3.10 | Python 3.11 | Python 3.12 | Python 3.13 |
|---|---|---|---|---|
| push | FAILURE，2061 tests / 0F / 1E / 0skip | SUCCESS，metadata only | SUCCESS，metadata only | SUCCESS，metadata only |
| pull_request | SUCCESS，metadata only | SUCCESS，metadata only | SUCCESS，metadata only | SUCCESS，2061 tests / 0F / 0E / 0skip |

唯一 ERROR 为 `test_durable_process.DurableProcessTests.test_expired_stopped_owner_holding_shared_gate_is_killed_and_publication_recovers`。栈停在 `tests/test_durable_process.py:424` 的恢复行情发布调用，经 `uta/durable_process.py:1532` 到 `uta/sharding.py:267`，抛出 `uta.service.ServiceError`，上游为 `BlockingIOError`。公开源码中的错误码为 `router_busy`，状态码为 503；并未观测异常实例的 `.code` 字段。此处为 `timeout=4` 的首个 EX gate 入场，尚未执行随后五秒断言。capture 轮询、stop 请求和 rollback 调用已返回，不足以证明实际 gate owner 或进程停止状态。原因仍为 **UNDETERMINED**。

- [metadata.json](metadata.json)：两次首次 run、八 job、真实 merge parents/tree、每次采集实际观察时间。首读时已终态，没有 terminal polling。
- [unit-projections.json](unit-projections.json)：唯一失败 unit 与预先固定的 PR3.13 成功 unit。实际 producer 是 **legacy exact7 fields**；worker 和 summary 均无 lease 两字段。未运行完整资格检查，`qualification` 为 null。
- [failure-classification.json](failure-classification.json)：有限异常类型、逐帧源码 Git 绑定和阶段界限。没有导出完整 traceback 或绑定值。
- [failed-joblog-finite-projection.json](failed-joblog-finite-projection.json)：原 connector decoded log 的 SHA/长度、精确非 map summary 投影。job log 打印摘要，原 traceback 在独立 unit member 中；本文件不是完整日志。
- [source-bindings.json](source-bindings.json)：两个 unit 各 372 项源码摘要前后相等并匹配 C；108 项 Git delta；476 个物理 regular 文件与 Git 字节一致；UTA 61 个 Python 文件以及 tests/tools/config/workflow/build 相对 PR40 base 均无差异。
- [active-profile-plan-binding.json](active-profile-plan-binding.json)：实际 full plan SHA `03c789c6cc191c4a86af1bcf306b46830c6ca8cbf1b3394673168833c034f21c` 的控制脚本、两个 manifest、当前 63 项与 original-scan 63 项 origin 的合并 66 项闭包，以及既有公开 SAFE receipt 的 66 项前后源码摘要，均对应当前 C。这里只重复静态绑定，不重复执行或重新签署旧 profile RAW。
- [package-report-projection.json](package-report-projection.json)：同一 PR3.13 job 的小型报告，七项 checks、installed 八测试/八命令均报告通过。7051 项 required paths 中包含全部 108 delta 和 169 项必要闭包；没有下载或审验 wheel/sdist 字节，也未执行 full qualification。
- [download-ledger.json](download-ledger.json)：三份原 ZIP 共 250487B，provider 长度/SHA 均一致，25 个 member 的 CRC 全部通过。每个授权引用与原件只请求一次。
- [private-inventory.json](private-inventory.json)：初次安全派生时的私有目录 hash/长度清单。
- [privacy-review.json](privacy-review.json)：有限字段公开范围及原件保密边界。
- [administrative-derivation-record.json](administrative-derivation-record.json)：保留派生阶段的五次守卫/格式假设停止及一个 JSON 格式探针错误。首次是稀疏物化漏静态 HTML，随后发现历史通用 plan 与当前源摘要不同、以及 job log 是省略两张 source maps 的 pretty JSON。这些是采集整理记录，不是 CI 重跑或业务测试失败。
- [final-status.json](final-status.json)：push FAIL 与 PR SUCCESS 分开保留，生产、金融、容量资格均为 false。

历史通用 `plan.json` 保留 H254 的旧 aggregate 和旧 manifest 摘要。它不是此次 full run 的授权 plan，旧值没有被回填为当前值。实际 host 读取显式 `--plan`，once-driver 读取对应精确 manifest；四个实际脚本未见加载通用 `plan.json` 的字面路径。历史差异与当前 full-plan 闭包分开记录，不作为 CI 原因。

原件在 `/workspace/pr47-ci-first-private`，目录 0700、文件 0600。原 ZIP、全部 unit members、完整 job log、helper/profile 的真实 PID/boot/nonce 绑定、下载引用和 connector 原响应均保持私有。公开可访问的 CI 不改变这些绑定值的交付边界。此目录仅含有限派生证据、源码摘要及原件收据，没有完整 DB/WAL/SHM、私有 capsule 或原件 ZIP。

采集器没有执行 UTA、SQL、native controller、测试、基准或 CI rerun，没有访问 PID/proc 或发送信号。新增 benchmark observer 方法是否在普通 unit CI 中执行，没有证据；测试发现入口是 `tests`，不能用 source map 中包含 benchmark 字节推导执行。既有六库组件结果和 PR 矩阵绿色均不能覆盖此次首 push ERROR。私有清单的后续封存补充与本次总 seal 另列文件，初始记录不回写。
