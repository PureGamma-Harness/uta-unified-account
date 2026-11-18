"""Unconnected D1 funding-hold arithmetic over supplied immutable USD data.

No input fact, ref, CAS, preview or returned flag authenticates an obligation or
permits a financial action. Real persistence, ACK, outbox and settlement are D2.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from hashlib import sha256
import json
import re


LEG_LIMIT = 10 ** 38
MAX_DUTIES = 1000
TOTAL_LIMIT = MAX_DUTIES * (LEG_LIMIT - 1)
DERIVED_LIMIT = 4000 * LEG_LIMIT
TIME_LIMIT = 2 ** 63 - 1
MAX_QUERY_ATTEMPTS = 10000
_ID = r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}"
_FINAL = ("FINAL_PAYABLE", "FINAL_RECEIVABLE", "FINAL_ZERO")


class HoldError(ValueError):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


class HoldUnsupported(HoldError):
    pass


def _require(condition, code):
    if not condition:
        raise HoldError(code)


def _exact(value, kind):
    _require(type(value) is kind, "exact_type_required")


def _identifier(value):
    _exact(value, str)
    _require(re.fullmatch(_ID, value) is not None, "identifier_invalid")


def _integer(value, lower, upper, code="units_out_of_range"):
    _exact(value, int)
    _require(lower <= value <= upper, code)
    return value


def _money(value, nonnegative=False):
    return _integer(value, 0 if nonnegative else -LEG_LIMIT + 1, LEG_LIMIT - 1)


def _time(value):
    return _integer(value, 0, TIME_LIMIT, "time_out_of_range")


def _digest(data):
    # Every caller builds a fixed shallow payload from validated own fields.
    return sha256(json.dumps(data, sort_keys=True, separators=(",", ":"),
                             ensure_ascii=True, allow_nan=False).encode("ascii")).hexdigest()


def _flag(value):
    _exact(value, bool)


def _same_scale(left, right):
    if left != right:
        raise HoldUnsupported("scale_conversion_unsupported")


@dataclass(frozen=True)
class Scope:
    authority_id: str
    authority_generation: str
    account_id: str
    usd_scale: int
    settlement_asset: str

    def __post_init__(self):
        _exact(self, Scope)
        for value in (self.authority_id, self.authority_generation, self.account_id):
            _identifier(value)
        _integer(self.usd_scale, 2, 8, "scale_unsupported")
        _exact(self.settlement_asset, str)
        if self.settlement_asset != "USD":
            raise HoldUnsupported("settlement_unsupported")


@dataclass(frozen=True)
class DutyKey:
    authority_id: str
    authority_generation: str
    symbol: str
    period_end: str
    interval_seconds: int
    settlement_asset: str
    account_id: str
    rule_scope_id: str
    schema: int

    def __post_init__(self):
        _exact(self, DutyKey)
        _integer(self.schema, 1, 1, "schema_unsupported")
        for value in (self.authority_id, self.authority_generation, self.symbol,
                      self.account_id, self.rule_scope_id):
            _identifier(value)
        _exact(self.settlement_asset, str)
        if self.settlement_asset != "USD":
            raise HoldUnsupported("settlement_unsupported")
        _integer(self.interval_seconds, 1, 86400, "period_invalid")
        _exact(self.period_end, str)
        _require(re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}\+00:00", self.period_end) is not None,
                 "period_not_canonical")
        try:
            end = datetime.fromisoformat(self.period_end)
        except ValueError as error:
            raise HoldError("period_invalid") from error
        _require(end.isoformat(timespec="seconds") == self.period_end, "period_not_canonical")
        delta = end - datetime(1970, 1, 1, tzinfo=timezone.utc)
        seconds = delta.days * 86400 + delta.seconds
        _require(seconds >= 0 and seconds % self.interval_seconds == 0, "period_unaligned")

    def payload(self):
        DutyKey.__post_init__(self)
        return {"schema": self.schema, "authority_id": self.authority_id,
                "authority_generation": self.authority_generation, "symbol": self.symbol,
                "period_end": self.period_end, "interval_seconds": self.interval_seconds,
                "settlement_asset": self.settlement_asset, "account_id": self.account_id,
                "rule_scope_id": self.rule_scope_id}

    @property
    def duty_id(self):
        return "funding-duty:v1:" + _digest(self.payload())

    @property
    def natural_slot(self):
        DutyKey.__post_init__(self)
        return (self.authority_id, self.authority_generation, self.symbol,
                self.period_end, self.settlement_asset, self.account_id)


def _key_scope(key, scope):
    _exact(key, DutyKey)
    _exact(scope, Scope)
    DutyKey.__post_init__(key)
    Scope.__post_init__(scope)
    if (key.authority_id, key.authority_generation, key.account_id, key.settlement_asset) != (
            scope.authority_id, scope.authority_generation, scope.account_id, scope.settlement_asset):
        raise HoldUnsupported("cross_account_or_authority_unsupported")


@dataclass(frozen=True)
class ContentRef:
    kind: str
    digest: str
    duty_id: str
    rule_scope_id: str

    def __post_init__(self):
        _exact(self, ContentRef)
        _exact(self.kind, str)
        _require(self.kind in ("EXPOSURE", "CAP", "FINAL_CUT"), "ref_kind_unsupported")
        _exact(self.digest, str)
        _require(re.fullmatch(r"[0-9a-f]{64}", self.digest) is not None, "ref_digest_invalid")
        _exact(self.duty_id, str)
        _require(re.fullmatch(r"funding-duty:v1:[0-9a-f]{64}", self.duty_id) is not None, "ref_duty_invalid")
        _identifier(self.rule_scope_id)


@dataclass(frozen=True)
class Stage:
    kind: str
    amount_units: int
    exposure_ref: ContentRef | None
    cap_ref: ContentRef | None
    final_ref: ContentRef | None

    def __post_init__(self):
        _exact(self, Stage)
        _exact(self.kind, str)
        _money(self.amount_units, True)
        if self.kind == "REGISTERED_UNASSESSED":
            _require(self.amount_units == 0 and self.exposure_ref is self.cap_ref is self.final_ref is None,
                     "registered_stage_invalid")
        elif self.kind == "EXPOSURE_RATE_PENDING":
            self._ref(self.exposure_ref, "EXPOSURE")
            self._ref(self.cap_ref, "CAP")
            _require(self.final_ref is None, "cap_stage_invalid")
        elif self.kind in _FINAL:
            self._ref(self.final_ref, "FINAL_CUT")
            _require((self.exposure_ref is None) == (self.cap_ref is None), "partial_cap_lineage")
            if self.cap_ref is not None:
                self._ref(self.exposure_ref, "EXPOSURE")
                self._ref(self.cap_ref, "CAP")
            _require((self.amount_units == 0) == (self.kind == "FINAL_ZERO"), "final_amount_invalid")
        else:
            raise HoldUnsupported("stage_unsupported_no_APPLIED")

    @staticmethod
    def _ref(value, kind):
        _exact(value, ContentRef)
        ContentRef.__post_init__(value)
        _require(value.kind == kind, "ref_kind_mismatch")

    @property
    def active_ref(self):
        Stage.__post_init__(self)
        return self.cap_ref if self.kind == "EXPOSURE_RATE_PENDING" else self.final_ref


def _link(stage, key):
    _exact(stage, Stage)
    Stage.__post_init__(stage)
    for ref in (stage.exposure_ref, stage.cap_ref, stage.final_ref):
        if ref is not None:
            _require(ref.duty_id == key.duty_id and ref.rule_scope_id == key.rule_scope_id,
                     "foreign_stage_reference")


@dataclass(frozen=True)
class DutyState:
    key: DutyKey
    usd_scale: int
    revision: int
    active: Stage
    history: tuple
    activation_permission: bool = field(default=False, init=False)

    def __post_init__(self):
        _exact(self, DutyState)
        _exact(self.key, DutyKey)
        DutyKey.__post_init__(self.key)
        _integer(self.usd_scale, 2, 8, "scale_unsupported")
        _integer(self.revision, 0, 2, "revision_invalid")
        _exact(self.history, tuple)
        _require(len(self.history) == self.revision, "revision_history_mismatch")
        chain = self.history + (self.active,)
        for stage in chain:
            _link(stage, self.key)
        kinds = tuple(stage.kind for stage in chain)
        valid = (kinds == ("REGISTERED_UNASSESSED",)
                 or len(kinds) == 2 and kinds[0] == "REGISTERED_UNASSESSED" and (kinds[1] == "EXPOSURE_RATE_PENDING" or kinds[1] in _FINAL)
                 or len(kinds) == 3 and kinds[:2] == ("REGISTERED_UNASSESSED", "EXPOSURE_RATE_PENDING") and kinds[2] in _FINAL)
        _require(valid, "stage_chain_invalid")
        if len(chain) == 2 and chain[-1].kind in _FINAL:
            _require(chain[-1].exposure_ref is chain[-1].cap_ref is None, "cap_lineage_without_stage")
        if len(chain) == 3:
            cap, final = chain[1:]
            _require(final.exposure_ref == cap.exposure_ref and final.cap_ref == cap.cap_ref,
                     "cap_lineage_changed")
            if final.amount_units > cap.amount_units:
                raise HoldUnsupported("cap_breach_preserve_prior_state")

    @classmethod
    def initial(cls, key, usd_scale):
        _require(cls is DutyState, "exact_type_required")
        return cls(key, usd_scale, 0, Stage("REGISTERED_UNASSESSED", 0, None, None, None), ())


def advance_stage(state, proposed, *, expected_revision, expected_active_ref):
    """Pure CAS check only. The caller's original state is never mutated."""
    _exact(state, DutyState)
    _exact(proposed, Stage)
    DutyState.__post_init__(state)
    Stage.__post_init__(proposed)
    _integer(expected_revision, 0, 2, "revision_invalid")
    if expected_active_ref is not None:
        _exact(expected_active_ref, ContentRef)
        ContentRef.__post_init__(expected_active_ref)
    _require(state.revision == expected_revision and state.active.active_ref == expected_active_ref,
             "stage_CAS_conflict")
    if state.active.kind in _FINAL:
        raise HoldUnsupported("final_stage_immutable")
    return DutyState(state.key, state.usd_scale, state.revision + 1, proposed,
                     state.history + (state.active,))


