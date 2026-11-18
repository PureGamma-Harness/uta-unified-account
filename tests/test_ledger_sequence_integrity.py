"""Synthetic reference-journal recovery cases; no database or external funds."""
from decimal import Decimal, localcontext
from fractions import Fraction
import unittest

from uta.ledger import JournalEvent, Ledger, LedgerError, Posting


class IntAlias(int):
    pass


class EqualityAlias:
    def __eq__(self, other):
        return other == 1


def dollars(amount="1"):
    value = Decimal(amount)
    return (Posting("clearing", "USD", value.copy_negate()),
            Posting("customer", "USD", value))


class LedgerSequenceIntegrityTests(unittest.TestCase):
    def test_numeric_aliases_reject_before_any_posting(self):
        # A valid USD1 transfer with corrupt sequence metadata must never post.
        class NoPostingLedger(Ledger):
            def post(self, event_id, postings):
                self.fail_post_was_reached = True
                raise AssertionError("invalid sequence reached journal posting")

        for sequence in (True, 1.0, Decimal("1"), Fraction(1), IntAlias(1), EqualityAlias()):
            with self.subTest(type=type(sequence).__name__):
                with self.assertRaisesRegex(LedgerError, "journal sequence is missing or out of order"):
                    NoPostingLedger.replay({"USD": 2}, [JournalEvent("deposit", sequence, dollars())])

    def test_consecutive_native_sequences_recover_exact_two_asset_balances(self):
        trade = JournalEvent("trade", 1, (
            Posting("customer", "USD", Decimal("-100")),
            Posting("clearing", "USD", Decimal("100")),
            Posting("customer", "BTC", Decimal("0.00123456")),
            Posting("clearing", "BTC", Decimal("-0.00123456")),
        ))
        fee = JournalEvent("fee", 2, (
            Posting("customer", "USD", Decimal("-0.25")),
            Posting("fees", "USD", Decimal("0.25")),
        ))
        with localcontext() as context:
            context.prec = 2
            restored = Ledger.replay({"USD": 2, "BTC": 8}, [trade, fee])
        expected = {
            ("customer", "USD"): Decimal("-100.25"),
            ("clearing", "USD"): Decimal("100"),
            ("fees", "USD"): Decimal("0.25"),
            ("customer", "BTC"): Decimal("0.00123456"),
            ("clearing", "BTC"): Decimal("-0.00123456"),
        }
        for (account, asset), amount in expected.items():
            self.assertEqual(restored.balance(account, asset), amount)
        self.assertEqual(tuple(event.sequence for event in restored.journal()), (1, 2))
        self.assertEqual(len(restored.journal()), 2)

    def test_gaps_ordering_and_duplicate_business_ids_still_reject(self):
        first = JournalEvent("deposit", 1, dollars())
        invalid = (
            [JournalEvent("zero", 0, dollars())],
            [JournalEvent("negative", -1, dollars())],
            [JournalEvent("gap", 2, dollars())],
            [first, JournalEvent("gap", 3, dollars())],
            [first, JournalEvent("repeated_sequence", 1, dollars())],
            [first, JournalEvent("deposit", 2, dollars())],
        )
        for index, events in enumerate(invalid):
            with self.subTest(case=index), self.assertRaises(LedgerError):
                Ledger.replay({"USD": 2}, events)

    def test_live_receipts_and_retries_keep_native_sequences(self):
        live = Ledger({"USD": 2})
        first = live.post("deposit", dollars())
        second = live.post("deposit-2", dollars("2"))
        self.assertIs(live.post("deposit", tuple(reversed(dollars()))), first)
        self.assertIs(type(first.sequence), int)
        self.assertIs(type(second.sequence), int)
        recovered = Ledger.replay({"USD": 2}, live.journal())
        self.assertEqual(recovered.balance("customer", "USD"), Decimal("3"))
        self.assertEqual(recovered.balance("clearing", "USD"), Decimal("-3"))
        self.assertEqual(recovered.journal(), live.journal())


if __name__ == "__main__":
    unittest.main()
