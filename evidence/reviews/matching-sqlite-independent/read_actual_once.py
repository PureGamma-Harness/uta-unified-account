"""Read captured JSON/file bytes only; never import UTA or connect to SQLite."""
from collections import Counter, defaultdict
from decimal import Decimal
from fractions import Fraction
from hashlib import sha256, sha1
import json
import os
from pathlib import Path
import stat
import sys

PUBLIC = Path('/workspace/uta-matching-selection-snapshot/evidence/reviews/matching-selection-snapshot/sqlite-first-3b0c49a-once01')
OWNER = PUBLIC.parents[3]
PRIVATE = Path('/workspace/uta-matching-sqlite-3b0c49a-once01')
SOURCE = '3b0c49a6df6773ea7cdb208945541480ea091ea8'
SEAL = '3da0ee847042e995dae57778a8f7f3a7245cfeb5'
TIME_KEYS = {'created_at', 'observed_at', 'recorded_at'}
SCALE = 10**8


def raw(path):
    path = Path(path)
    before = path.stat(follow_symlinks=False)
    assert stat.S_ISREG(before.st_mode) and path.resolve() == path
    fd = os.open(path, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW | os.O_NOATIME)
    try:
        blocks = []
        while True:
            value = os.read(fd, 1024 * 1024)
            if not value:
                break
            blocks.append(value)
        value = b''.join(blocks)
    finally:
        os.close(fd)
    after = path.stat(follow_symlinks=False)
    fields = ('st_dev', 'st_ino', 'st_size', 'st_mtime_ns', 'st_ctime_ns', 'st_atime_ns')
    assert tuple(getattr(before, x) for x in fields) == tuple(getattr(after, x) for x in fields)
    assert len(value) == before.st_size
    return value


def unique(pairs):
    result = {}
    for key, value in pairs:
        assert key not in result
        result[key] = value
    return result


def loads(value):
    return json.loads(value, object_pairs_hook=unique,
                      parse_constant=lambda x: (_ for _ in ()).throw(ValueError(x)))


def read(path):
    return loads(raw(path))


def encoded(value):
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(',', ':')).encode()


def digest(value):
    return sha256(encoded(value)).hexdigest()


def rational(value):
    assert type(value) is str
    decimal = Decimal(value)
    assert decimal.is_finite()
    return Fraction(decimal)


def strip_times(value):
    if type(value) is dict:
        return {k: strip_times(v) for k, v in value.items() if k not in TIME_KEYS}
    if type(value) is list:
        return [strip_times(v) for v in value]
    return value


