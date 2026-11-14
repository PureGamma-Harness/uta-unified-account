import json
import unittest
from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal, localcontext

from uta.migration import MigrationError, build_shadow
from uta.models import AssetSpec, InstrumentSpec
from uta.shadow_adapter import convert_shadow


NOW = datetime(2026, 11, 14, tzinfo=timezone.utc)
ASSETS = {"BTC": AssetSpec(Decimal("60000"), Decimal("0.8"))}
INSTRUMENTS = {
    "BTC-PERP": InstrumentSpec(Decimal("60000"), Decimal("0.10"), Decimal("0.06")),
}


def classic_snapshot():
    return {
        "account_id": "classic-account",
        "version": 7,
        "captured_at": NOW.isoformat(),
        "compartments": {
            "spot": {"balances": [
                {"asset": "BTC", "free": "0.123456", "locked": "0", "borrowed": "0",
                 "interest": "0"},
            ]},
            "margin": {"balances": [
                {"asset": "BTC", "free": "0.100001", "locked": "0", "borrowed": "0.14",
                 "interest": "0.000001"},
            ]},
            "futures": {"balances": [], "positions": [
                {"symbol": "BTC-PERP", "quantity": "-0.2000000000", "entry_price": "6e4"},
            ]},
        },
    }


class ShadowAdapterTests(unittest.TestCase):
    def test_exact_gross_projection_and_source_reference(self):
        shadow = build_shadow(classic_snapshot(), now=NOW)
        with localcontext() as context:
            context.prec = 2
            state = convert_shadow(shadow, asset_config=ASSETS, instruments=INSTRUMENTS)
        self.assertEqual(state["balances"], {"BTC": "0.223457"})
        self.assertEqual(state["liabilities"], {"BTC": "0.140001"})
        self.assertEqual(state["positions"], {
            "BTC-PERP": {"quantity": "-0.2", "entry_price": "60000"},
        })
        self.assertEqual(state["orders"], {})
        self.assertEqual(state["source"], {
            "account_id": "classic-account", "version": 7, "digest": shadow.source_digest,
        })
        self.assertEqual(state["as_of"], NOW.isoformat())
        self.assertEqual(state["prices"], {"BTC": "60000"})
        self.assertEqual(state["marks"], {"BTC-PERP": "60000"})
        self.assertEqual(state["asset_factors"], {"BTC": "0.8"})
        self.assertEqual(state["instruments"]["BTC-PERP"], {
            "initial_margin_rate": "0.10", "maintenance_margin_rate": "0.06",
        })
        self.assertEqual(json.loads(json.dumps(state)), state)

    def test_locked_balance_fails_without_order_reconciliation(self):
        raw = classic_snapshot()
        raw["compartments"]["spot"]["balances"][0]["locked"] = "0.1"
        with self.assertRaisesRegex(MigrationError, "unreconciled locked balance"):
            convert_shadow(build_shadow(raw, now=NOW), asset_config=ASSETS, instruments=INSTRUMENTS)

    def test_unmapped_assets_and_instruments_reject(self):
        shadow = build_shadow(classic_snapshot(), now=NOW)
        with self.assertRaisesRegex(MigrationError, "unsupported classic asset"):
            convert_shadow(shadow, asset_config={}, instruments=INSTRUMENTS)
        with self.assertRaisesRegex(MigrationError, "unsupported classic instrument"):
            convert_shadow(shadow, asset_config=ASSETS, instruments={})

    def test_multiple_positions_never_net(self):
        shadow = build_shadow(classic_snapshot(), now=NOW)
        first = shadow.positions[0]
        second = replace(first, quantity=-first.quantity)
        with self.assertRaisesRegex(MigrationError, "multiple classic positions"):
            convert_shadow(replace(shadow, positions=(first, second)),
                           asset_config=ASSETS, instruments=INSTRUMENTS)
