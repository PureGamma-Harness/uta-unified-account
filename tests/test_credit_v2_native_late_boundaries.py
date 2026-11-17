"""Real staged audit/loan obligations survive neither late failure nor context loss."""
from datetime import timedelta
from decimal import Decimal as D
import json
import os
import sqlite3
import unittest

from tests.credit_v2_runtime_fixture import SyntheticCreditAuthority
from uta.credit_native_v2 import _actual_guard, operation_scope
from uta.writer_fence import WriterFenceError


class NativeLateBoundaryTests(unittest.TestCase):
    def test_complete_real_staged_loan_cannot_commit_after_context_loss_or_late_failure(self):
        self.assertNotIn("UTA_CREDIT_V2_PRIVATE_DB_DIRECTORY", os.environ)
        fixture = SyntheticCreditAuthority(additional_accounts=("bob",))
        self.addCleanup(fixture.close)
        fixture.install_and_open()
        exchange, credit, fifo = fixture.services.exchange, fixture.services.credit, fixture.fifo
        fifo.enqueue_borrow("alice", "late-loan", "BTC", D(".1"), actor_id="synthetic:late-boundary",
            source_reference="synthetic:late:loan")
        tables = ("uta_accounts", "uta_liabilities", "credit_commands", "ledger_events", "ledger_postings",
                  "ledger_balances", "uta_events", "credit_v2_intents", "credit_v2_expected_postings", "uta_credit_decisions")
        def snapshot():
            with exchange.database.read_transaction() as connection:
                return {name: [tuple(row) for row in connection.execute("SELECT * FROM " + name + " ORDER BY rowid")]
                        for name in tables}
        before = snapshot()
        original_now = fixture.now
        observations = []
        for scenario in ("lost_operation_before_closing", "lost_context_after_closing", "stale_before_closing",
                         "stale_before_commit", "unrelated_account"):
            with self.subTest(scenario=scenario):
                fixture.now = original_now
                staged = False
                with self.assertRaises(WriterFenceError) as refused:
                    with exchange._transaction() as connection:
                        connection.execute("SAVEPOINT real_outer")
                        guard = _actual_guard(credit.database, connection, "financial")
                        try:
                            with operation_scope(credit, connection, command_id="late-loan"):
                                result = credit._borrow(connection, "alice", "late-loan", "BTC", D(".1"))
                                fifo._terminal(connection, "late-loan", result=result)
                                self.assertEqual(connection.execute("SELECT state FROM uta_command_inbox WHERE command_id='late-loan'").fetchone()[0], "SUCCEEDED")
                                self.assertEqual(connection.execute("SELECT COUNT(*) FROM uta_credit_decisions WHERE command_id='late-loan'").fetchone()[0], 1)
                                self.assertEqual(connection.execute("SELECT COUNT(*) FROM credit_commands WHERE command_id='late-loan'").fetchone()[0], 1)
                                self.assertEqual(connection.execute("SELECT COUNT(*) FROM ledger_events e JOIN credit_v2_intents i ON i.journal_id=e.event_id WHERE i.command_id='late-loan' AND e.sealed=1").fetchone()[0], 1)
                                staged = True
                                if scenario == "lost_operation_before_closing":
                                    # Negative memory-loss fault on the actual
                                    # registered guard, never a forged grant.
                                    guard.credit_v2_operation = None
                                elif scenario == "stale_before_closing":
                                    fixture.now += timedelta(days=1)
                                elif scenario == "unrelated_account":
                                    connection.execute("UPDATE uta_accounts SET version=version+1 WHERE account_id='bob'")
                        except (WriterFenceError, sqlite3.DatabaseError):
                            connection.execute("ROLLBACK TO real_outer")
                        if scenario == "lost_context_after_closing":
                            # Leave actual complete staged rows present. The
                            # final verifier must not skip them for None.
                            guard.credit_v2_context = None
                        elif scenario == "stale_before_commit":
                            fixture.now += timedelta(days=1)
                        connection.execute("RELEASE real_outer")
                fixture.now = original_now
                self.assertTrue(staged, "each fault must follow actual full audited financial staging")
                self.assertEqual(snapshot(), before)
                self.assertEqual(fifo.status("late-loan")["state"], "PENDING")
                observations.append({"scenario": scenario, "outer_commit_error": refused.exception.code,
                    "complete_actual_staged_borrow_before_fault": staged, "financial_snapshot_unchanged": True,
                    "original_command_state": "PENDING"})
        print(json.dumps({"actual_native_late_boundaries": observations,
                          "faults": "own disposable DB/context and synthetic clock only"}, sort_keys=True))


if __name__ == "__main__":
    unittest.main()
