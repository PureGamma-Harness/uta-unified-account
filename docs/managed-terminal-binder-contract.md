# 冻结 909 终态元数据绑定器候选

阶段一修复 `ac215ac16212ad95e5fe11682a77f509bda9d044` 关闭了未经绑定的 candidate。此阶段新增独立工具 `tools/bind_managed_terminal_evidence.py`，实现实际文件契约的元数据关联校验，**独立审查与实际执行尚未授权**。`REVIEW_AUTHORIZED=False`；完整合成链可以得到 `metadata_chain_bound=true`，仍不授予 candidate、金融、持续时长、容量或生产通过。

## 依据与边界

实际契约来自固定 `909acecd153e2e89dfe2238e3ed3a3d9a3d3c9f0` 的 `tools/run_managed_long.py`、`tools/managed_soak_observer.py`、`tools/managed_observer_finance.py` 与 `benchmarks/run_managed_soak.py`。参考公开 schema 还读取了 `e4396b4b1fd9c2e3a138e48a045feffe158705cc` 的 smoke02 producer/cold/projection JSON。短 smoke 的包装与六小时 supervisor 的 `Pipes.result` 有差别，不能照抄短 smoke 为完整长测回执：短 smoke 无 `identity/stdout_complete`，且未发行长测 cold receipt。长测契约以实际固定源码为准；尚无实际完整六小时终态例。

绑定器只打开固定列表里的 JSON 和一个外部已审 manifest。它不打开数据库、压缩日志、原始 HTTP 或密钥，不观察 `/proc`，不执行 audit、服务、风险重算或信号。逐币守恒和逐笔关联仍是原 observer/producer 的实际审计范围；本工具核对它们的记录、水位与来源一致性，不重新完成金融审计。完整风险及业务事件重执行始终未验收。

## 封存与真实性前置

需要 root 在原唯一监督器自然结束并完成原有终态收集后，另行批准封存元数据。manifest 格式为 `schema=uta-terminal-json-pins-v1`、`source_commit` 和精确 11 个固定相对路径到原始字节 SHA-256 的 `files` 映射。命令必须收到独立审查确认的 manifest 原始字节 SHA；从同一个未知来源自行计算 digest 再传入不能建立真实性。工具只证明与所给已审 pin 一致，无法独立证明 reviewer 身份或外部授权。

固定记录为 job/progress、observer/baseline、control/launch、producer-result、final-before、strict-cold-result、observer/cold-receipt、final-after、final-summary、live-coverage。缺一、重复键、非有限数、非普通文件、末级符号链接、超限、哈希不符、supervisor-failure 不可确认缺失时均拒绝绑定。上层目录必须是可信封存目录；本工具不提供敌对目录的完整路径隔离。前后两个观察 JSON 上限各 64MiB，与原 supervisor LINE_CAP 一致，其余更小；这是字节读取上限，不是文件系统 IO 的硬时间保证。

## 校验内容

- 原 job 配置为 21600s / 0.25 round/s / 5400 轮，合成账户与已种本金为原预算。baseline 的完整原 job、job ID、文件身份、source map、workload spec 与 observer 两个源哈希逐项绑定；boot、driver PID/birth、原起止时钟采用该次已登记任务的精确常量，不允许等待补足。
- 工程 qualification 与原 source/Python/SQLite/artifact 三项 digest 绑定；这不升级为生产批准。
- producer、final-before、cold、final-after 四个 `Pipes.result` 均要求 exit 0、完整 stdout、合法原子进程身份/开始/结束时间及 digest。producer 原身份与 launch 精确一致，过滤后的 response 与 progress 共享字段严格 JSON 值一致。四次子进程收集按原记录的 wall 时间顺序；时钟矛盾拒绝，不猜补偿。
- producer 必须 completed、一个 controller、原 active elapsed≥21600、5400 全 DONE、无未解决效果、原日志与 golden 已过。精确 worker=180、parent=18；前后观察均核对 198 条各轮计划、发送确认、DONE 和代际提升，拒绝重复或畸形条目。
- 前后 snapshot 绑定同 contract/start/deadline、稳定边界、停止的 driver/listener/worker 及 inactive lease。核对原 finance golden/retry/count/residual 记录，checkpoint/ledger/business watermark、日志 head 和物理 reopen 声明。关闭后可能有 market/progress stale informational alert；不新增“任何 alert 均失败”的原规则外门槛，最终金融状态依照原 final reconciliation 及 fatal summary。
- final-before 合法地仅缺 `producer_cold_audit_same_watermark_missing`，eligible=false；final-after 必须无错误且 eligible=true。两侧同水位，receipt 同源码、审计 SHA、Python/SQLite、私有完整冷备份 scope、原 1GiB clone 预算；cold wrapper response 与 receipt、after 审计摘要交叉匹配。
- final-summary 的真实故障计数、无 collection/fatal error、未 drain、完成状态与 coverage 记录完全一致，不能用 summary true 覆盖底层失败。

