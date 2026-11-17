"""Independent real-process partial liquidation, using only synthetic funds.

Expected cash, fees and remaining quantities are hand-computed/Fraction values.
No financial result, execution, clock or matching function is mocked.
"""
import copy
from datetime import datetime, timezone
from decimal import Decimal as D
from fractions import Fraction as F
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from time import monotonic, sleep
import unittest

from uta.durable_process import DurableProcessRouter
from uta.examples import synthetic_policy
from uta.market import MarketSnapshot
from uta.models import AssetSpec, InstrumentSpec
from uta.reconciliation import reconcile_exchange
from uta.storage import Database


class ReadOnlyAuthorityDatabase(Database):
    def transaction(self):
        return self.read_transaction()


class ManagedPartialLiquidationTests(unittest.TestCase):
    def wait_for(self, predicate, description, timeout=12):
        deadline = monotonic() + timeout
        while monotonic() < deadline:
            value = predicate()
            if value:
                return value
            sleep(.02)
        self.fail('deadline waiting for ' + description + ': ' + str(self.router.diagnostics()))

    def market(self, version, mark):
        # Each publish is a fresh synthetic observation, including after kill;
        # no old timestamp is extended and no fake service clock is installed.
        return MarketSnapshot(version, datetime.now(timezone.utc),
            {'USD': AssetSpec(D(1), D(1)), 'BTC': AssetSpec(D(mark), D('.8'))},
            {'BTC-PERP': InstrumentSpec(D(mark), D('.1'), D('.05'))})

    def publish_activate(self, version, mark):
        published = self.router.publish_market(self.market(version, mark), timeout=12)
        self.assertFalse(published['publishing'], published)
        self.assertTrue(published['halted'])
        self.assertFalse(self.router.set_kill_switch(False, timeout=12)['halted'])

    def submit(self, account, command, order, quantity, price, *, reduce_only=False):
        queued = self.router.submit_order(account, command, order, 'BTC-PERP', D(quantity), D(price),
                                          reduce_only=reduce_only)
        self.assertEqual(queued['ack'], 'durably_queued')
        terminal = self.router.wait(command, account_id=account, timeout=12)
        self.assertEqual(terminal['state'], 'SUCCEEDED', terminal)
        return terminal

    def snapshot(self):
        with self.router._database(0).read_transaction() as connection:
            positions = {row['account_id']: F(row['quantity']) for row in connection.execute(
                "SELECT account_id,quantity FROM uta_positions WHERE symbol='BTC-PERP'")}
            liquidation = connection.execute('SELECT state FROM uta_liquidation_accounts WHERE account_id=?',
                                              (self.victim,)).fetchone()
            matches = [dict(row) for row in connection.execute('SELECT * FROM uta_matches ORDER BY sequence')]
            return dict(positions=positions, state=liquidation[0] if liquidation else None, matches=matches,
                cash=F(connection.execute("SELECT units FROM ledger_balances WHERE account=? AND asset='USD'",
                                          ('customer:' + self.victim,)).fetchone()[0]) / 10**8,
                writer_time=connection.execute('SELECT observed_ns FROM writer_fence_lease').fetchone()[0])

    def test_managed_partial_liquidation_survives_real_worker_kill_and_reconciles(self):
        self.run_liquidation(decision_audit=False)

    def test_required_audit_partial_liquidation_replays_historical_decisions_after_restart(self):
        self.run_liquidation(decision_audit=True)

    def run_liquidation(self, *, decision_audit):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        path = Path(temporary.name) / 'managed-liquidation'
        catalog, rules = synthetic_policy()
        templates = {}
        def bootstrap(router):
            same = [name for name in ('party-' + str(index) for index in range(100))
                    if router.shard_for(name) == 0]
            self.victim, self.peer = same[:2]
            self.ghost = next(name for name in ('ghost-' + str(index) for index in range(100))
                              if router.shard_for(name) == 1)
            for account, cash in ((self.victim, '1000'), (self.peer, '100000'), (self.ghost, '123')):
                router.create_account(account)
                router.deposit(account, 'synthetic-capital', 'USD', D(cash))
            templates.update(enumerate(router._services))
        audit_option = {'decision_audit': decision_audit}
        self.router = DurableProcessRouter.initialize(path, 2, {'USD': 8, 'BTC': 8}, managed=True,
            bootstrap=bootstrap, product_catalog=catalog, portfolio_rules=rules,
            lease_seconds=.6, poll_interval=.01, background_interval=.05,
            reserve_cache_size=32, market_cache_size=4, **audit_option)
        self.addCleanup(self.router.close)
        self.router.start()
        self.publish_activate(1, '100')
        workers = self.router.diagnostics()['workers']
        self.assertEqual(len({row['pid'] for row in workers}), 2)
        self.assertTrue(all(row['pid'] not in (None, os.getpid()) and row['owner_pid'] == row['pid'] for row in workers))

        self.submit(self.victim, 'open-victim', 'long', '90', '100')
        self.submit(self.peer, 'open-peer', 'short', '-90', '100')
        self.wait_for(lambda: len(self.snapshot()['matches']) == 1, 'the actual opening paired trade')
        opened = self.snapshot()
        self.assertEqual(opened['positions'], {self.victim: F(90), self.peer: F(-90)})
        self.assertEqual(opened['cash'], F('996.4'))  # 1000 - 90*100*.0004.

        self.publish_activate(2, '90')
        self.wait_for(lambda: self.snapshot()['state'] == 'LIQUIDATING', 'persisted account risk freeze')
        self.router.submit_order(self.victim, 'frozen-new-risk', 'must-not-exist', 'BTC-PERP', D(1), D(90))
        rejected = self.router.wait('frozen-new-risk', account_id=self.victim, timeout=12)
        self.assertEqual((rejected['state'], rejected['error']['code']), ('REJECTED', 'account_frozen'))
        self.submit(self.peer, 'depth-one', 'first-depth', '45', '90', reduce_only=True)
        self.wait_for(lambda: len(self.snapshot()['matches']) == 2, 'first actual partial liquidation')
        partial = self.snapshot()
        self.assertEqual(partial['positions'], {self.victim: F(45), self.peer: F(-45)})
        self.assertEqual(partial['cash'], F('544.78'))  # 996.4 - 450 - 45*90*.0004.
        self.assertEqual(partial['state'], 'LIQUIDATING')

        # Wait for three distinct committed background writer checkpoints, not
        # merely a sleep, while verifying that no counterparty means no fill.
        checkpoints = {partial['writer_time']}
        def no_fabricated_liquidity():
            state = self.snapshot()
            self.assertEqual(len(state['matches']), 2)
            self.assertEqual(state['positions'][self.victim], F(45))
            self.assertEqual(state['cash'], F('544.78'))
            checkpoints.add(state['writer_time'])
            return len(checkpoints) >= 4
        self.wait_for(no_fabricated_liquidity, 'three real no-liquidity background checkpoints')
        old = self.router.diagnostics()['workers'][0]
        self.router.terminate_worker(0)
        def new_owner():
            current = self.router.diagnostics()['workers'][0]
            return (current['pid'] not in (None, old['pid'], os.getpid()) and current['lease_active']
                    and current['owner_pid'] == current['pid'] and current['generation'] > old['generation'])
        self.wait_for(new_owner, 'a genuinely new PID and fenced generation')
        resumed = self.snapshot()
        self.assertEqual((resumed['positions'][self.victim], len(resumed['matches'])), (F(45), 2))
        self.publish_activate(3, '90')
        self.submit(self.peer, 'depth-two', 'second-depth', '45', '90', reduce_only=True)
        self.wait_for(lambda: len(self.snapshot()['matches']) == 3 and not self.snapshot()['positions']
                      and self.snapshot()['state'] == 'NORMAL', 'confirmed remaining liquidation and recovery')
        final = self.snapshot()
        # Independent complete cashflow: 1000 - opening fee3.6 - loss900 - closing fee3.24.
        self.assertEqual(final['cash'], F('93.16'))
        liquidation = [row for row in final['matches'] if row['sell_account_id'] == self.victim
                       and row['sell_order_id'].startswith('liq:')]
        self.assertEqual(len(liquidation), 2)  # Excludes the 90-unit opening trade.
        self.assertEqual([F(row['quantity']) for row in liquidation], [F(45), F(45)])
        self.assertEqual({F(row['price']) for row in liquidation}, {F(90)})
        self.assertEqual(len({row['trade_id'] for row in final['matches']}), 3)
        if decision_audit:
            self.publish_activate(4, '110')  # Current data differs from archived fill snapshots.
        self.router.close()

        for shard in (0, 1):
            # Clone the original service codec/policy, never invoke a financial
            # constructor to repair missing schema before reconciliation.
            view = copy.copy(templates[shard])
            view.database = ReadOnlyAuthorityDatabase(self.router._database(shard).path)
            view.ledger = copy.copy(view.ledger)
            view.ledger.database = view.database
            report = reconcile_exchange(view, matching_only=True)
            self.assertEqual(report['status'], 'passed')
            self.assertEqual((report['matches'], report['paired_fills'], report['positions']),
                             (3, 6, 0) if shard == 0 else (0, 0, 0))
            with view.database.read_transaction() as connection:
                self.assertEqual(sum(int(row[0]) for row in connection.execute("SELECT units FROM ledger_balances WHERE asset='USD'")), 0)
                if shard == 0:
                    self.assertEqual(F(connection.execute("SELECT units FROM ledger_balances WHERE account='system:fees' AND asset='USD'").fetchone()[0]) / 10**8, F('13.68'))
                    self.assertEqual(connection.execute("SELECT COUNT(*) FROM uta_orders WHERE order_id='must-not-exist'").fetchone()[0], 0)
                    self.assertEqual(connection.execute("SELECT COUNT(*) FROM uta_fills WHERE account_id=?", (self.victim,)).fetchone()[0], 3)
                    self.assertEqual(connection.execute("SELECT COUNT(*) FROM uta_events WHERE event_type='FILL_APPLIED'").fetchone()[0], 6)
                else:
                    self.assertEqual(connection.execute('SELECT COUNT(*) FROM uta_orders').fetchone()[0], 0)
                    self.assertEqual(F(connection.execute("SELECT units FROM ledger_balances WHERE account=? AND asset='USD'", ('customer:' + self.ghost,)).fetchone()[0]) / 10**8, F(123))
            if decision_audit and shard == 0:
                self.check_audited_cashflow(view.database)

    def check_audited_cashflow(self, database):
        from uta.decision_audit import DecisionAudit
        audit = DecisionAudit(database)
        with database.read_transaction() as connection:
            self.assertEqual(connection.execute('SELECT version FROM uta_schema').fetchone()[0], 3)
            self.assertEqual(connection.execute('SELECT COUNT(*) FROM uta_orders WHERE admission_decision_id IS NULL').fetchone()[0], 0)
            self.assertEqual(connection.execute('SELECT COUNT(*) FROM uta_fills WHERE execution_decision_id IS NULL').fetchone()[0], 0)
            orders = connection.execute('SELECT COUNT(*) FROM uta_orders').fetchone()[0]
            fills = connection.execute('SELECT COUNT(*) FROM uta_fills').fetchone()[0]
            self.assertEqual(connection.execute('SELECT COUNT(*) FROM uta_risk_decisions').fetchone()[0], orders + fills)
            victim_fills = [dict(row) for row in connection.execute('SELECT * FROM uta_fills WHERE account_id=? ORDER BY rowid', (self.victim,))]
            self.assertEqual(json.loads(connection.execute('SELECT payload FROM uta_market').fetchone()[0])['version'], 4)
        self.assertEqual(len(victim_fills), 3)
        before_cash = ('1000', '996.4', '544.78')
        after_cash = ('996.4', '544.78', '93.16')
        before_position, after_position = (0, 90, 45), (90, 45, 0)
        before_equity, after_equity = ('1000', '96.4', '94.78'), ('996.4', '94.78', '93.16')
        for index, fill in enumerate(victim_fills):
            with self.subTest(fill=index):
                identity = fill['execution_decision_id']
                record = audit.decision(identity)
                self.assertEqual((record['kind'], record['account_id'], record['business_id']),
                                 ('FILL_CONFIRMED', self.victim, fill['fill_id']))
                self.assertEqual(F(record['summary']['fee']), F(('3.6', '1.62', '1.62')[index]))
                self.assertEqual(F(record['summary']['realized_pnl']), F((0, -450, -450)[index]))
                for side, cash, quantity in (('before', before_cash[index], before_position[index]),
                                              ('after', after_cash[index], after_position[index])):
                    archived = record['inputs'][side]
                    self.assertEqual(F(archived['balances']['USD']), F(cash))
                    self.assertEqual(F(archived['positions'].get('BTC-PERP', {}).get('quantity', '0')), F(quantity))
                archived_market = json.loads(audit.market(record['market_snapshot_id'])['payload'])
                self.assertEqual(archived_market['version'], (1, 2, 3)[index])
                self.assertEqual(F(archived_market['instruments']['BTC-PERP']['mark_price']), F((100, 90, 90)[index]))
                policy = audit.policy_record(record['policy_id'])
                self.assertEqual((policy['scales']['USD'], F(policy['fee_rate'])), (8, F('.0004')))
                self.assertFalse(audit.artifact(record['artifact_id'])['signed'])
                self.assertIn('service.py', audit.artifact(record['artifact_id'])['source_files'])
                replayed = audit.replay(identity)
                self.assertTrue(replayed['matches'], replayed['differences'])
                self.assertEqual(F(replayed['values']['before']['equity']), F(before_equity[index]))
                self.assertEqual(F(replayed['values']['after']['equity']), F(after_equity[index]))
