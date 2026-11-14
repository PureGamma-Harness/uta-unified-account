"""Reference calculations and the authenticated durable exchange foundation."""
import argparse
import json
import re
import signal
import sqlite3
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
    parser = argparse.ArgumentParser(description='UTA research and durable exchange foundation')
    parser.add_argument('command', choices=['demo', 'serve', 'exchange', 'acceptance'], nargs='?', default='demo')
    parser.add_argument('--port', type=int, default=8080, help='local-only API port (default 8080)')
    parser.add_argument('--host', default='127.0.0.1', help='exchange bind address; use a TLS reverse proxy')
    parser.add_argument('--database', help='persistent SQLite database on local storage')
    parser.add_argument('--credentials', help='private credential JSON file, owned by the service user')
    parser.add_argument('--asset-scale', action='append', metavar='ASSET=DIGITS',
                        help='asset minor-unit scale; repeat for all assets (default: USD=8)')
    args = parser.parse_args()
    if not 0 <= args.port <= 65535:
        parser.error('port must be between 0 and 65535')
    if args.command == 'exchange':
        if not args.database or not args.credentials:
            parser.error('exchange requires --database and --credentials')
        from .storage import Database, StorageError
        try:
            scales = _scales(args.asset_scale)
            from .gateway import load_credentials, make_server
            from .service import ExchangeService
            # Validate credentials before creating or opening financial state.
            credentials = load_credentials(args.credentials)
            database = Database(args.database)
            service = ExchangeService(database, scales)
            service.ledger.verify()
            server = make_server(service, args.host, args.port, credentials=credentials)
        except (ValueError, OSError, StorageError, sqlite3.Error) as exc:
            parser.error(str(exc))
        def stop(signum, frame):
            raise KeyboardInterrupt
        previous = signal.signal(signal.SIGTERM, stop)
        try:
            print(json.dumps({'service': 'uta-exchange', 'host': args.host,
                              'port': server.server_address[1],
                              'mode': 'local-order-book; no external order routing'}), flush=True)
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            try:
                server.server_close()
            finally:
                signal.signal(signal.SIGTERM, previous)
    elif args.command == 'acceptance':
        from .acceptance import run_acceptance
        print(json.dumps(run_acceptance(), indent=2))
    elif args.command == 'serve':
        serve(args.port)
    else:
        demo()


def _scales(entries):
    if not entries:
        return {'USD': 8}
    result = {}
    for entry in entries:
        asset, separator, scale = entry.partition('=')
        if (not separator or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}', asset)
                or asset in result or not scale.isascii() or not scale.isdigit()):
            raise ValueError('asset scales must be unique ASSET=DIGITS entries')
        digits = int(scale)
        if not 0 <= digits <= 18:
            raise ValueError('asset scale must be in 0..18')
        result[asset] = digits
    if 'USD' not in result:
        raise ValueError('USD settlement scale is required')
    return result


if __name__ == '__main__':
    main()
