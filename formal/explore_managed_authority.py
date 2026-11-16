"""Two independent bounded safety models of the managed local protocol.

No production module, reference calculator or implementation model is imported.
The two graphs are deliberately NOT a composed/refinement proof. Atomic local
commits, durable storage and reliable identity primitives are explicit premises.
"""
from collections import Counter, deque
from dataclasses import asdict, dataclass, replace
import json


HALT, PUBLISHING, ACTIVE = 'HALT', 'PUBLISHING', 'ACTIVE'
OLD_PARENT, NO_PARENT, NEW_PARENT = 0, 1, 2
RUNNING, STOPPED, EXITED, REUSED_PID = 0, 1, 2, 3
PENDING, SUCCEEDED, REJECTED = 0, 1, 2


def put(values, index, value):
    return values[:index] + (value,) + values[index + 1:]


@dataclass(frozen=True)
class Owner:
    old_process: int = RUNNING
    old_lease: bool = True
    new_started: bool = False
    new_lease: bool = False

    @property
    def current_generation(self):
        return 2 if self.new_started else 1

    @property
    def current_lease(self):
        return self.new_lease if self.new_started else self.old_lease


@dataclass(frozen=True)
class RiskCommit:
    shard: int
    token_generation: int
    token_birth: int
    current_generation: int
    current_birth: int
    lease_valid: bool
    mode: str
    target: int
    prepared_market: int
    markets: tuple[int, int]
    acknowledgements: int


@dataclass(frozen=True)
class Kill:
    shard: int
    registered_birth: int
    actual_birth: int
    lease_valid: bool


@dataclass(frozen=True)
class Authority:
    parent: int = OLD_PARENT
    owners: tuple[Owner, Owner] = (Owner(), Owner())
    mode: str = HALT
    target: int = 0
    markets: tuple[int, int] = (0, 0)
    acknowledgements: int = 3
    prepared_actor: int = -1  # actor = 2*shard + generation-1.
    prepared_market: int = 0
    shared_gate: bool = False
    commit: RiskCommit | None = None
    last_kill: Kill | None = None


AUTHORITY_MUTANTS = (
    'steal_live_lease', 'check_current_lease_without_token_identity', 'skip_commit_expiry',
    'kill_reused_pid_without_birth', 'kill_orphan_before_lease_expiry',
    'activate_partial_fanout', 'risk_commit_using_only_local_market', 'release_shared_before_commit',
)


def actor_parts(actor):
    return actor // 2, actor % 2 + 1


def actor_running(state, actor):
    shard, generation = actor_parts(actor)
    owner = state.owners[shard]
    return owner.old_process == RUNNING if generation == 1 else owner.new_started


def token_matches(state, actor):
    shard, generation = actor_parts(actor)
    owner = state.owners[shard]
    return actor_running(state, actor) and generation == owner.current_generation


def publication_complete(state):
    return state.markets == (state.target, state.target) and state.acknowledgements == 3


def clear_actor(state, shard):
    if state.prepared_actor >= 0 and actor_parts(state.prepared_actor) == (shard, 1):
        return replace(state, prepared_actor=-1, shared_gate=False)
    return state


