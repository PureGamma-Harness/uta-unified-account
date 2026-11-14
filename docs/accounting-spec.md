# Cross UTA 账务与借贷规范

本规范对应同一个 SQLite 事务内的 `ExchangeService`、`DurableLedger` 与 `CreditService`。范围是多资产抵押、USD 报告单位、线性永续及显式现货借贷；本阶段没有 Isolated、完整 PM、自动借款或第三方资金托管。所有金额都用 `Decimal` 输入，按资产固定精度转换成整数最小单位；不能整除最小单位的输入直接拒绝，不隐式四舍五入。

## 总账不变量

每个 journal event 的每一种资产分别满足 `sum(posting.amount) = 0`。正数增加命名科目余额，负数减少余额；这里是代数记账约定，不能把 BTC 与 USD 数量相加平账。科目名同时区分现金与债权债务，不能把借款到账和借款负债提前净额化。

`ledger_events.sequence` 连续递增，事件 ID 全局唯一。流水一经封存不能追加分录、修改或删除。相同事件 ID 与相同规范化分录返回原结果；内容不同则拒绝。账务流水、借贷命令、账户版本、负债投影和业务审计事件必须一起提交或一起回滚。数据库采用 `BEGIN IMMEDIATE` 取得写锁后才读取额度、资金池和账户风险，多个实例不能重复花费同一资金。

`DurableLedger.verify()` 独立重放双分录，核对哈希链和物化余额。`CreditService.verify()` 进一步核对每个客户的本金、利息投影和对应负债科目；不能只用 SQLite 的页完整性检查代替财务对账。哈希链的可信边界是数据库文件所有者，不等同于外部审计封存。

## 科目表

| 科目 | 用途 | 正常符号 |
| --- | --- | --- |
| `customer:{account_id}` | 客户已结算的该资产总现金余额 | 非负；永续结算可能产生负余额，负余额不能用于还款 |
| `system:custody` | 现有可信入金命令的资金来源对手科目 | 入金时为负 |
| `system:migration-custody` | 经典账户已确认资产导入的来源对手科目 | 资产导入时为负 |
| `system:credit-pool` | 已注资、尚未出借的该资产现金 | 非负 |
| `system:credit-capital` | 经特权操作记录的外部授信资金来源对手科目 | 注资时为负 |
| `liability:principal:{account_id}` | 客户应付借款本金，独立于客户现金 | 非正 |
| `liability:interest:{account_id}` | 客户应付已确认利息 | 非正 |
| `system:credit-principal-receivable` | 本金债权子账 | 非负 |
| `system:credit-interest-receivable` | 已计提、尚未收到的利息债权 | 非负 |
| `system:credit-interest-cash` | 已实收利息的现金子账 | 非负 |
| `system:realized-pnl`、`system:fees` | 永续已实现盈亏对手科目及已收费用 | 随业务事件变化 |

`uta_liabilities(account_id, asset, principal, interest)` 是负债投影，不是现金余额。两项必须非负，并分别等于客户对应负债科目的相反数。经典账户导入若包含旧本金和旧利息，也使用相同负债及债权科目，来源版本、摘要、外部 fence 证明放在迁移凭证和事件中；不能通过一次普通入金伪装成迁移。

## 借贷分录

以下每列均为同一资产的数量，不是 USD 估值。所有动作都生成可追溯命令与 journal event ID。

| 动作 | 增加的科目 | 减少的科目 |
| --- | --- | --- |
| 确认资金池注资 `x` | `system:credit-pool +x` | `system:credit-capital -x` |
| 借本金 `x` 的现金流 | `customer:{id} +x` | `system:credit-pool -x` |
| 同次借款的债权债务 | `system:credit-principal-receivable +x` | `liability:principal:{id} -x` |
| 确认利息 `i` | `system:credit-interest-receivable +i` | `liability:interest:{id} -i` |
| 偿还本金 `p` 的现金流 | `system:credit-pool +p` | `customer:{id} -p` |
| 同次偿还本金的债权债务 | `liability:principal:{id} +p` | `system:credit-principal-receivable -p` |
| 偿还利息 `i` 的现金流 | `system:credit-interest-cash +i` | `customer:{id} -i` |
| 同次偿还利息的债权债务 | `liability:interest:{id} +i` | `system:credit-interest-receivable -i` |

