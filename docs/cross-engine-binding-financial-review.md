# Cross engine binding：独立金融 CODE/spec 审查

审查对象固定为 `53acece53d27fb118c89286c10e5be41bb2ca5e7`，仅三份设计文档/JSON 与其固定源码。**D0 金融政策边界审查完成；D2 同步金融 shadow 仍阻断。** 没有运行目标 import、编译、测试、SQL、进程检查、worker、CI 或服务；没有修改运行时或资金状态。本审查不批准生产、候选权威、借贷、真实资金或既有 authority 迁移。

机器记录见 [review.json](../evidence/reviews/cross-engine-binding-financial/review.json)，设计见 [原提案](cross-engine-binding-design.md)。21 条源码的 Git blob、字节数和 SHA-256 全部独立核对一致。PR52 相对 PR49 的六个运行时变化以及 PR55 仅新增候选内核也已由固定 Git tree 核对，未假定已有组合运行基线。

## 可关闭的静态金融边界

默认 valuation 十字段、order 十一字段、execution_options 两字段与 PR52 源码一致。实验 risk policy、order envelope、artifact envelope 使用显式新版本；binding 自有 format 1 不替代旧 artifact format 1。未知 key、重复 key、bool 版本、未知 engine/契约都拒绝，不能删字段后作为旧格式成功。

绑定要求覆盖实际 registry/module/dispatcher 对象、defaults、kwdefaults、closure、unwrap、helper、常量、模型类布局、全局和 builtin alias、受信 runtime。相同名字或在盘 SHA 不构成实际执行绑定。这个要求在设计层充分，EBD-001..004 的实际覆盖仍未验证。

实验归档明确捕获唯一 UTC `evaluated_at`、market snapshot、contract 和 binding；两计算器、决策 before/after 以及历史 v2 replay 使用同一时间。旧 v1 继续只证明数值，不补造历史行情新鲜度。未知 authority 不得自动选择参考引擎；reference-authoritative shadow 的 candidate 失败也不代表发生了引擎切换。

Credit V2 的 ten-field base、零缓存、持久策略比较保持原契约。实验 exchange-only 打开、能力安装及 borrow 拒绝必须在资金池、债务账、能力与 authority 变化前发生。带债合成导入仍没有受审导入契约，未闭合前仅能离线估值；不能从现有负债估值推导新增借款授权。

## EBD-FIN-001：D2 前必须定义强制结算恢复矩阵

设计要求构造/重开前验证完整 binding，同时要求 shadow 失败不阻断已确认义务。它尚未说明重启后仅 candidate binding 不可用时，如何打开受限结算权威。PR52 `apply_fill` 明确是本地执行授权，**不是外部已确认成交的入账接口**；其 projected risk、audit-before 和 audit-after 均可能抛错回滚，不能直接证明该承诺。

实施前应分清“尚未撮合的本地授权”与“撮合已确认、必须履行的持久义务”，定义受 fencing 保护的幂等结算/恢复入口。candidate 单独超域、差异、缺失或漂移时，应保留已声明参考权威和原费用/预占规则，完成义务并持久记录失败、关闭新增风险。对未知契约、参考/共享模型/runtime binding 损坏则不得默认 fallback；保留义务和预占，使用受审的精确参考制品恢复，不能伪报已结算。

验收须在撮合确认前后、after-state 审计及重启分别注入 shadow 故障，证明每笔真实确认成交、费用、仓位和分录恰好一次对应；未确认授权可以拒绝。若仍不能区分这些路径，按设计已有规则限制为只读/离线，禁止 D2 金融接入。

## EBD-FIN-002：D2 前必须定义回滚与冻结的崩溃顺序

`ROLLBACK ... THEN DURABLY FREEZE` 是期望结果，尚不是恢复协议。金融回滚后、独立控制记录落盘前崩溃，会丢失冻结意图；单写者若未明确关闭队列准入，也可能在这段间隙处理下一条新增风险命令。本轮没有运行时 shadow，因此不把这项设计缺口称作已复现缺陷。

实施必须定义准入关闸、账户/generation 范围、关联失败意图、金融回滚、控制记录提交与错误回执的顺序。下一条新增风险被选择前必须关闸；重启/接管不能因缺少尚未写成的 freeze 记录就重新放行。控制存储不可用时保持拒绝新增风险，同时保留已确认义务的执行能力。不得把已回滚金融事务里的告警称作持久冻结；原命令 ID 的查询与结果未知协议保持原义。

验收须逐边界崩溃或有界状态枚举，加上排队并发命令；重新打开存储后证明失败接纳没有预占残留，冻结前后不出现未经批准的新接纳，确认结算仍能恰好一次推进。

## 人工数值复核与限定

M02 的 gross200、债务130、折扣160、risk30、loan80、IM13/MM6.5、available17 一致。M01 的抵押1105、债务112、PnL40、risk1033、IM56.3/MM28.15、available966.7 一致；USD388 与 BTC3.88 是互斥单独 quote，不能相加。

M09 的 11→9、11.01→10 符合严格 MM 边界，但必须明确它是假设借款所得立即离开抵押品的保守 quote，不能称为借款现金仍到账内时的实际 post-borrow equity，也不授权借款。EBD-M04 的 89.94 与 94.94 在列出的 mark、费用、最小单位和 reserve 前置成立时算术一致；94.94 是 RO 已确认全成并终结其自身预占后的状态。若投影仍保留该 RO fee reserve，则为94.92，不能混作同一个逻辑时点。

这些是人工纸面复算，不是独立 oracle 运行或撮合/账务证据。538 例、所有15个 EBD 门槛均未由本审查复跑。

## 后续门槛与回滚

D0 可作为有条件的静态设计依据。D1 仅可在另行源范围审查后实现纯绑定；本审查不授权执行目标。D2 必须先关闭上述两项并取得 EBD-001..012 所需证据；D3/D4、旧 writer 排斥、真实撮合、故障恢复和容量分别验收。未启用借贷、PM/Isolated、候选清算或多节点能力。

本提交只有审查文档，回滚为 revert 此审查 commit；没有数据迁移或运行时兼容性变化。此前已封存的 CI/RAW 证据不变。没有 push、CI rerun、部署或上线动作。
