"""Integrity of a backup is not proof of recovery through the latest receipt."""
from datetime import datetime, timezone
from decimal import Decimal as D
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from uta.market import MarketSnapshot
from uta.models import AssetSpec, InstrumentSpec
from uta.ops import backup_database, check_database, restore_database
from uta.service import ExchangeService
from uta.storage import Database


class RestoreWatermarkTests(unittest.TestCase):
    def test_healthy_old_backup_does_not_prove_latest_acknowledged_order_survives(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            now = datetime(2026, 11, 14, tzinfo=timezone.utc)
            source = root / "source.sqlite3"
            service = ExchangeService(Database(source), {"USD": 8}, clock=lambda: now)
            service.create_account("synthetic")
            service.deposit("synthetic", "seed", "USD", D(1000))
            service.publish_market(MarketSnapshot(1, now,
                {"USD": AssetSpec(D(1), D(1))},
                {"BTC-PERP": InstrumentSpec(D(100), D(".1"), D(".05"))}))
            service.set_kill_switch(False)
            before = service.account("synthetic")
            backup = root / "before-order.sqlite3"
            backup_database(source, backup)
            receipt = service.submit_order("synthetic", "acknowledged-after-backup",
                                           "BTC-PERP", D(1), D(100))
            self.assertEqual(receipt["status"], "OPEN")
            current = service.account("synthetic")
            restored_path = root / "restored.sqlite3"
            report = restore_database(backup, restored_path)
            self.assertTrue(report["requires_reconciliation"])
            self.assertEqual(check_database(restored_path)["integrity"], "ok")
            restored = ExchangeService(Database(restored_path), {"USD": 8}, clock=lambda: now)
            self.assertEqual(restored.orders("synthetic"), [])
            self.assertEqual(restored.account("synthetic"), before)
            self.assertLess(before["version"], current["version"])
            # Restore did not mutate or overwrite the still-authoritative source.
            reopened = ExchangeService(Database(source), {"USD": 8}, clock=lambda: now)
            self.assertEqual(reopened.account("synthetic"), current)
            self.assertEqual(reopened.orders("synthetic")[0]["order_id"], receipt["order_id"])
            # Do not blindly replay the acknowledged request into the old copy.
            # Reconciliation needs the original receipt and post-backup history.
