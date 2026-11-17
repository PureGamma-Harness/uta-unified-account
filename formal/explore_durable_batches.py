"""Independent finite durable-financial-batch protocol model (stdlib only).

This is a design artifact, NOT imported by runtime and NOT a refinement proof.
Atomic local SQLite commits, durable storage and authentic CID identity are
premises. The state graph intentionally has small fixed bounds; see its JSON.
"""
from collections import deque
from dataclasses import asdict, dataclass, replace
import json


PENDING, SUCCEEDED, REJECTED, QUARANTINED = range(4)
MAX_BATCH = 2
MAX_ATTEMPTS = 3
MAX_WORK = 2  # abstract command steps, not wall-clock milliseconds
CAPACITY = (2, 2)
RO_CAPACITY = (1, 1)


@dataclass(frozen=True)
class Command:
    account: int
    kind: str
    order: int = -1
    amount: int = 1


SCENARIOS = {
    "fifo_cancel_repay": (Command(0, "NEW", 0), Command(0, "CANCEL", 0), Command(1, "REPAY")),
    "cumulative_reduce_only": (Command(0, "REDUCE", 0), Command(0, "REDUCE", 1), Command(1, "REPAY")),
    "duplicate_order": (Command(0, "NEW", 0), Command(0, "NEW", 0), Command(1, "REPAY")),
    "conflicting_order": (Command(0, "NEW", 0), Command(0, "NEW", 0, 2), Command(1, "REPAY")),
    "reject_and_poison": (Command(0, "REJECT"), Command(0, "POISON"), Command(1, "REPAY")),
}


def put(values, index, value):
    return values[:index] + (value,) + values[index + 1:]


@dataclass(frozen=True)
class Book:
    terminal: tuple = (PENDING,) * 3
    effects: tuple = (0,) * 3
    evidence: tuple = (0,) * 3  # decision audit/event/existing-effect link, per kind
    reservation: tuple = (0,) * 3
    replay_of: tuple = (-1,) * 3
    repaid: tuple = (0, 0)


@dataclass(frozen=True)
class State:
    durable: Book = Book()
    scratch: Book | None = None
    batch: tuple = ()
    manifest: tuple = ()  # durable original-CID membership, NOT a new command ID
    cursor: int = 0
    phase: str = "idle"
    gate: bool = False
    lease: bool = True
    fresh: bool = True
    environment_changed: bool = False
    control_requested: bool = False
    control_served: bool = False
    attempts: int = 0
    generic_faults: int = 0
    poison_seen: bool = False
    query_mask: int = 0
    work: int = 0
    sealed: bool = False
    restarted: bool = False
    unknown_actual_commit: bool = False  # oracle-only coverage label, never used by protocol
    bad: str = ""


def heads(book, commands, selected=()):
    pending = [i for i in range(3) if book.terminal[i] == PENDING and i not in selected]
    return [i for i in pending if not any(j < i and commands[j].account == commands[i].account
                                        for j in pending)]


def choices(book, commands, unsafe_fifo=False):
    """Reserved kinds win between eligible heads; never jump their own head.

    A production scheduler also needs the documented age/round-robin escape.
    The tiny bound permits two consecutive same-account commands, so risk is
    checked against earlier savepoint writes in the SAME transaction too.
    """
    def extend(selected):
        eligible = ([i for i in range(3) if book.terminal[i] == PENDING and i not in selected]
                    if unsafe_fifo else heads(book, commands, selected))
        priority = [i for i in eligible if commands[i].kind in ("CANCEL", "REPAY")]
        for index in priority or eligible:
            batch = selected + (index,)
            yield batch
            if len(batch) < MAX_BATCH:
                yield from extend(batch)
    yield from extend(())


