"""Exhaustively enumerate a small abstraction; not a TLA+ interpreter."""
from collections import deque
from dataclasses import dataclass, replace


ORDERS = ("o1", "o2", "o3")
CAPACITY = 2


@dataclass(frozen=True)
class State:
    phase: tuple[str, ...] = ("idle",) * len(ORDERS)
    seen: tuple[int, ...] = (0,) * len(ORDERS)
    amount: tuple[int, ...] = (0,) * len(ORDERS)
    held: tuple[int, ...] = (0,) * len(ORDERS)
    version: int = 0
    # Additional history used only in the unsafe comparison model.
    seen_free: tuple[int, ...] = (0,) * len(ORDERS)


def put(values, i, value):
    return values[:i] + (value,) + values[i + 1:]


def next_states(s, *, unsafe):
    total = sum(s.held)
    for i, order in enumerate(ORDERS):
        if s.phase[i] == "idle":
            for amount in range(1, CAPACITY + 1):
                yield (f"begin({order}, {amount})", replace(
                    s, phase=put(s.phase, i, "pending"),
                    seen=put(s.seen, i, s.version),
                    seen_free=put(s.seen_free, i, CAPACITY - total),
                    amount=put(s.amount, i, amount)))
        elif s.phase[i] == "pending":
            # Safe branch matches the version and current-capacity checks in the
            # TLA+ spec. The mutant checks an old snapshot and skips the version.
            allowed = (s.amount[i] <= s.seen_free[i]) if unsafe else (
                s.seen[i] == s.version and total + s.amount[i] <= CAPACITY)
            if allowed:
                yield (f"commit({order})", replace(
                    s, phase=put(s.phase, i, "held"),
                    held=put(s.held, i, s.amount[i]), version=s.version + 1))
            else:
                yield (f"reject({order})", replace(s, phase=put(s.phase, i, "rejected")))
        elif s.phase[i] == "held":
            yield (f"release({order})", replace(
                s, phase=put(s.phase, i, "released"),
                held=put(s.held, i, 0), version=s.version + 1))


def violation(s):
    if sum(s.held) > CAPACITY:
        return "total held exceeds capacity"
    for i, phase in enumerate(s.phase):
        if phase == "held" and not (s.held[i] == s.amount[i] and s.amount[i] > 0):
            return "held amount differs from request"
        if phase != "held" and s.held[i] != 0:
            return "non-held order has a reservation"
    return None


def explore(*, unsafe=False):
    start = State()
    queue = deque([start])
    previous = {start: None}
    while queue:
        current = queue.popleft()
        problem = violation(current)
        if problem:
            trace = []
            while previous[current] is not None:
                prior, action = previous[current]
                trace.append((action, current))
                current = prior
            return len(previous), problem, list(reversed(trace))
        for action, successor in next_states(current, unsafe=unsafe):
            if successor not in previous:
                previous[successor] = (current, action)
                queue.append(successor)
    return len(previous), None, []


def main():
    count, problem, _ = explore()
    if problem:
        raise AssertionError(f"safe abstraction violates invariant: {problem}")
    print(f"Safe abstraction: {count} reachable states, invariants hold.")
    count, problem, trace = explore(unsafe=True)
    if not problem:
        raise AssertionError("expected counterexample was not found")
    print(f"Unsafe snapshot-only mutation: {problem} ({count} states found).")
    for action, state in trace:
        print(f"  {action}: held={state.held}, version={state.version}")


if __name__ == "__main__":
    main()
