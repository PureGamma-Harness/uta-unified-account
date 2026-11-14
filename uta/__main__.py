"""Run the local reference demonstration or local-only JSON API."""
import argparse
import json
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory

from .api import SAMPLE, evaluate, json_value, serve
from .liquidation import LiquidationController, TimedRisk
from .models import Account, AssetSpec, InstrumentSpec, Position
from .migration import build_shadow
from .risk import calculate_risk


def demo():
    risk = evaluate('/risk', SAMPLE)
    order = dict(SAMPLE, order={'symbol': 'BTC-PERP', 'quantity': '0.02', 'execution_price': '21010', 'fee_rate': '0.001'})
    checked = evaluate('/order-check', order)
    # Deliberately distressed fictional account to demonstrate a cancellation proposal.
    account = Account({'USD': Decimal('80')}, {'BTC-PERP': Position('BTC-PERP', Decimal('0.1'), Decimal('21000'))})
    assets = {'USD': AssetSpec(Decimal('1'), Decimal('1'))}
    instruments = {'BTC-PERP': InstrumentSpec(Decimal('21000'), Decimal('.1'), Decimal('.05'))}
    now = datetime.now(timezone.utc)
    controller = LiquidationController('demo')
    action = controller.next_action(TimedRisk(calculate_risk(account, assets, instruments), now), now=now)
    shadow = build_shadow({'account_id': 'classic-demo', 'version': 1, 'captured_at': now.isoformat(),
                           'compartments': {
                               'spot': {'balances': [{'asset': 'USD', 'free': '1000', 'locked': '0', 'borrowed': '0', 'interest': '0'}]},
                               'margin': {'balances': []},
                               'futures': {'balances': [], 'positions': []}}}, now=now)
    print(json.dumps({'classic_shadow': json_value(shadow), 'disclaimer': 'Illustrative only; no real orders or exchange connection', 'risk': risk,
                      'order_check': checked, 'distressed_account_action': json_value(action)}, indent=2))


def scenario(path, account_id, shards):
    from .simulator import Simulator

    sim = Simulator(path, shards=shards)
    initial = sim.bootstrap(account_id)
    version = 0
    trace = []

    def step(command_id, kind, **fields):
        nonlocal version
        receipt = sim.execute(account_id, command_id, version, {"type": kind, **fields})
        version = receipt["version"]
        trace.append({"version": version, "action": receipt["action"], "health": receipt["health"],
                      "equity": receipt["risk"]["equity"], "fills": receipt.get("fills", [])})

    step("entry", "place_order", symbol="BTC-PERP", quantity="0.9", limit_price="60000", fee_rate="0.001")
    step("fill", "fill_order", order_id="entry", quantity="0.9", price="60000")
    step("resting", "place_order", symbol="BTC-PERP", quantity="0.1", limit_price="60000", fee_rate="0.001")
    step("shock", "set_prices", prices={"USD": "1", "BTC": "40000", "ETH": "2100"},
         marks={"BTC-PERP": "40000", "ETH-PERP": "2100"})
    for index in range(16):
        current = sim.view(account_id)
        if current["health"] == "HEALTHY" or (not current["state"]["positions"] and not any(
            order["status"] == "OPEN" for order in current["state"]["orders"].values()
        )):
            break
        step(f"liquidation-{index}", "liquidate")
    else:
        raise RuntimeError("scenario exceeded its liquidation step budget")
    reopened = Simulator(path, shards=shards)
    return {"initial_equity": initial["risk"]["equity"], "steps": trace,
            "ending_account": reopened.view(account_id), "replay": reopened.verify_replay(account_id)}


def main():
    parser = argparse.ArgumentParser(description='UTA reference simulation (not for live trading)')
    parser.add_argument('command', choices=['demo', 'serve', 'lab', 'scenario', 'replay'], nargs='?', default='demo')
    parser.add_argument('--port', type=int, help='loopback port (serve: 8080, lab: 8765)')
    parser.add_argument('--db', type=Path, help='SQLite path or base name for a sharded database')
    parser.add_argument('--shards', type=int, default=1, help='fixed number of database shards (1–64)')
    parser.add_argument('--account', default='demo', help='account for scenario or replay')
    args = parser.parse_args()
    if args.port is not None and not 0 <= args.port <= 65535:
        parser.error('port must be between 0 and 65535')
    if not 1 <= args.shards <= 64:
        parser.error('shards must be between 1 and 64')
    if args.command == 'serve':
        serve(8080 if args.port is None else args.port)
    elif args.command == 'demo':
        demo()
    else:
        from .server import serve as serve_simulator
        from .simulator import Simulator, SimulatorError
        from .store import StoreError

        try:
            if args.command == 'lab':
                serve_simulator(args.db or Path('uta-lab.sqlite3'),
                                8765 if args.port is None else args.port, shards=args.shards)
            elif args.command == 'replay':
                if args.db is None:
                    parser.error('replay requires --db')
                print(json.dumps(Simulator(args.db, shards=args.shards).verify_replay(args.account), indent=2))
            elif args.db is None:
                with TemporaryDirectory() as directory:
                    print(json.dumps(scenario(Path(directory) / 'scenario.sqlite3', args.account, args.shards), indent=2))
            else:
                print(json.dumps(scenario(args.db, args.account, args.shards), indent=2))
        except (SimulatorError, StoreError) as exc:
            parser.error(str(exc))


if __name__ == '__main__':
    main()