合成完整例验证的是字段与校验路径，不证明任何真实子进程、备份、水位或资金动作发生。manifest 哈希也不能代替完整风险回放。任何缺失给出固定错误代码，不回显未知字段、error 文本、路径、nonce 或业务明细。

## 验证、部署与回滚

新增测试仅以临时合成 JSON、字典和哈希验证合法链与缺失、失败退出、未知身份、短时钟、错误 boot/source、冷水位/SHA/runtime/scope、重复故障、运行中 worker、drain、coverage、封存 pin 等负控。固定代码 `2a9d9a8a35bd9676494cb4b9af164a6ee6611861` 的首次阶段二纯验证在 CPU3、10s 上限内得到 **12/12 PASS**，unittest 0.078s、完整子进程 214,661,282ns；原 stdout/stderr 与输入哈希保留在 `evidence/managed-terminal-binder-20261117`。没有读取实际长测目录、SQL、observer 或冷审计。保留阶段一原首 FNF、5RED 和修复结果，不将其覆写；阶段二仍待独立审查。

独立 `ae5e52c322780024d9669d8bf49377d17bc1e709` 后续首批 17 项 challenge 得到 11 PASS / 6 RED：布尔零值、浮点轮数和故障计数仍可被 Python 宽松相等接受；两份 child 回执可以复用完全相同的 PID/birth；1001 位 elapsed 整数会令 `math.isfinite` 抛 OverflowError。全部首原件与源固定保留。本次严格化修订尚待新的纯验证和独立复核，不覆盖原 12 PASS 或原 6 RED。

修订按实际 schema 统一约束：所有元数据数值先检查有界范围；整数证据采用精确 int（排除 bool/float），默认范围为正负 signed 64-bit，count/clock 字段另外要求非负或正值，PID 至多 signed 32-bit、birth 为 ASCII 十进制有界 token。秒值支持源 schema 的 int/float，仅接受有限且位于 0 至 86400 的值；该范围是六小时任务元数据契约，不改变任何金融计算精度或原长测时限。字段值超界先返回固定结构化错误，不再经过隐式 int→float 转换。

该次注册的 coverage 数值契约来自 v4 计划及实际 `Coverage.report`：12 个 1800s block、每块至少 1 次独立 golden、61s 采样、technical unknown 总预算 3、连续预算 1。对计数、block index/时钟、required/observed、轮数、零残余、故障、文件设备/inode 等按真实类型检查；跨记录用规范 JSON 的类型敏感比较，避免 True/1 或 5400.0/5400 的隐式相等。四个子进程的 `(pid,birth)` 必须两两不同；同 PID 配不同 birth 仍被允许，不能把正常 PID 重用当成错误。

`Pipes.result.response` 已由原监督器过滤，无法从它重建原始 stdout 字节。因此 `stdout_sha256` 仅作为原回执中的已封存声明检查形状/文件 pin，**不声称已反算或独立核验原 stdout digest**。需要原始流时必须另有已授权、已保留原始资料；不得通过重新序列化过滤后 response 制造验证证明。

不部署到运行源；不实际对正在运行的目录调用。审查通过且原任务终态封存后，root 再给予准确 bundle、manifest SHA 和一次实际提取的具体 GO。激活候选资格亦需经审查的代码版本，不接受未审命令开关绕过。

回滚只移除本新增绑定器、测试与文档引用，保留全部旧失败与原始资料。阶段一 extractor 的 candidate=false 继续有效。无服务 schema、公共 API、账务、风险参数或原长测阈值迁移。
