"""Small synthetic full-replay differentials; no service/worker/benchmark.

The manually assembled hash/integer reference below calls no production
fingerprint/hash/normalization functions. SQL corruptions occur only offline in
new test-private authorities, with the original trigger SQL restored verbatim.
"""
from decimal import Decimal
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from uta.ledger import LedgerError, Posting
from uta.storage import Database, DurableLedger


def literal_journal(events):
    previous, rows, postings, balances = "0" * 64, [], [], {}
    for sequence, (event_id, canonical) in enumerate(events, 1):
        # Independent integer/string composition, not a call to ledger helpers.
        fingerprint = sha256(json.dumps(canonical, ensure_ascii=True,
            separators=(",", ":")).encode()).hexdigest()
        event_hash = sha256(json.dumps([sequence, event_id, previous, fingerprint],
            ensure_ascii=True, separators=(",", ":")).encode()).hexdigest()
        rows.append((sequence, event_id, fingerprint, previous, event_hash, 1))
        for ordinal, (account, asset, units) in enumerate(canonical):
            postings.append((sequence, ordinal, account, asset, str(units)))
            balances[account, asset] = balances.get((account, asset), 0) + units
        previous = event_hash
    return rows, postings, [(a, s, str(u)) for (a, s), u in sorted(balances.items())]


MANUAL = [("manual:1", [("a", "USD", -1250), ("b", "USD", 1250)]),
          ("manual:2", [("b", "USD", -300), ("c", "USD", 300)])]


class TraceDatabase(Database):
    def __init__(self, path):
        super().__init__(path)
        self.statements = []

    def _connect(self):
        connection = super()._connect()
        connection.set_trace_callback(self.statements.append)
        return connection