def stage(book, index, commands, stale_reduce=False):
    """One savepoint; all risk reads use the current transaction scratch book."""
    command = commands[index]
    if command.kind == "REJECT":
        return replace(book, terminal=put(book.terminal, index, REJECTED),
                       evidence=put(book.evidence, index, 1))
    if command.kind in ("NEW", "REDUCE"):
        prior = next((j for j in range(index) if commands[j].account == command.account
                      and commands[j].order == command.order and book.terminal[j] == SUCCEEDED
                      and commands[j].kind in ("NEW", "REDUCE")), None)
        if prior is not None:
            # A different CID with identical order identity returns existing
            # result/effect. Ingress CID conflicts are checked separately.
            same = commands[prior] == command
            return replace(book, terminal=put(book.terminal, index, SUCCEEDED if same else REJECTED),
                           evidence=put(book.evidence, index, 1),
                           replay_of=put(book.replay_of, index, prior if same else -1))
        used = sum(book.reservation[j] for j in range(3) if commands[j].account == command.account)
        ro = sum(book.reservation[j] for j in range(3) if commands[j].account == command.account
                 and commands[j].kind == "REDUCE")
        if stale_reduce:
            ro = 0
        rejected = used + command.amount > CAPACITY[command.account] or (
            command.kind == "REDUCE" and ro + command.amount > RO_CAPACITY[command.account])
        if rejected:
            return replace(book, terminal=put(book.terminal, index, REJECTED),
                           evidence=put(book.evidence, index, 1))
        return replace(book, terminal=put(book.terminal, index, SUCCEEDED),
                       effects=put(book.effects, index, book.effects[index] + 1),
                       evidence=put(book.evidence, index, 1),
                       reservation=put(book.reservation, index, command.amount))
    reservation, repaid = book.reservation, book.repaid
    if command.kind == "CANCEL":
        for prior in range(index):
            if commands[prior].account == command.account and commands[prior].order == command.order:
                reservation = put(reservation, prior, 0)
    elif command.kind == "REPAY":
        repaid = put(repaid, command.account, repaid[command.account] + command.amount)
    return replace(book, terminal=put(book.terminal, index, SUCCEEDED),
                   effects=put(book.effects, index, book.effects[index] + 1),
                   evidence=put(book.evidence, index, 1), reservation=reservation, repaid=repaid)


def clear(state, **changes):
    return replace(state, scratch=None, batch=(), manifest=(), cursor=0, phase="idle", gate=False,
                   query_mask=0, work=0, sealed=False, unknown_actual_commit=False, **changes)


