# 可选持久批处理、账户缓存与连接内借款：工程验收中

本里程碑建立在固定工程版本 `763202d` 之上，独立于该版本正在执行的 smoke/长测。
声明版本为 `0.5.0a1`，默认批大小和 NORMAL 缓存容量均为 0；managed 新借款仍不启用。
当前分支未完成全量冻结、安装包、容量或长稳
验收，**生产 NO-GO**，不得用本文件覆盖此前任何失败或为新源码复用旧报告。

## 运行时与资金边界

只有全新合成 managed 布局可以通过显式离线 `init --durable-batches` 创建不可逆能力。
已有布局不自动迁移。持久格式标记使不识别它的旧实际二进制拒绝成为 writer。
`serve --financial-batch-size 3` 等显式设置选择 3..8；默认 0 保留单条处理。即使配置为 0，
具有该能力的布局仍须先恢复未决 manifest，核对全部原 CID 并真实续租后才 READY。

manifest 元数据提交与金融提交是两笔真实事务。元数据角色仅可向两张官方批表 INSERT，
不具有订单终态、金融分录或 DDL 权限，仍受原生 SQL UDF、PID/token/租约和最终 fencing
约束。逐命令效果、终态、逐命令审计和 COMMITTED disposition 同一金融 COMMIT；
queued ACK 和 manifest 都不是接纳回执。控制命令保持原单条协议。

每账户 FIFO、head backoff、单批每账户数量限制和逐项完整风险检查保留。每条业务拒绝
实际回滚其 SAVEPOINT；同事务后继能看到前序真实预占、撤单和还款。软预算可能形成
selected=3/executed=1 或 0，必须按实际完成计数。正常路径增加元数据 COMMIT，不能
无测量宣称吞吐收益。新增批级技术故障、恢复、未决与个体 attempt 分开统计。

COMMIT 或回执未知时，从持久 manifest 查询全部原 CID。任何读取未知即停止恢复，
不能因前几个已终态跳过后续，也不能扣无归因邻居的 poison attempt。新 owner 先解决
旧 manifest，保留原 ID。精确 schema 校验覆盖保留命名空间或表归属的所有对象类型，
包括合法六条原生 guard；拒绝缺失、额外或弱化定义，不自动修复。

借款 `_borrow(connection,...)` 只加入已有正确 authority 的 financial 事务，不创建或
提升角色，不自行 COMMIT。调用者负责 SAVEPOINT 或整笔回滚，不能捕获晚期风险拒绝后
继续提交已暂存分录。资产、折扣、借款本金、利息及资金池归属保留原精确规则。

managed authority 对未经新借贷能力审计的新借款返回 501；canonical 原 CID 重放先行，
preseal bootstrap、冲突检测和还款保留。这是当前代码的拒绝政策，未增加借款操作级的
旧二进制 SQL 门禁。现有资产限额为单片额度，跨片总预算仅有离线分配设计，未实现全局
动态预算；不得把单库 sum 当成全交易所原子额度。

`normal_cache_size` 仅复用重复的 NORMAL 监督结果；启用后每次命中仍检查当前 SQL 证明、
状态、版本及行情新鲜度。冷启动的完整账本和借贷验证、原生 prepared worker、READY 前
恢复及最终金融 COMMIT 的 fencing 不受此设置绕过。容量范围为 0..65536，默认 0。
`--normal-cache-size 0` 关闭新缓存使用，不改变持久能力或恢复要求。

| 范围 | 此里程碑行为 | 尚未提供的操作 |
| --- | --- | --- |
| 合成 USD 线性永续 / Cross | 原有持久下单、撤单、还款、真实撮合及清算链路；可选批处理与缓存 | 多结算币、交割、反向、期权及合资格现货 PM 抵消不启用 |
| 新借款与现货订单 | 封存前合成引导与已有借款还款保留；managed v2 两者均返回 501 `unsupported_durable_operation`，trusted credit 新借款返回 501 `unsupported_credit_operation` | 没有在线借款能力、managed 现货撮合入口或动态跨片总额度 |
| Isolated、PM 与模式转换 | 无对应 managed 启用入口 | 不将研究计算器视为已接纳的账户模式；不以参数静默切换 |
| 订单与批处理 | 已有受保护限价/只减仓规则；原 CID 查询及重放 | 条件触发、多腿原子策略和外部交易所接入不因批处理而获得支持 |

