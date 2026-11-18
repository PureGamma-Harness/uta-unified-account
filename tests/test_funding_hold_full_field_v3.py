"""Unrun complete-response differential gate over independent synthetic V3 data.

This driver knows the wire contract and declared case metadata. It contains no
financial equations, expected money values, DTO builder or rounding helper.
"""
from collections import Counter
import hashlib
import json
import math
import unittest
from unittest.mock import patch

from funding_hold_d1_reference_cases_v3 import iter_cases
from reference_funding_hold_d1_v3 import evaluate_request, load_request
from funding_hold_target_adapter_v3 import decode_request, evaluate


CASE_KEYS = {"seed", "family", "partition", "expected_status", "request", "hash_wire", "activation_permission"}
RESPONSE_KEYS = {"schema", "case_id", "status", "value", "diagnostic_code", "activation_permission", "hash_wire"}
STATUSES = {"OK", "REJECT", "UNSUPPORTED"}
OPERATIONS = {"duty_identity", "policy_identity", "action_identity", "stage_advance",
              "aggregate", "decompose", "payment_precondition", "wait_preview",
              "wait_records", "unsupported"}
CONTRACT_TAG = "CODE_CONTRACT_IMPLEMENTED_NOT_RUN"


class DifferentialTechnicalFailure(RuntimeError):
    """An implementation/transport failure, never a matching business reject."""


class DifferentialContractFailure(RuntimeError):
    """Malformed stream, incomplete response or misclassified declared case."""


def _native_tree(value, *, floats, depth=0, ancestors=None, work=None):
    if ancestors is None:
        ancestors, work = set(), [0]
    work[0] += 1
    if depth > 32 or work[0] > 250000:
        raise DifferentialContractFailure("bounded native wire tree required")
    kind = type(value)
    if value is None or kind in (str, int, bool):
        return
    if kind is float and floats and math.isfinite(value):
        return  # Input negatives may contain finite floats; outputs may not.
    if kind not in (list, dict) or id(value) in ancestors:
        raise DifferentialContractFailure("non-native or cyclic wire value")
    ancestors.add(id(value))
    if kind is dict:
        if any(type(key) is not str for key in value):
            raise DifferentialContractFailure("native string object keys required")
        for key, child in value.items():
            _native_tree(key, floats=floats, depth=depth + 1, ancestors=ancestors, work=work)
            _native_tree(child, floats=floats, depth=depth + 1, ancestors=ancestors, work=work)
    else:
        for child in value:
            _native_tree(child, floats=floats, depth=depth + 1, ancestors=ancestors, work=work)
    ancestors.remove(id(value))


def _canonical(value, *, floats=False):
    _native_tree(value, floats=floats)
    raw = json.dumps(value, sort_keys=True, ensure_ascii=True,
                     separators=(",", ":"), allow_nan=False).encode("ascii")
    if len(raw) > 2 * 1024 * 1024:
        raise DifferentialContractFailure("wire value exceeds the declared byte bound")
    return raw


def _technical_call(label, function, argument):
    try:
        return function(argument)
    except Exception as error:
        # In particular, a known implementation exception escaping evaluate is
        # still technical here; only a returned valid response is business data.
        raise DifferentialTechnicalFailure(label + ":" + type(error).__name__) from error


def _response(value, case_id):
    if type(value) is not dict or any(type(k) is not str for k in value) or set(value) != RESPONSE_KEYS:
        raise DifferentialContractFailure("complete response fields required")
    if type(value["schema"]) is not int or value["schema"] != 3 or value["case_id"] != case_id:
        raise DifferentialContractFailure("response correlation/version mismatch")
    if type(value["case_id"]) is not str or type(value["status"]) is not str or value["status"] not in STATUSES:
        raise DifferentialContractFailure("known native response status required")
    if value["activation_permission"] is not False or value["hash_wire"] != CONTRACT_TAG:
        raise DifferentialContractFailure("response fixed flags/contract tag mismatch")
    expected_code = {"OK": None, "REJECT": "REJECTED_INPUT_OR_PRECONDITION",
                     "UNSUPPORTED": "UNSUPPORTED_OPERATION_OR_CAPABILITY"}[value["status"]]
    if type(value["diagnostic_code"]) is not type(expected_code) or value["diagnostic_code"] != expected_code:
        raise DifferentialContractFailure("response diagnostic contract mismatch")
    if value["status"] != "OK" and value["value"] is not None:
        raise DifferentialContractFailure("business rejection must not contain a value")
    return _canonical(value)


