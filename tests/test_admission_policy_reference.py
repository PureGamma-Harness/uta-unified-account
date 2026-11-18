"""Hand-computed synthetic admission predicates; no service or database use."""
from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal as D, Inexact, Rounded, localcontext
from fractions import Fraction
import unittest

from uta.decision_audit import ADMISSION_CONTRACT, DecisionAudit
from uta.market import MarketSnapshot
from uta.models import AssetSpec, InstrumentSpec


NOW = datetime(2026, 11, 18, 9, tzinfo=timezone.utc)


def risk(equity, im, mm, reserve, available):
    return dict(zip(("equity", "initial_margin", "maintenance_margin",
                     "open_order_margin", "available_margin"),
                    (equity, im, mm, reserve, available)))


def example(*, cash="100", mm=".05", quantity="1", price="100", positions=None,
            orders=None, before_values=None, after_values=None, projected_values=None,
            pnl="0", fee="0.04", reserved="10.04", reduce_only=False):
    before = {"version": 3, "balances": {"USD": cash}, "frozen_assets": {},
              "positions": positions or {}, "liabilities": [], "orders": orders or [],
              "halted": False, "liquidation_state": None}
    after = deepcopy(before)
    after["version"] = 4
    request = {"order_id": "new", "symbol": "X", "quantity": quantity,
               "limit_price": price, "reduce_only": reduce_only}
    after["orders"].append(dict(request, account_id="a", reduce_only=int(reduce_only),
        filled_quantity="0", status="OPEN", version=4, fee_notional="0", charged_fee="0",
        admission_decision_id="decision:manual"))
    projected = projected_values or risk("99.96", "10", "5", "0", "89.96")
    projected = dict(projected, account_version=3, market_version=7,
                     observed_at=NOW.isoformat(), risk_mode="legacy_reference")
    record = {"decision_id": "decision:manual", "kind": "ORDER_ACCEPTED",
              "account_id": "a", "business_id": "new",
              "inputs": {"before": before, "after": after, "operation": request},
              "summary": {"risk_before": before_values or risk("100", "0", "0", "0", "100"),
                          "risk_after": after_values or risk("100", "0", "0", "10.04", "89.96"),
                          "reserved_margin": reserved, "projected_execution": projected,
                          "admission": {"format": 1, "contract": ADMISSION_CONTRACT,
                                        "projected_realized_pnl": pnl, "projected_fee": fee}}}
    policy = {"admission_contract": ADMISSION_CONTRACT, "catalog": None, "rules": None,
              "risk_mode": "legacy_reference", "scales": {"USD": 2}, "fee_rate": "0.0004"}
    market = MarketSnapshot(7, NOW, {"USD": AssetSpec(D(1), D(1))},
                            {"X": InstrumentSpec(D(100), D(".1"), D(mm))})
    return record, market, policy


def verify(fixture):
    record, market, policy = fixture
    values = {side: DecisionAudit._replay_state(record["inputs"][side], market, policy)
              for side in ("before", "after")}
    return DecisionAudit._replay_admission(record, market, policy, values,
        {"reserved_margin": record["summary"]["reserved_margin"]})


