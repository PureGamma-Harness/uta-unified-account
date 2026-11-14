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

原有 `python -m uta serve --port 8080` 保留为**不认证的本机纯计算演示**，接收调用者提供的参考输入，不连接持久交易账本，不应作为交易入口或公网服务。

并发 main 新增的研究功能也完整保留：`python -m uta lab --db research.sqlite3` 启动本机模拟控制台，`python -m uta scenario --shards 4` 执行并重开回放，`python -m uta replay --db research.sqlite3` 验证模拟事件。研究库与认证交易库是两个不同权威，禁止混用同一路径，程序会拒绝不符的库。场景 PM 参考能力不授予生产 PM 权限；见 [研究说明](docs/research-lab.md) 和 [原口径基准复跑](docs/main-baseline-rerun.md)。

## 证据与验收

本系统政策不等于 Bybit、Binance 或 CME 的生产参数。参见 [证据库](docs/evidence-register.md)、[规则矩阵](evidence/rules.csv)、[目标架构](docs/target-architecture.md)、[账务规格](docs/accounting-spec.md)、[保证金规则](docs/margin-rules.md)、[清算及违约](docs/liquidation-rules.md)。金融负责人签核和真实资金审批尚未完成。

开放环工具区分纯计算、持久接纳及模拟清算，保留计划到达时间、逐请求结果、profile、环境与校验清单：

```sh
python benchmarks/run_benchmark.py --help
```

当前短测用于瓶颈诊断，**未满足每秒万条持久接纳/万笔清算成交、持续至少 30 分钟的生产门槛**。原始证据和口径见 [性能基线](docs/performance-baseline.md)，进程/磁盘满及形式化假设见 [故障验收](docs/fault-acceptance.md)。不把业务拒绝、尝试次数或纯模拟成交计入真实持久吞吐。

本轮完整交付、合入并发 main 后的 402 项测试、安装后验收、失败记录及回滚说明见 [M1 验收报告](docs/milestone-m1.md)。

后续 [分片实验报告](docs/milestone-sharding.md) 和 [分组持久准入报告](docs/milestone-grouped.md) 保留各自独立验收记录。最新集成通过 503 项测试，新增 opt-in 有界批提交、真实 HTTP、独立故障/金融验证及真实双侧清算探针。单次同配置短测为 464→744 条持久接纳/秒，所有生产容量门槛仍未通过；原始数据、适用边界和部署回退均在报告中。

## 交付顺序

1. M0：持久基础、证据与差距、测试、部署恢复。
2. M1：经典导入、现货借贷、线性双侧撮合、部分清算、重启与逐笔对账的合成纵向链路。
3. P1：首批产品的真实规则/资金交接、容量、容灾、独立金融和上线审批。
4. P2 / P3：多结算与交割/反向，再扩展期权全量重估与合资格 PM 抵消，逐批重新验收。

在相应门槛关闭前保持产品禁用。贡献约定见 [CONTRIBUTING.md](CONTRIBUTING.md)，公开提交仅使用合成或获授权脱敏数据，不提交密钥、客户账单和私人流水。

本轮同步了远端 main@02549e5 的研究文档更新；[研究命令业务流程](docs/workflows.md)、[场景模型](docs/risk-model.md) 与 [研究验证](docs/verification.md) 描述 simulator/store，认证交易与分批生产门槛仍以本页和 target-architecture.md 为准。
