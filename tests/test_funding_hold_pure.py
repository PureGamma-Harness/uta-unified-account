"""Unrun D1 pure-data contracts; no SQL, clock, actor or financial service.

Expected unit values come from public synthetic manual cases, never another
production calculation. A separate group supplies an independent Fraction oracle.
"""
from dataclasses import FrozenInstanceError, replace
from decimal import Decimal
import unittest

from uta import funding_hold_pure as h


def scope(account="synthetic-payer", scale=2):
    return h.Scope("synthetic-authority", "synthetic-generation", account, scale, "USD")


def key(symbol="SYNTH-USD-PERP", account="synthetic-payer", rule="synthetic-approved-funding-rules-v1", interval=28800):
    return h.DutyKey("synthetic-authority", "synthetic-generation", symbol,
        "2026-01-01T00:00:00+00:00", interval, "USD", account, rule, 1)


def ref(k, kind, digit="1"):
    return h.ContentRef(kind, digit * 64, k.duty_id, k.rule_scope_id)


def final(k, amount, kind="FINAL_PAYABLE", scale=2):
    initial = h.DutyState.initial(k, scale)
    stage = h.Stage(kind, amount, None, None, ref(k, "FINAL_CUT", "3"))
    return h.advance_stage(initial, stage, expected_revision=0, expected_active_stage=initial.active)


def cap(k, amount=600):
    initial = h.DutyState.initial(k, 2)
    stage = h.Stage("EXPOSURE_RATE_PENDING", amount, ref(k, "EXPOSURE"), ref(k, "CAP", "2"), None)
    return h.advance_stage(initial, stage, expected_revision=0, expected_active_stage=initial.active)


def totals(states):
    return h.aggregate(states, scope(), basis_complete=True)


def base(accounting=10000, risk=10000, im=2000, mm=1000, reserve=3000, cash=10000, frozen=0):
    return h.BaseValues(scope(), accounting, risk, im, mm, reserve, cash, frozen, "EXCLUDED")


def backing(states, own, cash, frozen=0, clear=True, quote=True):
    return h.backing_precondition(states, scope(), own.key.duty_id, cash_units=cash,
        spot_frozen_units=frozen, prior_confirmed_settlements_clear=clear,
        quote_available=quote, basis_complete=True)


def policy(max_wait=30000000, attempts=4):
    return h.WaitPolicy(1, "SYNTHETIC-PFH-WAIT-v1", "TRUSTED_UTC_PERSISTENT_HIGH_WATERMARK",
        max_wait, 5000000, attempts, "DEFAULT_REVIEW_PRESERVE_DEBT_FREEZE_AND_OUTBOX")


def wait_record(p=None):
    return h.WaitRecord.initial(h.ActionKey(scope(), "synthetic-allocation"), policy() if p is None else p, 0)


def wait(record, now, dispatch=False):
    return h.preview_wait(record, now_us=now, expected_revision=record.revision,
                          expected_policy_digest=record.policy.digest, dispatch_query=dispatch)


