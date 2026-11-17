from dataclasses import FrozenInstanceError, replace
import unittest

from uta.interest_accrual import (AccrualBook, AccrualCommand, AccrualError,
    PrincipalCommand, RateVersion, DAY_NS, YEAR_NS, DENOMINATOR, UNIT_LIMIT,
    MAX_TIMESTAMP_NS, MAX_RECEIPTS)


def book(principal=100, **kw):
    return AccrualBook(loan_id="loan.synthetic.01", account_id="alice", asset="BTC",
                       scale=8, principal_units=principal, as_of_ns=0, **kw)


def rate(ppb=50_000_000, **kw):
    values = dict(rate_id="rate.synthetic", version=1, asset="BTC", scale=8,
                  annual_ppb=ppb, valid_from_ns=0, valid_to_ns=MAX_TIMESTAMP_NS)
    values.update(kw)
    return RateVersion(**values)


def command(target, end, ref="period.01", selected=None, start=None, principal=None):
    s = target.state
    return AccrualCommand(ref, s.cursor_ns if start is None else start, end,
        s.principal_units if principal is None else principal, selected or rate(),
        s.sequence, s.state_hash)


def principal_command(target, after, ref="principal.01", at=None):
    s = target.state
    return PrincipalCommand(ref, s.cursor_ns if at is None else at, after,
                             s.sequence, s.state_hash)


