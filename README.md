# UTA / Portfolio Margin Engineering Platform

统一交易账户与组合保证金平台的可审查工程实现。保留精确参考计算、手算案例和事件回放，逐步交付权威账本、现货借贷、多币种抵押、交易前风控、本地撮合、结算、清算及恢复工具。

**当前是合成数据的单节点工程验收版本，尚未通过生产验收。** 第一批产品、万笔持续吞吐、多节点容灾和真实资金启用各有独立门槛；PM、期权、反向及交割产品默认禁止启用。参见 [验收门槛](docs/acceptance-gates.md)、[差距分析](docs/gap-analysis.md) 和 [产品矩阵](docs/product-support.md)。

## 已实现的工程主链路

- **持久账本**：逐币双分录、精确 minor units、幂等事件、不可改流水、哈希链及独立回放。账户、订单占用、仓位、费用和 outbox 在同一 SQLite WAL/FULL 事务提交。
- **交易风控**：持久限价预占、部分成交累计计费、最新行情下的执行前风险复核、累计只减仓约束、暂停与账户冻结。并发连接不能重复花费同一保证金。
- **本地双侧撮合**：数值价格/时间优先、maker 价格、真实对手订单和唯一回执，两侧结算原子提交。无对手盘不生成成交；未宣称跨分片原子性。
- **借贷**：已注资资金池、资产/账户限额、本金与利息分离、同币还款、债务投影对账。保留总资产与总负债，不先净额化再折扣。
- **经典账户迁移**：摘要校验、原子导入资产/负债/仓位、冻结保护、持久回执及受限补偿回退。不支持的冻结或在途订单明确拒绝；真实源 fencing 与增量切换仍是生产缺口。
- **风险规则**：不可变版本行情、时效检查、Cross 规则、阶梯抵押、借款限额和压力参考。未实现的产品、对冲与 PM 模式不能通过配置开启。
- **清算**：持久计划、监督冻结和撤单、只减仓、本地实际部分清算成交及重启恢复。保险基金与 ADL 自动处置未启用。
- **接口与运维**：账户隔离、reader/trader/funding/risk/admin 分权、私有事件分页、凭据轮换、健康检查、安装包、SIGTERM 排空、一致备份与离线恢复。

## 入口与数据权威

| 入口 | 实际执行路径 | 使用说明 |
| --- | --- | --- |
| `python -m uta exchange` | v1 同步 `ExchangeService`，单个认证交易数据库；响应等待金融 COMMIT | [API 契约](docs/api-contract.md)、[部署手册](docs/operations.md)；可选 `--batch-admission` 是内存有界队列的批提交，`--automate` 启动本进程后台工作 |
| `python -m uta.durable_cli serve`，安装后为 `uta-durable serve` | v2 parent 入队/查询，独立分片 PID 持租约执行；先返回入队 ACK，再查询业务终态 | [持久 CLI](docs/durable-cli.md)、[v2 契约](docs/durable-api.md)、[进程与恢复](docs/durable-process.md)；已有 managed 布局，required 决策审计，默认 HMAC + TLS |
| `python -m uta lab`、`python -m uta scenario`、`python -m uta replay` | `Simulator` + `Store` / `ShardedStore`，独立研究库 | [研究说明](docs/research-lab.md)、[模拟器](docs/simulator.md)；包含场景 PM 参考与事件回放 |
| `python -m uta demo`、`python -m uta serve` | 调用者输入的无状态参考计算 | `serve` 为本机不认证演示；不持有交易账户权威 |

源码入口见 [同步及研究命令](uta/__main__.py)、[managed CLI](uta/durable_cli.py) 和 [v2 HTTP factory](uta/durable_gateway.py)。`python -m uta ... --shards` 配置研究路径；managed 分片数量由显式 `uta-durable init --shards ...` 固定，不能借该研究参数改造 `exchange`。各类数据库应使用各自的私有路径和初始化流程；managed 金融写入必须由持有效 token 的 writer 完成。

## 运行与测试

Python 3.10–3.13，运行时只使用标准库。

```sh
python -m uta demo
python -m unittest discover -s tests -v
python -m uta acceptance
python formal/explore_reservation.py
python formal/explore_settlement.py
python formal/explore_group_commit.py
```

`acceptance` 在临时目录使用合成资金，不访问外部账户；输出明确包含 `production_approved: false`。完整测试包含真实 loopback HTTP 和子进程故障，需要运行环境允许本地 socket。

安装与认证服务：

```sh
python -m pip install .
python -m uta exchange \
  --database /var/lib/uta/exchange.sqlite3 \
  --credentials /etc/uta/credentials.json \
  --host 127.0.0.1 --port 8080
```

先按 [部署与恢复手册](docs/operations.md) 创建专用用户、私有目录和凭据。新数据库默认暂停新增风险；发布可信新鲜行情并经运营确认后再解除暂停。当前默认单一合成 USD 结算，真实 USDT/USDC 不能通过重命名示例币种获得验收。

本地撮合可独立轮询同一权威数据库：

```sh
python -m uta.matching --database /var/lib/uta/exchange.sqlite3 \
  --symbol BTC-PERP --loop
```

