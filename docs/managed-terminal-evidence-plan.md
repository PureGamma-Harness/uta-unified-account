# 909 六小时长测终态证据计划

本交付是只读元数据提取器与验收计划。冻结源为 `909acecd153e2e89dfe2238e3ed3a3d9a3d3c9f0`；运行目录为 `/workspace/uta-managed-observer-runs/909acec-six-hours-20261117`。不改变任务、参数、资金权限或运行源。此计划尚未执行终态审计。

## 原始边界与运行状态

原任务启动 CLOCK_BOOTTIME 为 `80871129103044ns`，原 duration 截止为 `102471129103044ns`，相差严格 `21600s`；对应最低时长目标为 `2026-11-18T01:29:04.651792Z`，这不是保证自然终态的硬时间点。原监督器在自身 producer 启动后 `21600+600s` 仍未退出时会请求 official drain；该既有宽限不修改。生产者每轮不能用压缩计划间隔追回延误，因此累计落后可能阻断 5,400 轮在原窗口内完成。实际生产者报告的完整时长亦须达到 21600s；观察者等待、任务暂停、重启或旧 887 任务的失败时长均不得补足。未终态之前，所有通过字段保持 false。

本地低流量合成任务的 5,400 轮包括真实撮合、结算、部分撤单、已种入借款的还款及进程故障恢复，不代表万笔容量、多节点、HA、真实资金或完整第一批产品的生产验收。新借款端点、PM、完整风险引擎重执行以及完整业务事件状态重执行没有由本任务得到验收。887 的首次实际 24h 失败继续保留；本任务不得覆盖它。

资源语义保持原样：预检保守空闲预留是 10,737,418,240B，生产者默认活跃空闲保护是 1,073,741,824B。17,448,304,640B 是其他 QA 同机准入参考，并非该任务活跃停止阈值。

## 分离的验收门槛

| 门槛 | 所需真正运行证据 | 不可替代它的证据 |
| --- | --- | --- |
| 连续时长 | 同一源、同一 boot、一个 controller session，原生产者 completed 且原 active duration ≥21600s | 观察者继续等待、预设 duration、旧任务 elapsed |
| 轮次完整 | 5,400/5,400 DONE，无其他轮状态，未完成 step/fault 均为零 | 部分完成轮的 golden PASS |
| 故障恢复 | 180 次 worker 与 18 次 parent 原计划信号，代际提升与接纳回执均可核对 | 尝试发送次数、observer 对 pid 的存活判断 |
| 日志与命令 | 分段清单与逐段 SHA、完整事件哈希链、每个 account/round/step 的唯一命令及终态 | 单独表总数、一次 JSON 摘要 |
| 撮合与金融对账 | 每轮 4 单/4 fill/2 match；全任务 orders=21,600、fills=21,600、matches=10,800、account commands=32,400、risk decisions=43,200、ledger events=27,006，逐笔订单/撮合/仓位/分录关联、逐币守恒及费用本金核对 | HTTP 成功数、尝试次数、撮合单边计数 |
| 停止与物理重开 | 生产者、listener、worker 均已停止且原身份已核对；独立只读重开前后 checkpoint/business/ledger watermark 一致，golden 通过，无 retry alert | 活跃库内采样、非一致读快照 |
| 冷生产者审计 | 原监督器执行的完整私有 SQLite backup 副本；相同源码与 Python/SQLite 版本的 audit receipt；前后同 watermark | 只拷投影、换用另一运行时、原库上临时执行写构造器 |
| 覆盖完整 | live-coverage 原预算内 COMPLETE，无 collection error、historical financial alert、official drain | final 一次健康快照 |
| 完整回放 | 独立批准并实际执行的风险引擎逐 decision 重算与业务状态完整重执行、原输入版本校验及逐项差异 | 本任务已提供的 journal hash/投影重建/关联核对；两项仍未测，不能宣称已通过 |

## 唯一执行者与终态收集

