"""Actual local queue catalog and closed intake components, no V2 loan claim."""
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest

from uta.credit import CreditService
from uta.credit_fifo_v2 import InternalCreditFIFO, is_business_rejection, verify_existing_queue
from uta.credit_transition import CreditTransitionError
from uta.durable_commands import QueueStore, _canonical
from uta.service import ExchangeService, ServiceError
from uta.storage import Database, StorageError


class CreditFIFOComponentTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory(prefix="uta-credit-v2-fifo-component-")
        self.addCleanup(self.temp.cleanup)
        self.db = Database(Path(self.temp.name)/"synthetic.sqlite3")
        self.exchange = ExchangeService(self.db, {"USD": 8, "BTC": 8})
        self.credit = CreditService(self.exchange)
        self.queue = QueueStore(self.db, queue_capacity=7, cancel_reserve=2, market_capacity=1, initialize=True)

    def snapshot(self):
        with self.db.read_transaction() as connection:
            return ([tuple(row) for row in connection.execute("SELECT * FROM sqlite_master ORDER BY name")],
                [tuple(row) for row in connection.execute("SELECT * FROM uta_command_inbox")])

    def test_actual_compiled_base_queue_validates_without_writes(self):
        before = self.snapshot()
        with self.db.read_transaction() as connection:
            statements = []
            connection.set_trace_callback(statements.append)
            self.assertEqual(verify_existing_queue(connection),
                {"queue_capacity": 7, "cancel_reserve": 2, "market_capacity": 1})
            connection.set_trace_callback(None)
        self.assertEqual(before, self.snapshot())
        self.assertFalse(any(sql.lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE", "CREATE", "ALTER", "DROP")) for sql in statements))

    def test_same_name_weakened_guard_is_not_accepted(self):
        with self.db.transaction() as connection:
            connection.execute("DROP TRIGGER uta_command_inbox_terminal_immutable")
            connection.execute("CREATE TRIGGER uta_command_inbox_terminal_immutable BEFORE UPDATE ON uta_command_inbox WHEN 0 BEGIN SELECT RAISE(ABORT,'terminal command receipt is immutable'); END")
        before = self.snapshot()
        with self.db.read_transaction() as connection, self.assertRaises(StorageError):
            verify_existing_queue(connection)
        self.assertEqual(before, self.snapshot())

    def test_extra_inbox_constraint_is_rejected_without_repair(self):
        with self.db.transaction() as connection:
            connection.execute("CREATE UNIQUE INDEX misleading_one_account ON uta_command_inbox(account_id)")
        before = self.snapshot()
        with self.db.read_transaction() as connection, self.assertRaises(StorageError):
            verify_existing_queue(connection)
        self.assertEqual(before, self.snapshot())

    def test_default_no_cap_constructor_cannot_open_intake(self):
        before = self.snapshot()
        with self.assertRaises(ServiceError) as error:
            InternalCreditFIFO(self.exchange, self.credit)
        self.assertEqual((error.exception.code, error.exception.status), ("unsupported_credit_operation", 501))
        self.assertEqual(before, self.snapshot())

    def test_generic_queue_does_not_gain_a_borrow_command(self):
        with self.assertRaises(ServiceError) as error:
            _canonical("BORROW", {"account_id": "alice", "asset": "BTC", "amount": "1"})
        self.assertEqual(error.exception.code, "unsupported_durable_command")

    def test_known_quota_refusal_keeps_its_original_pure_cause(self):
        cause = CreditTransitionError("credit_limit", "exact integer quota refused", 409)
        error = ServiceError("credit_limit", str(cause), 409)
        error.__cause__ = cause
        self.assertTrue(is_business_rejection("BORROW", error))
        self.assertIs(error.__cause__, cause)
        self.assertFalse(is_business_rejection("REPAY", ServiceError("credit_pool_empty", "pool", 409)))

    def test_hidden_sql_or_storage_failure_remains_technical_even_with_quota_code(self):
        for hidden in (sqlite3.OperationalError("synthetic disk unavailable"), StorageError("actual storage failure")):
            cause = CreditTransitionError("credit_limit", "quota-looking wrapper", 409)
            cause.__cause__ = hidden
            error = ServiceError("credit_limit", "wrapper", 409)
            error.__cause__ = cause
            self.assertFalse(is_business_rejection("BORROW", error))
        unknown = ServiceError("unknown_503", "no observed outcome", 503)
        self.assertFalse(is_business_rejection("BORROW", unknown))
        self.assertFalse(is_business_rejection("BORROW", ServiceError("credit_limit", "bad status", 503)))

    def test_known_market_refusal_is_distinct_from_unknown_or_credit_audit_failure(self):
        self.assertTrue(is_business_rejection("BORROW", ServiceError("market_unavailable", "no quote", 503)))
        self.assertFalse(is_business_rejection("BORROW", ServiceError("credit_audit_state_mismatch", "bad evidence", 503)))
        self.assertFalse(is_business_rejection("SOMETHING_ELSE", ServiceError("invalid_input", "bad input", 400)))


if __name__ == "__main__":
    unittest.main()