class InterestAccrualTests(unittest.TestCase):
    def assert_code(self, code, function):
        with self.assertRaises(AccrualError) as caught:
            function()
        self.assertEqual(caught.exception.code, code)

    def test_half_year_manual_fraction_preserves_pending_risk(self):
        b = book()
        receipt = b.accrue(command(b, YEAR_NS // 2))
        self.assertEqual(receipt.booked_delta_units, 2)
        self.assertEqual((b.state.cumulative_booked_units, b.state.carry_numerator), (2, DENOMINATOR // 2))
        self.assertEqual(b.state.unbooked_risk_reserve_units, 1)
        self.assertEqual(b.state.principal_units, 100)

    def test_one_unit_per_day_manual_case(self):
        b = book(365)
        for day in range(1, 366):
            receipt = b.accrue(command(b, day * DAY_NS, f"day.{day}", rate(10**9)))
            self.assertEqual(receipt.booked_delta_units, 1)
        self.assertEqual((b.state.cumulative_booked_units, b.state.carry_numerator), (365, 0))

    def test_split_schedule_does_not_charge_each_fraction_upward(self):
        split, whole = book(1), book(1)
        for day in range(1, 366):
            split.accrue(command(split, day * DAY_NS, f"day.{day}", rate(10**9)))
            self.assertEqual(split.state.unbooked_risk_reserve_units, int(day < 365))
        whole.accrue(command(whole, YEAR_NS, selected=rate(10**9)))
        self.assertEqual((split.state.cumulative_booked_units, split.state.carry_numerator), (1, 0))
        self.assertEqual((whole.state.cumulative_booked_units, whole.state.carry_numerator), (1, 0))

    def test_explicit_rate_change_has_no_compounding(self):
        b = book(365)
        half = YEAR_NS // 2
        b.accrue(command(b, half, selected=rate(100_000_000, valid_to_ns=half)))
        b.accrue(command(b, YEAR_NS, "period.02", rate(200_000_000, version=2, valid_from_ns=half)))
        self.assertEqual((b.state.cumulative_booked_units, b.state.carry_numerator),
                         (54, DENOMINATOR * 3 // 4))
        self.assertEqual(b.state.principal_units, 365)

    def test_principal_changes_only_after_accrual_to_that_boundary(self):
        b = book(365)
        half = YEAR_NS // 2
        self.assert_code("principal_requires_accrued_boundary",
                         lambda: b.change_principal(principal_command(b, 182, at=half)))
        b.accrue(command(b, half, selected=rate(10**9)))
        b.change_principal(principal_command(b, 182))
        b.accrue(command(b, YEAR_NS, "period.02", rate(10**9)))
        self.assertEqual((b.state.cumulative_booked_units, b.state.carry_numerator),
                         (273, DENOMINATOR // 2))

    def test_leap_elapsed_days_use_fixed_365_basis(self):
        b = book(365)
        b.accrue(command(b, 366 * DAY_NS, selected=rate(10**9)))
        self.assertEqual((b.state.cumulative_booked_units, b.state.carry_numerator), (366, 0))

    def test_zero_rate_and_zero_principal_do_not_discard_existing_carry(self):
        b = book(1, carry_numerator=DENOMINATOR // 2)
        b.accrue(command(b, DAY_NS, selected=rate(0)))
        b.change_principal(principal_command(b, 0))
        b.accrue(command(b, 2 * DAY_NS, "period.02", rate(0)))
        self.assertEqual((b.state.cumulative_booked_units, b.state.carry_numerator), (0, DENOMINATOR // 2))
        self.assertEqual(b.state.unbooked_risk_reserve_units, 1)

    def test_historical_retry_returns_original_without_rewinding_state(self):
        b = book()
        first = command(b, DAY_NS)
        original = b.accrue(first)
        b.accrue(command(b, 2 * DAY_NS, "period.02"))
        current = b.state
        self.assertIs(b.accrue(first), original)
        self.assertIs(b.state, current)
        self.assertIs(b.receipt(first.reference), original)
        self.assert_code("reference_conflict", lambda: b.accrue(replace(first, end_ns=2 * DAY_NS)))
        self.assertIs(b.state, current)

    def test_checkpoint_and_principal_disagreement_leave_state_unchanged(self):
        b = book()
        initial = b.state
        good = command(b, DAY_NS)
        self.assert_code("checkpoint_conflict", lambda: b.accrue(replace(good, expected_sequence=1)))
        self.assert_code("checkpoint_conflict", lambda: b.accrue(replace(good, expected_state_hash="f" * 64)))
        self.assert_code("principal_checkpoint_mismatch", lambda: b.accrue(replace(good, principal_units=101)))
        self.assertIs(b.state, initial)

    def test_gap_overlap_empty_negative_and_oversize_intervals_reject(self):
        b = book()
        self.assert_code("interval_gap_or_overlap", lambda: b.accrue(command(b, DAY_NS, start=1)))
        for start, end in [(0, 0), (1, 0), (-1, 1), (0, 367 * DAY_NS), (0, MAX_TIMESTAMP_NS + 1)]:
            with self.subTest(start=start, end=end):
                self.assert_code("interval_invalid", lambda: b.accrue(command(b, end, start=start)))
        b.accrue(command(b, DAY_NS))
        self.assert_code("interval_gap_or_overlap", lambda: b.accrue(command(b, 2 * DAY_NS, "late", start=0)))

    def test_rate_period_end_equal_is_valid_but_incomplete_cover_is_not(self):
        b = book()
        r = rate(valid_to_ns=DAY_NS)
        self.assert_code("rate_not_effective", lambda: b.accrue(command(b, DAY_NS + 1, selected=r)))
        b.accrue(command(b, DAY_NS, selected=r))
        self.assert_code("rate_not_effective", lambda: b.accrue(command(b, 2 * DAY_NS, "next", r)))

    def test_same_rate_version_cannot_change_its_payload(self):
        b = book()
        b.accrue(command(b, DAY_NS))
        self.assert_code("rate_version_conflict", lambda: b.accrue(
            command(b, 2 * DAY_NS, "next", rate(60_000_000))))
        self.assert_code("rate_currency_mismatch", lambda: b.accrue(
            command(b, 2 * DAY_NS, "other", rate(asset="USD"))))

    def test_numeric_policy_rejects_bool_float_strings_and_bad_rates(self):
        for invalid in [True, False, "1", 1.0, -1, UNIT_LIMIT]:
            with self.subTest(principal=invalid):
                self.assert_code("principal_invalid", lambda: book(invalid))
        for invalid in [True, "1", 1.0, -1, 10**9 + 1]:
            with self.subTest(rate=invalid):
                self.assert_code("rate_out_of_policy", lambda: rate(invalid))
        self.assert_code("day_count_unsupported", lambda: rate(day_count="ACT_360"))
        b = book()
        self.assert_code("interval_invalid", lambda: b.accrue(replace(command(b, DAY_NS), start_ns=True)))
        self.assert_code("sequence_invalid", lambda: b.accrue(replace(command(b, DAY_NS), expected_sequence=False)))

    def test_currency_scale_carry_and_risk_overflow_are_explicit(self):
        self.assert_code("scale_invalid", lambda: AccrualBook(loan_id="x", account_id="a", asset="BTC", scale=19, principal_units=0, as_of_ns=0))
        self.assert_code("asset_invalid", lambda: AccrualBook(loan_id="x", account_id="a", asset="btc", scale=8, principal_units=0, as_of_ns=0))
        self.assert_code("carry_invalid", lambda: book(carry_numerator=DENOMINATOR))
        self.assert_code("risk_units_overflow", lambda: book(cumulative_booked_units=UNIT_LIMIT - 1, carry_numerator=1))
        b = book(365, cumulative_booked_units=UNIT_LIMIT - 1)
        before = b.state
        self.assert_code("risk_units_overflow", lambda: b.accrue(command(b, DAY_NS, selected=rate(10**9))))
        self.assertIs(b.state, before)

    def test_receipts_are_immutable_and_scope_contains_the_original_identity(self):
        b = book()
        receipt = b.accrue(command(b, DAY_NS))
        with self.assertRaises(FrozenInstanceError):
            receipt.after.principal_units = 0
        self.assertIn('"loan_id":"loan.synthetic.01"', receipt.request_payload)
        self.assertIn('"account_id":"alice"', receipt.request_payload)
        self.assert_code("reference_unknown", lambda: b.receipt("unknown"))

    def test_bounded_history_still_allows_original_retries(self):
        b = book(0)
        first = command(b, 1, "event.0", rate(0))
        original = b.accrue(first)
        for i in range(1, MAX_RECEIPTS):
            b.accrue(command(b, i + 1, f"event.{i}", rate(0)))
        self.assertEqual(b.state.sequence, MAX_RECEIPTS)
        self.assert_code("receipt_capacity", lambda: b.accrue(command(b, MAX_RECEIPTS + 1, "overflow", rate(0))))
        current = b.state
        self.assertIs(b.accrue(first), original)
        self.assertIs(b.state, current)


if __name__ == "__main__":
    unittest.main()
