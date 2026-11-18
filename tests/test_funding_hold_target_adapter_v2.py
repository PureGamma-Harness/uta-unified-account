"""Unrun wire/technical-failure contracts, independent of the Fraction oracle."""
from copy import deepcopy
import unittest
from unittest.mock import patch

from funding_hold_target_adapter_v2 import (
    AdapterContractError, CONSTRUCTORS, DTO_FIELDS, WireReject, decode_request,
    evaluate, target,
)


def scope():
    return {"authority_id": "synthetic-authority", "authority_generation": "synthetic-generation",
            "account_id": "synthetic-payer", "usd_scale": 2, "settlement_asset": "USD"}


def request(op="aggregate", data=None):
    return {"schema": 2, "case_id": "ADAPTER-V2-SYNTHETIC", "op": op,
            "input": {"states": [], "scope": scope(), "basis_complete": True} if data is None else data}


class TargetFundingAdapterV2Tests(unittest.TestCase):
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
