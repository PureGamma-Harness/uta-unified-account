# PR50 首次 CI：保留失败

`2cf04629e3b724ea3d9a46ae83e6ff10ea6750ee` 的首次 push `44296411474` 与首次 PR `44296464423` 均为 **FAILURE，attempt 1**。本次没有重跑 CI，没有用成功样本覆盖失败。独立 RAW 复核仍为 **PENDING**。

| event | Python 3.10 | Python 3.11 | Python 3.12 | Python 3.13 |
|---|---|---|---|---|
| push | SUCCESS，metadata only | SUCCESS，metadata only | FAILURE，2061 / 0F / 1E | SUCCESS，2061 / 0F / 0E |
| pull_request | SUCCESS，metadata only | SUCCESS，metadata only | SUCCESS，metadata only | FAILURE，2061 / 1F / 0E |

固定 push3.13 job `134774479797`、PR3.13 job `134774662858` 均按原选择取 unit 原件；额外只取失败 push3.12 job `134774479890` 的 unit。三份原件均 0 skip，worker 是本分支实际使用的严格七字段格式，计数为 native int，状态为 bool。其他五个 unit 没有下载，不据 job 绿色声明其测试数。失败 job 的 unit 之后 compile、demo、research replay、transactional acceptance、formal、build、installed 等阶段为 skipped；元数据中的证据上传成功不表示这些阶段运行成功。

两项失败分别保留在 [failure-projections.json](failure-projections.json)：

- PR3.13：`test_process_readiness.ProcessReadinessTests.test_same_version_changed_persistent_content_is_not_reused` 在 `tests/test_process_readiness.py:158` 的最后 `assertTrue(financial_ready)` 得到 False。该断言没有附带完整 diagnostics 对象，不能由此还原当时全部就绪原因。
- push3.12：`test_owned_startup.OwnedStartupTests.test_additional_guarded_schema_after_full_replay_cannot_extend_frozen_manifest` 在进入启动上下文时，沿 `startup.py:211`、`writer_fence.py:533`、`writer_fence.py:295` 报 `WriterFenceError / lease_expired`，尚未到达该用例预期的 schema-change 拒绝检查。本分支七字段 worker 没有新版 lease observation。

这两处是不同的观测结果。根因均 **UNRESOLVED**；这里没有将其定性为偶发时序问题、候选回归或可忽略失败，也没有改 lease、timeout、断言或源码。固定 push3.13 同一方法通过只能作为该次运行的事实。

[source-bindings.json](source-bindings.json) 将三份各 373 项 before/after maps 逐项绑定到 exact head Git blob。实际 PR merge `c35b7962ea169f5a02c95142be88a76a3fe4cfbc` 的 API parents 为 base `f69c11dc822fc9c442913dbcd5dc8c7cf2f3ae91`、head，tree `282223c8dc43c83c6af1608b5ef7ac065149c4b4` 与 head 一致。本 PR 相对自身 base 的 26 条 delta 全在包 required 清单内，UTA runtime 与 CI/build 配置均未改变；没有与 PR51 混合验收。

只另取同 push3.13 的小型 package report。[package-report-projection.json](package-report-projection.json) 的七 checks、installed 八 tests 及八 command 返回码成功；62 个 runtime files 为 61 Python 和一个 HTML，其摘要逐项匹配 exact head。7094 个 required paths 与 Git 全树路径相等。此结果属于成功的 push3.13 job，不能补足两个失败 job 的 skipped 阶段。没有下载或独立重建 wheel/sdist payload。

[download-ledger.json](download-ledger.json) 记录四个 ZIP 共 **361298 B**、28 members，provider 长度/SHA、CRC 和提取成员字节均相符，引用与 payload 各取一次。没有下载其他成功 unit、joblog 或大型 wheel 容器。原件在生成 SAFE 前封存：46 files / 2623125 B，seal SHA `d1c75df9a8b7ab35d33351119fcf8d1303dbb23f8acaeac0fc42f9e1264ec4b6`。

全部原 connector、签名下载引用、ZIP、完整日志及 helper profile 留在私有 0700/0600 命名空间。公开仅有限投影、源码路径、canonical test ID 和 hash 收据；真实进程/代际/分片/运行路径绑定未导出，原件名称映射也不公开。详见 [privacy-review.json](privacy-review.json) 与 [private-inventory.json](private-inventory.json)。

`benchmarks/test_reserve_reuse_candidate.py` 的四个方法不属于 `tools/run_validation.py` 对 `tests/` 的正常 discovery。既有 pure/native profile 仍是各自历史源的证据，本次 CI 没有重做该实验，也不能将其收益归给 Cross 内核。采集器只做 API GET、下载、字节/JSON/ZIP 和行政 Git 读取；没有 UTA import、compile、SQL、native/PID/proc/signal、benchmark 或 CI rerun，没有启动 child agent。此首 CI **阻断验收**；万笔容量、30 分钟持续运行、复制持久化、容灾和真实资金批准仍未完成。