def next_states(state, commands, mutant=None):
    if not state.control_requested:
        yield "exclusive control requests gate", replace(state, control_requested=True)
    if state.control_requested and not state.control_served and not state.gate:
        yield "serve exclusive control between batches", replace(state, control_served=True)
    if state.phase == "idle" and state.attempts < MAX_ATTEMPTS and state.lease:
        if not state.control_requested or state.control_served:
            for batch in choices(state.durable, commands, mutant == "skip_same_account_head"):
                if state.poison_seen and any(commands[i].kind == "POISON" for i in batch) and len(batch) != 1:
                    continue
                yield "fenced metadata COMMIT records immutable original-CID manifest " + str(batch), replace(
                    state, manifest=batch, phase="prepared", attempts=state.attempts + 1)
    if state.phase == "prepared":
        if not state.control_requested or state.control_served:
            yield "SH gate + actual Wtxn; revalidate original manifest CIDs", replace(
                state, scratch=state.durable, batch=state.manifest, cursor=0, phase="run", gate=True,
                work=0, sealed=False)
    if state.phase in ("prepared", "run", "unknown") and not state.restarted:
        # Volatile batch list/scratch vanish; only the durable manifest and book
        # survive. The restarted worker must recover membership before querying.
        yield "process crash discards volatile list; durable manifest survives", replace(
            state, scratch=None, batch=(), phase="recover", gate=False, restarted=True, query_mask=0)
    if state.phase == "recover":
        yield "restart reads durable original-CID manifest", replace(
            state, batch=state.manifest, phase="unknown")
    if state.phase == "run":
        if not state.environment_changed:
            yield "lease expires inside batch", replace(state, lease=False, environment_changed=True)
            yield "quote reaches age limit inside batch", replace(state, fresh=False, environment_changed=True)
        if mutant == "release_gate_early" and state.gate:
            yield "unsafe release SH before financial COMMIT", replace(state, gate=False)
        if state.generic_faults == 0:
            yield "technical exception rolls back WHOLE Wtxn", clear(state, generic_faults=1)
        if 0 < state.cursor < len(state.batch) and not state.sealed:
            yield "soft batch budget seals executed prefix; remaining originals stay PENDING", replace(
                state, sealed=True)
        if state.cursor < len(state.batch) and state.work < MAX_WORK and not state.sealed:
            index = state.batch[state.cursor]
            if commands[index].kind == "POISON":
                if not state.poison_seen:
                    yield "poison aborts whole Wtxn; persist retry classification later", clear(
                        state, poison_seen=True)
                else:
                    # A subsequent singleton isolation transaction is represented
                    # here. No other selected command may be quarantined with it.
                    after = replace(state.scratch,
                        terminal=put(state.scratch.terminal, index, QUARANTINED))
                    yield "isolated poison gets nonfinancial quarantine receipt", replace(
                        state, scratch=after, cursor=state.cursor + 1, work=state.work + 1)
            else:
                after = stage(state.scratch, index, commands, mutant == "stale_reduce_only")
                if mutant == "reject_leaks_effect" and commands[index].kind == "REJECT":
                    after = replace(after, effects=put(after.effects, index, 1),
                                    reservation=put(after.reservation, index, 1))
                if after.terminal[index] == SUCCEEDED and mutant == "terminal_only_success":
                    after = replace(after, effects=put(after.effects, index, 0),
                                    reservation=put(after.reservation, index, 0), repaid=state.scratch.repaid)
                if commands[index].kind in ("NEW", "REDUCE") and mutant == "missing_reservation":
                    after = replace(after, reservation=put(after.reservation, index, 0))
                if commands[index].kind == "REPAY" and mutant == "missing_repayment":
                    after = replace(after, repaid=state.scratch.repaid)
                if commands[index].kind in ("NEW", "REDUCE") and after.terminal[index] == SUCCEEDED and mutant == "forged_replay_link":
                    after = replace(after, effects=put(after.effects, index, 0),
                                    reservation=put(after.reservation, index, 0),
                                    replay_of=put(after.replay_of, index, index))
                yield "savepoint evaluates original CID " + str(index), replace(
                    state, scratch=after, cursor=state.cursor + 1, work=state.work + 1)
        if state.cursor == len(state.batch) or state.sealed:
            has_new = any(commands[i].kind in ("NEW", "REDUCE") and
                          state.scratch.effects[i] > state.durable.effects[i] for i in state.batch)
            allowed = ((state.lease or mutant == "skip_final_lease") and
                       (state.fresh or not has_new or mutant == "skip_final_quote") and
                       (state.gate or mutant == "release_gate_early"))
            if allowed:
                bad = state.bad
                if not state.lease:
                    bad = "financial COMMIT after lease expiry"
                elif has_new and not state.fresh:
                    bad = "new financial effect after final quote-age failure"
                elif not state.gate:
                    bad = "financial COMMIT outside SH router gate"
                durable = state.scratch
                if mutant == "split_terminal":
                    durable = replace(durable, terminal=state.durable.terminal)
                yield "actual atomic COMMIT; response known", clear(state, durable=durable, bad=bad)
                yield "actual atomic COMMIT; response unknown", replace(
                    state, durable=durable, scratch=None, phase="unknown", gate=False, bad=bad,
                    unknown_actual_commit=True)
            if state.generic_faults == 0:
                yield "COMMIT fails/rollback; response unknown", replace(
                    state, scratch=None, phase="unknown", gate=False, generic_faults=1,
                    unknown_actual_commit=False)
            if not allowed:
                yield "final guard failure rolls back whole Wtxn", clear(state)
    if state.phase == "unknown":
        # Failed/unavailable reads are stuttering: no query bit is advanced and
        # no retry is allowed. Stuttering does not add another finite state.
        for position, index in enumerate(state.batch):
            if not state.query_mask & (1 << position):
                yield "query durable original CID " + str(index), replace(
                    state, query_mask=state.query_mask | (1 << position))
        complete = state.query_mask == (1 << len(state.batch)) - 1
        if complete:
            yield "all originals resolved; retry only remaining PENDING", clear(state)
        elif mutant == "retry_before_query_all":
            yield "unsafe retry/isolation before all original CIDs resolved", replace(
                state, bad="retry before querying every original CID")
        if mutant == "replay_committed_unknown":
            for index in state.batch:
                if state.durable.effects[index]:
                    durable = replace(state.durable, effects=put(
                        state.durable.effects, index, state.durable.effects[index] + 1))
                    yield "unsafe blind execution after committed unknown", replace(state, durable=durable)


