# PR51 首次 CI：有限通过证据

Cross Decimal 候选源 `667171d1f248f571b3f3386402bdc02f1fc0dc92` 的首次 push `44296777854` 和首次 PR `44296832834` 均 **SUCCESS，attempt 1**。独立 RAW 复核仍为 **PENDING**。

| event | Python 3.10 | Python 3.11 | Python 3.12 | Python 3.13 |
|---|---|---|---|---|
| push | SUCCESS，metadata only | SUCCESS，metadata only | SUCCESS，metadata only | SUCCESS，2135 / 0F / 0E / 0skip |
| pull_request | SUCCESS，metadata only | SUCCESS，metadata only | SUCCESS，metadata only | SUCCESS，2135 / 0F / 0E / 0skip |

只下载固定 push3.13 job `134775754383` 与 PR3.13 job `134775944546` 的 unit 原件。其余六个 unit 未下载，不声明其具体测试数。两份原件均 Python3.13.18 / SQLite3.46.1；worker 严格九字段，native int 计数与 bool 状态、summary 对应字段均匹配，`lease_observations` 为 native 空 list，`lease_observations_truncated is False`。没有执行 qualification，结果保持 null。

[selected-test-outcomes.json](selected-test-outcomes.json) 逐 canonical ID 保留每份 Cross 九个正常测试方法和 lease-tag 六个方法的 plain `ok` 行号及摘要。正常 CI 原件没有逐 subtest 成功回调计数，不能称为又一次独立捕获 96 callbacks；既有 first-nine pure 原件的 96 回调收据继续独立对应其原始 source/plan。人工 literal 分类也不是本次新增的独立人工执行次数。

[source-bindings.json](source-bindings.json) 将两份各 382 项 before/after maps 逐项绑定 exact head Git blob。实际 merge `208f86b6a4ef40a2bea4945b8dd27b20028847b1` 的 API parents 为自身 base `c3e937a967711cd5cae7293ac3bf63c8260d8528`、head，tree `3a2e02e8d0b94170c3a8a6695445e3b19befe8ab` 与 head 相同。相对自身 base 为 25 条 delta，唯一 UTA runtime 新文件是 `uta/cross_decimal_kernel.py`，既有 61 个 UTA Python 文件与 CI/build 配置均未改变。没有与 PR50 的另一 base 混合。

同 push3.13 的小型 package report 中，七 checks、installed 八 tests、八 command 返回码均报告成功。63 个 runtime files 为 62 Python 和一个 HTML，逐项匹配 head；7386 个 required paths 与 Git 全树路径相等并覆盖全部 delta。已采集的八 jobs 各 25 steps 的状态在 [metadata.json](metadata.json)；未下载各阶段完整输出，元数据不是那些未采集原件的替代。未下载或独立重建 wheel/sdist payload。详见 [package-report-projection.json](package-report-projection.json)。

[download-ledger.json](download-ledger.json) 记录三 ZIP 共 **268694 B**、25 members，provider 长度/SHA、CRC 和提取成员字节均相符，引用与 payload 各取一次。没有其他 unit、joblog 或大型 wheel 容器。原件在 SAFE 派生前封存：43 files / 2160149 B，seal SHA `a1515ba3fcd9c06dbe3e19664051ae531b93f3605e737e35aa31e55e518a3641`。

原 connector、签名下载引用、ZIP、完整 unit log 及 helper profile 留在私有 0700/0600 命名空间。公开仅有限投影和 hash 收据，真实进程/代际/分片/运行路径绑定及原件名称映射均未导出。见 [privacy-review.json](privacy-review.json)、[private-inventory.json](private-inventory.json)。历史 source-bound plans 保持历史 pins；包中保留旧文件不等于授权对当前源重跑。

默认仍使用 reference；候选未接入默认 service 或新的 loaded-engine authority。更多情景覆盖、金融人审、future loaded-engine binding 和 Cross 性能验收仍 OPEN。PR50 的 legacy reserve profile 收益不能转作本候选收益。采集器没有执行 UTA import、compile、SQL、native/PID/proc/signal、benchmark、CI rerun 或 child agent。绿色只证明本次有限 CI；万笔、30 分钟持续运行、复制持久化、容灾和真实资金批准均未完成。边界见 [deployment-boundaries.json](deployment-boundaries.json)。
