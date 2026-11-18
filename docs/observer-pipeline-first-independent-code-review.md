# Compact pipeline 首次独立 CODE 审查：协议身份阻塞

固定 runtime source `9cd70912d6c8c2c40f348f8d6bca1071363a47aa` 与未执行 fixture tip `73bfdce2551c2925af442f6987fe510b5ac4c6a9`。**CODE 审查发现一项确定阻塞 PIPE-CODE-01；pipeline 尚未执行，不能把此记录描述为实际 audit 失败。**

## PIPE-CODE-01：watch 与 strict audit 使用不同 baseline contract

v2 watch 由 `observer_command` 传入 `--collector-input-v2`，Observer.contract 据此增加 `observer_output_protocol` 和四项额外代码 SHA；首次 sample 将这个 contract 封为 baseline。

但同一 run 的 `observer_command(audit=True)` 不传该 flag，parser 还禁止将它用于 producer-audit。新 audit Observer 的 collector_input_v2 默认 false，因此 contract 不含上述协议字段及四项 SHA。producer_audit 第一步调用 Observer.sample，sample 要求当前 contract 与既存 baseline 完全相等；此组合必在 `original_source_start_deadline_or_identity_changed` 路径拒绝。

这不是放宽 strict gate 的理由。应将“当前 run 的协议/代码身份绑定”与“stdout 是否输出 full-input frame”分开；watch、final-before、strict audit、final-after 必须使用同一被登记协议身份，而 audit 保留原审计输出模式。不能删除 baseline、抹去额外 SHA 或更改旧 gate 来促成通过。当前候选 fake pipeline 用例没有覆盖这一实际命令/contract 组合。

## 其余 CODE 路径的限定结论

- 原完整 classify_safely、回滚和 known-fatal financial drain 已搬入共享 process_samples，并位于分类落盘、CAS 与 compact publication 前。export UNKNOWN 记录保留既有分类，不再消费相同 attempt。
- raw queue cap 为2，read_samples 每次最多取2帧，包括 protocol-failed 后的 discard 路径；不会因生产者持续补满队列而无限循环。EOF、pending、queued、protocol failure 与 stdout retention 分开表示。shutdown pump 在同一180s deadline 前后检查，没有新加成功宽限。
- final_once 内存保留原 RESULT_FIELDS 投影用于旧 final 判断；磁盘 response 变为 compact，stdout SHA 单独标为 full-input wire scope。这不证明图可重建未纳入原字段投影的完整 wire bytes。
- 外部 Timeline 对 v2 必须使用 dependency store 完整 hydrate，缺 store 生成 UNKNOWN marker，旧完整 consumer 不能直接把 display summary 当 finance proof。
- nodes、publication receipts 和失败 full-input retention 均位于 observer output；原聚合 budget 代码未获得排除这些目录的新豁免。失败保留不足须明确 UNKNOWN。目录、落盘、崩溃和实际存储量仍未测试。

以上是源码序列与边界审查，不是并发、实际 drain、落盘、SQL、observer 或容量测试。raw frame 限制和queue数量也不构成已测峰值 RSS 或处理延迟保证。

## 证据与回滚

五个固定文件 SHA 与 runtime/fixture 区别记录在 [静态绑定](../evidence/reviews/observer-pipeline-first-code/static-code-findings.json)。本次没有运行新12、原8/25、FSadapter、SQL、watch、strict audit、原数据、网络或crypto。原 typed修复与各次首失败均保留。

本 OWN 仅新增独立文档与静态记录，无服务、schema、风险参数或数据迁移。回滚只移除本 OWN 新文件；保留 PIPE-CODE-01，后续需新源码关闭并单独验收。当前实际输出增长治理、冷审计链路、六小时稳定性、生产与真实资金资格仍为 NO_GO。
