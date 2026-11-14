from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest

from uta.service import ExchangeService, ServiceError
from uta.sharding import ShardRouter
from uta.storage import Database
from uta.store import Store, StoreConflict


class ShardAuthorityTests(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name) / "router"

    @staticmethod
    def dump(path):
        with sqlite3.connect(path) as conn:
            return tuple(conn.iterdump())

    def test_control_cannot_be_opened_as_exchange_or_research(self):
        router = ShardRouter(self.directory, 1, {"USD": 8})
        before = self.dump(router.control.path)
        with self.assertRaises(ServiceError) as error:
            ExchangeService(Database(router.control.path), {"USD": 8})
        self.assertEqual(error.exception.code, "wrong_authority")
        with self.assertRaises(StoreConflict):
            Store(router.control.path)
        self.assertEqual(self.dump(router.control.path), before)

    def test_exchange_cannot_be_used_as_router_control(self):
        self.directory.mkdir(mode=0o700)
        path = self.directory / "router.sqlite3"
        ExchangeService(Database(path), {"USD": 8})
        before = self.dump(path)
        with self.assertRaises(ServiceError) as error:
            ShardRouter(self.directory, 1, {"USD": 8})
        self.assertEqual(error.exception.code, "wrong_authority")
        self.assertEqual(self.dump(path), before)

    def test_existing_router_can_claim_legacy_control_without_mutating_funds(self):
        router = ShardRouter(self.directory, 1, {"USD": 8})
        router.create_account("alice")
        with router.control.transaction() as conn:
            conn.execute("DROP TABLE uta_authority")
        reopened = ShardRouter(self.directory, 1, {"USD": 8})
        self.assertEqual(reopened.account("alice")["balances"], {"USD": "0"})
        self.assertTrue(reopened._state()["halted"])


if __name__ == "__main__":
    unittest.main()