def authority_next(state, mutant=None):
    if state.parent == OLD_PARENT:
        yield 'coordinator_dies', replace(state, parent=NO_PARENT)
    elif state.parent == NO_PARENT:
        yield 'new_coordinator_takes_supervisor_lock', replace(state, parent=NEW_PARENT)
    for shard, owner in enumerate(state.owners):
        prefix = 'shard' + str(shard) + ':'
        if owner.old_lease:
            yield prefix + 'old_lease_reaches_expiry', replace(state,
                owners=put(state.owners, shard, replace(owner, old_lease=False)))
        if owner.new_lease:
            yield prefix + 'new_lease_reaches_expiry', replace(state,
                owners=put(state.owners, shard, replace(owner, new_lease=False)))
        if owner.old_process == RUNNING:
            yield prefix + 'SIGSTOP_registered_old_worker', replace(state,
                owners=put(state.owners, shard, replace(owner, old_process=STOPPED)))
            if state.parent != OLD_PARENT:
                exited = clear_actor(state, shard)
                yield prefix + 'old_worker_observes_parent_death_and_exits', replace(exited,
                    owners=put(state.owners, shard, replace(owner, old_process=EXITED)))
        if owner.old_process == STOPPED:
            yield prefix + 'old_worker_resumes', replace(state,
                owners=put(state.owners, shard, replace(owner, old_process=RUNNING)))
        if owner.old_process == EXITED:
            yield prefix + 'same_numeric_PID_reused_with_different_birth', replace(state,
                owners=put(state.owners, shard, replace(owner, old_process=REUSED_PID)))
        if state.parent == NEW_PARENT and owner.old_process in (RUNNING, STOPPED, REUSED_PID):
            identity_ok = owner.old_process != REUSED_PID
            expired = not owner.old_lease
            permitted = identity_ok and expired
            if mutant == 'kill_reused_pid_without_birth' and expired:
                permitted = True
            if mutant == 'kill_orphan_before_lease_expiry' and identity_ok:
                permitted = True
            if permitted:
                killed = clear_actor(state, shard)
                witness = Kill(shard, 1, 9 if owner.old_process == REUSED_PID else 1, owner.old_lease)
                yield prefix + 'pidfd_kill_after_rechecking_registered_birth_and_expiry', replace(killed,
                    owners=put(state.owners, shard, replace(owner, old_process=EXITED)), last_kill=witness)
        if state.parent == NEW_PARENT and not owner.new_started:
            if not owner.old_lease or mutant == 'steal_live_lease':
                yield prefix + 'grant_generation2_to_new_PID_birth', replace(state,
                    owners=put(state.owners, shard, replace(owner, new_started=True, new_lease=True)))
    if state.parent != NO_PARENT:
        if state.mode == ACTIVE and not state.shared_gate:
            yield 'persist_global_HALT', replace(state, mode=HALT)
        if state.target == 0 and not state.shared_gate:
            yield 'exclusive_begin_new_market_generation', replace(state, mode=PUBLISHING,
                target=1, acknowledgements=0)
        if state.mode == PUBLISHING:
            for shard, owner in enumerate(state.owners):
                current_actor = 2 * shard + owner.current_generation - 1
                if token_matches(state, current_actor) and owner.current_lease and state.markets[shard] != state.target:
                    yield 'shard' + str(shard) + ':commit_actual_market_payload', replace(state,
                        markets=put(state.markets, shard, state.target))
                if state.markets[shard] == state.target and not state.acknowledgements & (1 << shard):
                    yield 'collect_persisted_market_receipt_shard' + str(shard), replace(state,
                        acknowledgements=state.acknowledgements | (1 << shard))
            if publication_complete(state):
                yield 'complete_fanout_but_remain_HALTED', replace(state, mode=HALT)
            elif mutant == 'activate_partial_fanout' and state.acknowledgements in (1, 2):
                yield 'unsafe_activate_after_only_one_shard_receipt', replace(state, mode=ACTIVE)
        if state.mode == HALT and publication_complete(state):
            yield 'explicit_activate_complete_current_market', replace(state, mode=ACTIVE)
    if state.prepared_actor < 0 and state.commit is None:
        for actor in range(4):
            shard, _ = actor_parts(actor)
            owner = state.owners[shard]
            gate_ok = state.mode == ACTIVE and publication_complete(state)
            if mutant == 'risk_commit_using_only_local_market':
                gate_ok = state.mode in (ACTIVE, PUBLISHING) and state.markets[shard] == state.target
            if token_matches(state, actor) and owner.current_lease and gate_ok:
                yield 'actor' + str(actor) + ':hold_SHARED_and_prepare_risk_command', replace(state,
                    prepared_actor=actor, prepared_market=state.markets[shard], shared_gate=True)
    if state.prepared_actor >= 0:
        actor = state.prepared_actor
        shard, generation = actor_parts(actor)
        owner = state.owners[shard]
        yield 'rollback_uncommitted_risk_work', replace(state, prepared_actor=-1, shared_gate=False)
        if mutant == 'release_shared_before_commit' and state.shared_gate:
            yield 'unsafe_release_SHARED_before_commit', replace(state, shared_gate=False)
        identity_ok = token_matches(state, actor)
        if mutant == 'check_current_lease_without_token_identity':
            identity_ok = actor_running(state, actor)
        expiry_ok = owner.current_lease or mutant == 'skip_commit_expiry'
        gate_ok = (state.mode == ACTIVE and publication_complete(state)
                   and state.prepared_market == state.target)
        if mutant == 'risk_commit_using_only_local_market':
            gate_ok = state.mode in (ACTIVE, PUBLISHING) and state.markets[shard] == state.prepared_market
        if identity_ok and expiry_ok and gate_ok:
            witness = RiskCommit(shard, generation, generation, owner.current_generation,
                owner.current_generation, owner.current_lease, state.mode, state.target,
                state.prepared_market, state.markets, state.acknowledgements)
            yield 'actor' + str(actor) + ':atomic_risk_COMMIT_with_prestate_witness', replace(state,
                prepared_actor=-1, shared_gate=False, commit=witness)


