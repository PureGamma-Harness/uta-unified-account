# Joined credit 的独立金融验证

审阅源码固定为 `44a25b21fca1c6b86e68c05d2620a01ca3b8b04f`，对应计划
`5cc9896`、join 重构 `1c14441`、受信 owner 原反例 `5a75a3a` 及新借款拒绝 `44a25b2`。
本组仅新增独立测试和证据，未修改实现、主集成或长测 authority。**本范围未发现阻断项**，
不等于完整发布、真实金融签字或产品上线通过。

## 独立性与手算

[测试](../tests/test_credit_reference_review.py)的 expected 值来自逐业务动作构造的整单位
owner journal，以及明确的 `Fraction` 手算。oracle 不导入或调用生产估值、保证金、舍入、
账本回放函数；实际服务的风险输出只是被比较对象。账户/报价/产品配置使用合成数据。

USD 原始资产100，BTC 价格100、抵押因子0.8，借款 IM20% / MM10%，初始无 BTC。
本金和利息按100%价格计负债，不能先与同币资产净额抵消：

| 动作 | gross BTC | 本金 | 利息 | 会计权益 USD | 风险权益 USD | 借款 IM USD | 可用 USD |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 借入0.4 | .4 | .4 | 0 | 100 | 92 | 8 | 84 |
| 计息0.01 | .4 | .4 | .01 | 99 | 91 | 8.2 | 82.8 |
| 还款0.015 | .385 | .395 | 0 | 99 | 91.3 | 7.9 | 83.4 |

最后一次还款先还息0.01、再还本金0.005。pool 从1→0.6→0.605，interest cash 为0.01，
本金应收和对应负债分别为+0.395/-0.395。测试逐项比较全部 owner/asset 非零余额，并
独立重建每笔分录及每个币种的零和；重开和同 ID 重放不得产生新分录。

阶梯例另有已持有 BTC0.25，借入0.4 后 gross BTC0.65，USD100，负债BTC0.4。
前 USD25 抵押因子0.9、后续0.6：风险权益
`100 + 25×.9 + 40×.6 - 40 = 106.5`，会计权益125。
错误的先净额口径会得到122.5；测试明确区分，并在 Decimal 精度4的外部环境下核对。

借款0.4与线性限价订单8张共享同一真实写事务时，订单预占80，剩余额度
`100 + 32 - 40 - 8 - 80 = 4`。再加1张必须拒绝。两账户也共享同一库的 pool 和资产
限额：0.3+0.2 后第三笔0.01分别触及已耗尽的pool或0.5额度，不能重复使用资金。
这只验证同库预算，不宣称跨分片原子总额度。

## 合同与兼容核对

- AST 对比确认 A1 的原 borrow 事务内部金融主体与新 helper 主体相同；`_prepare` 和旧
  `_assert_joinable` 原合同未改。新 strict helper 只接受注册中的同连接、同 DB/path、
  同 writer binding 的 financial role；raw/read/inbox/control 与别库连接实际拒绝。
- A2 从事务读取 persistent authority，并在 canonical credit replay 后拒绝新借款501。
  真实 schema3 + 仍活 token 下 public/private 两路均无新 cash/debt/version/分录/成功
  receipt；同 ID replay 在 halt/过期行情下仍返回原结果，异内容仍409，既存债务还款保留。
- 原三处还款夹具的本金金额和 ID 不变，仅在 fence 前 bootstrap 原义务。两个 USD10/
  `loan` 及一个 BTC0.1/`borrow` 的后续金融断言保留，三项原测试实际复跑通过。
- 私有 helper **没有自己的业务 savepoint**。独立 late-rejection 案例确认 projected
  risk 拒绝前已存在 staged cash/debt；调用方必须真实 `ROLLBACK TO`。测试回滚后提交并
  重开，原分录/CID无成功，再补足抵押后原 CID 才能成功。public method 自有外层事务
  仍负责异常回滚；未来 dispatcher 不得 catch 业务异常后提交部分贷款。

501 是本次代码级拒绝政策。它不新增 SQL 操作级旧二进制门禁，不批准在线新借款、自动
借贷、利息调度、跨币还款或跨片全局额度。后续启用仍需显式 capability、完整信用决策
审计、预算分配和独立验收；上述未交付项不能由本组结果推断为通过。

## 实际证据

三运行时各7项新独立案例通过：Python3.12/SQLite3.53.1、Python3.10/SQLite3.53.1、
Python3.13/SQLite3.46.1。均单CPU，使用 `-W error::ResourceWarning`，未观察到警告。
包含进程启动的实测时间分别约0.608/0.679/0.745秒。另三个原还款测试在3.12中通过，
0.330秒。原始日志、源摘要、命令及 AST 核对见[证据目录](../evidence/runs/credit-independent-review/README.md)。

首跑6通过/1 ERROR 是新夹具遗漏 `ProductSpec.status=ACTIVE`，订单尚未进入风险阶段。
原日志保留；仅显式启用该合成产品后重跑，没有把 product rejection 当成风险拒绝或
修改运行时。没有执行完整发布矩阵、撮合压力、服务长测或任何真实账户操作。
