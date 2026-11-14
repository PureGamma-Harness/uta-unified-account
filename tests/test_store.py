"""Persistence, compare-and-swap, and atomicity tests for the command store."""

from contextlib import closing
import hashlib
import sqlite3
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier

from uta.store import AccountNotFound, ShardedStore, Store, StoreConflict, StoreError


def add_one(state):
    state["units"] += 1
    return state, {"units": state["units"]}


class StoreTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name) / "uta.sqlite3"
        self.store = Store(self.path)

    def test_audit_and_retries_survive_reopening_database(self):
        start = {"units": 0, "nested": {"items": []}}
        result = self.store.create("account", start)
        start["nested"]["items"].append("caller mutation")
        result["nested"]["items"].append("returned mutation")
        request = {"type": "increment", "amount": "1"}
        first = self.store.apply("account", "first", 0, request, add_one)
        self.store.apply("account", "second", 1, request, add_one)

        reopened = Store(self.path)
        replay = reopened.apply("account", "first", 0, {"amount": "1", "type": "increment"},
                                lambda _: self.fail("replay ran the transition"))
        self.assertEqual(replay, first)
        self.assertEqual(reopened.read("account"), {"version": 2, "units": 2, "nested": {"items": []}})
        log = reopened.events("account")
        self.assertEqual([event["version"] for event in log], [0, 1, 2])
        self.assertEqual(log[0]["command"], {"type": "create", "state": {"version": 0, "units": 0, "nested": {"items": []}}})
        self.assertEqual(log[1]["result"], first)
        self.assertEqual(log[1]["expected_version"], 0)

        with self.assertRaises(StoreConflict):
            reopened.apply("account", "first", 0, {"type": "increment", "amount": "2"}, add_one)
        with self.assertRaises(StoreConflict):
            reopened.apply("account", "first", 2, request, add_one)
        with self.assertRaises(StoreConflict):
            reopened.apply("account", "stale", 1, request, add_one)

    def test_compare_and_swap_serializes_independent_connections(self):
        self.store.create("account", {"units": 0})
        other = Store(self.path)
        line = Barrier(2, timeout=5)

        def submit(store, identifier):
            line.wait()
            try:
                return store.apply("account", identifier, 0, {"type": "increment"}, add_one)
            except StoreConflict:
                return None

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(submit, store, identifier)
                       for store, identifier in ((self.store, "one"), (other, "two"))]
            self.assertCountEqual([future.result(timeout=10) for future in futures],
                                  [{"version": 1, "units": 1}, None])
        self.assertEqual(self.store.read("account"), {"version": 1, "units": 1})
        self.assertEqual(len(self.store.events("account")), 2)

    def test_audit_write_failure_rolls_back_snapshot(self):
        self.store.create("account", {"units": 0})
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("""CREATE TRIGGER deny_uta_event BEFORE INSERT ON uta_events
                          BEGIN SELECT RAISE(ABORT, 'simulated audit failure'); END""")
        with self.assertRaises(StoreError):
            self.store.apply("account", "command", 0, {"type": "increment"}, add_one)
        self.assertEqual(self.store.read("account"), {"version": 0, "units": 0})
        self.assertEqual(len(self.store.events("account")), 1)
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("DROP TRIGGER deny_uta_event")
        self.assertEqual(self.store.apply("account", "command", 0, {"type": "increment"}, add_one),
                         {"version": 1, "units": 1})

    def test_failed_transition_and_unserializable_result_do_not_mutate_storage(self):
        self.store.create("account", {"units": 0})

        def fail(state):
            state["units"] = 10
            raise ValueError("unacceptable command")

        with self.assertRaisesRegex(ValueError, "unacceptable command"):
            self.store.apply("account", "failed", 0, {"type": "fail"}, fail)
        with self.assertRaises(StoreError):
            self.store.apply("account", "invalid", 0, {"type": "fail"},
                             lambda state: (state, {"units": float("nan")}))
        self.assertEqual(self.store.read("account"), {"version": 0, "units": 0})
        self.assertEqual(len(self.store.events("account")), 1)

    def test_command_ids_are_scoped_to_account(self):
        with self.assertRaises(AccountNotFound):
            self.store.events("missing")
        for account in ("one", "two"):
            self.store.create(account, {"units": 0})
            self.store.apply(account, "shared", 0, {"type": "increment"}, add_one)
        with self.assertRaises(StoreConflict):
            self.store.create("one", {"units": 0})
        self.assertEqual(self.store.apply("two", "other", 1, {"type": "increment"}, add_one),
                         {"version": 2, "units": 2})
        self.assertEqual(self.store.read("one"), {"version": 1, "units": 1})

    def test_batch_commits_successes_and_replays_exact_receipts_in_order(self):
        for account in ("one", "two"):
            self.store.create(account, {"units": 0})

        def reject(state):
            state["units"] = 20
            raise ValueError("policy rejection")

        request = {"type": "increment"}
        batch = [
            ("one", "first", 0, request, add_one),
            ("one", "rejected", 1, request, reject),
            ("two", "wrong version", 1, request, add_one),
            ("one", "second", 1, request, add_one),
            ("two", "first", 0, request, add_one),
            ("one", "first", 0, request, lambda _: self.fail("retry ran the transition")),
        ]
        first, rejected, conflict, second, other, replay = self.store.apply_many(batch)
        self.assertEqual(first, {"version": 1, "units": 1})
        self.assertIsInstance(rejected, ValueError)
        self.assertIsInstance(conflict, StoreConflict)
        self.assertEqual(second, {"version": 2, "units": 2})
        self.assertEqual(other, first)
        self.assertEqual(replay, first)
        other_store = Store(self.path)
        self.assertEqual([row["command_id"] for row in other_store.events("one")], [None, "first", "second"])
        self.assertEqual(other_store.read("one"), second)
        self.assertEqual(other_store.read("two"), other)

    def test_batch_database_failure_rolls_back_earlier_commands(self):
        self.store.create("one", {"units": 0})
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("""CREATE TRIGGER deny_uta_event BEFORE INSERT ON uta_events
                          WHEN NEW.command_id = 'second'
                          BEGIN SELECT RAISE(ABORT, 'simulated audit failure'); END""")
        request = {"type": "increment"}
        with self.assertRaises(StoreError):
            self.store.apply_many([("one", "first", 0, request, add_one),
                                   ("one", "second", 1, request, add_one)])
        self.assertEqual(self.store.read("one"), {"version": 0, "units": 0})
        self.assertEqual(len(self.store.events("one")), 1)


class ShardedStoreTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name) / "uta.sqlite3"

    def test_stable_routing_and_manifest_checked_on_reopen(self):
        store = ShardedStore(self.path, shards=4)
        for account in ("one", "two", "three", "four"):
            store.create(account, {"units": 0})
            store.apply(account, "increment", 0, {"type": "increment"}, add_one)
            index = int(hashlib.sha256(account.encode()).hexdigest(), 16) % 4
            filename = store.directory / f"shard-{index:02d}.sqlite3"
            with closing(sqlite3.connect(filename)) as db, db:
                self.assertEqual(db.execute("PRAGMA journal_mode").fetchone()[0], "wal")
                self.assertEqual(db.execute("SELECT version FROM uta_accounts WHERE account_id = ?",
                                            (account,)).fetchone(), (1,))
        reopened = ShardedStore(self.path, shards=4)
        self.assertEqual(reopened.read("one"), {"version": 1, "units": 1})
        with self.assertRaises(StoreConflict):
            ShardedStore(self.path, shards=5)
        with self.assertRaises(StoreConflict):
            Store(self.path)
        index = int(hashlib.sha256(b"one").hexdigest(), 16) % 4
        missing_shard = store.directory / f"shard-{index:02d}.sqlite3"
        missing_shard.unlink()
        with self.assertRaises(StoreError):
            store.read("one")
        self.assertFalse(missing_shard.exists())
        with self.assertRaises(StoreError):
            ShardedStore(self.path, shards=4)

    def test_independent_shards_can_write_while_same_account_conflicts(self):
        store = ShardedStore(self.path, shards=2)
        peer = ShardedStore(self.path, shards=2)
        account_for = {}
        for n in range(100):
            account = f"account-{n}"
            index = int(hashlib.sha256(account.encode()).hexdigest(), 16) % 2
            account_for.setdefault(index, account)
        one, two = account_for[0], account_for[1]
        store.create(one, {"units": 0})
        store.create(two, {"units": 0})
        barrier = Barrier(2, timeout=5)

        def increment(state):
            # Both transitions must enter while holding their respective write
            # locks, so this would fail if the two accounts shared a database.
            barrier.wait()
            return add_one(state)

        request = {"type": "increment"}
        with ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(store.apply, one, "add", 0, request, increment)
            second = pool.submit(peer.apply, two, "add", 0, request, increment)
            self.assertEqual(first.result(timeout=7), {"version": 1, "units": 1})
            self.assertEqual(second.result(timeout=7), {"version": 1, "units": 1})

            def compete(participant, command_id):
                barrier.wait()
                try:
                    return participant.apply(one, command_id, 1, request, add_one)
                except StoreConflict:
                    return None

            contenders = [pool.submit(compete, participant, key)
                          for participant, key in ((store, "step-a"), (peer, "step-b"))]
            self.assertCountEqual([contender.result(timeout=7) for contender in contenders],
                                  [{"version": 2, "units": 2}, None])
        self.assertEqual(peer.apply(one, "add", 0, request, lambda _: self.fail("duplicate ran")),
                         {"version": 1, "units": 1})

    def test_existing_single_database_is_not_replaced_by_shards(self):
        Store(self.path).create("one", {"units": 0})
        with self.assertRaises(StoreConflict):
            ShardedStore(self.path, shards=2)

    def test_batch_is_independent_per_shard_and_preserves_input_order(self):
        store = ShardedStore(self.path, shards=2)
        accounts = {}
        for n in range(100):
            value = f"account-{n}"
            index = int(hashlib.sha256(value.encode()).hexdigest(), 16) % 2
            accounts.setdefault(index, value)
        one, two = accounts[0], accounts[1]
        store.create(one, {"units": 0})
        store.create(two, {"units": 0})
        with closing(sqlite3.connect(store.directory / "shard-01.sqlite3")) as db, db:
            db.execute("""CREATE TRIGGER deny_uta_event BEFORE INSERT ON uta_events
                          WHEN NEW.command_id = 'second'
                          BEGIN SELECT RAISE(ABORT, 'simulated audit failure'); END""")

        request = {"type": "increment"}
        cross_shard = Barrier(2, timeout=5)

        def increment(state):
            cross_shard.wait()
            return add_one(state)

        receipts = store.apply_many([
            (two, "first", 0, request, increment),
            (one, "first", 0, request, increment),
            (two, "second", 1, request, add_one),
        ])
        self.assertIsInstance(receipts[0], StoreError)
        self.assertEqual(receipts[1], {"version": 1, "units": 1})
        self.assertIsInstance(receipts[2], StoreError)
        self.assertEqual(store.read(one), {"version": 1, "units": 1})
        self.assertEqual(store.read(two), {"version": 0, "units": 0})
        self.assertEqual(len(store.events(two)), 1)