def authority_violation(state):
    for shard, owner in enumerate(state.owners):
        if int(owner.old_lease) + int(owner.new_lease) > 1:
            return 'overlapping_live_writer_lease_grants_shard' + str(shard)
    if state.mode == ACTIVE and not publication_complete(state):
        return 'ACTIVE_with_incomplete_or_unacknowledged_market_fanout'
    if state.prepared_actor >= 0 and not state.shared_gate:
        return 'prepared_risk_command_released_SHARED_before_commit'
    if state.last_kill is not None:
        if state.last_kill.actual_birth != state.last_kill.registered_birth:
            return 'orphan_recovery_killed_a_reused_unrelated_PID_birth'
        if state.last_kill.lease_valid:
            return 'orphan_recovery_killed_owner_before_lease_expiry'
    if state.commit is not None:
        event = state.commit
        if (event.token_generation, event.token_birth) != (event.current_generation, event.current_birth):
            return 'stale_generation_or_PID_birth_committed_financial_risk'
        if not event.lease_valid:
            return 'expired_owner_committed_financial_risk'
        if (event.mode != ACTIVE or event.markets != (event.target, event.target)
                or event.acknowledgements != 3 or event.prepared_market != event.target):
            return 'financial_risk_committed_without_complete_current_global_barrier'
    return None


def authority_coverage(state):
    return {
        'stopped_orphan_holds_shared_gate': state.parent != OLD_PARENT and state.prepared_actor >= 0
            and actor_parts(state.prepared_actor)[1] == 1
            and state.owners[actor_parts(state.prepared_actor)[0]].old_process == STOPPED,
        'partial_fanout_remains_closed': state.mode == PUBLISHING and state.markets in ((0, 1), (1, 0)),
        'generation2_risk_commit': state.commit is not None and state.commit.token_generation == 2,
        'reused_pid_still_alive': any(owner.old_process == REUSED_PID for owner in state.owners),
        'valid_orphan_recovery': state.last_kill is not None and not state.last_kill.lease_valid
            and state.last_kill.actual_birth == state.last_kill.registered_birth,
        'new_coordinator_activated_market1': state.parent == NEW_PARENT and state.mode == ACTIVE and state.target == 1,
    }


@dataclass(frozen=True)
class Commands:
    queued: int = 0
    terminal: tuple[int, ...] = (PENDING,) * 3
    admitted: tuple[int, ...] = (0,) * 3
    admission_effects: tuple[int, ...] = (0,) * 3
    filled: tuple[int, ...] = (0,) * 3
    fill_effects: tuple[int, ...] = (0,) * 3
    position: int = 2
    liquidity_supplied: int = 1
    worker_generation: int = 1
    worker_alive: bool = True
    staged_kind: str = ''
    staged_id: int = -1
    outcome_delivered: int = 0
    fill_delivered: int = 0


COMMAND_MUTANTS = (
    'terminal_success_before_commit', 'financial_without_terminal', 'terminal_without_financial', 'repeat_original_command',
    'repeat_confirmed_fill_after_restart', 'count_unmatched_liquidation_as_filled',
    'reverse_liquidation_direction', 'overfill_order_quantity', 'skip_reduce_only_reservation',
)


