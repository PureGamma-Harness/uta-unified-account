import concurrent.futures
import unittest
from decimal import Decimal, localcontext

from uta.ledger import JournalEvent, Ledger, LedgerError, Posting


D = Decimal


class LedgerTests(unittest.TestCase):
    def setUp(self):
        self.ledger = Ledger({"USDT": 6, "BTC": 8})

    @staticmethod
    def transfer(amount=D("12.500000")):
        return [Posting("external", "USDT", -amount),
                Posting("customer", "USDT", amount)]

    def test_replay_and_idempotency_with_reordered_postings(self):
        event = self.ledger.post("deposit:1", self.transfer())
        self.assertEqual(event, self.ledger.post("deposit:1", self.transfer()[::-1]))
        self.assertEqual(len(self.ledger.journal()), 1)
        restored = Ledger.replay({"USDT": 6, "BTC": 8}, self.ledger.journal())
        self.assertEqual(restored.balance("customer", "USDT"), D("12.5"))
        self.assertEqual(restored.balance("external", "USDT"), D("-12.5"))
        with self.assertRaises(LedgerError):
            restored.post("deposit:1", self.transfer(D("13")))

    def test_atomic_rejection_for_unbalanced_or_invalid_events(self):
        self.ledger.post("valid", self.transfer())
        before = self.ledger.journal()
        bad = [Posting("external", "USDT", D("-1")), Posting("customer", "USDT", D("2"))]
        with self.assertRaises(LedgerError):
            self.ledger.post("bad", bad)
        with self.assertRaises(LedgerError):
            self.ledger.post("bad", self.transfer(D("0.0000001")))
        self.assertEqual(self.ledger.journal(), before)
        self.assertEqual(self.ledger.balance("customer", "USDT"), D("12.5"))
        # A rejected ID remains reusable for a valid event.
        self.ledger.post("bad", self.transfer(D("1")))
        self.assertEqual(self.ledger.balance("customer", "USDT"), D("13.5"))

    def test_cross_asset_event_requires_balance_for_each_asset(self):
        # An exchange trade must supply both sides for each asset, not net USD
        # and BTC as if they shared a unit of account.
        postings = [Posting("customer", "USDT", D("-100")),
                    Posting("exchange", "USDT", D("100")),
                    Posting("customer", "BTC", D("0.001")),
                    Posting("exchange", "BTC", D("-0.001"))]
        self.ledger.post("trade", postings)
        self.assertEqual(self.ledger.balance("customer", "BTC"), D("0.001"))
        with self.assertRaises(LedgerError):
            self.ledger.post("invalid-trade", postings[:-1])

    def test_exactness_is_independent_of_decimal_context(self):
        postings = [Posting("a", "USDT", D("-12345678901234567890.123456")),
                    Posting("b", "USDT", D("12345678901234567890.123456"))]
        with localcontext() as ctx:
            ctx.prec = 4
            self.ledger.post("large", postings)
            self.assertEqual(self.ledger.balance("b", "USDT"), D("12345678901234567890.123456"))

    def test_replay_rejects_gaps_and_duplicate_ids(self):
        one = self.ledger.post("x", self.transfer())
        with self.assertRaises(LedgerError):
            Ledger.replay({"USDT": 6}, [JournalEvent("x", 2, one.postings)])
        with self.assertRaises(LedgerError):
            Ledger.replay({"USDT": 6}, [one, JournalEvent("x", 2, one.postings)])

    def test_replay_preserves_wide_journal_amounts_and_idempotency(self):
        scales = {"USD": 18}
        ledger = Ledger(scales, unit_digits=60)
        deposit = [
            Posting("external", "USD", D("-10000000000000000000000000.123456789012345678")),
            Posting("customer", "USD", D("10000000000000000000000000.123456789012345678")),
        ]
        ledger.post("deposit", deposit)
        ledger.post("withdraw", [Posting("customer", "USD", D("-0.000000000000000001")),
                                 Posting("external", "USD", D("0.000000000000000001"))])
        with localcontext() as ctx:
            ctx.prec = 2
            restored = Ledger.replay(scales, ledger.journal(), unit_digits=60)
        self.assertEqual(restored.journal(), ledger.journal())
        self.assertEqual(restored.balance("customer", "USD"),
                         D("10000000000000000000000000.123456789012345677"))
        self.assertIs(restored.post("deposit", deposit[::-1]), restored.journal()[0])
        # Wider histories must not silently enlarge the default replay policy.
        with self.assertRaises(LedgerError):
            Ledger.replay(scales, ledger.journal())

    def test_replay_keeps_requested_balance_limit_for_new_events(self):
        restored = Ledger.replay({"USD": 0}, [], unit_digits=40)
        maximum = D("9" * 40)
        restored.post("maximum", [Posting("external", "USD", maximum.copy_negate()),
                                  Posting("customer", "USD", maximum)])
        before = restored.journal()
        with self.assertRaisesRegex(LedgerError, "balance exceeds supported range"):
            restored.post("overflow", [Posting("external", "USD", D("-1")),
                                       Posting("customer", "USD", D("1"))])
        self.assertEqual(restored.journal(), before)
        self.assertEqual(restored.balance("customer", "USD"), maximum)

    def test_concurrent_retries_commit_once(self):
        def post(_):
            return self.ledger.post("retry", self.transfer())
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            results = list(executor.map(post, range(100)))
        self.assertTrue(all(result == results[0] for result in results))
        self.assertEqual(len(self.ledger.journal()), 1)
        self.assertEqual(self.ledger.balance("customer", "USDT"), D("12.5"))


if __name__ == "__main__":
    unittest.main()