def _declared_status(expected, reference, actual, context=""):
    if expected not in STATUSES or reference["status"] != expected or actual["status"] != expected:
        raise DifferentialContractFailure("actual status violates independent declared case classification " + context
            + " declared=" + str(expected) + " reference=" + reference["status"] + " target=" + actual["status"])


def _first_difference(left, right, path="$", depth=0):
    if type(left) is not type(right):
        return {"path": path[:512], "kind": "NATIVE_TYPE", "reference_type": type(left).__name__,
                "target_type": type(right).__name__}
    if type(left) is dict:
        if set(left) != set(right):
            return {"path": path[:512], "kind": "OBJECT_FIELDS"}
        for key in sorted(left):
            difference = _first_difference(left[key], right[key], path + "/" + key[:128], depth + 1)
            if difference is not None:
                return difference
    elif type(left) is list:
        if len(left) != len(right):
            return {"path": path[:512], "kind": "ARRAY_LENGTH", "reference_length": len(left), "target_length": len(right)}
        for index, (a, b) in enumerate(zip(left, right)):
            difference = _first_difference(a, b, path + "/" + str(index), depth + 1)
            if difference is not None:
                return difference
    elif left != right:
        return {"path": path[:512], "kind": "VALUE"}
    return None


def _frame(digest, raw):
    digest.update(len(raw).to_bytes(8, "big"))
    digest.update(raw)


def _ordered_cases():
    iterator = _technical_call("generator.iter_cases", lambda _: iter(iter_cases()), None)
    for seed in range(1024):
        yield seed, _technical_call("generator.next seed=" + str(seed), next, iterator)
    try:
        next(iterator)
    except StopIteration:
        return
    except Exception as error:
        raise DifferentialTechnicalFailure("generator exhaustion after seed=1023:" + type(error).__name__) from error
    raise DifferentialContractFailure("generator emitted more than1024 cases")


