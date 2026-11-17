"""Exact offline borrow accounting transition, without permission or DB writes.

This is one component of future credit operation replay. Its caller must still
prove the source of snapshots, recompute the quote/risk and bind actual native
intent, first-source, market, code and durable terminal evidence. No result of
this module authorizes a loan or activates a NATIVE_PREPARED authority.
"""
from dataclasses import dataclass
import re
from types import MappingProxyType

from .credit_policy import NativeCreditDescriptor, UNIT_LIMIT
from .storage import StorageError


SNAPSHOT_FIELDS = frozenset({"version", "cash_units", "principal_units", "interest_units",
    "principal_ledger_units", "interest_ledger_units", "shard_principal_units", "shard_interest_units",
    "pool_units", "principal_receivable_units", "interest_receivable_units"})
LIMIT_FIELDS = frozenset({"account_limit_units", "local_asset_limit_units"})
SIGNED_FIELDS = frozenset({"cash_units", "principal_ledger_units", "interest_ledger_units"})
_IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}\Z", re.ASCII)
_UNITS = re.compile(r"(?:0|-?[1-9][0-9]{0,37})\Z", re.ASCII)


class CreditTransitionError(StorageError):
    def __init__(self, code, message, status=503):
        super().__init__(message)
        self.code, self.status = code, status


def _invalid(message):
    raise CreditTransitionError("credit_transition_invalid", message)


def _units(value, *, signed=False):
    if type(value) is not str or _UNITS.fullmatch(value) is None:
        _invalid("credit transition requires canonical bounded integer unit strings")
    number = int(value)
    if abs(number) >= UNIT_LIMIT or not signed and number < 0:
        _invalid("credit transition unit amount exceeds its signed or magnitude bounds")
    return number


def _bounded(value):
    if abs(value) >= UNIT_LIMIT:
        _invalid("credit transition result exceeds the ledger magnitude bound")
    return value


def _snapshot(raw):
    if type(raw) is not dict or set(raw) != SNAPSHOT_FIELDS:
        _invalid("credit transition snapshot is incomplete or has unknown fields")
    version = raw["version"]
    if type(version) is not int or not 0 <= version < 2**63 - 1:
        _invalid("credit transition account version cannot be advanced")
    state = {field: _units(value, signed=field in SIGNED_FIELDS)
             for field, value in raw.items() if field != "version"}
    state["version"] = version
    principal, interest = state["principal_units"], state["interest_units"]
    if (state["principal_ledger_units"] != -principal
            or state["interest_ledger_units"] != -interest):
        _invalid("credit transition gross debt differs from its account journal balances")
    if (principal > state["shard_principal_units"] or interest > state["shard_interest_units"]
            or state["principal_receivable_units"] != state["shard_principal_units"]
            or state["interest_receivable_units"] != state["shard_interest_units"]):
        _invalid("credit transition shard components do not reconcile to gross receivables")
    _bounded(principal + interest)
    _bounded(state["shard_principal_units"] + state["shard_interest_units"])
    return state


@dataclass(frozen=True)
class BorrowTransition:
    """Immutable expected arithmetic, deliberately without accepted/ready flags."""
    account_id: str
    asset: str
    scale: int
    amount_units: int
    descriptor_id: str
    allocation_id: str
    before: object
    after: object
    postings: tuple

    def wire(self):
        return {"account_id": self.account_id, "asset": self.asset, "scale": self.scale,
            "amount_units": str(self.amount_units), "descriptor_id": self.descriptor_id,
            "allocation_id": self.allocation_id,
            "before": {key: value if key == "version" else str(value) for key, value in self.before.items()},
            "after": {key: value if key == "version" else str(value) for key, value in self.after.items()},
            "postings": [{"ordinal": ordinal, "account": account, "asset": self.asset,
                          "units": str(units)} for ordinal, (account, units) in enumerate(self.postings)]}


