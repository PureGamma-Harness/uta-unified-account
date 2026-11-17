"""Independent finite specifications for a proposed rolling market policy.

No UTA imports, SQLite, subprocesses, load, or financial arithmetic.  These
graphs are intentionally separate; this is not a refinement/composition proof.
"""
from collections import deque
from dataclasses import asdict, dataclass, replace
import json


LIMIT = 100_000


@dataclass(frozen=True)
class Replica:
    pointer: int = 0
    archive: int = 1
    receipts: int = 1
    observed: int = 1
    life: int = 0  # 0: first owner alive; 1: dead; 2: replacement alive


@dataclass(frozen=True)
class Delivery:
    authorized: int = 0
    replicas: tuple = (Replica(), Replica())
    stale_commit: bool = False


DELIVERY_MUTATIONS = {
    "pointer_without_archive_receipt": "atomic_install",
    "delayed_delivery_regresses_pointer": "monotone_pointer",
    "delivery_is_success_ack": "ack_requires_durable_receipt",
    "old_generation_commits_after_restart": "current_writer_generation",
}


def delivery_invariants(state):
    errors = []
    if state.stale_commit:
        errors.append("current_writer_generation")
    for replica in state.replicas:
        if (replica.archive != replica.receipts
                or not replica.archive & (1 << replica.pointer)):
            errors.append("atomic_install")
        if replica.pointer != replica.archive.bit_length() - 1:
            errors.append("monotone_pointer")
        if replica.observed & ~replica.receipts:
            errors.append("ack_requires_durable_receipt")
        if replica.archive >> (state.authorized + 1):
            errors.append("install_requires_authorization")
    return tuple(sorted(set(errors)))


def delivery_edges(state, mutation=""):
    if state.authorized < 2:
        yield "authorize_child_" + str(state.authorized + 1), replace(
            state, authorized=state.authorized + 1)
    for index, replica in enumerate(state.replicas):
        def changed(new_replica, **fields):
            replicas = list(state.replicas)
            replicas[index] = new_replica
            return replace(state, replicas=tuple(replicas), **fields)

        if replica.life == 0:
            yield f"worker_{index}_dies", changed(replace(replica, life=1))
        elif replica.life == 1:
            yield f"worker_{index}_recovers_with_new_generation", changed(
                replace(replica, life=2))
        # A read-only durable outcome query does not require a live worker.
        for epoch in range(1, state.authorized + 1):
            bit = 1 << epoch
            if not replica.observed & bit and (
                    replica.receipts & bit or mutation == "delivery_is_success_ack"):
                yield f"observe_success_{epoch}_on_{index}", changed(
                    replace(replica, observed=replica.observed | bit))
        if replica.life == 1:
            continue
        for epoch in range(1, state.authorized + 1):
            bit = 1 << epoch
            if epoch > replica.pointer:
                installed = replace(replica, pointer=epoch,
                                    archive=replica.archive | bit,
                                    receipts=replica.receipts | bit)
                if mutation == "pointer_without_archive_receipt":
                    installed = replace(replica, pointer=epoch)
                yield f"install_{epoch}_on_{index}_ack_unknown", changed(installed)
                if replica.life == 2 and mutation == "old_generation_commits_after_restart":
                    yield f"old_token_installs_{epoch}_on_{index}", changed(
                        installed, stale_commit=True)
            elif epoch < replica.pointer and mutation == "delayed_delivery_regresses_pointer":
                yield f"delayed_{epoch}_regresses_{index}", changed(
                    replace(replica, pointer=epoch))
            else:
                # A duplicate delivery/query has no financial/install effect.
                yield f"replay_{epoch}_on_{index}", state


@dataclass(frozen=True)
class Checkpoint:
    now: int = 0
    authorized: int = 0
    pointer: int = 0
    open: bool = True
    selected: int = -1
    done: bool = False
    # Immutable witness: quote, audit ID, time, global-open, authorized head.
    accepted: tuple = ()


CHECKPOINT_MUTATIONS = {
    "fresh_only_at_entry": "fresh_at_final_checkpoint",
    "release_shared_gate_before_commit": "hard_barrier_excludes_commit",
    "replace_pointer_during_decision": "decision_snapshot_is_pinned",
}


def fresh(epoch, now):
    # Abstract observed_at(epoch)=epoch, TTL=1, future tolerance=1.
    return -1 <= now - epoch <= 1


