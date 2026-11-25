"""Replay must validate the same command envelope as normal submission."""
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest

from uta.simulator import Simulator, SimulatorError


class ReplayCommandTests(unittest.TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.directory = Path(directory.name)
        self.now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        self.sequence = 0

    @staticmethod
    def fill_command():
        return {"type": "fill_order", "order_id": "buy", "quantity": "0.01", "price": "60000"}

    def simulator(self, shards):
        self.sequence += 1
        sim = Simulator(self.directory / f"case-{self.sequence}.sqlite3",
                        clock=lambda: self.now, shards=shards)
        sim.bootstrap("account")
        sim.execute("account", "buy", 0, {
            "type": "place_order", "symbol": "BTC-PERP", "quantity": "0.01",
            "limit_price": "60000", "fee_rate": "0.001",
        })
        sim.execute("account", "fill", 1, self.fill_command())
        store = sim.store if shards == 1 else sim.store._for_account("account")
        return sim, store.path

    @staticmethod
    def rows(path):
        with sqlite3.connect(path) as db:
            return (db.execute("SELECT version, snapshot FROM uta_accounts "
                               "WHERE account_id = 'account'").fetchall(),
                    db.execute("SELECT * FROM uta_events WHERE account_id = 'account' "
                               "ORDER BY version").fetchall())

    def test_replay_rejects_commands_that_execute_rejects(self):
        cases = ({"type": "unknown"}, {"type": None}, {"type": True}, {"extra": True})
        for shards in (1, 4):
            for changes in cases:
                with self.subTest(shards=shards, changes=changes):
                    sim, path = self.simulator(shards)
                    command = {**self.fill_command(), **changes}
                    original = self.rows(path)
                    message = "unrecognized command or incorrect fields"
                    with self.assertRaisesRegex(SimulatorError, message):
                        sim.execute("account", "probe", 2, command)
                    self.assertEqual(self.rows(path), original)
                    with sqlite3.connect(path) as db:
                        db.execute("UPDATE uta_events SET command = ? "
                                   "WHERE account_id = 'account' AND version = 2",
                                   (json.dumps(command),))
                    corrupted = self.rows(path)
                    with self.assertRaisesRegex(SimulatorError, message):
                        sim.verify_replay("account")
                    self.assertEqual(self.rows(path), corrupted)

    def test_replay_rejects_command_identifiers_that_execute_rejects(self):
        for shards in (1, 4):
            for command_id in (None, "", "bad id", ".leading", "x" * 65):
                with self.subTest(shards=shards, command_id=command_id):
                    sim, path = self.simulator(shards)
                    original = self.rows(path)
                    message = "IDs require 1–64"
                    with self.assertRaisesRegex(SimulatorError, message):
                        sim.execute("account", command_id, 2, self.fill_command())
                    self.assertEqual(self.rows(path), original)
                    with sqlite3.connect(path) as db:
                        db.execute("UPDATE uta_events SET command_id = ? "
                                   "WHERE account_id = 'account' AND version = 2", (command_id,))
                    corrupted = self.rows(path)
                    with self.assertRaisesRegex(SimulatorError, message):
                        sim.verify_replay("account")
                    self.assertEqual(self.rows(path), corrupted)

    def test_replay_preserves_recorded_time_when_live_clock_has_advanced(self):
        for shards in (1, 4):
            with self.subTest(shards=shards):
                sim, path = self.simulator(shards)
                self.now += timedelta(days=1)
                self.assertEqual(sim.view("account")["health"], "STALE")
                before = self.rows(path)
                self.assertEqual(sim.verify_replay("account"),
                                 {"account_id": "account", "version": 2, "events_verified": 3})
                self.assertEqual(self.rows(path), before)