`fund_pool(command_id, asset, amount, source_reference=...)` 是特权记账入口：调用方必须先确认资金或授信已存在，并提供独立来源引用。示例和测试只能使用标明 synthetic 的来源；接口本身不能证明银行、链上或第三方资金实际到账。未注资的资金池不能借出资产。

`borrow(account_id, command_id, asset, amount)` 只有在以下条件全部成立时提交：

1. 全局 kill switch 关闭，账户未被风险 supervisor 冻结。
2. 资产存在于固定精度表和新鲜、完整的可信行情中。
3. 已明确配置该资产的总授信额度、该账户的该资产额度；默认无额度，等价于禁用借款。
4. 现有本金加利息加本次借款不超过任一额度，资金池现金足额。
5. 现金和本金同时入账后的 `equity - initial_margin - open_order_margin >= 0`。

额度用相应资产数量表示，不是 USD。`configure_asset_limit` 与 `configure_limit` 首次配置后固化；相同配置重试不产生事件，修改配置拒绝。将来调整额度需要独立、可审计的版本迁移，不能直接改数据库。利息是已经发生的义务，可以把总负债推到额度之上，随后拒绝进一步借款，不能因为额度不足而丢弃应付利息。

`accrue_interest` 仅接受特权调用方提供的、已有本金的明确利息事件。模块不会自行推断时间、年化率、计息周期或复利，不会给客户增加现金。调用方负责计息来源和期间唯一性，使用稳定 command ID 重试。

`repay` 固定先还利息，再还本金；请求不得超过总负债，也不会自动借币填补现金不足。同一资产的已结算可用现金必须足额，待结算或冻结资产不能还款。在现金非负且抵押率 `h∈[0,1]` 的范围内，还款 `x` 的权益变化是 `x × price × (1-h) >= 0`，因此不会减少 IM/MM 余量，可以在 kill switch 启用、清算冻结或行情过期时继续偿债。

## 资产、订单冻结与待结算

`customer:{id}` 是已结算现金总额。现金支出必须统一调用 `ExchangeService._available_asset(connection, account_id, asset)`，再叠加动作需要的账户风险检查。当前永续订单占用的是 USD 报告单位的保证金，不是某一种资产的实物冻结；不能把 `open_order_margin` 的 USD 数值直接从 BTC 数量中扣除。

现货订单接入时，每个订单的实物锁定必须持久化，并在同一交易事务内扣减 `_available_asset`。锁定资产仍属于客户，是否抵押必须由明确风险政策决定；不能在账本里无声消失。禁止还款、提现或第二个订单消费已经锁定的数量。解除锁定必须由确定的撤单、拒单或成交状态驱动，不能仅因超时猜测订单已经结束。

待结算资金应保存在独立的 pending 子账，只有可信结算确认后才能转入 settled 现金；pending 不计入可还款数量或可用抵押品。规范保留 `frozen-customer:{id}` 和 `pending-customer:{id}` 命名空间用于未来实物划转，与 `customer:` 前缀分离，避免带冒号的合法账户 ID 发生科目碰撞。若采用此方式，风险引擎必须显式汇总应计入权益的冻结资产，不能只移动余额而漏算权益。当前没有启用这两个资金划转入口；经典镜像携带 locked 或在途数据时应显式拒绝切入，不能丢弃字段后继续。

## 独立复算案例

初始 USD 现金 `1000`，BTC 价格 `100`，BTC 抵押率 `0.8`，无持仓和订单：

- 借 BTC `2` 后，USD 现金仍为 `1000`，BTC 现金为 `2`，本金为 `2`；权益为 `1000 + 2×100×0.8 - 2×100 = 960`。先把 BTC 资产负债净额化会错误算成 `1000`。
- 确认 BTC 利息 `0.1` 后，BTC 现金仍为 `2`，本金 `2`、利息 `0.1`，权益为 `950`。
- 还 BTC `0.15`，先还利息 `0.1`，再还本金 `0.05`。BTC 现金 `1.85`，本金 `1.95`，利息 `0`；权益为 `1000 + 1.85×100×0.8 - 1.95×100 = 953`。资金池回收本金 `0.05`，利息现金子账增加 `0.1`。

这些值在 `tests/test_credit.py` 中逐项验证。测试还覆盖限额与资金池并发、命令重放、冻结/陈旧行情借款阻断、18 位资产最小单位、结算前异常的全事务回滚，以及负债投影损坏拒绝启动。
