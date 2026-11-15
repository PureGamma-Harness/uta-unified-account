# 精确计算缓存与受控分片批提交：验收记录

本轮以 PR #3 的 `92086bd` 为起点，由预占内核、行情、路由、独立金融、故障、性能、运维交叉审查和协议模型八个 Agent 工作流滚动交付，集成负责人负责合并与最终复验。版本为 **0.3.0a1**。所有资金、行情、借款和对手深度均为合成数据；工程审查不是具名金融负责人或真实资金审批。

交付 [PR #6](https://github.com/PureGamma-Harness/uta-unified-account/pull/6)，叠加 PR #3，保持 Draft。**万笔持续容量、PM、多节点容灾与真实资金启用继续 BLOCKED。**

## 业务与兼容边界

精确预占缓存仅记忆完整经济输入对应的数学结果；行情缓存仅记忆完整持久 payload 对应的不可变解码模型。每次仍读取权威订单/账户与行情行，重新检查时效、规则、产品、暂停和剩余额度。缓存中没有账户风险决定、可用额度或可长期复用的准入授权。

`ExchangeService`、CLI 和 `ShardRouter` 的两项容量默认均为 0。容量 0 保留原 Fraction 参考计算；显式容量可分别启用预占与行情缓存。同版本价格修改不能命中旧 payload，数量、已成交量、累计收费、IM、mark、limit、费率与精度等任何经济输入变化都参与重算。异常解码不缓存，命中不延长价格有效期。

`RouterAdmissionBatcher` 由路由器持有实际事务：shared flock、控制状态、资金 claim、片内身份、行情摘要与 savepoint 检查覆盖真实 COMMIT，再发布 Future。有限 worker、队列与撤单保留槽均有明确上界。同一实例同一 shard 至多一个在途组；不承诺多个 adapter、同步调用者或跨重启的全局 FIFO，也不提供跨分片原子多腿交易。

| 范围 | 本轮支持 | 未支持或拒绝行为 |
| --- | --- | --- |
| 产品/模式 | 原有合成 USD Cross、现货借贷、多币抵押和线性永续路径 | 未扩展产品许可；生产 PM、Isolated、实际 USDT/USDC、交割、反向及期权仍按原矩阵拒绝 |
| 订单 | 原限价、累计 reduce-only、撤单、部分成交与幂等查询 | 未新增市价/条件/改单或原子多腿接口；不支持项仍拒绝 |
| 单库 HTTP | 可选分组提交、两项缓存容量、risk/admin 诊断 | 客户 reader/trader/funding 不可读取全局缓存指标 |
| 分片接入 | 本地主机 Python adapter，经过原 router 权威与屏障 | 没有分片 REST/WS 服务、跨片资金事务、复制、在线 resharding 或 HA |

无 schema 迁移、无新保证金政策。缓存容量不进入经济 layout descriptor，重启为 0/0 不更改资金归属、精度、规则或分片布局。每个 service 都有自己的容量，分片数及并存进程会放大总内存需求；entry 上限不是硬 RSS 上限。

## 正确性、故障与独立审查

冻结运行代码为 `146fe74d3006d39b5ecb3fb3b2d1cbf2e133ad6a`，本地 Python 3.10 / 3.12 各 **605 项完整通过**，0 failures/errors/skips，50.68 / 47.86 秒。随后增加启用缓存的完整纵向链路和 300,000 条归档验证两个测试；最终完整测试及四版本 CI 原始状态保存在下列索引，不用旧测试数替代新候选。

- [最终 Python 3.10](../evidence/runs/kernel-final/python310-607/summary.json) / [逐项日志](../evidence/runs/kernel-final/python310-607/unittest.txt)，[最终 Python 3.12](../evidence/runs/kernel-final/python312-607/summary.json) / [逐项日志](../evidence/runs/kernel-final/python312-607/unittest.txt)：607 项各完整通过，0 failures/errors/skips，50.49 / 48.24 秒。
- [四版本 CI 元数据及选取日志](../evidence/runs/kernel-final/github-ci.json)：`9983b64` 的 Python 3.10–3.13 均完成成功，3.13 实际607项且没有 unclosed database 警告；[完整运行](https://github.com/PureGamma-Harness/uta-unified-account/actions/runs/43690088873)。之后仅归档证据与文档，不改变已验运行模块。
- [冻结代码的 605 项原始结果](../evidence/runs/kernel-final/python312/summary.json)与[首次预检及真实失败](../evidence/runs/kernel-preflight/)均保留。Python 3.10 缺少 `sqlite3.SQLITE_FULL` 导出，只调整测试兼容写法；真实 SQLite 页数上限、整批回滚和原 ID 恢复预期不变。
- [独立金融验证](kernel-validation.md)：896 个 Fraction 标准输入、低 Decimal context、部分成交、累计收费、LRU/清空、政策/行情修改、并发额度与冷重启。
- [独立故障验证](kernel-faults.md)：真实 SQLITE_FULL、延迟外键 COMMIT 失败、提交前后 `os._exit`、已提交响应丢失、跨实例争用、同版本 payload 损坏、换片身份、旧 control 丢 claim、队列取消及关停。
- [独立运维交叉审查](kernel-operations-review.md)：实际 HTTP 权限、早拒不建库、独立 wheel 安装、SIGTERM 排空、warm cache 下失败回滚及同 DB 关闭缓存。报告区分当时审查源码/包与本轮最终安装证据。
- [最终包与模型记录](../evidence/runs/kernel-final/package-and-models.json)：仓库之外安装 0.3.0a1，40 个运行模块/dashboard 文件与源码逐一匹配；原参考验收、研究 scenario、CLI 和启用缓存的真实借贷/撮合/清算链路均执行成功。

启用缓存的纵向链路没有伪造金融结果：仅在构造实际 `ExchangeService` 时选择 32/4 容量，之后经典导入、资金池借贷、利息、现货真实对手撮合、永续真实对手开仓、第一笔 45 单位清算、无深度残余风险、同库服务重建、第二笔 45 单位清算和逐笔对账均走原服务。最终现金 **93.152 USD / 0.999 BTC**，3 笔线性匹配、2 笔现货匹配，并确认发生缓存命中。服务对象重建不能称机器掉电或 HA 演练，源 fencing 仍未验证。

独立组推动关闭两类实际错误处理缺口：激活分片的行情缺失/损坏应持久化全局暂停；`router_halted` 的可隔离分支也必须检查底层 SQL/账本/存储异常链。真实 SQL 在第二个命令已写入后被包装成暂停错误的回归，要求包括第一单在内全部回滚。没有通过放宽资金、权限或回执断言获得通过。

## 协议模型的实际证明边界

[独立模型](shard-admission-model.md)和[原始 JSON](../formal/results/shard-admission-model-20261115.json)分别验证：调度/行情屏障 2,742 个状态、5,862 条转换；崩溃/原 ID 重试 20 个状态、32 条转换。8 个故意不安全变体全部产生反例。两个子模型不是组合证明，不证明实现等价、任意规模、跨 adapter/restart FIFO、活性、公平性、复制或硬件 RPO。

原预占、双侧结算与单库组提交模型继续保留；CI 新增运行分片模型。模型和真实 SQLite/进程/撮合测试互相补充，不互相替代。

## 同源码重复配对结果

测量源码固定为 `146fe74…`，tracked 工作树与前后所有运行模块/生成器摘要一致。4 CPU quota、5 个可见 CPU affinity、16 GiB 内存上限、AMD EPYC 9V74、本地 overlay 上 SQLite WAL/FULL，无复制。其他协作 Agent 在测量窗口停止本地计算；共享执行主机不是专用性能硬件。

每个 cohort 三对交替 AB/BA/AB。每次单进程/单库，100 个账户，5000/s × 5 秒，batch64、4 dispatcher、共享 outstanding=1024、SQLite busy timeout=2 秒。base 容量 0/0，optimized 为 4096/4。热点 cohort 单列：10 个账户承担 30% 到达，40 种方向/数量/合法限价组合；未触及每账户 1000 挂单上限。

| cohort / 模式 | 三次中位持久接纳/s | 三次成功接纳 P99 中位/ms | P99.9 中位/ms |
| --- | ---: | ---: | ---: |
| 均匀 / 0,0 | 708.20 | 1786.19 | 1789.76 |
| 均匀 / 4096,4 | 992.63 | 1358.28 | 1363.72 |
| 热点多样 / 0,0 | 615.67 | 2121.23 | 2129.73 |
| 热点多样 / 4096,4 | 856.38 | 1478.72 | 1481.68 |

表中延迟是三次“成功持久接纳”分位数的中位数，**不是**合并样本分位数；每次完整 all/accepted P50/P95/P99/P99.9 在[性能报告](kernel-performance.md)。所有延迟从原计划到达计时，吞吐分母包括实际排空。不能拿大量快速拒绝后的 all-response 尾延迟替代成功接纳尾延迟。

共 12 个独立运行、**300,000 次计划到达**，61,852 次持久接纳、238,148 次过载；接纳中 38,025 次超过 1 秒软期限。业务拒绝、技术失败和结果未知为零。每次已确认订单保持 OPEN 和完整预占，重开时关闭两缓存，按每个订单真实经济输入独立 Fraction 核对订单、事件、现金、版本、占用与账本。

三对比率：均匀 1.462 / 1.402 / 1.399，热点多样 1.405 / 1.362 / 1.406。这是少量 5 秒合成样本的观测收益，非长期稳定性或最大容量证明。两类仍大量过载与迟到，**所有正式容量 gate 均为 false**，不与前一天不同源码/环境的 744/s 混比，也不把不同新库的总请求量算作一次持续容量。

[完整 raw、环境、计划、命令和校验清单](../benchmarks/results/20261115-kernel-cross/)保留全部记录；源 SQLite 仅留本地，不上传公开结果。该测量没有调用新分片 adapter，不能据它声称分片或多节点吞吐。

## 部署、关停和回滚

按[运行手册](operations.md)从审查过的 SHA 构建独立 wheel，核对包与源码摘要；0.3.0a1 是工程评审包。先验证原配置/产品规则与合成链路。需要评估优化时在原单库 exchange 命令增加：

```sh
--batch-admission --admission-batch-size 64 \
--reserve-cache-size 4096 --market-cache-size 4
```

不加参数仍为 0/0；batch64 是本次测量值，没有改变批长默认32。新分片 adapter 的显式 Python 接入、容量、控制检查和关闭方式见[分片准入契约](shard-admission.md)。`--shards` 仍属于研究命令，不是新的生产分片 HTTP 部署开关。

监控每个 service 的命中/淘汰/解码失败、adapter 排队/在途/技术失败与预期拒绝、行情年龄、磁盘、对账差异及端到端尾延迟。分片 `market_rejected` 统计包含其预期市场/全局暂停不可用结果，不能把它全部理解成价格过期。诊断计数不回滚，不能作为金融分录或唯一接纳数量。

回退时先暂停新增风险、停止接收新请求，排空 HTTP、批队列、撮合及其他合作写者；核对已确认与结果未知原 ID 后做一致备份。同库将容量设为 0/0 可回到参考计算。撤去 router adapter 时回到原同步 **router** 方法，保留全套 control、layout 和全部分片；禁止直接打开私有 shard service 绕过屏障，禁止单独回退旧 control 或更改分片数。

代码降级到旧评审版本时移除其不认识的新 CLI 参数；无 schema 变化并不允许恢复一份遗漏新成交的旧数据库。已确认事件保留，未知命令按原 ID 查询/重试。未 COMMIT 的内存队列不是持久接纳；停止期限需覆盖实际 HTTP/锁等待和队列排空，不能无条件依赖示例30秒。

剩余瓶颈仍包含逐次读取/扫描活跃挂单和聚合精确风险。本轮没有引入未经独立验证的账户风险缓存或投影。事务内增量预占、多进程分片、行情扇出、真实流动性下持续清算、混合热点长稳、租约/fencing、复制与实测 RPO/RTO 都需继续独立实现和验收；G3–G7 不因本轮提升而关闭。