冻结 `tools/run_managed_long.py:490–538` 已由原监督器拥有终态流程：等待原生产者返回，记录 producer result，停止已有观察者，运行 final-before、同一运行时的 strict producer cold audit、final-after，再输出 `control/final-summary.json`。不得启动第二监督器、第二观察者或重复冷审计来争抢这段流程。原文件若缺失、失败或内容不完整，保留该首次结果，报告 UNKNOWN/NO_GO。

`tools/managed_soak_observer.py:624–697` 校验停止边界、完整轮数、原时长、源版本、未完成效果、独立金融 golden、逐段日志、物理重开同 watermark 和冷审计 receipt；`699–797` 以私有完整备份执行冷审计，私有数据不公开。上述是静态识别的原设计，实际 PASS 只能由自然终态后的原始结果确认。

本提取器只读取固定六个 JSON 元数据文件，每个有大小上限、单次读取、拒绝重复键/非有限数，末级文件拒绝符号链接与非普通文件。它不执行 SQL、服务、审计、进程信号或风险计算；源目录的上层路径必须由操作员指向可信原任务目录。并发读取不构成一致快照。它将安全字段列入摘要，原 error 文本、业务明细和未知字段不导出。

初版 `7e5a6ae` 将这些局部布尔观察聚合为 candidate。独立 `bc478063a8f3e911ff00403525fff24678154f99` 的首个实际假文件验证得到 5 RED / 1 PASS：失败/空子进程回执、缺失前后冷快照、不同 watermark/审计 SHA 和互相矛盾的计数仍能变为 candidate。全部原件及最初导入前 FileNotFoundError 保留。本修订选择保守关闭候选资格：`candidate_for_independent_terminal_review` **无条件 false**，`terminal_binding_status=NOT_IMPLEMENTED_FAIL_CLOSED`。原局部观察聚合改名为 `local_metadata_predicates_observed`，不代表链条完整或一致。输出明确列出退出、身份、原 contract、冷水位、审计 SHA/runtime/scope、跨记录一致性及逐笔对账尚未由本工具验证。

实际固定源码的 `Pipes.result()` 返回 `exit_code`、原 child `identity`、`ended_wall_ns`、`stdout_sha256`、`stdout_complete`、stderr 摘要和过滤后的 `response`；仅观察到文件存在不证明成功。`final_once()` 将前后观察写为这种包装，冷 receipt 则由 producer-audit 另外生成；final-before 合法情况下尚未有 producer receipt。原 observer 的 `validate_metadata()` 从 job `configuration/environment/planned_rounds` 加 checkpoint 的起始时钟和 boot 派生 contract，并非读取一个 `job.json.contract`。独立负控的短 `contract` 是特意构造的未读字段，不能当成实际 job 格式。当前工具不实现这些链条的 schema 绑定，schema 形状正确的合成回执也不能激活候选资格。

待独立代码审查通过后，root 可在自然终态后执行一次：

```sh
python3 -B tools/extract_managed_terminal_evidence.py --run-root /workspace/uta-managed-observer-runs/909acec-six-hours-20261117
```

输出保存在新的私有证据目录，原任务目录不写入；再由另行实现并独立审查的终态绑定步骤验证原 SOURCE、控制文件哈希、进程身份、原 supervisor 实际退出与 cold receipt。当前提取器不分析 final-after 中的逐笔数据、不签署真伪，也不能授予 candidate。任何未知必须保留，后续增加缺失验证应作为新任务及独立原始输出，不能覆盖旧失败。

## 部署、回滚与批准

本交付仅新增工具、测试和计划，不改变服务 schema、公共 API 或运行参数。部署时将工具放入独立只读审查目录，保持当前源与运行目录不变。回滚仅移除新增提取器和引用，保留所有首次原始报告；不回退实际账务、不删除私有 clone 或改写历史 flags。真实资金启用仍需独立验证组审查和明确上线批准。
