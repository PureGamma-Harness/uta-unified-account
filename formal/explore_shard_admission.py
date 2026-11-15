"""Independent bounded admission scheduling/barrier and crash-retry models.

No UTA/runtime imports. These are finite safety abstractions, not a proof of
implementation equivalence, fairness, distributed fencing, or physical fsync.
"""
from collections import deque
from dataclasses import asdict, dataclass, replace
from hashlib import sha256
import json
from pathlib import Path
import platform


COMMANDS = (("alice", 0), ("alice", 0), ("bob", 1))
WORKERS = 2
MAX_GROUP = 2


def put(items, index, value):
    return items[:index] + (value,) + items[index + 1:]


@dataclass(frozen=True)
class Group:
    jobs: tuple[int, ...] = ()
    phase: str = "idle"
    shared: bool = False
    generation: int = -1
    allowed: bool = False


@dataclass(frozen=True)
class Schedule:
    queue: tuple[int, ...] = (0, 1, 2)
    workers: tuple[Group, ...] = (Group(), Group())
    durable: tuple[int, ...] = (0, 0, 0)
    committed: int = 0
    success: int = 0
    rejected: int = 0
    completed: int = 0
    execution: tuple[int, ...] = ()
    publisher: str = "idle"
    generation: int = 0
    markets: tuple[int, int] = (0, 0)
    halted: bool = False
    publishing: bool = False
    invalid_commit: bool = False


def exclusive(state):
    return state.publisher in ("exclusive0", "exclusive1", "exclusive2", "activate")


def shard(group):
    return COMMANDS[group.jobs[0]][1]


def bits(jobs):
    return sum(1 << job for job in jobs)


def schedule_violation(state):
    live = [group for group in state.workers if group.phase != "idle"]
    for target in (0, 1):
        if sum(shard(group) == target for group in live) > 1:
            return "two groups own the same shard in one adapter"
        if sum(shard(group) == target and group.phase in ("gated", "staged") for group in live) > 1:
            return "more than one active writer owns a shard"
    if exclusive(state) and any(group.shared for group in live):
        return "exclusive publication overlaps a shared admission gate"
    if exclusive(state) and any(group.phase in ("gated", "staged") for group in live):
        return "exclusive publication overlaps an uncommitted admission writer"
    for account in ("alice", "bob"):
        expected = tuple(index for index, command in enumerate(COMMANDS) if command[0] == account)
        actual = tuple(index for index in state.execution if COMMANDS[index][0] == account)
        if actual != expected[:len(actual)]:
            return "same-account execution is not an enqueue-order prefix"
    if state.success & ~state.committed:
        return "a successful Future was visible before its group COMMIT"
    for job in range(len(COMMANDS)):
        if state.success & (1 << job) and state.durable[job] != 1:
            return "a successful receipt has no durable reservation"
    if any(value not in (0, 1) for value in state.durable):
        return "one command ID created more than one durable reservation"
    if state.invalid_commit:
        return "a new reservation committed against a changed or halted market generation"
    if state.success & state.rejected:
        return "one command was both successful and rejected"
    if not state.halted and (state.publishing or state.markets != (state.generation,) * 2):
        return "global activation has an incomplete market publication barrier"
    assigned = [job for group in live for job in group.jobs]
    completed = [job for job in range(len(COMMANDS)) if state.completed & (1 << job)]
    if sorted((*state.queue, *assigned, *completed)) != list(range(len(COMMANDS))):
        return "the bounded scheduler lost or multiply assigned a queued command"
    return None


