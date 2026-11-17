"""Real prepared-only native capability; never fake a trading owner or audit."""
from contextlib import contextmanager
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal as D
from hashlib import sha256
import json
from pathlib import Path, PurePosixPath
import shutil
import sqlite3
import subprocess
import sys
import tarfile
from tempfile import TemporaryDirectory
from threading import Barrier
import unittest
from unittest.mock import patch

from tests.credit_policy_cases import descriptor, reseal
from uta.credit import CreditService
from uta.credit_native import CreditNativeError, operation_scope, prepare_credit_native
from uta.decision_audit import DecisionAudit
from uta.durable_batches import BatchStore
from uta.durable_commands import QueueStore
from uta.market import MarketSnapshot
from uta.models import AssetSpec, InstrumentSpec
from uta.service import ExchangeService
from uta.storage import Database
from uta.writer_fence import WriterFence, WriterFenceError, WriterToken


@contextmanager
def authority(*, batch=False, opening_loan=False):
    with TemporaryDirectory(prefix="uta-credit-native-") as directory:
        path = Path(directory) / "authority.sqlite3"
        db = Database(path)
        now = datetime(2026, 11, 17, tzinfo=timezone.utc)
        service = ExchangeService(db, {"USD": 8, "BTC": 8}, fee_rate=D(0), clock=lambda: now)
        service.create_account("alice")
        service.deposit("alice", "opening-cash", "USD", D(100))
        service.publish_market(MarketSnapshot(1, now,
            {"USD": AssetSpec(D(1), D(1)), "BTC": AssetSpec(D(100), D(".8"))},
            {"BTC-PERP": InstrumentSpec(D(100), D(".1"), D(".05"))}))
        service.set_kill_switch(False)
        credit = CreditService(service)
        credit.configure_asset_limit("BTC", D(100))
        credit.configure_limit("alice", "BTC", D(10))
        credit.fund_pool("pool:0", "BTC", D(1), source_reference="synthetic:credit-pool:0")
        if opening_loan:
            credit.borrow("alice", "opening-loan", "BTC", D(".4"))
            credit.accrue_interest("alice", "opening-interest", "BTC", D(".05"))
        QueueStore(db, initialize=True)
        audit = DecisionAudit(db)
        with db.transaction() as con:
            audit.install(con, policy=DecisionAudit.policy(service), recorded_at=now.isoformat())
        if batch:
            BatchStore.initialize(db)
        fence = WriterFence(db)
        fence.enable("credit:shard0")
        if batch:
            fence.enable_batches()
        doc = descriptor(fence.status()["authority_id"])
        if opening_loan:
            entry = doc["certificate"]["assets"]["BTC"]["allocations"][0]
            entry.update(opening_principal_units="40000000", opening_interest_units="5000000", opening_pool_units="60000000")
            reseal(doc)
        yield db, service, credit, fence, doc


def financial(db):
    tables = ("ledger_events", "ledger_postings", "ledger_balances", "uta_accounts", "uta_liabilities",
              "credit_commands", "uta_events", "uta_command_inbox", "uta_risk_decisions")
    with db.read_transaction() as con:
        return {table: [tuple(row) for row in con.execute(f"SELECT * FROM {table} ORDER BY rowid")] for table in tables}


def extract_fixture(archive, destination):
    with tarfile.open(archive) as source:
        for member in source.getmembers():
            path = PurePosixPath(member.name)
            if (path.is_absolute() or ".." in path.parts or not member.name
                    or not (member.name == "LICENSE" or path.parts[0] == "uta")
                    or not (member.isdir() or member.isfile())):
                raise AssertionError("unsafe old source fixture")
            target = destination.joinpath(*path.parts)
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                with source.extractfile(member) as original, target.open("wb") as output:
                    shutil.copyfileobj(original, output)


