# 第一批风险边界：独立手算 golden

固定来源 `bb34b5fb4397f485c04fe440557b24bb28d1cae2`，自有 worktree
`/workspace/uta-pm-independent-next`、分支 `test/pm-independent-next`。
全部数据是合成输入；这里核对项目的 `UTA-CROSS-LOAN-v1` 和
`UTA-PRODUCT-GATE-v1`，没有外部交易所参数验证、真实金融负责人签字或生产结论。
PM/Isolated 均仍拒绝；压力参考不能激活 PM。

独立来源是 [oracle](../tests/pm_independent_next_oracle.py)。它只导入标准库，先以
Fraction 核对下表的手工常数，再把相同原始字符串交给被测系统。预期值不读取
`uta` 对象、返回值、内部金额 helper 或现有 reference calculator。

## 手工规则表

| 项目 | 本组人为指定的规则 |
| --- | --- |
| 价格 | USD=1、BTC=100、ETH=50，两个线性合约 X/Y 的 mark 均为 100、乘数均为 1 |
| 可用抵押数量 | gross−frozen；冻结资产保留 accounting value，不贡献抵押值 |
| 抵押阶梯 | USD 全额；BTC 前 100 USD ×0.8、超出部分 ×0.5；ETH 前 50 USD ×0.9、超出部分 ×0.6 |
| 抵押借款价值 | 上述折扣值再乘 LTV：USD=1、BTC/ETH=0.5；仅 V5 显式改为全 1 |
| 债务 | 本金、利息、cash deficit 各自按全价相加，不先从同币 gross 扣除 |
| 借款 IM/MM | USD=0.1/0.05、BTC=0.2/0.1、ETH=0.1/0.05；只对本金+利息收取。V5 显式全为 0 |
| 线性 IM/MM | 每个 symbol 的绝对标记名义价值 ×0.1/0.05，符号相反不抵消 |
| 报价步长/上限 | USD=.25、BTC=.001、ETH=.01；各币本金上限 1000、总债上限 10000 |
| 健康阈值 | E≤MM 为 LIQUIDATION；否则 available<0 为 MARGIN_CALL；available=0 可为 HEALTHY |
| 借款可行性 | 新借款所得离开抵押品；结果 available≥0 且 E>MM，另满足 LTV/债务/本金上限 |
| 压力 | 每个抵押币与每个线性 symbol 先取非负损失，再加总；requirement=max(worst,floor)+liquidity+credit |
| 权限 | Cross 且 quote/settlement/catalog settlement 均为 USD 且无 eligible_hedges；PM/Isolated 拒绝 |
| 账本边界 | 实际 ledger 每种币的有符号整数 posting 必须独立平衡；本组只测纯函数，不发生成交、借款或账本 posting |

## 六组向量与新增覆盖

已有 `test_portfolio_reference.py` 包含 320 个生成账户、96 组压力、单币阶梯/冻结、
维护门槛与同标的双腿正控；本组新增的是以下固定组合的可手算结果，不把已有
cash-deficit 修复/正控再称为缺陷发现。

| 组 | 输入与手算结果 |
| --- | --- |
| V1 | USD gross50/deficit3；BTC gross2/frozen1/principal.5/interest.1；ETH gross2/principal.2/interest.1；order1.25。抵押=50+80+75=205，p/i/deficit=60/15/3，总债78；accounting272、E127、loan127.5、IM13.5、MM6.75、available112.25。把同币可用资产先减 p+i 再折扣会误得 E145，夸大18。 |
| V2 | 同 V1，BTC ±10%、ETH ±20%。BTC 净抵押风险价值基准20、下跌18、上涨19，因此两个方向损失分别2与1；ETH 基准60、下跌51、上涨69，损失9与0。总损失 down11/up1；floor8、liquidity2、credit1，requirement14。冻结使 BTC 恰位于阶梯100，压力必须重新跨阶梯计算。 |
| V3 | USD100、BTC gross1/p.5/i.1，X +1/cost100、Y −1/cost−100。E120、IM32、MM16、available88；down/up20% 时压力24/22，参考缺口 E−requirement=96。去掉 X 后 IM22/MM11/available98、压力4/22、缺口98；去掉 Y 后同样 Cross 保证金但压力24/2、缺口96。这里的去腿是三个静态账户快照，未模拟成交结算。 |
| V4 | USD principal10，gross 为10.5、10.51、12；最后一例 order1。E 分别 .5/.51/2，IM1/MM.5，available −.5/−.49/0，状态依次 LIQUIDATION/MARGIN_CALL/HEALTHY，USD借款报价均0。覆盖正 MM 等号、一个最小输入差以及带挂单 IM 等号。 |
| V5 | BTC gross2/frozen1/p1/i.0025，零借款 IM/MM、全1 LTV；USD gross=.25/20.25/20.5。债务100.25、E=−20/0/.25；前两例 LIQUIDATION，最后 HEALTHY。最后 USD 报价0，因为一个 .25 步长使 E=MM=0；BTC 报价.002，下一格.003使 E<0。区别于无债单USD正控，本例同时保留gross、冻结与微小利息。 |
| V6 | 同标的 X/Y 对向线性仓位不能让 Y 的 BTC settlement 或 EUR quote 获得资格；另检查非USD catalog settlement、声明 eligible_hedges、spot-margin 元数据及空仓 PM/Isolated 的明确拒绝。 |

