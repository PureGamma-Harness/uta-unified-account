"""Local SQLite fill races, not venue or multi-node execution guarantees."""
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal as D
from threading import Barrier
import unittest

import test_service_catalog as fixture_module
from uta.service import ServiceError


class FillRaceTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixture_module.ServiceCatalogTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.service = self.fixture.funded()
        self.service.submit_order('alice', 'order', 'X', D('1'), D('100'))

    def race(self, specifications):
        peers = [self.fixture.create() for _ in specifications]
        barrier = Barrier(len(peers))
        def apply(index):
            fill_id, quantity = specifications[index]
            barrier.wait(timeout=10)
            try:
                peers[index].apply_fill('alice', 'order', fill_id, D(quantity), D('100'))
                return 'ok'
            except ServiceError as error:
                return error.code
        with ThreadPoolExecutor(max_workers=len(peers)) as pool:
            return list(pool.map(apply, range(len(peers))))

    def snapshot(self):
        with self.service.database.transaction() as connection:
            return '\n'.join(connection.iterdump())

    def assert_fill_state(self, count, quantity):
        with self.service.database.transaction() as connection:
            self.assertEqual(connection.execute('SELECT COUNT(*) FROM uta_fills').fetchone()[0], count)
            actual = connection.execute("SELECT filled_quantity FROM uta_orders WHERE order_id='order'").fetchone()[0]
            self.assertEqual(D(actual), D(quantity))
        self.service.ledger.verify()

    def test_concurrent_equivalent_fill_replays_are_one_effect(self):
        results = self.race([('same', '.50' if index % 2 else '.5') for index in range(8)])
        self.assertEqual(results, ['ok'] * 8)
        self.assert_fill_state(1, '.5')
        before = self.snapshot()
        reopened = self.fixture.create()
        reopened.apply_fill('alice', 'order', 'same', D('.500'), D('100.00'))
        with self.assertRaises(ServiceError) as rejected:
            reopened.apply_fill('alice', 'order', 'same', D('.6'), D('100'))
        self.assertEqual(rejected.exception.code, 'idempotency_conflict')
        self.assertEqual(self.snapshot(), before)

    def test_distinct_fill_ids_cannot_race_past_remaining_quantity(self):
        # Either request may win; the assertion does not depend on scheduling.
        results = self.race([('one', '.6'), ('two', '.6')])
        self.assertCountEqual(results, ['ok', 'invalid_fill'])
        self.assert_fill_state(1, '.6')
        reopened = self.fixture.create()
        reopened.apply_fill('alice', 'order', 'remainder', D('.4'), D('100'))
        self.assert_fill_state(2, '1')
        self.assertEqual(reopened.orders('alice')[0]['status'], 'FILLED')
