# 经典账户权威移交与回退规则 v1

本批交付 `ClassicImporter`，用于**合成或已获授权、完全静止的账户快照**向空 UTA 账户的一次事务移交。它不是可以直接启用真实客户的通用迁移适配器。当前验收为局部功能验收；源系统增量日志边界、旧写入者失效和完整挂单迁移尚未通过生产验收。

## 支持范围与拒绝行为

| 输入 | 本批行为 |
| --- | --- |
| gross 现货现金、多币种抵押、借款本金、利息 | 保留原始分量，分别入账；资产必须配置币种精度及可信价格 |
| 已知 USD 结算、乘数为 1 的线性永续净仓 | 保存数量与有符号精确成本 `quantity * entry_price` |
| source 已存在、目标不存在或只创建过空账户 | 允许一次移交；不能覆盖有账务或订单历史的 UTA |
| 冻结余额非零 | `unsupported_lock`，因为旧快照没有冻结原因及占用对象 |
| 挂单、条件单、待结算项目、汇划中项目非空 | `unsupported_migration_state`；四个清单必须由调用方显式提供 |
| 反向、交割、期权、未知合约或未知资产 | `migration_product` / `migration_asset`；不能将其他合约假装成线性合约 |
| 同一源账户使用第二个移交命令 | `source_already_imported`，防止换 ID 重复导入 |
| 目标已发生财务变更 | `destination_not_empty` |
| 风险权益为负的合法源快照 | 保留已存在的资产与债务，先冻结；监督器将其判定为破产或继续处置 |

“已知线性合约”在旧参考模式中指 `MarketSnapshot.instruments` 的线性 USD 结算语义。配置版本化 `ProductCatalog` 后，每个已有仓位还必须经过 `require_risk_supported(..., CROSS)`，且产品类型必须为线性永续、乘数为 1、报价及结算均为 USD。不能用行情中的同一个符号把期权、反向、现货或不同乘数的仓位伪装成线性仓位。已停牌但仍可估值的合格旧仓位可以导入；账户仍先 BLOCKED，并不因此获得交易资格。源数量和入场价也须满足服务当前的最多 8 位小数与数值范围。

## 规则追溯

以下均为本系统制定的 `LOCAL-CUTOVER-v1` 政策，不声称复刻 Bybit、Binance 或其他交易所的迁移行为。时间精度为有时区的 UTC 微秒，资金单位为对应资产，风险单位为 USD。分录不舍入，不能精确表示为资产最小单位时整体拒绝。

| 规则编号 | 政策及边界 | 验证编号 / 测试 |
| --- | --- | --- |
| MIG-001 | 源摘要在使用时重新计算；新移交默认要求源快照不超过 30 秒，行情服从服务 5 秒策略 | `test_digest_unknown_asset_and_unsupported_product_fail_atomically`、`test_stale_source_or_market_rejected_before_any_book_change` |
| MIG-002 | 必须明确断言四类在途清单为空；冻结不得丢失 | `test_required_in_flight_and_locked_state_are_never_discarded` |
| MIG-003 | 资产、本金、利息和仓位分别保留；同币种资产与借款不做抵押前净额 | `test_import_preserves_gross_cash_principal_interest_position_and_freezes` |
| MIG-004 | 目标账户为空；源账户全局只能成功移交一次 | `test_empty_existing_account_is_allowed_but_financial_history_is_not`、`test_global_command_conflict_and_repeated_source_rejected` |
| MIG-005 | 分录、债务投影、仓位、账户版本、冻结状态和回执同事务提交 | `test_insert_failure_cannot_leave_assets_positions_debt_or_consumed_id`、`test_process_death_after_book_updates_before_commit_rolls_back_then_resumes` |
| MIG-006 | 同命令、同内容在重启或过期后返回原不可变回执；不同内容报冲突 | `test_same_command_returns_immutable_receipt_after_expiry_and_restart`、`test_concurrent_importers_commit_one_receipt_and_one_journal` |
| MIG-007 | 所有导入账户先 BLOCKED，使用新的服务端风险决策才可恢复交易；负权益不得当作零值丢弃 | `test_import_preserves_gross_cash_principal_interest_position_and_freezes`、`test_negative_equity_is_retained_frozen_and_supervised_as_bankrupt` |
| MIG-008 | 未发生导入后变更时才能用新分录补偿；保留原移交事件，不允许删除账本 | `test_compensating_handback_preserves_original_history_and_deduplicates`、`test_new_activity_requires_forward_recovery_and_cannot_be_database_rolled_back` |
| MIG-009 | 金融计算与调用方 Decimal 精度、舍入及陷阱无关 | `test_import_and_compensation_ignore_decimal_precision_and_traps` |
| MIG-010 | 回执和补偿记录不可原地修改；重放核对摘要及原始、补偿分录 | `test_receipts_immutable_and_verify_detects_dropped_guard_and_corruption` |
| MIG-011 | 配置目录后的导入必须同时通过已有暴露估值资格、线性类型、乘数及结算币门禁；停牌不丢弃旧仓位 | `test_same_market_symbol_cannot_smuggle_option_inverse_spot_or_multiplier_positions`、`test_unlisted_symbol_is_rejected_even_if_market_retains_a_price`、`test_existing_halted_supported_exposure_is_imported_frozen_and_can_be_valued` |
| MIG-012 | 会计分量逐项对账；不同规则模型的 IM/MM 不能直接等同。配置模式按独立 gross 会计权益表达式核对，并保留规则版本和实际保证金 | `test_versioned_loan_margin_can_differ_from_legacy_without_discarding_source_finances`、`test_imported_cross_debt_repayment_preserves_cashflow_and_reduces_configured_loan_margin` |

