"""Bounded two-order/two-trade atomic settlement model, independent of UTA code.

Assumptions: one exclusive writer, atomic commit/rollback, durable committed
state, unique trade IDs, no external side effect before local authorization.
This is finite safety enumeration, not a proof of HA, fairness or real code.
"""
from collections import deque
from dataclasses import dataclass, replace
import json


ASSETS = ("USD", "USD", "USD", "USD", "BTC", "BTC")
TRADES = ("trade-1", "trade-2")


@dataclass(frozen=True)
class State:
    buys: tuple[int, ...] = (0, 0)
    sells: tuple[int, ...] = (0, 0)
    receipts: tuple[int, ...] = (0, 0)
    positions: tuple[int, int] = (0, 0)
    balances: tuple[int, ...] = (100, 100, 0, -200, 3, -3)
    held: tuple[int, int] = (2, 2)
    cancelled: tuple[bool, bool] = (False, False)
    delivered: tuple[bool, bool] = (False, False)
    phase: str = "idle"
    active: int = -1


def put(values, index, value):
    return values[:index] + (value,) + values[index + 1:]


def committed(state, index, *, unsafe=None):
    balance = state.balances
    next_balance = (balance[0] - 1, balance[1] - 1, balance[2] + 2, *balance[3:])
    if unsafe == "cross_asset_netting":
        # The scalar sum still balances, but one USD fee is credited as BTC.
        next_balance = (balance[0] - 1, balance[1] - 1, balance[2] + 1,
                        balance[3], balance[4] + 1, balance[5])
    return replace(state, buys=put(state.buys, index, state.buys[index] + 1),
                   sells=put(state.sells, index, state.sells[index] + 1),
                   receipts=put(state.receipts, index, 1),
                   positions=(state.positions[0] + 1, state.positions[1] - 1),
                   balances=next_balance,
                   held=(state.held[0] - 1, state.held[1] - 1), phase="idle", active=-1)


def successors(state, *, unsafe=None):
    if state.phase == "idle":
        for index, trade_id in enumerate(TRADES):
            if state.receipts[index]:
                if not state.delivered[index]:
                    yield "receive_or_query(" + trade_id + ")", replace(
                        state, delivered=put(state.delivered, index, True))
                if unsafe == "duplicate_retry":
                    # Deliberately broken: ignore the immutable receipt on retry.
                    yield "retry_without_dedup(" + trade_id + ")", committed(state, index)
            elif not any(state.cancelled) and min(state.held) > 0:
                yield "begin(" + trade_id + ")", replace(state, phase="validated", active=index)
        for side in range(2):
            if not state.cancelled[side] and state.held[side]:
                yield "cancel(" + str(side) + ")", replace(
                    state, cancelled=put(state.cancelled, side, True), held=put(state.held, side, 0))
    else:
        # Queued cancel/retry cannot read uncommitted writes or bypass the writer.
        # Failures after either side or receipt staging all roll back together.
        yield "abort_or_crash(" + state.phase + ")", replace(state, phase="idle", active=-1)
        if state.phase == "validated":
            if unsafe == "split_commit":
                index, balance = state.active, state.balances
                yield "publish_buy_before_sell", replace(
                    state, buys=put(state.buys, index, 1),
                    positions=(state.positions[0] + 1, state.positions[1]),
                    balances=(balance[0] - 1, balance[1], balance[2] + 1, *balance[3:]),
                    held=(state.held[0] - 1, state.held[1]), phase="buy_staged")
            else:
                yield "stage_buy", replace(state, phase="buy_staged")
        elif state.phase == "buy_staged":
            yield "stage_sell", replace(state, phase="both_staged")
        elif state.phase == "both_staged":
            yield "stage_unique_receipt", replace(state, phase="receipt_staged")
        elif state.phase == "receipt_staged":
            yield "atomic_commit", committed(state, state.active, unsafe=unsafe)


def violation(state):
    for index in range(len(TRADES)):
        if (state.buys[index], state.sells[index]) != (state.receipts[index],) * 2:
            return "a confirmed trade must have exactly one settlement on each side"
        if state.receipts[index] not in (0, 1):
            return "a trade ID may be committed only once"
        if state.delivered[index] and state.receipts[index] != 1:
            return "an observed receipt must survive restart"
    if sum(state.positions) != 0:
        return "matched positions must conserve signed contract quantity"
    for asset in set(ASSETS):
        if sum(balance for symbol, balance in zip(ASSETS, state.balances) if symbol == asset) != 0:
            return "journal postings must balance independently for " + asset
    for side in range(2):
        remaining = 2 - sum(state.receipts)
        expected = 0 if state.cancelled[side] else remaining
        if state.held[side] != expected or state.held[side] < 0:
            return "only unfilled, uncancelled quantity may retain its reservation"
    return None


def explore(*, unsafe=None):
    start = State()
    previous = {start: None}
    pending = deque([start])
    while pending:
        current = pending.popleft()
        problem = violation(current)
        if problem:
            trace = []
            while previous[current] is not None:
                parent, action = previous[current]
                trace.append(action)
                current = parent
            return {"result": "counterexample", "reachable_states": len(previous),
                    "violation": problem, "trace": list(reversed(trace))}
        for action, successor in successors(current, unsafe=unsafe):
            if successor not in previous:
                previous[successor] = current, action
                pending.append(successor)
    return {"result": "invariants_hold", "reachable_states": len(previous)}


def main():
    report = {"safe": explore(), "unsafe_split_commit": explore(unsafe="split_commit"),
              "unsafe_duplicate_retry": explore(unsafe="duplicate_retry"),
              "unsafe_cross_asset_netting": explore(unsafe="cross_asset_netting"),
              "assumptions": ["two orders", "two one-unit trades", "one atomic writer",
                              "durable commits", "no execution before authorization"],
              "not_verified": ["HA/replication", "liveness", "network partitions",
                               "code/model equivalence", "arbitrary portfolio size"]}
    if (report["safe"]["result"] != "invariants_hold"
            or report["unsafe_split_commit"]["result"] != "counterexample"
            or report["unsafe_duplicate_retry"]["result"] != "counterexample"
            or report["unsafe_cross_asset_netting"]["result"] != "counterexample"):
        raise RuntimeError("settlement model failed its safety/mutant checks")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
