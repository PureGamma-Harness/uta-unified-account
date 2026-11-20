# 独立内存清算控制器

[uta/liquidation.py](../uta/liquidation.py) 的 `LiquidationController` 为一个账户提出撤单或只减仓动作，由调用方执行并确认。`python -m uta demo` 只演示撤单建议。它保存进程内阶段、待确认动作和已确认 ID，没有数据库事务、撮合或外部交易所调用。`lab` 的持久化清算使用另一套 [Simulator 流程](workflows.md)。

## 决策顺序与状态

`TimedRisk` 包含 `risk.equity`、`risk.maintenance_margin`、带时区的 `observed_at` 和完整性标志。权益、MM 必须是有限 `Decimal`，MM 非负。默认最大年龄为 10 秒，恰好 10 秒有效；未来、缺失时区、不完整、早于已见快照，或不严格晚于上次成功确认时间的数据均被阻断。

```mermaid
flowchart TD
    Start["next_action：先关闭 trading_allowed"] --> Valid{"_valid：完整、新鲜、数值和时间有效？"}
    Valid -->|否| Block["phase=BLOCKED，返回 None<br/>保留活动阶段和待确认动作"]
    Valid -->|是| Pending{"有待确认动作？"}
    Pending -->|是| Retry["返回原动作与原 action_id<br/>禁止交易，不评估恢复"]
    Pending -->|否| Normal{"活动阶段是 NORMAL 或 RECOVERED？"}
    Normal -->|是| Healthy{"权益大于 MM？"}
    Healthy -->|是| Allow["NORMAL，返回 None<br/>本次允许交易"]
    Healthy -->|否| Cancel["新一轮 CANCEL_ORDERS<br/>提出撤销所有订单"]
    Normal -->|否| Recover{"权益精确大于 MM × recovery_buffer？"}
    Recover -->|是| Recovered["RECOVERED，返回 None<br/>本次允许交易"]
    Recover -->|否| Phase{"活动阶段为 CANCEL_ORDERS？"}
    Phase -->|是| CancelAgain["提出撤单动作"]
    Phase -->|否| Reduction{"提供 PositionReduction？"}
    Reduction -->|否| Wait["REDUCE_EXPOSURE，返回 None<br/>仍禁止交易"]
    Reduction -->|是| Bounds{"数量为正且不超过精确持仓绝对值？"}
    Bounds -->|否或字段非法| Error["ValueError，无新待确认动作"]
    Bounds -->|是| Propose["REDUCE_POSITION，reduce_only=true<br/>多头 sell，空头 buy"]
```

依据：[LiquidationController._valid / next_action](../uta/liquidation.py)。图中的活动阶段是内部 `_active_phase`：阻断不会清除它；下一次有效快照会恢复该阶段，再检查待确认动作。返回 `None` 可以表示阻断、等待减仓输入或健康，须结合 `phase` 与 `trading_allowed` 判断。

成功确认撤单后进入 `REDUCE_EXPOSURE`；减仓确认后保持该阶段。恢复条件只用于仍在清算周期、没有待确认动作的评估。进入 `RECOVERED` 后，下一次有效评估重新按 `权益 > MM` 决定回到 `NORMAL` 或开始新一轮清算。`trading_allowed` 只描述最近一次评估，时间流逝不会自动更新它，调用方应在每次订单前重新评估。

## 动作确认与新快照

```mermaid
sequenceDiagram
    participant U as 调用方
    participant C as LiquidationController
    U->>C: next_action(s0：权益=MM=100，时间=t0)
    C-->>U: cancel_all_orders，action_id=A
    U->>C: next_action(有效快照，动作未确认)
    C-->>U: 原动作 A，仍禁止交易
    U->>C: acknowledge(A, success=false, now=t0)
    C-->>U: false，保留 A
    Note over U: 核对撤单结果后确认；控制器不执行动作
    U->>C: acknowledge(A, success=true, now=t0)
    C-->>U: true，清除 A，进入 REDUCE_EXPOSURE
    U->>C: next_action(s0，observed_at=t0)
    C-->>U: None，BLOCKED，快照须严格晚于 t0
    U->>C: next_action(s1：t1大于t0，权益=MM=100，仓位=-1.96，减仓=1.96)
    C-->>U: 动作 B：buy，quantity=1.96，reduce_only=true
    Note over U: 核对减仓结果后确认；确认不更新余额或风险
    U->>C: acknowledge(B, success=true, now=t1)
    C-->>U: true，等待严格晚于 t1 的新风险快照
    U->>C: next_action(s2：t2大于t1，权益=101.2，MM=92)
    C-->>U: None，REDUCE_EXPOSURE，仍禁止交易
    U->>C: next_action(s3：t3大于t2，权益=101.201，MM=92)
    C-->>U: None，RECOVERED，本次允许交易
```

依据：[next_action / acknowledge](../uta/liquidation.py)、[test_cancel_then_reduce_and_recover_with_new_snapshots](../tests/test_liquidation.py)。图中各快照均完整、未过期，`now` 等于观察时间，缓冲使用默认 1.10。

`acknowledge` 的 `False` 可表示失败确认或重复确认。失败保留同一动作；成功 ID 的再次确认是内存中的无操作。未知或乱序 ID、无时区的确认时间、早于已见快照的确认时间抛出 `ValueError`。调用方必须串行访问控制器，并核对结果不明的动作；进程重启会丢失阶段和 ID，该模块没有跨进程幂等保证。

## 精确阈值和减仓上限

清算恢复使用严格大于，默认缓冲及触发条件未改变。在已确认撤单、无待确认动作、使用新鲜快照时：

| 输入 | 预期行为 |
| --- | --- |
| MM=92，权益=101.19 | 小于阈值 101.2，保持 `REDUCE_EXPOSURE` |
| MM=92，权益=101.2 | 等于阈值，仍不恢复 |
| MM=92，权益=101.201 | 越过阈值，进入 `RECOVERED` |
| 仓位=-1.96，减仓=1.97，权益尚未恢复 | 超过精确绝对值 1.96，拒绝 |
| 仓位=-1.96，减仓=1.96，权益尚未恢复 | 提出买入只减仓建议 |

调用方设置 `Decimal` 精度为 2 时，直接计算 `92 × 1.10` 会舍入成 100，`abs(Decimal('-1.96'))` 会舍入成 2.0，分别导致提前恢复和放行超量减仓。[_above_recovery_threshold](../uta/liquidation.py) 先比较调整后指数，再将正数尾数缩放到有限区间，用足以容纳乘积的独立上下文精确比较；持仓上限使用不舍入的 `copy_abs()`。比较不改变调用方精度、舍入方式、指数范围、陷阱或已有标志。

控制器自身不沿用风险模型的 ±100 指数限制；来自 `calculate_risk` 的数据仍受 [风险模型输入边界](risk-model.md) 约束。极小指数回归使用紧凑 Decimal 表示，只验证阈值比较，不扩大产品范围或证明上游风险计算正确。1.10 是项目已有的演示参数，不是交易所规则。

定向验证：

```bash
python -m unittest discover -s tests -p test_liquidation.py -v
```

测试及完整贡献检查见 [验证与证据](verification.md)。这些证据覆盖内存决策与比较边界，不包括真实撤单、成交、外部幂等、重启恢复或持久化模拟器的端到端验收。
