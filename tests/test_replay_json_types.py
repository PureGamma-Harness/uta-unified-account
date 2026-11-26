"""Audit comparisons must distinguish booleans, integers and floats."""
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest

from uta.simulator import Simulator, SimulatorError


def reverse_objects(value):
    if isinstance(value, dict):
        return {key: reverse_objects(item) for key, item in reversed(value.items())}
    if isinstance(value, list):
        return [reverse_objects(item) for item in value]
    return value


class ReplayJsonTypeTests(unittest.TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.directory = Path(directory.name)
        self.now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        self.sequence = 0

    def simulator(self, shards):
        self.sequence += 1
        sim = Simulator(self.directory / f"case-{self.sequence}.sqlite3",
                        clock=lambda: self.now, shards=shards)
        sim.bootstrap("account")
        store = sim.store if shards == 1 else sim.store._for_account("account")
        return sim, store.path

    @staticmethod
    def rows(path):
        with sqlite3.connect(path) as db:
            return (db.execute("SELECT version, snapshot FROM uta_accounts "
                               "WHERE account_id = 'account'").fetchall(),
                    db.execute("SELECT * FROM uta_events WHERE account_id = 'account' "
                               "ORDER BY version").fetchall())

    @staticmethod
    def market_command(sim):
        state = sim.view("account")["state"]
        return {"type": "mark_and_liquidate", "prices": state["prices"],
                "marks": state["marks"]}

    def test_replay_rejects_numeric_aliases_in_receipts(self):
        cases = (("version", True), ("version", 1.0),
                 ("liquidation_pending", 0), ("liquidation_pending", 0.0))
        for shards in (1, 4):
            for field, value in cases:
                with self.subTest(shards=shards, field=field, value=value):
                    sim, path = self.simulator(shards)
                    receipt = sim.execute("account", "market", 0, self.market_command(sim))
                    self.assertIs(type(receipt["version"]), int)
                    self.assertIs(receipt["liquidation_pending"], False)
                    receipt[field] = value
                    with sqlite3.connect(path) as db:
                        db.execute("UPDATE uta_events SET result = ? "
                                   "WHERE account_id = ? AND version = 1",
                                   (json.dumps(receipt), "account"))
                    before = self.rows(path)
                    with self.assertRaisesRegex(SimulatorError, "receipt differs at version 1"):
                        sim.verify_replay("account")
                    self.assertEqual(self.rows(path), before)

    def test_replay_rejects_float_alias_in_nested_snapshot_version(self):
        for shards in (1, 4):
            with self.subTest(shards=shards):
                sim, path = self.simulator(shards)
                sim.execute("account", "buy", 0, {
                    "type": "place_order", "symbol": "BTC-PERP", "quantity": "0.01",
                    "limit_price": "60000", "fee_rate": "0.001",
                })
                sim.execute("account", "cancel", 1, {"type": "cancel_order", "order_id": "buy"})
                snapshot = sim.store.read("account")
                self.assertIs(type(snapshot["orders"]["buy"]["closed_version"]), int)
                snapshot["orders"]["buy"]["closed_version"] = 2.0
                with sqlite3.connect(path) as db:
                    db.execute("UPDATE uta_accounts SET snapshot = ? WHERE account_id = ?",
                               (json.dumps(snapshot), "account"))
                before = self.rows(path)
                with self.assertRaisesRegex(SimulatorError, "snapshot differs from replay"):
                    sim.verify_replay("account")
                self.assertEqual(self.rows(path), before)

    def test_replay_accepts_reordered_objects_and_whitespace_without_writes(self):
        for shards in (1, 4):
            with self.subTest(shards=shards):
                sim, path = self.simulator(shards)
                sim.execute("account", "market", 0, self.market_command(sim))
                original = self.rows(path)
                with sqlite3.connect(path) as db:
                    snapshot = db.execute("SELECT snapshot FROM uta_accounts "
                                          "WHERE account_id = 'account'").fetchone()[0]
                    db.execute("UPDATE uta_accounts SET snapshot = ? WHERE account_id = 'account'",
                               (json.dumps(reverse_objects(json.loads(snapshot)), indent=2),))
                    events = db.execute("SELECT version, command, result FROM uta_events "
                                        "WHERE account_id = 'account' ORDER BY version").fetchall()
                    for version, command, receipt in events:
                        db.execute("UPDATE uta_events SET command = ?, result = ? "
                                   "WHERE account_id = 'account' AND version = ?", (
                                       json.dumps(reverse_objects(json.loads(command)), indent=2),
                                       json.dumps(reverse_objects(json.loads(receipt)), indent=2), version))
                formatted = self.rows(path)
                self.assertNotEqual(formatted, original)
                self.assertEqual(sim.verify_replay("account"),
                                 {"account_id": "account", "version": 1, "events_verified": 2})
                self.assertEqual(self.rows(path), formatted)
