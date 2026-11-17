"""Independent adversarial retained-data checks, never native SQL execution."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("independent_repayment", ROOT/"scripts/credit_v2_repayment_reference.py")
REP = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(REP)
REF = REP.REF
ORIGINAL = ROOT/"evidence/reviews/credit-repayment-independent/original-actual-repayment-observations.json"


class IndependentRepaymentReferenceTests(unittest.TestCase):
    def cases(self):
        return json.loads(ORIGINAL.read_bytes())["observations"]

    def test_manual_interest_first_for_halted_case_uses_no_quote(self):
        before = REF.state(btc="0.4", principal="0.4", interest="0.05", pool="0.6", version=3)
        before["halted"] = True
        after = REF.transition("REPAY", REF.POLICY, before, 10_000_000)["after"]
        self.assertEqual([after[k] for k in ("principal_units", "interest_units", "pool_units", "interest_cash_units")],
                         [35_000_000, 0, 65_000_000, 5_000_000])
        self.assertEqual(after["balances"]["BTC"], 30_000_000)

    def test_market_quote_limits_and_borrow_decision_cannot_enter_repayment(self):
        for field, value in (("market_snapshot_id", "forged-SID"), ("selected_at", "2026-11-17T00:00:00+00:00"),
                             ("operation_id", "borrow-operation"), ("decision_kind", "CREDIT_BORROWED")):
            case = self.cases()[0]
            case["intent"][field] = value
            with self.subTest(field=field), self.assertRaises(REF.ReferenceInputError):
                REP.check_repayment(case)
        case = self.cases()[0]
        pre = json.loads(case["intent"]["pre_state_payload"])
        pre["quote_units"] = "100000000"
        case["intent"]["pre_state_payload"] = REF.canonical(pre)
        case["intent"]["pre_state_hash"] = REF.digest(pre)
        with self.assertRaisesRegex(REF.ReferenceInputError, "borrow input"):
            REP.check_repayment(case)

    def test_bool_sequence_and_declared_count_are_not_native_integers(self):
        for row, key in (("inbox", "sequence"), ("intent", "expected_postings"), ("intent", "journal_sealed")):
            case = self.cases()[0]
            case[row][key] = True
            with self.subTest(key=key), self.assertRaises(REF.ReferenceInputError):
                REP.check_repayment(case)

    def test_original_receipt_pays_interest_before_principal(self):
        case = self.cases()[1]
        receipt = json.loads(case["credit"]["result"])
        receipt.update(interest_repaid="0", principal_repaid="0.1")
        case["credit"]["result"] = case["inbox"]["result"] = REF.canonical(receipt)
        with self.assertRaisesRegex(REF.ReferenceInputError, "receipt amount"):
            REP.check_repayment(case)

    def test_frozen_cash_blocks_payment_despite_debt_and_complete_rehash(self):
        case = self.cases()[1]
        pre = json.loads(case["intent"]["pre_state_payload"])
        pre["account"]["frozen_assets"] = {"BTC": "0.4"}
        case["intent"]["pre_state_payload"] = REF.canonical(pre)
        case["intent"]["pre_state_hash"] = REF.digest(pre)
        with self.assertRaisesRegex(REF.ReferenceRefusal, "insufficient_unfrozen_cash"):
            REP.check_repayment(case)

    def test_materialized_pool_tamper_cannot_replace_original_postings(self):
        case = self.cases()[0]
        for row in case["actual_financial_rows"]["ledger_balances"]:
            if row["account"] == "system:credit-pool":
                row["units"] = "80000000"
        with self.assertRaisesRegex(REF.ReferenceInputError, "full ledger balances"):
            REP.check_repayment(case)

    def test_rehashed_balanced_principal_first_financial_forgery_still_refuses(self):
        case = self.cases()[1]
        target = case["journal"]["sequence"]
        legs = [{"ordinal": 0, "account": "customer:alice", "asset": "BTC", "units": "-10000000"},
            {"ordinal": 1, "account": "liability:principal:alice", "asset": "BTC", "units": "10000000"},
            {"ordinal": 2, "account": "system:credit-pool", "asset": "BTC", "units": "10000000"},
            {"ordinal": 3, "account": "system:credit-principal-receivable", "asset": "BTC", "units": "-10000000"}]
        fp, digest = REF.journal_hashes(target, case["journal"]["event_id"], case["journal"]["previous_hash"],
                                      [{**leg, "units": int(leg["units"])} for leg in legs])
        case["journal"].update(postings=legs, fingerprint=fp, event_hash=digest)
        rows = case["actual_financial_rows"]
        rows["ledger_postings"] = [leg for leg in rows["ledger_postings"] if leg["sequence"] != target] + [{"sequence": target, **leg} for leg in legs]
        for event in rows["ledger_events"]:
            if event["sequence"] == target:
                event.update(fingerprint=fp, event_hash=digest)
        balances = {}
        for leg in rows["ledger_postings"]:
            key = (leg["account"], leg["asset"])
            balances[key] = balances.get(key, 0)+int(leg["units"])
        rows["ledger_balances"] = [{"account": key[0], "asset": key[1], "units": str(value)} for key, value in balances.items()]
        rows["uta_liabilities"][0].update(principal="0.3", interest="0.05")
        case["actual_post_interest_cash_units"] = "0"
        case["intent"].update(expected_postings=4, new_principal_units="30000000", new_interest_units="5000000")
        case["expected_postings"] = [{"command_id": case["inbox"]["command_id"], **leg} for leg in legs]
        receipt = json.loads(case["credit"]["result"])
        receipt.update(principal_repaid="0.1", interest_repaid="0", principal="0.3", interest="0.05")
        case["credit"]["result"] = case["inbox"]["result"] = REF.canonical(receipt)
        with self.assertRaisesRegex(REF.ReferenceInputError, "gross component"):
            REP.check_repayment(case)


if __name__ == "__main__":
    unittest.main()