def violation(state, commands):
    if state.bad:
        return state.bad
    if state.work > MAX_WORK or len(state.batch) > MAX_BATCH:
        return "batch bound exceeded"
    for position, index in enumerate(state.batch):
        earlier_selected = state.batch[:position]
        if any(j < index and commands[j].account == commands[index].account and
               state.durable.terminal[j] == PENDING and j not in earlier_selected for j in range(3)):
            return "reserved command skipped an earlier same-account PENDING head"
    book = state.durable
    if any(count > 1 for count in book.effects):
        return "original CID produced its financial effect twice"
    for account in (0, 1):
        used = sum(book.reservation[i] for i in range(3) if commands[i].account == account)
        ro = sum(book.reservation[i] for i in range(3) if commands[i].account == account
                 and commands[i].kind == "REDUCE")
        if used > CAPACITY[account]:
            return "account reservation exceeds capacity"
        if ro > RO_CAPACITY[account]:
            return "cumulative reduce-only reservation exceeds reducible position"
        if book.repaid[account] != sum(commands[i].amount * book.effects[i] for i in range(3)
                if commands[i].account == account and commands[i].kind == "REPAY"):
            return "REPAY terminal/effect lacks matching committed ledger amount"
    for index, terminal in enumerate(book.terminal):
        if terminal == REJECTED and (book.effects[index] or book.reservation[index]):
            return "business savepoint rejection leaked a financial effect"
        if book.effects[index] and (terminal != SUCCEEDED or book.evidence[index] != 1):
            return "effect/reservation/evidence/terminal were not one COMMIT"
        if terminal in (SUCCEEDED, REJECTED) and book.evidence[index] != 1:
            return "business terminal lacks committed decision/event/replay evidence"
        if terminal == SUCCEEDED and book.effects[index] != 1 and book.replay_of[index] < 0:
            return "successful terminal lacks its financial effect or existing-effect link"
        if terminal == QUARANTINED and commands[index].kind != "POISON":
            return "innocent batch neighbour was quarantined"
        if terminal != PENDING and any(book.terminal[j] == PENDING and
                commands[j].account == commands[index].account for j in range(index)):
            return "later account command became terminal before its head"
        prior = book.replay_of[index]
        if prior >= 0 and (not 0 <= prior < index or commands[prior] != commands[index]
                          or commands[index].kind not in ("NEW", "REDUCE") or book.effects[index]
                          or book.terminal[prior] != SUCCEEDED or book.effects[prior] != 1
                          or book.evidence[prior] != 1):
            return "duplicate order did not link to a committed original effect"
        expected = 0
        if commands[index].kind in ("NEW", "REDUCE") and book.effects[index]:
            cancelled = any(commands[j].kind == "CANCEL" and commands[j].account == commands[index].account
                            and commands[j].order == commands[index].order and book.terminal[j] == SUCCEEDED
                            for j in range(index + 1, 3))
            expected = 0 if cancelled else commands[index].amount
        if book.reservation[index] != expected:
            return "committed NEW effect lacks exact active reservation (or CANCEL did not release it)"
    return None