def checkpoint_invariants(state):
    if not state.accepted:
        return ()
    quote, audit_id, checked_at, was_open, authorized = state.accepted
    errors = []
    if not fresh(quote, checked_at):
        errors.append("fresh_at_final_checkpoint")
    if not was_open:
        errors.append("hard_barrier_excludes_commit")
    if quote != audit_id:
        errors.append("decision_snapshot_is_pinned")
    if quote > authorized:
        errors.append("decision_requires_authorized_snapshot")
    return tuple(errors)


def checkpoint_edges(state, mutation=""):
    if state.now < 3:
        yield "clock_advances", replace(state, now=state.now + 1)
    active = state.selected >= 0
    if state.authorized == 0 and not active:
        yield "authorize_child_1_without_freeze", replace(state, authorized=1)
    if state.open and not state.done and not active and fresh(state.pointer, state.now):
        yield "begin_decision_pin_local_snapshot_and_shared_gate", replace(
            state, selected=state.pointer)
    if state.authorized == 1 and state.pointer == 0 and (
            not active or mutation == "replace_pointer_during_decision"):
        yield "install_authorized_child_1", replace(state, pointer=1)
    if state.open and (not active or mutation == "release_shared_gate_before_commit"):
        yield "hard_freeze_durable", replace(state, open=False)
    if active:
        yield "rollback_or_worker_death", replace(state, selected=-1, done=True)
        valid_age = fresh(state.selected, state.now) or mutation == "fresh_only_at_entry"
        valid_gate = state.open or mutation == "release_shared_gate_before_commit"
        if valid_age and valid_gate:
            # This action is the last validation boundary, NOT a model of all
            # wall-clock time spent inside SQLite COMMIT/fsync afterwards.
            yield "final_checkpoint_and_abstract_commit", replace(
                state, selected=-1, done=True,
                accepted=(state.selected, state.pointer, state.now, state.open, state.authorized))


@dataclass(frozen=True)
class HardBarrier:
    global_epoch: int = 0
    open: bool = True
    installed_parent: tuple = (0, 0)
    observed_parent: tuple = (0, 0)
    child_witness: tuple = ()  # (child parent, global parent at authorization)


BARRIER_MUTATIONS = {
    "thaw_after_one_shard": "thaw_requires_complete_new_parent",
    "authorize_old_parent_after_config_change": "child_requires_current_parent",
}


def barrier_invariants(state):
    errors = []
    if state.open and (state.installed_parent != (state.global_epoch,) * 2
                       or state.observed_parent != (state.global_epoch,) * 2):
        errors.append("thaw_requires_complete_new_parent")
    if state.child_witness and state.child_witness[0] != state.child_witness[1]:
        errors.append("child_requires_current_parent")
    return tuple(errors)


def barrier_edges(state, mutation=""):
    if state.open and state.child_witness != (state.global_epoch,) * 2:
        yield "authorize_child_of_current_open_parent", replace(
            state, child_witness=(state.global_epoch,) * 2)
    if state.global_epoch == 0:
        yield "hard_freeze_and_create_config_parent_1", HardBarrier(
            global_epoch=1, open=False, child_witness=state.child_witness)
    else:
        for index in range(2):
            if state.installed_parent[index] == 0:
                parents = list(state.installed_parent)
                parents[index] = 1
                yield f"install_config_parent_1_on_{index}", replace(
                    state, installed_parent=tuple(parents))
            if (state.installed_parent[index] == 1
                    and state.observed_parent[index] == 0):
                parents = list(state.observed_parent)
                parents[index] = 1
                yield f"verify_parent_1_receipt_and_payload_on_{index}", replace(
                    state, observed_parent=tuple(parents))
        full = state.installed_parent == state.observed_parent == (1, 1)
        partial = 1 in state.observed_parent
        if not state.open and (full or mutation == "thaw_after_one_shard" and partial):
            yield "explicit_thaw", replace(state, open=True)
        if mutation == "authorize_old_parent_after_config_change":
            yield "authorize_child_of_retired_parent_0", replace(
                state, child_witness=(0, state.global_epoch))


@dataclass(frozen=True)
class PhysicalGap:
    now: int = 0
    checked: bool = False
    committed_at: int = -1


def physical_gap_edges(state, mutation=""):
    if state.now < 2:
        yield "os_or_io_delay", replace(state, now=state.now + 1)
    if not state.checked and state.committed_at < 0 and fresh(0, state.now):
        yield "last_userland_freshness_check_then_enter_sqlite_commit", replace(
            state, checked=True)
    if state.checked and state.committed_at < 0:
        yield "physical_durable_commit", replace(state, committed_at=state.now)


def physical_gap_invariants(state):
    return ("physical_commit_age_unbounded",) if state.committed_at >= 0 and not fresh(0, state.committed_at) else ()


