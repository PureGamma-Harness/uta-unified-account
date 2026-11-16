# 证据库与本系统政策

远端代码证据补充：初次检出之后出现的 `main@f8d72ef` 已在本分支合并，其六条基准已原样复跑；[复跑报告](main-baseline-rerun.md) 更正了初始 checkout 缺少基准材料的时间线。新增场景 PM 与控制台保留为研究系统，不绕过认证交易链路的产品启用门槛。

观察日期：2026-11-14 UTC。首次拉取的 main 为 `30deff6`；没有获得客户账户、交易所后台参数、历史逐笔盘口或生产事故的授权数据。所有测试账户、资金、成交、借贷和压力场景均为合成数据。官方网页只用于理解接口和方法，不证明本项目复现了任何交易所的规则或实测行为。

原始网页的请求地址、重定向后地址、HTTP 状态、取证时间、字节数、SHA-256 和简短摘录保存在 [证据清单](../evidence/sources/official-20261114.json)。重新取证运行 `python tools/collect_sources.py --output /tmp/official-new.json`，人工比较后新增记录；不得覆盖旧证据或自动修改风险政策。哈希用于识别取得的文档版本，不是第三方时间戳或网页永久存档。

| 来源 ID | 核验结果 | 可以支持的结论 | 不支持的结论 |
| --- | --- | --- | --- |
| BYBIT-WALLET | V5 钱包字段文档 HTTP 200 | `totalEquity`、`totalWalletBalance`、账户 IM/MM 及可用余额是不同字段；手动借款存在新旧钱包口径变化 | 仅凭钱包净额重建全部资产负债、订单冻结或生产 PM |
| BYBIT-COLLATERAL | V5 抵押品文档 HTTP 200 | `collateralRatio` 已标注过时；阶梯抵押和平台资格、用户开关需要分别考虑 | 把单一折扣参数当成当前 Bybit 实际阶梯表 |
| BYBIT-BORROW | V5 手动借款文档 HTTP 200 | 借款是显式业务接口 | 未授权账户的借贷额度、自动还款与利息时点 |
| BYBIT-CHANGELOG | V5 变更日志 HTTP 200 | API 口径有版本变化，需要记录适用时间 | 所有历史口径向当前余额公式直接兼容 |
| BINANCE-PM | 官方 PM account 目录 HTTP 200 | `uniMMR`、`accountEquity`、`actualEquity`、IM/MM 有不同字段和单位 | 内部 `equity/MM` 与交易所风险率数值等同、风险恶化方向可互换 |
| BINANCE-PRO-SPAN | 官方 PM Pro account 目录 HTTP 200 | PM Pro 与 Pro SPAN 有各自账户信息接口 | 两者的风险单元、抵消规则及参数等价 |
| CME-SPAN2 | 官方方法页面 HTTP 200 | 市场、流动性及集中度风险需要可解释归因 | 本项目获得 CME 专有参数、通过清算所认证或复制 SPAN 2 |

查询错误也保留为证据缺口：Bybit `/v5/account/info`、CME `/risk-management/span-2.html` 最初返回 404；Binance 若干旧详情路径返回 HTTP 200 的通用首页。取证脚本因此同时检查语义标记，不能只凭 HTTP 200 宣称证据有效。当前采用的是清单中的有效页面。

## 冲突、未获授权与选择

1. 不将钱包净值视为原始总资产。客户资产、借款本金和利息独立保存；先对资产折扣，再扣全部负债。依据为本地规则 ACCT-002；不假设 Bybit/Binance 的字段可以无损互换。
2. 抵押阶梯、借贷限额、压力参数与风险隔离是本系统的版本化政策。未取得交易所逐账户参数时，所有合成默认值只用于测试，不标注为交易所参数。
3. 内部 `margin_ratio=equity/MM` 在 MM 大于零时越低越危险；MM 为零时返回 `null`。清算直接比较金额，不能通过风险率字符串判断。外部 `accountMMRate`、`uniMMR` 留在各自适配器命名空间，未完成口径核验前不自动映射。
4. 第一批纵向链路采用单节点、Cross、单一合成 USD 结算。USDT/USDC 实际结算、真实经典账户写入者失效证明、跨可用区复制和 PM 产品启用均是未关闭的验收项，不将合成 USD 当作已上线的稳定币产品。
5. 没有获得真实事故与历史深度样本。行情中断、跳价、脱锚、无流动性、磁盘满和重复回执用标明假设的合成场景复现。历史校准、样本外回测和真实交易所差分结果保留为缺口。

## 规则变更与签核

每次规则 PR 需要更新 [追溯矩阵](../evidence/rules.csv)，提供人工案例、实现与独立验证结果，并保留代码 SHA、配置版本、市场快照和命令 ID。量化风险组负责公式；独立验证组可以否决启用。工程 agent 的审查记录不替代金融规则负责人的真实授权签字、模型委员会批准或真实资金上线审批。

## 后续可复现验证索引（2026-11-16 UTC）

下列记录固定到提交 `51623cb0e0081834e7e167039ba27fec582c9bc8`，不能把该提交的通过结果自动套用到后续提交。该提交的 Python 3.10–3.13 push/PR 共八项 CI 已通过；提交前对应源码的完整本地回归为 524 tests、32.391 秒。测试数量不是风险覆盖率，也不表示验收门槛全部关闭。

| 可复现证据 | 直接检查的性质 | 仍未证明 |
| --- | --- | --- |
| [成交竞态测试](../tests/test_fill_races.py) | 同 fill ID 并发重放只有一次业务效果；不同 ID 不能竞争超出剩余量；重启后继续结算 | 交易所端幂等、多主执行、跨节点 fencing |
| [账户作用域重放](../tests/test_account_scoped_replay.py) | 不同账户可独立复用订单/成交 ID；重启等值重放及冲突拒绝不改变逻辑数据库 | API 租户身份认证、真实客户隔离 |
| [网关路径作用域](../tests/test_gateway_path_scope.py) | 七种读取路径与五种取消路径的拒绝不调用 FakeService；合法路径正对照正常 | 反向代理路径规范化、外部部署、完整权限审计 |
| [优化模式验收负对照](../tests/test_optimized_acceptance.py) | 独立 python -O 子进程仍拒绝余额回读多一美元；正常与还原后验收通过 | 任意金融计算正确、真实行情校准、生产批准 |

从源码根目录运行单项：

```sh
python -m unittest discover -s tests -p test_fill_races.py -v
python -m unittest discover -s tests -p test_account_scoped_replay.py -v
python -m unittest discover -s tests -p test_gateway_path_scope.py -v
python -m unittest discover -s tests -p test_optimized_acceptance.py -v
```

这些测试均加入常规 unittest discovery；FakeService 不处理真实订单，验收使用临时合成存储。测试内的负对照仅临时 mock 回读结果，不删除运行时防护、不改真实数据库或外部安全设置。详细有限模型与实现边界见 [版本性质及耐久测试证据](../formal/version-property.md)。

下一阶段需要的是关闭证据缺口，而非只增加测试数量：真实源写入者隔离证明、复制与恢复水位、外部执行对账及未知结果处理、正式持续容量测量、金融校准与责任人签核，仍按 [验收门槛](acceptance-gates.md) 管理。上述新增证据不授权实盘，不自动批准迁移隔离实现，也不将旧快照完整性等同于零数据损失。