@dataclass(frozen=True)
class Totals:
    scope: Scope
    duty_ids: tuple
    P: int
    U: int
    N: int
    H: int
    activation_permission: bool = field(default=False, init=False)

    def __post_init__(self):
        _exact(self, Totals)
        _exact(self.scope, Scope)
        Scope.__post_init__(self.scope)
        _exact(self.duty_ids, tuple)
        _require(len(self.duty_ids) <= MAX_DUTIES, "duplicate_or_excess_duties")
        for identity in self.duty_ids:
            _exact(identity, str)
            _require(re.fullmatch(r"funding-duty:v1:[0-9a-f]{64}", identity) is not None, "duty_id_invalid")
        _require(len(set(self.duty_ids)) == len(self.duty_ids), "duplicate_or_excess_duties")
        for name in ("P", "U", "N", "H"):
            _integer(getattr(self, name), 0, TOTAL_LIMIT)
        _require(self.P + self.U == self.H and self.P + self.U + self.N <= len(self.duty_ids) * (LEG_LIMIT - 1),
                 "totals_inconsistent")


def aggregate(states, scope, *, basis_complete):
    """Aggregate a complete *provided* collection, not authenticated storage."""
    _exact(states, tuple)
    _exact(scope, Scope)
    Scope.__post_init__(scope)
    _flag(basis_complete)
    if not basis_complete:
        raise HoldUnsupported("incomplete_basis_not_zero")
    _require(len(states) <= MAX_DUTIES, "too_many_duties")
    slots, identities, amounts = set(), set(), {"P": 0, "U": 0, "N": 0}
    for state in states:
        _exact(state, DutyState)
        DutyState.__post_init__(state)
        _key_scope(state.key, scope)
        _same_scale(state.usd_scale, scope.usd_scale)
        identity, slot = state.key.duty_id, state.key.natural_slot
        _require(identity not in identities and slot not in slots, "duplicate_duty_or_natural_slot")
        identities.add(identity)
        slots.add(slot)
        if state.active.kind == "REGISTERED_UNASSESSED":
            raise HoldUnsupported("unassessed_duty_not_zero")
        name = {"EXPOSURE_RATE_PENDING": "U", "FINAL_PAYABLE": "P", "FINAL_RECEIVABLE": "N", "FINAL_ZERO": None}[state.active.kind]
        if name is not None:
            amounts[name] += state.active.amount_units
    return Totals(scope, tuple(sorted(identities)), amounts["P"], amounts["U"], amounts["N"], amounts["P"] + amounts["U"])