def trace_to(state, parents):
    trace = []
    while parents[state] is not None:
        previous, action = parents[state]
        trace.append({"action": action, "state": plain(state)})
        state = previous
    trace.append({"action": "initial", "state": plain(state)})
    return list(reversed(trace))


def plain(state):
    return json.loads(json.dumps(asdict(state)))


def explore(initial, edges, invariants, mutation="", limit=LIMIT):
    allowed = {delivery_edges: DELIVERY_MUTATIONS,
               checkpoint_edges: CHECKPOINT_MUTATIONS,
               barrier_edges: BARRIER_MUTATIONS,
               physical_gap_edges: {}}
    if edges not in allowed or mutation and mutation not in allowed[edges]:
        raise ValueError("unknown model or mutation")
    if limit < 1:
        raise ValueError("state limit must be positive")
    parents = {initial: None}
    queue = deque([initial])
    transitions = 0
    coverage = {"divergent_shards": 0, "committed_ack_unknown": 0,
                "recovered_with_durable_history": 0, "accepted_old_local_quote": 0,
                "current_parent_child_authorized": 0}
    while queue:
        current = queue.popleft()
        errors = invariants(current)
        if errors:
            return {"complete": False, "states": len(parents), "transitions": transitions,
                    "violations": list(errors), "counterexample": trace_to(current, parents)}
        if isinstance(current, Delivery):
            coverage["divergent_shards"] += int(current.replicas[0].pointer != current.replicas[1].pointer)
            coverage["committed_ack_unknown"] += int(any(
                r.receipts & ~r.observed for r in current.replicas))
            coverage["recovered_with_durable_history"] += int(any(
                r.life == 2 and r.pointer > 0 for r in current.replicas))
        if isinstance(current, Checkpoint):
            coverage["accepted_old_local_quote"] += int(bool(
                current.accepted and current.accepted[0] == 0 and current.accepted[4] == 1))
        if isinstance(current, HardBarrier):
            coverage["current_parent_child_authorized"] += int(bool(current.child_witness))
        for action, successor in edges(current, mutation):
            transitions += 1
            if successor not in parents:
                if len(parents) >= limit:
                    raise RuntimeError("incomplete exploration: state limit exceeded")
                parents[successor] = current, action
                queue.append(successor)
    return {"complete": True, "states": len(parents), "transitions": transitions,
            "violations": [], "coverage": coverage}


def replay(initial, edges, invariants, mutation, counterexample):
    """Reject a counterexample unless every named edge exists in that variant."""
    current = initial
    if counterexample[0] != {"action": "initial", "state": plain(initial)}:
        return False
    for item in counterexample[1:]:
        successors = [successor for action, successor in edges(current, mutation)
                      if action == item["action"] and plain(successor) == item["state"]]
        if len(successors) != 1 or invariants(current):
            return False
        current = successors[0]
    return bool(invariants(current))


MODELS = {
    "delivery": (Delivery, delivery_edges, delivery_invariants, DELIVERY_MUTATIONS),
    "checkpoint": (Checkpoint, checkpoint_edges, checkpoint_invariants, CHECKPOINT_MUTATIONS),
    "hard_barrier": (HardBarrier, barrier_edges, barrier_invariants, BARRIER_MUTATIONS),
}


def run():
    result = {"scope": "independent bounded specifications; runtime unchanged",
              "composition_proven": False, "runtime_refinement_proven": False,
              "physical_commit_age_proven": False, "production_approved": False,
              "bounds": {"shards": 2, "ordinary_children": 2, "owners_per_shard": 2,
                         "decisions": 1, "clock_ticks": 3, "config_transitions": 1},
              "models": {}, "negative_controls": {}}
    for name, (factory, edges, invariants, mutations) in MODELS.items():
        baseline = explore(factory(), edges, invariants)
        if not baseline["complete"] or baseline["violations"]:
            raise AssertionError((name, baseline))
        result["models"][name] = baseline
        for mutation, target in mutations.items():
            broken = explore(factory(), edges, invariants, mutation)
            if (target not in broken["violations"]
                    or not replay(factory(), edges, invariants, mutation, broken["counterexample"])):
                raise AssertionError((mutation, broken))
            broken["expected_violation"] = target
            broken["replayed"] = True
            result["negative_controls"][mutation] = broken
    gap = explore(PhysicalGap(), physical_gap_edges, physical_gap_invariants)
    if "physical_commit_age_unbounded" not in gap["violations"]:
        raise AssertionError("physical COMMIT delay limitation was hidden")
    result["physical_commit_boundary_counterexample"] = gap
    result["passed"] = True
    return result


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))