工程签字：迁移组已实现并执行对应测试；金融规则复核与独立验收状态由集成验收报告记录。此文件不伪造人工审批或真实资金上线签字。

## 账户及分录

资产记入 `customer:{account_id}`，交接资产的对方科目为 `system:migration-custody`。该科目代表源系统已移交的托管资产义务，不代表本程序接收了链上充值。

借款本金使用负余额科目 `liability:principal:{account_id}`，对应 `system:credit-principal-receivable`；利息使用 `liability:interest:{account_id}`，对应 `system:credit-interest-receivable`。`uta_liabilities` 分别保存非负本金与利息，供风险和 CreditService 还款核对。导入旧源债务不要求本系统曾发放该笔借款。CreditService 仍须以逐客户、逐币种负债分录为准。

举例：源 gross USD 现金为 1,150、BTC 现金为 2；USD 借款本金 300、利息 0.25。BTC 标价 200，抵押因子 0.5；线性仓位 0.1，入场价 200、标记价 220，IM 10%、MM 5%。则会计现金分量保持 1,150 USD、2 BTC；风险权益为 `1150 + 2*200*0.5 - 300 - 0.25 + 0.1*(220-200) = 1051.75 USD`，仓位 IM 2.2 USD、MM 1.1 USD。不能把 USD 现金先净成 849.75 再处理抵押政策。

配置版 Cross 风险包含借贷 IM/MM 和阶梯抵押规则，与旧固定费率参考模型不是同一保证金口径。导入先逐项核对现金、本金、利息、仓位数量及精确成本，再用 `gross_assets * price - gross_debt * price + quantity * mark - cost` 独立核对会计权益。`risk_at_import` 保留实际风险权益、IM/MM、`rule_id`、`rule_version`、`catalog_version` 及 `market_version`；`reconciliation_basis` 明确采用配置版会计权益还是旧参考风险全字段对比。

配置手算例：gross USD 1,000、BTC 2，BTC 标价 200；USD 本金 100、利息 1；线性仓位 2、入场价 100、标记价 110。BTC 抵押按首 100 USD 的 0.9、其余 300 USD 的 0.5 计为 240 USD；会计权益为 `1000+400-101+20=1319`，风险权益为 `1000+240-101+20=1159`。线性 IM/MM 为 22/11，借贷费率 20%/10% 再计 20.2/10.1，合计 IM/MM 为 42.2/21.1。不能因为旧参考模型没有这部分借贷保证金就拒绝已确认的源资产。导入债务即使高于新借款限额也保留原分量并冻结，限额只决定此后的新增借款资格。

