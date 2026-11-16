"""Real SQLite COMMIT failures must not acknowledge uncommitted commands."""

from contextlib import closing, contextmanager
import hashlib
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from uta.store import ShardedStore, Store, StoreError


def install_commit_failure(path):
    # The trigger succeeds at INSERT. Its deferred foreign key fails at COMMIT.
    with closing(sqlite3.connect(path)) as db, db:
        db.executescript("""
            CREATE TABLE commit_parent (id TEXT PRIMARY KEY);
            CREATE TABLE commit_guard (
                parent_id TEXT REFERENCES commit_parent(id)
                    DEFERRABLE INITIALLY DEFERRED
            );
            CREATE TRIGGER fail_commit AFTER INSERT ON uta_events
                WHEN NEW.command_id = 'fail'
                BEGIN INSERT INTO commit_guard VALUES ('missing'); END;
        """)


def remove_commit_failure(path):
    with closing(sqlite3.connect(path)) as db, db:
        db.execute("DROP TRIGGER fail_commit")


@contextmanager
def trace_statements():
    statements = []
    connect = sqlite3.connect

    def traced_connect(*args, **kwargs):
        db = connect(*args, **kwargs)
        db.set_trace_callback(statements.append)
        return db

    # Observe real connections; neither COMMIT nor its exception is mocked.
    with patch("uta.store.sqlite3.connect", new=traced_connect):
        yield statements


class StoreCommitTests(unittest.TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name) / "uta.sqlite3"

    def command(self, account, command_id, version, calls):
        def transition(state):
            calls.append(command_id)
            state["units"] += 1
            return state, {"units": state["units"]}
        return account, command_id, version, {"type": "increment"}, transition

    def assert_commit_error(self, error):
        self.assertIsInstance(error, StoreError)
        self.assertIsInstance(error.__cause__, sqlite3.IntegrityError)
        self.assertIn("FOREIGN KEY", str(error.__cause__))

    def assert_account(self, store, account, units, command_ids):
        self.assertEqual(store.read(account), {"units": units, "version": len(command_ids)})
        events = store.events(account)
        self.assertEqual([event["command_id"] for event in events], [None, *command_ids])
        self.assertEqual([event["version"] for event in events], list(range(len(events))))

    def test_single_command_commit_failure_rolls_back_and_retries_once(self):
        store = Store(self.path)
        store.create("one", {"units": 0})
        install_commit_failure(self.path)
        calls = []
        command = self.command("one", "fail", 0, calls)
        with trace_statements() as statements, self.assertRaises(StoreError) as error:
            store.apply(*command)
        self.assert_commit_error(error.exception)
        self.assertIn("COMMIT", statements)
        self.assertEqual(calls, ["fail"])
        reopened = Store(self.path)
        self.assert_account(reopened, "one", 0, [])

        remove_commit_failure(self.path)
        receipt = reopened.apply(*command)
        retry = (*command[:-1], lambda _: self.fail("committed retry ran the transition"))
        self.assertEqual(Store(self.path).apply(*retry), receipt)
        self.assertEqual(calls, ["fail", "fail"])
        self.assert_account(Store(self.path), "one", 1, ["fail"])

    def test_batch_commit_failure_rolls_back_every_account_and_later_command(self):
        store = Store(self.path)
        for account in ("one", "two"):
            store.create(account, {"units": 0})
        install_commit_failure(self.path)
        calls = []
        commands = [self.command("one", "first", 0, calls),
                    self.command("two", "fail", 0, calls),
                    self.command("one", "last", 1, calls)]
        with trace_statements() as statements, self.assertRaises(StoreError) as error:
            store.apply_many(commands)
        self.assert_commit_error(error.exception)
        self.assertIn("COMMIT", statements)
        # Even commands after the deferred violation ran before COMMIT failed.
        self.assertEqual(calls, ["first", "fail", "last"])
        reopened = Store(self.path)
        for account in ("one", "two"):
            self.assert_account(reopened, account, 0, [])

        remove_commit_failure(self.path)
        receipts = reopened.apply_many(commands)
        self.assertEqual([receipt["version"] for receipt in receipts], [1, 1, 2])
        retries = [(*command[:-1], lambda _: self.fail("committed batch retry ran"))
                   for command in commands]
        self.assertEqual(Store(self.path).apply_many(retries), receipts)
        self.assertEqual(calls, ["first", "fail", "last"] * 2)
        self.assert_account(Store(self.path), "one", 2, ["first", "last"])
        self.assert_account(Store(self.path), "two", 1, ["fail"])

    def test_cross_shard_retry_preserves_other_shards_committed_receipt(self):
        store = ShardedStore(self.path, shards=2)
        accounts = {}
        for index in range(100):
            account = f"account-{index}"
            shard = int(hashlib.sha256(account.encode()).hexdigest(), 16) % 2
            accounts.setdefault(shard, account)
        good, bad = accounts[0], accounts[1]
        for account in (good, bad):
            store.create(account, {"units": 0})
        failed_path = store.directory / "shard-01.sqlite3"
        install_commit_failure(failed_path)
        calls = []
        commands = [self.command(bad, "first", 0, calls),
                    self.command(good, "good", 0, calls),
                    self.command(bad, "fail", 1, calls)]
        with trace_statements() as statements:
            receipts = store.apply_many(commands)
        self.assertGreaterEqual(statements.count("COMMIT"), 2)
        for index in (0, 2):
            self.assert_commit_error(receipts[index])
        self.assertEqual(receipts[1], {"units": 1, "version": 1})
        reopened = ShardedStore(self.path, shards=2)
        self.assert_account(reopened, good, 1, ["good"])
        self.assert_account(reopened, bad, 0, [])

        remove_commit_failure(failed_path)
        retries = list(commands)
        retries[1] = (*commands[1][:-1], lambda _: self.fail("successful shard executed twice"))
        retried = reopened.apply_many(retries)
        self.assertEqual(retried, [{"units": 1, "version": 1}, receipts[1],
                                   {"units": 2, "version": 2}])
        self.assertEqual(calls.count("good"), 1)
        self.assert_account(ShardedStore(self.path, shards=2), good, 1, ["good"])
        self.assert_account(ShardedStore(self.path, shards=2), bad, 2, ["first", "fail"])


if __name__ == "__main__":
    unittest.main()
