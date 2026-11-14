# M1 合成纵向链路验收报告

状态：**软件合成验收通过，生产验收 BLOCKED**。范围为单节点 Cross、合成 USD 结算、BTC 多币种抵押/显式借贷、现货及线性限价撮合。它不是 USDT/USDC 真实产品批准，也不是完整 PM。

## 合入并发 main 后的最终状态

本轮工作期间 main 新增 `f8d72ef`。已通过 merge 保留其原始场景 PM 模型、模拟器、控制台、store、全部测试与性能数据。研究场景计算独立保存在 `scenario_margin.py` 并保持原导出兼容；Cross 实盘门禁仍不允许 PM。两个数据库增加权威类型及结构校验，拒绝误开，修复默认账本常量和不可变账户 JSON 兼容。

最终运行代码 `f6c439f59e386e678c87765b935169b775995f94`：**402 项通过、0 failures/errors/skips，25.95 秒**。[完整结果](../evidence/runs/m1-main-integrated/summary.json)及[逐项日志](../evidence/runs/m1-main-integrated/unittest.txt)包含原 main 和新功能全部用例。安装 wheel 后再次通过交易验收和四片研究场景，控制台 HTML 资源完整；全部 34 个运行模块与源码一致，见[安装证据](../evidence/runs/m1-main-integrated/wheel-smoke.json)。初版证据保留如下，不冒充合并后的运行结果。

已发布的六条原基准使用 **未修改的 main@f8d72ef** 同规模复跑，技术错误均为零：纯计算 11,488.8/s，4 库持久检查 817.10/s（其中持久提交 612.82/s），fused 模拟清算 431.17/s。详见 [复跑报告](main-baseline-rerun.md)。它们是原脚本的组件/closed-loop/模拟口径，不是新的真实双侧撮合、开放环持续生产吞吐。

## 初版可复跑证据（保留历史）

- 运行代码提交：`ec5fee919844d50d42a414ec9d3ec38e42e021b7`。
- 环境：Python 3.12.14、SQLite 3.53.1、Linux x86_64；硬件/资源与性能试验各自完整记录。
- 完整测试：**361 项通过，0 failures、0 errors、0 skips**，23.98 秒。
- 原始日志、运行时间、代码/文件哈希：[最终测试](../evidence/runs/m1-final/summary.json)、[逐项结果](../evidence/runs/m1-final/unittest.txt)。
- [源代码验收 JSON](../evidence/runs/m1-final/acceptance.json) 与 [离开源码目录后的 wheel 验收](../evidence/runs/m1-final/installed-acceptance.json) 均通过。全部 29 个已安装运行模块与审查源码哈希一致；[wheel 元数据](../evidence/runs/m1-final/wheel-smoke.json) 保存包 SHA-256。
- reservation 有界模型遍历 2,628 个安全状态；双侧 settlement 模型遍历 48 个安全状态，三种不安全变体均找到反例。模型不证明任意规模代码等价或 HA。[模型输出](../evidence/runs/m1-final/settlement-model.json)。

```sh
python tools/run_validation.py --output /tmp/uta-validation-new
python -m uta acceptance
python formal/explore_reservation.py
python formal/explore_settlement.py
python -m pip wheel . --no-deps --no-build-isolation --wheel-dir /tmp/uta-wheel
```

## 纵向案例

1. 原始经典快照：USD 1000、BTC 1；显式空挂单/条件单/待结算/转账集合。校验摘要后原子导入并冻结，再以新鲜规则/行情监督解锁。源 fence reference 仅合成证据引用，`source_fence_verified=false`。
2. 先给信用资金池注资并设置资产/账户限额，借 BTC 0.1，独立计息 0.001。以真实对手限价订单卖出再买回 0.1 BTC，费用合计 USD 0.008；还本付息 0.101 BTC。
3. 真实双侧开仓 90 单位线性永续，价格 100，开仓费 USD 3.6。行情降至 90 后监督器冻结风险并建立只减仓单。
4. 对手流动性只提供 45 单位，先确认第一次部分清算；剩余 45 仍保存为风险，无对手盘时成交数为零。重新打开数据库及 worker，再提供 45 单位对手订单，完成第二次清算。
5. 独立现金流：`1000 − .008 − 900 − 3.6 − 3.24 = 93.152 USD`；BTC 利息后为 `0.999`。最终无合约仓位、无借款负债、无重复分录，3 笔线性撮合、2 笔现货撮合可逐笔回放。
6. 对订单、撮合回执、仓位成本、费用、现金分录、源迁移及借款投影执行只读一致事务核对。独立验收验证了成功和失败的对账路径都不修改数据库。

## 失败记录与纠正

[首次集成](../evidence/runs/m1-preflight/summary.json) 保留 353 项运行、9 个错误；均来自早期清算 fixture 通过新借款构造了后来 LTV 门禁不允许的既存负债。修正为从明确经典快照导入旧义务，保留原始资产/负债与目标数值，没有削弱借款门禁或跳过测试。随后 [355 项集成运行](../evidence/runs/m1-integrated/summary.json) 全部通过，再加入未知 worker 异常暂停及独立运行时回归，最终 361 项通过。

实际发现并修复的缺陷包括清算 Decimal 上下文污染、truthy 确认、部分成交费用放大、成本尾差、旧行情订单授权破产、资金来源重复注资、无合约借款风险漏判、现货锁未先释放及不完整仓位对账。发现、修复、独立回归按功能 commit 保留。

## 数据迁移、兼容和回滚

保留原精确参考模型及旧本机演示。交易 schema v1→v2 回填订单累计计费元数据；信用 schema v1→v2 增加资金来源唯一约束，既有重复凭证导致拒绝启动，不删除或改写原流水。配置模式和资产精度固化，缺省参数不能降级已有 Cross 库。

上线/回退先停止旧写入者、备份到新路径、保留幂等及事件水位，按 [操作手册](operations.md) 离线恢复与回放。迁移补偿只在未发生后续账户变更时允许；已确认成交不能通过恢复旧快照撤销。软件 downgrade 不得打开更高 schema，发生新成交后采用 forward recovery 或审批纠错。

## 独立审查与未关闭门槛

量化验证：320 个账户、384 个压力情景及低精度环境无数值差异；运行时/撮合/磁盘容量/进程崩溃/HTTP 权限由其他工作组交叉验证。当前无已确认的 M1 合成范围阻断问题。

第一批生产仍需：真实稳定币结算、授权源连续增量及 fencing、借款强制处置、正式资金费/利率和产品参数校准、真实行情源/深度/历史回放、持续容量与长稳、跨故障域复制、签名/nonce/WS/IAM、真实金融及上线签字。无合约但借款风险不足目前只冻结并进入人工处置，不声称完成自动借贷清算。

单分片 5 秒诊断约 346 durable admissions/s，WAL 生命周期实验收益不稳定被否决默认合入；均未通过万笔/30 分钟门槛。分片容量是独立实验 PR，不由本报告授予生产资格。所有生产关卡见 [G0–G7](acceptance-gates.md)，`production_approved` 始终为 false。
