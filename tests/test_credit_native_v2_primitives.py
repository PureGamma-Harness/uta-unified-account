"""Storage/data primitives only: no native owner, scoped loan or fake UDF.

The component fixture uses actual core parents and a raw private temp connection
to isolate catalog constraints. It is not V2 installation/financial admission.
"""
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest

from tests.credit_policy_cases import canonical, descriptor
from uta.credit import CreditService
from uta import credit_audit_v2 as audit, credit_native_v2 as native
from uta.decision_audit import DecisionAudit
from uta.durable_commands import QueueStore
from uta.service import ExchangeService
from uta.storage import Database

NOW = datetime(2026, 11, 17, 12, 0, tzinfo=timezone.utc)


def envelope():
    static = descriptor()
    validated = native.validate_native_descriptor(static, expected_authority_id="credit:shard0")
    return {"format": 2, "stage": "SYNTHETIC_INTERNAL", "synthetic": True,
        "authority_id": "credit:shard0", "shard": 0, "static_budget": static,
        "static_budget_id": validated.descriptor_id, "audit_format": 2, "source_format": 2,
        "fifo_format": 2, "native_format": 2, "artifact_id": "credit-artifact:" + "a" * 64,
        "settlement_asset": "USD", "borrow_asset": "BTC", "batch_size": 0,
        "reserve_cache_size": 0, "market_cache_size": 0, "production_approved": False}


def source(cid="credit:1", ref="synthetic:1"):
    return native.source_receipt(authority_id="credit:shard0", account_id="alice", command_id=cid,
        kind="BORROW", actor_id="synthetic:runner", source_reference=ref,
        command_payload=canonical({"account_id": "alice", "asset": "BTC", "amount": "0.4"}), accepted_at=NOW)


def insert_source(connection, item, *, actor_id=None):
    connection.execute("INSERT INTO credit_v2_sources VALUES(?,?,?,?,?,?,?,?,?,?,?)",
        (item.command_id, item.source_id, item.account_id, item.kind, item.payload_hash,
         "synthetic_local", actor_id or item.actor_id, item.source_reference, item.authority_id,
         item.command_payload, item.canonical_payload))


def insert_inbox(connection, item):
    connection.execute("INSERT INTO uta_command_inbox(command_id,account_id,kind,payload,state,enqueued_at) VALUES(?,?,?,?,'PENDING',?)",
        (item.command_id, item.account_id, item.kind, item.command_payload, NOW.isoformat(timespec="microseconds")))


@contextmanager
def component():
    with TemporaryDirectory(prefix="uta-credit-v2-catalog-") as directory:
        db = Database(Path(directory) / "component.sqlite3")
        exchange = ExchangeService(db, {"USD": 8, "BTC": 8}, clock=lambda: NOW)
        exchange.create_account("alice")
        CreditService(exchange)
        QueueStore(db, initialize=True)
        with db.transaction() as con:
            DecisionAudit(db).install(con, policy=DecisionAudit.policy(exchange), recorded_at=NOW.isoformat())
        # Explicit raw component connection, not a claimed native owner. Real
        # core FK parents above are reused; no successful permission callback.
        con = db._connect()
        try:
            con.execute("BEGIN IMMEDIATE")
            for statement in (*audit.OBJECT_SQL.values(), *native.OBJECT_SQL.values()):
                con.execute(statement)
            con.commit()
            yield db, con
        finally:
            if con.in_transaction:
                con.rollback()
            con.close()


