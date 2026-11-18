"""Independent N3/K2 literal fixture and zero-genesis causal integer oracle.

No author fixture, budget, validator helper, UTA core, SQL or original data is
used to derive expected results. The candidate validates only synthetic JSON.
"""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[3]
CORE = ROOT / "tools/prefix_contract.py"
CORE_SHA256 = '13269c504e67d2667b3a225377b54bc60d82a19f5ba4d8117e4bd7593a41272c'
SOURCE = "909acecd153e2e89dfe2238e3ed3a3d9a3d3c9f0"
A, B, C = ("managed-soak-alice", "managed-soak-bob", "managed-soak-credit")
JOB = "independent-n3-k2"
FLAGS = {name: False for name in (
    "complete_original_job", "continuous_6h_stability_passed", "continuous_24h_stability_passed",
    "financial_6h_passed", "capacity_10000_per_s_passed", "full_risk_engine_reexecution_passed",
    "whole_business_event_reexecution_passed", "production_approved")}
CHECK_NAMES = ("source_manifest_verified", "quiescence_verified", "coherent_private_snapshot_verified",
    "original_prefix_boundary_verified", "all_commands_and_controls_resolved", "segmented_logs_verified",
    "financial_journal_and_positions_reconciled", "independent_reopen_same_watermark")
LIMITS = {"ORIGINAL_JOB_INCOMPLETE", "NOT_FULL_DURATION_ACCEPTANCE", "NO_FULL_RISK_REEXECUTION",
    "NO_WHOLE_BUSINESS_EVENT_REEXECUTION", "NO_PRODUCTION_APPROVAL", "SOURCE_OR_BOUNDARY_UNPROVEN",
    "UNRESOLVED_OBLIGATION", "PRIVATE_SNAPSHOT_NOT_CREATED", "AUDIT_NOT_EXECUTED",
    "METHOD_NOT_INDEPENDENTLY_APPROVED"}


def cid(round_number, step):
    return "ms:" + JOB + ":r" + str(round_number).zfill(9) + ":" + step