class AdmissionPolicyReferenceTests(unittest.TestCase):
    def test_manual_strict_mm_and_legal_im_equality(self):
        for mm, expected in ((".1", False), (".05", True)):
            with self.subTest(mm=mm), localcontext() as context:
                context.prec = 2
                context.traps[Inexact] = context.traps[Rounded] = True
                fixture = example(cash="10.04", mm=mm,
                    before_values=risk("10.04", "0", "0", "0", "10.04"),
                    after_values=risk("10.04", "0", "0", "10.04", "0"),
                    projected_values=risk("10", "10", "10" if mm == ".1" else "5", "0", "0"))
                result = verify(fixture)
                self.assertEqual(result["eligible"], expected)
                self.assertEqual(result["status"], "VERIFIED" if expected else "FAILED")
                self.assertEqual(result["checks"]["strict_maintenance_surplus"], expected)

    def test_full_fee_and_existing_live_order_reserves(self):
        insufficient = example(cash="10.03", before_values=risk("10.03", "0", "0", "0", "10.03"),
            after_values=risk("10.03", "0", "0", "10.04", "-0.01"),
            projected_values=risk("9.99", "10", "5", "0", "-0.01"))
        self.assertFalse(verify(insufficient)["checks"]["initial_margin_reservation"])
        old = {"order_id": "old", "symbol": "X", "quantity": "1", "filled_quantity": "0",
               "limit_price": "100", "reduce_only": 0, "fee_notional": "0", "charged_fee": "0"}
        fixture = example(cash="20.08", orders=[old],
            before_values=risk("20.08", "0", "0", "10.04", "10.04"),
            after_values=risk("20.08", "0", "0", "20.08", "0"),
            projected_values=risk("20.04", "10", "5", "10.04", "0"))
        self.assertTrue(verify(fixture)["matches"])
        fixture[0]["inputs"]["after"]["orders"][0]["quantity"] = "2"
        self.assertFalse(verify(fixture)["checks"]["prior_live_orders_unchanged"])

    def test_reduce_only_allocation_and_surplus_are_separate(self):
        fixture = example(cash="4", quantity="-1", positions={"X": {"quantity": "1", "cost_basis": "100"}},
            reduce_only=True, reserved="0.04", before_values=risk("4", "10", "5", "0", "-6"),
            after_values=risk("4", "10", "5", "0.04", "-6.04"),
            projected_values=risk("3.96", "0", "0", "0", "3.96"))
        fixture[0]["inputs"]["before"]["halted"] = True
        fixture[0]["inputs"]["after"]["halted"] = True
        self.assertTrue(verify(fixture)["matches"])
        held = {"order_id": "held", "symbol": "X", "quantity": "-.5", "filled_quantity": "0",
                "limit_price": "100", "reduce_only": 1, "fee_notional": "0", "charged_fee": "0"}
        overlap = example(cash="4", quantity="-1", positions={"X": {"quantity": "1", "cost_basis": "100"}},
            orders=[held], reduce_only=True, reserved="0.04",
            before_values=risk("4", "10", "5", "0.02", "-6.02"),
            after_values=risk("4", "10", "5", "0.06", "-6.06"),
            projected_values=risk("3.96", "0", "0", "0.02", "3.94"))
        self.assertFalse(verify(overlap)["checks"]["reduce_only_quantity"])
        worse = example(cash="4", quantity="-.5", price="90", positions={"X": {"quantity": "1", "cost_basis": "100"}},
            reduce_only=True, reserved="5.02", pnl="-5", fee="0.02",
            before_values=risk("4", "10", "5", "0", "-6"),
            after_values=risk("4", "10", "5", "5.02", "-11.02"),
            projected_values=risk("-1.02", "5", "2.5", "0", "-6.02"))
        self.assertFalse(verify(worse)["checks"]["reduce_only_surplus"])

    def test_settlement_dust_flip_and_short_close_manual_values(self):
        cases = (
            (".3", ".003", "-.2", ".009", ".1", "-.0088", "-.01", ".01", "99.98"),
            ("1", "100", "-2", "90", "-1", "-90", "-10", ".08", "89.92"),
            ("-1", "-100", ".5", "90", "-.5", "-50", "5", ".02", "104.98"),
        )
        for old, basis, quantity, price, remaining, cost, pnl, fee, cash in cases:
            with self.subTest(quantity=quantity, price=price), localcontext() as context:
                context.prec = 2
                context.traps[Inexact] = context.traps[Rounded] = True
                fixture = example(quantity=quantity, price=price,
                    positions={"X": {"quantity": old, "cost_basis": basis}})
                state, actual_pnl, actual_fee = DecisionAudit._admission_projection(
                    fixture[0]["inputs"]["before"], fixture[0]["inputs"]["operation"], fixture[2])
                self.assertEqual(Fraction(D(state["positions"]["X"]["quantity"])), Fraction(D(remaining)))
                self.assertEqual(Fraction(D(state["positions"]["X"]["cost_basis"])), Fraction(D(cost)))
                self.assertEqual((actual_pnl, actual_fee), (Fraction(D(pnl)), Fraction(D(fee))))
                self.assertEqual(Fraction(D(state["balances"]["USD"])), Fraction(D(cash)))

    def test_reduce_only_requires_native_boolean_halt_state(self):
        fixture = example(cash="4", quantity="-1", positions={"X": {"quantity": "1", "cost_basis": "100"}},
            reduce_only=True, reserved="0.04", before_values=risk("4", "10", "5", "0", "-6"),
            after_values=risk("4", "10", "5", "0.04", "-6.04"),
            projected_values=risk("3.96", "0", "0", "0", "3.96"))
        for halted in (False, True):
            candidate = (deepcopy(fixture[0]), fixture[1], fixture[2])
            for side in ("before", "after"):
                candidate[0]["inputs"][side]["halted"] = halted
            self.assertTrue(verify(candidate)["matches"])
        for halted in (None, "unknown", 0, 1, [], {}):
            with self.subTest(halted=halted):
                candidate = (deepcopy(fixture[0]), fixture[1], fixture[2])
                for side in ("before", "after"):
                    candidate[0]["inputs"][side]["halted"] = halted
                result = verify(candidate)
                self.assertEqual((result["status"], result["eligible"], result["matches"]),
                                 ("FAILED", False, False))
                self.assertFalse(result["checks"]["control_state_valid"])

    def test_missing_legacy_and_unknown_contract_never_verify(self):
        for mutation, reason in ((lambda row: row["summary"].pop("admission"), "historical_admission_evidence_missing"),
                                (lambda row: row.update(kind="FILL_CONFIRMED"), "decision_kind_not_supported"),
                                (lambda row: row["summary"]["admission"].update(contract="unknown-contract"), "admission_contract_not_supported"),
                                (lambda row: row["summary"]["admission"].update(format=True), "admission_contract_not_supported")):
            fixture = example()
            mutation(fixture[0])
            result = verify(fixture)
            self.assertEqual((result["status"], result["eligible"], result["matches"], result["reason"]),
                             ("UNSUPPORTED", None, None, reason))
        for contract in (None, "unknown-contract"):
            fixture = example()
            if contract is None:
                fixture[2].pop("admission_contract")
            else:
                fixture[2]["admission_contract"] = contract
            result = verify(fixture)
            self.assertEqual((result["status"], result["eligible"], result["matches"]),
                             ("UNSUPPORTED", None, None))

    def test_projection_fee_versions_and_control_tampering_fail(self):
        changes = (
            lambda row: row["summary"]["projected_execution"].update(equity="100"),
            lambda row: row["summary"]["admission"].update(projected_fee="0"),
            lambda row: row["summary"]["projected_execution"].update(market_version=8),
            lambda row: row["inputs"]["after"].update(version=5),
            lambda row: row["inputs"]["after"]["balances"].update(USD="101"),
            lambda row: row["inputs"]["before"].update(halted=True),
            lambda row: row["summary"]["risk_before"].update(available_margin="0"),
        )
        for change in changes:
            fixture = example()
            change(fixture[0])
            self.assertFalse(verify(fixture)["matches"])


if __name__ == "__main__":
    unittest.main()
