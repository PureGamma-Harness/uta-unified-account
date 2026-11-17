"""Synthetic prices with real UTC/monotonic clocks, distinct from static fixtures."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal as D
import json
import os
from pathlib import Path
import time
import unittest

from tests.credit_v2_runtime_fixture import SyntheticCreditAuthority, actual_credit_observation
from uta.credit_audit_v2 import CreditAuditV2, canonical, utc_checkpoint
from uta.credit_fifo_v2 import InternalCreditFIFO
from uta.credit_native_v2 import metadata_scope
from uta.existing_services import open_existing_services
from uta.market import MarketSnapshot


class CreditV2RealtimeClockTests(unittest.TestCase):
    def test_real_utc_fresh_borrow_partial_repay_stale_rejection_and_new_sid_recovery(self):
        fixture = SyntheticCreditAuthority()
        self.addCleanup(fixture.close)
        fixture.install_and_open()
        # Keep the original static seed/clock unchanged. Construct distinct real
        # initialized runtime services, using a real UTC provider and the same
        # actual native token-bound database, before publishing fresh prices.
        services = open_existing_services(fixture.services.exchange.database,
            clock=lambda: datetime.now(timezone.utc))
        exchange, credit = services.exchange, services.credit
        fifo = InternalCreditFIFO(exchange, credit)
        baseline_wall, baseline_monotonic = datetime.now(timezone.utc), time.monotonic()

        def publish(version):
            raw = json.loads(fixture.market.to_json())
            raw.update(version=version, observed_at=datetime.now(timezone.utc).isoformat())
            snapshot = MarketSnapshot.from_json(canonical(raw))
            with exchange._transaction() as connection:
                with metadata_scope(credit, connection, operation="PUBLISH_MARKET"):
                    result = exchange._publish_market(connection, snapshot)
            return snapshot, result["market_snapshot_id"]

        first_market, first_sid = publish(fixture.market.version+1)
        fifo.enqueue_borrow("alice", "realtime-loan", "BTC", D(".4"),
            actor_id="synthetic:realclock-borrower", source_reference="synthetic:realclock:loan")
        self.assertEqual(fifo.process_one()["state"], "SUCCEEDED")
        with exchange.database.read_transaction() as connection:
            first = actual_credit_observation(connection, "realtime-loan")
        evidence = json.loads(first["decision_bundle"]["decision"]["payload"])
        selected, checked, recorded = [utc_checkpoint(evidence[name])
            for name in ("selected_at", "last_checked_at", "recorded_at")]
        self.assertLessEqual(baseline_wall, selected)
        self.assertLess(selected, checked)
        self.assertLessEqual(checked, recorded)
        self.assertLessEqual(recorded, datetime.now(timezone.utc))
        self.assertEqual(evidence["market_snapshot_id"], first_sid)
        self.assertIsNone(evidence["physical_commit_at"])

        fifo.enqueue_repay("alice", "realtime-partial-repay", "BTC", D(".1"),
            actor_id="synthetic:realclock-borrower", source_reference="synthetic:realclock:repay")
        repaid = fifo.process_one()
        self.assertEqual((repaid["state"], repaid["result"]["principal"]), ("SUCCEEDED", "0.3"))
        expiry = first_market.observed_at+exchange.max_price_age+timedelta(milliseconds=30)
        remaining = (expiry-datetime.now(timezone.utc)).total_seconds()
        self.assertLessEqual(remaining, 6, "test uses the original five-second policy, not a long artificial wait")
        if remaining > 0:
            time.sleep(remaining)  # Real wall-time expiry, no fixture/OS clock mutation.
        self.assertGreater(datetime.now(timezone.utc)-first_market.observed_at, exchange.max_price_age)
        fifo.enqueue_borrow("alice", "realtime-stale", "BTC", D(".01"),
            actor_id="synthetic:realclock-borrower", source_reference="synthetic:realclock:stale")
        rejected = fifo.process_one()
        self.assertEqual((rejected["state"], rejected["error"]["code"], rejected["error"]["status"]),
            ("REJECTED", "market_unavailable", 503))
        with exchange.database.read_transaction() as connection:
            self.assertEqual(connection.execute("SELECT principal,interest FROM uta_liabilities WHERE account_id='alice' AND asset='BTC'").fetchone()[:], ("0.3", "0"))
            self.assertIsNone(connection.execute("SELECT 1 FROM credit_v2_intents WHERE command_id='realtime-stale'").fetchone())
        _, second_sid = publish(first_market.version+1)
        self.assertNotEqual(first_sid, second_sid)
        self.assertEqual(fifo.enqueue_borrow("alice", "realtime-stale", "BTC", D(".01"),
            actor_id="synthetic:realclock-borrower", source_reference="synthetic:realclock:stale"), rejected)
        fifo.enqueue_borrow("alice", "realtime-after-fresh", "BTC", D(".01"),
            actor_id="synthetic:realclock-borrower", source_reference="synthetic:realclock:after-fresh")
        recovered = fifo.process_one()
        self.assertEqual((recovered["state"], recovered["result"]["principal"]), ("SUCCEEDED", "0.31"))
        with exchange.database.read_transaction() as connection:
            last = actual_credit_observation(connection, "realtime-after-fresh")
            self.assertEqual(last["decision_bundle"]["decision"]["market_snapshot_id"], second_sid)
            self.assertEqual(connection.execute("PRAGMA foreign_key_check").fetchall(), [])
        self.assertTrue(CreditAuditV2(exchange, credit).replay(first["decision_bundle"]["decision"]["decision_id"])["matches"])
        report = {"clock_scope": "real datetime.now(UTC) and monotonic; synthetic prices; original static fixture unchanged",
            "wall_begin": baseline_wall.isoformat(), "wall_end": datetime.now(timezone.utc).isoformat(),
            "monotonic_elapsed_seconds": time.monotonic()-baseline_monotonic,
            "first_sid": first_sid, "second_sid": second_sid,
            "selected_at": evidence["selected_at"], "last_checked_at": evidence["last_checked_at"], "recorded_at": evidence["recorded_at"],
            "stale_receipt": rejected, "physical_commit_at": None}
        output = os.environ.get("UTA_CREDIT_V2_CAPTURE_DIRECTORY")
        if output:
            directory = Path(output)
            directory.mkdir(parents=True, exist_ok=True)
            (directory/"actual-realtime-first-borrow.json").write_text(canonical(first)+"\n")
            (directory/"actual-realtime-restored-borrow.json").write_text(canonical(last)+"\n")
            (directory/"actual-realtime-clock.json").write_text(json.dumps(report, indent=2)+"\n")
        print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    unittest.main()
