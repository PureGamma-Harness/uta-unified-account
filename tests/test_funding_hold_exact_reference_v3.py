"""Independent reference contract and transport tests; no production import.

These tests do not constitute differential execution against production.
The hand-entered expected fields are deliberately labeled partial slices.
"""
import json
from pathlib import Path
import re
import unittest
from unittest.mock import patch

import reference_funding_hold_d1_v3 as reference
import funding_hold_d1_reference_cases_v3 as cases


MANUAL = (Path(__file__).resolve().parents[1] / "evidence" / "designs" /
          "funding-hold-exact-reference-v3" / "manual-slices.json")


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
        self.assertEqual(response["hash_wire"], "CODE_CONTRACT_IMPLEMENTED_NOT_RUN")
        self.assertEqual(response["schema"], 3)
        self.assertEqual(set(response), {"schema", "case_id", "status", "value",
                         "diagnostic_code", "activation_permission", "hash_wire"})
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
                    cases.stage(current["key"], kind, amount, lineage=current["active"]))
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
        operations = set()
        valid_identity = {"duty_identity": 0, "policy_identity": 0, "action_identity": 0}
        for case in cases.iter_cases():
            with self.subTest(seed=case["seed"], family=case["family"]):
                before = cases.clone(case["request"])
                response = reference.evaluate_request(case["request"])
                self.assertEqual(response["status"], case["expected_status"], response)
                self.assertIs(response["activation_permission"], False)
                self.assertEqual(case["request"], before)
                partitions[case["partition"]] += 1
                families[case["family"]][case["partition"]] += 1
                operations.add(case["request"]["op"])
                if case["partition"] == "valid" and case["family"] == "identity":
                    valid_identity[case["request"]["op"]] += 1
        self.assertEqual(operations, {"duty_identity", "policy_identity", "action_identity",
            "stage_advance", "aggregate", "decompose", "payment_precondition",
            "wait_preview", "wait_records", "unsupported"})
        self.assertEqual(valid_identity,
            {"duty_identity": 32, "policy_identity": 16, "action_identity": 16})
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
            cases.state(kind="REGISTERED_UNASSESSED")]), "UNSUPPORTED")
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
            cases.stage(final["key"], "FINAL_RECEIVABLE", 246)), "UNSUPPORTED")
        cap = cases.state(kind="EXPOSURE_RATE_PENDING", amount=600)
        q = cases.stage_request("CAP-STALE", cap,
            cases.stage(cap["key"], "FINAL_PAYABLE", 246, lineage=cap["active"]))
        q["input"]["expected_active_stage"]["cap_ref"]["digest"] = "e" * 64
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
        changed["input"]["expected_policy_digest"] = "d" * 64
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
        for kind in (RuntimeError, ValueError, TypeError):
            error = kind("synthetic_failure")
            with self.subTest(kind=kind.__name__), patch.object(reference, "_evaluate", side_effect=error):
                with self.assertRaises(kind) as caught:
                    reference.evaluate_request(cases.request("TECHNICAL", "aggregate", {}))
                self.assertIs(caught.exception, error)

    def test_v3_policy_identity_literal_payload_and_digest(self):
        policy = cases.policy()
        result = self.ok(cases.request("V3-POLICY", "policy_identity", {"policy": policy}))
        self.assertEqual(result, {"digest": "5124f316d0767fa0354ead3466d522f0d740c8d6134b4608a98352efb0cfd662",
                         "payload": policy, "activation_permission": False})
        q = cases.request("V3-POLICY-EXTRA", "policy_identity", {"policy": cases.clone(policy)})
        q["input"]["policy"]["action_id"] = "not-a-policy-field"
        self.rejected(q)

    def test_v3_action_identity_payload_and_scale_exclusion(self):
        action = {"scope": cases.scope(), "allocation_id": "allocation-0"}
        first = self.ok(cases.request("V3-ACTION", "action_identity", {"action": action}))
        payload = {"authority_id": "synthetic-authority", "authority_generation": "gen-1",
                   "account_id": "synthetic-account", "settlement_asset": "USD",
                   "allocation_id": "allocation-0", "action": "CANCEL_QUERY",
                   "terminal_goal": "CONFIRMED_CLOSED"}
        self.assertEqual(first, {"action_id": "funding-action:v1:32676d7af47822bbfecc62ae7f27acd113028657d7fbb0a7865f7466cb372469",
                                 "payload": payload, "activation_permission": False})
        action["scope"]["usd_scale"] = 8
        self.assertEqual(self.ok(cases.request("V3-ACTION-SCALE", "action_identity", {"action": action})), first)
        q = cases.request("V3-ACTION-CLAIM", "action_identity", {"action": cases.clone(action)})
        q["input"]["action"]["claim_id"] = "cannot-reset-root-lineage"
        self.rejected(q)

    def test_v3_epoch_and_period_alignment(self):
        for text, interval, expected in (
            ("1970-01-01T00:00:00+00:00", 86400, "OK"),
            ("2026-01-01T08:00:00+00:00", 28800, "OK"),
            ("1969-12-31T00:00:00+00:00", 86400, "REJECT"),
            ("2026-01-01T07:59:59+00:00", 28800, "REJECT"),
            ("2026-01-01T08:00:01+00:00", 28800, "REJECT")):
            with self.subTest(text=text):
                key = cases.key()
                key.update(period_end=text, interval_seconds=interval)
                response = reference.evaluate_request(cases.request("V3-PERIOD", "duty_identity", {"key": key}))
                self.assertEqual(response["status"], expected)
                if expected == "OK":
                    self.assertEqual(response["value"]["natural_slot"], [key[n] for n in
                        ("authority_id", "authority_generation", "symbol", "period_end", "settlement_asset", "account_id")])

    def test_v3_complete_expected_stage_and_legacy_keyword(self):
        current = cases.state(kind="EXPOSURE_RATE_PENDING", amount=600)
        proposed = cases.stage(current["key"], "FINAL_PAYABLE", 246, lineage=current["active"])
        for field in ("exposure_ref", "cap_ref", "amount_units"):
            q = cases.stage_request("V3-FULL-CAS", cases.clone(current), proposed)
            if field == "amount_units":
                q["input"]["expected_active_stage"][field] = 599
            else:
                q["input"]["expected_active_stage"][field]["digest"] = "d" * 64
            before = cases.clone(q)
            self.rejected(q)
            self.assertEqual(q, before)
        final = cases.state(kind="FINAL_PAYABLE", amount=246)
        q = cases.stage_request("V3-KIND-CAS", final, cases.stage(final["key"], "FINAL_ZERO", 0))
        q["input"]["expected_active_stage"]["kind"] = "FINAL_RECEIVABLE"
        self.rejected(q)
        legacy = cases.stage_request("V3-LEGACY-REF", current, proposed)
        del legacy["input"]["expected_active_stage"]
        legacy["input"]["expected_active_ref"] = current["active"]["cap_ref"]
        self.rejected(legacy, "UNSUPPORTED")

    def test_v3_normal_noop_retains_revision_and_query_budget(self):
        record = cases.wait_record(attempts=1)
        response = self.ok(cases.wait_request("V3-NOOP", record, now=0, dispatch=False))
        self.assertEqual(response["record"], record)
        self.assertEqual(response["record"]["revision"], 1)
        self.assertFalse(response["query_counted"])
        self.rejected(cases.wait_request("V3-EARLY-DISPATCH", record, now=0, dispatch=True))
        charged = self.ok(cases.wait_request("V3-DISPATCH", record, now=5000000))
        self.assertEqual((charged["record"]["attempts"], charged["record"]["revision"]), (2, 2))
        retried = self.ok(cases.wait_request("V3-UNKNOWN-RESULT", charged["record"], now=5000000, dispatch=False))
        self.assertEqual(retried["record"], charged["record"])
        self.assertFalse(retried["query_counted"])
        self.rejected(cases.wait_request("V3-UNKNOWN-REDISPATCH", charged["record"], now=5000000))

    def test_v3_maximum_revision_only_genuine_noop_permitted(self):
        for default in (False, True):
            record = cases.wait_record(attempts=1, default=default)
            record["revision"] = 2**63 - 1
            original = cases.clone(record)
            unchanged = self.ok(cases.wait_request("V3-MAX-NOOP", record, now=0, dispatch=False))
            self.assertEqual(unchanged["record"], original)
            self.rejected(cases.wait_request("V3-MAX-CHANGE", record, now=1, dispatch=False))
            self.assertEqual(record, original)
        initial = cases.wait_record()
        initial["revision"] = 2**63 - 1
        self.rejected(cases.wait_request("V3-MAX-QUERY", initial, now=0, dispatch=True))

    def test_v3_deadline_interval_equality_and_default_at_maxrevision(self):
        record = cases.wait_record(attempts=1)
        self.rejected(cases.wait_request("V3-INTERVAL-BEFORE", record, now=4999999))
        not_due = self.ok(cases.wait_request("V3-OBSERVE-BEFORE", record, now=4999999, dispatch=False))
        self.assertFalse(not_due["query_counted"])
        due = self.ok(cases.wait_request("V3-INTERVAL-EQUAL", record, now=5000000))
        self.assertTrue(due["query_counted"])
        deadline = self.ok(cases.wait_request("V3-DEADLINE-EQUAL", record, now=30000000))
        self.assertEqual(deadline["outcome"], "DEFAULT_REVIEW")
        self.assertFalse(deadline["query_counted"])
        record.update(observed_highwater_us=30000000, revision=2**63 - 1)
        self.rejected(cases.wait_request("V3-MAX-DEFAULT-CHANGE", record, now=30000000, dispatch=False))
        budget = cases.wait_record(attempts=4, default=False)
        budget["revision"] = 2**63 - 1
        self.rejected(cases.wait_request("V3-MAX-BUDGET-DEFAULT", budget, dispatch=False))

    def test_v3_full_output_schema_action_ids_and_transport_boundaries(self):
        path = MANUAL.parents[1] / "funding-hold-exact-reference-v3" / "wire-contract.json"
        contract = json.loads(path.read_text(encoding="utf-8"))
        definitions = contract["$defs"]
        def check(schema, value):
            if "$ref" in schema:
                return check(definitions[schema["$ref"].rsplit("/", 1)[-1]], value)
            if "oneOf" in schema:
                count = 0
                for option in schema["oneOf"]:
                    try:
                        check(option, value)
                    except AssertionError:
                        continue
                    count += 1
                self.assertEqual(count, 1)
                return
            if "const" in schema:
                self.assertIs(type(value), type(schema["const"]))
                self.assertEqual(value, schema["const"])
            if "enum" in schema:
                self.assertTrue(any(type(value) is type(item) and value == item for item in schema["enum"]))
            kind = schema.get("type")
            if kind is not None:
                types = {"integer": int, "boolean": bool, "string": str, "object": dict,
                         "array": list, "null": type(None)}
                self.assertIs(type(value), types[kind])
            if kind == "object":
                self.assertEqual(set(value), set(schema["required"]))
                for name, item in value.items():
                    check(schema["properties"][name], item)
            if kind == "array":
                self.assertLessEqual(len(value), schema.get("maxItems", len(value)))
                self.assertGreaterEqual(len(value), schema.get("minItems", 0))
                for item in value:
                    check(schema["items"], item)
            if kind == "string" and "pattern" in schema:
                self.assertIsNotNone(re.fullmatch(schema["pattern"], value))
            for field, compare in (("minimum", lambda a, b: a >= b), ("maximum", lambda a, b: a <= b),
                                   ("exclusiveMinimum", lambda a, b: a > b), ("exclusiveMaximum", lambda a, b: a < b)):
                if field in schema:
                    self.assertTrue(compare(value, schema[field]))
        for case in cases.iter_cases():
            response = reference.evaluate_request(case["request"])
            check(contract["response"], response)
            if response["status"] == "OK":
                self.assertIsNone(response["diagnostic_code"])
                check(contract["operations"][case["request"]["op"]]["value"], response["value"])
            else:
                self.assertIsNone(response["value"])
                self.assertEqual(response["diagnostic_code"], "REJECTED_INPUT_OR_PRECONDITION"
                    if response["status"] == "REJECT" else "UNSUPPORTED_OPERATION_OR_CAPABILITY")
        rows = [cases.wait_record(9), cases.wait_record(0)]
        value = self.ok(cases.request("V3-FULL-ACTION-IDS", "wait_records", {"records": rows}))
        ids = [self.ok(cases.request("V3-ACTION-ITEM", "action_identity", {"action": row["action"]}))["action_id"] for row in rows]
        self.assertEqual(value, {"action_ids": sorted(ids), "record_count": 2,
                                "holds_unchanged": True, "activation_permission": False})
        for malformed in (None, {}, {"schema": 3, "case_id": "bad id", "op": "aggregate", "input": {}},
                          {"schema": 3, "case_id": "GOOD", "op": "unknown", "input": {}},
                          {"schema": 2, "case_id": "GOOD", "op": "aggregate", "input": {}}):
            with self.assertRaises(reference.ReferenceWireReject):
                reference.evaluate_request(malformed)
        self.assertEqual(reference.load_request("9" * 128), int("9" * 128))
        with self.assertRaises(reference.ReferenceWireReject):
            reference.load_request("9" * 129)
        self.assertIs(type(reference.load_request("1.0")), float)
        for raw in ("NaN", "Infinity", "1e999", b"\xef\xbb\xbf{}", b"\xff"):
            with self.assertRaises(reference.ReferenceWireReject):
                reference.load_request(raw)
        depth32 = "[" * 32 + "0" + "]" * 32
        reference.load_request(depth32)
        with self.assertRaises(reference.ReferenceWireReject):
            reference.load_request("[" + depth32 + "]")
        # Root list counts once; the 249999 scalar values reach exactly250000.
        reference.load_request("[" + ",".join(["0"] * 249999) + "]")
        with self.assertRaises(reference.ReferenceWireReject):
            reference.load_request("[" + ",".join(["0"] * 250000) + "]")
        expanded = json.dumps("é" * 400000, ensure_ascii=False).encode("utf-8")
        self.assertLess(len(expanded), 2 * 1024 * 1024)
        with self.assertRaises(reference.ReferenceWireReject):
            reference.load_request(expanded)
        cycle = []
        cycle.append(cycle)
        cyclic = cases.aggregate_request("V3-CYCLE", [])
        cyclic["input"]["extra"] = cycle
        with self.assertRaises(reference.ReferenceWireReject):
            reference.evaluate_request(cyclic)
        shared = cases.state(kind="FINAL_ZERO", amount=0)
        # Repeated aliases pass transport, then duplicate duty is known REJECT.
        self.rejected(cases.aggregate_request("V3-ALIAS", [shared, shared]))

    def test_lineage_direct_and_via_U_all_final_kinds_compare_complete_stage(self):
        for kind, amount, expected in (
            ("FINAL_PAYABLE", 246, {"P": 246, "U": 0, "N": 0, "H": 246}),
            ("FINAL_RECEIVABLE", 246, {"P": 0, "U": 0, "N": 246, "H": 0}),
            ("FINAL_ZERO", 0, {"P": 0, "U": 0, "N": 0, "H": 0})):
            for through_U in (False, True):
                with self.subTest(kind=kind, through_U=through_U):
                    current = cases.state(kind="EXPOSURE_RATE_PENDING", amount=600) if through_U else cases.state(kind="REGISTERED_UNASSESSED")
                    proposed = cases.stage(current["key"], kind, amount,
                        lineage=current["active"] if through_U else None)
                    request = cases.stage_request("D1V3-LINEAGE-POSITIVE", current, proposed)
                    before = cases.clone(request)
                    result = self.ok(request)
                    self.assertEqual(result["active"], proposed)
                    self.assertEqual(result["history"], current["history"] + [current["active"]])
                    self.assertEqual(result["revision"], 2 if through_U else 1)
                    self.assertEqual(result["active"]["exposure_ref"], current["active"]["exposure_ref"])
                    self.assertEqual(result["active"]["cap_ref"], current["active"]["cap_ref"])
                    self.assertIsNotNone(result["active"]["final_ref"])
                    totals = self.ok(cases.aggregate_request("D1V3-LINEAGE-ONE-ACTIVE", [result]))
                    self.assertEqual({name: totals[name] for name in ("P", "U", "N", "H")}, expected)
                    self.assertEqual(request, before)

    def test_lineage_missing_partial_changed_and_foreign_pairs_reject(self):
        for kind in ("FINAL_PAYABLE", "FINAL_RECEIVABLE", "FINAL_ZERO"):
            current = cases.state(kind="EXPOSURE_RATE_PENDING", amount=600)
            amount = 0 if kind == "FINAL_ZERO" else 246
            good = cases.stage(current["key"], kind, amount, lineage=current["active"])
            for defect in ("missing_both", "missing_E", "missing_C", "changed_E", "changed_C",
                           "foreign_duty", "foreign_scope", "missing_final"):
                proposed = cases.clone(good)
                if defect == "missing_both":
                    proposed["exposure_ref"] = proposed["cap_ref"] = None
                elif defect == "missing_E":
                    proposed["exposure_ref"] = None
                elif defect == "missing_C":
                    proposed["cap_ref"] = None
                elif defect == "changed_E":
                    proposed["exposure_ref"]["digest"] = "d" * 64
                elif defect == "changed_C":
                    proposed["cap_ref"]["digest"] = "e" * 64
                elif defect == "foreign_duty":
                    proposed["exposure_ref"]["duty_id"] = cases.duty_id(cases.key(999))
                elif defect == "foreign_scope":
                    proposed["cap_ref"]["rule_scope_id"] = "synthetic-foreign-rule"
                else:
                    proposed["final_ref"] = None
                q = cases.stage_request("D1V3-LINEAGE-NEGATIVE", current, proposed)
                before = cases.clone(q)
                with self.subTest(kind=kind, defect=defect):
                    self.rejected(q)
                    self.assertEqual(q, before)

    def test_lineage_context_and_provided_immutable_history_must_agree(self):
        for kind in ("FINAL_PAYABLE", "FINAL_RECEIVABLE", "FINAL_ZERO"):
            amount = 0 if kind == "FINAL_ZERO" else 246
            pending = cases.state(kind="EXPOSURE_RATE_PENDING", amount=600)
            initial = cases.state(kind="REGISTERED_UNASSESSED")
            supplied = cases.stage(initial["key"], kind, amount, lineage=pending["active"])
            self.rejected(cases.stage_request("D1V3-NO-PRIOR-U", initial, supplied))
            final = cases.state(kind=kind, amount=amount, cap=600)
            for field in ("exposure_ref", "cap_ref"):
                bad = cases.clone(final)
                bad["history"][1][field]["digest"] = "d" * 64
                q = cases.aggregate_request("D1V3-HISTORY-MISMATCH", [bad])
                before = cases.clone(q)
                with self.subTest(kind=kind, history_field=field):
                    self.rejected(q)
                    self.assertEqual(q, before)
        pending = cases.state(kind="EXPOSURE_RATE_PENDING", amount=600)
        too_large = cases.stage(pending["key"], "FINAL_PAYABLE", 601, lineage=pending["active"])
        self.rejected(cases.stage_request("D1V3-CAP-BOUND", pending, too_large), "UNSUPPORTED")
        # Coherent wholesale replacement cannot be authenticated by supplied-data D1.
        # This test promises internal history equality only, never global provenance.
