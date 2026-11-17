"""Standalone synthetic SQLite controls; no runtime/service imports or processes."""
from contextlib import contextmanager
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest

from tools.managed_observer_finance import ACCOUNTS, COLUMNS, SCALE, read_financial


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value):
    return sha256(canonical(value).encode()).hexdigest()


def fixture(path, *, completed=0):
    """Hand-built genesis and one closed round, independent of production code."""
    con = sqlite3.connect(path)
    for table, columns in COLUMNS.items():
        integers = {"sequence", "ordinal", "scale", "version", "reduce_only", "pre_version", "post_version",
            "market_version", "buy_version", "sell_version", "format", "singleton", "sealed", "attempts",
            "legacy_event_watermark", "legacy_order_count", "legacy_fill_count"}
        definition = ",".join(name + (" INTEGER" if name in integers else " TEXT") for name in columns.split(","))
        con.execute("CREATE TABLE " + table + " (" + definition + ")")
    def insert(table, **values):
        names = list(values)
        con.execute("INSERT INTO " + table + " (" + ",".join(names) + ") VALUES (" + ",".join("?" for _ in names) + ")", list(values.values()))
    balances = {}
    event_number, previous_hash = 0, "0" * 64
    def event(name, changes):
        nonlocal event_number, previous_hash
        event_number += 1
        normalized = sorted(changes)
        fingerprint = digest(normalized)
        current = digest([event_number, name, previous_hash, fingerprint])
        insert("ledger_events", sequence=event_number, event_id=name, fingerprint=fingerprint,
            previous_hash=previous_hash, event_hash=current, sealed=1)
        for ordinal, (owner, asset, units) in enumerate(normalized):
            insert("ledger_postings", sequence=event_number, ordinal=ordinal, account=owner, asset=asset, units=str(units))
            balances[(owner, asset)] = balances.get((owner, asset), 0) + units
        previous_hash = current
        return name
    insert("uta_schema", version=3)
    for asset in ("BTC", "USD"):
        insert("ledger_assets", asset=asset, scale=8)
    insert("credit_asset_limits", asset="BTC", units=str(SCALE))
    insert("credit_account_limits", account_id=ACCOUNTS[2], asset="BTC", units=str(SCALE))
    for account in ACCOUNTS:
        insert("uta_accounts", account_id=account, version=0)
        event("deposit:" + account, [("customer:" + account, "USD", 1_000_000 * SCALE),
            ("system:custody", "USD", -1_000_000 * SCALE)])
    event("buffer", [("customer:" + ACCOUNTS[2], "BTC", SCALE), ("system:custody", "BTC", -SCALE)])
    funded = event("funding", [("system:credit-pool", "BTC", SCALE), ("system:credit-capital", "BTC", -SCALE)])
    borrowed = event("loan", [("customer:" + ACCOUNTS[2], "BTC", 2), ("system:credit-pool", "BTC", -2),
        ("liability:principal:" + ACCOUNTS[2], "BTC", -2), ("system:credit-principal-receivable", "BTC", 2)])
    insert("credit_commands", scope="pool", command_id="synthetic-initial-pool", kind="pool_funded",
        asset="BTC", amount="1", source_reference="synthetic:observer-test", result="{}", journal_event_id=funded, created_at="2026-01-01")
    insert("credit_commands", scope="account:" + ACCOUNTS[2], command_id="synthetic-initial-loan", kind="borrowed",
        asset="BTC", amount="0.00000002", source_reference=None, result="{}", journal_event_id=borrowed, created_at="2026-01-01")
    insert("uta_audit_capability", singleton=1, format=1, enabled_at="2026-01-01", legacy_event_watermark=0,
        legacy_order_count=0, legacy_fill_count=0, gaps="[]")
    archives = {}
    for table, key, content, prefix in (("uta_market_history", "snapshot_id", "payload", "market:"),
            ("uta_code_artifacts", "artifact_id", "manifest", "artifact:"),
            ("uta_risk_policies", "policy_id", "payload", "policy:")):
        raw = canonical({"synthetic": True})
        content_digest = sha256(raw.encode()).hexdigest()
        identity = prefix + content_digest
        archives[table] = identity
        values = {key: identity, content: raw}
        if table == "uta_market_history":
            values.update(content_digest=content_digest, origin="synthetic", recorded_at="2026-01-01")
        insert(table, **values)
    prefix = "ms:" + "a" * 24 + ":r000000001:"
    def decision(identity, kind, account, business):
        insert("uta_risk_decisions", decision_id=identity, kind=kind, account_id=account, business_id=business,
            market_snapshot_id=archives["uta_market_history"], artifact_id=archives["uta_code_artifacts"],
            policy_id=archives["uta_risk_policies"], pre_version=0, post_version=1, recorded_at="2026-01-01",
            input_payload="{}", summary_payload="{}")
    if completed:
        specs = (("open-buy", ACCOUNTS[0], "0.02", "CANCELLED", 0),
            ("open-sell", ACCOUNTS[1], "-0.01", "FILLED", 0),
            ("close-sell", ACCOUNTS[0], "-0.01", "FILLED", 1),
            ("close-buy", ACCOUNTS[1], "0.01", "FILLED", 1))
        for name, account, quantity, status, reduce_only in specs:
            oid, fid = prefix + name, "fill:" + name
            did, fdid = "admit:" + name, "execute:" + name
            decision(did, "ORDER_ACCEPTED", account, oid)
            decision(fdid, "FILL_CONFIRMED", account, fid)
            insert("uta_orders", account_id=account, order_id=oid, symbol="BTC-PERP", quantity=quantity,
                limit_price="100", reduce_only=reduce_only, filled_quantity="-0.01" if quantity[0] == "-" else "0.01",
                status=status, version=1, created_at="2026-01-01", admission_decision_id=did, charged_fee="0.0004", fee_notional="1")
            insert("uta_fills", account_id=account, fill_id=fid, order_id=oid, quantity="-0.01" if quantity[0] == "-" else "0.01",
                price="100", realized_pnl="0", fee="0.0004", execution_decision_id=fdid)
            event("fee:" + name, [("customer:" + account, "USD", -40_000), ("system:fees", "USD", 40_000)])
        for seq, buy, sell, buyer, seller in ((1, "open-buy", "open-sell", ACCOUNTS[0], ACCOUNTS[1]),
                (2, "close-buy", "close-sell", ACCOUNTS[1], ACCOUNTS[0])):
            insert("uta_matches", sequence=seq, trade_id="trade:" + str(seq), symbol="BTC-PERP",
                buy_account_id=buyer, buy_order_id=prefix + buy, buy_fill_id="fill:" + buy,
                sell_account_id=seller, sell_order_id=prefix + sell, sell_fill_id="fill:" + sell,
                buy_filled_before="0", sell_filled_before="0", quantity="0.01", price="100", market_version=1,
                buy_version=1, sell_version=1, created_at="2026-01-01")
        repaid = event("repayment", [("customer:" + ACCOUNTS[2], "BTC", -2), ("system:credit-pool", "BTC", 2),
            ("liability:principal:" + ACCOUNTS[2], "BTC", 2), ("system:credit-principal-receivable", "BTC", -2)])
        repayment_result = canonical({"account_id": ACCOUNTS[2], "command_id": prefix + "repay", "asset": "BTC",
            "amount": "0.00000002", "principal_repaid": "0.00000002", "interest_repaid": "0",
            "principal": "0", "interest": "0", "journal_event_id": repaid})
        insert("credit_commands", scope="account:" + ACCOUNTS[2], command_id=prefix + "repay", kind="repaid",
            asset="BTC", amount="0.00000002", source_reference=None, result=repayment_result, journal_event_id=repaid, created_at="2026-01-01")
        for seq, (name, account, kind) in enumerate((("open-buy", ACCOUNTS[0], "SUBMIT_ORDER"),
                ("open-sell", ACCOUNTS[1], "SUBMIT_ORDER"), ("cancel-partial", ACCOUNTS[0], "CANCEL_ORDER"),
                ("close-sell", ACCOUNTS[0], "SUBMIT_ORDER"), ("close-buy", ACCOUNTS[1], "SUBMIT_ORDER"),
                ("repay", ACCOUNTS[2], "REPAY")), 1):
            insert("uta_command_inbox", sequence=seq, command_id=prefix + name, account_id=account, kind=kind,
                payload="{}", state="SUCCEEDED", result=repayment_result if name == "repay" else "{}", error=None, enqueued_at="2026-01-01", completed_at="2026-01-01",
                attempts=0, last_error=None, next_attempt_at=None)
    insert("uta_liabilities", account_id=ACCOUNTS[2], asset="BTC", principal="0" if completed else "0.00000002", interest="0")
    for (owner, asset), units in balances.items():
        insert("ledger_balances", account=owner, asset=asset, units=str(units))
    con.commit()
    con.close()