@dataclass(frozen=True)
class BaseValues:
    scope: Scope
    accounting_equity_units: int
    risk_equity_units: int
    initial_margin_units: int
    maintenance_margin_units: int
    order_reserve_units: int
    cash_units: int
    spot_frozen_units: int
    funding_components: str

    def __post_init__(self):
        _exact(self, BaseValues)
        _exact(self.scope, Scope)
        Scope.__post_init__(self.scope)
        _exact(self.funding_components, str)
        if self.funding_components != "EXCLUDED":
            raise HoldUnsupported("base_funding_components_must_be_excluded")
        for value in (self.accounting_equity_units, self.risk_equity_units, self.cash_units):
            _money(value)
        for value in (self.initial_margin_units, self.maintenance_margin_units,
                      self.order_reserve_units, self.spot_frozen_units):
            _money(value, True)
        _require(self.spot_frozen_units <= max(self.cash_units, 0), "invalid_existing_backing")


@dataclass(frozen=True)
class Decomposition:
    scope: Scope
    P: int
    U: int
    N: int
    H: int
    accrual_equity_units: int
    risk_equity_units: int
    available_margin_units: int
    initial_margin_units: int
    maintenance_margin_units: int
    order_reserve_units: int
    ordinary_spend_raw_units: int
    ordinary_spendable_units: int
    activation_permission: bool = field(default=False, init=False)


