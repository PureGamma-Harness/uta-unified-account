"""Finite local SQL capture plan; synthetic accounts, no native workers."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal as D
from pathlib import Path
import tempfile
import unittest

from uta.examples import synthetic_policy
from uta.market import MarketSnapshot
from uta.models import AssetSpec, InstrumentSpec
from uta.service import ExchangeService, ServiceError
from uta.storage import Database


class DecisionAdmissionCaptureTests(unittest.TestCase):
    def fixture(self, *, mm=".05", cash="10.04", scale=2, configured=False):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        path = Path(temporary.name) / "admission.sqlite3"
        database = Database(path)
        times = [datetime(2026, 11, 18, 9, tzinfo=timezone.utc)]
        options = {}
        scales = {"USD": scale}
        if configured:
            catalog, rules = synthetic_policy()
            options.update(product_catalog=catalog, portfolio_rules=rules)
            scales["BTC"] = 8
        service = ExchangeService(database, scales, clock=lambda: times[0], decision_audit=True, **options)
        service.create_account("alice")
        service.deposit("alice", "fund", "USD", D(cash))
        assets = {"USD": AssetSpec(D(1), D(1))}
        if configured:
            assets["BTC"] = AssetSpec(D(100), D(".8"))
        service.publish_market(MarketSnapshot(1, times[0], assets,
            {"BTC-PERP": InstrumentSpec(D(100), D(".1"), D(mm))}))
        service.set_kill_switch(False)
        return service, database, times

    def test_ordinary_capture_and_known_id_retry_preserve_original_decision(self):
        service, database, times = self.fixture()
        order = service.submit_order("alice", "order", "BTC-PERP", D(1), D(100))
        identity = order["decision_id"]
        original = service.audit.decision(identity)
        self.assertEqual(original["summary"]["admission"]["projected_fee"], "0.04")
        self.assertEqual(original["summary"]["admission"]["projected_realized_pnl"], "0")
        projected = original["summary"]["projected_execution"]
        self.assertEqual((projected["equity"], projected["initial_margin"], projected["maintenance_margin"]), ("10", "10", "5"))
        result = service.audit.replay(identity)
        self.assertTrue(result["matches"])
        self.assertTrue(result["valuation_matches"])
        self.assertEqual(result["admission"]["status"], "VERIFIED")
        service.set_kill_switch(True)
        times[0] += timedelta(seconds=10)
        retry = service.submit_order("alice", "order", "BTC-PERP", D("1.0"), D("100.00"))
        self.assertEqual(retry["decision_id"], identity)
        self.assertEqual(service.audit.decision(identity), original)
        with database.read_transaction() as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM uta_risk_decisions").fetchone()[0], 1)
        self.assertEqual(service.ledger.verify(), 1)

    def test_mm_equality_rejection_has_no_fabricated_accepted_evidence(self):
        service, database, _ = self.fixture(mm=".1", scale=8)
        before = service.account("alice")
        with self.assertRaises(ServiceError) as caught:
            service.submit_order("alice", "unsafe", "BTC-PERP", D(1), D(100))
        self.assertEqual((caught.exception.code, caught.exception.status), ("insufficient_margin", 409))
        self.assertEqual(service.account("alice"), before)
        self.assertEqual(service.orders("alice"), [])
        with database.read_transaction() as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM uta_risk_decisions").fetchone()[0], 0)

    def test_configured_projection_and_reduce_only_have_explicit_coverage(self):
        service, database, _ = self.fixture(configured=True, cash="100")
        ordinary = service.submit_order("alice", "open", "BTC-PERP", D(1), D(100))
        fill = service.apply_fill("alice", "open", "fill", D(".5"), D(100))
        reduction = service.submit_order("alice", "close", "BTC-PERP", D("-.5"), D(100), reduce_only=True)
        for order in (ordinary, reduction):
            result = service.audit.replay(order["decision_id"])
            self.assertTrue(result["matches"])
            self.assertEqual(result["admission"]["status"], "VERIFIED")
            self.assertTrue(result["admission"]["checks"]["product_eligibility"])
            self.assertTrue(result["admission"]["checks"]["version_provenance"])
        execution = service.audit.replay(fill["execution_decision_id"])
        self.assertTrue(execution["matches"])
        self.assertEqual(execution["admission"]["status"], "UNSUPPORTED")
        self.assertEqual(execution["admission"]["reason"], "decision_kind_not_supported")
        self.assertEqual(service.ledger.verify(), 2)
        with database.read_transaction() as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM uta_risk_decisions").fetchone()[0], 3)


if __name__ == "__main__":
    unittest.main()
