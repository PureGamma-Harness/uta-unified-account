"""Independent positive controls for a suspected, unconfirmed replay omission."""

import importlib.util
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("cash_deficit_a35_probe", ROOT / "scripts/probe_audit_cash_deficit_reference.py")
PROBE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PROBE)


class CashDeficitArchiveReferenceTests(unittest.TestCase):
    def test_pure_negative_cash_and_gross_debt_are_retained(self):
        result = PROBE.pure_probe()
        self.assertTrue(result["all_match"], result)
        no_debt, gross_debt = result["cases"]
        self.assertEqual([no_debt["actual_replay_state"][k] for k in ("risk_equity", "accounting_equity", "debt_value")], ["79", "99", "1"])
        self.assertEqual([gross_debt["actual_replay_state"][k] for k in ("risk_equity", "accounting_equity", "debt_value", "initial_margin", "maintenance_margin")], ["68", "88", "12", "2.2", "1.1"])

    def test_real_fee_reaches_negative_cash_and_both_audit_archives_replay(self):
        result = PROBE.service_probe()
        self.assertTrue(result["all_match"], result)
        self.assertTrue(result["temp_directory_cleaned"])
        self.assertEqual(result["opening_account"]["balances"]["USD"], "0")
        self.assertEqual(result["final_archival_state"]["balances"], {"USD": "-1", "BTC": "1"})
        self.assertEqual(result["final_archival_state"]["liabilities"], [{"asset": "BTC", "principal": "0.1", "interest": "0.01"}])
        self.assertEqual([d["kind"] for d in result["actual_decisions"]], ["ORDER_ACCEPTED", "FILL_CONFIRMED"])
        final = result["actual_final_service_risk"]
        self.assertEqual([final[k] for k in ("risk_equity", "accounting_equity", "debt_value", "cash_deficit_value", "initial_margin", "maintenance_margin", "available_margin")], ["68", "88", "12", "1", "12.2", "6.1", "55.8"])
        fill = result["actual_decisions"][1]
        self.assertEqual(fill["actual_archival_decision"]["summary"]["fee"], "1")
        self.assertTrue(fill["actual_full_replay"]["matches"])
        self.assertEqual(fill["actual_full_replay"]["differences"], {})


if __name__ == "__main__":
    unittest.main()
