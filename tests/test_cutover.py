import copy
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal as D, Inexact, localcontext
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest

from uta.cutover import ClassicImporter
from uta.credit import CreditService
from uta.market import MarketSnapshot
from uta.migration import build_shadow
from uta.models import AssetSpec, InstrumentSpec
from uta.service import ExchangeService, ServiceError
from uta.storage import Database


class ClassicCutoverTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "cutover.sqlite3"
        self.now = datetime(2026, 11, 14, tzinfo=timezone.utc)
        self.service = self.reopen()
        self.service.publish_market(MarketSnapshot(1, self.now,
            {"USD": AssetSpec(D(1), D(1)), "BTC": AssetSpec(D(200), D(".5"))},
            {"BTC-PERP": InstrumentSpec(D(220), D(".1"), D(".05"))}))
        self.service.set_kill_switch(False)
        self.importer = ClassicImporter(self.service)

    def reopen(self):
        return ExchangeService(Database(self.path), {"USD": 8, "BTC": 8}, clock=lambda: self.now)

    def source(self):
        return {"account_id": "classic-1", "version": 4, "captured_at": self.now.isoformat(),
                "compartments": {
                    "spot": {"balances": [
                        {"asset": "USD", "free": "1000", "locked": "0", "borrowed": "0", "interest": "0"},
                        {"asset": "BTC", "free": "2", "locked": "0", "borrowed": "0", "interest": "0"}]},
                    "margin": {"balances": [
                        {"asset": "USD", "free": "100", "locked": "0", "borrowed": "300", "interest": ".25"}]},
                    "futures": {"balances": [
                        {"asset": "USD", "free": "50", "locked": "0", "borrowed": "0", "interest": "0"}],
                        "positions": [{"symbol": "BTC-PERP", "quantity": ".1", "entry_price": "200"}]}}}

    def shadow(self, source=None):
        return build_shadow(source or self.source(), now=self.now)

    def import_it(self, shadow=None, command="cutover-1", importer=None, **changes):
        args = dict(source_fence_reference="classic-sim:writer-epoch-9-disabled",
                    open_orders=[], conditional_orders=[], pending_settlements=[], transfers_in_flight=[])
        args.update(changes)
        return (importer or self.importer).import_shadow(shadow or self.shadow(), command, **args)

    def state(self):
        with self.service.database.transaction() as conn:
            return {table: [tuple(row) for row in conn.execute(f"SELECT * FROM {table}")]
                    for table in ("uta_accounts", "uta_positions", "uta_liabilities", "migration_imports",
                                  "migration_reversals", "uta_liquidation_accounts", "uta_events", "ledger_events",
                                  "ledger_postings", "ledger_balances")}

    def test_import_preserves_gross_cash_principal_interest_position_and_freezes(self):
        receipt = self.import_it()
        account = self.service.account("classic-1")
        self.assertEqual(account["balances"], {"BTC": "2", "USD": "1150"})
        self.assertEqual(account["liabilities"], {"USD": {"principal": "300", "interest": "0.25", "total": "300.25"}})
        self.assertEqual(account["positions"]["BTC-PERP"], {"quantity": "0.1", "entry_price": "200", "cost_basis": "20"})
        self.assertEqual(self.service.risk("classic-1")["equity"], "1051.75")
        self.assertEqual(self.service.ledger.balance("liability:principal:classic-1", "USD"), D(-300))
        self.assertEqual(self.service.ledger.balance("system:credit-interest-receivable", "USD"), D(".25"))
        self.assertEqual(receipt["state"], "BLOCKED")
        self.assertIsNone(receipt["source_event_cursor"])
        self.assertFalse(receipt["source_fence_verified"])
        with self.assertRaises(ServiceError) as frozen:
            self.service.submit_order("classic-1", "new", "BTC-PERP", D(".01"), D(220))
        self.assertEqual(frozen.exception.code, "account_frozen")
        self.assertEqual(self.importer.verify(), 1)
        self.assertEqual(self.service.ledger.verify(), 1)
        self.assertEqual(self.service.supervise_account("classic-1")["state"], "NORMAL")
        self.service.submit_order("classic-1", "new", "BTC-PERP", D(".01"), D(220))

    def test_same_command_returns_immutable_receipt_after_expiry_and_restart(self):
        shadow = self.shadow()
        original = self.import_it(shadow)
        before = self.state()
        original_copy = copy.deepcopy(original)
        original["assets"]["USD"] = "999999"
        self.now += timedelta(seconds=60)
        restarted = ClassicImporter(self.reopen())
        self.assertEqual(self.import_it(shadow, importer=restarted), original_copy)
        self.assertEqual(restarted.receipt("cutover-1"), original_copy)
        self.assertEqual(self.state(), before)

    def test_global_command_conflict_and_repeated_source_rejected(self):
        self.import_it()
        original = self.state()
        changed = self.source()
        changed["version"] = 99
        changed["compartments"]["spot"]["balances"][0]["free"] = "1001"
        for shadow, command, expected in ((self.shadow(changed), "cutover-1", "idempotency_conflict"),
                                          (self.shadow(changed), "new-command", "source_already_imported"),
                                          (self.shadow(), "new-command", "source_already_imported")):
            with self.assertRaises(ServiceError) as caught:
                self.import_it(shadow, command)
            self.assertEqual(caught.exception.code, expected)
            self.assertEqual(self.state(), original)
        with self.assertRaises(ServiceError) as caught:
            self.import_it(source_fence_reference="different-fence")
        self.assertEqual(caught.exception.code, "idempotency_conflict")

    def test_required_in_flight_and_locked_state_are_never_discarded(self):
        baseline = self.state()
        with self.assertRaises(TypeError):
            self.importer.import_shadow(self.shadow(), "missing", source_fence_reference="fence")
        for field in ("open_orders", "conditional_orders", "pending_settlements", "transfers_in_flight"):
            for value in ([{"id": "unresolved"}], None, {}, False):
                with self.subTest(field=field, value=value), self.assertRaises(ServiceError):
                    self.import_it(**{field: value})
                self.assertEqual(self.state(), baseline)
        raw = self.source()
        raw["compartments"]["spot"]["balances"][0]["locked"] = "1"
        with self.assertRaises(ServiceError) as caught:
            self.import_it(self.shadow(raw))
        self.assertEqual(caught.exception.code, "unsupported_lock")
        self.assertEqual(self.state(), baseline)

    def test_stale_source_or_market_rejected_before_any_book_change(self):
        old = self.shadow()
        self.now += timedelta(seconds=31)
        baseline = self.state()
        with self.assertRaises(ServiceError) as caught:
            self.import_it(old)
        self.assertEqual(caught.exception.code, "stale_migration")
        self.assertEqual(self.state(), baseline)
        fresh = self.shadow()
        with self.assertRaises(ServiceError) as caught:
            self.import_it(fresh)
        self.assertEqual(caught.exception.code, "market_unavailable")
        self.assertEqual(self.state(), baseline)

    def test_digest_unknown_asset_and_unsupported_product_fail_atomically(self):
        baseline = self.state()
        bad = [replace(self.shadow(), source_digest="0" * 64), replace(self.shadow(), balances=None)]
        unknown_asset = self.source()
        unknown_asset["compartments"]["spot"]["balances"][0]["asset"] = "UNKNOWN"
        bad.append(self.shadow(unknown_asset))
        unknown_product = self.source()
        unknown_product["compartments"]["futures"]["positions"][0]["symbol"] = "BTC-INVERSE"
        bad.append(self.shadow(unknown_product))
        unrepresentable = self.source()
        unrepresentable["compartments"]["spot"]["balances"][0]["free"] = "1.000000001"
        bad.append(self.shadow(unrepresentable))
        for shadow in bad:
            with self.subTest(shadow=shadow), self.assertRaises(ServiceError):
                self.import_it(shadow)
            self.assertEqual(self.state(), baseline)

    def test_empty_existing_account_is_allowed_but_financial_history_is_not(self):
        self.service.create_account("classic-1")
        self.import_it()
        self.assertEqual(self.importer.verify(), 1)
        second_source = self.source()
        second_source["account_id"] = "funded"
        self.service.create_account("funded")
        self.service.deposit("funded", "deposit", "USD", D(1))
        baseline = self.state()
        with self.assertRaises(ServiceError) as caught:
            self.import_it(self.shadow(second_source), "funded-import")
        self.assertEqual(caught.exception.code, "destination_not_empty")
        self.assertEqual(self.state(), baseline)

    def test_concurrent_importers_commit_one_receipt_and_one_journal(self):
        shadow = self.shadow()
        importers = [ClassicImporter(self.reopen()) for _ in range(6)]
        with ThreadPoolExecutor(max_workers=6) as pool:
            receipts = list(pool.map(lambda importer: self.import_it(shadow, importer=importer), importers))
        self.assertTrue(all(receipt == receipts[0] for receipt in receipts))
        self.assertEqual(self.importer.verify(), 1)
        self.assertEqual(len(self.service.ledger.journal()), 1)
        with self.service.database.transaction() as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM migration_imports").fetchone()[0], 1)

    def test_insert_failure_cannot_leave_assets_positions_debt_or_consumed_id(self):
        baseline = self.state()
        with self.service.database.transaction() as conn:
            conn.execute("""CREATE TRIGGER reject_cutover BEFORE INSERT ON migration_imports
                BEGIN SELECT RAISE(ABORT,'injected receipt failure'); END""")
        with self.assertRaises(sqlite3.IntegrityError):
            self.import_it()
        self.assertEqual(self.state(), baseline)
        with self.service.database.transaction() as conn:
            conn.execute("DROP TRIGGER reject_cutover")
        self.import_it()
        self.assertEqual(self.importer.verify(), 1)

    def test_process_death_after_book_updates_before_commit_rolls_back_then_resumes(self):
        baseline = self.state()
        script = """
import json,os,sys
from datetime import datetime
from uta.cutover import ClassicImporter
from uta.migration import build_shadow
from uta.service import ExchangeService
from uta.storage import Database
raw=json.loads(sys.argv[2]); now=datetime.fromisoformat(raw['captured_at'])
service=ExchangeService(Database(sys.argv[1]),{'USD':8,'BTC':8},clock=lambda:now)
importer=ClassicImporter(service); original=service._event
def event(connection,kind,account_id,payload):
    if kind=='MIGRATION_IMPORTED': os._exit(61)
    original(connection,kind,account_id,payload)
service._event=event
importer.import_shadow(build_shadow(raw,now=now),'cutover-1',source_fence_reference='classic-sim:writer-epoch-9-disabled',
                      open_orders=[],conditional_orders=[],pending_settlements=[],transfers_in_flight=[])
"""
        result = subprocess.run([sys.executable, "-c", script, str(self.path), json.dumps(self.source())],
                                capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 61, result.stderr)
        self.assertEqual(self.state(), baseline)
        self.import_it()
        self.assertEqual(self.importer.verify(), 1)

    def test_negative_equity_is_retained_frozen_and_supervised_as_bankrupt(self):
        source = self.source()
        source["compartments"]["spot"]["balances"] = []
        source["compartments"]["margin"]["balances"][0]["free"] = "0"
        source["compartments"]["futures"] = {"balances": [], "positions": []}
        self.import_it(self.shadow(source))
        self.assertEqual(self.service.risk("classic-1")["equity"], "-300.25")
        with self.assertRaises(ServiceError):
            self.service.submit_order("classic-1", "bad", "BTC-PERP", D(1), D(220))
        self.assertEqual(self.service.supervise_account("classic-1")["state"], "BANKRUPT")
        self.assertEqual(self.importer.verify(), 1)

    def test_imported_debt_can_be_repaid_without_inventing_prior_pool_funding(self):
        self.import_it()
        credit = CreditService(self.service)
        self.assertEqual(credit.verify()["nonzero_liabilities"], 1)
        before_equity = self.service.risk("classic-1")["equity"]
        credit.repay("classic-1", "repay-source-debt", "USD", D("300.25"))
        self.assertEqual(self.service.account("classic-1")["balances"]["USD"], "849.75")
        self.assertEqual(self.service.account("classic-1")["liabilities"]["USD"]["total"], "0")
        self.assertEqual(self.service.risk("classic-1")["equity"], before_equity)
        self.assertEqual(self.service.ledger.balance("system:credit-pool", "USD"), D(300))
        self.assertEqual(self.service.ledger.balance("system:credit-interest-cash", "USD"), D(".25"))
        self.assertEqual(self.service.ledger.balance("system:credit-principal-receivable", "USD"), D(0))
        self.assertEqual(self.service.ledger.balance("system:credit-interest-receivable", "USD"), D(0))
        self.assertEqual(credit.verify()["nonzero_liabilities"], 0)
        self.assertEqual(self.importer.verify(), 1)

    def test_compensating_handback_preserves_original_history_and_deduplicates(self):
        original = self.import_it()
        reversal = self.importer.reverse_import("cutover-1", "reverse-1", source_handback_reference="classic:epoch-10-handover")
        before = self.state()
        self.assertEqual(self.importer.reverse_import("cutover-1", "reverse-1", source_handback_reference="classic:epoch-10-handover"), reversal)
        self.assertEqual(self.state(), before)
        self.assertEqual(self.importer.receipt("cutover-1"), original)
        self.assertEqual(self.importer.status("cutover-1"), {
            "import": original, "handback": reversal, "active": False, "current_account_version": 2})
        account = self.service.account("classic-1")
        self.assertEqual(account["balances"], {"BTC": "0", "USD": "0"})
        self.assertEqual(account["positions"], {})
        self.assertEqual(account["liabilities"], {})
        self.assertEqual(len(self.service.ledger.journal()), 2)
        self.assertEqual(self.importer.verify(), 1)
        with self.assertRaises(ServiceError) as caught:
            self.importer.reverse_import("cutover-1", "another", source_handback_reference="another")
        self.assertEqual(caught.exception.code, "migration_already_reversed")
        with self.assertRaises(ServiceError):
            self.import_it(command="reimport")

    def test_new_activity_requires_forward_recovery_and_cannot_be_database_rolled_back(self):
        self.import_it()
        self.service.deposit("classic-1", "new-cash", "USD", D(1))
        before = self.state()
        with self.assertRaises(ServiceError) as caught:
            self.importer.reverse_import("cutover-1", "reverse", source_handback_reference="attestation")
        self.assertEqual(caught.exception.code, "migration_forward_recovery_required")
        self.assertEqual(self.state(), before)

    def test_receipts_immutable_and_verify_detects_dropped_guard_and_corruption(self):
        self.import_it()
        with self.service.database.transaction() as conn:
            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute("UPDATE migration_imports SET receipt='{}'")
            conn.execute("DROP TRIGGER migration_imports_no_update")
            conn.execute("UPDATE migration_imports SET receipt='{}'")
        with self.assertRaises(ServiceError) as caught:
            self.importer.verify()
        self.assertEqual(caught.exception.code, "migration_corrupt")

    def test_import_and_compensation_ignore_decimal_precision_and_traps(self):
        with localcontext() as context:
            context.prec = 1
            context.Emax = 2
            context.traps[Inexact] = True
            self.import_it()
            self.assertEqual(self.service.risk("classic-1")["equity"], "1051.75")
            self.importer.reverse_import("cutover-1", "reverse", source_handback_reference="handover")
            self.assertEqual(self.importer.verify(), 1)


if __name__ == "__main__":
    unittest.main()