class CreditNativeV2PrimitiveTests(unittest.TestCase):
    def test_envelope_is_content_addressed_declaration_not_current_code_permission(self):
        doc = envelope()
        raw = canonical(doc)
        value = native.validate_envelope(raw, expected_authority_id="credit:shard0")
        self.assertEqual(value.capability_id, "credit-internal-v2:" + sha256(raw.encode()).hexdigest())
        self.assertEqual(value.static_descriptor.descriptor_id, doc["static_budget_id"])
        self.assertNotEqual(value.capability_id, value.static_descriptor.descriptor_id)
        with self.assertRaises(native.CreditV2Error):
            native.validate_envelope(raw, expected_authority_id="credit:shard0", expected_artifact_id="credit-artifact:" + "b" * 64)
        self.assertFalse(hasattr(native, "acquire_credit_v2"))
        self.assertFalse(hasattr(native, "operation_scope"))

    def test_envelope_unknown_scope_bool_formats_and_noncanonical_data_fail_typed(self):
        for name, value in (("native_format", True), ("batch_size", 1), ("reserve_cache_size", 1),
                            ("market_cache_size", 1), ("borrow_asset", "USDT"), ("production_approved", True),
                            ("stage", "NATIVE_PREPARED"), ("ready", True)):
            candidate = deepcopy(envelope())
            candidate[name] = value
            with self.subTest(name=name):
                with self.assertRaises(native.CreditV2Error) as refused:
                    native.validate_envelope(canonical(candidate), expected_authority_id="credit:shard0")
                self.assertEqual(refused.exception.code, "credit_v2_descriptor_invalid")
        for raw in ("{}", "{\"format\":2,\"format\":2}", "{\"format\":2.0}", "{\"format\":NaN}"):
            with self.assertRaises(native.CreditV2Error):
                native.validate_envelope(raw, expected_authority_id="credit:shard0")

    def test_source_hash_and_canonical_receipt_validate_exact_business_and_time(self):
        item = source()
        self.assertEqual(item.source_id, "credit-source:" + sha256(item.canonical_payload.encode()).hexdigest())
        self.assertEqual(item, native.parse_source(item.canonical_payload))
        for name, value in (("source_kind", "hmac"), ("accepted_at", "2026-11-17T12:00:00Z"),
                            ("payload_hash", "0" * 64), ("account_id", "bob"), ("execute", "unknown.module")):
            record = json.loads(item.canonical_payload)
            record[name] = value
            with self.subTest(name=name), self.assertRaises(native.CreditV2Error) as refused:
                native.parse_source(canonical(record))
            self.assertEqual(refused.exception.code, "credit_v2_source_invalid")

    def test_actual_source_then_matching_inbox_commit_and_reopen(self):
        with component() as (db, con):
            item = source()
            con.execute("BEGIN IMMEDIATE")
            insert_source(con, item)
            insert_inbox(con, item)
            con.commit()
            reopened = db._connect()
            try:
                self.assertEqual(native.read_source(reopened, item.command_id, expected_authority_id=item.authority_id), item)
                self.assertEqual(reopened.execute("SELECT COUNT(*) FROM credit_commands").fetchone()[0], 0)
                self.assertEqual(reopened.execute("SELECT COUNT(*) FROM uta_credit_decisions").fetchone()[0], 0)
            finally:
                reopened.close()

    def test_actual_deferred_source_fk_fails_commit_and_reopen_has_no_source(self):
        with component() as (db, con):
            item = source()
            con.execute("BEGIN IMMEDIATE")
            insert_source(con, item)
            with self.assertRaises(sqlite3.IntegrityError) as refused:
                con.commit()
            actual = getattr(refused.exception, "sqlite_errorcode", None)
            if actual is not None:
                self.assertEqual(actual, 787)
            else:
                self.assertEqual(str(refused.exception), "FOREIGN KEY constraint failed")
            print(json.dumps({"component": "missing_inbox_parent", "actual_native_code": actual,
                              "exception_type": type(refused.exception).__name__}, sort_keys=True))
            con.rollback()
            reopened = db._connect()
            try:
                self.assertEqual(reopened.execute("SELECT COUNT(*) FROM credit_v2_sources").fetchone()[0], 0)
                self.assertEqual(reopened.execute("SELECT COUNT(*) FROM uta_command_inbox").fetchone()[0], 0)
            finally:
                reopened.close()

    def test_stored_relational_mismatch_is_reader_rejected_not_native_permission(self):
        with component() as (_, con):
            item = source()
            con.execute("BEGIN IMMEDIATE")
            # Raw component SQL has no runtime source-UDF gate in this slice.
            # A mismatched row is NOT a valid receipt or permission. The real
            # reader must reject it even though the structural FK is satisfied.
            insert_source(con, item, actor_id="synthetic:different")
            insert_inbox(con, item)
            con.commit()
            with self.assertRaises(native.CreditV2Error) as refused:
                native.read_source(con, item.command_id, expected_authority_id=item.authority_id)
            self.assertEqual(refused.exception.code, "credit_v2_source_invalid")

    def test_source_immutable_all_unique_identities_with_recursive_triggers_off(self):
        with component() as (_, con):
            item = source()
            con.execute("BEGIN IMMEDIATE")
            insert_source(con, item)
            insert_inbox(con, item)
            con.commit()
            self.assertEqual(con.execute("PRAGMA recursive_triggers").fetchone()[0], 0)
            original = tuple(con.execute("SELECT * FROM credit_v2_sources").fetchone())
            for collision in ("command", "source", "reference"):
                candidate = list(original)
                candidate[0], candidate[1], candidate[7] = "credit:different", "credit-source:different", "synthetic:different"
                candidate[{"command": 0, "source": 1, "reference": 7}[collision]] = original[{"command": 0, "source": 1, "reference": 7}[collision]]
                con.execute("BEGIN IMMEDIATE")
                with self.subTest(collision=collision), self.assertRaises(sqlite3.IntegrityError) as refused:
                    con.execute("INSERT OR REPLACE INTO credit_v2_sources VALUES(?,?,?,?,?,?,?,?,?,?,?)", candidate)
                self.assertEqual(str(refused.exception), "credit v2 identity cannot replace")
                if getattr(refused.exception, "sqlite_errorcode", None) is not None:
                    self.assertEqual(refused.exception.sqlite_errorcode, 1811)
                con.rollback()
                self.assertEqual(tuple(con.execute("SELECT * FROM credit_v2_sources").fetchone()), original)