def schedule_next(state, mutant=None):
    for worker, group in enumerate(state.workers):
        label = "worker" + str(worker)
        if group.phase == "idle":
            active = {shard(other) for other in state.workers if other.phase != "idle"}
            eligible = [job for job in state.queue
                        if COMMANDS[job][1] not in active or mutant == "overlapping_shard_groups"]
            if not eligible:
                continue
            target = COMMANDS[eligible[0]][1]
            queued = tuple(job for job in state.queue if COMMANDS[job][1] == target)
            for size in range(1, min(MAX_GROUP, len(queued)) + 1):
                jobs = queued[:size]
                if mutant == "account_fifo_overtake" and len(queued) > size:
                    jobs = queued[-size:]
                selected = Group(jobs=jobs, phase="selected")
                yield label + ":select" + str(jobs), replace(
                    state, queue=tuple(job for job in state.queue if job not in jobs),
                    workers=put(state.workers, worker, selected))
        elif group.phase == "selected" and not exclusive(state):
            admitted = replace(group, phase="gated", shared=True,
                               generation=state.generation,
                               allowed=not state.halted and not state.publishing)
            yield label + ":acquire_SHARED_and_shard_writer", replace(
                state, workers=put(state.workers, worker, admitted))
        elif group.phase == "gated":
            yield label + ":stage_FIFO_commands" + str(group.jobs), replace(
                state, execution=state.execution + group.jobs,
                workers=put(state.workers, worker, replace(group, phase="staged")))
        elif group.phase == "staged":
            if mutant == "future_before_commit" and group.allowed:
                yield label + ":publish_success_BEFORE_COMMIT", replace(
                    state, success=state.success | bits(group.jobs))
            if mutant == "release_shared_before_commit" and group.shared:
                yield label + ":release_SHARED_BEFORE_COMMIT", replace(
                    state, workers=put(state.workers, worker, replace(group, shared=False)))
            durable = list(state.durable)
            if group.allowed:
                for job in group.jobs:
                    durable[job] += 1
            bad = (group.allowed and (state.halted or state.publishing
                or group.generation != state.generation
                or state.markets[shard(group)] != group.generation))
            committed = replace(group, phase="committed", shared=False)
            yield label + ":atomic_COMMIT_then_release_SHARED", replace(
                state, durable=tuple(durable), committed=state.committed | bits(group.jobs),
                invalid_commit=state.invalid_commit or bad,
                workers=put(state.workers, worker, committed))
        elif group.phase == "committed":
            successes = bits(group.jobs) if group.allowed else 0
            rejections = 0 if group.allowed else bits(group.jobs)
            yield label + ":deliver_committed_outcomes", replace(
                state, success=state.success | successes, rejected=state.rejected | rejections,
                completed=state.completed | bits(group.jobs),
                workers=put(state.workers, worker, Group()))

    shared = any(group.shared for group in state.workers)
    if state.publisher == "idle":
        yield "publisher:request_EXCLUSIVE", replace(state, publisher="waiting")
    elif state.publisher == "waiting" and not shared:
        yield "publisher:acquire_EXCLUSIVE_and_persist_halt", replace(
            state, publisher="exclusive0", halted=True, publishing=True)
    elif state.publisher == "exclusive0":
        yield "publisher:fanout_shard0", replace(state, publisher="exclusive1", markets=(1, 0))
    elif state.publisher == "exclusive1":
        yield "publisher:fanout_shard1", replace(state, publisher="exclusive2", markets=(1, 1))
    elif state.publisher == "exclusive2":
        yield "publisher:commit_barrier_and_release_EXCLUSIVE", replace(
            state, publisher="paused", generation=1, publishing=False)
    elif state.publisher == "paused":
        yield "operator:request_explicit_activation", replace(state, publisher="activate_wait")
    elif state.publisher == "activate_wait" and not shared:
        yield "operator:acquire_EXCLUSIVE_for_activation", replace(state, publisher="activate")
    elif state.publisher == "activate":
        yield "operator:validate_all_markets_and_activate", replace(
            state, publisher="done", halted=False)


@dataclass(frozen=True)
class Retry:
    phase: str = "idle"
    attempt: int = 0
    durable: int = 0
    commit_witness: int = 0
    staged: int = 0
    acknowledged: bool = False
    current_success: bool = False


def retry_violation(state):
    if state.durable != state.commit_witness:
        return "financial state differs from the successful atomic COMMIT witness"
    if state.durable not in (0, 1):
        return "retry of the same immutable business ID duplicated its reservation"
    if state.current_success and state.phase != "committed":
        return "a retry Future succeeded before its transaction committed"
    if state.acknowledged and state.durable != 1:
        return "a client-observed success did not survive process restart"
    return None


def rollback(state):
    return replace(state, phase="idle", staged=state.durable, current_success=False)