class HistoryPostingsStreamTests(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory(prefix="uta-postings-stream-test-")
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "authority.sqlite3"
        self.database = TraceDatabase(self.path)
        self.ledger = DurableLedger(self.database, {"USD": 2})
        with self.database.transaction() as connection:
            for event_id, canonical in MANUAL:
                self.ledger.post(event_id, [Posting(account, asset,
                    Decimal((int(units < 0), tuple(map(int, str(abs(units)))), -2)))
                    for account, asset, units in canonical], connection=connection)

    def corrupt(self, operation):
        # This is fixture construction, before any verifier runs. Neither path
        # runs with removed guards, patched clocks or a forged verification.
        with sqlite3.connect(self.path) as connection:
            triggers = list(connection.execute("SELECT name,sql FROM sqlite_master WHERE type='trigger'"))
            for name, _ in triggers:
                connection.execute('DROP TRIGGER "' + name.replace('"', '""') + '"')
            operation(connection)
            for _, statement in triggers:
                connection.execute(statement)

    def outcomes(self):
        outcomes = []
        for mode in (False, True):
            try:
                outcomes.append(("ok", self.ledger.verify(ordered_postings=mode)))
            except Exception as error:
                outcomes.append((type(error).__name__, str(error)))
        self.assertEqual(outcomes[0], outcomes[1])
        return outcomes[0]

    def rejected(self, message):
        self.assertEqual(self.outcomes(), ("LedgerError", message))

    def test_manual_reference_complete_counts_and_balances(self):
        self.assertEqual(self.outcomes(), ("ok", 2))
        with self.database.read_transaction() as connection:
            expected = literal_journal(MANUAL)
            observed = [list(map(tuple, connection.execute(sql))) for sql in (
                "SELECT * FROM ledger_events ORDER BY sequence",
                "SELECT * FROM ledger_postings ORDER BY sequence,ordinal",
                "SELECT * FROM ledger_balances ORDER BY account,asset")]
        self.assertEqual(observed, list(expected))
        self.assertEqual(expected[2], [("a", "USD", "-1250"), ("b", "USD", "950"), ("c", "USD", "300")])

    def test_sql_dispatch_counts_and_default_off(self):
        counts = []
        for kwargs in ({}, {"ordered_postings": False}, {"ordered_postings": True}):
            self.database.statements.clear()
            self.assertEqual(self.ledger.verify(**kwargs), 2)
            counts.append(sum("FROM ledger_postings" in sql and sql.startswith("SELECT")
                              for sql in self.database.statements))
        self.assertEqual(counts, [2, 2, 1])

    def test_option_types_reject_before_storage(self):
        with patch.object(self.database, "_using", side_effect=AssertionError("opened storage")):
            for value in (0, 1, None, "true", []):
                with self.subTest(value=value), self.assertRaisesRegex(ValueError, "must be a boolean"):
                    self.ledger.verify(ordered_postings=value)

    def test_reverse_physical_insertion(self):
        def reverse(connection):
            events, postings, balances = literal_journal(MANUAL)
            connection.execute("DELETE FROM ledger_postings")
            connection.execute("DELETE FROM ledger_events")
            connection.execute("DELETE FROM ledger_balances")
            connection.executemany("INSERT INTO ledger_events VALUES(?,?,?,?,?,?)", events[::-1])
            connection.executemany("INSERT INTO ledger_postings VALUES(?,?,?,?,?)", postings[::-1])
            connection.executemany("INSERT INTO ledger_balances VALUES(?,?,?)", balances[::-1])
        self.corrupt(reverse)
        self.assertEqual(self.outcomes(), ("ok", 2))

    def test_missing_group(self):
        self.corrupt(lambda c: c.execute("DELETE FROM ledger_postings WHERE sequence=2"))
        self.rejected("at least two postings are required")

    def test_missing_last_posting(self):
        self.corrupt(lambda c: c.execute("DELETE FROM ledger_postings WHERE sequence=2 AND ordinal=1"))
        self.rejected("at least two postings are required")

    def test_ordinal_gap(self):
        self.corrupt(lambda c: c.execute("UPDATE ledger_postings SET ordinal=2 WHERE sequence=2 AND ordinal=1"))
        self.rejected("journal posting sequence is broken")

    def test_orphan_inventory(self):
        self.corrupt(lambda c: c.execute("INSERT INTO ledger_postings VALUES(99,0,'orphan','USD','1')"))
        self.rejected("database foreign-key check failed")

    def test_event_sequence_gap_with_valid_foreign_keys(self):
        def gap(c):
            c.execute("UPDATE ledger_postings SET sequence=3 WHERE sequence=2")
            c.execute("UPDATE ledger_events SET sequence=3 WHERE sequence=2")
        self.corrupt(gap)
        self.rejected("journal sequence or hash chain is broken")

    def test_noncanonical_posting_order(self):
        def swap(c):
            c.execute("UPDATE ledger_postings SET ordinal=ordinal+10 WHERE sequence=2")
            c.execute("UPDATE ledger_postings SET ordinal=11-ordinal WHERE sequence=2")
        self.corrupt(swap)
        self.rejected("journal event fingerprint changed")

    def test_prior_hash(self):
        self.corrupt(lambda c: c.execute("UPDATE ledger_events SET previous_hash='broken' WHERE sequence=2"))
        self.rejected("journal sequence or hash chain is broken")

    def test_event_hash(self):
        self.corrupt(lambda c: c.execute("UPDATE ledger_events SET event_hash='broken' WHERE sequence=2"))
        self.rejected("journal event hash changed")

    def test_canonical_units_and_both_signed_bounds(self):
        for value in ("+300", "0300", "-0", str(10**38), str(-(10**38))):
            with self.subTest(value=value):
                self.corrupt(lambda c: c.execute("UPDATE ledger_postings SET units=? WHERE sequence=2 AND ordinal=1", (value,)))
                # The negative boundary is 40 characters and hits the existing
                # length check before the positive boundary's numeric check.
                self.rejected("corrupt ledger integer" if len(value) > 39 else
                              "corrupt or out-of-range ledger integer")

    def test_noninteger_units(self):
        self.corrupt(lambda c: c.execute("UPDATE ledger_postings SET units='x' WHERE sequence=2 AND ordinal=1"))
        self.rejected("corrupt ledger integer")

    def test_both_signed_cumulative_overflow(self):
        for sign in (-1, 1):
            with self.subTest(sign=sign):
                entries = [("limit:1", [("a", "USD", sign * (10**38-1)), ("b", "USD", -sign * (10**38-1))]),
                           ("limit:2", [("a", "USD", sign), ("b", "USD", -sign)])]
                def replace(c):
                    events, postings, balances = literal_journal(entries)
                    for table in ("ledger_postings", "ledger_events", "ledger_balances"):
                        c.execute("DELETE FROM " + table)
                    c.executemany("INSERT INTO ledger_events VALUES(?,?,?,?,?,?)", events)
                    c.executemany("INSERT INTO ledger_postings VALUES(?,?,?,?,?)", postings)
                    c.executemany("INSERT INTO ledger_balances VALUES(?,?,?)", balances)
                self.corrupt(replace)
                self.rejected("replayed balance exceeds supported range")

    def test_materialized_balance(self):
        self.corrupt(lambda c: c.execute("UPDATE ledger_balances SET units='951' WHERE account='b'"))
        self.rejected("materialized balances differ from journal replay")

    def test_first_error_preserved_before_later_group_decode(self):
        def twice(c):
            c.execute("UPDATE ledger_events SET previous_hash='broken' WHERE sequence=1")
            c.execute("UPDATE ledger_postings SET units='x' WHERE sequence=2")
        self.corrupt(twice)
        self.rejected("journal sequence or hash chain is broken")

    def test_first_chain_error_before_initial_invalid_utf8(self):
        for column in ("account", "units"):
            with self.subTest(column=column):
                def twice(c):
                    c.execute("UPDATE ledger_events SET previous_hash='broken' WHERE sequence=1")
                    c.execute("UPDATE ledger_postings SET account='a',units='-1250' WHERE sequence=1 AND ordinal=0")
                    c.execute("UPDATE ledger_postings SET " + column + "=CAST(X'ff' AS TEXT) WHERE sequence=1 AND ordinal=0")
                self.corrupt(twice)
                self.rejected("journal sequence or hash chain is broken")

    def test_fingerprint_error_before_future_invalid_utf8(self):
        for column in ("account", "units"):
            with self.subTest(column=column):
                def twice(c):
                    c.execute("UPDATE ledger_events SET fingerprint='broken' WHERE sequence=1")
                    c.execute("UPDATE ledger_postings SET account='b',units='-300' WHERE sequence=2 AND ordinal=0")
                    c.execute("UPDATE ledger_postings SET " + column + "=CAST(X'ff' AS TEXT) WHERE sequence=2 AND ordinal=0")
                self.corrupt(twice)
                self.rejected("journal event fingerprint changed")

    def test_invalid_utf8_asset_keeps_original_foreign_key_priority(self):
        def twice(c):
            c.execute("UPDATE ledger_events SET previous_hash='broken' WHERE sequence=1")
            c.execute("UPDATE ledger_postings SET asset=CAST(X'ff' AS TEXT) WHERE sequence=1 AND ordinal=0")
        self.corrupt(twice)
        self.rejected("database foreign-key check failed")

    def test_protection_missing(self):
        with sqlite3.connect(self.path) as c:
            c.execute("DROP TRIGGER ledger_events_no_delete")
        self.rejected("journal protection trigger is missing")

    def test_asset_scale_change(self):
        self.corrupt(lambda c: c.execute("UPDATE ledger_assets SET scale=3 WHERE asset='USD'"))
        self.rejected("ledger asset scales changed")

    def test_schema_change(self):
        self.corrupt(lambda c: c.execute("UPDATE ledger_schema SET version=2"))
        self.rejected("ledger schema version changed")


if __name__ == "__main__":
    unittest.main()
