# 产品目录与分批能力边界

目录规则 ID：`UTA-PRODUCT-GATE-v1`。实现位于 `uta/products.py`，不声称与任何具体交易所一致。

| 类型 / 模式 | 第一批目录能力 | 第一批风险计算 | 实际执行要求 |
| --- | --- | --- | --- |
| Cross 现货 / 现货借贷 | 支持元数据与准入校验 | 总资产、本金、利息、冻结与梯度抵押值 | 结算、借还款必须接入同一持久化事务；目录不会自行成交 |
| Cross 单 USD 结算线性永续 | 支持 | 乘数、有符号成本、独立 IM/MM | 服务必须真正应用乘数、步长及规则版本；不能仅依靠原研究 risk API |
| Isolated | 显式拒绝 | 未启用 | `phase1_account_mode_unsupported` |
| PM 与 spot/perp hedge offsets | 显式拒绝 | 仅有不可激活的压力参考 | `phase1_account_mode_unsupported` / `phase1_hedge_offsets_disabled` |
| Inverse perpetual | 即使目录为 active 仍拒绝 | 未启用 | `phase1_product_unsupported: inverse_perpetual` |
| Dated futures | 即使目录为 active 仍拒绝 | 未启用 | `phase1_product_unsupported: dated_future` |
| Options | 即使目录为 active 仍拒绝 | 未启用 | `phase1_product_unsupported: option` |
| 非 USD quote / settlement | 显式拒绝 | 未启用 | `phase1_settlement_unsupported` |

目录描述能力与服务执行能力分开验收：目录允许第一批产品的元数据，并不意味着某个运行中的服务已经实现该产品的撮合或结算。真实请求必须经过运行服务的产品门禁与财务事务。未实现的 spot 结算、非 1 合约乘数、借贷或账户模式，运行服务应继续拒绝，直至对应执行路径及测试完成。

每个 `ProductSpec` 包含 symbol、product kind、underlying、quote、settlement、乘数、价格 tick、数量 step、最小名义金额、risk tier、expiry、funding interval、交易状态及 eligible hedge 列表。expiry 对 dated future / option 必填，其余类型不得填；funding interval 只能属于永续产品。期权行权价、波动率曲面及执行/指派属于未启用的后续产品模型。

`funding_interval_seconds` 只是元数据，不宣称已经收付资金费。`risk_tier` 指向版本化的显式保证金规则，不会自动从名称推断费率。线性合约名义金额为 `abs(quantity) × price × multiplier`；step、tick 必须精确整除，最小名义金额允许等于门槛，不能以四舍五入偷偷修正不合格订单。

`active` 可以进入产品能力检查；`halted`、`cancel_only`、`delisted` 和 `disabled` 拒绝新执行准入。`reduce_only` 仅允许调用方声明只减仓的请求，持仓符号与不超仓的动态检查仍必须由服务事务完成。产品停牌后仍须对既有持仓计算风险，因此 `require_risk_supported` 不把“停止交易”误当作“持仓消失”。

目录版本及配置使用不可变对象和严格 JSON 解析，拒绝重复字段、未声明字段、浮点财务值和非标准 JSON 常量。目录本身不建立真实报价可信性；行情还须满足独立的版本与新鲜度检查。

本阶段测试依据是合成数据的人工规则用例和软件不变量测试。金融规则负责人和独立验证负责人均**尚未由真实人员签字**；用户提供的三批建设要求不等于完成这些验收。