def explore(commands, mutant=None):
    initial = State()
    previous, queue = {initial: None}, deque([initial])
    edges = 0
    coverage = set()
    while queue:
        state = queue.popleft()
        if all(t != PENDING for t in state.durable.terminal):
            coverage.add("all_original_cids_terminal")
        if state.phase == "unknown":
            coverage.add("unknown_after_actual_commit" if state.unknown_actual_commit else "unknown_after_rollback")
            if state.unknown_actual_commit and any(state.durable.terminal[i] == PENDING for i in state.batch):
                coverage.add("committed_prefix_unknown_has_terminal_and_pending_originals")
        if state.sealed:
            coverage.add("soft_budget_seals_prefix_without_executing_later_originals")
        if state.control_served:
            coverage.add("exclusive_control_served_between_batches")
        if state.restarted and state.phase == "unknown" and state.batch == state.manifest:
            coverage.add("restart_recovers_all_original_cids_from_manifest")
        if any(i >= 0 for i in state.durable.replay_of):
            coverage.add("duplicate_order_links_existing_effect")
        if any(commands[i].kind in ("NEW", "REDUCE") and state.durable.terminal[i] == REJECTED
               and any(commands[j].account == commands[i].account and commands[j].order == commands[i].order
                       and commands[j] != commands[i] and state.durable.terminal[j] == SUCCEEDED
                       for j in range(i)) for i in range(3)):
            coverage.add("same_order_different_payload_rejected_without_effect")
        if QUARANTINED in state.durable.terminal:
            coverage.add("poison_isolated_without_neighbour_quarantine")
        if state.scratch is not None and any(state.scratch.effects[i] > state.durable.effects[i]
                for i in state.batch) and any(state.scratch.terminal[i] == REJECTED and
                state.durable.terminal[i] == PENDING for i in state.batch):
            coverage.add("same_batch_success_and_business_rejection")
        problem = violation(state, commands)
        if problem:
            trace = []
            while previous[state] is not None:
                before, action = previous[state]
                trace.append({"action": action, "after": asdict(state)})
                state = before
            return {"states": len(previous), "transitions": edges, "violation": problem,
                    "counterexample": list(reversed(trace))}
        for action, after in next_states(state, commands, mutant):
            edges += 1
            if after not in previous:
                previous[after] = state, action
                queue.append(after)
    return {"states": len(previous), "transitions": edges, "violation": None,
            "coverage": sorted(coverage)}


def identity_cases():
    """Exhaust every same/different CID + canonical payload pair in tiny domain.

    The immutable map is the ingress premise, not a production SQL trigger test.
    ACK is represented only as queued; it never increments financial success.
    """
    checked = 0
    for old_cid in (0, 1):
        for old_payload in (0, 1):
            for cid in (0, 1):
                for payload in (0, 1):
                    rows = {old_cid: old_payload}
                    conflict = cid in rows and rows[cid] != payload
                    if not conflict:
                        rows.setdefault(cid, payload)
                    assert rows[old_cid] == old_payload
                    assert conflict == (cid == old_cid and payload != old_payload)
                    assert len(rows) == (1 if cid == old_cid else 2)
                    checked += 1
    return {"cases": checked, "passed": True,
            "same_cid_different_payload": "conflict; immutable queued identity",
            "ack_is_financial_success": False}


