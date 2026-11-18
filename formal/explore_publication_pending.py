"""Independent bounded publication/activation/pending-command specification.

Only stdlib data structures; no runtime imports, files, SQL, clocks or actors.
This is a proposed protocol model, not a refinement or liveness proof.
"""
from collections import deque
from dataclasses import asdict, dataclass, replace
import json


STATE_LIMIT = 25_000


@dataclass(frozen=True)
class State:
    phase: str = "idle"
    halted: bool = False
    publishing: bool = False
    pending: bool = False
    operator_halt: bool = False
    operator_revision: int = 0
    publication_revision: int = -1
    activation_revision: int = -1
    installed: tuple = (0, 0)
    observed: tuple = (0, 0)
    market: int = 0
    fresh: bool = True
    lease: bool = True
    fatal_observed: bool = False
    recovered: bool = False
    command: str = "PENDING"
    attempts: int = 0
    reservations: int = 0
    admission_witness: tuple = ()
    activation_witness: tuple = ()


MUTATIONS = {
    "exception_without_freeze": "fatal_exit_clears_temporary_pause",
    "late_publication_revives_pause": "operator_halt_dominates_old_control",
    "late_activation_reopens_gate": "operator_halt_dominates_old_control",
    "partial_fanout_visible": "visible_market_has_both_durable_receipts",
    "paused_poll_charges_attempt": "paused_pending_command_is_unchanged",
    "duplicate_admission_reserves_twice": "one_CID_reserves_once",
    "activation_ignores_stale_quote": "activation_has_final_freshness_check",
    "restart_forgets_pending": "temporary_pause_survives_restart",
}


def invariants(s):
    errors = []
    if s.operator_halt and (not s.halted or s.pending):
        errors.append("operator_halt_dominates_old_control")
    if s.fatal_observed and (not s.halted or s.pending):
        errors.append("fatal_exit_clears_temporary_pause")
    if s.market == 1 and (s.installed != (1, 1) or s.observed != (1, 1)):
        errors.append("visible_market_has_both_durable_receipts")
    if s.command == "PENDING" and s.attempts != 0:
        errors.append("paused_pending_command_is_unchanged")
    if s.reservations != int(s.command == "SUCCEEDED"):
        errors.append("one_CID_reserves_once")
    if (s.phase in ("publishing", "gap", "validating")
            and not s.operator_halt and not s.fatal_observed and not s.pending):
        errors.append("temporary_pause_survives_restart")
    if s.admission_witness:
        halted, publishing, pending, operator, fresh, lease, fatal, market, installed, observed = s.admission_witness
        if (halted or publishing or pending or operator or not fresh or not lease
                or fatal or installed != (market, market) or observed != (market, market)):
            errors.append("admission_uses_complete_live_authority")
    if s.activation_witness:
        fresh, lease, fatal, captured, current, operator = s.activation_witness
        if not fresh or not lease or fatal:
            errors.append("activation_has_final_freshness_check")
        if captured != current or operator:
            errors.append("operator_halt_dominates_old_control")
    return tuple(sorted(set(errors)))


def edges(s, mutation=""):
    if not s.operator_halt:
        yield "operator_halt_durably_clears_pause", replace(
            s, operator_halt=True, operator_revision=1, halted=True, pending=False)
    if s.fresh:
        yield "quote_expires", replace(s, fresh=False)
    if s.lease:
        yield "writer_lease_expires", replace(s, lease=False)
    if not s.recovered:
        pending = False if mutation == "restart_forgets_pending" else s.pending
        yield "restart_from_durable_control_and_original_CID", replace(
            s, recovered=True, pending=pending)
    if s.phase == "idle":
        yield "begin_one_publication", replace(
            s, phase="publishing", halted=True, publishing=True,
            pending=not s.operator_halt, publication_revision=s.operator_revision)
    if s.phase == "publishing":
        for index in range(2):
            if s.installed[index] == 0:
                installed = list(s.installed)
                installed[index] = 1
                yield "install_shard_" + str(index), replace(s, installed=tuple(installed))
            if s.installed[index] == 1 and s.observed[index] == 0:
                observed = list(s.observed)
                observed[index] = 1
                yield "query_durable_receipt_shard_" + str(index), replace(s, observed=tuple(observed))
        complete = s.installed == s.observed == (1, 1)
        if complete or mutation == "partial_fanout_visible" and 1 in s.observed:
            pending = (s.publication_revision == s.operator_revision and not s.operator_halt)
            if mutation == "late_publication_revives_pause":
                pending = True
            yield "complete_publication_keep_activation_gap", replace(
                s, phase="gap", publishing=False, market=1, pending=pending)
    if s.phase == "gap" and not s.operator_halt and s.pending:
        yield "begin_activation_capture_operator_revision", replace(
            s, phase="validating", activation_revision=s.operator_revision)
    if s.phase == "validating":
        # This is a caught fatal validation result, not the unobserved moment
        # when a local file becomes corrupt.  Its state transition is atomic.
        yield "fatal_validation_exit", replace(
            s, phase="failed", halted=True, fatal_observed=True,
            pending=s.pending if mutation == "exception_without_freeze" else False)
        if not s.fresh or not s.lease:
            yield "retryable_age_or_lease_failure_remains_closed", replace(s, phase="gap")
        current_intent = (s.activation_revision == s.operator_revision and not s.operator_halt)
        acceptable_quote = s.fresh or mutation == "activation_ignores_stale_quote"
        if s.lease and acceptable_quote and (current_intent or mutation == "late_activation_reopens_gate"):
            yield "last_validation_and_activate_atomically", replace(
                s, phase="complete", halted=False, pending=False,
                activation_witness=(s.fresh, s.lease, s.fatal_observed,
                                    s.activation_revision, s.operator_revision, s.operator_halt))
    if s.command == "PENDING":
        if s.pending:
            if mutation == "paused_poll_charges_attempt":
                yield "poll_paused_CID", replace(s, attempts=1)
            else:
                yield "poll_paused_CID", s
        elif s.halted or s.publishing:
            yield "hard_halt_rejects_CID_once", replace(s, command="REJECTED", attempts=1)
        elif s.fresh and s.lease and not s.fatal_observed:
            yield "last_checkpoint_and_one_CID_reservation", replace(
                s, command="SUCCEEDED", attempts=1, reservations=1,
                admission_witness=(s.halted, s.publishing, s.pending, s.operator_halt,
                                   s.fresh, s.lease, s.fatal_observed,
                                   s.market, s.installed, s.observed))
    else:
        yield "duplicate_CID_query", (replace(s, reservations=2)
            if s.command == "SUCCEEDED" and mutation == "duplicate_admission_reserves_twice" else s)


