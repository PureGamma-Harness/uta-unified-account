"""Default readiness is unchanged; actual V2 denial is in the runtime chain."""
from datetime import datetime, timezone
from decimal import Decimal as D
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from uta.market import MarketSnapshot
from uta.models import AssetSpec, InstrumentSpec
from uta.service import ExchangeService
from uta.storage import Database


class CreditV2ReadinessBoundaryTests(unittest.TestCase):
    def test_default_no_credit_cap_keeps_original_ready_and_halt_result(self):
        with TemporaryDirectory(prefix="credit-v2-default-readiness-") as directory:
            now = datetime(2026, 11, 17, tzinfo=timezone.utc)
            database = Database(Path(directory)/"synthetic.sqlite3")
            exchange = ExchangeService(database, {"USD": 8, "BTC": 8}, clock=lambda: now)
            exchange.publish_market(MarketSnapshot(1, now,
                {"USD": AssetSpec(D(1), D(1)), "BTC": AssetSpec(D(100), D(".8"))},
                {"BTC-PERP": InstrumentSpec(D(100), D(".1"), D(".05"))}))
            exchange.set_kill_switch(False)
            self.assertEqual(exchange.readiness(), {"ready": True, "halted": False, "market_version": 1,
                "reason": "ready", "risk_mode": "legacy_reference"})
            exchange.set_kill_switch(True)
            self.assertEqual(exchange.readiness(), {"ready": False, "halted": True, "market_version": 1,
                "reason": "trading_halted", "risk_mode": "legacy_reference"})
            with database.read_transaction() as connection:
                self.assertIsNone(connection.execute("SELECT 1 FROM sqlite_master WHERE name LIKE 'writer_fence_credit%'").fetchone())


if __name__ == "__main__":
    unittest.main()