def _derived(value):
    return _integer(value, -DERIVED_LIMIT, DERIVED_LIMIT, "derived_units_out_of_range")


def decompose(base, totals):
    _exact(base, BaseValues)
    _exact(totals, Totals)
    BaseValues.__post_init__(base)
    Totals.__post_init__(totals)
    _same_scale(base.scope.usd_scale, totals.scope.usd_scale)
    if base.scope != totals.scope:
        raise HoldUnsupported("cross_account_or_authority_unsupported")
    accrual = _derived(base.accounting_equity_units - totals.P + totals.N)
    risk = _derived(base.risk_equity_units - totals.H)
    available = _derived(risk - base.initial_margin_units - base.order_reserve_units)
    raw = _derived(base.cash_units - base.spot_frozen_units - totals.H)
    return Decomposition(base.scope, totals.P, totals.U, totals.N, totals.H, accrual, risk,
                         available, base.initial_margin_units, base.maintenance_margin_units,
                         base.order_reserve_units, raw, max(raw, 0))


@dataclass(frozen=True)
class PaymentProjection:
    scope: Scope
    outcome: str
    own_duty_id: str
    projected_cash_units: int
    projected_P: int
    projected_U: int
    projected_N: int
    projected_H: int
    other_H_units: int
    risk_recheck_required: bool
    activation_permission: bool = field(default=False, init=False)


