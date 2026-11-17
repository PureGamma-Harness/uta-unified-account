"""Actual disposable process worker for crash-after-COMMIT credit acceptance."""
from datetime import datetime, timezone
from decimal import Decimal as D
from hashlib import sha256
import json
import os
from pathlib import Path
import sys

from uta.credit_audit_v2 import CreditAuditV2, canonical
from uta.credit_fifo_v2 import InternalCreditFIFO
from uta.credit_native_v2 import acquire_credit_v2, install_internal_credit_v2
from uta.existing_services import open_existing_services
from uta.storage import Database
from uta.writer_fence import WriterFence


def clock():
    return datetime(2026, 11, 17, tzinfo=timezone.utc)


def private_checkpoint(path, data):
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w") as output:
        output.write(canonical(data)+"\n")
        output.flush()
        os.fsync(output.fileno())


def main():
    mode, database_path, envelope_path, checkpoint_path = sys.argv[1:]
    database = Database(database_path)
    if mode == "commit_then_crash":
        bootstrap = open_existing_services(database, clock=clock)
        install_internal_credit_v2(database, bootstrap.exchange, bootstrap.credit, Path(envelope_path).read_text())
        token = acquire_credit_v2(database, "synthetic:crashing-credit-worker", 15)
        services = open_existing_services(database.for_writer(token), clock=clock)
        fifo = InternalCreditFIFO(services.exchange, services.credit)
        fifo.enqueue_borrow("alice", "crash-loan", "BTC", D(".4"),
            actor_id="synthetic:process-borrower", source_reference="synthetic:process:loan")
        fifo.process_one()  # Actual COMMIT returns; the application reply is discarded.
        fifo.enqueue_repay("alice", "crash-repay", "BTC", D(".1"),
            actor_id="synthetic:process-borrower", source_reference="synthetic:process:repay")
        fifo.process_one()  # Same original financial COMMIT semantics, no reply delivered.
        private_checkpoint(checkpoint_path, {"phase": "after_actual_borrow_and_repay_COMMIT_before_client_reply",
            "pid": os.getpid(), "clock_scope": "static synthetic financial clock; real native bootclock lease",
            "command_ids": ["crash-loan", "crash-repay"]})
        os._exit(73)  # Real disposable worker exits without release/normal shutdown.
    if mode != "recover":
        raise ValueError("unknown process-worker test mode")
    token = acquire_credit_v2(database, "synthetic:replacement-credit-worker", 15)
    services = open_existing_services(database.for_writer(token), clock=clock)
    fifo = InternalCreditFIFO(services.exchange, services.credit)
    before = {cid: fifo.status(cid) for cid in ("crash-loan", "crash-repay")}
    assert all(row["state"] == "SUCCEEDED" for row in before.values())
    assert fifo.enqueue_borrow("alice", "crash-loan", "BTC", D(".4"),
        actor_id="synthetic:process-borrower", source_reference="synthetic:process:loan") == before["crash-loan"]
    assert fifo.enqueue_repay("alice", "crash-repay", "BTC", D(".1"),
        actor_id="synthetic:process-borrower", source_reference="synthetic:process:repay") == before["crash-repay"]
    assert fifo.process_one() is None
    with services.exchange.database.read_transaction() as connection:
        row = connection.execute("SELECT decision_id FROM uta_credit_decisions WHERE command_id='crash-loan'").fetchone()
        actual = {"counts": {table: connection.execute("SELECT COUNT(*) FROM "+table).fetchone()[0]
            for table in ("credit_v2_sources", "credit_v2_intents", "uta_credit_decisions", "ledger_events")},
            "debt": tuple(connection.execute("SELECT principal,interest FROM uta_liabilities WHERE account_id='alice' AND asset='BTC'").fetchone()),
            "customer_btc_units": connection.execute("SELECT units FROM ledger_balances WHERE account='customer:alice' AND asset='BTC'").fetchone()[0],
            "pool_btc_units": connection.execute("SELECT units FROM ledger_balances WHERE account='system:credit-pool' AND asset='BTC'").fetchone()[0],
            "foreign_key_check": [tuple(item) for item in connection.execute("PRAGMA foreign_key_check")]}
    assert CreditAuditV2(services.exchange, services.credit).replay(row[0])["matches"]
    assert services.ledger.verify() == 4
    assert not services.exchange.readiness()["ready"]
    WriterFence(database).release(token)
    print(canonical({"pid": os.getpid(), "generation": token.generation,
        "original_receipt_sha256": {cid: sha256(canonical(value).encode()).hexdigest() for cid, value in before.items()},
        "actual": actual, "decision_id": row[0], "scope": "new actual process recovered original CIDs after prior COMMIT/reply loss and real lease expiry"}))


if __name__ == "__main__":
    main()
