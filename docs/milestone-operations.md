# Managed 读模型、迁移与恢复验收台账

本里程碑由 [Draft PR #13](https://github.com/PureGamma-Harness/uta-unified-account/pull/13)
交付，基于 PR #10。集成负责人负责源码冻结；安装包组、启动协议组、诊断组和独立验证组
分别提交证据并交叉审查。当前 **生产 NO-GO**，没有真实金融负责人或上线审批人的签字。

## 业务及格式变化

新增账户隔离的 v2 只读视图，使用同一 RO 快照返回账务、挂单、仓位、费用、债务、清算及
历史决策引用。游标绑定账户、事件流和版本；无可复算在线风险接口时 `/risk` 明确返回 501。
它不通过构造金融服务自动修复 schema。managed 交易范围仍是合成 USD Cross 线性限价、
reduce-only、撤单和既有债务同币还款。新借款、现货、PM、Isolated、真实稳定币产品、
跨片撮合结算及模式切换没有因此启用，按现有 unsupported 契约拒绝。

迁移在任何 sealing 副作用前核对所有分片的原生账本保护、逐币完整账本及现货义务。
live/partial 现货订单、残余冻结或缺失/弱化的历史证据拒绝切换。终态现货历史必须保持
回执、双方成交、订单、审计事件与分录双向一致，不能用补造回执或安装缺失 guard 修复。
来源边界见 [迁移范围](managed-migration-scope-review.md)。

owned startup 在固定 schema 准备后执行原 ledger/credit 完整 RO 校验；keeper 续仍有效的
原 token，最后 fresh fenced COMMIT 成功才 READY。启动线程与本进程 keeper 的写操作在
SQLite 连接前排队，原 TTL、SQLite busy timeout 和逐笔 SQL 的执行次数不变。外部写者
竞争、租约过期、续约结果未知仍使本次启动失败，不能凭内存完成标记复活 authority。
详见 [启动协议](owned-startup-protocol.md)和[写竞争反例](startup-write-contention.md)。

内部执行故障新增有界、去敏事件，与 attempt/quarantine 元数据同事务提交；不存异常
message、SQL、locals、路径或密钥。原金融终态不被故障记录覆盖。损坏的 SQLite 存储类型
以类型化摘要保留，不能让诊断自身阻塞隔离坏命令。

## 已发生的验收结果

| 固定源码 | 本地完整测试 | CI | 安装包 | 集成结论 |
| --- | --- | --- | --- | --- |
| `13e6924` | 三运行时各 1078 通过 | push/PR 各四版本通过 | 新安装及归档核验通过 | 仅该历史范围工程通过 |
| `24ac06b` | 三运行时各 1092，均 1 失败 | 两轮失败 | 不据此宣称新包通过 | NO-GO，保留诊断新增事件夹具失败 |
| `4608ffe` | 3.12/3.13 各 1096 通过；3.10 有 1 失败 | PR 四版本通过；push 3.10 三项失败，其余通过 | 新安装 8、RO 视图 3 及全部源文件核验通过 | NO-GO，包通过不能抵消完整测试失败 |
| `7ae94eb` | 三运行时各 1110 通过 | push 四版本通过；PR 3.12 一项 ERROR，其他三版本通过 | 未据失败源码重新构建独立包 | NO-GO，负例在预期故障阶段之前真实过期 |

`7ae94eb` 的[三本地及八份 CI 原始结果](../evidence/runs/operations-qa-7ae94eb/README.md)
全部保留。PR checkout 是 merge 提交 `bd8e5b4`，208 项验证输入与 head 完全相同，但不
改写为 head SHA。唯一 ERROR 发生在 external producer BUSY 负例的构造阶段：原 0.4 秒
测试租约已过期，系统正确拒绝续约，尚未进入强制写锁区间。这不证明任何生产 lease
应被延长，也不能把 setup 失败当成 BUSY 负例通过；独立测试修正仍须重新冻结验收。

原失败不得用同源码另一次成功覆盖。后续修复已在独立工作树构造真实 SQLite 竞争和
真实 HTTP UNKNOWN 反例；这些反例说明可发生的路径，不证明缺少异常取证的旧失败具有
唯一根因。新源码必须另行冻结并完整重测；本表不预填未来结果。

同 ID 的 UNKNOWN 恢复测试保留 50ms 服务等待和 4s socket timeout，只重试两个明确的
503 状态；仍要求唯一接纳、唯一撤单、逐笔分录及重开结果一致。只读诊断将真实 BUSY/
LOCKED 归为有界诊断超时，完整性/IO 错误仍是 fatal，未知金融字段不伪装为零或 ready。

## 部署与回滚

仅在新的私有合成目录以固定源码或经核验 wheel 启动。停止源 writer，备份完整 control、
各 shard、inbox、审计及认证水位，完成离线预检后保持 HALTED；发布同一新鲜行情、核验
全部片的实际 receipt/payload 并显式激活。CLI 及步骤见 [运行手册](operations.md)和
[managed 运行说明](managed-soak.md)。本里程碑没有实际部署到目标交易所或可用区。

不可逆 fencing 后的失败保留 HALTED/incomplete，按原业务 ID 查询并前滚恢复。禁止删除
authority、重置 generation/nonce、降级到不识别 guard/schema 的旧二进制，或用旧备份
抹去已确认的新成交。停止入口并 drain 后选择修复 artifact，重开逐笔对账；若恢复结果
未知，保留未知状态并停止依赖操作。

容量仍参考 [720 短探针](managed-corrected-baseline-20261117.md)：S1 有 1 次内部 retry、
418 笔成功超过 1 秒，技术稳定性和延迟门槛未通过。行情 epoch 与金融批处理当前只有
独立设计/有界模型；本里程碑不声称运行时收益。6 小时新 managed 作业、持续万笔、复制
RPO/RTO、保险基金/ADL、私有 WS、金融签核仍待完成。原 887 历史 24 小时任务不能资格化
本源码，实际完成前所有相应通过标志保持 false。