此表说明本次新增代码的授权范围；精确 HTTP 错误与订单状态遵循现有
[接口契约](durable-api.md)。不支持的产品未进入可交易目录，输入校验拒绝；不产生资金预占。

## 证据与审查

- 批运行时在 `ebf8459` 三运行时各 105 项专项通过；真实独立 worker、prepare 后死亡、
  换代恢复和旧二进制拒绝有工程证据。后续金融四例和 preseal 夹具适配另存原件。
- 连接内借款和 managed 拒绝边界三运行时各 113 项专项通过。独立金融组用整数分录及
  Fraction 手算七例、三运行时通过，首轮夹具错误原样保留。
- 独立恢复组七例三运行时通过：实际 deferred-FK COMMIT 失败、准备/金融回执丢失、
  最后 CID 读取未知、prefix0/1、混合终态换代及 backoff。其 READY 结论是静态顺序审查，
  不冒充独立 HA 测试。
- NORMAL 缓存已合入，38 项专项在三种运行时通过。独立的批处理与缓存组合三例在三种
  运行时通过，包含真实 worker 死亡、换代、RECOVERED 先于 READY，以及最终原 CID
  唯一财务回执。所选三条不保证同一次金融 COMMIT 全部执行，实际 prefix 如实保留。
- 完整预检 `45818c0` 实际运行 1,219 项，1 项失败、0 错误、0 跳过；原日志保留在
  `evidence/runs/capacity-preflight-45818c0`。初始 PR CI 的 Python 3.11 同类失败另存
  `evidence/runs/pr14-initial-ci-4e59084`。修复 `82688a6` 仅使测试等待真实 owner READY
  和原行情发布 CID 的持久成功；原 0.25 秒 fanout timeout、2 秒行情 TTL 与 missing/
  partial/stale/recovery 断言保留。三个 API 专项通过不等于新全量报告通过。
- `0.5.0a1` 的源码声明、冻结源码版本提取、唯一 METADATA Version 及安装版本一致性
  校验有 19 项专项在 Python 3.10 和 3.12 通过；实际新包尚待生成和独立安装验收。
- 新基准工具也必须纳入下一次固定源码验收。旧版本的全量、CI、安装与长稳结果均不可
  晋升为本里程碑结果；重新冻结后执行三运行时全量、push/PR 八个 CI 作业和真实包校验。

具体命令与原始记录见 [批实现](durable-financial-batches-implementation.md)、
[独立恢复](batch-recovery-independent-review.md)、[借贷边界](managed-credit-boundary.md)
及[独立金融](managed-credit-independent-review.md)、[组合验证](batch-cache-combination-validation.md)
和[版本声明](release-version-declarations.md)。Agent 审查不替代真实金融或上线签字。

## 部署与回滚

在独立私有合成目录使用固定 artifact，离线预检全部分片，显式创建新布局并保持 HALTED。
核对能力、账本、资金来源、队列和审计，发布真实新鲜行情并显式激活后才允许测试请求。
异常时关闭入口、drain 并保留原 CID，修复版本先 query-all 恢复，再重开逐笔对账。

降为 `financial_batch_size=0` 仅改变新命令调度，不删除格式能力或跳过历史恢复。禁止
用旧二进制降级已启用布局，禁止删 manifest、重置 generation 或用旧备份抹去已确认
成交。存储/租约/完整性错误使作业停机或 unknown，不返回虚假成功。多节点复制、AZ
恢复、保险基金/ADL、真实资金与持续万笔验收均未完成。
