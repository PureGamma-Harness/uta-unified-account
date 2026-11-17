"""Incomplete V2 cannot publish/acquire; old actual sources reject its marker.

The raw marker fixture is an explicit inventory prototype, not an installed or
financially valid V2. No fake successful authorization callback is registered.
"""
from pathlib import Path
import json
import sqlite3
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from tests.test_credit_native import authority, extract_fixture
from tests.test_credit_native_v2_primitives import envelope
from uta.credit_native_v2 import CreditV2Error, MARKER_NAME, MARKER_SQL
from uta.writer_fence import WriterFence, WriterFenceError, _CONTROL_TRIGGER_SQL, _create_control_object, _load, _observed


FIXTURE = Path(__file__).parent / "fixtures/legacy_credit_899c91d_uta.tar.gz"
PROVENANCE = FIXTURE.with_name("legacy_credit_899c91d_provenance.json")


def marker_row():
    return (1, 2, "SYNTHETIC_INTERNAL", "credit-internal-v2:" + "b" * 64,
            json.dumps(envelope(), sort_keys=True, separators=(",", ":")))


def raw_marker(db, fence):
    # Deliberate trusted-host component mutation: this is never a native
    # installer or a successful credit capability. It proves old inventory
    # refusal even when a prototype claims the new format.
    state = fence.status()
    con = db._connect()
    try:
        con.execute("BEGIN IMMEDIATE")
        con.execute(MARKER_SQL)
        con.execute("INSERT INTO writer_fence_credit_v2_capability VALUES(?,?,?,?,?)", marker_row())
        fence._event(con, "credit_internal_enabled_v2", state, state["observed_ns"])
        con.commit()
    finally:
        if con.in_transaction:
            con.rollback()
        con.close()


class CreditNativeV2FenceBoundaryTests(unittest.TestCase):
    def test_marker_definition_is_exact_compiled_control_definition(self):
        from uta.writer_fence import _CONTROL_TABLE_SQL
        self.assertEqual(_CONTROL_TABLE_SQL[MARKER_NAME], MARKER_SQL)

    def test_explicit_internal_acquire_cannot_turn_uncapped_authority_into_v2(self):
        with authority() as (db, _, _, fence, _):
            with self.assertRaises(WriterFenceError) as refused:
                fence._acquire_internal_credit_v2("synthetic:owner", 30)
            self.assertEqual(refused.exception.code, "credit_v2_not_active")
            self.assertEqual(fence.status()["generation"], 0)

    def test_partial_native_objects_without_marker_refuse_writer_without_repair(self):
        with authority() as (db, _, _, fence, _):
            con = db._connect()
            try:
                con.execute("CREATE TABLE credit_v2_unexpected(value TEXT)")
                with self.assertRaises(WriterFenceError) as refused:
                    _load(con)
                self.assertEqual(refused.exception.code, "credit_v2_partial_schema")
                self.assertEqual(con.execute("SELECT generation FROM writer_fence_lease").fetchone()[0], 0)
            finally:
                con.close()
            with self.assertRaises(WriterFenceError):
                fence.acquire("synthetic:owner", 30)

    def test_real_control_publication_missing_runtime_rolls_back_marker_event(self):
        from uta import credit_native_v2 as native
        actual_import = native.importlib.import_module
        unavailable = []
        def missing_fifo(name, package=None):
            if name == "uta.credit_fifo_v2":
                unavailable.append(name)
                raise ModuleNotFoundError("synthetic unavailable fixed FIFO implementation")
            return actual_import(name, package)
        with authority() as (db, _, _, fence, _):
            # Explicit absence fault, not a successful permission callback.
            # This remains the same fail-closed test once a real FIFO ships.
            with patch.object(native.importlib, "import_module", side_effect=missing_fifo):
                with self.assertRaises(CreditV2Error) as refused:
                    with db._fence_transaction() as con:
                        state = _load(con)
                        _create_control_object(con, MARKER_NAME)
                        for name, (table, _) in _CONTROL_TRIGGER_SQL.items():
                            if table == MARKER_NAME:
                                _create_control_object(con, name)
                        con.execute("INSERT INTO writer_fence_credit_v2_capability VALUES(?,?,?,?,?)", marker_row())
                        now, _ = _observed(db, state)
                        fence._event(con, "credit_internal_enabled_v2", state, now)
            self.assertEqual(refused.exception.code, "credit_v2_runtime_incomplete")
            self.assertEqual(unavailable, ["uta.credit_fifo_v2"])
            reopened = db._connect()
            try:
                self.assertIsNone(reopened.execute("SELECT 1 FROM sqlite_master WHERE name=?", (MARKER_NAME,)).fetchone())
                self.assertEqual(reopened.execute("SELECT COUNT(*) FROM writer_fence_events").fetchone()[0], 1)
                self.assertEqual(reopened.execute("SELECT generation FROM writer_fence_lease").fetchone()[0], 0)
            finally:
                reopened.close()

    def test_actual_old_899_base_positive_vs_new_marker_negative(self):
        outcomes = []
        with TemporaryDirectory(prefix="uta-credit-v2-old899-") as old_directory:
            extract_fixture(FIXTURE, Path(old_directory))
            for prototype in (False, True):
                with authority() as (db, _, _, fence, _):
                    before_connection = db._connect()
                    try:
                        before_version = before_connection.execute("SELECT version FROM uta_accounts WHERE account_id='alice'").fetchone()[0]
                    finally:
                        before_connection.close()
                    if prototype:
                        raw_marker(db, fence)
                    code = """import json,sys
from hashlib import sha256
from pathlib import Path
from uta.storage import Database,StorageError
import uta.writer_fence as actual_fence
from uta.writer_fence import WriterFence
db=Database(sys.argv[1])
try:
 token=WriterFence(db).acquire('synthetic:old-owner',30)
 with db.for_writer(token).transaction() as con:
  con.execute("UPDATE uta_accounts SET version=version+1 WHERE account_id='alice'")
 result={'old_source':'899c91d','acquired':True,'financial_write':True}
except StorageError as exc:
 result={'old_source':'899c91d','acquired':False,'financial_write':False,'code':getattr(exc,'code',None)}
result['writer_source_sha256']=sha256(Path(actual_fence.__file__).read_bytes()).hexdigest()
print(json.dumps(result,sort_keys=True))
"""
                    run = subprocess.run([sys.executable, "-c", code, db.path], cwd=old_directory,
                        capture_output=True, text=True, timeout=5)
                    self.assertEqual(run.returncode, 0, run.stderr)
                    result = json.loads(run.stdout)
                    self.assertEqual(result["writer_source_sha256"], json.loads(PROVENANCE.read_text())["writer_fence_source_sha256"])
                    self.assertEqual(result["acquired"], not prototype)
                    self.assertEqual(result["financial_write"], not prototype)
                    if prototype:
                        self.assertEqual(result["code"], "fence_guard_corrupt")
                    con = db._connect()
                    try:
                        self.assertEqual(con.execute("SELECT version FROM uta_accounts WHERE account_id='alice'").fetchone()[0], before_version + int(not prototype))
                        self.assertEqual(con.execute("SELECT generation FROM writer_fence_lease").fetchone()[0], int(not prototype))
                        self.assertEqual(con.execute("SELECT COUNT(*) FROM uta_liabilities").fetchone()[0], 0)
                    finally:
                        con.close()
                    outcomes.append({"prototype_marker": prototype, **result})
        print(json.dumps({"actual_old_binary_inventory_controls": outcomes}, sort_keys=True))
