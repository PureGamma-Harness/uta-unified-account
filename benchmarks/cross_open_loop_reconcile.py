"""New RO reopen, existing-source native rebuild and independent fixed oracle."""
from collections import Counter
from decimal import Decimal as D
from fractions import Fraction as F
from hashlib import sha256
import json

from benchmarks.cross_open_loop_model import accounts, order_reserve
from benchmarks.cross_open_loop_checks import verify_admission_link
from benchmarks.run_managed_benchmark import verify_ledger, command_technical_diagnostics
from uta.decision_audit import DecisionAudit
from uta.durable_views import _ExistingViewDatabase
from uta.existing_services import open_existing_services


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def reconcile(router, rows):
    by_id = {r['command_id']: r for r in rows}
    reports, all_commands, accepted_ids, rejected_ids, pending_ids = [], [], set(), set(), set()
    for shard in (0, 1):
        database = _ExistingViewDatabase(router._control._path(shard), timeout=.2)
        with database.read_transaction() as connection:
            require(connection.execute('PRAGMA integrity_check').fetchone()[0] == 'ok', 'integrity failure')
            require(connection.execute('PRAGMA foreign_key_check').fetchone() is None, 'foreign key failure')
            DecisionAudit.validate(connection)
            services = open_existing_services(database, connection=connection)
            exchange = services.exchange
            market = exchange._market(connection)  # Native default UTC/TTL5; no repaired clock or quote.
            quote = connection.execute('SELECT payload FROM uta_market WHERE singleton=1').fetchone()[0]
            commands = [dict(r) for r in connection.execute('SELECT * FROM uta_command_inbox ORDER BY sequence')]
            all_commands.extend({'shard': shard, **r} for r in commands)
            orders = {(r['account_id'], r['order_id']): dict(r) for r in connection.execute('SELECT * FROM uta_orders')}
            versions, reserves, per_account_cids = {}, Counter(), {}
            success_keys = set()
            for command in commands:
                if command['kind'] != 'SUBMIT_ORDER':
                    require(command['kind'] in ('PUBLISH_MARKET', 'SET_HALT') and command['state'] == 'SUCCEEDED', 'failed or unknown control receipt')
                    continue
                cid = command['command_id']; require(cid in by_id, 'unoffered CID persisted')
                arrival = by_id[cid]; payload = json.loads(command['payload'])
                require((payload['account_id'], payload['order_id'], payload['symbol'], F(payload['quantity']), F(payload['limit_price'])) ==
                        (arrival['account_id'], arrival['order_id'], 'BTC-PERP', F(arrival['quantity']), F(100)), 'CID payload changed')
                key = payload['account_id'], payload['order_id']
                per_account_cids.setdefault(key[0], []).append(cid)
                if command['state'] == 'SUCCEEDED':
                    require(not arrival['expected_business_rejection'], 'off-step product order accepted')
                    order = orders.get(key); receipt = json.loads(command['result'])
                    require(order is not None and order['status'] == 'OPEN' and F(order['filled_quantity']) == 0,
                            'accepted order/reservation missing or executed')
                    amount = order_reserve(arrival['quantity'], arrival['limit_price'])
                    require(F(receipt['reserved_margin']) == amount and receipt['order_id'] == key[1]
                            and receipt['account_id'] == key[0], 'persistent receipt reserve differs from hand oracle')
                    decision = connection.execute('SELECT * FROM uta_risk_decisions WHERE decision_id=?', (order['admission_decision_id'],)).fetchone()
                    require(decision is not None and decision['kind'] == 'ORDER_ACCEPTED' and decision['business_id'] == key[1]
                            and decision['post_version'] == order['version'] and decision['post_version'] == decision['pre_version'] + 1,
                            'accepted order lacks matching audit/version')
                    verify_admission_link(arrival,command,order,dict(decision),amount)
                    archived=connection.execute('SELECT payload,content_digest FROM uta_market_history WHERE snapshot_id=?', (decision['market_snapshot_id'],)).fetchone()
                    require(archived is not None and sha256(archived['payload'].encode()).hexdigest()==archived['content_digest']
                            and decision['market_snapshot_id']=='market:'+archived['content_digest'], 'decision market source hash differs')
                    accepted_ids.add(cid); success_keys.add(key); reserves[key[0]] += amount
                    versions.setdefault(key[0], []).append(order['version'])
                else:
                    require(key not in orders, 'non-success receipt has an order effect')
                    if command['state'] == 'PENDING':
                        pending_ids.add(cid)
                    elif command['state'] == 'REJECTED':
                        error = json.loads(command['error'])
                        require(arrival['expected_business_rejection'] and error['code'] == 'product_rejected' and error['status'] == 409,
                                'unexpected terminal rejection; do not hide market/control failure as workload business mix')
                        rejected_ids.add(cid)
                    else:
                        raise AssertionError('quarantined/technical command cannot qualify')
            require(set(orders) == success_keys, 'orphan or duplicate accepted order')
            details = []
            for account in accounts():
                if router.shard_for(account) != shard:
                    continue
                ordered = [r['command_id'] for r in rows if r['account_id'] == account and r['command_id'] in per_account_cids.get(account, [])]
                require(per_account_cids.get(account, []) == ordered, 'native persisted per-account FIFO differs from generator dispatch order')
                n = len(versions.get(account, []))
                require(sorted(versions.get(account, [])) == list(range(4, 4+n)), 'admission versions are not one durable bump each')
                native = exchange._risk(connection, account, market)
                financial = dict(accounting_equity=F(200), collateral_value=F(181), risk_equity=F(180), loan_value=F(141),
                    principal_value=F(1), interest_value=F(0), cash_deficit_value=F(0), debt_value=F(1), unrealized_pnl=F(0),
                    frozen_value=F(0), initial_margin=F('.1'), maintenance_margin=F('.05'),
                    available_margin=F('179.9')-reserves[account], equity=F(180), open_order_margin=reserves[account], margin_ratio=F(3600))
                other = {'account_version','market_version','observed_at','market_id','borrowable','status','risk_mode','rule_id','rule_version','catalog_version'}
                require(set(native) == set(financial) | other, 'unknown/missing configured Cross risk field')
                require(all(F(native[k]) == v for k,v in financial.items()), 'configured Cross hand risk mismatch')
                require(native['account_version'] == 3+n and native['market_version'] == market.version
                    and native['observed_at'] == market.observed_at.isoformat() and native['status'] == 'HEALTHY'
                    and native['risk_mode'] == 'phase1_cross' and native['rule_id'] == exchange.portfolio_rules.rule_id
                    and native['rule_version'] == native['catalog_version'] == 1
                    and native['market_id'] == f'market-{market.version}@{market.observed_at.isoformat()}', 'risk provenance/state mismatch')
                require({k:F(v) for k,v in native['borrowable'].items()} == {'USD':F(140), 'BTC':F('1.4')}, 'gross discounted LTV borrow oracle differs')
                view = exchange._account(connection, account)
                require({k:F(v) for k,v in view['balances'].items()} == {'USD':F(101), 'BTC':F(1)}
                    and F(view['open_order_margin']) == reserves[account] and view['positions'] == {}, 'gross cash/reserve changed')
                require(view['liabilities'] == {'USD':{'principal':'1','interest':'0','total':'1'}}, 'gross loan components changed')
                details.append({'account_id':account,'accepted_orders':n,'reserve_fraction':str(reserves[account]),'native_risk':native})
            for table in ('uta_positions','uta_fills','uta_matches'):
                require(connection.execute('SELECT COUNT(*) FROM '+table).fetchone()[0] == 0, 'admission-only pilot produced execution')
            ledger_count = verify_ledger(connection)
            require(ledger_count == 7, 'expected one funded pool plus two deposits and one loan per shard account')
            lease = dict(connection.execute('SELECT * FROM writer_fence_lease WHERE singleton=1').fetchone())
            reports.append({'shard':shard,'accounts':details,'ledger_events':ledger_count,'current_market_payload':quote,
                'current_market_sha256':sha256(quote.encode()).hexdigest(),'writer_lease_raw':lease,
                'configured_source_readonly_rebuild':True,'query_only':connection.execute('PRAGMA query_only').fetchone()[0]})
    observed = {r['command_id'] for r in rows if r.get('outcome') == 'accepted_persistent'}
    acknowledged = {r['command_id'] for r in rows if r.get('enqueue_ack_ns') is not None}
    stored = {r['command_id'] for r in all_commands if r['kind']=='SUBMIT_ORDER'}
    require(observed <= accepted_ids and acknowledged <= stored, 'observed committed receipt or enqueue ACK lost on reopen')
    return {'shards':reports,'persisted_accepted_CIDs':sorted(accepted_ids),'persisted_business_rejected_CIDs':sorted(rejected_ids),
        'pending_original_CIDs':sorted(pending_ids),'unobserved_success_CIDs_found_after_stop':sorted(accepted_ids-observed),
        'offered_CIDs_absent_after_reopen':sorted(set(by_id)-stored),'technical_facts':command_technical_diagnostics(all_commands),
        'read_only_reopen':True,'no_missing_command_auto_rebuild':True}
