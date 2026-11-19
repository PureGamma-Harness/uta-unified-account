"""Public contract regressions through both independent V3 front doors.

No production DTO, clock, actor or financial authority is constructed here.
The original failing request is retained separately from the corrected stream.
"""
from copy import deepcopy
from hashlib import sha256
import json
import unittest

from funding_hold_target_adapter_v3 import decode_request, evaluate
from reference_funding_hold_d1_v3 import load_request, evaluate_request
import funding_hold_d1_reference_cases_v3 as cases


def wire(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("ascii")


def record():
    return {
        "action": {"scope": {"authority_id": "synthetic-authority",
            "authority_generation": "gen-1", "account_id": "synthetic-account",
            "usd_scale": 2, "settlement_asset": "USD"},
            "allocation_id": "allocation-0"},
        "policy": {"format": 1, "policy_id": "synthetic-wait-30s-q4",
            "clock_policy": "TRUSTED_UTC_PERSISTENT_HIGH_WATERMARK",
            "max_wait_us": 30000000, "min_query_interval_us": 5000000,
            "max_query_attempts": 4,
            "expiry_action": "DEFAULT_REVIEW_PRESERVE_DEBT_FREEZE_AND_OUTBOX"},
        "revision": 1, "started_us": 0, "deadline_us": 30000000,
        "observed_highwater_us": 0, "attempts": 1,
        "last_dispatch_us": 0, "default_review": False,
    }


def request(value, now, dispatch, case_id="WAIT-BOUNDARY"):
    return {"schema": 3, "case_id": case_id, "op": "wait_preview", "input": {
        "record": value, "now_us": now, "expected_revision": value["revision"],
        "expected_policy_digest": "5124f316d0767fa0354ead3466d522f0d740c8d6134b4608a98352efb0cfd662",
        "dispatch_query": dispatch}}


def response(q, status, value=None):
    return {"schema": 3, "case_id": q["case_id"], "status": status,
        "value": value, "diagnostic_code": {"OK": None, "REJECT": "REJECTED_INPUT_OR_PRECONDITION",
            "UNSUPPORTED": "UNSUPPORTED_OPERATION_OR_CAPABILITY"}[status],
        "activation_permission": False, "hash_wire": "CODE_CONTRACT_IMPLEMENTED_NOT_RUN"}


def projection(value, outcome="WAIT", counted=False):
    return {"record": value, "outcome": outcome, "query_counted": counted,
            "holds_unchanged": True, "activation_permission": False}


class FundingHoldContractBoundaryV3Tests(unittest.TestCase):
    def check_response(self, q, expected):
        raw = wire(q)
        for name, loader, evaluator in (("reference", load_request, evaluate_request),
                                         ("target", decode_request, evaluate)):
            with self.subTest(implementation=name):
                decoded = loader(raw)
                self.assertEqual(wire(decoded), raw)
                observed = evaluator(decoded)
                self.assertEqual(wire(observed), wire(expected))
                self.assertEqual(wire(decoded), raw, "evaluation mutated its request")
        self.assertEqual(wire(q), raw)

    def test_original_seed_0321_remains_a_rejected_dispatch_request(self):
        old = record()
        old["action"]["allocation_id"] = "allocation-1"
        old.update(started_us=100000000, deadline_us=130000000,
                   observed_highwater_us=100000000, last_dispatch_us=100000000)
        q = request(old, 104999999, True, "D1V3-SEED-0321")
        # Canonical request bytes from immutable source 7a4f41a6, before repair.
        self.assertEqual(sha256(wire(q)).hexdigest(),
                         "90e77f4246fd8c533cd1ca577f5e8b40dec95890482d0a1fb062ed35fe1e602f")
        self.check_response(q, response(q, "REJECT"))

    def test_dispatch_at_interval_minus_one_equal_and_plus_one(self):
        for now, status in ((4999999, "REJECT"), (5000000, "OK"), (5000001, "OK")):
            with self.subTest(now=now):
                old = record()
                q = request(old, now, True)
                if status == "REJECT":
                    expected = response(q, status)
                else:
                    new = deepcopy(old)
                    new.update(revision=2, observed_highwater_us=now,
                               attempts=2, last_dispatch_us=now)
                    expected = response(q, status, projection(new, counted=True))
                self.check_response(q, expected)

    def test_observation_before_interval_keeps_the_attempt_and_dispatch_time(self):
        for now in (0, 4999999):
            with self.subTest(now=now):
                old = record()
                new = deepcopy(old)
                if now:
                    new.update(revision=2, observed_highwater_us=4999999)
                q = request(old, now, False)
                self.check_response(q, response(q, "OK", projection(new)))

    def test_default_deadline_and_attempt_cap_precede_interval_rejection(self):
        for cause in ("sticky", "deadline", "attempt_cap"):
            with self.subTest(cause=cause):
                old = record()
                if cause == "sticky":
                    old["default_review"] = True
                    now = 1
                    new = deepcopy(old)
                    new.update(revision=2, observed_highwater_us=1)
                elif cause == "deadline":
                    old.update(observed_highwater_us=29999999, last_dispatch_us=29999999)
                    now = 30000000
                    new = deepcopy(old)
                    new.update(revision=2, observed_highwater_us=30000000, default_review=True)
                else:
                    old.update(revision=4, attempts=4,
                               observed_highwater_us=15000000, last_dispatch_us=15000000)
                    now = 15000001
                    new = deepcopy(old)
                    new.update(revision=5, observed_highwater_us=15000001, default_review=True)
                q = request(old, now, True)
                self.check_response(q, response(q, "OK", projection(new, "DEFAULT_REVIEW")))

    def test_stage_cap_and_final_limits_preserve_CAS_and_lineage_rejections(self):
        pending = cases.state(kind="EXPOSURE_RATE_PENDING", amount=600)
        too_large = cases.stage(pending["key"], "FINAL_PAYABLE", 601, lineage=pending["active"])
        q = cases.stage_request("CAP-UNSUPPORTED", pending, too_large)
        self.check_response(q, response(q, "UNSUPPORTED"))
        stale = deepcopy(q)
        stale["input"]["expected_revision"] = 0
        self.check_response(stale, response(stale, "REJECT"))
        bad_lineage = deepcopy(q)
        bad_lineage["input"]["proposed"]["exposure_ref"]["digest"] = "d" * 64
        self.check_response(bad_lineage, response(bad_lineage, "REJECT"))
        final = cases.state(kind="FINAL_PAYABLE", amount=246)
        q = cases.stage_request("FINAL-UNSUPPORTED", final,
                               cases.stage(final["key"], "FINAL_ZERO", 0))
        self.check_response(q, response(q, "UNSUPPORTED"))

    def test_collection_support_limits_do_not_accept_malformed_inputs(self):
        for defect in ("incomplete", "unassessed", "scale"):
            with self.subTest(defect=defect):
                q = cases.aggregate_request("COLLECTION-LIMIT", [cases.state()])
                if defect == "incomplete":
                    q["input"]["basis_complete"] = False
                elif defect == "unassessed":
                    q["input"]["states"] = [cases.state(kind="REGISTERED_UNASSESSED")]
                else:
                    q["input"]["states"][0]["usd_scale"] = 8
                self.check_response(q, response(q, "UNSUPPORTED"))
        q = cases.aggregate_request("MALFORMED-BASIS-FLAG", [cases.state()])
        q["input"]["basis_complete"] = 0
        self.check_response(q, response(q, "REJECT"))
        q = cases.aggregate_request("MALFORMED-SCALE", [cases.state()])
        q["input"]["states"][0]["usd_scale"] = 9
        self.check_response(q, response(q, "REJECT"))

    def test_included_base_is_unsupported_and_nontext_flag_is_rejected(self):
        for flag, status in (("INCLUDED", "UNSUPPORTED"), (True, "REJECT")):
            with self.subTest(flag=flag):
                b = cases.base()
                b["funding_components"] = flag
                q = cases.request("BASE-FUNDING-LIMIT", "decompose", {
                    "base": b, "states": [cases.state()], "basis_complete": True})
                self.check_response(q, response(q, status))

    def test_nonpayable_is_unsupported_and_missing_own_duty_is_rejected(self):
        q = cases.payment_request("PAYMENT-KIND-LIMIT", [cases.state(kind="FINAL_RECEIVABLE")])
        self.check_response(q, response(q, "UNSUPPORTED"))
        missing = deepcopy(q)
        missing["input"]["own_duty_id"] = "funding-duty:v1:" + "f" * 64
        self.check_response(missing, response(missing, "REJECT"))


if __name__ == "__main__":
    unittest.main()
