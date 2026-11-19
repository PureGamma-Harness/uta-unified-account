"""Unrun wire/technical-failure contracts, independent of the Fraction oracle."""
from copy import deepcopy
import unittest
from unittest.mock import PropertyMock, patch

from funding_hold_target_adapter_v2 import (
    AdapterContractError, CONSTRUCTORS, DTO_FIELDS, WireReject, decode_request,
    evaluate, target, _validate_output,
)


def scope():
    return {"authority_id": "synthetic-authority", "authority_generation": "synthetic-generation",
            "account_id": "synthetic-payer", "usd_scale": 2, "settlement_asset": "USD"}


def request(op="aggregate", data=None):
    return {"schema": 2, "case_id": "ADAPTER-V2-SYNTHETIC", "op": op,
            "input": {"states": [], "scope": scope(), "basis_complete": True} if data is None else data}


class TargetFundingAdapterV2Tests(unittest.TestCase):
    def test_all_schema_branches_are_checked_before_value_selection(self):
        bad_branches = (
            {"type": "number"},
            {"type": ["null", "integer"]},
            {"type": "object", "properties": {"x": {"unknown_feature": True}},
             "required": ["x"], "additionalProperties": False},
            {"type": "array", "items": {"unknown_feature": True}},
            {"type": "object", "properties": {"x": {"type": "string"}},
             "required": "x", "additionalProperties": False},
            {"oneOf": []},
            {"type": "array", "items": {"type": "integer"}, "maxItems": True},
            {"enum": "x"},
        )
        for branch in bad_branches:
            with self.subTest(branch_keys=tuple(branch)), self.assertRaises(AdapterContractError):
                _validate_output({"oneOf": [{"type": "null"}, branch]}, None)

    def test_supported_alternatives_preserve_exact_native_integer_rules(self):
        schema = {"oneOf": [{"type": "null"}, {"type": "integer", "minimum": 0}]}
        self.assertIsNone(_validate_output(schema, None))
        self.assertIsNone(_validate_output(schema, 0))
        with self.assertRaises(AdapterContractError):
            _validate_output(schema, True)

    def test_action_ID_elements_have_wire_native_type_and_format(self):
        for identities in ((0,), (False,), ("not-an-action-id",)):
            with patch.object(target, "validate_wait_records", return_value=identities):
                with self.assertRaises(AdapterContractError):
                    evaluate(request("wait_records", {"records": []}))

    def test_query_counted_integer_zero_is_not_boolean_false(self):
        policy = target.WaitPolicy(1, "synthetic-policy", "TRUSTED_UTC_PERSISTENT_HIGH_WATERMARK",
            30000000, 5000000, 4, "DEFAULT_REVIEW_PRESERVE_DEBT_FREEZE_AND_OUTBOX")
        native = target.WaitRecord(target.ActionKey(target.Scope(**scope()), "synthetic-allocation"),
            policy, 0, 0, 30000000, 0, 0, None, False)
        data = {"record": {
            "action": {"scope": scope(), "allocation_id": "synthetic-allocation"},
            "policy": {"format": 1, "policy_id": "synthetic-policy",
                "clock_policy": "TRUSTED_UTC_PERSISTENT_HIGH_WATERMARK", "max_wait_us": 30000000,
                "min_query_interval_us": 5000000, "max_query_attempts": 4,
                "expiry_action": "DEFAULT_REVIEW_PRESERVE_DEBT_FREEZE_AND_OUTBOX"},
            "revision": 0, "started_us": 0, "deadline_us": 30000000, "observed_highwater_us": 0,
            "attempts": 0, "last_dispatch_us": None, "default_review": False},
            "now_us": 0, "expected_revision": 0, "expected_policy_digest": "0" * 64,
            "dispatch_query": False}
        with patch.object(target, "preview_wait", return_value=target.WaitProjection(native, "WAIT", 0)):
            with self.assertRaises(AdapterContractError):
                evaluate(request("wait_preview", data))

    def test_encoding_known_target_exception_is_not_business_rejection(self):
        with patch("funding_hold_target_adapter_v2._encode", side_effect=target.HoldError("synthetic encoder fault")):
            with self.assertRaises(target.HoldError):
                evaluate(request("wait_records", {"records": []}))
        data = {"policy": {"format": 1, "policy_id": "synthetic-policy",
            "clock_policy": "TRUSTED_UTC_PERSISTENT_HIGH_WATERMARK", "max_wait_us": 30000000,
            "min_query_interval_us": 5000000, "max_query_attempts": 4,
            "expiry_action": "DEFAULT_REVIEW_PRESERVE_DEBT_FREEZE_AND_OUTBOX"}}
        with patch("funding_hold_target_adapter_v2._encode", side_effect=target.HoldError("synthetic encoder fault")):
            with self.assertRaises(target.HoldError):
                evaluate(request("policy_identity", data))

    def test_invalid_intermediate_type_never_reaches_downstream_target(self):
        base = {"scope": scope(), "accounting_equity_units": 10000, "risk_equity_units": 10000,
                "initial_margin_units": 0, "maintenance_margin_units": 0, "order_reserve_units": 0,
                "cash_units": 10000, "spot_frozen_units": 0, "funding_components": "EXCLUDED"}
        with patch.object(target, "aggregate", return_value={}), patch.object(target, "decompose") as downstream:
            with self.assertRaises(AdapterContractError):
                evaluate(request("decompose", {"base": base, "states": [], "basis_complete": True}))
            downstream.assert_not_called()

    def test_intermediate_bad_field_or_downstream_rejection_is_technical(self):
        base = {"scope": scope(), "accounting_equity_units": 10000, "risk_equity_units": 10000,
                "initial_margin_units": 0, "maintenance_margin_units": 0, "order_reserve_units": 0,
                "cash_units": 10000, "spot_frozen_units": 0, "funding_components": "EXCLUDED"}
        data = request("decompose", {"base": base, "states": [], "basis_complete": True})
        corrupt = target.Totals(target.Scope(**scope()), (), 0, 0, 0, 0)
        object.__setattr__(corrupt, "P", True)
        with patch.object(target, "aggregate", return_value=corrupt), patch.object(target, "decompose") as downstream:
            with self.assertRaises(AdapterContractError):
                evaluate(data)
            downstream.assert_not_called()
        valid = target.Totals(target.Scope(**scope()), (), 0, 0, 0, 0)
        with patch.object(target, "aggregate", return_value=valid), patch.object(target, "decompose", side_effect=target.HoldError("synthetic downstream fault")):
            with self.assertRaises(AdapterContractError):
                evaluate(data)

    def test_native_natural_slot_is_not_coerced_from_another_iterable(self):
        key = {"authority_id": "synthetic-authority", "authority_generation": "synthetic-generation",
               "symbol": "SYNTH-USD-PERP", "period_end": "2026-01-01T00:00:00+00:00",
               "interval_seconds": 28800, "settlement_asset": "USD", "account_id": "synthetic-payer",
               "rule_scope_id": "synthetic-approved-funding-rules-v1", "schema": 1}
        for bad_slot in ("abcdef", ["a"] * 6, ("a",) * 5 + (0,)):
            with patch.object(target.DutyKey, "natural_slot", new_callable=PropertyMock, return_value=bad_slot):
                with self.assertRaises(AdapterContractError):
                    evaluate(request("duty_identity", {"key": key}))

    def test_unsupported_schema_cannot_be_hidden_by_another_oneof_branch(self):
        with self.assertRaisesRegex(AdapterContractError, "unsupported_output_schema"):
            _validate_output({"oneOf": [{"type": "null"}, {"unknown_feature": True}]}, None)

    def test_transport_never_fabricates_response_for_invalid_envelope(self):
        for change in ({"case_id": None}, {"schema": True}, {"op": "unknown"}, {"input": []}):
            item = request()
            item.update(change)
            with self.assertRaises(WireReject):
                evaluate(item)
        with self.assertRaises(WireReject):
            evaluate({**request(), "extra": False})

    def test_codec_rejects_duplicate_nonfinite_BOM_and_inferred_UTF16(self):
        values = (b'{"schema":2,"schema":2}', b'{"number":NaN}', b'{"number":1e999}',
                  b'\xef\xbb\xbf{}', '{}'.encode('utf-16'))
        for raw in values:
            with self.subTest(raw_length=len(raw)), self.assertRaises(WireReject):
                decode_request(raw)

    def test_known_input_rejection_retains_valid_case_identity(self):
        item = request(data={"states": [], "scope": scope()})
        result = evaluate(item)
        self.assertEqual((result["status"], result["case_id"], result["value"]),
                         ("REJECT", item["case_id"], None))
        self.assertEqual(result["diagnostic_code"], "REJECTED_INPUT_OR_PRECONDITION")

    def test_unexpected_target_and_constructor_exceptions_remain_technical(self):
        with patch.object(target, "aggregate", side_effect=TypeError("synthetic technical fault")):
            with self.assertRaisesRegex(TypeError, "synthetic technical fault"):
                evaluate(request())
        def unexpected(**_):
            raise ValueError("synthetic constructor fault")
        with patch.dict(CONSTRUCTORS, {"Scope": unexpected}):
            with self.assertRaisesRegex(ValueError, "synthetic constructor fault"):
                evaluate(request())
        class UnknownHoldError(target.HoldError):
            pass
        with patch.object(target, "aggregate", side_effect=UnknownHoldError("synthetic unknown type")):
            with self.assertRaises(UnknownHoldError):
                evaluate(request())

    def test_complete_DTO_output_and_original_request_are_preserved(self):
        item = request()
        before = deepcopy(item)
        result = evaluate(item)
        self.assertEqual(item, before)
        self.assertEqual(result["status"], "OK")
        self.assertEqual(set(result["value"]), set(DTO_FIELDS["Totals"]))
        self.assertEqual(result["value"]["duty_ids"], [])
        self.assertEqual(tuple(result["value"][name] for name in ("P", "U", "N", "H")), (0, 0, 0, 0))
        self.assertIs(result["value"]["activation_permission"], False)

    def test_validator_actual_return_order_is_not_sorted_or_replaced_by_adapter(self):
        ids = ("funding-action:v1:" + "b" * 64, "funding-action:v1:" + "a" * 64)
        with patch.object(target, "validate_wait_records", return_value=ids):
            result = evaluate(request("wait_records", {"records": []}))
        self.assertEqual(result["value"]["action_ids"], list(ids))
        self.assertEqual(result["value"]["record_count"], 0)

    def test_malformed_target_returns_are_technical_failures(self):
        with patch.object(target, "aggregate", return_value={}):
            with self.assertRaises(AdapterContractError):
                evaluate(request())
        with patch.object(target, "validate_wait_records", return_value=[]):
            with self.assertRaises(AdapterContractError):
                evaluate(request("wait_records", {"records": []}))
        with patch.object(target, "unsupported_request", return_value=None):
            with self.assertRaises(AdapterContractError):
                evaluate(request("unsupported", {"operation": "ledger"}))

    def test_finite_float_and_bool_are_not_coerced_into_valid_integer_inputs(self):
        for scale in (2.0, True):
            data = request()
            data["input"]["scope"]["usd_scale"] = scale
            self.assertEqual(evaluate(data)["status"], "REJECT")

    def test_legacy_single_reference_is_unsupported_without_inference(self):
        result = evaluate(request("stage_advance", {"expected_active_ref": None}))
        self.assertEqual((result["status"], result["diagnostic_code"], result["value"]),
                         ("UNSUPPORTED", "UNSUPPORTED_OPERATION_OR_CAPABILITY", None))


if __name__ == "__main__":
    unittest.main()
