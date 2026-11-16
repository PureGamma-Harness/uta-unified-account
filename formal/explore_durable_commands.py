"""Bounded, independent durable-queue/financial-commit safety model.

No production module is imported. WAL durability and an atomic database writer
are assumptions, not properties established by this finite exploration.
"""
from collections import deque
from dataclasses import asdict, dataclass, replace
import json


ACCOUNTS = (0, 0, 1, 0)
AMOUNTS = (1, 2, 2, 0)  # Last command cancels the first order.
CAPACITY = (2, 2)
PENDING, ACCEPTED, REJECTED, CANCELLED = range(4)


@dataclass(frozen=True)
class State:
    queued: int = 0
    terminal: tuple[int, ...] = (PENDING,) * 4
    held: tuple[int, ...] = (0,) * 3
    effects: tuple[int, ...] = (0,) * 4
    delivered: tuple[bool, ...] = (False,) * 4
    generation: int = 0
    live: bool = False
    staged: int = -1
    staged_generation: int = 0
    unfenced_commit: bool = False


def put(values, index, value):
    return values[:index] + (value,) + values[index + 1:]


def financial_commit(state, index):
    held, effects = state.held, state.effects
    if index == 3:
        held = put(held, 0, 0)
        effects = put(effects, index, effects[index] + 1)
        outcome = CANCELLED
    else:
        used = sum(amount for position, amount in enumerate(held)
                   if ACCOUNTS[position] == ACCOUNTS[index])
        if used + AMOUNTS[index] > CAPACITY[ACCOUNTS[index]]:
            outcome = REJECTED
        else:
            held = put(held, index, held[index] + AMOUNTS[index])
            effects = put(effects, index, effects[index] + 1)
            outcome = ACCEPTED
    return replace(state, held=held, effects=effects,
                   terminal=put(state.terminal, index, outcome), staged=-1)


def transitions(state, mutant=None):
    if state.queued < 4:
        yield 'durably enqueue next command', replace(state, queued=state.queued + 1)
    if not state.live and state.generation < 2:
        yield 'acquire next writer generation', replace(state, live=True, generation=state.generation + 1)
    if state.live:
        yield 'lease expires', replace(state, live=False)
    if state.staged < 0 and state.live:
        for index in range(state.queued):
            if state.terminal[index] != PENDING:
                if mutant == 'duplicate_retry' and state.effects[index] and index < 3:
                    yield 'unsafe replay of terminal effect', replace(state,
                        held=put(state.held, index, state.held[index] + AMOUNTS[index]),
                        effects=put(state.effects, index, state.effects[index] + 1))
                continue
            earlier = [prior for prior in range(index) if ACCOUNTS[prior] == ACCOUNTS[index]
                       and state.terminal[prior] == PENDING]
            if earlier and mutant != 'skip_fifo':
                continue
            yield 'stage account head ' + str(index), replace(state, staged=index,
                                                               staged_generation=state.generation)
    if state.staged >= 0:
        index = state.staged
        yield 'crash before commit; durable inbox survives', replace(state, staged=-1)
        allowed = state.live and state.staged_generation == state.generation
        if allowed or mutant == 'skip_fence':
            committed = financial_commit(state, index)
            if not allowed:
                committed = replace(committed, unfenced_commit=True)
            if mutant == 'split_terminal':
                committed = replace(committed, terminal=state.terminal)
            yield 'commit financial effect and terminal', committed
        if mutant == 'early_accept':
            yield 'unsafe acceptance before financial commit', replace(state,
                delivered=put(state.delivered, index, True))
    for index in range(state.queued):
        if state.terminal[index] != PENDING and not state.delivered[index]:
            yield 'deliver or query immutable terminal ' + str(index), replace(state,
                delivered=put(state.delivered, index, True))


def violation(state):
    if state.unfenced_commit:
        return 'financial commit used an expired or superseded writer'
    for account, capacity in enumerate(CAPACITY):
        used = sum(amount for index, amount in enumerate(state.held) if ACCOUNTS[index] == account)
        if used > capacity:
            return 'account capacity was reserved twice'
    for index, count in enumerate(state.effects):
        if state.terminal[index] != PENDING and any(state.terminal[prior] == PENDING
                and ACCOUNTS[prior] == ACCOUNTS[index] for prior in range(index)):
            return 'later account command became terminal before its pending head'
        if count > 1:
            return 'same command produced financial effect twice'
        if count and state.terminal[index] not in (ACCEPTED, CANCELLED):
            return 'financial effect lacks committed successful terminal'
        if state.delivered[index] and state.terminal[index] == PENDING:
            return 'client acceptance was published before terminal commit'
        if index >= state.queued and state.terminal[index] != PENDING:
            return 'terminal exists without durable enqueue'
    return None


def explore(mutant=None):
    initial = State()
    previous, queue = {initial: None}, deque([initial])
    edge_count = 0
    while queue:
        state = queue.popleft()
        problem = violation(state)
        if problem:
            trace = []
            while previous[state] is not None:
                before, action = previous[state]
                trace.append({'action': action, 'after': asdict(state)})
                state = before
            return {'states': len(previous), 'transitions': edge_count, 'violation': problem,
                    'counterexample': list(reversed(trace))}
        for action, after in transitions(state, mutant):
            edge_count += 1
            if after not in previous:
                previous[after] = state, action
                queue.append(after)
    return {'states': len(previous), 'transitions': edge_count, 'violation': None}


def main():
    safe = explore()
    mutants = {name: explore(name) for name in
               ('early_accept', 'split_terminal', 'duplicate_retry', 'skip_fence', 'skip_fifo')}
    passed = safe['violation'] is None and all(result['violation'] for result in mutants.values())
    print(json.dumps({'passed': passed, 'safe': safe, 'negative_controls': mutants,
        'bounds': {'commands': 4, 'accounts': 2, 'writer_generations': 2, 'concurrent_transactions': 1},
        'assumptions': ['atomic local financial and terminal commit', 'durable queued records survive process crash',
                        'fixed immutable command IDs and payloads', 'one transaction writer at a time'],
        'not_proven': ['implementation refinement', 'liveness or scheduling fairness', 'real clock correctness',
                       'physical WAL/fsync durability', 'arbitrary scale', 'replication or HA', 'production approval'],
        'production_approved': False}, indent=2))
    return 0 if passed else 1


if __name__ == '__main__':
    raise SystemExit(main())