def plain(state):
    # Serialized counterexamples must replay after a JSON round trip as well.
    return json.loads(json.dumps(asdict(state)))


def trace(state, parents):
    result = []
    while parents[state] is not None:
        previous, action = parents[state]
        result.append({"action": action, "state": plain(state)})
        state = previous
    result.append({"action": "initial", "state": plain(state)})
    return list(reversed(result))


def explore(mutation=""):
    if mutation and mutation not in MUTATIONS:
        raise ValueError("unknown closed model variant")
    initial = State()
    parents, queue, transitions = {initial: None}, deque([initial]), 0
    coverage = {"paused_CIDs": 0, "activation_gap": 0, "halted_during_publication": 0,
                "inflight_activation_halt": 0, "recovered_pause": 0,
                "admitted": 0, "fatal_observed": 0}
    while queue:
        current = queue.popleft()
        violations = invariants(current)
        if violations:
            return {"complete": False, "states": len(parents), "transitions": transitions,
                    "violations": list(violations), "counterexample": trace(current, parents)}
        coverage["paused_CIDs"] += int(current.pending and current.command == "PENDING")
        coverage["activation_gap"] += int(current.phase == "gap" and current.pending)
        coverage["halted_during_publication"] += int(current.publishing and current.operator_halt)
        coverage["inflight_activation_halt"] += int(current.phase == "validating" and current.operator_halt)
        coverage["recovered_pause"] += int(current.recovered and current.pending)
        coverage["admitted"] += int(current.command == "SUCCEEDED")
        coverage["fatal_observed"] += int(current.fatal_observed)
        for action, successor in edges(current, mutation):
            transitions += 1
            if successor not in parents:
                if len(parents) >= STATE_LIMIT:
                    raise RuntimeError("INCOMPLETE: fixed state bound exceeded")
                parents[successor] = current, action
                queue.append(successor)
    return {"complete": True, "states": len(parents), "transitions": transitions,
            "violations": [], "coverage": coverage}


def replay(mutation, counterexample):
    current = State()
    if counterexample[0] != {"action": "initial", "state": plain(current)}:
        raise AssertionError("counterexample has a different initial state")
    for item in counterexample[1:]:
        candidates = [successor for action, successor in edges(current, mutation)
                      if action == item["action"] and plain(successor) == item["state"]]
        if len(candidates) != 1 or invariants(current):
            raise AssertionError("counterexample edge is not uniquely replayable")
        current = candidates[0]
    if MUTATIONS[mutation] not in invariants(current):
        raise AssertionError("counterexample misses its required invariant")


def run():
    baseline = explore()
    if not baseline["complete"] or baseline["violations"] or not all(baseline["coverage"].values()):
        raise AssertionError("baseline incomplete, unsafe or missing required event coverage")
    controls = {}
    for mutation, invariant in MUTATIONS.items():
        result = explore(mutation)
        if invariant not in result["violations"]:
            raise AssertionError("negative control did not expose " + invariant)
        replay(mutation, json.loads(json.dumps(result["counterexample"])))
        controls[mutation] = {**result, "required_violation": invariant, "replayed": True}
    return {"kind": "INDEPENDENT_BOUNDED_PUBLICATION_PENDING_DESIGN_MODEL",
            "bounds": {"shards": 2, "publications": 1, "operator_halts": 1,
                       "restarts": 1, "CIDs": 1, "state_limit_each_variant": STATE_LIMIT},
            "baseline": baseline, "negative_controls": controls, "passed": True,
            "runtime_imports": 0, "SQL_process_threads_network": 0,
            "runtime_refinement_proven": False, "liveness_proven": False,
            "physical_fsync_age_proven": False, "production_approved": False}


if __name__ == "__main__":
    print(json.dumps(run(), sort_keys=True, indent=2))