def backing_precondition(states, scope, own_duty_id, *, cash_units, spot_frozen_units,
                         prior_confirmed_settlements_clear, quote_available, basis_complete):
    """Conditional own-payable preview, never cash authority, real ACK or APPLIED."""
    totals = aggregate(states, scope, basis_complete=basis_complete)
    _exact(own_duty_id, str)
    _money(cash_units)
    _money(spot_frozen_units, True)
    _require(spot_frozen_units <= max(cash_units, 0), "invalid_existing_backing")
    _flag(prior_confirmed_settlements_clear)
    _flag(quote_available)
    own = [state for state in states if state.key.duty_id == own_duty_id]
    _require(len(own) == 1, "own_duty_not_found")
    state = own[0]
    if state.active.kind != "FINAL_PAYABLE":
        raise HoldUnsupported("only_fixed_payable_preview_supported")
    amount = state.active.amount_units
    after = _derived(cash_units - amount)
    eligible = prior_confirmed_settlements_clear and spot_frozen_units <= max(after, 0)
    return PaymentProjection(scope, "PREVIEW_BACKING_ELIGIBLE" if eligible else "WAITING_ENCUMBRANCE_RELEASE",
                             own_duty_id, after if eligible else cash_units,
                             totals.P - amount if eligible else totals.P, totals.U, totals.N,
                             totals.H - amount if eligible else totals.H, totals.H - amount,
                             not quote_available)


@dataclass(frozen=True)
class WaitPolicy:
    format: int
    policy_id: str
    clock_policy: str
    max_wait_us: int
    min_query_interval_us: int
    max_query_attempts: int
    expiry_action: str

    def __post_init__(self):
        _exact(self, WaitPolicy)
        _integer(self.format, 1, 1, "wait_format_unsupported")
        _identifier(self.policy_id)
        _require(type(self.clock_policy) is str and self.clock_policy == "TRUSTED_UTC_PERSISTENT_HIGH_WATERMARK", "clock_policy_unsupported")
        _integer(self.max_wait_us, 1, TIME_LIMIT)
        _integer(self.min_query_interval_us, 1, self.max_wait_us)
        _integer(self.max_query_attempts, 1, MAX_QUERY_ATTEMPTS)
        _require(type(self.expiry_action) is str and self.expiry_action == "DEFAULT_REVIEW_PRESERVE_DEBT_FREEZE_AND_OUTBOX", "expiry_action_unsupported")

    @property
    def digest(self):
        WaitPolicy.__post_init__(self)
        return _digest({"format": self.format, "policy_id": self.policy_id,
                        "clock_policy": self.clock_policy, "max_wait_us": self.max_wait_us,
                        "min_query_interval_us": self.min_query_interval_us,
                        "max_query_attempts": self.max_query_attempts, "expiry_action": self.expiry_action})


@dataclass(frozen=True)
class ActionKey:
    scope: Scope
    allocation_id: str

    def __post_init__(self):
        _exact(self, ActionKey)
        _exact(self.scope, Scope)
        Scope.__post_init__(self.scope)
        _identifier(self.allocation_id)

    @property
    def action_id(self):
        ActionKey.__post_init__(self)
        # No duty/claim/policy identity: one allocation action cannot get extra
        # budgets just because another duty or claimant requests it.
        return "funding-action:v1:" + _digest({"authority_id": self.scope.authority_id,
            "authority_generation": self.scope.authority_generation, "account_id": self.scope.account_id,
            "settlement_asset": "USD", "allocation_id": self.allocation_id,
            "action": "CANCEL_QUERY", "terminal_goal": "CONFIRMED_CLOSED"})