def fee(amount):
    scaled = amount * Fraction(1, 2500) * SCALE
    return Fraction(-(-scaled.numerator // scaled.denominator), SCALE)


def reserve(order):
    remaining = rational(order['quantity']) - rational(order['filled_quantity'])
    limit = rational(order['limit_price'])
    initial = 0 if order['reduce_only'] else abs(remaining) * max(100, limit) / 10
    loss = 0 if order['reduce_only'] else max(-remaining * (100 - limit), 0)
    return initial + loss + fee(rational(order['fee_notional']) + abs(remaining) * limit) - rational(order['charged_fee'])


def value_state(state):
    assert not state['liabilities'] and not any(rational(x) for x in state['frozen_assets'].values())
    equity = rational(state['balances']['USD'])
    im = mm = Fraction(0)
    for position in state['positions'].values():
        quantity, basis = rational(position['quantity']), rational(position['cost_basis'])
        equity += quantity * 100 - basis
        im += abs(quantity) * 10
        mm += abs(quantity) * 5
    held = sum((reserve(order) for order in state['orders']), Fraction(0))
    return {'equity': equity, 'initial_margin': im, 'maintenance_margin': mm,
            'open_order_margin': held, 'available_margin': equity - im - held}


def ledger_check(tables):
    postings = defaultdict(list)
    balances = defaultdict(int)
    for item in tables['ledger_postings']:
        assert type(item['units']) is str and str(int(item['units'])) == item['units']
        postings[item['sequence']].append(item)
        balances[item['account'], item['asset']] += int(item['units'])
    previous = '0' * 64
    by_id = {}
    for sequence, event in enumerate(tables['ledger_events'], 1):
        assert event['sequence'] == sequence and event['sealed'] == 1
        assert event['previous_hash'] == previous and event['event_id'] not in by_id
        legs = sorted(postings[sequence], key=lambda item: item['ordinal'])
        assert [leg['ordinal'] for leg in legs] == list(range(len(legs)))
        canonical = [[leg['account'], leg['asset'], int(leg['units'])] for leg in legs]
        fingerprint = sha256(json.dumps(canonical, ensure_ascii=True, separators=(',', ':')).encode()).hexdigest()
        assert fingerprint == event['fingerprint']
        previous = sha256(json.dumps([sequence, event['event_id'], previous, fingerprint],
                                     ensure_ascii=True, separators=(',', ':')).encode()).hexdigest()
        assert previous == event['event_hash']
        sums = defaultdict(int)
        actual = defaultdict(Fraction)
        for leg in legs:
            sums[leg['asset']] += int(leg['units'])
            actual[leg['account'], leg['asset']] += Fraction(int(leg['units']), SCALE)
        assert not any(sums.values())
        by_id[event['event_id']] = {key: amount for key, amount in actual.items() if amount}
    stored = {(item['account'], item['asset']): int(item['units']) for item in tables['ledger_balances']}
    assert stored == dict(balances)
    assert set(postings) == set(range(1, len(tables['ledger_events']) + 1))
    return by_id, stored


def economic_from_rows(tables, accounts):
    projection = {name: tables[name] for name in ('ledger_events', 'ledger_postings', 'ledger_balances',
        'uta_accounts', 'uta_positions', 'uta_fills', 'uta_liabilities', 'uta_deposits', 'uta_liquidation_accounts')}
    projection['accounts'] = accounts
    projection['orders'] = strip_times(tables['uta_orders'])
    projection['matches'] = strip_times(tables['uta_matches'])
    markets = {}
    for row in tables['uta_market_history']:
        assert row['snapshot_id'] == 'market:' + sha256(row['payload'].encode()).hexdigest()
        assert row['content_digest'] == sha256(row['payload'].encode()).hexdigest()
        market = loads(row['payload'])
        assert market['assets']['USD']['price'] == '1'
        markets[row['snapshot_id']] = market
    projection['events'] = []
    for row in tables['uta_events']:
        payload = loads(row['payload'])
        if row['event_type'] == 'MARKET_PUBLISHED':
            market = markets[payload['market_snapshot_id']]
            assert market['version'] == payload['version'] and market['observed_at'] == payload['observed_at']
            payload = {'version': payload['version']}
        projection['events'].append({'sequence': row['sequence'], 'event_type': row['event_type'],
                                     'account_id': row['account_id'], 'payload': strip_times(payload)})
    projection['decisions'] = []
    for row in tables['uta_risk_decisions']:
        assert row['market_snapshot_id'] in markets
        item = {key: value for key, value in row.items()
                if key not in {'market_snapshot_id', 'recorded_at', 'input_payload', 'summary_payload'}}
        item['inputs'] = strip_times(loads(row['input_payload']))
        item['summary'] = strip_times(loads(row['summary_payload']))
        for side in ('before', 'after'):
            expected = value_state(item['inputs'][side])
            for key, amount in expected.items():
                assert rational(item['summary']['risk_' + side][key]) == amount
        projection['decisions'].append(item)
    return projection


def financial_check(report):
    tables = report['final']['tables']
    journals, balances = ledger_check(tables)
    orders = {(row['account_id'], row['order_id']): row for row in tables['uta_orders']}
    fills = {(row['account_id'], row['fill_id']): row for row in tables['uta_fills']}
    assert len(fills) == len(tables['uta_fills'])
    positions, notional, charged, filled = {}, defaultdict(Fraction), defaultdict(Fraction), defaultdict(Fraction)
    seen = set()
    for row in tables['uta_deposits']:
        assert row['asset'] == 'USD' and row['amount'] == '10000'
        key = 'deposit:' + digest([row['account_id'], row['event_id']])
        assert journals[key] == {('customer:' + row['account_id'], 'USD'): Fraction(10000),
                                 ('system:custody', 'USD'): Fraction(-10000)}
    for event in tables['uta_events']:
        if event['event_type'] != 'FILL_APPLIED':
            continue
        payload = loads(event['payload'])
        account, fill_id = event['account_id'], payload['fill_id']
        assert (account, fill_id) in fills and (account, fill_id) not in seen
        seen.add((account, fill_id))
        row = fills[account, fill_id]
        order = orders[account, row['order_id']]
        amount, price = rational(row['quantity']), rational(row['price'])
        position_key = account, order['symbol']
        quantity, basis = positions.get(position_key, (Fraction(0), Fraction(0)))
        if not quantity or (quantity > 0) == (amount > 0):
            next_quantity, next_basis, pnl = quantity + amount, basis + amount * price, Fraction(0)
        else:
            closed = min(abs(quantity), abs(amount))
            pnl = closed * (price - basis / quantity) * (1 if quantity > 0 else -1)
            next_quantity = quantity + amount
            next_basis = (basis * next_quantity / quantity if abs(amount) <= abs(quantity) else next_quantity * price)
        if next_quantity:
            positions[position_key] = next_quantity, next_basis
        else:
            positions.pop(position_key, None)
        key = account, row['order_id']
        notional[key] += abs(amount) * price
        expected_fee = fee(notional[key]) - charged[key]
        charged[key] += expected_fee
        filled[key] += amount
        assert rational(row['realized_pnl']) == pnl and rational(row['fee']) == expected_fee
        assert rational(payload['quantity']) == amount and rational(payload['price']) == price
        assert rational(payload['realized_pnl']) == pnl and rational(payload['fee']) == expected_fee
        assert rational(payload['order']['filled_quantity']) == filled[key]
        expected = {('customer:' + account, 'USD'): pnl - expected_fee,
                    ('system:realized-pnl', 'USD'): -pnl, ('system:fees', 'USD'): expected_fee}
        assert journals['fill:' + digest([account, fill_id])] == {k: v for k, v in expected.items() if v}
    assert seen == set(fills)
    actual_positions = {(row['account_id'], row['symbol']): (rational(row['quantity']), rational(row['cost_basis']))
                        for row in tables['uta_positions']}
    assert actual_positions == positions
    for key, order in orders.items():
        assert rational(order['filled_quantity']) == filled[key]
        assert rational(order['fee_notional']) == notional[key]
        assert rational(order['charged_fee']) == charged[key]
    paired = set()
    for sequence, row in enumerate(tables['uta_matches'], 1):
        assert row['sequence'] == sequence
        identity = sha256(json.dumps([row['symbol'], row['buy_account_id'], row['buy_order_id'],
            row['sell_account_id'], row['sell_order_id'], row['buy_filled_before'], row['sell_filled_before'],
            row['quantity'], row['price']], separators=(',', ':'), ensure_ascii=True).encode()).hexdigest()
        assert row['trade_id'] == 'match:' + identity
        for side, sign, suffix in (('buy', 1, ':b'), ('sell', -1, ':s')):
            account, identifier = row[side + '_account_id'], row[side + '_fill_id']
            assert identifier == row['trade_id'] + suffix and (account, identifier) not in paired
            pair = fills[account, identifier]
            assert pair['order_id'] == row[side + '_order_id']
            assert rational(pair['quantity']) == sign * rational(row['quantity'])
            assert pair['price'] == row['price']
            paired.add((account, identifier))
    assert paired == set(fills)
    for stage in ('before_reopen', 'after_reopen', 'final'):
        capture = report[stage]
        assert capture['settings'] == {'journal_mode': 'wal', 'synchronous': 2}
        rebuilt = economic_from_rows(capture['tables'], capture['accounts'])
        assert rebuilt == capture['economic_projection']
    assert report['before_reopen']['economic_projection'] == report['after_reopen']['economic_projection']
    account_values = {item['account_id']: item for item in report['final']['accounts']}
    if report['case'] == 'fifo-stp-partial':
        assert all(item['balances']['USD'] == '9999.96' for item in account_values.values())
        assert account_values['d']['open_order_margin'] == '20.08'
        assert orders['a', 'self-taker']['status'] == 'CANCELLED'
        assert [row['buy_order_id'] for row in tables['uta_matches']] == ['first-buyer', 'second-buyer']
    elif report['case'] == 'reduce-only-cross-cancel':
        victim = account_values['victim']
        assert victim['balances']['USD'] == '9996.8012'
        assert victim['positions']['BTC-PERP']['quantity'] == '1' and victim['positions']['BTC-PERP']['cost_basis'] == '100'
        assert orders['victim', 'later-ro']['status'] == 'CANCELLED' and orders['victim', 'later-ro']['filled_quantity'] == '0'
        assert [row['sell_order_id'] for row in tables['uta_matches']] == ['opening-sell', 'ordinary-close', 'first-ro']
    elif report['case'] == 'second-leg-freeze':
        assert not fills and not positions
        assert orders['buyer', 'buyer-order']['status'] == 'OPEN' and orders['seller', 'seller-order']['status'] == 'CANCELLED'
        item = report['intermediate_originals'][0]
        assert item['buyer_before'] == item['buyer_after'] and item['before']['tables']['ledger_events'] == item['after']['tables']['ledger_events']
        action = next(item['result'] for item in report['actions'] if item['label'] == 'second-leg-real-account-frozen')
        assert [(row['code'], row['account_id']) for row in action['blocked']] == [('account_frozen', 'seller')]
    else:
        assert all(item['balances']['USD'] == '9999.9208' for item in account_values.values())
    expected = {'fifo-stp-partial': 2, 'reduce-only-cross-cancel': 3, 'second-leg-freeze': 0, 'no-liquidity-halt': 1}[report['case']]
    assert len(tables['uta_matches']) == expected and len(fills) == 2 * expected
    assert report['strict']['matches'] == expected and report['strict']['paired_fills'] == 2 * expected and report['strict']['unpaired_fills'] == 0
    assert report['independent']['status'] == 'passed'
    if expected:
        assert report['valuation_replay']['matches'] is True and report['valuation_replay']['differences'] == {}
    else:
        assert report['valuation_replay'] is None
    return {'case': report['case'], 'mode': report['mode'], 'matches': expected, 'paired_fills': len(fills),
            'ledger_events': len(tables['ledger_events']), 'ledger_postings': len(tables['ledger_postings']),
            'independent_captured_cash_cost_fee_and_hash_checks': True}


def main():
    git = {}
    for line in raw(Path(sys.argv[1])).decode().splitlines():
        head, name = line.split('\t', 1)
        mode, kind, oid, size = head.split()
        git[name] = (mode, oid, int(size))
    prefix = str(PUBLIC.relative_to(OWNER)) + '/'
    for name, (mode, oid, size) in git.items():
        data = raw(OWNER / name)
        assert len(data) == size and sha1(b'blob ' + str(size).encode() + b'\0' + data).hexdigest() == oid
    sealed = read(PUBLIC / 'seal.json')
    assert sealed['files_count'] == 17 and sum(v['bytes'] for v in sealed['files'].values()) == sealed['file_bytes'] == 4992311
    for name, pin in sealed['files'].items():
        data = raw(PUBLIC / name)
        assert len(data) == pin['bytes'] and sha256(data).hexdigest() == pin['sha256']
    copied = read(PUBLIC / 'copy-manifest.json')
    assert copied['copies'] == 11 and copied['copied_bytes'] == 4906804
    for name, pin in copied['private_reports'].items():
        left, right = raw(PUBLIC / 'report-originals' / name), raw(PRIVATE / pin['private_relative_path'])
        assert left == right and len(left) == pin['bytes'] and sha256(left).hexdigest() == pin['sha256']
    inventory = read(PUBLIC / 'report-originals/inventory.json')
    assert len(inventory['files']) == 82
    for name, pin in inventory['files'].items():
        data = raw(PRIVATE / name)
        assert len(data) == pin['bytes'] and sha256(data).hexdigest() == pin['sha256']
    assert sum(x['bytes'] for x in inventory['files'].values()) == inventory['sum_file_bytes']
    result = read(PUBLIC / 'report-originals/result.json')
    manifest_path = PRIVATE / 'source/evidence/reviews/matching-selection-snapshot/sqlite-source-manifest.json'
    assert sha256(raw(manifest_path)).hexdigest() == 'de3944988def848c59c98cb8c2ab02f048d53cab406d6dc20de0f02dea6c7ada'
    manifest = read(manifest_path)
    assert manifest['source_commit'] == SOURCE and len(manifest['inputs']) == 63
    expected_pins = {key: value['sha256'] for key, value in manifest['inputs'].items()}
    assert result['source_before_sha256'] == result['snapshot_after_sha256'] == result['original_after_sha256'] == expected_pins
    for name, pin in manifest['inputs'].items():
        assert sha256(raw(OWNER / name)).hexdigest() == pin['sha256']
        source_raw = raw(PRIVATE / 'source' / name)
        assert sha256(source_raw).hexdigest() == pin['sha256']
        assert sha1(b'blob ' + str(len(source_raw)).encode() + b'\0' + source_raw).hexdigest() == pin['git_blob']
    assert len(result['loaded_uta_origins']) == 18 and all(value in expected_pins for value in result['loaded_uta_origins'].values())
    data, err = raw(PUBLIC / 'stdout.txt'), raw(PUBLIC / 'stderr.txt')
    assert len(data) == 76270 and sha256(data).hexdigest() == '6bf03110cad36fc4607c03a3ed96dc742813a48cd084ae3bcfd89463344a025b' and not err
    lines = [loads(line) for line in data.splitlines()]
    assert len(lines) == 472 and lines[0]['event'] == 'BEGIN_SQLITE_ONCE' and lines[-1]['event'] == 'END_SQLITE_ONCE'
    checks = [row for row in lines if row['event'] == 'SQLITE_CHECKPOINT']
    assert len(checks) == result['checkpoints'] == 470
    execution = read(PUBLIC / 'execution.json')
    assert type(execution['actual_exit_status']) is int and execution['actual_exit_status'] == 0
    assert execution['automatic_retries'] == 0 and execution['actual_SQL_scope_invocations'] == 1
    assert execution['outer_monotonic_lifecycle_elapsed_ns'] is None
    assert execution['begin'] == lines[0] and execution['end'] == lines[-1]
    assert result['driver_elapsed_seconds'] == 10.072730762010906 < lines[-1]['driver_elapsed_seconds'] == 10.144206064011087 < 30
    assert result['max_observed_logical_bytes'] == 8563621 < lines[-1]['max_observed_logical_bytes'] == 8602820 < 67108864
    descriptor = result['runtime_descriptor']
    assert descriptor['sqlite_module']['kind'] == 'builtin' and descriptor['sqlite_module']['sha256'] is None
    assert descriptor['loaded_libraries'] is None and descriptor['loaded_libraries_status'] == 'NOT_OBSERVED'
    assert descriptor['runtime_attestation_complete'] is False and descriptor['sqlite_version'] == '3.53.1'
    assert descriptor['python_executable']['sha256'] == 'fa67443527ed9647f760d807e2a38f26340757123e643c4639cf273ed15d5ea7'
    assert result['actual_affinity'] == [0] and result['forbidden_imports'] == [] and result['active_threads_at_end'] == 1
    reports = {}
    outcomes = []
    for case in ('fifo-stp-partial', 'reduce-only-cross-cancel', 'second-leg-freeze', 'no-liquidity-halt'):
        for mode in ('scan', 'snapshot'):
            report = read(PUBLIC / 'report-originals' / (case + '-' + mode + '.json'))
            assert report['case'] == case and report['mode'] == mode
            outcomes.append(financial_check(report))
            reports[case, mode] = report
        left, right = (reports[case, mode] for mode in ('scan', 'snapshot'))
        assert left['final']['economic_projection'] == right['final']['economic_projection']
        assert strip_times(left['final']['risks']) == strip_times(right['final']['risks'])
    counts = {mode: {'matches': sum(x['matches'] for x in outcomes if x['mode'] == mode),
                     'paired_fills': sum(x['paired_fills'] for x in outcomes if x['mode'] == mode)} for mode in ('scan', 'snapshot')}
    assert all(value == {'matches': 6, 'paired_fills': 12} for value in counts.values())
    assert result['production_approved'] is False and result['performance_accepted'] is False
    return {'status': 'SCOPED_ACTUAL_SQLITE_EVIDENCE_PASS', 'owner_seal_commit': SEAL, 'source_commit': SOURCE,
            'Git_bound_public_files': len(git), 'sealed_files': 17, 'byte_exact_private_report_copies': 11,
            'private_report_bytes': 4906804, 'private_inventory_bytehash_entries': 82,
            'snapshot_source_pins': 63, 'captured_loaded_UTA_origins': 18, 'captured_stdout_bytes': 76270,
            'checkpoint_count': 470, 'captured_exit': 0, 'per_mode': counts, 'case_reviews': outcomes,
            'independent_data_reader_uses_no_UTA_core': True, 'reviewer_SQL_connections': 0,
            'reviewer_target_reexecutions': 0, 'reviewer_PID_network_probes': 0,
            'past_native_execution_evidence': 'fixed source plus captured outputs and exported SQL rows; no independent live kernel or SQL reexecution',
            'driver_end_seconds': lines[-1]['driver_elapsed_seconds'], 'outer_monotonic_seconds': None,
            'kernel_directory_quota_proven': False, 'performance_accepted': False, 'production_approved': False}


if __name__ == '__main__':
    print(json.dumps(main(), sort_keys=True, indent=2))