def command_next(state, mutant=None):
    if state.queued < 3:
        yield 'COMMIT_intent_and_return_durably_queued_only', replace(state, queued=state.queued + 1)
    if state.worker_alive:
        yield 'worker_crashes_losing_only_uncommitted_work_and_reply', replace(state,
            worker_alive=False, staged_kind='', staged_id=-1)
    elif state.worker_generation == 1:
        yield 'restart_generation2_and_reopen_original_command_and_fill_IDs', replace(state,
            worker_generation=2, worker_alive=True)
    if state.liquidity_supplied == 1:
        yield 'real_counterparty_replenishes_second_unit_of_depth', replace(state, liquidity_supplied=2)
    if state.worker_alive and not state.staged_kind:
        for index in range(state.queued):
            if state.terminal[index] == PENDING and all(value != PENDING for value in state.terminal[:index]):
                yield 'prepare_FIFO_command' + str(index), replace(state, staged_kind='command', staged_id=index)
            elif (mutant == 'repeat_original_command' and state.terminal[index] == SUCCEEDED
                  and state.worker_generation == 2):
                yield 'unsafe_retry_original_CID_as_new_effect' + str(index), replace(state,
                    staged_kind='command', staged_id=index)
            if state.admitted[index] and state.filled[index] == 0 and sum(state.filled) < state.liquidity_supplied:
                yield 'prepare_actual_paired_fill' + str(index), replace(state, staged_kind='fill', staged_id=index)
            elif (mutant == 'repeat_confirmed_fill_after_restart' and state.filled[index]
                  and state.worker_generation == 2):
                yield 'unsafe_replay_existing_fill_ID' + str(index), replace(state, staged_kind='fill', staged_id=index)
    if state.worker_alive and state.staged_kind:
        index = state.staged_id
        if state.staged_kind == 'command':
            if mutant == 'terminal_success_before_commit':
                yield 'unsafe_publish_terminal_outcome_before_COMMIT', replace(state,
                    outcome_delivered=state.outcome_delivered | (1 << index))
            held = sum(a - f for a, f in zip(state.admitted, state.filled))
            enough = held + 1 <= state.position
            if enough or mutant == 'skip_reduce_only_reservation':
                committed = replace(state,
                    admitted=put(state.admitted, index, state.admitted[index] + 1),
                    admission_effects=put(state.admission_effects, index, state.admission_effects[index] + 1),
                    terminal=put(state.terminal, index, SUCCEEDED), staged_kind='', staged_id=-1)
                if mutant == 'financial_without_terminal':
                    committed = replace(committed, terminal=state.terminal)
                if mutant == 'terminal_without_financial':
                    committed = replace(committed, admitted=state.admitted, admission_effects=state.admission_effects)
            else:
                committed = replace(state, terminal=put(state.terminal, index, REJECTED), staged_kind='', staged_id=-1)
            yield 'COMMIT_reservation_and_immutable_command_terminal_together', committed
        else:
            if mutant == 'count_unmatched_liquidation_as_filled':
                yield 'unsafe_count_unconfirmed_instruction_as_executed', replace(state, position=state.position - 1)
            amount = 2 if mutant == 'overfill_order_quantity' else 1
            next_position = state.position + amount if mutant == 'reverse_liquidation_direction' else state.position - amount
            yield 'COMMIT_actual_match_position_and_unique_fill_receipt_together', replace(state,
                position=next_position, filled=put(state.filled, index, state.filled[index] + amount),
                fill_effects=put(state.fill_effects, index, state.fill_effects[index] + 1),
                staged_kind='', staged_id=-1)
    for index in range(state.queued):
        if state.terminal[index] != PENDING and not state.outcome_delivered & (1 << index):
            yield 'query_or_redeliver_original_command_terminal' + str(index), replace(state,
                outcome_delivered=state.outcome_delivered | (1 << index))
        if state.filled[index] and not state.fill_delivered & (1 << index):
            yield 'query_or_redeliver_original_confirmed_fill' + str(index), replace(state,
                fill_delivered=state.fill_delivered | (1 << index))


def command_violation(state):
    if any(value > 1 for value in state.admission_effects):
        return 'original_command_ID_created_financial_effect_twice'
    if any(value > 1 for value in state.fill_effects):
        return 'original_confirmed_fill_ID_settled_twice'
    if not 0 <= state.position <= 2:
        return 'liquidation_reversed_or_expanded_the_initial_position'
    if any(filled > admitted for filled, admitted in zip(state.filled, state.admitted)):
        return 'confirmed_liquidation_overfilled_its_order_quantity'
    if state.position + sum(state.filled) != 2:
        return 'unconfirmed_liquidation_changed_position_or_reversed_direction'
    if sum(state.filled) > state.liquidity_supplied:
        return 'confirmed_quantity_exceeded_actual_counterparty_depth'
    if sum(a - f for a, f in zip(state.admitted, state.filled)) > state.position:
        return 'aggregate_reduce_only_reservation_exceeded_remaining_position'
    for index, terminal in enumerate(state.terminal):
        if terminal == SUCCEEDED and state.admission_effects[index] != 1:
            return 'successful_terminal_has_no_corresponding_financial_effect'
        if state.admission_effects[index] and terminal != SUCCEEDED:
            return 'financial_reservation_has_no_same_commit_success_terminal'
        if terminal == REJECTED and (state.admitted[index] or state.admission_effects[index]):
            return 'business_rejected_command_changed_financial_state'
        if state.outcome_delivered & (1 << index) and terminal == PENDING:
            return 'accepted_outcome_was_visible_before_financial_terminal_commit'
        if index >= state.queued and terminal != PENDING:
            return 'terminal_receipt_without_a_durable_intent'
        if terminal != PENDING and PENDING in state.terminal[:index]:
            return 'account_FIFO_was_not_a_terminal_prefix'
    return None


