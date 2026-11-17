#!/usr/bin/env python3
"""Bounded design model; no SQL, imports from uta, network or runtime grants.

Run on CPU3 with an external <=3s watchdog. This is NOT an implementation of
the proposed coordinator, old-binary retirement, importer or storage guards.
Atomic transitions abstract confirmed COMMIT; unknown outcomes require query.
Assume a trusted operator/host and a correctly enforced persistent intake gate,
terminal retirement and domain CAS. Actual implementations need independent
acceptance. Two fixed original CIDs, assets and epochs deliberately bound scope.
"""
from collections import deque
from dataclasses import dataclass, replace
from hashlib import sha256
import json
import time


NONE, SOURCE_ONLY, PENDING, SUCCEEDED, REJECTED = range(5)
OLD, QUIESCING, FROZEN, PREPARED, RETIRED, NEW, ABORTED = range(7)
ASSETS = ("BTC", "USD")
BUILDS = ("reviewed-old-runtime", "reviewed-new-runtime")
POLICIES = ("original-exact-policy", "same-semantics-reviewed-policy")
INITIAL = ((4, 5), (6, 8), (2, 0), (1, 0), (0, 0))
CID_PAYLOADS = ("borrow-original-payload", "repay-original-payload")


@dataclass(frozen=True)
class State:
    phase: int = OLD
    commands: tuple = (NONE, NONE)
    cash: tuple = INITIAL[0]
    pool: tuple = INITIAL[1]
    principal: tuple = INITIAL[2]
    interest: tuple = INITIAL[3]
    income: tuple = INITIAL[4]
    # Event = (original CID index, executing epoch, exact ordered postings).
    events: tuple = ()
    effects: tuple = (0, 0)
    # A model token is (epoch, generation). Real tokens also bind PID/boot/etc.
    lease: tuple = (0, 1)
    live: bool = True
    staged: tuple = ()
    snapshot: tuple = ()
    registry_epoch: int = 0
    retired: bool = False
    certificate_consumed: bool = False


def view(state):
    """Abstract complete root. Actual root must include ALL protocol groups."""
    return (ASSETS, state.commands, state.cash, state.pool, state.principal,
            state.interest, state.income, state.events, state.effects,
            CID_PAYLOADS, BUILDS[0], POLICIES[0])


def digest(value):
    return sha256(json.dumps(value, separators=(",", ":")).encode()).hexdigest()


def authorized(state, epoch, generation, build):
    allowed_phase = state.phase in (OLD, QUIESCING) if epoch == 0 else state.phase == NEW
    return (epoch in (0, 1) and allowed_phase and state.live
            and state.lease == (epoch, generation)
            and state.registry_epoch == epoch and build == BUILDS[epoch]
            and (epoch != 0 or not state.retired)
            and (epoch != 1 or state.retired and state.certificate_consumed))


def can_freeze(state):
    return (state.phase == QUIESCING and not state.live and not state.staged
            and all(value in (NONE, SUCCEEDED, REJECTED) for value in state.commands))


def intake(state, cid, *, split=False):
    if state.phase not in (OLD, NEW) or state.commands[cid] != NONE:
        return None
    # Fixed producer order bounds per-account FIFO without modeling transport.
    if cid == 1 and state.commands[0] == NONE:
        return None
    commands = list(state.commands)
    commands[cid] = SOURCE_ONLY if split else PENDING
    return replace(state, commands=tuple(commands))


def deliver(state, cid):
    if state.commands[cid] != SOURCE_ONLY or state.phase not in (OLD, QUIESCING, NEW):
        return None
    commands = list(state.commands)
    commands[cid] = PENDING
    return replace(state, commands=tuple(commands))


def begin(state, cid, *, build=None):
    epoch, generation = state.lease
    if not authorized(state, epoch, generation, build or BUILDS[epoch]):
        return None
    if state.staged or state.commands[cid] != PENDING:
        return None
    if any(value in (SOURCE_ONLY, PENDING) for value in state.commands[:cid]):
        return None
    return replace(state, staged=(cid, epoch, generation))


