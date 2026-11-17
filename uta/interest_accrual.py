"""Pure, bounded interest accrual proposals; no clock, database or permission.

This module does not extend the existing zero-rate credit capability. Its
in-memory reference/interval checks are not durable deduplication. A financial
integration must atomically persist the receipt, carry and two accounting legs.
"""
from dataclasses import dataclass
from hashlib import sha256
import json
import re

POLICY = "UTA-INTEREST-ACT365-PPB-CARRY-v1"
RATE_SCALE = 10**9
DAY_NS = 86400 * 10**9
YEAR_NS = 365 * DAY_NS
DENOMINATOR = YEAR_NS * RATE_SCALE
UNIT_LIMIT = 10**38
MAX_TIMESTAMP_NS = 2**63 - 1
MAX_INTERVAL_NS = 366 * DAY_NS
MAX_RECEIPTS = 4096
_IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,95}\Z", re.ASCII)
_ASSET = re.compile(r"[A-Z][A-Z0-9]{0,15}\Z", re.ASCII)
_HASH = re.compile(r"[0-9a-f]{64}\Z", re.ASCII)


class AccrualError(ValueError):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


def _require(value, code):
    if not value:
        raise AccrualError(code)


def _integer(value, low, high, code):
    _require(type(value) is int and low <= value <= high, code)
    return value


def _identifier(value):
    _require(type(value) is str and _IDENTIFIER.fullmatch(value) is not None, "identifier_invalid")


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)


def _digest(value):
    return sha256(_canonical(value).encode("ascii")).hexdigest()


@dataclass(frozen=True)
class RateVersion:
    rate_id: str
    version: int
    asset: str
    scale: int
    annual_ppb: int
    valid_from_ns: int
    valid_to_ns: int
    day_count: str = "ACT_365_FIXED_NS"

    def __post_init__(self):
        _identifier(self.rate_id)
        _integer(self.version, 1, MAX_TIMESTAMP_NS, "rate_version_invalid")
        _require(type(self.asset) is str and _ASSET.fullmatch(self.asset) is not None, "asset_invalid")
        _integer(self.scale, 0, 18, "scale_invalid")
        _integer(self.annual_ppb, 0, RATE_SCALE, "rate_out_of_policy")
        _integer(self.valid_from_ns, 0, MAX_TIMESTAMP_NS, "rate_time_invalid")
        _integer(self.valid_to_ns, 0, MAX_TIMESTAMP_NS, "rate_time_invalid")
        _require(self.valid_to_ns > self.valid_from_ns, "rate_interval_invalid")
        _require(type(self.day_count) is str and self.day_count == "ACT_365_FIXED_NS", "day_count_unsupported")

    def wire(self):
        return dict(rate_id=self.rate_id, version=self.version, asset=self.asset, scale=self.scale,
                    annual_ppb=self.annual_ppb, valid_from_ns=self.valid_from_ns,
                    valid_to_ns=self.valid_to_ns, day_count=self.day_count)


@dataclass(frozen=True)
class AccrualCommand:
    reference: str
    start_ns: int
    end_ns: int
    principal_units: int
    rate: RateVersion
    expected_sequence: int
    expected_state_hash: str


@dataclass(frozen=True)
class PrincipalCommand:
    reference: str
    at_ns: int
    principal_units_after: int
    expected_sequence: int
    expected_state_hash: str


@dataclass(frozen=True)
class AccrualState:
    cursor_ns: int
    principal_units: int
    cumulative_booked_units: int
    carry_numerator: int
    sequence: int
    state_hash: str

    @property
    def unbooked_risk_reserve_units(self):
        """Add to actual unpaid ledger interest, never substitute lifetime accrual."""
        return int(self.carry_numerator > 0)


@dataclass(frozen=True)
class AccrualReceipt:
    reference: str
    kind: str
    request_payload: str
    request_hash: str
    previous_state_hash: str
    booked_delta_units: int
    after: AccrualState


