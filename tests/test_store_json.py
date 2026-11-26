"""Stored objects must be unambiguous and contain only finite numbers."""
from datetime import datetime, timezone
from http.client import HTTPConnection
import json
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
from threading import Thread
import unittest

from uta.server import make_server
from uta.simulator import Simulator
from uta.store import ShardedStore, Store, StoreError


NONFINITE = ("NaN", "Infinity", "-Infinity", "1e400", "-1e400")


def increment(state):
    state["units"] += 1
    return state, {"units": state["units"]}


class StoredJsonTests(unittest.TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.directory = Path(directory.name)
        self.sequence = 0

    def path(self):
        self.sequence += 1
        return self.directory / f"case-{self.sequence}.sqlite3"

    @staticmethod
    def account_path(store):
        return (store if isinstance(store, Store) else store._for_account("account")).path

    @staticmethod
    def rows(path):
        with sqlite3.connect(path) as db:
            return (db.execute("SELECT * FROM uta_accounts ORDER BY account_id").fetchall(),
                    db.execute("SELECT * FROM uta_events ORDER BY account_id, version").fetchall())

    def store(self, shards):
        store = Store(self.path()) if shards == 1 else ShardedStore(self.path(), shards=shards)
        store.create("account", {"units": 0})
        return store, self.account_path(store)

    def test_read_and_new_command_reject_invalid_snapshots(self):
        invalid = (
            '{"version":9,"version":0,"units":0}',
            '{"version":0,"units":0,"nested":{"x":1,"\\u0078":1}}',
            '{"version":0,"units":0,"nested":[{"x":1,"x":2}]}',
            *('{"version":0,"units":0,"nested":[' + value + ']}' for value in NONFINITE),
        )
        for shards in (1, 4):
            for raw in invalid:
                with self.subTest(shards=shards, raw=raw):
                    store, path = self.store(shards)
                    with sqlite3.connect(path) as db:
                        db.execute("UPDATE uta_accounts SET snapshot = ?", (raw,))
                    before = self.rows(path)
                    with self.assertRaisesRegex(StoreError, "stored JSON is invalid"):
                        store.read("account")
                    with self.assertRaisesRegex(StoreError, "stored JSON is invalid"):
                        store.apply("account", "new", 0, {"type": "increment"},
                                    lambda _: self.fail("invalid snapshot reached the transition"))
                    self.assertEqual(self.rows(path), before)

    def test_event_read_and_retry_reject_invalid_receipts(self):
        invalid = (
            '{"version":9,"version":1,"units":1}',
            '{"version":1,"units":1,"units":1}',
            *('{"version":1,"units":1,"nested":[' + value + ']}' for value in NONFINITE),
        )
        for shards in (1, 4):
            for raw in invalid:
                with self.subTest(shards=shards, raw=raw):
                    store, path = self.store(shards)
                    command = {"type": "increment"}
                    store.apply("account", "first", 0, command, increment)
                    with sqlite3.connect(path) as db:
                        db.execute("UPDATE uta_events SET result = ? WHERE version = 1", (raw,))
                    before = self.rows(path)
                    with self.assertRaisesRegex(StoreError, "stored JSON is invalid"):
                        store.events("account")
                    with self.assertRaisesRegex(StoreError, "stored JSON is invalid"):
                        store.apply("account", "first", 0, command,
                                    lambda _: self.fail("retry ran the transition"))
                    self.assertEqual(store.read("account")["version"], 1)
                    self.assertEqual(self.rows(path), before)

    def test_replay_rejects_duplicate_fields_before_comparing_records(self):
        for shards in (1, 4):
            for target in ("command", "result", "snapshot", "creation_result"):
                with self.subTest(shards=shards, target=target):
                    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
                    sim = Simulator(self.path(), clock=lambda: now, shards=shards)
                    sim.bootstrap("account")
                    sim.execute("account", "buy", 0, {
                        "type": "place_order", "symbol": "BTC-PERP", "quantity": "0.01",
                        "limit_price": "60000", "fee_rate": "0.001",
                    })
                    command = {"type": "fill_order", "order_id": "buy",
                               "quantity": "0.01", "price": "60000"}
                    receipt = sim.execute("account", "fill", 1, command)
                    path = self.account_path(sim.store)
                    with sqlite3.connect(path) as db:
                        if target == "command":
                            raw = '{"type":"unknown",' + json.dumps(command)[1:]
                            db.execute("UPDATE uta_events SET command = ? WHERE version = 2", (raw,))
                        elif target == "result":
                            raw = '{"version":999,' + json.dumps(receipt)[1:]
                            db.execute("UPDATE uta_events SET result = ? WHERE version = 2", (raw,))
                        elif target == "snapshot":
                            raw = '{"version":999,' + json.dumps(sim.store.read("account"))[1:]
                            db.execute("UPDATE uta_accounts SET snapshot = ?", (raw,))
                        else:
                            db.execute('UPDATE uta_events SET result = ? WHERE version = 0',
                                       ('{"version":999,"version":0}',))
                    before = self.rows(path)
                    with self.assertRaisesRegex(StoreError, "stored JSON is invalid"):
                        sim.verify_replay("account")
                    self.assertEqual(self.rows(path), before)

    def test_valid_nested_values_survive_reopen_and_retry(self):
        values = [{"x": 1}, {"x": 2}, [True, None, 1, 1.25, -0.0, 1e308, 2**100],
                  {"中文": "NaN", "Infinity": "-Infinity"}]
        for shards in (1, 4):
            with self.subTest(shards=shards):
                path = self.path()
                store = Store(path) if shards == 1 else ShardedStore(path, shards=shards)
                store.create("account", {"units": 0, "values": values})
                receipt = store.apply("account", "first", 0, {"type": "increment"}, increment)
                before = self.rows(self.account_path(store))
                reopened = Store(path) if shards == 1 else ShardedStore(path, shards=shards)
                state = reopened.read("account")
                self.assertEqual(state, {"units": 1, "values": values, "version": 1})
                self.assertIs(type(state["values"][2][0]), bool)
                self.assertIs(type(state["values"][2][2]), int)
                self.assertIs(type(state["values"][2][3]), float)
                self.assertEqual(reopened.apply("account", "first", 0, {"type": "increment"},
                                                lambda _: self.fail("retry ran the transition")), receipt)
                self.assertEqual(len(reopened.events("account")), 2)
                self.assertEqual(self.rows(self.account_path(reopened)), before)

    def test_http_replay_reports_invalid_stored_json_as_unavailable(self):
        for shards in (1, 4):
            for raw in ('{"version":999,"version":0}', '{"version":0,"extra":NaN}'):
                with self.subTest(shards=shards, raw=raw):
                    sim = Simulator(self.path(), shards=shards)
                    sim.bootstrap("account")
                    path = self.account_path(sim.store)
                    with sqlite3.connect(path) as db:
                        db.execute("UPDATE uta_events SET result = ? WHERE version = 0", (raw,))
                    before = self.rows(path)
                    with make_server(sim) as server:
                        thread = Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01})
                        thread.start()
                        connection = HTTPConnection("127.0.0.1", server.server_port, timeout=2)
                        try:
                            connection.request("GET", "/v1/accounts/account/replay")
                            response = connection.getresponse()
                            data = json.loads(response.read())
                            self.assertEqual(response.status, 503)
                            self.assertEqual(data, {"error": "account store unavailable"})
                        finally:
                            connection.close()
                            server.shutdown()
                            thread.join(timeout=2)
                        self.assertFalse(thread.is_alive())
                    self.assertEqual(self.rows(path), before)
