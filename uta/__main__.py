"""Reference calculations and the authenticated durable exchange foundation."""
import argparse
import json
import math
import re
import signal
import sqlite3
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
    parser = argparse.ArgumentParser(description='UTA research and durable exchange foundation')
    parser.add_argument('command', choices=['demo', 'serve', 'exchange', 'acceptance', 'lab', 'scenario', 'replay'], nargs='?', default='demo')
    parser.add_argument('--port', type=int, help='loopback port (exchange/serve: 8080, research lab: 8765)')
    parser.add_argument('--db', type=Path, help='research simulator database; distinct from --database exchange authority')
    parser.add_argument('--shards', type=int, default=1, help='research simulator shard count (1..64)')
    parser.add_argument('--account', default='demo', help='research scenario/replay account')
    parser.add_argument('--host', default='127.0.0.1', help='exchange bind address; use a TLS reverse proxy')
    parser.add_argument('--database', help='persistent SQLite database on local storage')
    parser.add_argument('--credentials', help='private credential JSON file, owned by the service user')
    parser.add_argument('--catalog', help='versioned product catalog JSON file')
    parser.add_argument('--risk-rules', help='matching versioned Cross risk rules JSON file')
    parser.add_argument('--automate', action='store_true', help='run local risk supervision and real paired matching')
    parser.add_argument('--batch-admission', action='store_true', help='opt in to bounded grouped order/cancel commits')
    parser.add_argument('--admission-batch-size', type=int, default=32, help='grouped commands per commit (1..256)')
    parser.add_argument('--admission-delay-ms', type=float, default=2, help='maximum batch collection delay (0..1000ms)')
    parser.add_argument('--admission-queue-capacity', type=int, default=1024, help='pending grouped command limit (1..65536)')
    parser.add_argument('--admission-cancel-reserve', type=int, default=16, help='extra bounded FIFO cancellation slots (0..4096)')
    parser.add_argument('--admission-timeout', type=float, default=2, help='HTTP grouped-result wait deadline (.001..60s)')
    parser.add_argument('--reserve-cache-size', type=int, default=0, help='opt in to bounded exact reservation memoization (0..65536; 0 disables)')
    parser.add_argument('--market-cache-size', type=int, default=0, help='opt in to immutable market decoding cache (0..64; 0 disables)')
    parser.add_argument('--asset-scale', action='append', metavar='ASSET=DIGITS',
                        help='asset minor-unit scale; repeat for all assets (default: USD=8)')
    args = parser.parse_args()
    if args.port is not None and not 0 <= args.port <= 65535:
        parser.error('port must be between 0 and 65535')
    if not 1 <= args.shards <= 64:
        parser.error('shards must be between 1 and 64')
    if not 0 <= args.reserve_cache_size <= 65536 or not 0 <= args.market_cache_size <= 64:
        parser.error('invalid cache bounds: reserve 0..65536, market 0..64')
    if args.command != 'exchange' and (args.reserve_cache_size or args.market_cache_size):
        parser.error('risk computation caches are supported only for exchange')
    if (not 1 <= args.admission_batch_size <= 256
            or not math.isfinite(args.admission_delay_ms) or not 0 <= args.admission_delay_ms <= 1000
            or not 1 <= args.admission_queue_capacity <= 65536
            or not 0 <= args.admission_cancel_reserve <= 4096
            or not math.isfinite(args.admission_timeout) or not .001 <= args.admission_timeout <= 60):
        parser.error('invalid grouped admission bounds: batch 1..256, delay 0..1000ms, queue 1..65536, cancel reserve 0..4096, timeout .001..60s')
    if args.batch_admission and args.command != 'exchange':
        parser.error('--batch-admission is supported only for exchange')
    if args.command == 'exchange':
        if not args.database or not args.credentials:
            parser.error('exchange requires --database and --credentials')
        from .storage import Database, StorageError
        try:
            scales = _scales(args.asset_scale)
            from .gateway import load_credentials, make_server
            from .service import ExchangeService
            from .configuration import load_policy
            from .credit import CreditService
            from .matching import Matcher
            # Validate credentials before creating or opening financial state.
            credentials = load_credentials(args.credentials)
            policy = load_policy(args.catalog, args.risk_rules)
            database = Database(args.database)
            service = ExchangeService(database, scales, reserve_cache_size=args.reserve_cache_size,
                                      market_cache_size=args.market_cache_size, **policy)
            service.credit = CreditService(service)
            service.matcher = Matcher(service)
            if service.product_catalog is not None:
                from .spot import SpotExchange
                service.spot = SpotExchange(service, service.product_catalog)
            service.ledger.verify()
            server = make_server(service, args.host, 8080 if args.port is None else args.port,
                                 credentials=credentials, admission_timeout=args.admission_timeout)
        except (ValueError, OSError, StorageError, sqlite3.Error) as exc:
            parser.error(str(exc))
        def stop(signum, frame):
            raise KeyboardInterrupt
        previous = signal.signal(signal.SIGTERM, stop)
        worker = None
        admission = None
        try:
            if args.batch_admission:
                from .admission import AdmissionBatcher
                admission = AdmissionBatcher(service, max_batch_size=args.admission_batch_size,
                    max_delay_ms=args.admission_delay_ms, queue_capacity=args.admission_queue_capacity,
                    cancel_reserve=args.admission_cancel_reserve)
                service.admission = admission
            if args.automate:
                from .supervisor import ExchangeWorker
                worker = ExchangeWorker(service)
                service.worker = worker
                worker.start()
            print(json.dumps({'service': 'uta-exchange', 'host': args.host,
                              'port': server.server_address[1],
                              'automated': args.automate,
                              'batch_admission': args.batch_admission,
                              'mode': 'local-order-book; no external order routing'}), flush=True)
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            try:
                _drain_exchange(server, worker, admission)
            finally:
                signal.signal(signal.SIGTERM, previous)
    elif args.command in ('lab', 'scenario', 'replay'):
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
    elif args.command == 'acceptance':
        from .acceptance import run_acceptance
        print(json.dumps(run_acceptance(), indent=2))
    elif args.command == 'serve':
        serve(8080 if args.port is None else args.port)
    else:
        demo()


def _drain_exchange(server, worker=None, admission=None):
    """Release every owned component even if another component fails to stop."""
    try:
        if worker is not None:
            worker.stop()
    finally:
        try:
            # Admitted handlers can still enqueue. Keep the batcher accepting
            # until HTTP has drained, then flush its remaining commands.
            server.server_close()
        finally:
            if admission is not None:
                admission.close(wait=True)


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