def fixture():
    value = {
        "schema": "uta.synthetic_prefix_contract_input.v1", "scope": "synthetic_json_contract_only",
        "profile": "909-three-account-usd-btc8-linear-synthetic",
        "original": {"job_id": JOB, "source_commit": SOURCE, "status": "paused", "planned_rounds": 3, "completed_prefix_rounds": 2},
        "source": {"synthetic_only": True, "model_version": 1, "asset_scales": {"USD": 8, "BTC": 8}, "manifest_claimed_verified": True},
        "quiescence": {"synthetic_declaration_only": True, "writers": [{"pid": 1001, "birth": "2002", "known_stopped": True}]},
        "boundary": {"controller_sessions": 1, "unresolved_steps": 0, "unresolved_faults": 0, "active_rounds": [], "ended_status": "paused"},
        "unknown_actions": [], "positions": [], "remaining_principal_satoshi": 2,
    }
    for name in ("rounds", "commands", "controls", "orders", "fills", "matches", "decisions",
                 "credit_events", "ledger_events", "postings", "balances", "logs"):
        value[name] = []

    def event(kind, business, entries):
        sequence = len(value["ledger_events"]) + 1
        event_id = "independent-event:" + str(sequence)
        value["ledger_events"].append({"sequence": sequence, "event_id": event_id, "kind": kind, "business_id": business})
        value["postings"].extend({"event_id": event_id, "ordinal": ordinal, "owner": owner, "asset": asset, "units": units}
            for ordinal, (owner, asset, units) in enumerate(entries))
        return event_id

    def log(kind, round_number=None, status=None, business=None):
        sequence = len(value["logs"]) + 1
        value["logs"].append({"sequence": sequence, "previous_sequence": sequence - 1, "kind": kind,
                              "round": round_number, "status": status, "business_id": business})

    # Closed synthetic ledger starts at zero before its six genesis events.
    for account, business in ((A, "deposit-alice-usd"), (B, "deposit-bob-usd"), (C, "deposit-credit-usd")):
        event("DEPOSIT", business, [("customer:" + account, "USD", 100000000000000), ("system:custody", "USD", -100000000000000)])
    event("DEPOSIT", "deposit-credit-btc", [("customer:" + C, "BTC", 100000000), ("system:custody", "BTC", -100000000)])
    pool = event("POOL_FUNDED", "initial-pool", [("system:credit-pool", "BTC", 100000000), ("system:credit-capital", "BTC", -100000000)])
    loan = event("BORROWED", "initial-loan", [("customer:" + C, "BTC", 6), ("system:credit-pool", "BTC", -6),
        ("liability:principal:" + C, "BTC", -6), ("system:credit-principal-receivable", "BTC", 6)])
    value["credit_events"].extend([
        {"command_id": "initial-pool", "kind": "POOL_FUNDED", "amount_satoshi": 100000000, "journal_event_id": pool},
        {"command_id": "initial-loan", "kind": "BORROWED", "amount_satoshi": 6, "journal_event_id": loan},
    ])
    log("INITIALIZED"); log("CONTROLLER_STARTED")
    legs = (("open-buy", A, 2000000, 1000000, "CANCELLED", False),
            ("open-sell", B, -1000000, -1000000, "FILLED", False),
            ("close-sell", A, -1000000, -1000000, "FILLED", True),
            ("close-buy", B, 1000000, 1000000, "FILLED", True))
    commands = (("open-buy", A), ("open-sell", B), ("cancel-partial", A), ("close-sell", A), ("close-buy", B), ("repay", C))
    for round_number in (1, 2):
        value["rounds"].append({"sequence": round_number, "state": "DONE"})
        log("ROUND_STARTED", round_number)
        for suffix, kind, origin, log_kind in (
            ("market", "PUBLISH_MARKET", "ROUND_FEED", "CONTROL_MARKET_TERMINAL"),
            ("activate", "SET_HALT", "ROUND_ACTIVATION", "CONTROL_ACTIVATION_TERMINAL")):
            control = "ctl:" + JOB + ":r" + str(round_number).zfill(9) + ":" + suffix
            value["controls"].append({"control_id": control, "round": round_number, "kind": kind, "origin": origin,
                                      "state": "SUCCEEDED", "result_known": True, "asset_impact": False})
            log(log_kind, round_number, business=control)
        value["commands"].extend({"command_id": cid(round_number, step), "round": round_number, "step": step,
            "account": account, "state": "SUCCEEDED", "result_known": True} for step, account in commands)
        for step, account, quantity, filled, state, reduce_only in legs:
            order = cid(round_number, step); fill = "f:" + order
            value["orders"].append({"order_id": order, "account": account, "round": round_number, "step": step,
                "quantity_satoshi": quantity, "filled_satoshi": filled, "status": state, "reduce_only": reduce_only})
            value["fills"].append({"fill_id": fill, "order_id": order, "account": account, "quantity_satoshi": filled,
                "price_usd_minor_per_btc": 10000000000, "fee_usd_minor": 40000, "realized_pnl_usd_minor": 0})
            value["decisions"].extend({"decision_id": label + ":" + order, "kind": kind, "business_id": business,
                "account": account, "round": round_number} for label, kind, business in (
                    ("accepted", "ORDER_ACCEPTED", order), ("filled", "FILL_CONFIRMED", fill)))
            event("FILL_FEE", fill, [("customer:" + account, "USD", -40000), ("system:fees", "USD", 40000)])
        for phase, buy, sell in (("open", "open-buy", "open-sell"), ("close", "close-buy", "close-sell")):
            value["matches"].append({"trade_id": "m:" + JOB + ":" + str(round_number) + ":" + phase,
                "round": round_number, "phase": phase, "buy_fill_id": "f:" + cid(round_number, buy),
                "sell_fill_id": "f:" + cid(round_number, sell), "quantity_satoshi": 1000000,
                "price_usd_minor_per_btc": 10000000000})
        repayment = event("REPAID", cid(round_number, "repay"), [("customer:" + C, "BTC", -2),
            ("system:credit-pool", "BTC", 2), ("liability:principal:" + C, "BTC", 2),
            ("system:credit-principal-receivable", "BTC", -2)])
        value["credit_events"].append({"command_id": cid(round_number, "repay"), "kind": "REPAID",
                                       "amount_satoshi": 2, "journal_event_id": repayment})
        log("ROUND_DONE", round_number)
    log("CONTROLLER_ENDED", status="paused")
    value["balances"] = [{"owner": owner, "asset": asset, "units": amount} for owner, asset, amount in (
        ("customer:" + A, "USD", 99999999840000), ("customer:" + B, "USD", 99999999840000),
        ("customer:" + C, "USD", 100000000000000), ("system:fees", "USD", 320000),
        ("system:custody", "USD", -300000000000000), ("customer:" + C, "BTC", 100000002),
        ("system:credit-pool", "BTC", 99999998), ("liability:principal:" + C, "BTC", -2),
        ("system:credit-principal-receivable", "BTC", 2), ("system:custody", "BTC", -100000000),
        ("system:credit-capital", "BTC", -100000000))]
    value["receipt"] = {"schema": "uta.completed_prefix_forensic_receipt.v1", "mode": "completed_prefix_forensic",
        "scope": "quiescent_completed_prefix_only_original_job_incomplete", "execution_status": "PREFIX_VERIFIED",
        "audit_authorization": "GRANTED", "original_source_commit": SOURCE, "original_job_status": "paused",
        "planned_rounds": 3, "completed_prefix_rounds": 2, "reviewed_manifest_sha256": "c" * 64,
        "checks": {name: True for name in CHECK_NAMES}, "qualification": dict(FLAGS),
        "limitations": ["ORIGINAL_JOB_INCOMPLETE", "NO_PRODUCTION_APPROVAL"],
        "new_original_data_write": False, "receipt_is_original_strict_cold": False}
    return value