class FundingHoldFullFieldV3Tests(unittest.TestCase):
    def test_full_declared_stream_matches_complete_typed_responses(self):
        seen, operations = set(), set()
        families, partitions, declared, reference_counts, target_counts = (Counter() for _ in range(5))
        request_digest, reference_digest, target_digest = (hashlib.sha256() for _ in range(3))
        completed = 0
        for ordinal, item in _ordered_cases():
            if (type(item) is not dict or any(type(k) is not str for k in item) or set(item) != CASE_KEYS
                    or type(item["seed"]) is not int or item["seed"] != ordinal or ordinal >= 1024
                    or type(item["family"]) is not str or item["partition"] not in ("valid", "negative")
                    or type(item["expected_status"]) is not str or item["expected_status"] not in STATUSES
                    or item["hash_wire"] != CONTRACT_TAG or item["activation_permission"] is not False):
                raise DifferentialContractFailure("complete ordered independent case stream required seed=" + str(ordinal))
            if (item["partition"] == "valid") != (item["expected_status"] == "OK"):
                raise DifferentialContractFailure("declared valid/negative classification is inconsistent seed=" + str(ordinal))
            request = item["request"]
            raw = _technical_call("stream.encode seed=" + str(ordinal), lambda value: _canonical(value, floats=True), request)
            if (type(request) is not dict or set(request) != {"schema", "case_id", "op", "input"}
                    or type(request["schema"]) is not int or request["schema"] != 3
                    or type(request["case_id"]) is not str or request["case_id"] in seen
                    or type(request["op"]) is not str or request["op"] not in OPERATIONS):
                raise DifferentialContractFailure("unique complete version-three request required seed=" + str(ordinal))
            case_id = request["case_id"]
            context = json.dumps({"seed": ordinal, "case_id_prefix": case_id[:128],
                                  "case_id_sha256": hashlib.sha256(case_id.encode("utf-8")).hexdigest()}, sort_keys=True)
            seen.add(case_id)
            operations.add(request["op"])
            reference_request = _technical_call("reference.load_request " + context, load_request, raw)
            target_request = _technical_call("target.decode_request " + context, decode_request, raw)
            reference_before = _technical_call("reference.before " + context, lambda value: _canonical(value, floats=True), reference_request)
            target_before = _technical_call("target.before " + context, lambda value: _canonical(value, floats=True), target_request)
            self.assertEqual(reference_before, raw, "reference loader changed canonical request " + context)
            self.assertEqual(target_before, raw, "target loader changed canonical request " + context)
            reference = _technical_call("reference.evaluate_request " + context, evaluate_request, reference_request)
            actual = _technical_call("target.evaluate " + context, evaluate, target_request)
            reference_raw = _technical_call("reference.response " + context, lambda value: _response(value, case_id), reference)
            target_raw = _technical_call("target.response " + context, lambda value: _response(value, case_id), actual)
            reference_counts[reference["status"]] += 1
            target_counts[actual["status"]] += 1
            _declared_status(item["expected_status"], reference, actual, context)
            if reference_raw != target_raw:
                self.fail(json.dumps({"scope": "FUNDING_HOLD_V3_FULL_FIELD", "seed": ordinal,
                    "case_id": case_id, "family": item["family"], "operation": request["op"],
                    "completed_before_failure": completed, "request_sha256": hashlib.sha256(raw).hexdigest(),
                    "reference_response_sha256": hashlib.sha256(reference_raw).hexdigest(),
                    "target_response_sha256": hashlib.sha256(target_raw).hexdigest(),
                    "first_difference": _first_difference(reference, actual),
                    "reference_observed": dict(reference_counts), "target_observed": dict(target_counts)}, sort_keys=True))
            reference_after = _technical_call("reference.after " + context, lambda value: _canonical(value, floats=True), reference_request)
            target_after = _technical_call("target.after " + context, lambda value: _canonical(value, floats=True), target_request)
            self.assertEqual(reference_after, reference_before, "reference mutated request " + context)
            self.assertEqual(target_after, target_before, "target mutated request " + context)
            families[item["family"]] += 1
            partitions[item["partition"]] += 1
            declared[item["expected_status"]] += 1
            for digest, payload in ((request_digest, raw), (reference_digest, reference_raw), (target_digest, target_raw)):
                _frame(digest, payload)
            completed += 1
        self.assertEqual(completed, 1024)
        self.assertEqual(len(seen), 1024)
        self.assertEqual(operations, OPERATIONS)
        self.assertEqual(partitions, {"valid": 512, "negative": 512})
        print("FUNDING_HOLD_V3_FULL_FIELD " + json.dumps({"schema": 1, "completed": completed,
            "unique_cases": len(seen), "operations": sorted(operations), "families": dict(sorted(families.items())),
            "partitions": dict(partitions), "declared_statuses": dict(declared),
            "reference_observed": dict(reference_counts), "target_observed": dict(target_counts),
            "request_stream_sha256": request_digest.hexdigest(), "reference_response_stream_sha256": reference_digest.hexdigest(),
            "target_response_stream_sha256": target_digest.hexdigest(), "activation_permission": False,
            "capacity_claim": False, "D2": "BLOCKED"}, sort_keys=True))

    def test_comparison_preserves_native_types_array_order_and_all_fields(self):
        self.assertNotEqual(_canonical({"v": False}), _canonical({"v": 0}))
        self.assertNotEqual(_canonical({"v": ["a", "b"]}), _canonical({"v": ["b", "a"]}))
        self.assertNotEqual(_canonical({"v": 0}), _canonical({"v": 0, "extra": None}))
        self.assertEqual(_canonical({"a": 1, "b": False}), _canonical({"b": False, "a": 1}))

    def test_escaped_implementation_exception_is_technical(self):
        class SyntheticInternalFailure(ValueError):
            pass
        def broken(_):
            raise SyntheticInternalFailure("synthetic internal fault")
        with self.assertRaises(DifferentialTechnicalFailure) as captured:
            _technical_call("synthetic.evaluate", broken, {})
        self.assertIs(type(captured.exception.__cause__), SyntheticInternalFailure)

    def test_matching_rejection_cannot_pass_a_declared_valid_case(self):
        with self.assertRaises(DifferentialContractFailure):
            _declared_status("OK", {"status": "REJECT"}, {"status": "REJECT"})

    def test_missing_stream_case_is_technical_with_seed_context(self):
        with patch(__name__ + ".iter_cases", return_value=iter(())):
            with self.assertRaises(DifferentialTechnicalFailure) as captured:
                next(_ordered_cases())
        self.assertIn("seed=0", str(captured.exception))


if __name__ == "__main__":
    unittest.main()