def command_coverage(state):
    return {
        'durably_queued_without_acceptance': state.queued > 0 and not any(state.admitted),
        'committed_command_response_lost': any(value == SUCCEEDED and not state.outcome_delivered & (1 << index)
                                               for index, value in enumerate(state.terminal)),
        'committed_fill_response_lost': any(value and not state.fill_delivered & (1 << index)
                                          for index, value in enumerate(state.filled)),
        'partial_liquidation_without_depth': state.position == 1 and sum(state.filled) == state.liquidity_supplied,
        'restart_with_confirmed_partial_fill': state.worker_generation == 2 and state.position == 1,
        'confirmed_flat_terminal': state.position == 0 and sum(state.filled) == 2,
        'persisted_business_rejection': REJECTED in state.terminal,
    }


def explore(initial, next_states, violation, coverage, *, mutant=None, max_states=500000):
    """Complete BFS or explicit failure; never label a truncated graph safe."""
    queue, previous = deque([initial]), {initial: None}
    edges, reached = 0, Counter()
    while queue:
        state = queue.popleft()
        problem = violation(state)
        if problem:
            trace = []
            end = state
            while previous[state] is not None:
                before, action = previous[state]
                trace.append({'action': action, 'after': asdict(state)})
                state = before
            return {'complete': False, 'states': len(previous), 'transitions': edges,
                    'violation': problem, 'counterexample': list(reversed(trace)),
                    'violating_state': asdict(end), 'coverage': dict(reached)}
        reached.update({name: int(found) for name, found in coverage(state).items() if found})
        for action, after in next_states(state, mutant):
            edges += 1
            if after not in previous:
                if len(previous) >= max_states:
                    raise RuntimeError('state bound exhausted; this is incomplete, never a passing result')
                previous[after] = state, action
                queue.append(after)
    return {'complete': True, 'states': len(previous), 'transitions': edges,
            'violation': None, 'counterexample': [], 'coverage': dict(reached)}


def run_model(name, *, mutant=None, max_states=500000):
    if type(max_states) is not int or max_states < 1:
        raise ValueError('max_states must be a positive integer')
    if name == 'authority':
        if mutant is not None and mutant not in AUTHORITY_MUTANTS:
            raise ValueError('unknown authority mutation')
        return explore(Authority(), authority_next, authority_violation, authority_coverage,
                       mutant=mutant, max_states=max_states)
    if name == 'commands':
        if mutant is not None and mutant not in COMMAND_MUTANTS:
            raise ValueError('unknown command mutation')
        return explore(Commands(), command_next, command_violation, command_coverage,
                       mutant=mutant, max_states=max_states)
    raise ValueError('unknown bounded model')


def report():
    models = {}
    for name, variants in (('authority', AUTHORITY_MUTANTS), ('commands', COMMAND_MUTANTS)):
        safe = run_model(name)
        negative = {variant: run_model(name, mutant=variant) for variant in variants}
        models[name] = {'safe': safe, 'negative_controls': negative}
    passed = all(model['safe']['complete'] and model['safe']['violation'] is None
        and all(result['violation'] and result['counterexample'] for result in model['negative_controls'].values())
        for model in models.values())
    return {'passed': passed, 'models': models, 'composition_proven': False,
        'protocol_reference_commit': 'd5d2887626497671718edb5cf32c147b4fa3bb27',
        'bounds': {'authority': {'shards': 2, 'owner_generations_per_shard': 2,
            'coordinator_generations': 2, 'new_publications': 1, 'prepared_risk_commands': 1, 'risk_commits': 1},
            'commands': {'accounts': 1, 'queued_command_IDs': 3, 'fill_IDs': 3,
                'initial_position_units': 2, 'worker_generations': 2, 'total_counterparty_depth': 2}},
        'assumptions': ['local commits are atomic and durable', 'trusted local monotonic lease clock and exact expiry event',
            'birth identity, boot/authority binding and pidfd refer to the actual process',
            'durable registration precedes worker authority', 'the two component models are not composed'],
        'not_proven': ['production-code refinement', 'arbitrary-scale safety', 'liveness or fairness',
            'physical power-loss or filesystem durability', 'OS identity implementation', 'replication or cross-AZ HA',
            'full PM, insurance or ADL', 'throughput or 24-hour stability', 'production approval'],
        'production_approved': False}


def main():
    result = report()
    print(json.dumps(result, indent=2))
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
