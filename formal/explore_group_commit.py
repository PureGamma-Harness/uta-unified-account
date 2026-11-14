"""Bounded protocol exploration of two grouped, idempotent reservations.

Independent of admission.py. Two one-unit commands compete for one unit of
margin. One atomic writer can crash, fail COMMIT, lose responses, or retry IDs.
This explores the protocol abstraction, not Python/code equivalence or liveness.
"""
from collections import deque
from dataclasses import asdict, dataclass, replace
import json


CAPACITY = 1
MAX_ATTEMPTS = 2
ORDERS = ((0, 1), (1, 0))


@dataclass(frozen=True)
class State:
    phase: str = "idle"
    attempt: int = 0
    order: int = 0
    processed: int = 0
    durable: tuple[int, int] = (0, 0)
    committed: tuple[int, int] = (0, 0)
    staged: tuple[int, int] = (0, 0)
    accepted: int = 0
    rejected: int = 0
    sent_success: int = 0
    sent_rejection: int = 0
    historical_success: int = 0


def violation(state):
    if state.durable != state.committed:
        return "financial state changed without a successful atomic COMMIT"
    if any(value not in (0, 1) for value in state.durable) or sum(state.durable) > CAPACITY:
        return "a business ID reserved twice or durable margin exceeds capacity"
    if state.phase in ("processing", "ready") and sum(state.staged) > CAPACITY:
        return "staged retry duplicates a reservation or exceeds margin capacity"
    for command in (0, 1):
        if state.historical_success & (1 << command) and state.durable[command] != 1:
            return "success receipt has no corresponding committed reservation"
    if state.sent_success and state.phase != "committed":
        return "a success receipt was published before the group's COMMIT"
    if state.sent_rejection and state.phase != "committed":
        return "queued business rejection was published for an uncommitted or failed group"
    if state.accepted & state.rejected:
        return "one command cannot both succeed and be rejected in a group"
    return None


def aborted(state):
    return replace(state, phase="idle", processed=0, staged=state.durable,
                   accepted=0, rejected=0, sent_success=0, sent_rejection=0)


def transitions(state, mutant=None):
    if state.phase == "idle" and state.attempt < MAX_ATTEMPTS:
        for order in range(len(ORDERS)):
            yield ("begin_group" if not state.attempt else "retry_same_business_IDs") + str(ORDERS[order]), replace(
                state, phase="processing", attempt=state.attempt + 1, order=order,
                processed=0, staged=state.durable, accepted=0, rejected=0,
                sent_success=0, sent_rejection=0)
    if state.phase in ("processing", "ready"):
        yield "process_exit_before_COMMIT", aborted(state)
        if mutant == "early_success_before_commit":
            for command in (0, 1):
                bit = 1 << command
                if state.accepted & bit and not state.sent_success & bit:
                    yield f"publish_success({command})_BEFORE_COMMIT", replace(
                        state, sent_success=state.sent_success | bit,
                        historical_success=state.historical_success | bit)
    if state.phase == "processing":
        command = ORDERS[state.order][state.processed]
        bit = 1 << command
        staged = list(state.staged)
        accepted, rejected = state.accepted, state.rejected
        if state.durable[command]:
            accepted |= bit
            if mutant == "retry_duplicate_reserve":
                staged[command] += 1
            action = f"idempotent_replay({command})"
        elif sum(staged) < CAPACITY:
            staged[command] += 1
            accepted |= bit
            action = f"stage_reservation({command})"
        else:
            rejected |= bit
            action = f"business_reject_capacity({command})"
        processed = state.processed + 1
        yield action, replace(state, processed=processed, staged=tuple(staged),
                              accepted=accepted, rejected=rejected,
                              phase="ready" if processed == 2 else "processing")
    if state.phase == "ready":
        yield "atomic_COMMIT", replace(state, phase="committed", durable=state.staged,
                                        committed=state.staged)
        yield "COMMIT_failure_and_full_rollback", aborted(state)
        if mutant == "rejection_before_failed_commit" and state.rejected:
            bit = state.rejected & -state.rejected
            yield "publish_business_rejection_then_COMMIT_fails", replace(
                state, phase="failed", staged=state.durable, sent_rejection=bit)
        if mutant == "failed_group_leaks_writes":
            yield "COMMIT_failure_but_staged_writes_survive", replace(
                state, phase="failed", durable=state.staged, staged=state.durable)
    if state.phase == "committed":
        yield "process_exit_after_COMMIT_or_lost_response", aborted(state)
        for command in (0, 1):
            bit = 1 << command
            if state.accepted & bit and not state.sent_success & bit:
                yield f"publish_committed_success({command})", replace(
                    state, sent_success=state.sent_success | bit,
                    historical_success=state.historical_success | bit)
            if state.rejected & bit and not state.sent_rejection & bit:
                yield f"publish_business_rejection_after_COMMIT({command})", replace(
                    state, sent_rejection=state.sent_rejection | bit)


def explore(mutant=None):
    initial = State()
    pending = deque([initial])
    parents = {initial: None}
    edge_count, terminal_count = 0, 0
    while pending:
        state = pending.popleft()
        reason = violation(state)
        if reason:
            trace = []
            current = state
            while parents[current] is not None:
                previous, action = parents[current]
                trace.append({"action": action, "state": asdict(current)})
                current = previous
            return {"result": "counterexample", "reachable_states": len(parents),
                    "violation": reason, "trace": list(reversed(trace))}
        successors = list(transitions(state, mutant))
        if not successors:
            terminal_count += 1
        for action, next_state in successors:
            edge_count += 1
            if next_state not in parents:
                parents[next_state] = (state, action)
                pending.append(next_state)
    return {"result": "invariants_hold", "reachable_states": len(parents),
            "explored_transitions": edge_count, "terminal_states": terminal_count}


def main():
    report = {"safe": explore()}
    mutants = ("early_success_before_commit", "rejection_before_failed_commit",
               "failed_group_leaks_writes", "retry_duplicate_reserve")
    report.update({"unsafe_" + name: explore(name) for name in mutants})
    report["bounds"] = {"business_IDs": 2, "reservation_per_ID": 1,
                        "margin_capacity": CAPACITY, "group_size": 2,
                        "maximum_attempts": MAX_ATTEMPTS, "atomic_writers": 1}
    report["assumptions"] = ["same business ID and immutable content on retry",
        "one atomic database writer; successful WAL COMMIT is durable",
        "no financial execution outside the transaction", "no reservation release in this bounded model"]
    report["not_verified"] = ["implementation/model equivalence", "HA or replication",
        "power-loss durability of actual hardware", "liveness or arbitrary queue fairness",
        "arbitrary portfolios, IDs or retry counts", "market freshness and matching"]
    print(json.dumps(report, indent=2))
    passed = (report["safe"]["result"] == "invariants_hold" and
              all(report["unsafe_" + name]["result"] == "counterexample" for name in mutants))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