def retry_next(state, mutant=None):
    if state.phase == "idle" and state.attempt < 2:
        yield "begin_original_ID" if not state.attempt else "retry_same_ID_and_content", replace(
            state, phase="running", attempt=state.attempt + 1,
            staged=state.durable, current_success=False)
    if state.phase == "running":
        value = 1
        action = "stage_first_reservation" if not state.durable else "read_immutable_idempotent_receipt"
        if mutant == "retry_duplicate_reservation" and state.durable:
            value = state.durable + 1
            action = "BROKEN_replay_reserves_again"
        yield action, replace(state, phase="ready", staged=value)
        yield "process_exit_before_staging", rollback(state)
    if state.phase == "ready":
        yield "process_exit_before_COMMIT", rollback(state)
        yield "COMMIT_failure_and_rollback", rollback(state)
        yield "atomic_COMMIT", replace(state, phase="committed", durable=state.staged,
                                        commit_witness=state.staged)
        if mutant == "retry_future_before_commit":
            yield "publish_success_BEFORE_COMMIT", replace(state, current_success=True, acknowledged=True)
        if mutant == "rollback_leaks_reservation":
            yield "COMMIT_failure_but_write_leaks", replace(state, phase="idle", durable=state.staged)
    if state.phase == "committed":
        yield "process_exit_after_COMMIT_or_lost_response", rollback(state)
        if not state.current_success:
            yield "deliver_committed_success", replace(state, current_success=True, acknowledged=True)
        if mutant == "crash_loses_confirmed_commit" and state.acknowledged:
            yield "BROKEN_restart_loses_durable_commit", replace(
                state, phase="idle", durable=0, commit_witness=0, current_success=False)


def explore(initial, transitions, invariant, mutant=None):
    pending = deque([initial])
    previous = {initial: None}
    edges, terminals = 0, 0
    while pending:
        state = pending.popleft()
        failure = invariant(state)
        if failure:
            trace = []
            current = state
            while previous[current] is not None:
                parent, action = previous[current]
                trace.append({"action": action, "state": asdict(current)})
                current = parent
            return {"result": "counterexample", "reachable_states": len(previous),
                    "violation": failure, "trace": list(reversed(trace))}
        successors = list(transitions(state, mutant))
        if not successors:
            terminals += 1
        for action, successor in successors:
            edges += 1
            if successor not in previous:
                previous[successor] = state, action
                pending.append(successor)
    return {"result": "invariants_hold", "reachable_states": len(previous),
            "explored_transitions": edges, "terminal_states": terminals}


def main():
    scheduling_mutants = ("overlapping_shard_groups", "account_fifo_overtake",
                          "future_before_commit", "release_shared_before_commit")
    retry_mutants = ("retry_duplicate_reservation", "retry_future_before_commit",
                     "rollback_leaks_reservation", "crash_loses_confirmed_commit")
    scheduling = {"safe": explore(Schedule(), schedule_next, schedule_violation)}
    scheduling.update({"unsafe_" + name: explore(Schedule(), schedule_next, schedule_violation, name)
                       for name in scheduling_mutants})
    retry = {"safe": explore(Retry(), retry_next, retry_violation)}
    retry.update({"unsafe_" + name: explore(Retry(), retry_next, retry_violation, name)
                  for name in retry_mutants})
    report = {
        "model_source_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
        "python_version": platform.python_version(),
        "scheduler_and_market_barrier": scheduling,
        "crash_retry_idempotency": retry,
        "bounds": {"shards": 2, "workers": WORKERS, "commands": 3,
                   "accounts": 2, "max_group_size": MAX_GROUP,
                   "market_publications": 1, "explicit_activations": 1,
                   "retry_business_IDs": 1, "max_attempts_per_ID": 2},
        "assumptions": ["one adapter owns its FIFO queue and active-shard set",
            "cooperating writers share a host-local shared/exclusive barrier",
            "each shard transaction COMMIT is atomic and durable",
            "retry preserves the original ID and immutable content",
            "scheduler and crash models are separate safety abstractions"],
        "not_verified": ["runtime/model equivalence or a composition proof",
            "global FIFO across adapters, synchronous callers or process restarts",
            "liveness, starvation freedom or bounded lock wait",
            "persistent queues, cancellation, SAVEPOINT business-error classification",
            "physical fsync/power loss, HA, replication or distributed fencing",
            "financial formulas, matching or arbitrary queue/portfolio size"],
    }
    print(json.dumps(report, indent=2))
    safe = (scheduling["safe"]["result"] == "invariants_hold"
            and retry["safe"]["result"] == "invariants_hold")
    mutants_detected = (all(scheduling["unsafe_" + name]["result"] == "counterexample" for name in scheduling_mutants)
                        and all(retry["unsafe_" + name]["result"] == "counterexample" for name in retry_mutants))
    return 0 if safe and mutants_detected else 1


if __name__ == "__main__":
    raise SystemExit(main())
