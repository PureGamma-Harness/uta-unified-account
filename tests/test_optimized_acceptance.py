"""Synthetic acceptance must retain its checks when Python assertions are disabled."""
from pathlib import Path
import subprocess
import sys
import unittest


class OptimizedAcceptanceTests(unittest.TestCase):
    def test_cash_flow_negative_control_is_rejected_under_optimization(self):
        program = r'''
import sys
from decimal import Decimal
from unittest.mock import patch
from uta.acceptance import run_acceptance
from uta.service import ExchangeService
if sys.flags.optimize != 1:
    raise RuntimeError("expected python -O")
def check_success():
    result = run_acceptance()
    if result["status"] != "passed" or result["production_approved"] is not False:
        raise RuntimeError("synthetic acceptance result changed")
check_success()
original = ExchangeService.account
def wrong_balance(self, *args, **kwargs):
    result = dict(original(self, *args, **kwargs))
    result["balances"] = dict(result["balances"])
    result["balances"]["USD"] = str(Decimal(result["balances"]["USD"]) + 1)
    return result
with patch.object(ExchangeService, "account", wrong_balance):
    try:
        run_acceptance()
    except RuntimeError as error:
        if str(error) != "acceptance failed: independent round-trip cash flow":
            raise
    else:
        raise RuntimeError("incorrect balance escaped acceptance checks under -O")
check_success()
print("optimized acceptance negative control detected and restored")
'''
        result = subprocess.run([sys.executable, '-O', '-c', program],
                                cwd=Path(__file__).resolve().parents[1],
                                capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('optimized acceptance negative control detected and restored', result.stdout)
