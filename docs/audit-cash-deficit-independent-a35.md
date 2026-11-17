# a35 cash-deficit replay：独立最小实证

固定源码 `a35fd56fc98126b3e5cced8a459bd04ca580e537`，新隔离分支
`test/audit-cash-deficit-a35`；没有写冻结目录或修改任何`uta/`文件。**未复现所猜测的现金
亏空丢失。** 该源码的`DecisionAudit._replay_state`已把负余额原分量转换为`cash_deficits`；
实际纯helper和真实可达ORDER/FILL档案复算均与独立Fraction一致，不能据静态猜测认定bug。

纯输入第一控制：USD cash−1、BTC cash1，BTC price100、haircut.8，无贷款、仓位或挂单。
独立计算 collateral80、cash deficit1、risk79、accounting99、debt1。实际
`DecisionAudit._replay_state`与`calculate_cross_risk`相同，没有得到80/100/debt0。

第二纯控制保留BTC本金.1和历史利息.01：贷款债务11 USD，现金亏空另为1，total debt12；
collateral80、risk68、accounting88。贷款IM2.2、MM1.1，只对principal+interest征收，现金
亏空不重复收借款保证金。两项在最后有效输入上的纯计算窗口远小于0.1秒，见
[pure.json](../evidence/runs/audit-cash-deficit-a35/pure.json)。

为排除“手写负余额不是实际可达状态”，另在CPU3、自有全新TemporaryDirectory执行真实
本地受信controller调用，没有手写SQL现金或档案：

1. 配置synthetic USD/BTC、BTC-PERP线性multiplier1、mark/limit100、IM/MM .1/.05、
   fee .01；账户起初USD0。正向deposit BTC.9，并以独立synthetic source向pool注资BTC1。
2. 在**未封存、未managed**阶段，真实`CreditService`配置限额、借BTC.1、确认opening
   interest BTC.01；此时customer BTC1、principal.1、interest.01、pool.9。未调用任何
   managed新借款或绕过A2的501拒绝。
3. 启用真实schema3 decision audit。实际`submit_order`买1份@100，reserve为
   `100×.1+100×.01=11 USD`；真实`apply_fill`结算fee1 USD，客户USD0→−1，仓位1、
   cost basis100、未实现PNL0。风险与MM/available均有余量，原服务实际允许成交。
4. 获取真实`ORDER_ACCEPTED`和`FILL_CONFIRMED`两份不可变decision，保留所有before/after
   原balances、principal、interest、positions、orders及policy/market/artifact。对四个
   archived sides分别比较独立Fraction、recorded service risk、真实`_replay_state`和
   `DecisionAudit.replay`；最后再直接调用实际配置的`ExchangeService._risk`核对。

| 指标 | ORDER before | ORDER after / FILL before | FILL after |
| --- | ---: | ---: | ---: |
| USD cash | 0 | 0 | −1 |
| BTC cash / principal / interest | 1 / .1 / .01 | 1 / .1 / .01 | 1 / .1 / .01 |
| cash deficit / total debt USD | 0 / 11 | 0 / 11 | 1 / 12 |
| risk / accounting USD | 69 / 89 | 69 / 89 | 68 / 88 |
| IM / MM USD | 2.2 / 1.1 | 2.2 / 1.1 | 12.2 / 6.1 |
| order reserve USD | 0 | 11 | 0 |
| available USD | 66.8 | 55.8 | 55.8 |

两份真实replay都`matches=true`、`differences={}`，四个side及最终实际service风险全部
吻合。本路径服务阶段为0.157827秒，临时目录已清理。真实ledger/credit verify同时成功；
actual journal显示负USD来自fee posting，未通过负deposit、SQL伪造、fake position或虚构
audit生成。完整原档案与实际artifact manifest见
[service.json](../evidence/runs/audit-cash-deficit-a35/service.json)。这是本地授权成交，不
声称外部交易所成交、HMAC客户接入、双侧撮合或完整credit-specific operation replay。

过程失误单独保留，没有把它们算作生产缺陷：

- 第一次新oracle在空仓`sum()`结果上做除法产生float0.0，污染了随后p/i保证金参考；
  无贷款case实际helper已匹配，只有新参考侧extended case不一致。仅将参考的空sum初值
  和fee分母改为Fraction后核对。原始输出及旧script hash保存在
  [first oracle error](../evidence/runs/audit-cash-deficit-a35/pure-first-oracle-error.json)。
- 第一次live fixture用了fee .1，真实构造器按上限.01正确拒绝，尚未创建贷款/订单/audit。
  改成合法fee .01及qty1仍产生真实fee1。该拒绝保存在
  [invalid fee](../evidence/runs/audit-cash-deficit-a35/service-first-invalid-fee.json)；有效数学但
  live费率未调整的中间pure结果另存，未覆写。

可复跑的两项测试ID在
[test_audit_cash_deficit_reference_a35.py](../tests/test_audit_cash_deficit_reference_a35.py)，
脚本为 [probe](../scripts/probe_audit_cash_deficit_reference.py)。
[执行记录](../evidence/runs/audit-cash-deficit-a35/tests.json)保留实际退出码、CPU affinity、
Python/SQLite版本及全`uta/*.py` SHA256。核心三个摘要为：

| source | SHA256 |
| --- | --- |
| `uta/decision_audit.py` | `50671902d688cfe371e320d79d6fd5c329014ce9291dc522e5bc8f828424d5e6` |
| `uta/service.py` | `76e666497bd37c4955d0ac67bc7fd751387fa585047c3ed28c24565add13e0bd` |
| `uta/portfolio.py` | `c707d1bc45d8e73e671552bcd31fba582780974f1bb0da434ac2b8cee7c46879` |

没有生产红态或修复提交，因为指定冻结源码没有复现该缺陷。结论仅覆盖这两个纯state与
一个真实手续费路径，不外推其他source版本、完整信用审计或新M3能力。M2/frozen/活动
authority没有变更；certificate/native准备状态的owner/READY/activation否决仍独立保留。