def main():
    safe = {name: explore(commands) for name, commands in SCENARIOS.items()}
    negative_scenarios = {
        "split_terminal": ("fifo_cancel_repay", "effect/reservation/evidence/terminal were not one COMMIT"),
        "skip_same_account_head": ("fifo_cancel_repay", "reserved command skipped an earlier same-account PENDING head"),
        "skip_final_lease": ("fifo_cancel_repay", "financial COMMIT after lease expiry"),
        "skip_final_quote": ("fifo_cancel_repay", "new financial effect after final quote-age failure"),
        "release_gate_early": ("fifo_cancel_repay", "financial COMMIT outside SH router gate"),
        "retry_before_query_all": ("fifo_cancel_repay", "retry before querying every original CID"),
        "replay_committed_unknown": ("fifo_cancel_repay", "original CID produced its financial effect twice"),
        "stale_reduce_only": ("cumulative_reduce_only", "cumulative reduce-only reservation exceeds reducible position"),
        "reject_leaks_effect": ("reject_and_poison", "business savepoint rejection leaked a financial effect"),
        "terminal_only_success": ("fifo_cancel_repay", "successful terminal lacks its financial effect or existing-effect link"),
        "missing_reservation": ("fifo_cancel_repay", "committed NEW effect lacks exact active reservation (or CANCEL did not release it)"),
        "missing_repayment": ("fifo_cancel_repay", "REPAY terminal/effect lacks matching committed ledger amount"),
        "forged_replay_link": ("duplicate_order", "duplicate order did not link to a committed original effect"),
    }
    negative = {mutant: {**explore(SCENARIOS[name], mutant), "expected_violation": expected}
                for mutant, (name, expected) in negative_scenarios.items()}
    identities = identity_cases()
    common_coverage = {"all_original_cids_terminal", "unknown_after_actual_commit", "unknown_after_rollback",
        "restart_recovers_all_original_cids_from_manifest", "exclusive_control_served_between_batches",
        "soft_budget_seals_prefix_without_executing_later_originals",
        "committed_prefix_unknown_has_terminal_and_pending_originals"}
    extra_coverage = {
        "cumulative_reduce_only": {"same_batch_success_and_business_rejection"},
        "duplicate_order": {"duplicate_order_links_existing_effect"},
        "conflicting_order": {"same_order_different_payload_rejected_without_effect"},
        "reject_and_poison": {"poison_isolated_without_neighbour_quarantine", "same_batch_success_and_business_rejection"},
    }
    for name, result in safe.items():
        required = common_coverage | extra_coverage.get(name, set())
        result["required_coverage"] = sorted(required)
        result["missing_coverage"] = sorted(required - set(result.get("coverage", [])))
    passed = all(r["violation"] is None and not r["missing_coverage"] for r in safe.values()) and all(
        r["violation"] == r["expected_violation"] for r in negative.values()) and identities["passed"]
    print(json.dumps({"passed": passed, "safe": safe, "negative_controls": negative,
        "identity": identities,
        "bounds": {"commands": 3, "accounts": 2, "batch_size": MAX_BATCH,
                   "attempts": MAX_ATTEMPTS, "abstract_work_steps": MAX_WORK,
                   "environment_changes": 1, "generic_technical_faults": 1, "poison_failures": 1,
                   "process_crashes": 1,
                   "local_writers": 1, "shards_in_transaction": 1},
        "assumptions": ["atomic local financial/reservation/evidence/terminal COMMIT",
                        "durable inbox and authentic immutable original CID",
                        "durable immutable batch manifest and authoritative successful CID queries",
                        "one local writer; no external unmodelled financial writer",
                        "SH gate excludes EX control and funding transitions",
                        "SQL fencing validates actual token identity and lease at COMMIT"],
        "not_proven": ["runtime implementation/refinement", "liveness/fair scheduling",
                       "physical WAL/fsync durability or real RPO", "clock/pause bounds",
                       "real control-response latency or flock fairness", "all exception classes",
                       "arbitrary batch size/scale", "cross-shard atomicity/HA/replication",
                       "full financial calculator correctness or production approval"],
        "production_approved": False}, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