class PreparedNativeCreditTests(unittest.TestCase):
    def test_real_fresh_preparation_preserves_money_and_never_acquires(self):
        for batch in (False, True):
            with self.subTest(batch=batch), authority(batch=batch) as (db, service, credit, fence, doc):
                before = financial(db)
                prepared = prepare_credit_native(db, doc)
                self.assertEqual(prepared["stage"], "NATIVE_PREPARED")
                self.assertFalse(prepared["trading_enabled"])
                self.assertEqual(financial(db), before)
                state = fence.status()
                self.assertEqual((state["generation"], state["owner_nonce"], state["credit_format"]), (0, None, 1))
                self.assertEqual(state["batch_format"], int(batch))
                self.assertFalse(state["active"])
                with self.assertRaises(WriterFenceError) as blocked:
                    fence.acquire("cannot-become-owner", 1)
                self.assertEqual(blocked.exception.code, "credit_not_active")
                self.assertEqual(financial(db), before)

    def test_no_cap_base_and_batch_still_have_real_financial_owners(self):
        for batch in (False, True):
            with self.subTest(batch=batch), authority(batch=batch) as (db, service, credit, fence, doc):
                token = fence.acquire("real-nocap-owner", 5)
                with db.for_writer(token).transaction() as con:
                    con.execute("UPDATE uta_accounts SET version=version+1 WHERE account_id='alice'")
                fence.release(token)
                self.assertEqual(service.account("alice")["version"], 2)

    def test_released_real_owner_is_not_a_fresh_promotion(self):
        with authority() as (db, service, credit, fence, doc):
            token = fence.acquire("real-prior-owner", 5)
            fence.release(token)
            before = financial(db)
            with self.assertRaises(CreditNativeError) as blocked:
                prepare_credit_native(db, doc)
            self.assertEqual(blocked.exception.code, "credit_fresh_authority_required")
            self.assertEqual(financial(db), before)
            with db.read_transaction() as con:
                self.assertIsNone(con.execute("SELECT 1 FROM sqlite_master WHERE name='writer_fence_credit_capability'").fetchone())

    def test_wrong_actual_pool_claims_reject_before_any_marker(self):
        with authority() as (db, service, credit, fence, doc):
            claim = doc["certificate"]["assets"]["BTC"]["allocations"][0]["funding_claims"][0]
            claim["funded_units"] = "200000000"
            reseal(doc)
            with self.assertRaises(CreditNativeError) as blocked:
                prepare_credit_native(db, doc)
            self.assertEqual(blocked.exception.code, "credit_funding_mismatch")
            with db.read_transaction() as con:
                self.assertEqual(con.execute("SELECT COUNT(*) FROM sqlite_master WHERE name LIKE 'credit_native_%'").fetchone()[0], 0)

    def test_actual_opening_principal_and_interest_are_preserved(self):
        with authority(opening_loan=True) as (db, service, credit, fence, doc):
            before = financial(db)
            prepare_credit_native(db, doc)
            self.assertEqual(financial(db), before)
            with db.read_transaction() as con:
                self.assertEqual(tuple(con.execute("SELECT opening_principal_units,opening_interest_units,opening_pool_units FROM credit_native_allocations").fetchone()),
                                 ("40000000", "5000000", "60000000"))
                self.assertEqual(con.execute("SELECT COUNT(*) FROM credit_native_legacy_commands").fetchone()[0], 3)

    def test_same_descriptor_retries_only_verify_different_descriptor_conflicts(self):
        with authority() as (db, service, credit, fence, doc):
            result = prepare_credit_native(db, doc)
            self.assertEqual(prepare_credit_native(db, deepcopy(doc)), result)
            doc["certificate"]["version"] = 2
            reseal(doc)
            with self.assertRaises(CreditNativeError) as blocked:
                prepare_credit_native(db, doc)
            self.assertEqual(blocked.exception.code, "credit_descriptor_conflict")

    def test_financial_ddl_denial_is_immediate_and_cannot_be_caught_into_commit(self):
        with authority() as (db, service, credit, fence, doc):
            prepare_credit_native(db, doc)
            for sql in ("DROP TRIGGER credit_native_record_gate", "DROP INDEX credit_native_command_parent",
                        "ALTER TABLE credit_native_intents RENAME TO displaced_intents"):
                with self.subTest(sql=sql), self.assertRaises(WriterFenceError) as blocked:
                    with db.transaction() as con:
                        with self.assertRaises(sqlite3.DatabaseError):
                            con.execute(sql)
                        self.assertEqual(con.execute("SELECT 1").fetchone()[0], 1)
                self.assertEqual(blocked.exception.code, "credit_not_active")
            with db.read_transaction() as con:
                self.assertEqual(con.execute("SELECT COUNT(*) FROM sqlite_master WHERE name='credit_native_record_gate'").fetchone()[0], 1)

    def test_no_scope_or_forged_token_can_authorize_preparation(self):
        with authority() as (db, service, credit, fence, doc):
            prepare_credit_native(db, doc)
            with self.assertRaises(WriterFenceError) as blocked:
                with db.transaction() as con:
                    self.assertEqual(con.execute("SELECT uta_credit_operation_v1('INTENT','cid','digest')").fetchone()[0], 0)
            self.assertEqual(blocked.exception.code, "credit_not_active")
            with db.transaction() as con:
                with self.assertRaises(CreditNativeError) as scope:
                    with operation_scope(db, con, command_id="cid", payload_hash="a" * 64):
                        self.fail("a prepared scope became usable")
                self.assertEqual(scope.exception.code, "credit_not_active")
            with db.read_transaction() as con:
                with self.assertRaises(WriterFenceError) as token:
                    fence.assert_writer(con, WriterToken("credit:shard0", "forged-not-real-owner", 1))
                self.assertEqual(token.exception.code, "credit_not_active")

    def test_insert_update_delete_and_credit_record_are_all_blocked(self):
        with authority(opening_loan=True) as (db, service, credit, fence, doc):
            prepare_credit_native(db, doc)
            before = financial(db)
            statements = ("INSERT INTO uta_liabilities VALUES('alice','USD','1','0')",
                          "UPDATE uta_liabilities SET principal='0' WHERE account_id='alice'",
                          "DELETE FROM uta_liabilities WHERE account_id='alice'",
                          "DELETE FROM credit_commands")
            for sql in statements:
                with self.subTest(sql=sql), self.assertRaises(WriterFenceError):
                    with db.transaction() as con:
                        con.execute(sql)
                self.assertEqual(financial(db), before)

    def test_missing_schema_or_marker_is_never_repaired(self):
        for missing in ("trigger", "marker"):
            with self.subTest(missing=missing), authority() as (db, service, credit, fence, doc):
                prepare_credit_native(db, doc)
                con = sqlite3.connect(db.path)
                try:
                    con.execute("DROP TRIGGER credit_native_record_gate" if missing == "trigger" else "DROP TABLE writer_fence_credit_capability")
                    con.commit()
                finally:
                    con.close()
                with self.assertRaises((CreditNativeError, WriterFenceError)):
                    prepare_credit_native(db, doc)
                con = sqlite3.connect(Path(db.path).as_uri() + "?mode=ro", uri=True)
                try:
                    name = "credit_native_record_gate" if missing == "trigger" else "writer_fence_credit_capability"
                    self.assertIsNone(con.execute("SELECT 1 FROM sqlite_master WHERE name=?", (name,)).fetchone())
                finally:
                    con.close()

    def test_real_install_failure_rolls_back_all_ddl_before_retry(self):
        import uta.writer_fence as module
        with authority() as (db, service, credit, fence, doc):
            original = module._create_credit_object
            def actual_then_fail(connection, name):
                original(connection, name)
                if name == "credit_native_policies":
                    raise RuntimeError("synthetic installer interruption")
            with patch.object(module, "_create_credit_object", side_effect=actual_then_fail):
                with self.assertRaisesRegex(RuntimeError, "synthetic installer"):
                    prepare_credit_native(db, doc)
            with db.read_transaction() as con:
                self.assertEqual(con.execute("SELECT COUNT(*) FROM sqlite_master WHERE name LIKE 'credit_native_%'").fetchone()[0], 0)
            self.assertEqual(prepare_credit_native(db, doc)["stage"], "NATIVE_PREPARED")

    def test_real_prepare_and_acquire_race_cannot_both_succeed(self):
        with authority() as (db, service, credit, fence, doc):
            barrier = Barrier(2)
            def prepare():
                barrier.wait()
                try:
                    return ("prepared", prepare_credit_native(db, doc)["stage"])
                except CreditNativeError as error:
                    return ("prepare_rejected", error.code)
            def acquire():
                barrier.wait()
                try:
                    token = fence.acquire("real-race-owner", 5)
                except WriterFenceError as error:
                    return ("acquire_rejected", error.code)
                fence.release(token)
                return ("acquired", token.generation)
            with ThreadPoolExecutor(max_workers=2) as pool:
                left, right = pool.submit(prepare), pool.submit(acquire)
                results = left.result(), right.result()
            successes = [entry for entry in results if entry[0] in ("prepared", "acquired")]
            self.assertEqual(len(successes), 1, results)

    def test_actual_batch_aware_old_binary_rejects_prepared_credit_both(self):
        fixture = Path(__file__).parent / "fixtures"
        provenance = json.loads((fixture / "legacy_credit_45818c0_provenance.json").read_text())
        archive = fixture / "legacy_credit_45818c0_uta.tar.gz"
        self.assertEqual(sha256(archive.read_bytes()).hexdigest(), provenance["archive_sha256"])
        with TemporaryDirectory(prefix="uta-credit-old-native-") as root:
            source = Path(root)
            extract_fixture(archive, source)
            code = """import json,sys
from uta.storage import Database
from uta.writer_fence import WriterFence
try:
 db=Database(sys.argv[1]);fence=WriterFence(db)
 token=fence.acquire('actual-old458-owner',5)
 with db.for_writer(token).transaction() as con:
  con.execute("UPDATE uta_accounts SET version=version+1 WHERE account_id='alice'")
 fence.release(token)
except Exception as error:
 print(json.dumps({'rejected':True,'type':type(error).__name__,'code':getattr(error,'code',None)}))
else: print(json.dumps({'rejected':False,'real_financial_write':True}))
"""
            for batch in (False, True):
                for prepared in (False, True):
                    with self.subTest(batch=batch, prepared=prepared), authority(batch=batch) as (db, service, credit, fence, doc):
                        if prepared:
                            prepare_credit_native(db, doc)
                        before = financial(db)
                        result = subprocess.run([sys.executable, "-c", code, db.path], cwd=source,
                            capture_output=True, text=True, timeout=5)
                        self.assertEqual(result.returncode, 0, result.stderr)
                        record = json.loads(result.stdout)
                        if prepared:
                            self.assertEqual(record["code"], "fence_guard_corrupt")
                            self.assertEqual(financial(db), before)
                        else:
                            self.assertFalse(record["rejected"], record)
                            self.assertTrue(record["real_financial_write"])

    def test_actual_pre_fencing_ad3_cannot_write_prepared_authority(self):
        fixture = Path(__file__).parent / "fixtures"
        provenance = json.loads((fixture / "legacy_ad3f5b8_provenance.json").read_text())
        archive = fixture / "legacy_ad3f5b8_uta.tar.gz"
        self.assertEqual(sha256(archive.read_bytes()).hexdigest(), provenance["archive_sha256"])
        with TemporaryDirectory(prefix="uta-credit-ad3-native-") as root:
            source = Path(root)
            extract_fixture(archive, source)
            code = """import json,sys
from decimal import Decimal
from uta.storage import Database,DurableLedger
from uta.ledger import Posting
try:
 ledger=DurableLedger(Database(sys.argv[1]),{'USD':8,'BTC':8})
 ledger.post('ad3:unapproved',[Posting('system:custody','USD',Decimal(-1)),Posting('customer:alice','USD',Decimal(1))])
except Exception as error:
 print(json.dumps({'rejected':True,'type':type(error).__name__}))
else: raise AssertionError('unfenced old binary wrote prepared authority')
"""
            with authority() as (db, service, credit, fence, doc):
                prepare_credit_native(db, doc)
                before = financial(db)
                result = subprocess.run([sys.executable, "-c", code, db.path], cwd=source,
                    capture_output=True, text=True, timeout=5)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertTrue(json.loads(result.stdout)["rejected"])
                self.assertEqual(financial(db), before)


if __name__ == "__main__":
    unittest.main(verbosity=2)