@contextmanager
def readonly(path):
    con = sqlite3.connect(Path(path).absolute().as_uri() + "?mode=ro", uri=True, isolation_level=None)
    con.row_factory = sqlite3.Row
    try:
        con.execute("PRAGMA query_only=ON")
        con.execute("BEGIN")
        yield con
    finally:
        con.close()


class IndependentFinanceTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.path = self.directory / "synthetic.sqlite3"

    def mutate(self, sql, values=()):
        con = sqlite3.connect(self.path)
        try:
            con.execute(sql, values)
            con.commit()
        finally:
            con.close()

    def observe(self, completed, *, compare=True):
        with readonly(self.path) as con:
            return read_financial(con, 1, completed, compare_golden=compare)

    def test_genesis_and_closed_round_independent_integer_oracle(self):
        fixture(self.path)
        self.assertEqual(self.observe(0)["golden"]["errors"], [])
        self.path.unlink()
        fixture(self.path, completed=1)
        report = self.observe(1)
        self.assertTrue(report["golden"]["passed"], report["golden"])
        self.assertEqual(report["counts"]["ledger_events"], 11)
        self.assertEqual(report["gross_debt"][0]["principal_minor"], 0)
        self.assertEqual(len(report["command_inbox"]), 6)
        self.assertEqual(report["retry_alerts"], [])

    def test_real_readonly_snapshot_has_no_creation_ddl_or_mtime_effect(self):
        fixture(self.path, completed=1)
        before_files = set(self.directory.iterdir())
        before = {p.name: (p.stat().st_mtime_ns, p.read_bytes()) for p in before_files}
        with readonly(self.path) as con:
            with self.assertRaises(sqlite3.OperationalError):
                con.execute("CREATE TABLE forbidden (value)")
            read_financial(con, 1, 1, compare_golden=True)
        self.assertEqual(set(self.directory.iterdir()), before_files)
        self.assertEqual({p.name: (p.stat().st_mtime_ns, p.read_bytes()) for p in before_files}, before)
        with self.assertRaises(sqlite3.OperationalError):
            with readonly(self.directory / "missing.sqlite3"):
                pass
        self.assertFalse((self.directory / "missing.sqlite3").exists())

    def test_query_only_and_transaction_are_mandatory(self):
        fixture(self.path)
        con = sqlite3.connect(self.path)
        self.addCleanup(con.close)
        con.row_factory = sqlite3.Row
        with self.assertRaisesRegex(ValueError, "query-only"):
            read_financial(con, 1, 0)
        con.execute("BEGIN")
        with self.assertRaisesRegex(ValueError, "query-only"):
            read_financial(con, 1, 0)

    def test_midround_does_not_compare_previous_round_budget(self):
        fixture(self.path, completed=1)
        report = self.observe(0, compare=False)
        self.assertFalse(report["golden"]["compared"])
        self.assertFalse(report["golden"]["passed"])
        self.assertEqual(report["golden"]["errors"], [])
        self.assertFalse(self.observe(0)["golden"]["passed"])

    def test_final_mismatches_and_future_round_pairing_fail(self):
        fixture(self.path, completed=1)
        self.mutate("UPDATE ledger_balances SET units='1' WHERE account=? AND asset='USD'", ("customer:" + ACCOUNTS[2],))
        self.assertIn("complete_gross_owner_asset_budget", self.observe(1)["golden"]["errors"])
        self.mutate("UPDATE uta_matches SET sell_order_id=replace(sell_order_id,'r000000001','r000000002') WHERE sequence=1")
        self.assertIn("per_round_match_pair", self.observe(1)["golden"]["errors"])

    def test_any_retry_and_unknown_last_error_remain_alerts_and_redacted(self):
        fixture(self.path, completed=1)
        secret = "private-error-with-secret-and-internal-host"
        self.mutate("UPDATE uta_command_inbox SET attempts=1,last_error=? WHERE sequence=1", (secret,))
        report = self.observe(1)
        self.assertEqual(report["retry_alerts"][0]["cause"], "unknown")
        self.assertEqual(report["retry_alerts"][0]["attempts"], 1)
        self.assertEqual(report["command_inbox"][0]["last_error_code"], "unknown_redacted")
        self.assertNotIn(secret, json.dumps(report))
        self.assertIn("internal_retry_observed", report["golden"]["errors"])
        self.mutate("UPDATE uta_command_inbox SET attempts=0 WHERE sequence=1")
        self.assertEqual(len(self.observe(1)["retry_alerts"]), 1)

    def test_missing_required_column_fails_closed(self):
        fixture(self.path)
        self.mutate("ALTER TABLE uta_command_inbox RENAME COLUMN attempts TO missing_attempts")
        with self.assertRaises(sqlite3.OperationalError):
            self.observe(0)

    def test_control_lane_quarantine_and_retries_are_not_hidden(self):
        fixture(self.path, completed=1)
        con = sqlite3.connect(self.path)
        try:
            con.execute("INSERT INTO uta_command_inbox (sequence,command_id,account_id,kind,payload,state,attempts,last_error,error) VALUES (7,'private-control-cid',NULL,'PUBLISH_MARKET','{}','QUARANTINED',3,'technical_execution_failure','{}')")
            con.commit()
        finally:
            con.close()
        report = self.observe(1)
        control = report["command_inbox"][-1]
        self.assertEqual(len(report["command_inbox"]), 7)
        self.assertTrue(control["control_lane"])
        self.assertTrue(control["quarantined"])
        self.assertEqual(control["attempts"], 3)
        self.assertEqual(control["last_error_code"], "technical_execution_failure")
        self.assertEqual(report["retry_alerts"][-1]["cause"], "unknown")
        self.assertIn("non_succeeded_inbox", report["golden"]["errors"])

    def test_reader_sql_is_ro_and_never_accesses_writer_tables(self):
        fixture(self.path, completed=1)
        reads = set()
        def authorize(action, one, two, database, source):
            if action == sqlite3.SQLITE_READ:
                reads.add(one)
                self.assertNotIn("writer", one)
            self.assertNotIn(action, (sqlite3.SQLITE_INSERT, sqlite3.SQLITE_UPDATE,
                sqlite3.SQLITE_DELETE, sqlite3.SQLITE_CREATE_TABLE))
            return sqlite3.SQLITE_OK
        with readonly(self.path) as con:
            con.set_authorizer(authorize)
            self.assertTrue(read_financial(con, 1, 1, compare_golden=True)["golden"]["passed"])
        self.assertIn("uta_command_inbox", reads)
        self.assertIn("ledger_postings", reads)

    def test_exact_repayment_principal_receipt_is_required(self):
        fixture(self.path, completed=1)
        self.mutate("UPDATE credit_commands SET result='{}' WHERE kind='repaid'")
        self.assertIn("repayment_principal_receipt", self.observe(1)["golden"]["errors"])

    def test_business_watermark_excludes_noisy_private_writer_state(self):
        fixture(self.path)
        before = self.observe(0)["watermark"]
        self.mutate("CREATE TABLE writer_fence_lease (owner_nonce TEXT, observed_ns INTEGER)")
        self.mutate("INSERT INTO writer_fence_lease VALUES ('do-not-read-or-export', 1)")
        self.assertEqual(self.observe(0)["watermark"], before)
        self.mutate("UPDATE uta_accounts SET version=1 WHERE account_id=?", (ACCOUNTS[0],))
        self.assertNotEqual(self.observe(0)["watermark"], before)

    def test_watermark_ignores_row_order_and_retains_duplicate_multiplicity(self):
        fixture(self.path)
        before = self.observe(0)["watermark"]
        self.assertEqual(before["format"], 2)
        self.mutate("DELETE FROM uta_accounts WHERE account_id=?", (ACCOUNTS[0],))
        self.mutate("INSERT INTO uta_accounts VALUES (?,0)", (ACCOUNTS[0],))
        self.assertEqual(self.observe(0)["watermark"], before)
        self.mutate("INSERT INTO uta_accounts VALUES (?,0)", (ACCOUNTS[0],))
        self.assertNotEqual(self.observe(0)["watermark"], before)
        self.assertIn("fixed_three_accounts", self.observe(0)["golden"]["errors"])

    def test_foreign_key_check_failure_is_a_golden_error(self):
        fixture(self.path)
        self.mutate("CREATE TABLE parent (id INTEGER PRIMARY KEY)")
        self.mutate("CREATE TABLE child (parent_id INTEGER REFERENCES parent(id))")
        self.mutate("INSERT INTO child VALUES (123)")
        report = self.observe(0)
        self.assertFalse(report["golden"]["passed"])
        self.assertIn("sqlite_foreign_key_check_failed", report["golden"]["errors"])
        self.assertEqual(self.observe(0, compare=False)["golden"]["errors"], [])

    def test_unavailable_integrity_checks_fail_closed_without_raw_errors(self):
        fixture(self.path)
        def authorize(action, one, two, database, source):
            if action == sqlite3.SQLITE_PRAGMA and one in {"quick_check", "foreign_key_check"}:
                return sqlite3.SQLITE_DENY
            return sqlite3.SQLITE_OK
        with readonly(self.path) as con:
            con.set_authorizer(authorize)
            report = read_financial(con, 1, 0, compare_golden=True)
        self.assertFalse(report["golden"]["passed"])
        self.assertIn("sqlite_quick_check_failed_unavailable", report["golden"]["errors"])
        self.assertIn("sqlite_foreign_key_check_failed_unavailable", report["golden"]["errors"])

    def test_archive_canonical_content_and_unreferenced_rows_checked(self):
        fixture(self.path, completed=1)
        self.mutate("INSERT INTO uta_code_artifacts VALUES ('artifact:bad','{}')")
        self.assertIn("archive_content_id", self.observe(1)["golden"]["errors"])

    def test_nonsynthetic_identifiers_are_hash_redacted(self):
        fixture(self.path, completed=1)
        self.mutate("UPDATE uta_command_inbox SET command_id='secret-control-id',account_id=NULL,kind='private-kind' WHERE sequence=1")
        report = self.observe(1, compare=False)
        entry = report["command_inbox"][0]
        self.assertTrue(entry["control_lane"])
        self.assertTrue(entry["command_id"].startswith("sha256:"))
        self.assertNotIn("secret-control-id", json.dumps(report))
        self.assertNotIn("private-kind", json.dumps(report))


if __name__ == "__main__":
    unittest.main()