## 操作接口与未知结果处理

```python
from uta.cutover import ClassicImporter

importer = ClassicImporter(exchange)
receipt = importer.import_shadow(
    reconciled_shadow,
    "cutover-account-1",
    source_fence_reference="classic-sim:writer-epoch-9-disabled",
    open_orders=[],
    conditional_orders=[],
    pending_settlements=[],
    transfers_in_flight=[],
)
importer.verify()
exchange.supervise_account(receipt["account_id"])
```

`source_fence_reference` 仅是操作者保存的证据引用；程序不验证该来源签名、租约或旧写入者。回执明确返回 `source_fence_verified: false`、`source_event_cursor: null` 和 `incremental_events_verified: false`。源 `version` 在本批只是源快照版本，不能冒充连续事件游标。此接口不允许客户 REST token 直接调用。

连接中断或返回超时时，先用原 `command_id` 调用 `receipt()` / `status()` 查询。不能生成新的 ID 重试移交。完成的历史回执可在源快照或行情已过期后重查，因为它不会再次生效。`receipt()` 是当时不可变的执行凭证；若后来做过交回，`status()` 同时返回原移交、交回回执及 `active: false`，防止把历史回执误读为当前权威状态。

## 切换前置与恢复

1. 对源快照和授权范围留档；明确每币种资产、本金、利息、冻结原因、订单、条件单、仓位、资金费及待结算项目。不能把没有采集到的数据当作空数据。
2. 实际源适配器须获得原子快照及对应事件游标，持续消费到暂停水位。证明期间成交、撤单、费用、利息及转账各自只属于一个权威系统；有缺口或乱序就停止切换。本批尚未实现该证明。
3. 暂停源写入与交易流量，撤销旧写入者租约或凭据，并用拒绝写入测试确认失效。把经过复核的证据作为 `source_fence_reference` 留档；一个文本引用本身不满足验收。
4. 用相同逻辑时点和市场版本双跑，逐币、逐仓、逐订单、逐分录及权益、保证金核对。这个 importer 只接受四类在途项目为空、冻结为零的简化配置；其他账户留在源系统。
5. 小批移交。回执成功、账本 `verify()` 与源对账完成后，由新的 supervisor 重新计算；仅当账户状态和独立审批允许时恢复客户流量。

单进程或单节点事务故障由 SQLite 回滚并通过原业务 ID 恢复；FULL/WAL 不代表跨可用区复制或 RPO=0 灾难恢复。数据库必须位于访问受控的本地持久盘，备份与离线恢复见 [运行手册](operations.md)。不能让源系统和 UTA 同时成为活跃写入者。

## 回退和补偿

只有账户版本仍等于移交回执版本、没有挂单且现金、负债、仓位逐项未变时，允许调用：

```python
handback = importer.reverse_import(
    "cutover-account-1", "handback-account-1",
    source_handback_reference="classic-sim:epoch-10-handover",
)
```

它追加原分录的精确反向分录并记录新回执，清空本次导入的仓位与债务投影，保留原账本、移交和交回历史，账户继续 BLOCKED。原命令不能换 ID 再次导入。交回的源权威确认同样需要外部证据，程序不会自动恢复旧写入者。

导入后出现充值、借贷、交易、清算或改变账户版本的状态迁移时，返回 `migration_forward_recovery_required`。此时必须对新增业务逐笔继续切换、追账或设计审核后的补偿；恢复旧数据库会丢失已确认业务及幂等键，不能作为业务回退。

## 可复跑验收

```sh
python -m unittest discover -s tests -p test_cutover.py -v
python -m unittest discover -s tests -p test_cutover_configured.py -v
```

覆盖手算示例、六个独立服务连接争用、事务插入故障、账务和仓位已写后杀进程、重启重试、不可变回执、精度污染、负权益、拒绝隐含在途数据和补偿边界。仍未验证真实源增量适配、跨接口时差、外部 fence 有效性、挂单/条件单迁移、母子账户切换、跨可用区权威移交、真实资金或 30 分钟生产容量，因此不得据此宣布真实迁移验收通过。
