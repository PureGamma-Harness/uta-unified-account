import threading
import unittest
from decimal import Decimal as D, localcontext

from uta.reservations import (IdempotencyConflict, InsufficientMargin,
                              ReservationBook, ReservationError, VersionConflict)


class ReservationTests(unittest.TestCase):
    def test_concurrent_orders_cannot_reserve_same_capacity(self):
        book = ReservationBook(D('100'))
        barrier = threading.Barrier(20)
        outcomes = []
        lock = threading.Lock()

        def submit(i):
            barrier.wait()
            while True:
                version = book.snapshot().version
                try:
                    book.reserve(str(i), D('30'), expected_version=version)
                    result = 'accepted'
                    break
                except VersionConflict:
                    continue
                except InsufficientMargin:
                    result = 'rejected'
                    break
            with lock:
                outcomes.append(result)

        threads = [threading.Thread(target=submit, args=(i,)) for i in range(20)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=5)
            self.assertFalse(thread.is_alive())
        self.assertEqual(outcomes.count('accepted'), 3)
        self.assertEqual(outcomes.count('rejected'), 17)
        self.assertEqual(book.snapshot().reserved, D('90'))
        self.assertEqual(book.snapshot().available, D('10'))

    def test_idempotency_release_and_replay_cannot_reopen(self):
        book = ReservationBook(D('100'))
        first = book.reserve('order-1', D('60'), expected_version=0)
        self.assertEqual(book.reserve('order-1', D('60'), expected_version=0), first)
        self.assertEqual(book.snapshot().version, 1)
        with self.assertRaises(IdempotencyConflict):
            book.reserve('order-1', D('61'), expected_version=1)
        with self.assertRaises(VersionConflict):
            book.release('order-1', expected_version=0)
        released = book.release('order-1', expected_version=1)
        self.assertFalse(released.active)
        self.assertEqual(book.release('order-1', expected_version=0), released)
        self.assertEqual(book.reserve('order-1', D('60'), expected_version=0), released)
        self.assertEqual(book.snapshot().available, D('100'))
        self.assertEqual(book.snapshot().version, 2)

    def test_capacity_drop_blocks_new_orders_but_keeps_reserve(self):
        book = ReservationBook(D('100'))
        book.reserve('old', D('80'), expected_version=0)
        snapshot = book.update_capacity(D('40'), expected_version=1)
        self.assertEqual(snapshot.available, D('-40'))
        with self.assertRaises(InsufficientMargin):
            book.reserve('new', D('1'), expected_version=2)
        self.assertEqual(book.snapshot(), snapshot)
        book.release('old', expected_version=2)
        self.assertEqual(book.snapshot().available, D('40'))

    def test_stale_version_and_invalid_amounts_fail_without_mutation(self):
        book = ReservationBook(D('2'))
        for value in [D('NaN'), D('Infinity'), D('-1'), D('0'), D('0E+999999'),
                      D('0.0000000000000000001'), 1.0]:
            with self.subTest(value=value), self.assertRaises(ReservationError):
                book.reserve('x', value, expected_version=0)
        with self.assertRaises(VersionConflict):
            book.update_capacity(D('3'), expected_version=1)
        with self.assertRaises(ReservationError):
            book.release('missing', expected_version=0)
        self.assertEqual(book.snapshot().version, 0)
        self.assertEqual(book.snapshot().reserved, D('0'))

    def test_decimal_arithmetic_not_affected_by_low_caller_precision(self):
        with localcontext() as ctx:
            ctx.prec = 4
            book = ReservationBook(D('123456789.123456789123456789'))
            book.reserve('precise', D('123456788.123456789123456788'), expected_version=0)
            self.assertEqual(book.snapshot().available, D('1.000000000000000001'))


if __name__ == '__main__':
    unittest.main()