## 范围与回滚

新增独立 oracle、测试与证据，不修改 `uta/`、配置、schema、原作业 SQL 或冻结工作树。
所有调用均为纯风险/产品门禁；不启动服务、网络、压力测试或旧长跑，不触碰借贷 V2
activation/native M3。CPU affinity 固定为 CPU4，单次测试命令限时 30 秒。
回滚是撤销本组新增文件的提交；没有资金、数据库或运行状态需要迁移。

## 实际执行结果

Oracle、规则表与首次独立自检先提交为
`cc8e69d864fd08302fa816af29fe9c64838959d3`，随后才添加 SUT 对比测试。
运行器按参数列表执行子进程，每条命令真实设置 `taskset -c 4` 并施加 30 秒 timeout；
没有启动服务或网络。新测试的首次运行即为绿色，没有生产 red 或生产修复提交。

| 实际窗口 | 结果 | 测试日志耗时 / 进程墙钟耗时 |
| --- | --- | --- |
| Oracle-first / Python 3.12.14 | 六组手算自检通过，exit0 | 0.035秒进程 |
| 首次 SUT / Python 3.12.14 | 6 tests、0失败、0错误、0跳过，exit0 | 0.041 / 0.204秒 |
| 同一新测试 / Python 3.10.22 | 6 tests、0失败、0错误、0跳过，exit0 | 0.040 / 0.114秒 |
| 同一新测试 / Python 3.13.5 | 6 tests、0失败、0错误、0跳过，exit0 | 0.024 / 0.121秒 |
| 相关已有纯测试 / Python 3.12.14 | 25 tests、0失败、0错误、0跳过，exit0 | 0.764 / 0.938秒 |

相关检查仅选择 `IndependentCrossReferenceTests`、`IndependentStressReferenceTests`、
`ProductCatalogTests`、`PortfolioTests` 与 `RiskBoundaryTests`，没有执行同文件中的
服务集成类。新测试入口为 [test_pm_independent_next.py](../tests/test_pm_independent_next.py)。
原始 stdout/stderr、argv、退出码、版本、实际亲和性查询和逐文件 SHA256 均保存在
[证据目录](../evidence/runs/pm-independent-next)。其中首次 Oracle 的版本辅助查询
未设置 CPU 亲和性，显示 `[0,1,2,3,4]`；实际 Oracle 子进程的 argv 已设置 CPU4。
后续运行器的辅助查询也固定 CPU4，原记录保留原样。

本组 SUT 的 `uta/portfolio.py` SHA256 为
`c707d1bc45d8e73e671552bcd31fba582780974f1bb0da434ac2b8cee7c46879`；
`uta/products.py` 为
`c50ca57ffb206f2996aaef49b1eb198066582a573db93b96adcd61c2c5350f29`。
两个核心文件和所有 `uta/` 文件均没有改动。首次比较时测试尚未提交，其精确内容由
当次 metadata 的测试/oracle SHA256 绑定；没有把旧提交 HEAD 冒充包含未提交测试。

结论是这六组合成边界与自定义规则吻合，未发现待修生产缺陷。现金亏空作为债务计入且
不重复收贷款保证金的既有行为仍成立；本组不重写此前 a35 的实际负现金正控结论。
该局部结果不解除固定 bb34 来源的 Python3.10 全量兼容错误/NO-GO，也不证明完整模式
支持、真实交易所 PM、安全性、10k 或 HA。