这条命令只撮合已接纳的对手订单，不创建资金或价格。受产品/规则配置管理的数据库必须使用相同配置打开，不能缺省降级。见 [API 契约](docs/api-contract.md) 和 [撮合结算](docs/matching-settlement.md)。

上述独立撮合命令适用于非 managed 的同步 authority。managed 分片由其 worker 在 router gate 和有效租约内调用撮合，不能用这条无 writer token 的命令打开受管理分片。需要 v2 部署时，先运行 `python -m uta.durable_cli --help` 并按 [持久 CLI 手册](docs/durable-cli.md) 完成初始化、认证配置、行情发布及显式激活。

原有 `python -m uta serve --port 8080` 保留为**不认证的本机纯计算演示**，接收调用者提供的参考输入，不连接持久交易账本，不应作为交易入口或公网服务。

并发 main 新增的研究功能也完整保留：`python -m uta lab --db research.sqlite3` 启动本机模拟控制台，`python -m uta scenario --shards 4` 执行并重开回放，`python -m uta replay --db research.sqlite3` 验证模拟事件。研究库与认证交易库是两个不同权威，禁止混用同一路径，程序会拒绝不符的库。场景 PM 参考能力不授予生产 PM 权限；见 [研究说明](docs/research-lab.md) 和 [原口径基准复跑](docs/main-baseline-rerun.md)。

## 证据与验收

可选 `DurableLedger.verify(ordered_postings=True)` 的兼容性及首错顺序见 [账本回放的预取与解码边界](docs/history-postings-error-order.md)。该试验默认关闭；完整金融校验和原失败记录保留，旧性能观测不能作为修复后源码的加速或启用依据。

本系统政策不等于 Bybit、Binance 或 CME 的生产参数。参见 [证据库](docs/evidence-register.md)、[规则矩阵](evidence/rules.csv)、[目标架构](docs/target-architecture.md)、[账务规格](docs/accounting-spec.md)、[保证金规则](docs/margin-rules.md)、[清算及违约](docs/liquidation-rules.md)。金融负责人签核和真实资金审批尚未完成。

开放环工具区分纯计算、持久接纳及模拟清算，保留计划到达时间、逐请求结果、profile、环境与校验清单：

```sh
python benchmarks/run_benchmark.py --help
```

当前短测用于瓶颈诊断，**未满足每秒万条持久接纳/万笔清算成交、持续至少 30 分钟的生产门槛**。原始证据和口径见 [性能基线](docs/performance-baseline.md)，进程/磁盘满及形式化假设见 [故障验收](docs/fault-acceptance.md)。不把业务拒绝、尝试次数或纯模拟成交计入真实持久吞吐。

本轮完整交付、合入并发 main 后的 402 项测试、安装后验收、失败记录及回滚说明见 [M1 验收报告](docs/milestone-m1.md)。

后续 [分片实验报告](docs/milestone-sharding.md) 和 [分组持久准入报告](docs/milestone-grouped.md) 保留各自独立验收记录。该轮集成通过 506 项测试及 Python 3.10–3.13 CI，新增 opt-in 有界批提交、真实 HTTP、独立故障/金融验证及真实双侧清算探针。单次同配置短测为 464→744 条持久接纳/秒，所有生产容量门槛仍未通过；原始数据、适用边界和部署回退均在报告中。

0.3.0a1 评审候选新增默认关闭的精确预占/行情解析缓存，以及受 router 屏障保护的分片批提交。605 项双版本完整验收之后增加真实启用缓存纵向链路及归档验证，最终 607 项复验与 CI、八个工作流的交叉审查和回退见 [内核与分片准入报告](docs/milestone-kernel.md)。同源码三次配对中位持久接纳为均匀 708→993/s、热点多样 616→856/s；30 万到达含 23.8 万过载，仍未达到生产门槛，不以短测启用真实资金。

0.4.0a1 在独立评审分支增加同库持久命令、独立分片 writer 进程、真实历史二进制写入门禁、HMAC+TLS 与持久 nonce、历史行情和线性决策审计。参见 [当前交付与阻断项](docs/milestone-durable.md)。已排队不等于风险接纳；本机租约不等于跨区容灾。实际 24 小时测试独立冻结在早期源码，须等待真实时长与终态对账，不能作为本候选或万笔容量已通过的证明。

## 交付顺序

1. M0：持久基础、证据与差距、测试、部署恢复。
2. M1：经典导入、现货借贷、线性双侧撮合、部分清算、重启与逐笔对账的合成纵向链路。
3. P1：首批产品的真实规则/资金交接、容量、容灾、独立金融和上线审批。
4. P2 / P3：多结算与交割/反向，再扩展期权全量重估与合资格 PM 抵消，逐批重新验收。

在相应门槛关闭前保持产品禁用。贡献约定见 [CONTRIBUTING.md](CONTRIBUTING.md)，公开提交仅使用合成或获授权脱敏数据，不提交密钥、客户账单和私人流水。

本轮同步了远端 main@02549e5 的研究文档更新；[研究命令业务流程](docs/workflows.md)、[场景模型](docs/risk-model.md) 与 [研究验证](docs/verification.md) 描述 simulator/store，认证交易与分批生产门槛仍以本页和 target-architecture.md 为准。
