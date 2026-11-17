"""Owned reference checks, deliberately not production V2 acceptance tests."""
from copy import deepcopy
from fractions import Fraction as F
import hashlib
import importlib.util
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("owned_credit_reference", ROOT / "scripts/credit_v2_financial_reference.py")
REF = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(REF)


def manual_source():
    # Synthetic content-only specimen. It was never submitted to any producer.
    command = REF.canonical({"amount": "0.4", "asset": "BTC"})
    receipt = {"format": 2, "source_kind": "synthetic_local", "actor_id": "manual-actor",
               "source_reference": "manual:not-runtime", "authority_id": "manual-authority",
               "account_id": "alice", "command_id": "manual-cid", "kind": "BORROW",
               "payload_hash": hashlib.sha256(command.encode()).hexdigest(), "command_payload": command,
               "accepted_at": "2000-01-01T00:00:00.000000+00:00"}
    payload = REF.canonical(receipt)
    return {key: value for key, value in receipt.items() if key not in ("format", "accepted_at")} | {
        "payload": payload, "source_id": "credit-source:" + hashlib.sha256(payload.encode()).hexdigest()}


class IndependentCreditReferenceTests(unittest.TestCase):
    def test_eight_manual_vectors_leave_every_actual_observation_pending(self):
        result = REF.self_check()
        self.assertEqual(len(result["vectors"]), 8)
        self.assertEqual(result["runtime_status"], REF.RUNTIME_STATUS)
        for vector in result["vectors"]:
            for field in ("actual_capture", "source_id", "original_CID", "original_SID", "selected_at",
                          "last_checked_at", "journal_event_hash", "producer_commit", "financial_commit"):
                self.assertIsNone(vector[field])

    def test_gross_cash_deficit_principal_and_interest_remain_separate(self):
        _, kind, policy, before, amount = REF.manual_vectors()[2]
        result = REF.transition(kind, policy, before, REF.units(amount))
        self.assertEqual(result["gross_components"]["after"], {
            "assets": {"BTC": "1.1"}, "cash_deficits": {"USD": "1"},
            "principal": {"BTC": "0.2"}, "interest": {"BTC": "0.01"}})
        self.assertEqual(result["after"]["principal_ledger_units"], -REF.units("0.2"))
        self.assertEqual(result["after"]["interest_ledger_units"], -REF.units("0.01"))
        self.assertEqual(REF.risk(policy, result["after"])["initial_margin"], F("4.2"))

    def test_independently_derived_borrow_and_mixed_repay_ordinals_and_accounts(self):
        borrowed = REF.transition("BORROW", REF.POLICY, REF.state(), REF.units("0.4"))
        self.assertEqual([(leg["ordinal"], leg["account"], leg["asset"], leg["units"])
                          for leg in borrowed["ordered_legs"]], [
            (0, "customer:alice", "BTC", 40_000_000),
            (1, "liability:principal:alice", "BTC", -40_000_000),
            (2, "system:credit-pool", "BTC", -40_000_000),
            (3, "system:credit-principal-receivable", "BTC", 40_000_000)])
        before = REF.state(btc="0.5", principal="0.4", interest="0.05", pool="0.6")
        result = REF.transition("REPAY", REF.POLICY, before, REF.units("0.1"))
        self.assertEqual([(leg["account"], leg["units"]) for leg in result["ordered_legs"]], [
            ("customer:alice", -10_000_000), ("liability:interest:alice", 5_000_000),
            ("liability:principal:alice", 5_000_000), ("system:credit-interest-cash", 5_000_000),
            ("system:credit-interest-receivable", -5_000_000), ("system:credit-pool", 5_000_000),
            ("system:credit-principal-receivable", -5_000_000)])
        self.assertEqual(result["after"]["pool_units"] - before["pool_units"], 5_000_000)
        self.assertEqual(before["shard_principal_units"] + before["shard_interest_units"]
                         - result["after"]["shard_principal_units"] - result["after"]["shard_interest_units"], 10_000_000)

    def test_conservative_original_quote_refuses_point_zero_four_without_mutation(self):
        _, kind, policy, before, _ = REF.manual_vectors()[1]
        original = deepcopy(before)
        self.assertEqual(REF.authorized_quote(policy, before), REF.units("0.03"))
        with self.assertRaises(REF.ReferenceRefusal):
            REF.transition(kind, policy, before, REF.units("0.04"))
        self.assertEqual(before, original)

    def test_pool_account_local_and_static_allocation_caps_each_bind(self):
        base = REF.state()
        for changed_policy, changed_state in (
                ({"account_limit_units": REF.units("0.1")}, {}),
                ({"local_asset_limit_units": REF.units("0.1")}, {}),
                ({"allocations": {"0": REF.units("0.1"), "1": REF.units("0.9")}}, {}),
                ({}, {"pool_units": REF.units("0.1")})):
            policy, before = deepcopy(REF.POLICY), deepcopy(base)
            policy.update(changed_policy)
            before.update(changed_state)
            with self.subTest(policy=changed_policy, state=changed_state):
                self.assertEqual(REF.authorized_quote(policy, before), REF.units("0.1"))
                with self.assertRaises(REF.ReferenceRefusal):
                    REF.transition("BORROW", policy, before, REF.units("0.11"))

    def test_opening_interest_consumes_budget_without_becoming_pool_principal(self):
        before = REF.state(btc="0.4", principal="0.4", interest="0.05", pool="0.6")
        self.assertEqual(REF.authorized_quote(REF.POLICY, before), REF.units("0.05"))
        self.assertEqual(REF.transition("BORROW", REF.POLICY, before, REF.units("0.05"))["after"]["interest_units"], REF.units("0.05"))
        with self.assertRaises(REF.ReferenceRefusal):
            REF.transition("BORROW", REF.POLICY, before, REF.units("0.06"))

    def test_repayment_uses_no_quote_even_when_halted_and_zero_risk_capacity(self):
        before = REF.state(usd="-100", btc="0.5", principal="0.4", interest="0.05", pool="0.6")
        before.update(halted=True, liquidation_state="HALTED")
        self.assertEqual(REF.authorized_quote(REF.POLICY, before), 0)
        result = REF.transition("REPAY", REF.POLICY, before, REF.units("0.1"))
        self.assertEqual(result["market_dependency"], "NONE")
        self.assertEqual(result["new_borrow_decision_count"], 0)
        self.assertEqual(result["after"]["principal_units"], REF.units("0.35"))

    def test_invalid_integer_overflow_forged_liability_receivable_and_fields_reject(self):
        for field, value in (("principal_units", True), ("pool_units", 0.1), ("version", 2 ** 63 - 1),
                             ("pool_units", 10 ** 38), ("interest_units", -1),
                             ("principal_ledger_units", -1), ("principal_receivable_units", 1), ("forged", 0)):
            before = REF.state()
            before[field] = value
            with self.subTest(field=field, value=value), self.assertRaises(REF.ReferenceInputError):
                REF.validate(REF.POLICY, before)
        for value in (True, 0.4, 10 ** 38):
            with self.assertRaises(REF.ReferenceInputError):
                REF.transition("BORROW", REF.POLICY, REF.state(), value)

    def test_unknown_or_overallocated_static_shards_fail_without_releasing_budget(self):
        for values in ({"local_shard": "UNKNOWN"}, {"allocations": {"0": REF.units("0.6"), "1": REF.units("0.5")}}):
            policy = deepcopy(REF.POLICY)
            policy.update(values)
            with self.assertRaises(REF.ReferenceInputError):
                REF.authorized_quote(policy, REF.state())

    def test_published_canonical_unit_strings_reject_alternate_types_and_spellings(self):
        for value in (0, True, 1.0, "-0", "+1", "01", "1.0", "1e2", "١", str(10 ** 38), "9" * 1000):
            with self.subTest(value=str(value)[:30]), self.assertRaises(REF.ReferenceInputError):
                REF.unit_string(value, "wire amount")
        self.assertEqual(REF.unit_string("-1", "cash"), -1)
        self.assertEqual(REF.unit_string(str(10 ** 38 - 1), "max"), 10 ** 38 - 1)

    def test_duplicate_float_nonfinite_unknown_and_noncanonical_reference_json_reject(self):
        for text in ('{"a":1,"a":2}', '{"a":0.1}', '{"a":NaN}', '{"a":Infinity}', '{ "a":1}'):
            with self.subTest(text=text), self.assertRaises(REF.ReferenceInputError):
                REF.strict_loads(text, canonical_required=True)
        self.assertEqual(REF.strict_loads('{"a":1}', canonical_required=True), {"a": 1})
        policy = deepcopy(REF.POLICY)
        policy["forged_limit"] = 10 ** 37
        with self.assertRaises(REF.ReferenceInputError):
            REF.validate(policy, REF.state())

    def test_two_checkpoint_exact_age_and_future_boundaries_sid_and_order(self):
        observed = "2000-01-01T00:00:01+00:00"
        self.assertTrue(REF.checkpoint_contract(observed, "2000-01-01T00:00:00+00:00", "2000-01-01T00:00:06+00:00", "manualSID", "manualSID"))
        for selected, final, sid, error in (
                ("2000-01-01T00:00:00+00:00", "2000-01-01T00:00:06.000001+00:00", "manualSID", REF.ReferenceRefusal),
                ("1999-12-31T23:59:59.999999+00:00", "2000-01-01T00:00:01+00:00", "manualSID", REF.ReferenceRefusal),
                ("2000-01-01T00:00:02+00:00", "2000-01-01T00:00:01+00:00", "manualSID", REF.ReferenceRefusal),
                ("2000-01-01T00:00:01+00:00", "2000-01-01T00:00:02+00:00", "replacementSID", REF.ReferenceRefusal),
                ("2000-01-01T00:00:01Z", "2000-01-01T00:00:02+00:00", "manualSID", REF.ReferenceInputError)):
            with self.subTest(selected=selected, final=final, sid=sid), self.assertRaises(error):
                REF.checkpoint_contract(observed, selected, final, "manualSID", sid)

    def test_fifo_uses_original_account_cid_and_never_skips_pending_head(self):
        rows = [{"sequence": 1, "account": "bob", "CID": "other", "state": "PENDING"},
                {"sequence": 2, "account": "alice", "CID": "first", "state": "PENDING"},
                {"sequence": 3, "account": "alice", "CID": "next", "state": "PENDING"}]
        self.assertTrue(REF.fifo_contract(rows, "alice", "first"))
        with self.assertRaises(REF.ReferenceRefusal):
            REF.fifo_contract(rows, "alice", "next")
        rows[1]["state"] = "SUCCEEDED"
        self.assertTrue(REF.fifo_contract(rows, "alice", "next"))
        rows[1]["state"] = "UNKNOWN"
        with self.assertRaises(REF.ReferenceInputError):
            REF.fifo_contract(rows, "alice", "next")

    def test_synthetic_source_content_checks_cannot_claim_source_authenticity(self):
        source = manual_source()
        self.assertEqual(REF.source_contract(source)["source_authenticity"], "PENDING_ACTUAL_SOURCE_AND_INBOX_ROWS")
        for field, value in (("command_id", "replacement-CID"), ("source_id", "credit-source:forged"),
                             ("payload_hash", "f" * 64), ("command_payload", '{"amount":"0.5","asset":"BTC"}')):
            changed = deepcopy(source)
            changed[field] = value
            with self.subTest(field=field), self.assertRaises(REF.ReferenceInputError):
                REF.source_contract(changed)

    def manual_journal(self):
        # These four rows are hand constants, not a producer capture and not
        # seeded from transition()['ordered_legs'] or a claimed expected map.
        rows = [("customer:alice", "40000000"), ("liability:principal:alice", "-40000000"),
                ("system:credit-pool", "-40000000"), ("system:credit-principal-receivable", "40000000")]
        journal = {"sequence": 8, "event_id": REF.event_identity("alice", "manual-CID"),
                   "previous_hash": "1" * 64, "sealed": 1,
                   "postings": [{"ordinal": index, "account": name, "asset": "BTC", "units": value}
                                for index, (name, value) in enumerate(rows)]}
        self.rehash(journal)
        return journal

    def rehash(self, journal):
        legs = [{**row, "units": int(row["units"])} for row in journal["postings"]]
        journal["fingerprint"], journal["event_hash"] = REF.journal_hashes(
            journal["sequence"], journal["event_id"], journal["previous_hash"], legs)

    def compare(self, journal):
        return REF.compare_journal(journal, {"sequence": 7, "event_hash": "1" * 64},
            "BORROW", REF.POLICY, REF.state(), REF.units("0.4"), "alice", "manual-CID")

    def test_journal_uses_independent_financial_legs_and_keeps_sql_provenance_pending(self):
        self.assertEqual(self.compare(self.manual_journal())["actual_SQL_and_COMMIT_provenance"], "PENDING")

    def test_balanced_forged_legs_with_recomputed_self_hash_still_reject(self):
        journal = self.manual_journal()
        journal["postings"][2]["account"] = "system:credit-interest-cash"
        self.rehash(journal)
        with self.assertRaisesRegex(REF.ReferenceInputError, "independent financial transition"):
            self.compare(journal)

    def test_journal_wrong_cid_head_sequence_ordinal_bool_and_digest_reject(self):
        for field, value in (("sequence", 9), ("sequence", True), ("sealed", True),
                             ("event_id", REF.event_identity("alice", "replacement-CID")),
                             ("previous_hash", "2" * 64), ("fingerprint", "0" * 64)):
            journal = self.manual_journal()
            journal[field] = value
            with self.subTest(field=field), self.assertRaises(REF.ReferenceInputError):
                self.compare(journal)
        journal = self.manual_journal()
        journal["postings"][0]["ordinal"] = False
        with self.assertRaises(REF.ReferenceInputError):
            self.compare(journal)

    def test_late_reference_overflow_has_no_mutation_or_actual_sql_claim(self):
        before = REF.state()
        before["balances"]["BTC"] = 10 ** 38 - 1
        original = deepcopy(before)
        with self.assertRaises(REF.ReferenceInputError):
            REF.transition("BORROW", REF.POLICY, before, REF.units("0.01"))
        self.assertEqual(before, original)


if __name__ == "__main__":
    unittest.main()