class PureFundingHoldTests(unittest.TestCase):
    def test_complete_stage_CAS_rejects_stale_exposure_amount_and_kind(self):
        old = cap(key())
        proposed = h.Stage("FINAL_PAYABLE", 246, old.active.exposure_ref,
                           old.active.cap_ref, ref(old.key, "FINAL_CUT", "3"))
        expected_states = (
            replace(old.active, exposure_ref=ref(old.key, "EXPOSURE", "5")),
            replace(old.active, amount_units=599),
            replace(old.active, cap_ref=ref(old.key, "CAP", "4")),
            h.Stage("REGISTERED_UNASSESSED", 0, None, None, None),
        )
        for expected in expected_states:
            with self.subTest(kind=expected.kind, amount=expected.amount_units):
                with self.assertRaisesRegex(h.HoldError, "stage_CAS_conflict"):
                    h.advance_stage(old, proposed, expected_revision=1,
                                    expected_active_stage=expected)
        self.assertEqual((old.revision, old.active.amount_units), (1, 600))
        self.assertEqual(proposed.amount_units, 246)

    def test_complete_stage_CAS_rejects_foreign_malformed_and_legacy_expectation(self):
        old = cap(key())
        proposed = h.Stage("FINAL_ZERO", 0, old.active.exposure_ref,
                           old.active.cap_ref, ref(old.key, "FINAL_CUT", "3"))
        foreign = replace(old.active, exposure_ref=ref(key("OTHER"), "EXPOSURE"))
        with self.assertRaisesRegex(h.HoldError, "foreign_stage_reference"):
            h.advance_stage(old, proposed, expected_revision=1, expected_active_stage=foreign)
        for expected in (None, old.active.cap_ref, True):
            with self.assertRaises(h.HoldError):
                h.advance_stage(old, proposed, expected_revision=1, expected_active_stage=expected)
        with self.assertRaises(TypeError):
            h.advance_stage(old, proposed, expected_revision=1, expected_active_ref=old.active.cap_ref)
        self.assertEqual(old.history, (h.Stage("REGISTERED_UNASSESSED", 0, None, None, None),))

    def test_wait_same_time_noop_preserves_original_normal_and_default_records(self):
        normal = wait_record()
        same = wait(normal, 0)
        self.assertIs(same.record, normal)
        self.assertEqual((same.outcome, same.query_counted, same.record.revision), ("WAIT", False, 0))
        expired = wait(normal, normal.deadline_us).record
        for dispatch in (False, True):
            same = wait(expired, expired.observed_highwater_us, dispatch)
            self.assertIs(same.record, expired)
            self.assertEqual((same.outcome, same.query_counted), ("DEFAULT_REVIEW", False))

    def test_wait_revision_exhaustion_allows_only_actual_noop(self):
        normal = replace(wait_record(), revision=h.TIME_LIMIT)
        self.assertIs(wait(normal, 0).record, normal)
        for now, dispatch in ((1, False), (0, True)):
            with self.assertRaisesRegex(h.HoldError, "revision_overflow"):
                wait(normal, now, dispatch)
        default = replace(normal, default_review=True)
        self.assertIs(wait(default, 0, True).record, default)
        # Same time alone is insufficient: reaching a boundary changes default.
        at_deadline = replace(normal, observed_highwater_us=normal.deadline_us)
        at_cap = replace(normal, attempts=normal.policy.max_query_attempts, last_dispatch_us=0)
        for record in (at_deadline, at_cap):
            with self.assertRaisesRegex(h.HoldError, "revision_overflow"):
                wait(record, record.observed_highwater_us)
        self.assertEqual((normal.attempts, normal.default_review, normal.revision),
                         (0, False, h.TIME_LIMIT))

    def test_wait_interval_and_deadline_equality_do_not_grant_late_query(self):
        first = wait(wait_record(), 0, True).record
        with self.assertRaisesRegex(h.HoldError, "query_too_early"):
            wait(first, first.policy.min_query_interval_us - 1, True)
        second = wait(first, first.policy.min_query_interval_us, True)
        self.assertEqual((second.record.attempts, second.query_counted), (2, True))
        deadline = wait(first, first.deadline_us, True)
        self.assertEqual((deadline.outcome, deadline.record.attempts, deadline.query_counted),
                         ("DEFAULT_REVIEW", 1, False))
        self.assertEqual((first.attempts, first.observed_highwater_us), (1, 0))

    def test_wait_revision_changes_once_for_highwater_or_dispatch(self):
        original = wait_record()
        observed = wait(original, 1).record
        self.assertEqual((observed.revision, observed.attempts), (1, 0))
        self.assertIs(wait(observed, 1).record, observed)
        queried = wait(observed, 1, True).record
        self.assertEqual((queried.revision, queried.attempts), (2, 1))
        self.assertIs(wait(queried, 1).record, queried)
        self.assertEqual((original.revision, original.observed_highwater_us), (0, 0))

    def test_shared_root_action_scale_mismatch_cannot_create_second_tuple_budget(self):
        original = wait_record()
        other_scope = replace(original.action.scope, usd_scale=8)
        other_action = h.ActionKey(other_scope, original.action.allocation_id)
        self.assertEqual(original.action.action_id, other_action.action_id)
        other = h.WaitRecord.initial(other_action, original.policy, original.started_us)
        with self.assertRaisesRegex(h.HoldError, "shared_action_duplicate_budget"):
            h.validate_wait_records((original, other))
        self.assertEqual((original.attempts, other.attempts), (0, 0))

    def test_m18_exact_canonical_identity_precedes_schedule(self):
        k = key()
        self.assertEqual(k.duty_id, "funding-duty:v1:3608a7a0ec99683dd080f6663ad9283a965df92c46878e569c3a8c467d3f7779")
        self.assertEqual(k.payload()["period_end"], "2026-01-01T00:00:00+00:00")
        changed = key(rule="different-rule", interval=14400)
        self.assertEqual(k.natural_slot, changed.natural_slot)
        self.assertNotEqual(k.duty_id, changed.duty_id)
        for value in ("2026-01-01T00:00:00Z", "2026-01-01T00:00:00.000000+00:00", "2026-01-01T01:00:00+01:00"):
            with self.subTest(value=value), self.assertRaises(h.HoldError):
                replace(k, period_end=value)
        for change in ({"schema": True}, {"interval_seconds": True}):
            with self.assertRaises(h.HoldError):
                replace(k, **change)

    def test_m01_m02_gross_payables_never_net_pending_receivers(self):
        a = final(key(), 1200)
        first = h.decompose(base(), totals((a,)))
        self.assertEqual((first.P, first.N, first.H, first.risk_equity_units, first.available_margin_units),
                         (1200, 0, 1200, 8800, 3800))
        self.assertEqual(first.ordinary_spend_raw_units, 8800)
        b, receiver = final(key("SECOND"), 700), final(key("RECEIVER"), 2000, "FINAL_RECEIVABLE")
        view = h.decompose(base(), totals((a, b, receiver)))
        self.assertEqual((view.P, view.N, view.H, view.accrual_equity_units, view.risk_equity_units,
                          view.available_margin_units), (1900, 2000, 1900, 10100, 8100, 3100))
        self.assertIs(view.activation_permission, False)

    def test_m03_only_given_original_rounded_units_are_aggregated(self):
        a, b = final(key("PERIOD-A"), 1), final(key("PERIOD-B"), 1)
        self.assertEqual(totals((a, b)).H, 2)
        with self.assertRaises(h.HoldUnsupported):
            h.unsupported_request("round_unrounded_periods")

    def test_m10_m19_cap_resolution_has_one_active_stage_and_history(self):
        old = cap(key())
        proposed = h.Stage("FINAL_PAYABLE", 246, old.active.exposure_ref, old.active.cap_ref, ref(old.key, "FINAL_CUT", "3"))
        resolved = h.advance_stage(old, proposed, expected_revision=1, expected_active_stage=old.active)
        self.assertEqual((resolved.key.duty_id, resolved.revision), (old.key.duty_id, 2))
        self.assertEqual((totals((old,)).U, totals((resolved,)).U, totals((resolved,)).P), (600, 0, 246))
        self.assertEqual(resolved.history[-1], old.active)
        self.assertEqual(old.active.kind, "EXPOSURE_RATE_PENDING")
        self.assertIs(resolved.activation_permission, False)
        with self.assertRaises(FrozenInstanceError):
            resolved.revision = 3
        with self.assertRaises(h.HoldError):
            h.advance_stage(resolved, proposed, expected_revision=1, expected_active_stage=old.active)

    def test_m19_sign_zero_cap_breach_and_CAS_ref_conflicts(self):
        old = cap(key())
        for kind, amount, wanted in (("FINAL_RECEIVABLE", 246, (0, 246, 0)), ("FINAL_ZERO", 0, (0, 0, 0))):
            proposed = h.Stage(kind, amount, old.active.exposure_ref, old.active.cap_ref, ref(old.key, "FINAL_CUT", "3"))
            changed = h.advance_stage(old, proposed, expected_revision=1, expected_active_stage=old.active)
            got = totals((changed,))
            self.assertEqual((got.U, got.N, got.H), wanted)
        excess = h.Stage("FINAL_PAYABLE", 601, old.active.exposure_ref, old.active.cap_ref, ref(old.key, "FINAL_CUT", "3"))
        with self.assertRaises(h.HoldUnsupported):
            h.advance_stage(old, excess, expected_revision=1, expected_active_stage=old.active)
        with self.assertRaises(h.HoldError):
            h.advance_stage(old, excess, expected_revision=1, expected_active_stage=replace(old.active, cap_ref=ref(old.key, "CAP", "4")))
        self.assertEqual(totals((old,)).U, 600)

    def test_m07_m18_duplicate_slots_and_foreign_ref_do_not_create_extra_debt(self):
        a = final(key(), 1200)
        with self.assertRaises(h.HoldError):
            totals((a, a))
        other_scope_same_slot = final(key(rule="other-rule", interval=14400), 1200)
        with self.assertRaises(h.HoldError):
            totals((a, other_scope_same_slot))
        initial = h.DutyState.initial(key(), 2)
        bad = h.Stage("FINAL_PAYABLE", 1, None, None, ref(key("OTHER"), "FINAL_CUT"))
        with self.assertRaises(h.HoldError):
            h.advance_stage(initial, bad, expected_revision=0, expected_active_stage=initial.active)
        with self.assertRaises(h.HoldUnsupported):
            h.unsupported_request("claim_or_lease_expiry")

    def test_unknown_unassessed_missing_or_cross_scope_is_not_zero(self):
        self.assertEqual(totals(()).H, 0)
        with self.assertRaises(h.HoldUnsupported):
            h.aggregate((), scope(), basis_complete=False)
        with self.assertRaises(h.HoldUnsupported):
            totals((h.DutyState.initial(key(), 2),))
        with self.assertRaises(h.HoldUnsupported):
            totals((final(key(account="other-account"), 1),))
        with self.assertRaises(h.HoldUnsupported):
            totals((final(key(), 1, scale=8),))
        with self.assertRaises(h.HoldError):
            h.aggregate((), scope(), basis_complete=None)

    def test_money_scale_exact_types_limits_and_no_user_hash_hook(self):
        class NotNativeInt(int):
            pass
        for value in (True, 1.0, Decimal("1"), NotNativeInt(1), -1, h.LEG_LIMIT):
            with self.subTest(type=type(value).__name__), self.assertRaises(h.HoldError):
                h.Stage("FINAL_PAYABLE", value, None, None, ref(key(), "FINAL_CUT"))
        for asset in ("USDT", "BTC"):
            with self.assertRaises(h.HoldUnsupported):
                replace(scope(), settlement_asset=asset)
        with self.assertRaises(h.HoldError):
            replace(scope(), usd_scale=True)
        calls = []
        class Trap:
            def __hash__(self):
                calls.append("hash")
                raise AssertionError("untrusted hash")
        with self.assertRaises(h.HoldError):
            h.Totals(scope(), (Trap(),), 0, 0, 0, 0)
        self.assertEqual(calls, [])

    def test_checked_1000_duty_aggregate_has_auditable_python_integer_bound(self):
        states = tuple(final(key("BOUND-" + str(i)), h.LEG_LIMIT - 1) for i in range(1000))
        result = totals(states)
        self.assertEqual(result.P, h.TOTAL_LIMIT)
        self.assertEqual(result.H, 1000 * (10 ** 38 - 1))
        with self.assertRaises(h.HoldError):
            totals(states + (states[0],))
        with self.assertRaises(h.HoldError):
            h.Totals(scope(), (), 1, 0, 0, 1)

    def test_m04_loans_fees_and_funding_are_given_separate_base_components(self):
        own = final(key(), 800)
        before = h.decompose(base(accounting=7800, risk=7800, im=220, mm=110, reserve=1000), totals((own,)))
        after_fee = h.decompose(base(accounting=7700, risk=7700, im=220, mm=110, reserve=1000, cash=9900), totals((own,)))
        self.assertEqual((before.risk_equity_units, before.available_margin_units), (7000, 5780))
        self.assertEqual((after_fee.risk_equity_units, after_fee.available_margin_units), (6900, 5680))
        preview = backing((own,), own, 9900)
        self.assertEqual((preview.projected_cash_units, preview.projected_P, preview.projected_H), (9100, 0, 0))
        self.assertIs(preview.activation_permission, False)
        with self.assertRaises(h.HoldUnsupported):
            replace(base(), funding_components="ALREADY_INCLUDED")

    def test_m05_m25_zero_frozen_negative_cash_keeps_other_H_once(self):
        own = final(key(), 500)
        view = h.decompose(base(accounting=300, risk=300, im=0, mm=0, reserve=0, cash=300), totals((own,)))
        preview = backing((own,), own, 300)
        self.assertEqual((view.risk_equity_units, preview.projected_cash_units, preview.projected_H), (-200, -200, 0))
        self.assertEqual(view.ordinary_spendable_units, 0)
        larger, other = final(key("LARGE"), 1200), final(key("OTHER"), 1000)
        blocked = backing((larger, other), larger, 500, frozen=100, quote=False)
        self.assertEqual((blocked.outcome, blocked.projected_cash_units, blocked.projected_H),
                         ("WAITING_ENCUMBRANCE_RELEASE", 500, 2200))
        released = backing((larger, other), larger, 500, frozen=0, quote=False)
        self.assertEqual((released.projected_cash_units, released.projected_H, released.other_H_units), (-700, 1000, 1000))
        self.assertIs(released.risk_recheck_required, True)

    def test_m06_receiver_has_no_preview_cash_and_other_payable_stays(self):
        a, b = final(key("A"), 1200), final(key("B"), 700)
        receiver = final(key("R"), 2000, "FINAL_RECEIVABLE")
        result = backing((a, b, receiver), a, 10000)
        self.assertEqual((result.projected_cash_units, result.projected_P, result.projected_N, result.projected_H),
                         (8800, 700, 2000, 700))
        with self.assertRaises(h.HoldUnsupported):
            backing((a, b, receiver), receiver, 10000)

    def test_m08_m09_given_margin_arithmetic_is_not_liquidation_or_admission(self):
        a = final(key(), 3000)
        negative = h.decompose(base(reserve=6000), totals((a,)))
        cancelled_input = h.decompose(base(reserve=0), totals((a,)))
        self.assertEqual((negative.risk_equity_units, negative.available_margin_units, cancelled_input.available_margin_units),
                         (7000, -1000, 5000))
        equality = final(key("EQUALITY"), 2000)
        result = h.decompose(base(accounting=2500, risk=2500, im=1000, mm=500, reserve=0, cash=2500), totals((equality,)))
        self.assertEqual(result.risk_equity_units, result.maintenance_margin_units)
        self.assertIs(result.activation_permission, False)
        self.assertEqual(backing((equality,), equality, 2500).projected_cash_units, 500)

    def test_m11_m12_provided_USD_base_values_do_not_revalue_collateral(self):
        own = final(key(), 1200)
        ordinary = h.decompose(base(), totals((own,)))
        self.assertEqual((ordinary.ordinary_spendable_units, ordinary.available_margin_units), (8800, 3800))
        tier_before = h.decompose(base(accounting=30000, risk=23000), totals((own,)))
        tier_after = h.decompose(base(accounting=25000, risk=20500), totals((own,)))
        self.assertEqual((tier_before.risk_equity_units, tier_before.available_margin_units), (21800, 16800))
        self.assertEqual((tier_after.risk_equity_units, tier_after.available_margin_units), (19300, 14300))
        with self.assertRaises(h.HoldUnsupported):
            h.unsupported_request("revalue_BTC_tiers")

    def test_m13_m17_given_receivables_do_not_grant_risk_or_capital(self):
        own = final(key(), 1200)
        correction_data = final(key("DECLARED-RECEIVABLE"), 200, "FINAL_RECEIVABLE")
        view = h.decompose(base(im=0, mm=0, reserve=0), totals((own, correction_data)))
        self.assertEqual((view.H, view.accrual_equity_units, view.risk_equity_units), (1200, 9000, 8800))
        receiver = final(key("ROUNDING-RECEIVER"), 1, "FINAL_RECEIVABLE")
        self.assertEqual((totals((receiver,)).N, totals((receiver,)).H), (1, 0))
        for operation in ("correction", "rounding_capital"):
            with self.assertRaises(h.HoldUnsupported):
                h.unsupported_request(operation)

    def test_m20_m24_frozen_backing_wait_and_given_true_release_projection(self):
        own = final(key(), 1200)
        before = h.decompose(base(risk=500, im=0, mm=0, reserve=0, frozen=9500), totals((own,)))
        blocked = backing((own,), own, 10000, frozen=9500)
        self.assertEqual((before.accrual_equity_units, before.risk_equity_units), (8800, -700))
        self.assertEqual((blocked.outcome, blocked.projected_cash_units, blocked.projected_P, blocked.projected_H),
                         ("WAITING_ENCUMBRANCE_RELEASE", 10000, 1200, 1200))
        released_input = h.decompose(base(risk=1500, im=0, mm=0, reserve=0, frozen=8500), totals((own,)))
        preview = backing((own,), own, 10000, frozen=8500)
        self.assertEqual((released_input.risk_equity_units, preview.projected_cash_units, preview.projected_H), (300, 8800, 0))
        self.assertEqual(own.active.amount_units, 1200)  # Preview never settles.
        self.assertIs(preview.activation_permission, False)

    def test_m21_m22_prior_confirmed_fill_or_unknown_ack_does_not_release_backing(self):
        own = final(key(), 1200)
        uncertain = backing((own,), own, 10000, frozen=0, clear=False)
        self.assertEqual((uncertain.outcome, uncertain.projected_P), ("WAITING_ENCUMBRANCE_RELEASE", 1200))
        after_fill = backing((own,), own, 9500, frozen=9100)
        after_real_release_input = backing((own,), own, 9500, frozen=8100)
        self.assertEqual((after_fill.projected_cash_units, after_fill.projected_H), (9500, 1200))
        self.assertEqual((after_real_release_input.projected_cash_units, after_real_release_input.projected_H), (8300, 0))
        with self.assertRaises(h.HoldError):
            backing((own,), own, 10000, frozen=10001)

    def test_m23_deadline_and_highwater_not_reset_by_observations(self):
        original = wait_record()
        observed = wait(original, 20000000).record
        self.assertEqual((observed.started_us, observed.deadline_us, observed.attempts), (0, 30000000, 0))
        expired = wait(observed, 30000000)
        self.assertEqual(expired.outcome, "DEFAULT_REVIEW")
        late = wait(expired.record, 50000000, dispatch=True)
        self.assertEqual((late.record.deadline_us, late.record.attempts, late.record.observed_highwater_us),
                         (30000000, 0, 50000000))
        self.assertIs(late.record.default_review, True)
        with self.assertRaises(h.HoldError):
            wait(late.record, 40000000)
        self.assertIs(late.query_counted, False)
        self.assertIs(late.holds_unchanged, True)
        self.assertIs(late.activation_permission, False)
        with self.assertRaises(h.HoldError):
            wait(observed, 19999999)
        with self.assertRaises(h.HoldError):
            replace(observed, deadline_us=50000000)

    def test_m23_unknown_dispatched_query_consumes_budget_and_CAS_once_in_projection(self):
        current = wait_record()
        for count, now in enumerate((0, 5000000, 10000000, 15000000), 1):
            outcome = wait(current, now, dispatch=True)
            current = outcome.record
            self.assertEqual(current.attempts, count)
            self.assertIs(outcome.query_counted, True)
        self.assertEqual(outcome.outcome, "DEFAULT_REVIEW")
        self.assertEqual((current.deadline_us, current.last_dispatch_us), (30000000, 15000000))
        with self.assertRaises(h.HoldError):
            h.preview_wait(wait_record(), now_us=0, expected_revision=1,
                           expected_policy_digest=policy().digest, dispatch_query=True)
        first = wait(wait_record(), 0, dispatch=True).record
        with self.assertRaises(h.HoldError):
            wait(first, 4999999, dispatch=True)

    def test_shared_action_cannot_take_second_policy_or_duty_budget(self):
        a = wait_record()
        b = h.WaitRecord.initial(a.action, policy(max_wait=60000000), 0)
        self.assertEqual(a.action.action_id, b.action.action_id)
        with self.assertRaises(h.HoldError):
            h.validate_wait_records((a, b))
        self.assertEqual(h.validate_wait_records((a,)), (a.action.action_id,))
        with self.assertRaises(h.HoldError):
            h.preview_wait(a, now_us=0, expected_revision=0,
                           expected_policy_digest=b.policy.digest, dispatch_query=True)
        for value in (None, True, 0):
            with self.assertRaises(h.HoldError):
                replace(policy(), max_wait_us=value)
        with self.assertRaises(h.HoldError):
            h.WaitRecord.initial(a.action, policy(), h.TIME_LIMIT)

    def test_m26_given_capital_snapshot_does_not_authorize_financing(self):
        own = final(key(), 1200)
        projected = backing((own,), own, 10700, frozen=9500)
        self.assertEqual((projected.projected_cash_units, projected.projected_P), (9500, 0))
        view = h.decompose(base(accounting=10700, risk=1200, im=0, mm=0, reserve=0, cash=10700, frozen=9500), totals((own,)))
        self.assertEqual(view.risk_equity_units, 0)
        self.assertIs(view.activation_permission, False)
        with self.assertRaises(h.HoldUnsupported):
            h.unsupported_request("capital_substitution")

    def test_m14_m15_m27_and_other_unsupported_operations_have_no_fallback(self):
        for operation in ("borrow_quote", "calculate_IM", "calculate_MM", "cap_from_rate",
                          "real_ACK", "outbox", "apply", "ledger", "whole_period_apply", "auto_borrow"):
            with self.subTest(operation=operation), self.assertRaises(h.HoldUnsupported):
                h.unsupported_request(operation)
        with self.assertRaises(h.HoldUnsupported):
            h.Stage("APPLIED", 0, None, None, None)
        with self.assertRaises(h.HoldUnsupported):
            totals((final(key(account="payerA"), 1200), final(key(account="payerB"), 800)))


if __name__ == "__main__":
    unittest.main()
