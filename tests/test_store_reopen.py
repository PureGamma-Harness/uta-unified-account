"""Existing-file and interrupted-initialization boundaries for the local store."""
import hashlib
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from uta.store import ShardedStore, Store, StoreError


class StoreReopenTests(unittest.TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name) / "accounts.sqlite3"

    def test_existing_only_store_never_creates_a_missing_database(self):
        with self.assertRaises(StoreError):
            Store(self.path, create_if_missing=False)
        self.assertFalse(self.path.exists())

        original = Store(self.path)
        original.create("one", {"units": 7})
        reopened = Store(self.path, create_if_missing=False)
        self.assertEqual(reopened.read("one"), {"version": 0, "units": 7})

        def increment(state):
            state["units"] += 1
            return state, {"units": state["units"]}

        self.assertEqual(reopened.apply("one", "add", 0, {"type": "increment"}, increment),
                         {"version": 1, "units": 8})
        self.assertEqual(original.read("one"), {"version": 1, "units": 8})

    def test_ready_shard_disappearing_after_check_is_not_recreated(self):
        store = ShardedStore(self.path, shards=2)
        store.create("one", {"units": 7})
        victim = store._for_account("one").path
        original_store = Store
        removed = []

        def open_after_removal(path, *args, **kwargs):
            if Path(path) == victim:
                # ShardedStore has already checked every ready path before
                # calling the first Store constructor. Remove a real file now.
                self.assertTrue(victim.is_file())
                victim.unlink()
                removed.append(victim)
            return original_store(path, *args, **kwargs)

        with patch("uta.store.Store", side_effect=open_after_removal):
            with self.assertRaises(StoreError):
                ShardedStore(self.path, shards=2)
        self.assertEqual(removed, [victim])
        self.assertFalse(victim.exists())
        with sqlite3.connect(store.directory / "manifest.sqlite3") as db:
            self.assertEqual(db.execute("SELECT ready FROM layout WHERE id = 1").fetchone(), (1,))

    def test_incomplete_layout_can_finish_initializing(self):
        store = ShardedStore(self.path, shards=2)
        # Model an interrupted first initialization, before any accounts exist.
        with sqlite3.connect(store.directory / "manifest.sqlite3") as db:
            db.execute("UPDATE layout SET ready = 0 WHERE id = 1")
        missing = store.directory / "shard-01.sqlite3"
        missing.unlink()

        reopened = ShardedStore(self.path, shards=2)
        self.assertTrue(missing.is_file())
        with sqlite3.connect(store.directory / "manifest.sqlite3") as db:
            self.assertEqual(db.execute("SELECT ready FROM layout WHERE id = 1").fetchone(), (1,))
        accounts = {}
        for n in range(100):
            account = f"account-{n}"
            index = int(hashlib.sha256(account.encode()).hexdigest(), 16) % 2
            accounts.setdefault(index, account)
        self.assertEqual(set(accounts), {0, 1})
        for index, account in accounts.items():
            reopened.create(account, {"units": index})
            self.assertEqual(reopened.read(account), {"version": 0, "units": index})


if __name__ == "__main__":
    unittest.main()
