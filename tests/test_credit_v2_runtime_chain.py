"""Actual native/source/FIFO/audit/ledger chain; never a dummy audit callback."""
from datetime import timedelta
from decimal import Decimal as D
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import unittest

from tests.credit_v2_runtime_fixture import SyntheticCreditAuthority, actual_credit_observation
from tests.sqlite_connection_observer import trace_new_sqlite_connections
from uta.credit_audit_v2 import CreditAuditV2, canonical
from uta.credit_audit_v2_replay import replay_bundle
from uta.existing_services import open_existing_services
from uta.service import ServiceError


class CreditV2RuntimeChainTests(unittest.TestCase):
    def authority(self, **options):
        fixture = SyntheticCreditAuthority(**options)
        self.addCleanup(fixture.close)
        return fixture.install_and_open()

    def test_actual_borrow_only_preserves_original_db_for_independent_observation(self):
        fixture = self.authority()
        exchange, credit, fifo = fixture.services.exchange, fixture.services.credit, fixture.fifo
        self.assertFalse(exchange.readiness()["ready"])
        self.assertEqual(fifo.enqueue_borrow("alice", "loan-1", "BTC", D(".4"),
            actor_id="synthetic:integration-borrower", source_reference="synthetic:integration:loan-1")["state"], "PENDING")
        receipt = fifo.process_one()
        self.assertEqual((receipt["state"], receipt["result"]["principal"]), ("SUCCEEDED", "0.4"))
        with exchange.database.read_transaction() as connection:
            observed = actual_credit_observation(connection, "loan-1")
            self.assertEqual(connection.execute("PRAGMA foreign_key_check").fetchall(), [])
        bundle = observed["decision_bundle"]
        self.assertTrue(replay_bundle(bundle)["matches"])
        reopened = open_existing_services(exchange.database, clock=lambda: fixture.now)
        self.assertEqual(reopened.ledger.verify(), observed["journal"]["sequence"])
        self.assertEqual(fifo.status("loan-1"), receipt)
        self.assertEqual(fifo.enqueue_borrow("alice", "loan-1", "BTC", D(".4"),
            actor_id="synthetic:integration-borrower", source_reference="synthetic:integration:loan-1"), receipt)
        self.assertIsNone(fifo.process_one())
        with self.assertRaises(ServiceError) as refused:
            credit.borrow("alice", "no-public-scope", "BTC", D(".01"))
        self.assertEqual((refused.exception.code, refused.exception.status), ("unsupported_credit_operation", 501))
        with exchange.database.read_transaction() as connection:
            self.assertEqual(actual_credit_observation(connection, "loan-1"), observed)
            self.assertEqual([connection.execute("SELECT COUNT(*) FROM "+table).fetchone()[0]
                for table in ("credit_v2_sources", "credit_v2_intents", "uta_credit_decisions")], [1, 1, 1])
        output = os.environ.get("UTA_CREDIT_V2_CAPTURE_DIRECTORY")
        if output:
            directory = Path(output)
            directory.mkdir(parents=True, exist_ok=True)
            raw = canonical(observed)
            (directory/"actual-borrow-observation.json").write_text(raw+"\n")
            print(json.dumps({"actual_capture_sha256": sha256(raw.encode()).hexdigest(),
                "scope": "actual synthetic native loan/COMMIT/reopen; private original DB stops after borrow for independent SQL",
                "decision_id": bundle["decision"]["decision_id"]}, sort_keys=True))

    def test_actual_borrow_commit_and_reopen_have_complete_original_evidence(self):
        fixture = self.authority()
        fifo, exchange, credit = fixture.fifo, fixture.services.exchange, fixture.services.credit
        readiness = exchange.readiness()
        self.assertEqual(readiness["reason"], "internal_credit_authority_not_trading")
        self.assertFalse(readiness["ready"])
        accepted = fifo.enqueue_borrow("alice", "loan-1", "BTC", D(".4"),
            actor_id="synthetic:integration-borrower", source_reference="synthetic:integration:loan-1")
        self.assertEqual((accepted["state"], accepted["ack"]), ("PENDING", "durably_queued"))
        result = fifo.process_one()
        self.assertEqual((result["command_id"], result["state"]), ("loan-1", "SUCCEEDED"))
        self.assertEqual((result["result"]["principal"], result["result"]["interest"]), ("0.4", "0"))
        with exchange.database.read_transaction() as connection:
            observed = actual_credit_observation(connection, "loan-1")
            self.assertEqual(connection.execute("PRAGMA foreign_key_check").fetchall(), [])
            self.assertEqual(len(observed["expected_postings"]), 4)
            self.assertEqual(observed["journal"]["sealed"], 1)
            self.assertEqual(observed["intent"]["market_dependency"], "SID")
            self.assertEqual(observed["inbox"]["result"], observed["credit"]["result"])
            counts = [connection.execute("SELECT COUNT(*) FROM "+table).fetchone()[0]
                for table in ("credit_v2_sources", "credit_v2_intents", "uta_credit_decisions", "ledger_events")]
        bundle = observed["decision_bundle"]
        self.assertTrue(replay_bundle(bundle)["matches"])
        self.assertTrue(CreditAuditV2(exchange, credit).replay(bundle["decision"]["decision_id"])["matches"])
        reopened = open_existing_services(exchange.database, clock=lambda: fixture.now)
        self.assertIsNot(reopened.exchange, exchange)
        self.assertIsNot(reopened.credit, credit)
        self.assertEqual(reopened.ledger.verify(), counts[-1])
        self.assertEqual(fifo.status("loan-1"), result)
        self.assertEqual(fifo.enqueue_borrow("alice", "loan-1", "BTC", D(".4"),
            actor_id="synthetic:integration-borrower", source_reference="synthetic:integration:loan-1"), result)
        self.assertIsNone(fifo.process_one())
        with exchange.database.read_transaction() as connection:
            self.assertEqual(actual_credit_observation(connection, "loan-1"), observed)
            self.assertEqual([connection.execute("SELECT COUNT(*) FROM "+table).fetchone()[0]
                for table in ("credit_v2_sources", "credit_v2_intents", "uta_credit_decisions", "ledger_events")], counts)
        fifo.enqueue_repay("alice", "partial-repay-1", "BTC", D(".1"),
            actor_id="synthetic:integration-borrower", source_reference="synthetic:integration:partial-repay-1")
        repayment = fifo.process_one()
        self.assertEqual((repayment["state"], repayment["result"]["principal"], repayment["result"]["interest"]),
                         ("SUCCEEDED", "0.3", "0"))
        self.assertEqual(fifo.status("loan-1"), result)
        self.assertTrue(CreditAuditV2(exchange, credit).replay(bundle["decision"]["decision_id"])["matches"])
        self.assertEqual(credit.borrow("alice", "loan-1", "BTC", D(".4")), result["result"])
        with exchange.database.read_transaction() as connection:
            repaid = actual_credit_observation(connection, "partial-repay-1")
            self.assertEqual((repaid["intent"]["market_dependency"], repaid["intent"]["market_snapshot_id"],
                repaid["decision_bundle"], len(repaid["journal"]["postings"])), ("NONE", None, None, 4))
            self.assertEqual(actual_credit_observation(connection, "loan-1"), observed)
            final_counts = [connection.execute("SELECT COUNT(*) FROM "+table).fetchone()[0]
                for table in ("credit_v2_sources", "credit_v2_intents", "uta_credit_decisions", "ledger_events")]
            self.assertEqual(final_counts, [counts[0]+1, counts[1]+1, counts[2], counts[3]+1])
            self.assertEqual(connection.execute("PRAGMA foreign_key_check").fetchall(), [])
        self.assertEqual(reopened.ledger.verify(), final_counts[-1])
        with self.assertRaises(ServiceError) as refused:
            credit.borrow("alice", "no-public-scope", "BTC", D(".01"))
        self.assertEqual((refused.exception.code, refused.exception.status), ("unsupported_credit_operation", 501))
        self.assertIsNone(fixture.bootstrap.database.writer_token)
        output = os.environ.get("UTA_CREDIT_V2_CAPTURE_DIRECTORY")
        if output:
            directory = Path(output)
            directory.mkdir(parents=True, exist_ok=True)
            raw = canonical(observed)
            (directory/"actual-borrow-observation.json").write_text(raw+"\n")
            (directory/"actual-partial-repay-observation.json").write_text(canonical(repaid)+"\n")
            print(json.dumps({"actual_capture_sha256": sha256(raw.encode()).hexdigest(),
                "scope": "actual synthetic BORROW/partial REPAY, dedicated historical replay and same-process reopen; process restart pending",
                "decision_id": bundle["decision"]["decision_id"], "counts": final_counts}, sort_keys=True))

    def test_initial_quota_refusal_rolls_back_then_original_fifo_can_continue(self):
        fixture = self.authority()
        fifo, exchange = fixture.fifo, fixture.services.exchange
        with exchange.database.read_transaction() as connection:
            before = {name: [tuple(row) for row in connection.execute("SELECT * FROM "+name+" ORDER BY rowid")]
                for name in ("uta_accounts", "uta_liabilities", "ledger_events", "ledger_postings", "ledger_balances", "credit_commands", "uta_events")}
        fifo.enqueue_borrow("alice", "too-much", "BTC", D(".51"), actor_id="synthetic:integration-borrower",
                            source_reference="synthetic:integration:too-much")
        refused = fifo.process_one()
        self.assertEqual((refused["state"], refused["error"]["code"], refused["error"]["status"]), ("REJECTED", "credit_limit", 409))
        with exchange.database.read_transaction() as connection:
            after = {name: [tuple(row) for row in connection.execute("SELECT * FROM "+name+" ORDER BY rowid")] for name in before}
            self.assertEqual(after, before)
            self.assertEqual([connection.execute("SELECT COUNT(*) FROM "+name).fetchone()[0]
                for name in ("credit_v2_sources", "credit_v2_intents", "uta_credit_decisions")], [1, 0, 0])
        fifo.enqueue_borrow("alice", "after-refusal", "BTC", D(".4"), actor_id="synthetic:integration-borrower",
                            source_reference="synthetic:integration:after-refusal")
        self.assertEqual(fifo.process_one()["state"], "SUCCEEDED")

    def test_real_fifo_repay_pays_interest_first_during_halt_and_stale_market(self):
        fixture = self.authority(opening_interest=True)
        exchange, credit, fifo = fixture.services.exchange, fixture.services.credit, fixture.fifo
        from uta.credit_native_v2 import metadata_scope
        with exchange._transaction() as connection:
            with metadata_scope(credit, connection, operation="SET_HALT"):
                exchange._set_kill_switch(connection, True)
        fixture.now += timedelta(days=1)  # Own synthetic fixture clock only.
        fifo.enqueue_repay("alice", "repay-stale-halt", "BTC", D(".1"), actor_id="synthetic:integration-borrower",
                           source_reference="synthetic:integration:repay-stale-halt")
        statements = []
        with trace_new_sqlite_connections(statements):
            receipt = fifo.process_one()
        self.assertEqual(receipt["state"], "SUCCEEDED")
        self.assertEqual({field: receipt["result"][field] for field in
            ("principal", "interest", "principal_repaid", "interest_repaid")},
            {"principal": "0.35", "interest": "0", "principal_repaid": "0.05", "interest_repaid": "0.05"})
        self.assertFalse([sql for sql in statements if re.search(r'\b(?:FROM|JOIN)\s+["`\[]?uta_market(?:_history)?\b', sql, re.I)])
        with exchange.database.read_transaction() as connection:
            observed = actual_credit_observation(connection, "repay-stale-halt")
            self.assertEqual((observed["intent"]["market_dependency"], observed["intent"]["market_snapshot_id"],
                              observed["intent"]["operation_id"], observed["decision_bundle"]), ("NONE", None, None, None))
            self.assertEqual(len(observed["expected_postings"]), 7)
            self.assertEqual(len(observed["journal"]["postings"]), 7)
            self.assertEqual(connection.execute("PRAGMA foreign_key_check").fetchall(), [])
        self.assertEqual(fifo.status("repay-stale-halt"), receipt)


if __name__ == "__main__":
    unittest.main()
