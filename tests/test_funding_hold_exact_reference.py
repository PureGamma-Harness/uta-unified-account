"""Unexecuted independent reference test definitions; no production import.

These tests do not constitute differential execution against production.
The hand-entered expected fields are deliberately labeled partial slices.
"""
import json
from pathlib import Path
import unittest
from unittest.mock import patch

import reference_funding_hold_d1 as reference
import funding_hold_d1_reference_cases as cases


MANUAL = (Path(__file__).resolve().parents[1] / "evidence" / "designs" /
          "funding-hold-exact-reference" / "manual-slices.json")


def _legs(values, scale=2):
    kinds = {"P": "FINAL_PAYABLE", "U": "EXPOSURE_RATE_PENDING",
             "N": "FINAL_RECEIVABLE", "ZERO": "FINAL_ZERO"}
    return [cases.state(index, kinds[kind], units, scale)
            for index, (kind, units) in enumerate(values)]


class FundingHoldExactReferenceDefinitions(unittest.TestCase):
    def ok(self, request):
        response = reference.evaluate_request(request)
        self.assertEqual(response["status"], "OK", response)
        self.assertIs(response["activation_permission"], False)
        self.assertEqual(response["hash_wire"], "NOT_VERIFIED")
        return response["value"]

    def rejected(self, request, status="REJECT"):
        response = reference.evaluate_request(request)
        self.assertEqual(response["status"], status, response)
        self.assertIsNone(response["value"])
        self.assertIsInstance(response["diagnostic_code"], str)
        self.assertIs(response["activation_permission"], False)
        return response

    def test_manual_decomposition_hand_entered_fields_only(self):
        manual = json.loads(MANUAL.read_text(encoding="utf-8"))
        for vector in manual["decomposition_vectors"]:
            with self.subTest(slice_id=vector["id"]):
                b = cases.base(**vector["base"])
                q = cases.request(vector["id"], "decompose", {
                    "base": b, "states": _legs(vector["legs"]), "basis_complete": True})
                before = cases.clone(q)
                result = self.ok(q)
                for field, expected in vector["expected"].items():
                    self.assertEqual(result[field], expected, field)
                self.assertEqual(q, before)

    def test_manual_payment_hand_entered_fields_only(self):
        manual = json.loads(MANUAL.read_text(encoding="utf-8"))
        for vector in manual["payment_vectors"]:
            with self.subTest(slice_id=vector["id"]):
                q = cases.payment_request(vector["id"], _legs(vector["legs"]),
                    cash=vector["cash"], frozen=vector["frozen"],
                    prior=vector["prior"], quote=vector["quote"])
                before = cases.clone(q)
                result = self.ok(q)
                for field, expected in vector["expected"].items():
                    self.assertEqual(result[field], expected, field)
                self.assertEqual(q, before)

    def test_original_27_matrix_is_slice_only_or_unsupported(self):
        manual = json.loads(MANUAL.read_text(encoding="utf-8"))
        matrix = manual["matrix"]
        self.assertEqual([row["id"] for row in matrix],
                         ["PFH-M" + str(i).zfill(2) for i in range(1, 28)])
        self.assertTrue(all(row["coverage"] in ("SLICE_ONLY", "UNSUPPORTED")
                            and row["not_covered"] for row in matrix))
        self.assertEqual(matrix[13]["coverage"], "UNSUPPORTED")
        self.assertEqual(matrix[26]["coverage"], "UNSUPPORTED")
        self.assertIs(manual["activation_permission"], False)

    def test_m10_provided_cap_to_each_final_not_rate_derivation(self):
        for kind, amount, hold in (("FINAL_PAYABLE", 246, 246),
                                   ("FINAL_RECEIVABLE", 246, 0),
                                   ("FINAL_ZERO", 0, 0)):
            with self.subTest(kind=kind):
                current = cases.state(0, "EXPOSURE_RATE_PENDING", 600)
                q = cases.stage_request("M10", current,
                    cases.stage(current["key"], kind, amount))
                after = self.ok(q)
                self.assertEqual(after["revision"], 2)
                self.assertEqual(after["history"][1], current["active"])
                totals = self.ok(cases.aggregate_request("M10-SUM", [after]))
                self.assertEqual(totals["H"], hold)
                self.assertEqual(totals["U"], 0)

    def test_m23_queries_are_charged_before_unknown_results(self):
        record = cases.wait_record()
        for index, observed in enumerate((0, 5000000, 10000000, 15000000), start=1):
            result = self.ok(cases.wait_request("M23", record, observed))
            record = result["record"]
            self.assertEqual(record["attempts"], index)
            self.assertEqual(record["deadline_us"], 30000000)
            self.assertTrue(result["query_counted"])
            self.assertEqual(record["default_review"], index == 4)
            self.assertTrue(result["holds_unchanged"])
        retry = self.ok(cases.wait_request("M23-UNKNOWN-RETRY", record, 15000000))
        self.assertEqual(retry["record"], record)
        self.assertFalse(retry["query_counted"])
        self.assertEqual(retry["outcome"], "DEFAULT_REVIEW")

    def test_all_1024_declared_statuses_no_target_comparison(self):
        partitions = {"valid": 0, "negative": 0}
        families = {name: {"valid": 0, "negative": 0} for name in cases.FAMILIES}
        for case in cases.iter_cases():
            with self.subTest(seed=case["seed"], family=case["family"]):
                before = cases.clone(case["request"])
                response = reference.evaluate_request(case["request"])
                self.assertEqual(response["status"], case["expected_status"], response)
                self.assertIs(response["activation_permission"], False)
                self.assertEqual(case["request"], before)
                partitions[case["partition"]] += 1
                families[case["family"]][case["partition"]] += 1
        self.assertEqual(partitions, {"valid": 512, "negative": 512})
        self.assertTrue(all(counts == {"valid": 64, "negative": 64}
                            for counts in families.values()))

    def test_seed_wire_determinism_and_two_mib_bound(self):
        for seed in range(1024):
            first, second = cases.case_for_seed(seed), cases.case_for_seed(seed)
            self.assertEqual(first, second)
            raw = json.dumps(first["request"], separators=(",", ":"), ensure_ascii=True)
            self.assertLessEqual(len(raw.encode("ascii")), 2 * 1024 * 1024)
            self.assertEqual(reference.load_request(raw), first["request"])

    def test_seed_domain_is_closed_native_integer(self):
        for value in (-1, 1024, True, 1.0, "1", None):
            with self.subTest(value=value), self.assertRaises(ValueError):
                cases.case_for_seed(value)

    def test_duty_canonical_literal_and_natural_slot(self):
        value = cases.key()
        # Literal canonical bytes are independent of either serializer helper.
        literal = ('{"account_id":"synthetic-account","authority_generation":"gen-1",'
                   '"authority_id":"synthetic-authority","interval_seconds":28800,'
                   '"period_end":"2026-01-01T08:00:00+00:00","rule_scope_id":'
                   '"synthetic-funding-rule-v1","schema":1,"settlement_asset":"USD",'
                   '"symbol":"SYNTH-0"}')
        self.assertEqual(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                    ensure_ascii=True), literal)
        result = self.ok(cases.request("KEY-LITERAL", "duty_identity", {"key": value}))
        self.assertEqual(result["duty_id"],
                         "funding-duty:v1:fe691611fdc347f693218f1f9043313d9a516f9979eb6e0027a8a58b06fb1509")
        for name, replacement in (("interval_seconds", 14400),
                                   ("rule_scope_id", "different-rule-v2")):
            changed = cases.clone(value)
            changed[name] = replacement
            other = self.ok(cases.request("KEY-CHANGED", "duty_identity", {"key": changed}))
            self.assertNotEqual(other["duty_id"], result["duty_id"])
            self.assertEqual(other["natural_slot"], result["natural_slot"])

    def test_unassessed_required_duty_never_zero(self):
        self.rejected(cases.aggregate_request("UNASSESSED", [
            cases.state(kind="REGISTERED_UNASSESSED")]))
        empty = self.ok(cases.aggregate_request("EMPTY-SUPPLIED-COMPLETE", []))
        self.assertEqual((empty["P"], empty["U"], empty["N"], empty["H"]), (0, 0, 0, 0))
        # The caller's complete flag is not authenticated completeness evidence.

    def test_receivable_does_not_offset_hold_or_spend(self):
        before = self.ok(cases.request("NO-N", "decompose", {
            "base": cases.base(), "states": _legs([["P", 1200], ["U", 600]]),
            "basis_complete": True}))
        after = self.ok(cases.request("WITH-N", "decompose", {
            "base": cases.base(), "states": _legs([["P", 1200], ["U", 600], ["N", 2000]]),
            "basis_complete": True}))
        self.assertEqual(after["H"], 1800)
        self.assertEqual(after["accrual_equity_units"] - before["accrual_equity_units"], 2000)
        for field in ("H", "risk_equity_units", "available_margin_units",
                      "ordinary_spend_raw_units", "ordinary_spendable_units"):
            self.assertEqual(before[field], after[field])

    def test_conditional_external_payment_accrual_identity(self):
        before = self.ok(cases.request("CONTINUITY-BEFORE", "decompose", {
            "base": cases.base(accounting=10000, risk=1500, cash=10000, frozen=8500,
                               im=0, mm=0, reserve=0),
            "states": _legs([["P", 1200]]), "basis_complete": True}))
        # This is an externally supplied hypothetical AFTER base, not an ACK/APPLIED.
        after = self.ok(cases.request("CONTINUITY-HYPOTHETICAL-AFTER", "decompose", {
            "base": cases.base(accounting=8800, risk=300, cash=8800, frozen=8500,
                               im=0, mm=0, reserve=0),
            "states": [], "basis_complete": True}))
        self.assertEqual(before["accrual_equity_units"], 8800)
        self.assertEqual(after["accrual_equity_units"], 8800)
        self.assertEqual(before["risk_equity_units"], 300)
        self.assertEqual(after["risk_equity_units"], 300)

    def test_spot_freeze_only_counted_in_supplied_base_once(self):
        value = self.ok(cases.request("NO-DOUBLE-F", "decompose", {
            "base": cases.base(risk=1500, cash=10000, frozen=8500),
            "states": _legs([["P", 1200]]), "basis_complete": True}))
        self.assertEqual(value["risk_equity_units"], 300)
        self.assertEqual(value["ordinary_spend_raw_units"], 300)

    def test_final_representation_immutable_and_stale_cap_rejected(self):
        final = cases.state(kind="FINAL_PAYABLE", amount=246)
        self.rejected(cases.stage_request("FINAL-IMMUTABLE", final,
            cases.stage(final["key"], "FINAL_RECEIVABLE", 246)))
        cap = cases.state(kind="EXPOSURE_RATE_PENDING", amount=600)
        q = cases.stage_request("CAP-STALE", cap,
            cases.stage(cap["key"], "FINAL_PAYABLE", 246))
        q["input"]["expected_active_ref"]["digest"] = "e" * 64
        self.rejected(q)

    def test_large_units_exact_without_i64_or_float(self):
        units = 10 ** 38 - 1
        states = [cases.state(i, "FINAL_PAYABLE", units, scale=8) for i in range(1000)]
        value = self.ok(cases.aggregate_request("MAX-1000", states, scale=8))
        self.assertEqual(value["P"], 1000 * units)
        self.assertEqual(value["H"], 1000 * units)
        self.assertEqual(value["N"], 0)
        self.assertEqual(len(value["duty_ids"]), 1000)
        self.rejected(cases.aggregate_request("OVER-1000", states + [
            cases.state(1000, "FINAL_ZERO", 0, scale=8)], scale=8))

    def test_backing_equality_other_hold_and_zero_lock_negative_cash(self):
        values = _legs([["P", 1200], ["U", 600], ["P", 700], ["N", 900]])
        result = self.ok(cases.payment_request("BACKING-EQUALITY", values,
                                             cash=10000, frozen=8800))
        self.assertEqual(result["outcome"], "PREVIEW_BACKING_ELIGIBLE")
        self.assertEqual(result["projected_cash_units"], 8800)
        self.assertEqual(result["projected_H"], 1300)
        self.assertEqual(result["projected_N"], 900)
        negative = self.ok(cases.payment_request("NEGATIVE-CASH", _legs([["P", 500]]),
                                               cash=-100, frozen=0))
        self.assertEqual(negative["projected_cash_units"], -600)

    def test_prior_unresolved_and_crossing_wait_have_no_effect(self):
        for cash, frozen, prior in ((10000, 9500, True), (10000, 0, False)):
            result = self.ok(cases.payment_request("WAIT-UNCHANGED",
                _legs([["P", 1200], ["U", 600], ["N", 2000]]),
                cash=cash, frozen=frozen, prior=prior))
            self.assertEqual(result["outcome"], "WAITING_ENCUMBRANCE_RELEASE")
            self.assertEqual((result["projected_cash_units"], result["projected_P"],
                result["projected_U"], result["projected_N"], result["projected_H"]),
                (cash, 1200, 600, 2000, 1800))

    def test_wait_deadline_boundary_no_automatic_release(self):
        record = cases.wait_record(attempts=1)
        result = self.ok(cases.wait_request("DEADLINE-EXACT", record, 30000000))
        self.assertEqual(result["outcome"], "DEFAULT_REVIEW")
        self.assertFalse(result["query_counted"])
        self.assertEqual(result["record"]["attempts"], 1)
        self.assertTrue(result["holds_unchanged"])
        changed = cases.wait_request("POLICY-NO-RESET", record)
        changed["input"]["expected_policy"]["max_wait_us"] += 1
        self.rejected(changed)
        regression = cases.wait_request("CLOCK-REGRESSION", record, now=0)
        regression["input"]["record"]["observed_highwater_us"] = 1
        self.rejected(regression)

    def test_shared_action_dedup_does_not_select_larger_policy(self):
        first, second = cases.wait_record(), cases.wait_record()
        second["policy"]["max_query_attempts"] = 10
        self.rejected(cases.request("SHARED-NO-LARGER", "wait_records", {
            "records": [first, second]}))
        second["action"]["scope"]["usd_scale"] = 8
        self.rejected(cases.request("SHARED-NO-SCALE-RESET", "wait_records", {
            "records": [first, second]}))

    def test_json_closed_keys_duplicates_and_native_money(self):
        with self.assertRaises(reference.ReferenceReject):
            reference.load_request('{"schema":1,"schema":1}')
        with self.assertRaises(reference.ReferenceReject):
            reference.load_request('{"amount":NaN}')
        with self.assertRaises(reference.ReferenceReject):
            reference.load_request(" " * (2 * 1024 * 1024 + 1))
        q = cases.payment_request("BOOL-IS-NOT-MONEY", _legs([["P", 500]]))
        q["input"]["cash_units"] = True
        self.rejected(q)
        q = cases.request("EXTRA-KEY", "duty_identity", {"key": cases.key()})
        q["input"]["key"]["claim_id"] = "synthetic-claim"
        self.rejected(q)

    def test_unsupported_borrowable_and_d2_never_return_success(self):
        for operation in ("BORROWABLE", "QTY_MARK_RATE_CAP", "NEW_IM_MM",
                          "LEDGER_ACK_APPLY", "WHOLE_PERIOD_COMMIT"):
            self.rejected(cases.request("UNSUPPORTED-" + operation, "unsupported", {
                "operation": operation}), "UNSUPPORTED")

    def test_unknown_internal_exception_is_not_business_rejection(self):
        with patch.object(reference, "_evaluate", side_effect=RuntimeError("synthetic_failure")):
            with self.assertRaisesRegex(RuntimeError, "synthetic_failure"):
                reference.evaluate_request(cases.request("TECHNICAL", "aggregate", {}))
