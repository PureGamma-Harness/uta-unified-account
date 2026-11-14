"""Run the local reference demonstration or local-only JSON API."""
import argparse
import json
from datetime import datetime, timezone
from decimal import Decimal

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


def main():
    parser = argparse.ArgumentParser(description='UTA reference simulation (not for live trading)')
    parser.add_argument('command', choices=['demo', 'serve'], nargs='?', default='demo')
    parser.add_argument('--port', type=int, default=8080, help='local-only API port (default 8080)')
    args = parser.parse_args()
    if not 0 <= args.port <= 65535:
        parser.error('port must be between 0 and 65535')
    if args.command == 'serve':
        serve(args.port)
    else:
        demo()


if __name__ == '__main__':
    main()
