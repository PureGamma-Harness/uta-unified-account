# PR49 首次整合 CI 结果

精确源 `7665253ced0888e8204b9806b63c4163f2cafe42` 的首次 push `44284378478` 和首次 PR `44284677670` 均成功，均为 attempt 1；八个 Python 矩阵 job 的 25 个步骤各自全部报告 success。这里记录新整合源的首次结果，旧组件证据保持原来源和原结论。

指定下载的 push3.13 与 PR3.13 原始 unit 各报告 2126 tests、零 failure/error/skip，worker exit 0。实际九字段 worker 和 summary 的保留观测字段均为 native 空列表及 False，计数 native int、状态 bool 与原件一致。其余六个成功 unit 仅采 metadata，没有推定个别测试数量。qualification 未执行，结果仍为 null。

两份报告各自实际定位 6 MM、4 ledger、6 tag、8 SH pure 及两项原 native SH 方法，共 26 项 `ok`。含真实 helper profile 的进度行留私有，公开记录只有 canonical ID、源码摘要、行号与实际 `ok`。这不是新的本地 native 探针、RTO 测量或旧 CI 原因证明。

真实 merge `e0372c0a08d98d87b96ef6faccceff3cea1f91be` 的 parents 是 PR44 base `9b6299af78e3f55055b6c297f6aa4a23da7f0415`、新 head，tree 与 head 完全一致。两个 unit 各 379 项 before/after maps、548 项物理 regular/Git 字节和全部 179 delta 已核对。当前 canonical tag inventory 61 项对应本 C。历史 SH/MM/ledger 计划的源摘要仍保留旧值，不能沿用批准或对新源执行后重新标注。

同 push3.13 的小型 package 报告七 checks 成功，installed 八测试/八命令成功；7344 required paths 覆盖全部 179 delta、73 项组件源输入路径并集和 548 项交付闭包，runtime 62 files 匹配本 C。只核报告和 ZIP CRC，没有下载或独立审验 wheel/sdist payload，也未调用完整资格检查。

root 在既有 PR body 记录的 literal-pattern scanner 误报和 shell 续 commit/push 事实原样保留为有来源的行政说明；更正不改变源字节，不用它解释 CI。本轮整理时的读取/命名空间假设停止单独保留，没有修改目标或重下原件。

原 ZIP、全部 unit members、真实 profile 绑定和下载引用均在私有目录，公开仅有限投影。D2 export 静态默认 False；本轮未收集独立 image/executable digest。没有启用 phase2 credit read admission 或扩展产品/内核；真实资金、持续容量、混合负载、稳定性、复制持久化和容灾资格仍不成立。

本提交仅增加 [本轮安全证据](../evidence/runs/pr49-first-ci/README.md) 和说明，没有改运行时、测试、workflow、旧 marker 或 authority。独立 RAW 复核保持 PENDING，后续应新增记录闭合。部署只适用于新合成 code-bound 环境的另行验收；本证据提交无数据迁移。回滚证据提交时保留原件与历史审计，不能删除已确认交易或用旧绑定给新源借签。
