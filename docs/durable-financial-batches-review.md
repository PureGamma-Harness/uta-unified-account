# 持久金融批处理设计的独立审阅记录

日期：2026-11-17。基线 `21aa6510bafcce8383fc24ac2c35e671074b9baf`，
worktree `/workspace/uta-durable-batch-design`，分支 `design/durable-batches`。
这是一份设计/有限模型 peer review 记录，不是 runtime、性能或生产审批。

三个互相分离的只读子任务分别核对真实 corrected P1 子 PID profile、现 managed 逐入口
路径、独立模型/设计声明。profile 与入口审阅不修改任何文件、不运行负载；模型审阅只
允许单 CPU 的极小构造/重跑。所有修改由本设计组在上述独立 worktree 中完成。

| 审阅发现 | 处理结果 |
| --- | --- |
| 原 invariant 只有 effect→terminal，terminal-only success 可漏过 | 增加 SUCCEEDED→实际 effect 或合法原 effect link；增加 `terminal_only_success` 负控 |
| reservation/REPAY ledger 未与 effect 对齐 | 增加 exact active reserve、CANCEL 释放、REPAY 金额一致性；增加 missing-reservation/missing-repayment 负控 |
| replay link 可能引用自身或无效果 target | 必须 earlier、同 account/OID/canonical、target 有真实 committed effect/evidence；增加 `forged_replay_link` 负控 |
| 普通 technical fault 与 poison failure 的预算混写 | 分别标出各最多一次；process crash 另有一次上界 |
| 同 OID 异内容分支未被场景触发 | 增加 `conflicting_order`，要求其无新 effect 的 REJECTED 覆盖 |
| negative controls 只要求任意 violation | 每个 variant 绑定 `expected_violation`，原因不匹配就失败 |
| query-all 仅保留易失 list，重启身份来源不清 | 增加 durable manifest、prepared/recover、易失 list 丢失、restart 重建；明确权威读取及 manifest 耐久是前提 |
| 模型未覆盖 budget seal prefix / mixed unknown | 增加 prefix seal/commit；unknown 包括同 manifest 的 terminal/PENDING 混合；物理 commit 标签只用于观察统计 |
| 文档称覆盖“要求”，main 只强制终态可达 | common/per-scenario `required_coverage` 全部强制，缺项非通过 |
| 控制公平、wall-clock、manifest 永久历史/权限不在图中 | 设计明确列为未证明；模型只验证抽象排他和让出机会，active-slot 不代表 append-only schema 验证 |

最终 reviewer 在单 CPU 独立重跑约 .513 秒，退出 0，stdout 与保存 JSON 完全一致。
5 个 safe 场景共有 **18,411 states / 41,426 transitions**，无 violation，所有 required coverage
满足；13 个 unsafe variants 各命中指定 violation，另有 16 个 ingress identity 组合。
reviewer 的结论为：未发现剩余阻断性设计声明问题，可作为实现审查输入；不构成实现
refinement、性能收益、liveness、真实 RPO 或生产批准。

可复查产物：

- [设计、证据与逐入口追踪](durable-financial-batches-design.md)
- [独立枚举器](../formal/explore_durable_batches.py)，SHA-256
  `56796bee981bb09b0a8f139754ce55312ed88bccc3c7e2aaebe530f42b56f372`
- [完整结果及最短反例](../formal/results/durable-batches-design-20261117.json)，SHA-256
  `c7b8bd5359e3287128bba2591e8930edb33b86f65b84c2bbf81bec0d7580fcc2`

模型未覆盖准备 manifest 后其他写者产生 terminal 的竞争、保留历史 schema/hash/role
实现、逐 CID attempt 计费、持续到达/age fairness、完整 control barrier 内容、换代 token
细节、真实 pause/fsync/clock 或任意规模。runtime、benchmark 原始证据、其他 worktree
和旧 24h 作业未修改；本轮无 benchmark/profile/重压。