def financial(state, *, build=None):
    if not state.staged:
        return None
    cid, epoch, generation = state.staged
    if not authorized(state, epoch, generation, build or BUILDS[epoch]):
        return None
    if state.commands[cid] != PENDING or state.effects[cid]:
        return None
    cash, pool, principal, interest, income = [list(getattr(state, field))
        for field in ("cash", "pool", "principal", "interest", "income")]
    if cid == 0:
        # Four exact BTC legs: cash, pool, principal receivable, debt liability.
        amount = 2
        if pool[0] < amount:
            return None
        cash[0] += amount
        pool[0] -= amount
        principal[0] += amount
        legs = (("customer_cash", "BTC", 2), ("pool", "BTC", -2),
                ("principal_receivable", "BTC", 2), ("principal_liability", "BTC", -2))
    else:
        amount = 2
        paid_interest = min(amount, interest[0])
        paid_principal = min(amount - paid_interest, principal[0])
        paid = paid_interest + paid_principal
        if cash[0] < paid or not paid:
            return None
        cash[0] -= paid
        pool[0] += paid_principal
        principal[0] -= paid_principal
        interest[0] -= paid_interest
        income[0] += paid_interest
        legs = tuple(row for row in (
            ("customer_cash", "BTC", -paid), ("pool", "BTC", paid_principal),
            ("interest_cash", "BTC", paid_interest),
            ("interest_liability", "BTC", paid_interest),
            ("interest_receivable", "BTC", -paid_interest),
            ("principal_liability", "BTC", paid_principal),
            ("principal_receivable", "BTC", -paid_principal)) if row[2])
    commands, effects = list(state.commands), list(state.effects)
    commands[cid], effects[cid] = SUCCEEDED, effects[cid] + 1
    return replace(state, cash=tuple(cash), pool=tuple(pool),
        principal=tuple(principal), interest=tuple(interest), income=tuple(income),
        commands=tuple(commands), effects=tuple(effects), staged=(),
        events=state.events + ((cid, epoch, legs),))


def receipt(state, cid, payload):
    if payload != CID_PAYLOADS[cid]:
        raise ValueError("original-CID payload conflict")
    if state.commands[cid] not in (SUCCEEDED, REJECTED):
        return (cid, state.commands[cid], "not-terminal")
    return (cid, state.commands[cid], CID_PAYLOADS[cid],
            tuple(event for event in state.events if event[0] == cid))


def prepare(state, root, *, approved=True, build=BUILDS[1]):
    if state.phase == PREPARED and root == state.snapshot and approved and build == BUILDS[1]:
        return state
    if (state.phase != FROZEN or root != state.snapshot or root != view(state)
            or not approved or build != BUILDS[1]):
        return None
    # Import is exact continuation metadata; do not post another loan/funding.
    return replace(state, phase=PREPARED)


def retire(state):
    if state.phase == RETIRED:
        return state
    if state.phase != PREPARED or state.snapshot != view(state):
        return None
    return replace(state, phase=RETIRED, retired=True, live=False)


def activate(state):
    if state.phase == NEW and state.certificate_consumed:
        return state
    if (state.phase != RETIRED or not state.retired or state.registry_epoch != 0
            or state.certificate_consumed or state.snapshot != view(state)):
        return None
    # Atomic global certificate consumption + CAS; local lease comes later.
    return replace(state, phase=NEW, registry_epoch=1, certificate_consumed=True,
                   lease=(1, 3), live=False)


def abort(state):
    if state.phase not in (FROZEN, PREPARED) or state.retired:
        return None
    return replace(state, phase=ABORTED, live=False)


def next_states(state):
    for cid in range(2):
        for split in (False, True):
            candidate = intake(state, cid, split=split)
            if candidate is not None:
                yield "source-split" if split else "source+pending", candidate
        candidate = deliver(state, cid)
        if candidate is not None:
            yield "deliver-original-source", candidate
        candidate = begin(state, cid)
        if candidate is not None:
            yield "begin-financial", candidate
    if state.staged:
        candidate = financial(state)
        if candidate is not None:
            yield "financial-commit", candidate
        yield "rollback-before-commit", replace(state, staged=())
        cid = state.staged[0]
        commands = list(state.commands)
        commands[cid] = REJECTED
        yield "known-business-rejection", replace(state, commands=tuple(commands), staged=())
    if state.phase == OLD:
        yield "durable-intake-barrier", replace(state, phase=QUIESCING)
    if state.live and state.phase in (OLD, QUIESCING, NEW):
        yield "crash-or-expire", replace(state, live=False, staged=())
    if not state.live and state.phase in (OLD, QUIESCING) and state.lease == (0, 1):
        yield "old-exact-runtime-recover", replace(state, lease=(0, 2), live=True)
    if not state.live and state.phase == NEW and state.lease[1] in (3, 4):
        generation = 4 if state.lease[1] == 3 else 4
        yield "new-exact-runtime-recover", replace(state, lease=(1, generation), live=True)
    if can_freeze(state):
        yield "freeze-and-bind-root", replace(state, phase=FROZEN, snapshot=view(state))
    for name, candidate in (
        ("prepare-reviewed-successor", prepare(state, state.snapshot)),
        ("retire-original", retire(state)), ("certificate-CAS", activate(state)),
        ("abort-before-retirement", abort(state))):
        if candidate is not None and candidate != state:
            yield name, candidate


