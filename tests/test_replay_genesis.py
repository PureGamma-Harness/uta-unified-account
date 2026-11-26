"""Persisted genesis corruption must not be counted as verified history."""
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest

from uta.simulator import Simulator, SimulatorError


class ReplayGenesisTests(unittest.TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.directory = Path(directory.name)
        self.now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        self.sequence = 0

    def simulator(self, shards):
        self.sequence += 1
        return Simulator(self.directory / f"case-{self.sequence}.sqlite3",
                         clock=lambda: self.now, shards=shards)

    @staticmethod
    def account_store(sim):
        return sim.store if hasattr(sim.store, "path") else sim.store._for_account("account")

    def test_genesis_json_shape_and_native_version_types_are_checked(self):
        invalid = "account creation event is invalid"
        receipt_error = "receipt differs at version 0"
        cases = (
            ("command_id", "named-creation", invalid),
            ("expected_version", 0, invalid),
            ("command", {}, invalid),
            ("command", {"type": "place_order", "state": {"version": 0}}, invalid),
            ("command", {"type": "create", "state": {"version": 0}, "extra": True}, invalid),
            ("command", {"type": "create", "state": []}, invalid),
            ("command", {"type": "create", "state": {}}, invalid),
            ("command", {"type": "create", "state": {"version": False}}, invalid),
            ("command", {"type": "create", "state": {"version": 0.0}}, invalid),
            ("command", {"type": "create", "state": {"version": "0"}}, invalid),
            ("command", {"type": "create", "state": {"version": 1}}, invalid),
            ("result", {}, receipt_error),
            ("result", {"version": False}, receipt_error),
            ("result", {"version": 0.0}, receipt_error),
            ("result", {"version": "0"}, receipt_error),
            ("result", {"version": 1}, receipt_error),
            ("result", {"version": 0, "extra": True}, receipt_error),
        )
        for shards in (1, 4):
            for column, value, message in cases:
                with self.subTest(shards=shards, column=column, value=value):
                    sim = self.simulator(shards)
                    sim.bootstrap("account")
                    store = self.account_store(sim)
                    encoded = json.dumps(value) if column in ("command", "result") else value
                    with sqlite3.connect(store.path) as db:
                        db.execute(f"UPDATE uta_events SET {column} = ? "
                                   "WHERE account_id = ? AND version = 0", (encoded, "account"))
                    snapshot, events = store.read_for_replay("account")
                    with self.assertRaisesRegex(SimulatorError, message):
                        sim.verify_replay("account")
                    self.assertEqual(store.read_for_replay("account"), (snapshot, events))

    def test_missing_genesis_is_reported_before_replaying_later_commands(self):
        for shards in (1, 4):
            with self.subTest(shards=shards):
                sim = self.simulator(shards)
                sim.bootstrap("account")
                sim.execute("account", "buy", 0, {
                    "type": "place_order", "symbol": "BTC-PERP", "quantity": "0.01",
                    "limit_price": "60000", "fee_rate": "0.001",
                })
                store = self.account_store(sim)
                with sqlite3.connect(store.path) as db:
                    db.execute("DELETE FROM uta_events WHERE account_id = ? AND version = 0",
                               ("account",))
                self.assertEqual([event["version"] for event in sim.events("account")], [1])
                with self.assertRaisesRegex(SimulatorError, "account creation event is missing"):
                    sim.verify_replay("account")
                self.assertEqual(sim.store.read("account")["version"], 1)

    def test_valid_bootstrap_and_import_replay_without_writing_history(self):
        for shards in (1, 4):
            for imported in (False, True):
                with self.subTest(shards=shards, imported=imported):
                    sim = self.simulator(shards)
                    if imported:
                        sim.import_classic("account", {
                            "account_id": "classic", "version": 17,
                            "captured_at": self.now.isoformat(),
                            "compartments": {
                                "spot": {"balances": [{"asset": "USD", "free": "500",
                                                        "locked": "0", "borrowed": "0",
                                                        "interest": "0"}]},
                                "margin": {"balances": []},
                                "futures": {"balances": [], "positions": []},
                            },
                        })
                    else:
                        sim.bootstrap("account")
                    self.assertEqual(sim.verify_replay("account"),
                                     {"account_id": "account", "version": 0, "events_verified": 1})
                    sim.execute("account", "buy", 0, {
                        "type": "place_order", "symbol": "BTC-PERP", "quantity": "0.01",
                        "limit_price": "60000", "fee_rate": "0.001",
                    })
                    store = self.account_store(sim)
                    before = store.read_for_replay("account")
                    if imported:
                        self.assertEqual(before[0]["source"]["version"], 17)
                    self.assertEqual(sim.verify_replay("account"),
                                     {"account_id": "account", "version": 1, "events_verified": 2})
                    self.assertEqual(store.read_for_replay("account"), before)