def calculate_borrow_transition(*, descriptor, account_id, asset, amount_units,
                                before, limits, quote_units, quantity_step_units):
    """Recompute gross funded borrowing, limited to this immutable shard budget.

    The quote is an input requiring separate actual market/risk replay. The
    descriptor is a validated declaration, not proof of funding or permission.
    Other shards' balances are never queried, summed or redistributed here.
    """
    if type(descriptor) is not NativeCreditDescriptor:
        _invalid("credit transition requires a validated native descriptor")
    if type(account_id) is not str or _IDENTIFIER.fullmatch(account_id) is None:
        _invalid("credit transition account identity is invalid")
    if type(asset) is not str:
        _invalid("credit transition asset identity is invalid")
    allocation = descriptor.allocation_for(asset, descriptor.shard)
    budget = next(item for item in descriptor.assets if item.asset == asset)
    state = _snapshot(before)
    if type(limits) is not dict or set(limits) != LIMIT_FIELDS:
        _invalid("credit transition needs explicit account and local asset limits")
    account_limit, asset_limit = (_units(limits[field]) for field in
                                 ("account_limit_units", "local_asset_limit_units"))
    amount, quote, step = _units(amount_units), _units(quote_units), _units(quantity_step_units)
    if amount == 0 or step == 0 or amount % step:
        _invalid("credit transition amount must be positive and exactly on its positive step")
    if amount > quote:
        raise CreditTransitionError("credit_limit", "borrow exceeds independently replayed conservative quote", 409)
    if state["principal_units"] + state["interest_units"] + amount > account_limit:
        raise CreditTransitionError("credit_limit", "account gross principal plus interest limit exceeded", 409)
    debt_after = state["shard_principal_units"] + state["shard_interest_units"] + amount
    if debt_after > asset_limit or debt_after > allocation.limit_units:
        raise CreditTransitionError("credit_limit", "local asset or immutable shard allocation exceeded", 409)
    if state["pool_units"] < amount:
        raise CreditTransitionError("credit_pool_empty", "funded local pool has insufficient cash", 409)
    after = dict(state)
    for field, change in (("cash_units", amount), ("principal_units", amount),
                          ("principal_ledger_units", -amount), ("shard_principal_units", amount),
                          ("pool_units", -amount), ("principal_receivable_units", amount)):
        after[field] = _bounded(state[field] + change)
    after["version"] += 1
    # DurableLedger._normalize uses lexicographic account/asset order. A borrow
    # has four distinct legs; no fee, interest or netting is fabricated.
    postings = tuple(sorted((("customer:" + account_id, amount),
        ("liability:principal:" + account_id, -amount),
        ("system:credit-pool", -amount), ("system:credit-principal-receivable", amount))))
    if sum(units for _, units in postings) != 0:
        _invalid("credit transition generated an unbalanced journal")
    return BorrowTransition(account_id, asset, budget.scale, amount, descriptor.descriptor_id,
        allocation.allocation_id, MappingProxyType(state), MappingProxyType(after), postings)


def compare_borrow_transition(expected, *, after, postings):
    """Require the complete recorded post-state and sealed journal legs to agree.

    Journal ID, sealing, hash chain and physical COMMIT are intentionally outside
    this arithmetic component and remain mandatory in future native replay.
    """
    if type(expected) is not BorrowTransition:
        _invalid("credit transition comparison requires its exact expected type")
    _snapshot(after)
    if type(postings) is not list or len(postings) != 4:
        _invalid("credit transition comparison requires all four ordered journal legs")
    for posting in postings:
        if (type(posting) is not dict or set(posting) != {"ordinal", "account", "asset", "units"}
                or type(posting["ordinal"]) is not int or type(posting["account"]) is not str
                or type(posting["asset"]) is not str):
            _invalid("credit transition posting has invalid fields or metadata types")
        _units(posting["units"], signed=True)
    actual = expected.wire()
    if after != actual["after"] or postings != actual["postings"]:
        raise CreditTransitionError("credit_transition_mismatch", "recorded gross debt, cash, pool or complete journal differs")
    return {"accounting_matches": True, "operation_authorized": False,
            "verification_scope": "offline gross accounting and static local budget arithmetic only"}