def writer_invariant(state, authorizer=authorized):
    assert not authorizer(state, 0, state.lease[1], "unknown-build")
    assert not authorizer(state, 1, state.lease[1], "unknown-build")
    writers = [epoch for epoch in (0, 1)
               if authorizer(state, epoch, state.lease[1], BUILDS[epoch])]
    assert len(writers) <= 1
    assert not state.retired or 0 not in writers


def invariant(state):
    assert state.registry_epoch == int(state.certificate_consumed)
    assert not state.certificate_consumed or state.retired
    assert state.phase != NEW or state.retired and state.certificate_consumed
    writer_invariant(state)
    for cid in range(2):
        assert 0 <= state.effects[cid] <= 1
        assert state.effects[cid] == sum(event[0] == cid for event in state.events)
        assert bool(state.effects[cid]) == (state.commands[cid] == SUCCEEDED)
    for asset_index, asset in enumerate(ASSETS):
        assert state.cash[asset_index] + state.pool[asset_index] + state.income[asset_index] == (
            INITIAL[0][asset_index] + INITIAL[1][asset_index] + INITIAL[4][asset_index])
        assert min(state.pool[asset_index], state.principal[asset_index],
                   state.interest[asset_index], state.income[asset_index]) >= 0
        for _, _, legs in state.events:
            assert sum(units for _, leg_asset, units in legs if leg_asset == asset) == 0
    assert (state.cash[1], state.pool[1], state.principal[1], state.interest[1], state.income[1]) == (5, 8, 0, 0, 0)
    # Independent simple formula from the two commands, not the transition code.
    borrowed, repaid = state.effects
    assert state.cash[0] == 4 + 2 * borrowed - 2 * repaid
    assert state.pool[0] == 6 - 2 * borrowed + repaid
    assert state.principal[0] == 2 + 2 * borrowed - repaid
    assert state.interest[0] == 1 - repaid
    assert state.income[0] == repaid
    if state.phase in (FROZEN, PREPARED, RETIRED):
        assert state.snapshot == view(state)
        assert not state.live and not state.staged
        assert all(value in (NONE, SUCCEEDED, REJECTED) for value in state.commands)
    if state.staged:
        cid, epoch, generation = state.staged
        assert state.commands[cid] == PENDING
        assert authorized(state, epoch, generation, BUILDS[epoch])


def frozen_empty():
    state = replace(State(), phase=QUIESCING, live=False)
    return replace(state, phase=FROZEN, snapshot=view(state))


