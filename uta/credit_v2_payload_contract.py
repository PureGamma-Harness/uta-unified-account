"""Normative retained-data fields; these declarations grant no capability.

The independent oracle reads this published wire contract without importing any
production valuation, accounting, rounding or replay implementation.
"""
FORMAT = 2
KIND = "CREDIT_BORROWED"
DECISION_FIELDS = frozenset({
    "format", "kind", "operation_id", "capability_id", "capability_payload",
    "account_id", "command_id", "asset", "amount", "amount_units", "payload_hash",
    "source_id", "source", "descriptor_id", "static_budget", "allocation_id",
    "market_snapshot_id", "artifact_id", "policy_id", "pre_state", "post_state",
    "gross_components", "pool_funding", "journal", "receipt", "selected_at",
    "last_checked_at", "recorded_at", "physical_commit_at",
})
PRE_STATE_FIELDS = frozenset({
    "account", "credit", "limits", "market_snapshot_id", "risk", "quote_units",
    "quantity_step_units", "selected_at", "journal_head",
})
POST_STATE_FIELDS = frozenset({"account", "credit", "limits", "risk"})
ACCOUNT_FIELDS = frozenset({
    "version", "balances", "frozen_assets", "positions", "liabilities", "orders",
    "halted", "liquidation_state",
})
CREDIT_FIELDS = frozenset({
    "version", "cash_units", "principal_units", "interest_units",
    "principal_ledger_units", "interest_ledger_units", "shard_principal_units",
    "shard_interest_units", "pool_units", "principal_receivable_units",
    "interest_receivable_units",
})
LIMIT_FIELDS = frozenset({"account_limit_units", "local_asset_limit_units"})
GROSS_FIELDS = frozenset({"assets", "cash_deficits", "principal", "interest"})
JOURNAL_FIELDS = frozenset({
    "sequence", "event_id", "fingerprint", "previous_hash", "event_hash", "sealed", "postings",
})
POSTING_FIELDS = frozenset({"ordinal", "account", "asset", "units"})
SOURCE_FIELDS = frozenset({
    "command_id", "source_id", "account_id", "kind", "payload_hash", "source_kind",
    "actor_id", "source_reference", "authority_id", "command_payload", "payload",
})
SOURCE_RECEIPT_FIELDS = frozenset({
    "format", "source_kind", "actor_id", "source_reference", "authority_id",
    "account_id", "command_id", "kind", "payload_hash", "command_payload", "accepted_at",
})
POLICY_FIELDS = frozenset({
    "format", "base_policy", "max_future_skew_us", "clock_policy", "physical_commit_time_captured",
})
BUNDLE_FIELDS = frozenset({"format", "decision", "market", "artifact", "policy"})
BASE_POLICY_FIELDS = frozenset({
    "format", "risk_mode", "catalog", "rules", "scales", "fee_rate", "max_price_age_us",
    "order_precision", "reserve_formula", "execution_options",
})
ORDER_FIELDS = frozenset({
    "account_id", "order_id", "symbol", "quantity", "limit_price", "reduce_only",
    "filled_quantity", "status", "version", "created_at", "fee_notional", "charged_fee",
    "admission_decision_id",
})
RISK_FIELDS = frozenset({
    "accounting_equity", "collateral_value", "risk_equity", "loan_value", "principal_value",
    "interest_value", "cash_deficit_value", "debt_value", "unrealized_pnl", "frozen_value",
    "initial_margin", "maintenance_margin", "available_margin", "account_version", "equity",
    "open_order_margin", "margin_ratio", "market_version", "observed_at", "market_id", "borrowable",
    "status", "risk_mode", "rule_id", "rule_version", "catalog_version",
})
RECEIPT_FIELDS = frozenset({
    "account_id", "command_id", "asset", "amount", "principal", "interest", "total",
    "account_version", "journal_event_id", "risk_evidence",
})
RECEIPT_RISK_FIELDS = frozenset({
    "market_version", "market_observed_at", "borrowable_before", "equity", "initial_margin",
    "maintenance_margin", "open_order_margin", "available_margin", "rule_id", "rule_version", "catalog_version",
})
