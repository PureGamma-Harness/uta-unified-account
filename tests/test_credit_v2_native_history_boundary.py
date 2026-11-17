"""Actual native history candidates, fail-closed effects and physical rollback."""
from decimal import Decimal as D
import os
import sqlite3
import unittest

from tests.credit_v2_runtime_fixture import SyntheticCreditAuthority
from uta.credit_native_v2 import operation_scope
from uta.writer_fence import WriterFenceError


class NativeHistoryBoundaryTests(unittest.TestCase):
    def authority(self, **options):
        self.assertNotIn("UTA_CREDIT_V2_PRIVATE_DB_DIRECTORY", os.environ)
        fixture = SyntheticCreditAuthority(**options)
        self.addCleanup(fixture.close)
        return fixture.install_and_open()

    def snapshot(self, fixture):
        with fixture.services.exchange.database.read_transaction() as connection:
            return {table: [tuple(row) for row in connection.execute("SELECT * FROM " + table + " ORDER BY rowid")]
                for table in ("uta_accounts", "uta_liabilities", "credit_commands", "ledger_events", "ledger_postings",
                    "ledger_balances", "uta_events", "credit_v2_intents", "credit_v2_expected_postings", "uta_credit_decisions")}

    def test_second_same_and_different_account_borrow_commit_with_historical_intents(self):
        fixture = self.authority(additional_accounts=("bob",))
        fifo = fixture.fifo
        for account, cid, amount, expected_principal in (("alice", "first", ".2", "0.2"),
                ("alice", "second", ".1", "0.3"), ("bob", "third", ".1", "0.1")):
            fifo.enqueue_borrow(account, cid, "BTC", D(amount), actor_id="synthetic:history-boundary",
                source_reference="synthetic:history:" + cid)
            receipt = fifo.process_one()
            self.assertEqual((receipt["state"], receipt["result"]["principal"]), ("SUCCEEDED", expected_principal))
        with fixture.services.exchange.database.read_transaction() as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM credit_v2_intents").fetchone()[0], 3)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM uta_credit_decisions").fetchone()[0], 3)
            self.assertEqual(connection.execute("PRAGMA foreign_key_check").fetchall(), [])
        self.assertEqual(fixture.services.ledger.verify(), 6)

    def test_missing_actual_intent_and_current_wrong_row_or_digest_still_poison_commit(self):
        fixture = self.authority()
        exchange, credit, fifo = fixture.services.exchange, fixture.services.credit, fixture.fifo
        fifo.enqueue_borrow("alice", "current", "BTC", D(".1"), actor_id="synthetic:history-boundary",
            source_reference="synthetic:history:current")
        before = self.snapshot(fixture)
        # Each attempted transaction uses the same original pending command.
        # No successful financial effect or fake scope is used as a shortcut.
        for scenario in ("no_scope", "rolled_back_intent", "wrong_current_row", "wrong_current_digest", "caught_ddl"):
            with self.subTest(scenario=scenario):
                refusal = []
                with self.assertRaises(WriterFenceError):
                    with exchange._transaction() as connection:
                        connection.execute("SAVEPOINT real_outer")
                        try:
                            if scenario == "no_scope":
                                try:
                                    connection.execute("UPDATE uta_accounts SET version=version+1 WHERE account_id='alice'")
                                except sqlite3.DatabaseError as error:
                                    refusal.append(getattr(error, "sqlite_errorcode", None))
                            else:
                                with operation_scope(credit, connection, command_id="current") as view:
                                    if scenario == "rolled_back_intent":
                                        connection.execute("ROLLBACK TO real_outer")
                                    try:
                                        if scenario == "wrong_current_digest":
                                            self.assertEqual(connection.execute("SELECT uta_credit_v2_gate('ACCOUNT',?,?,?, ?, ?)",
                                                ("current", "credit-intent:" + "0" * 64, "alice", view.pre_version, view.pre_version + 1)).fetchone()[0], 0)
                                            refusal.append("current_digest_zero_permission")
                                        elif scenario == "caught_ddl":
                                            connection.execute("DROP TRIGGER credit_v2_gate_posting")
                                        else:
                                            increment = 2 if scenario == "wrong_current_row" else 1
                                            connection.execute("UPDATE uta_accounts SET version=version+? WHERE account_id='alice'", (increment,))
                                    except sqlite3.DatabaseError as error:
                                        refusal.append(getattr(error, "sqlite_errorcode", None))
                        except WriterFenceError:
                            pass  # Catching the scoped failure cannot authorize COMMIT.
                        connection.execute("ROLLBACK TO real_outer")
                        connection.execute("RELEASE real_outer")
                self.assertTrue(refusal, "the actual protected mutation must have been attempted and refused")
                self.assertEqual(self.snapshot(fixture), before)
                self.assertEqual(fifo.status("current")["state"], "PENDING")


if __name__ == "__main__":
    unittest.main()