def causal_oracle(value):
    """Closed-profile zero genesis only; not a rule for arbitrary funded accounts."""
    by_event = {}
    for posting in value["postings"]:
        by_event.setdefault(posting["event_id"], []).append(posting)
    balances = {}
    for event in value["ledger_events"]:
        for posting in by_event[event["event_id"]]:
            pair = posting["owner"], posting["asset"]
            balances[pair] = balances.get(pair, 0) + posting["units"]
        for (owner, _), units in balances.items():
            if (owner.startswith("customer:") or owner == "system:credit-pool" or
                    owner == "system:credit-principal-receivable") and units < 0:
                return False
            if owner.startswith("liability:principal:") and units > 0:
                return False
    if not set(value["receipt"]["limitations"]) <= LIMITS:
        return False
    expected = {(row["owner"], row["asset"]): row["units"] for row in value["balances"]}
    return balances == expected and balances[("liability:principal:" + C, "BTC")] == -2


def move_event(value, business, destination):
    index = next(i for i, row in enumerate(value["ledger_events"]) if row["business_id"] == business)
    value["ledger_events"].insert(destination, value["ledger_events"].pop(index))
    for sequence, row in enumerate(value["ledger_events"], 1):
        row["sequence"] = sequence


class IndependentPrefixCausalTests(unittest.TestCase):
    def assert_refused(self, value):
        self.assertFalse(causal_oracle(value))
        result = candidate.validate(value)
        self.assertIs(result["contract_consistent"], False)

    def test_legal_manual_profile_preserves_all_real_authority_false(self):
        value = fixture()
        self.assertTrue(causal_oracle(value))
        actual = candidate.validate(value)
        self.assertIs(actual["contract_consistent"], True, actual)
        self.assertEqual(actual["qualification"], FLAGS)
        for key in ("forensic_audit_performed", "real_quiescence_verified", "cryptographic_log_chain_verified",
                    "raw_source_or_manifest_authenticated", "sql_or_original_data_read"):
            self.assertIs(actual[key], False)

    def test_repayment_before_only_genesis_loan_is_refused(self):
        value = fixture(); move_event(value, cid(1, "repay"), 4)
        self.assert_refused(value)

    def test_only_genesis_loan_before_pool_capital_is_refused(self):
        value = fixture(); move_event(value, "initial-loan", 4)
        self.assert_refused(value)

    def test_fee_before_customer_genesis_funding_is_refused(self):
        value = fixture(); move_event(value, "f:" + cid(1, "open-buy"), 0)
        self.assert_refused(value)

    def test_unknown_limitation_in_declared_v1_receipt_is_refused(self):
        value = fixture(); value["receipt"]["limitations"].append("UNREGISTERED_APPROVAL_SCOPE")
        self.assert_refused(value)

    def test_independent_genesis_deposits_may_commute(self):
        value = fixture(); move_event(value, "deposit-bob-usd", 0)
        self.assertTrue(causal_oracle(value))
        self.assertIs(candidate.validate(value)["contract_consistent"], True)

    def test_no_numeric_alias_may_replace_gross_balance_integer(self):
        value = fixture(); value["balances"][0]["units"] = float(value["balances"][0]["units"])
        self.assertIs(candidate.validate(value)["contract_consistent"], False)

    def test_control_unknown_ownership_does_not_become_real_audit(self):
        value = fixture(); value["controls"][1]["origin"] = "UNEXPLAINED_OPERATOR_CHANGE"
        result = candidate.validate(value)
        self.assertIs(result["contract_consistent"], False)
        self.assertIs(result["forensic_audit_performed"], False)


def guard(event, args):
    if event in {"sqlite3.connect", "subprocess.Popen", "os.fork", "os.kill", "os.posix_spawn",
                 "socket.__new__", "socket.connect", "os.mkdir", "os.link", "os.remove", "os.rename"}:
        raise AssertionError("independent synthetic reference attempted native effect")
    if event == "open":
        _, mode, flags = args
        if (mode and any(char in mode for char in "wax+")) or flags & (os.O_WRONLY | os.O_RDWR):
            raise AssertionError("independent synthetic reference attempted write")


if __name__ == "__main__":
    raw = CORE.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == CORE_SHA256
    spec = importlib.util.spec_from_file_location("frozen_synthetic_prefix_candidate", CORE)
    candidate = importlib.util.module_from_spec(spec)
    sys.dont_write_bytecode = True
    sys.addaudithook(guard)
    spec.loader.exec_module(candidate)
    unittest.main()