def golden_checks():
    outcomes = []

    def record(name, condition):
        assert condition, name
        outcomes.append(name)

    source = intake(State(), 0, split=True)
    record("split-producer-COMMIT-has-no-financial-effect", source.effects == (0, 0))
    blocked = replace(source, phase=QUIESCING, live=False)
    record("source-only-and-UNKNOWN-block-freeze", not can_freeze(blocked))
    pending = deliver(source, 0)
    staged = begin(pending, 0)
    rolled = replace(staged, staged=())
    record("pre-COMMIT-rollback-preserves-original-PENDING", rolled == pending)
    record("loaded-build-change-denies-final-COMMIT", financial(staged, build="unknown-build") is None)
    borrowed = financial(staged)
    original_receipt = receipt(borrowed, 0, CID_PAYLOADS[0])
    record("four-leg-borrow-original-CID-once", len(borrowed.events[0][2]) == 4
           and intake(borrowed, 0) is None and begin(borrowed, 0) is None)
    # A reply-loss observer/query is pure; neither success nor failure is guessed.
    record("after-COMMIT-lost-reply-query-is-original", original_receipt == receipt(borrowed, 0, CID_PAYLOADS[0])
           and borrowed.effects == (1, 0))
    try:
        receipt(borrowed, 0, "changed-payload")
    except ValueError:
        conflict = True
    else:
        conflict = False
    record("same-CID-changed-payload-denied", conflict)
    repaid = financial(begin(intake(borrowed, 1), 1))
    record("seven-leg-interest-first-repay", len(repaid.events[1][2]) == 7
           and repaid.interest[0] == 0 and repaid.principal[0] == 3
           and repaid.pool[0] == 5 and repaid.income[0] == 1)
    frozen = frozen_empty()
    tampered = list(frozen.snapshot)
    tampered[3] = (6, 9)  # Silent USD pool change must not pass a BTC-only check.
    record("all-asset-opening-root-mismatch-denied", prepare(frozen, tuple(tampered)) is None)
    record("unknown-build-and-missing-independent-approval-denied",
           prepare(frozen, frozen.snapshot, build="unknown-build") is None
           and prepare(frozen, frozen.snapshot, approved=False) is None)
    prepared = prepare(frozen, frozen.snapshot)
    record("repeat-identical-prepare-is-idempotent", prepare(prepared, prepared.snapshot) == prepared)
    record("abort-before-retirement-is-reviewable", abort(prepared).phase == ABORTED)
    retired = retire(prepared)
    record("retirement-to-CAS-interruption-has-no-writer", not retired.live
           and not authorized(retired, 0, 1, BUILDS[0]) and abort(retired) is None)
    activated = activate(retired)
    record("once-only-certificate-and-activation", activate(activated) == activated
           and activated.certificate_consumed and retire(retired) == retired)
    active = replace(activated, live=True)
    record("stale-old-primary-and-unknown-new-build-denied",
           not authorized(active, 0, 1, BUILDS[0])
           and begin(intake(active, 0), 0, build="unknown-build") is None)
    new_borrow = financial(begin(intake(active, 0), 0))
    record("new-effect-never-permits-simple-downgrade", abort(new_borrow) is None
           and not authorized(new_borrow, 0, 1, BUILDS[0]))
    record("opening-import-creates-no-funding-or-loan", view(active) == frozen.snapshot
           and active.events == () and active.effects == (0, 0))
    # Mutant: original DB has no terminal retirement, so old exact binary can
    # reacquire its separate local lease after the successor is active.
    def missing_retirement_fence(state, epoch, generation, build):
        if state.phase == NEW and epoch == 0 and build == BUILDS[0]:
            return True
        return authorized(state, epoch, generation, build)

    try:
        writer_invariant(active, missing_retirement_fence)
    except AssertionError:
        two_writers_caught = True
    else:
        two_writers_caught = False
    record("negative-control-missing-fence-detects-two-writers", two_writers_caught)
    # Mutant: accept an altered opening instead of comparing it with old close.
    bad_import = replace(frozen, phase=PREPARED, snapshot=tuple(tampered))
    try:
        invariant(bad_import)
    except AssertionError:
        wrong_opening_caught = True
    else:
        wrong_opening_caught = False
    record("negative-control-missing-root-check-detects-USD-tamper", wrong_opening_caught)
    for state in (source, pending, staged, borrowed, repaid, frozen, prepared, retired, activated, active, new_borrow):
        invariant(state)
    return outcomes


def main():
    started = time.process_time()
    goldens = golden_checks()
    initial = State()
    queue, seen = deque([initial]), {initial}
    transitions, terminal, eventful_new = 0, 0, 0
    phases = set()
    while queue:
        state = queue.popleft()
        invariant(state)
        phases.add(state.phase)
        terminal += state.phase == ABORTED
        eventful_new += state.phase == NEW and any(event[1] == 1 for event in state.events)
        for _, candidate in next_states(state):
            transitions += 1
            invariant(candidate)
            if candidate not in seen:
                seen.add(candidate)
                queue.append(candidate)
    assert phases == set(range(7)) and terminal and eventful_new
    cpu = time.process_time() - started
    assert cpu < 3.0, "bounded model exceeded the 3s CPU budget"
    print(json.dumps({
        "model": "credit-authority-upgrade-bounded-v1", "status": "passed",
        "scope": "pure design contract; no database, service, production acceptance or actual binary test",
        "bounds": {"CIDs": 2, "assets": list(ASSETS), "epochs": 2,
                   "simultaneous_financial_transactions": 1, "CPU_budget_seconds": 3},
        "states": len(seen), "transitions": transitions, "phases_visited": len(phases),
        "aborted_states": terminal, "new_epoch_effect_states": eventful_new,
        "goldens": goldens, "golden_count": len(goldens),
        "empty_opening_digest": digest(view(State())), "process_cpu_seconds": round(cpu, 6),
        "assumptions": ["trusted host/operator", "implemented durable intake barrier",
                        "implemented terminal retirement", "implemented atomic domain certificate/CAS",
                        "confirmed atomic storage transitions", "complete snapshot exporter not modeled"],
        "production_approval": False}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
