"""Pure regression contracts for distinct order and credit policy envelopes."""
from copy import deepcopy
from datetime import timedelta
from decimal import Decimal as D
import json
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from uta.credit_audit_v2 import CreditAuditError, audit_policy
from uta.credit_v2_payload_contract import BASE_POLICY_FIELDS
from uta.decision_audit import ADMISSION_CONTRACT, DecisionAudit
from uta.examples import synthetic_policy


def fixture():
    catalog, rules = synthetic_policy()
    exchange = SimpleNamespace(product_catalog=catalog, portfolio_rules=rules,
        scales={"USD": 8, "BTC": 8}, fee_rate=D(0), max_price_age=timedelta(seconds=5),
        _reserve_kernel=SimpleNamespace(capacity=0), _market_decode_cache=SimpleNamespace(capacity=0))
    # Independent statement of the already published credit-v2 wire fields;
    # no production policy function supplies this expected dictionary.
    base = dict(format=1, risk_mode="phase1_cross", catalog=json.loads(catalog.to_json()),
        rules=json.loads(rules.to_json()), scales={"USD": 8, "BTC": 8}, fee_rate="0",
        max_price_age_us=5000000, order_precision=8,
        reserve_formula="linear-adverse-loss-cumulative-fee-v1",
        execution_options=dict(reserve_cache_size=0, market_cache_size=0))
    stored = dict(format=2, base_policy=base, max_future_skew_us=1000000,
        clock_policy="actual exchange UTC checkpoints; no physical commit timestamp",
        physical_commit_time_captured=False)
    return exchange, base, stored


class AdmissionCreditPolicyContracts(unittest.TestCase):
    def test_valuation_fields_preserve_the_exact_credit_wire_contract(self):
        exchange, expected, _ = fixture()
        actual = DecisionAudit.valuation_policy(exchange)
        self.assertEqual(set(actual), BASE_POLICY_FIELDS)
        self.assertEqual(actual, expected)
        self.assertNotIn("admission_contract", actual)

    def test_order_envelope_preserves_admission_and_copies_runtime_values(self):
        exchange, expected, _ = fixture()
        actual = DecisionAudit.policy(exchange)
        self.assertEqual(actual.pop("admission_contract"), ADMISSION_CONTRACT)
        self.assertEqual(actual, expected)
        actual["scales"]["USD"] = 2
        self.assertEqual(DecisionAudit.valuation_policy(exchange), expected)

    def test_credit_policy_does_not_consume_the_order_admission_envelope(self):
        exchange, _, stored = fixture()
        with patch.object(DecisionAudit, "policy", side_effect=AssertionError("order envelope used for credit")), \
                patch("uta.credit_audit_v2._persisted_policy", return_value=stored) as read:
            self.assertIs(audit_policy(exchange, None), stored)
        read.assert_called_once_with(None)

    def test_exact_credit_comparison_rejects_changed_and_unknown_valuation_fields(self):
        exchange, base, stored = fixture()
        changed = deepcopy(base)
        changed["order_precision"] = 7
        unknown = deepcopy(base)
        unknown["unknown_valuation_rule"] = "unreviewed"
        for candidate in (changed, unknown):
            with self.subTest(candidate=candidate), \
                    patch.object(DecisionAudit, "valuation_policy", return_value=candidate), \
                    patch("uta.credit_audit_v2._persisted_policy", return_value=stored):
                with self.assertRaises(CreditAuditError) as rejected:
                    audit_policy(exchange, None)
                self.assertEqual(rejected.exception.code, "credit_audit_policy_mismatch")


if __name__ == "__main__":
    unittest.main()