class AccrualBook:
    """One immutable loan identity and a bounded in-memory receipt history.

    Cumulative booked interest is a lifetime accrual counter, not an outstanding
    liability balance: interest repayment is owned by the actual credit ledger.
    This object is single-threaded and deliberately supplies no financial flags.
    """
    def __init__(self, *, loan_id, account_id, asset, scale, principal_units, as_of_ns,
                 cumulative_booked_units=0, carry_numerator=0):
        _identifier(loan_id)
        _identifier(account_id)
        _require(type(asset) is str and _ASSET.fullmatch(asset) is not None, "asset_invalid")
        _integer(scale, 0, 18, "scale_invalid")
        _integer(principal_units, 0, UNIT_LIMIT - 1, "principal_invalid")
        _integer(as_of_ns, 0, MAX_TIMESTAMP_NS, "cursor_invalid")
        _integer(cumulative_booked_units, 0, UNIT_LIMIT - 1, "booked_units_invalid")
        _integer(carry_numerator, 0, DENOMINATOR - 1, "carry_invalid")
        _require(cumulative_booked_units + int(carry_numerator > 0) < UNIT_LIMIT, "risk_units_overflow")
        self._identity = dict(policy=POLICY, loan_id=loan_id, account_id=account_id, asset=asset, scale=scale)
        self._receipts, self._rates = {}, {}
        initial = dict(self._identity, cursor_ns=as_of_ns, principal_units=principal_units,
                       cumulative_booked_units=cumulative_booked_units, carry_numerator=carry_numerator,
                       sequence=0)
        self._state = AccrualState(as_of_ns, principal_units, cumulative_booked_units,
                                   carry_numerator, 0, _digest(initial))

    @property
    def state(self):
        return self._state

    def receipt(self, reference):
        _identifier(reference)
        _require(reference in self._receipts, "reference_unknown")
        return self._receipts[reference]

    def _request(self, command, kind, fields):
        _identifier(command.reference)
        _integer(command.expected_sequence, 0, MAX_TIMESTAMP_NS, "sequence_invalid")
        _require(type(command.expected_state_hash) is str
                 and _HASH.fullmatch(command.expected_state_hash) is not None, "state_hash_invalid")
        request = dict(self._identity, reference=command.reference, kind=kind,
                       expected_sequence=command.expected_sequence,
                       expected_state_hash=command.expected_state_hash, **fields)
        payload = _canonical(request)
        previous = self._receipts.get(command.reference)
        if previous is not None:
            _require(previous.request_payload == payload, "reference_conflict")
            return payload, previous
        _require(len(self._receipts) < MAX_RECEIPTS, "receipt_capacity")
        _require(command.expected_sequence == self._state.sequence
                 and command.expected_state_hash == self._state.state_hash, "checkpoint_conflict")
        _require(self._state.sequence < MAX_TIMESTAMP_NS, "sequence_overflow")
        return payload, None

    def _finish(self, command, kind, payload, *, cursor, principal, booked, carry, delta):
        old = self._state
        values = dict(self._identity, cursor_ns=cursor, principal_units=principal,
                      cumulative_booked_units=booked, carry_numerator=carry,
                      sequence=old.sequence + 1, previous_state_hash=old.state_hash,
                      request_hash=sha256(payload.encode("ascii")).hexdigest())
        after = AccrualState(cursor, principal, booked, carry, old.sequence + 1, _digest(values))
        receipt = AccrualReceipt(command.reference, kind, payload, values["request_hash"],
                                 old.state_hash, delta, after)
        self._receipts[command.reference] = receipt
        self._state = after
        return receipt

    def accrue(self, command):
        _require(type(command) is AccrualCommand and type(command.rate) is RateVersion, "command_invalid")
        _integer(command.start_ns, 0, MAX_TIMESTAMP_NS, "interval_invalid")
        _integer(command.end_ns, 0, MAX_TIMESTAMP_NS, "interval_invalid")
        _integer(command.principal_units, 0, UNIT_LIMIT - 1, "principal_invalid")
        _require(0 < command.end_ns - command.start_ns <= MAX_INTERVAL_NS, "interval_invalid")
        rate = command.rate
        _require((rate.asset, rate.scale) == (self._identity["asset"], self._identity["scale"]), "rate_currency_mismatch")
        _require(rate.valid_from_ns <= command.start_ns < command.end_ns <= rate.valid_to_ns, "rate_not_effective")
        payload, previous = self._request(command, "ACCRUE", dict(start_ns=command.start_ns,
            end_ns=command.end_ns, principal_units=command.principal_units, rate=rate.wire()))
        if previous is not None:
            return previous  # Historical retry must not rewind the current cursor.
        old = self._state
        _require(command.start_ns == old.cursor_ns, "interval_gap_or_overlap")
        _require(command.principal_units == old.principal_units, "principal_checkpoint_mismatch")
        rate_key = (rate.rate_id, rate.version)
        _require(rate_key not in self._rates or self._rates[rate_key] == _canonical(rate.wire()), "rate_version_conflict")
        numerator = old.carry_numerator + command.principal_units * rate.annual_ppb * (command.end_ns - command.start_ns)
        _require(numerator < 2**256, "intermediate_overflow")
        delta, carry = divmod(numerator, DENOMINATOR)
        booked = old.cumulative_booked_units + delta
        _require(booked < UNIT_LIMIT and booked + int(carry > 0) < UNIT_LIMIT, "risk_units_overflow")
        receipt = self._finish(command, "ACCRUE", payload, cursor=command.end_ns,
            principal=old.principal_units, booked=booked, carry=carry, delta=delta)
        self._rates[rate_key] = _canonical(rate.wire())
        return receipt

    def change_principal(self, command):
        _require(type(command) is PrincipalCommand, "command_invalid")
        _integer(command.at_ns, 0, MAX_TIMESTAMP_NS, "principal_time_invalid")
        _integer(command.principal_units_after, 0, UNIT_LIMIT - 1, "principal_invalid")
        payload, previous = self._request(command, "PRINCIPAL", dict(at_ns=command.at_ns,
            principal_units_after=command.principal_units_after))
        if previous is not None:
            return previous
        old = self._state
        _require(command.at_ns == old.cursor_ns, "principal_requires_accrued_boundary")
        return self._finish(command, "PRINCIPAL", payload, cursor=old.cursor_ns,
            principal=command.principal_units_after, booked=old.cumulative_booked_units,
            carry=old.carry_numerator, delta=0)
