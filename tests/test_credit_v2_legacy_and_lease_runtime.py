"""Actual archived binaries and real native lease handover; synthetic only."""
from decimal import Decimal as D
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

from tests.credit_v2_runtime_fixture import SyntheticCreditAuthority
from tests.test_credit_native import authority, extract_fixture
from uta.credit_fifo_v2 import InternalCreditFIFO
from uta.credit_native_v2 import acquire_credit_v2, install_internal_credit_v2
from uta.durable_commands import CommandExecutionError
from uta.existing_services import open_existing_services
from uta.writer_fence import WriterFenceError


_CHILD = r'''
from hashlib import sha256
from pathlib import Path
import json,sys
from decimal import Decimal
import uta.storage as actual_storage
from uta.storage import Database,DurableLedger
from uta.ledger import Posting
mode,path=sys.argv[1:]
record={'phase':'starting','real_financial_write':False,'acquired':False}
try:
 if mode=='fenced':
  import uta.writer_fence as actual_fence
  from uta.writer_fence import WriterFence
  record['phase']='acquire'
  db=Database(path);fence=WriterFence(db)
  token=fence.acquire('synthetic:legacy-control',10)
  record['acquired']=True
  record['phase']='financial_write'
  with db.for_writer(token).transaction() as con:
   con.execute("UPDATE uta_accounts SET version=version+1 WHERE account_id='alice'")
  record['real_financial_write']=True
  fence.release(token)
  record['writer_source_sha256']=sha256(Path(actual_fence.__file__).read_bytes()).hexdigest()
 else:
  record['phase']='ledger_constructor'
  ledger=DurableLedger(Database(path),{'USD':8,'BTC':8})
  record['phase']='ledger_post'
  ledger.post('synthetic:ad3:actual-write',[Posting('system:custody','USD',Decimal(-1)),Posting('customer:alice','USD',Decimal(1))])
  record['real_financial_write']=True
 record['phase']='completed'
except Exception as error:
 record.update(rejected=True,type=type(error).__name__,code=getattr(error,'code',None),
   native_error_code=getattr(error,'sqlite_errorcode',None),message=str(error))
else:record['rejected']=False
record['storage_source_sha256']=sha256(Path(actual_storage.__file__).read_bytes()).hexdigest()
print(json.dumps(record,sort_keys=True))
'''


class LegacyAndLeaseRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.assertNotIn("UTA_CREDIT_V2_PRIVATE_DB_DIRECTORY", os.environ)

    def snapshot(self, database):
        with database.read_transaction() as connection:
            tables = ("uta_accounts", "uta_liabilities", "credit_commands", "ledger_events", "ledger_postings",
                "ledger_balances", "uta_events", "uta_command_inbox", "credit_v2_sources", "credit_v2_intents",
                "credit_v2_expected_postings", "uta_credit_decisions")
            existing = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            return {name: [tuple(row) for row in connection.execute("SELECT * FROM " + name + " ORDER BY rowid")]
                    for name in tables if name in existing}

    def test_actual_three_legacy_sources_refuse_complete_fresh_v2_with_positive_controls(self):
        fixture = SyntheticCreditAuthority()
        self.addCleanup(fixture.close)
        # Real complete installation, not a hand-written marker prototype. No
        # owner is acquired before the three actual old processes try it.
        installed = install_internal_credit_v2(fixture.db, fixture.bootstrap, fixture.bootstrap_credit, fixture.envelope)
        self.assertFalse(installed["writer_acquired"])
        full_before = self.snapshot(fixture.db)
        observations = []
        directory = Path(__file__).parent / "fixtures"
        for label, archive_name, provenance_name, mode in (
            ("899c91d", "legacy_credit_899c91d_uta.tar.gz", "legacy_credit_899c91d_provenance.json", "fenced"),
            ("45818c0", "legacy_credit_45818c0_uta.tar.gz", "legacy_credit_45818c0_provenance.json", "fenced"),
            ("ad3f5b8", "legacy_ad3f5b8_uta.tar.gz", "legacy_ad3f5b8_provenance.json", "unfenced")):
            with self.subTest(actual_legacy_source=label), TemporaryDirectory(prefix="uta-v2-actual-legacy-") as root:
                archive = directory / archive_name
                provenance = json.loads((directory / provenance_name).read_text())
                self.assertEqual(sha256(archive.read_bytes()).hexdigest(), provenance["archive_sha256"])
                source = Path(root)/"source"
                source.mkdir()
                extract_fixture(archive, source)
                expected_storage = sha256((source/"uta/storage.py").read_bytes()).hexdigest()
                def run(path):
                    process = subprocess.run([sys.executable, "-c", _CHILD, mode, str(path)], cwd=source,
                        capture_output=True, text=True, timeout=8)
                    self.assertEqual(process.returncode, 0, process.stderr)
                    result = json.loads(process.stdout)
                    self.assertEqual(result["storage_source_sha256"], expected_storage)
                    return result
                if mode == "fenced":
                    with authority() as (base_db, _, _, base_fence, _):
                        with base_db.read_transaction() as connection:
                            version = connection.execute("SELECT version FROM uta_accounts WHERE account_id='alice'").fetchone()[0]
                        positive = run(base_db.path)
                        self.assertFalse(positive["rejected"], positive)
                        self.assertTrue(positive["acquired"] and positive["real_financial_write"])
                        self.assertEqual(positive["writer_source_sha256"], sha256((source/"uta/writer_fence.py").read_bytes()).hexdigest())
                        with base_db.read_transaction() as connection:
                            self.assertEqual(connection.execute("SELECT version FROM uta_accounts WHERE account_id='alice'").fetchone()[0], version+1)
                        self.assertEqual(base_fence.status()["generation"], 1)
                else:
                    # An actual pre-fence binary has no acquire API. Its true
                    # positive control is an unfenced independent ledger DB.
                    positive = run(Path(root)/"positive.sqlite3")
                    self.assertFalse(positive["rejected"], positive)
                    self.assertTrue(positive["real_financial_write"])
                negative = run(fixture.db.path)
                self.assertTrue(negative["rejected"], negative)
                self.assertFalse(negative["acquired"] or negative["real_financial_write"])
                if mode == "fenced":
                    self.assertEqual(negative["code"], "fence_guard_corrupt")
                self.assertEqual(self.snapshot(fixture.db), full_before)
                with fixture.db.read_transaction() as connection:
                    generation, owner = connection.execute("SELECT generation,owner_nonce FROM writer_fence_lease").fetchone()
                    self.assertEqual(generation, 0)
                    self.assertIsNone(owner)
                    self.assertEqual(connection.execute("PRAGMA foreign_key_check").fetchall(), [])
                observations.append({"actual_source": label, "archive_sha256": provenance["archive_sha256"],
                    "positive": positive, "complete_v2_negative": negative,
                    "complete_v2_financial_snapshot_unchanged": True, "complete_v2_generation": generation})
        print(json.dumps({"actual_legacy_sources_with_complete_v2": observations}, sort_keys=True))

    def test_real_renew_release_reacquire_preserves_original_pending_cid_and_receipt(self):
        fixture = SyntheticCreditAuthority().install_and_open()
        self.addCleanup(fixture.close)
        fifo, first = fixture.fifo, fixture.token
        queued = fifo.enqueue_borrow("alice", "handover-cid", "BTC", D(".1"), actor_id="synthetic:lease-handover",
            source_reference="synthetic:lease:handover-cid")
        before = self.snapshot(fixture.services.exchange.database)
        renewed = fixture.fence.renew(first, 60)
        self.assertIs(renewed, first)
        self.assertEqual(fixture.fence.status()["generation"], first.generation)
        self.assertEqual(self.snapshot(fixture.services.exchange.database), before)
        fixture.fence.release(first)
        second = acquire_credit_v2(fixture.db, "synthetic:lease-second-owner", 60)
        self.assertEqual(second.generation, first.generation+1)
        with self.assertRaises(WriterFenceError) as stale_renew:
            fixture.fence.renew(first, 60)
        self.assertEqual(stale_renew.exception.code, "writer_fenced")
        with self.assertRaises(CommandExecutionError):
            fifo.process_one()  # Actual former bound owner cannot settle it.
        self.assertEqual(self.snapshot(fixture.services.exchange.database), before)
        reopened = open_existing_services(fixture.db.for_writer(second), clock=lambda: fixture.now)
        resumed = InternalCreditFIFO(reopened.exchange, reopened.credit)
        self.assertEqual(resumed.status("handover-cid"), queued)
        receipt = resumed.process_one()
        self.assertEqual((receipt["state"], receipt["result"]["principal"]), ("SUCCEEDED", "0.1"))
        after = self.snapshot(reopened.exchange.database)
        self.assertEqual(resumed.enqueue_borrow("alice", "handover-cid", "BTC", D(".1"),
            actor_id="synthetic:lease-handover", source_reference="synthetic:lease:handover-cid"), receipt)
        self.assertIsNone(resumed.process_one())
        self.assertEqual(self.snapshot(reopened.exchange.database), after)
        with reopened.exchange.database.read_transaction() as connection:
            self.assertEqual([connection.execute("SELECT COUNT(*) FROM "+table).fetchone()[0]
                for table in ("credit_v2_sources", "credit_v2_intents", "uta_credit_decisions")], [1, 1, 1])
            self.assertEqual(connection.execute("PRAGMA foreign_key_check").fetchall(), [])
        print(json.dumps({"actual_same_process_native_lease_handover": {
            "first_generation": first.generation, "second_generation": second.generation,
            "renew_keeps_generation": True, "old_owner_financial_attempt_refused": True,
            "original_pending_cid_settled_once": True, "original_receipt_replay_no_new_effects": True,
            "scope": "real native boot-clock lease; same process reopen, not process restart or expiry timing"}}, sort_keys=True))


if __name__ == "__main__":
    unittest.main()