@dataclass(frozen=True)
class WaitRecord:
    action: ActionKey
    policy: WaitPolicy
    revision: int
    started_us: int
    deadline_us: int
    observed_highwater_us: int
    attempts: int
    last_dispatch_us: int | None
    default_review: bool

    def __post_init__(self):
        _exact(self, WaitRecord)
        _exact(self.action, ActionKey)
        _exact(self.policy, WaitPolicy)
        ActionKey.__post_init__(self.action)
        WaitPolicy.__post_init__(self.policy)
        _integer(self.revision, 0, TIME_LIMIT, "revision_invalid")
        for value in (self.started_us, self.deadline_us, self.observed_highwater_us):
            _time(value)
        _require(self.deadline_us == self.started_us + self.policy.max_wait_us, "wait_deadline_changed")
        _require(self.started_us <= self.observed_highwater_us, "clock_regression")
        _integer(self.attempts, 0, self.policy.max_query_attempts)
        _flag(self.default_review)
        _require((self.last_dispatch_us is None) == (self.attempts == 0), "dispatch_count_inconsistent")
        if self.last_dispatch_us is not None:
            _time(self.last_dispatch_us)
            _require(self.started_us <= self.last_dispatch_us <= self.observed_highwater_us, "dispatch_time_inconsistent")

    @classmethod
    def initial(cls, action, policy, started_us):
        _require(cls is WaitRecord, "exact_type_required")
        _exact(action, ActionKey)
        _exact(policy, WaitPolicy)
        ActionKey.__post_init__(action)
        WaitPolicy.__post_init__(policy)
        _time(started_us)
        _time(started_us + policy.max_wait_us)
        return cls(action, policy, 0, started_us, started_us + policy.max_wait_us, started_us, 0, None, False)


@dataclass(frozen=True)
class WaitProjection:
    record: WaitRecord
    outcome: str
    query_counted: bool
    holds_unchanged: bool = field(default=True, init=False)
    activation_permission: bool = field(default=False, init=False)


def validate_wait_records(records):
    _exact(records, tuple)
    _require(len(records) <= MAX_DUTIES, "too_many_wait_actions")
    identities = set()
    for record in records:
        _exact(record, WaitRecord)
        WaitRecord.__post_init__(record)
        identity = record.action.action_id
        _require(identity not in identities, "shared_action_duplicate_budget")
        identities.add(identity)
    return tuple(sorted(identities))


def preview_wait(record, *, now_us, expected_revision, expected_policy_digest, dispatch_query):
    """Preview a proposed query before dispatch, never authorize or execute it.

    Future D2 must commit a counted attempt with its outbox before dispatch; an
    unknown result never refunds that attempt. An expired preview counts no new
    query and cannot describe an actually dispatched late action. This module
    cannot observe real dispatch, persist CAS, read a clock or prove an ACK.
    """
    _exact(record, WaitRecord)
    WaitRecord.__post_init__(record)
    _time(now_us)
    _integer(expected_revision, 0, TIME_LIMIT, "revision_invalid")
    _exact(expected_policy_digest, str)
    _flag(dispatch_query)
    _require(expected_revision == record.revision and expected_policy_digest == record.policy.digest,
             "wait_CAS_or_policy_conflict")
    _require(now_us >= record.observed_highwater_us, "clock_regression")
    if record.default_review and now_us == record.observed_highwater_us:
        return WaitProjection(record, "DEFAULT_REVIEW", False)
    expired = record.default_review or now_us >= record.deadline_us or record.attempts >= record.policy.max_query_attempts
    attempts, last = record.attempts, record.last_dispatch_us
    if dispatch_query and not expired:
        _require(last is None or now_us - last >= record.policy.min_query_interval_us, "query_too_early")
        attempts += 1
        last = now_us
    review = expired or attempts >= record.policy.max_query_attempts
    # No revision saturation: a changed record requires a new exact revision.
    revision = _integer(record.revision + 1, 0, TIME_LIMIT, "revision_overflow")
    updated = WaitRecord(record.action, record.policy, revision, record.started_us, record.deadline_us,
                         now_us, attempts, last, review)
    return WaitProjection(updated, "DEFAULT_REVIEW" if review else "WAIT", dispatch_query and not expired)


def unsupported_request(operation):
    _identifier(operation)
    raise HoldUnsupported("operation_not_in_pure_hold_subset")
