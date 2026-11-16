"""Independent exact-money and durable-command contract checks.

All fixtures are synthetic. Expected balances and capacity use integer minor
units or Fraction, never production valuation/reserve/admission helpers.
"""
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from decimal import Decimal as D, Inexact, Rounded, localcontext
from fractions import Fraction as F
from pathlib import Path
import random
import os
import sqlite3
from tempfile import TemporaryDirectory
from time import monotonic, sleep
import unittest
from unittest.mock import patch

from uta.ledger import Ledger, LedgerError, Posting
from uta.examples import synthetic_policy
from uta.market import MarketSnapshot
from uta.models import AssetSpec, InstrumentSpec
from uta.service import ExchangeService, ServiceError
from uta.storage import Database
from formal.explore_durable_commands import explore


def minor_units(value, scale):
    return D((int(value < 0), tuple(map(int, str(abs(value)))), -scale))


class IndependentReplayPrecisionTests(unittest.TestCase):
    def test_original_precision_replays_exactly_and_keeps_future_balance_limit(self):
        for width in (38, 40, 60):
            scale, maximum = 18, 10**width - 1
            amount, one = minor_units(maximum, scale), minor_units(1, scale)
            ledger = Ledger({'USD': scale}, unit_digits=width)
            original = [Posting('customer', 'USD', amount),
                        Posting('source', 'USD', amount.copy_negate())]
            ledger.post('capital', original)
            ledger.post('one-unit-payment', [Posting('customer', 'USD', one.copy_negate()),
                                             Posting('merchant', 'USD', one)])
            with self.subTest(width=width), localcontext() as context:
                context.prec, context.Emax, context.Emin = 1, 2, -2
                context.traps[Inexact] = context.traps[Rounded] = True
                restored = Ledger.replay({'USD': scale}, ledger.journal(), unit_digits=width)
                self.assertEqual(F(restored.balance('customer', 'USD')), F(maximum - 1, 10**scale))
                self.assertEqual(F(restored.balance('merchant', 'USD')), F(1, 10**scale))
                self.assertEqual(F(restored.balance('source', 'USD')), F(-maximum, 10**scale))
                self.assertEqual(restored.journal(), ledger.journal())
                self.assertIs(restored.post('capital', list(reversed(original))), restored.journal()[0])
                before = restored.journal()
                two = minor_units(2, scale)
                with self.assertRaisesRegex(LedgerError, 'balance exceeds supported range'):
                    restored.post('overflow', [Posting('customer', 'USD', two),
                                               Posting('new-source', 'USD', two.copy_negate())])
                self.assertEqual(restored.journal(), before)
                self.assertEqual(F(restored.balance('customer', 'USD')), F(maximum - 1, 10**scale))

    def test_wide_history_cannot_implicitly_expand_default_precision(self):
        amount = minor_units(10**40 - 1, 18)
        ledger = Ledger({'USD': 18}, unit_digits=60)
        ledger.post('wide', [Posting('customer', 'USD', amount),
                             Posting('source', 'USD', amount.copy_negate())])
        with self.assertRaises(LedgerError):
            Ledger.replay({'USD': 18}, ledger.journal())

    def test_replay_rejects_invalid_precision_instead_of_inferencing_history(self):
        for width in (True, 37, 61, 40.0, '40', None):
            with self.subTest(width=width), self.assertRaises(LedgerError):
                Ledger.replay({'USD': 18}, (), unit_digits=width)


class IndependentDurableProtocolModelTests(unittest.TestCase):
    def test_safe_bounded_protocol_and_five_negative_controls(self):
        safe = explore()
        self.assertIsNone(safe['violation'])
        self.assertEqual((safe['states'], safe['transitions']), (817, 2372))
        for mutant in ('early_accept', 'split_terminal', 'duplicate_retry', 'skip_fence', 'skip_fifo'):
            with self.subTest(mutant=mutant):
                result = explore(mutant)
                self.assertIsNotNone(result['violation'])
                self.assertTrue(result['counterexample'])


def independent_reserve(quantity, limit):
    quantity, limit = F(quantity), F(limit)
    fee_whole, fee_remainder = divmod(abs(quantity) * limit * F(1, 2500) * 10**8, 1)
    fee = F(int(fee_whole) + bool(fee_remainder), 10**8)
    return abs(quantity) * max(F(100), limit) / 10 + max(F(0), quantity * (limit - 100)) + fee


class CashCommandReference:
    def __init__(self, cash):
        self.cash = {account: F(amount) for account, amount in cash.items()}
        self.orders = {}
        self.versions = {account: 1 for account in cash}
        self.new_orders = self.cancelled = 0

    def held(self, account):
        return sum((value['margin'] for (owner, _), value in self.orders.items()
                    if owner == account and value['status'] == 'OPEN'), F(0))

    def apply(self, kind, account, identifier, quantity=None, price=None):
        key = account, identifier
        previous = self.orders.get(key)
        if kind == 'cancel':
            if previous is None:
                return 'order_not_found', None
            if previous['status'] == 'OPEN':
                previous['status'] = 'CANCELLED'
                self.versions[account] += 1
                self.cancelled += 1
            return None, 'CANCELLED'
        payload = F(quantity), F(price)
        if previous is not None:
            if payload != previous['payload']:
                return 'idempotency_conflict', None
            return None, previous['status']
        margin = independent_reserve(quantity, price)
        if margin > self.cash[account] - self.held(account):
            return 'insufficient_margin', None
        self.orders[key] = dict(payload=payload, margin=margin, status='OPEN')
        self.versions[account] += 1
        self.new_orders += 1
        return None, 'OPEN'


class LostCommitReplyDatabase(Database):
    fail_after_commit = False

    @contextmanager
    def transaction(self):
        with super().transaction() as connection:
            yield connection
        if self.fail_after_commit:
            self.fail_after_commit = False
            raise RuntimeError('independent test lost the real COMMIT reply')


class IndependentDurableCommandTests(unittest.TestCase):
    def setUp(self):
        from uta.durable_commands import CommandExecutionError, QueueStore
        from uta.writer_fence import WriterFence
        self.QueueStore, self.ExecutionError = QueueStore, CommandExecutionError
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.path = Path(temporary.name) / 'durable.sqlite3'
        self.now = datetime(2026, 11, 16, tzinfo=timezone.utc)
        self.catalog, self.rules = synthetic_policy()
        self.database = LostCommitReplyDatabase(self.path)
        self.service = self.reopen()
        self.service.publish_market(self.market())
        self.service.set_kill_switch(False)
        self.queue = QueueStore(self.database, clock=lambda: self.now, initialize=True)
        self.fence = WriterFence(self.database)
        self.fence.enable('independent-inbox')
        token = self.fence.acquire('independent-worker', ttl_seconds=3600)
        self.writer_database = self.database.for_writer(token)
        self.service = self.reopen()

    def reopen(self):
        return ExchangeService(getattr(self, 'writer_database', self.database), {'USD': 8, 'BTC': 8}, clock=lambda: self.now,
            product_catalog=self.catalog, portfolio_rules=self.rules, reserve_cache_size=16, market_cache_size=4)

    def market(self, version=1):
        return MarketSnapshot(version, self.now,
            {'USD': AssetSpec(D(1), D(1)), 'BTC': AssetSpec(D(100), D('.8'))},
            {'BTC-PERP': InstrumentSpec(D(100), D('.1'), D('.05'))})

    def fund(self, account, amount):
        self.service.create_account(account)
        self.service.deposit(account, 'capital', 'USD', D(amount))

    def enqueue(self, command, order, account='alice', quantity='1', price='100'):
        return self.queue.enqueue_submit(account, command, order, 'BTC-PERP', D(quantity), D(price))

    def financial_rows(self):
        with self.database.transaction() as connection:
            return {table: [tuple(row) for row in connection.execute('SELECT * FROM ' + table)]
                    for table in ('uta_accounts', 'uta_orders', 'uta_positions', 'uta_fills',
                                  'uta_events', 'ledger_events', 'ledger_balances')}

    def drain(self):
        results = []
        for _ in range(512):
            result = self.queue.process_one(self.service)
            if result is None:
                return results
            results.append(result)
        self.fail('bounded synthetic trace did not drain')

    def assert_error(self, code, call, *args, **kwargs):
        with self.assertRaises(ServiceError) as error:
            call(*args, **kwargs)
        self.assertEqual(error.exception.code, code)

    def test_durable_queue_ack_has_no_order_or_reserve_and_survives_service_restart(self):
        self.fund('alice', '10.04')
        before = self.financial_rows()
        queued = self.enqueue('command', 'order')
        self.assertEqual((queued['ack'], queued['state']), ('durably_queued', 'PENDING'))
        self.assertIsNone(queued['result'])
        self.assertEqual(self.financial_rows(), before)
        self.assertEqual(F(self.service.account('alice')['open_order_margin']), F(0))
        self.queue = self.QueueStore(Database(self.path), clock=lambda: self.now)
        self.service = self.reopen()
        self.assertEqual(self.queue.status('command'), queued)
        completed = self.queue.process_one(self.service)
        self.assertEqual(completed['state'], 'SUCCEEDED')
        self.assertEqual(completed['result']['order_id'], 'order')
        self.assertEqual(F(self.service.account('alice')['open_order_margin']), F('10.04'))

    def test_120_seeded_commands_match_independent_per_account_cash_book_and_fifo(self):
        cash = {'alice': '20.08', 'bob': '10.04', 'carol': '30.12'}
        for account, amount in cash.items():
            self.fund(account, amount)
        reference = CashCommandReference(cash)
        generator = random.Random(16112026)
        expected = {}
        for index in range(120):
            account = generator.choice(tuple(cash))
            identifier = 'order-' + str(generator.randrange(8))
            command = 'command-' + str(index)
            if generator.randrange(4) == 0:
                expected[command] = reference.apply('cancel', account, identifier)
                self.queue.enqueue_cancel(account, command, identifier)
            else:
                quantity = generator.choice(('.1', '-.1', '.25', '-.25', '1', '-1'))
                price = generator.choice(('99', '100', '101'))
                expected[command] = reference.apply('submit', account, identifier, quantity, price)
                self.enqueue(command, identifier, account, quantity, price)
        with localcontext() as context:
            context.prec, context.Emax, context.Emin = 1, 2, -2
            context.traps[Inexact] = context.traps[Rounded] = True
            results = self.drain()
        self.assertEqual(len(results), 120)
        for command, (code, status) in expected.items():
            record = self.queue.status(command)
            with self.subTest(command=command):
                if code:
                    self.assertEqual(record['state'], 'REJECTED')
                    self.assertEqual(record['error']['code'], code)
                    self.assertIsNone(record['result'])
                else:
                    self.assertEqual(record['state'], 'SUCCEEDED')
                    self.assertEqual(record['result']['status'], status)
        for account in cash:
            actual = self.service.account(account)
            self.assertEqual(F(actual['balances']['USD']), F(cash[account]))
            self.assertEqual(F(actual['open_order_margin']), reference.held(account))
            self.assertEqual(actual['version'], reference.versions[account])
        events = self.service.events(limit=1000)
        self.assertEqual(sum(row['event_type'] == 'ORDER_ACCEPTED' for row in events), reference.new_orders)
        self.assertEqual(sum(row['event_type'] == 'ORDER_CANCELLED' for row in events), reference.cancelled)
        self.service.ledger.verify()

    def test_same_command_rejection_stays_terminal_after_capacity_recovers(self):
        self.fund('alice', '10.04')
        self.enqueue('first-command', 'first')
        self.enqueue('rejected-command', 'second')
        self.drain()
        rejected = self.queue.status('rejected-command')
        self.assertEqual((rejected['state'], rejected['error']['code']), ('REJECTED', 'insufficient_margin'))
        self.queue.enqueue_cancel('alice', 'cancel-command', 'first')
        self.drain()
        before = self.financial_rows()
        self.assertEqual(self.enqueue('rejected-command', 'second'), rejected)
        self.assertIsNone(self.queue.process_one(self.service))
        self.assertEqual(self.financial_rows(), before)
        # A new command is an explicit new decision; the previously rejected
        # order ID has no persisted financial order and can now be admitted.
        self.enqueue('new-command', 'second')
        self.drain()
        self.assertEqual(self.queue.status('new-command')['state'], 'SUCCEEDED')
        self.assertEqual(F(self.service.account('alice')['open_order_margin']), F('10.04'))

    def test_equivalent_retry_and_conflicting_command_never_add_financial_effect(self):
        self.fund('alice', '20.08')
        original = self.enqueue('same-command', 'same-order')
        self.assertEqual(self.enqueue('same-command', 'same-order', quantity='1.00', price='100.00'), original)
        self.assert_error('idempotency_conflict', self.enqueue, 'same-command', 'same-order', quantity='2')
        self.drain()
        terminal = self.queue.status('same-command')
        self.queue.enqueue_cancel('alice', 'later-cancel', 'same-order')
        self.drain()
        before = self.financial_rows()
        self.assertEqual(self.enqueue('same-command', 'same-order'), terminal)
        self.assertEqual(terminal['result']['status'], 'OPEN')
        self.assertEqual(self.service.order('alice', 'same-order')['status'], 'CANCELLED')
        self.assert_error('idempotency_conflict', self.queue.enqueue_cancel, 'alice', 'same-command', 'same-order')
        self.assertIsNone(self.queue.process_one(self.service))
        self.assertEqual(self.financial_rows(), before)
        self.assertEqual(F(self.service.account('alice')['open_order_margin']), F(0))

    def test_queued_order_uses_execution_time_market_and_old_rejection_does_not_revive(self):
        self.fund('alice', '10.04')
        self.enqueue('queued-with-fresh-market', 'order')
        before = self.financial_rows()
        self.now += timedelta(seconds=6)
        rejected = self.queue.process_one(self.service)
        self.assertEqual((rejected['state'], rejected['error']['code'], rejected['error']['status']),
                         ('REJECTED', 'market_unavailable', 503))
        self.assertEqual(self.financial_rows(), before)
        self.service.publish_market(self.market(version=2))
        self.assertEqual(self.enqueue('queued-with-fresh-market', 'order'), rejected)
        self.assertIsNone(self.queue.process_one(self.service))
        self.enqueue('explicit-new-decision', 'order')
        self.assertEqual(self.queue.process_one(self.service)['state'], 'SUCCEEDED')
        self.assertEqual(F(self.service.account('alice')['open_order_margin']), F('10.04'))

    def test_business_rejection_after_attempted_financial_writes_rolls_back_only_finance(self):
        self.fund('alice', '20.08')
        self.enqueue('late-command', 'late-order')
        before = self.financial_rows()
        event = self.service._event
        def late_rejection(connection, kind, account, payload):
            event(connection, kind, account, payload)
            if kind == 'ORDER_ACCEPTED':
                raise ServiceError('insufficient_margin', 'independent late policy rejection', 409)
        with patch.object(self.service, '_event', side_effect=late_rejection):
            result = self.queue.process_one(self.service)
        self.assertEqual((result['state'], result['error']['code']), ('REJECTED', 'insufficient_margin'))
        self.assertEqual(self.financial_rows(), before)
        self.assertEqual(self.queue.status('late-command'), result)

    def test_unknown_after_real_commit_preserves_terminal_during_failure_recording_and_retry(self):
        self.fund('alice', '10.04')
        self.enqueue('unknown-command', 'order')
        self.writer_database.fail_after_commit = True
        with self.assertRaises(self.ExecutionError):
            self.queue.process_one(self.service)
        terminal = self.queue.status('unknown-command')
        self.assertEqual(terminal['state'], 'SUCCEEDED')
        before = self.financial_rows()
        self.queue.record_failure(self.service, 'unknown-command', max_attempts=1)
        self.queue = self.QueueStore(Database(self.path), clock=lambda: self.now)
        self.service = self.reopen()
        self.assertEqual(self.enqueue('unknown-command', 'order'), terminal)
        self.assertIsNone(self.queue.process_one(self.service))
        self.assertEqual(self.financial_rows(), before)

    def test_backoff_holds_only_its_account_head_until_equal_deadline(self):
        self.fund('alice', '20.08')
        self.fund('bob', '20.08')
        self.enqueue('poison-head', 'first')
        self.queue.enqueue_cancel('alice', 'behind-head', 'first')
        self.enqueue('other-account', 'bob-order', 'bob')
        event = self.service._event
        def fail_first(connection, kind, account, payload):
            event(connection, kind, account, payload)
            if kind == 'ORDER_ACCEPTED' and account == 'alice':
                raise sqlite3.OperationalError('independent rollback before COMMIT')
        with patch.object(self.service, '_event', side_effect=fail_first):
            with self.assertRaises(self.ExecutionError):
                self.queue.process_one(self.service)
        self.queue.record_failure(self.service, 'poison-head', max_attempts=3, backoff_seconds=1)
        result = self.queue.process_one(self.service)
        self.assertEqual(result['command_id'], 'other-account')
        self.assertIsNone(self.queue.process_one(self.service))
        self.assertEqual(self.queue.status('behind-head')['state'], 'PENDING')
        self.now += timedelta(seconds=1)
        self.assertEqual(self.queue.process_one(self.service)['command_id'], 'poison-head')
        self.assertEqual(self.queue.process_one(self.service)['command_id'], 'behind-head')
        self.assertEqual(F(self.service.account('alice')['open_order_margin']), F(0))
        self.assertEqual(F(self.service.account('bob')['open_order_margin']), F('10.04'))

    def test_exhausted_technical_attempts_are_stable_quarantine_not_business_rejection(self):
        self.fund('alice', '10.04')
        self.enqueue('technical', 'order')
        before = self.financial_rows()
        self.queue.record_failure(self.service, 'technical', max_attempts=1)
        terminal = self.queue.status('technical')
        self.assertEqual(terminal['state'], 'QUARANTINED')
        self.assertEqual(terminal['error']['status'], 503)
        self.assertEqual(self.enqueue('technical', 'order'), terminal)
        self.assertIsNone(self.queue.process_one(self.service))
        self.assertEqual(self.financial_rows(), before)


class IndependentWriterLeaseTests(unittest.TestCase):
    def setUp(self):
        from uta.writer_fence import WriterFence, WriterFenceError
        self.WriterFence, self.FenceError = WriterFence, WriterFenceError
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.path = Path(temporary.name) / 'managed.sqlite3'
        self.tick = 1_000_000_000
        self.boot = '11111111-1111-1111-1111-111111111111'
        self.database = Database(self.path, fence_clock_ns=lambda: self.tick, fence_boot_id=self.boot)
        self.now = datetime(2026, 11, 16, tzinfo=timezone.utc)
        self.catalog, self.rules = synthetic_policy()
        self.old_service = self.open_service(self.database)
        self.old_service.publish_market(MarketSnapshot(1, self.now,
            {'USD': AssetSpec(D(1), D(1)), 'BTC': AssetSpec(D(100), D('.8'))},
            {'BTC-PERP': InstrumentSpec(D(100), D('.1'), D('.05'))}))
        self.old_service.set_kill_switch(False)
        self.old_service.create_account('alice')
        self.old_service.deposit('alice', 'capital', 'USD', D('20.08'))
        self.old_service.submit_order('alice', 'existing', 'BTC-PERP', D(1), D(100))
        self.fence = WriterFence(self.database)
        self.fence.enable('independent-authority')

    def open_service(self, database):
        return ExchangeService(database, {'USD': 8, 'BTC': 8}, clock=lambda: self.now,
            product_catalog=self.catalog, portfolio_rules=self.rules, reserve_cache_size=16, market_cache_size=4)

    def acquire(self, owner='first-owner', ttl=1):
        token = self.fence.acquire(owner, ttl_seconds=ttl)
        database = self.database.for_writer(token)
        return token, database, self.open_service(database)

    def test_preexisting_unfenced_service_cannot_write_after_enable_but_still_reads(self):
        before = self.old_service.account('alice'), self.old_service.ledger.journal()
        token, _, writer = self.acquire()
        for call in (
                lambda: self.old_service.deposit('alice', 'forbidden', 'USD', D(1)),
                lambda: self.old_service.submit_order('alice', 'forbidden', 'BTC-PERP', D(1), D(100)),
                lambda: self.old_service.cancel_order('alice', 'existing'),
                lambda: self.open_service(self.database)):
            with self.subTest(call=call), self.assertRaises(self.FenceError):
                call()
        self.assertEqual((self.old_service.account('alice'), self.old_service.ledger.journal()), before)
        writer.deposit('alice', 'authorized', 'USD', D(1))
        self.assertEqual(F(self.old_service.account('alice')['balances']['USD']), F('21.08'))
        self.assertEqual(F(self.old_service.account('alice')['open_order_margin']), F('10.04'))
        self.assertGreaterEqual(token.generation, 1)

    def test_lease_equality_expires_and_financial_changes_roll_back_before_commit(self):
        token, database, writer = self.acquire()
        before = self.old_service.account('alice'), self.old_service.ledger.journal()
        with self.assertRaises(self.FenceError) as failure:
            with database.transaction() as connection:
                writer.ledger.post('uncommitted', [Posting('customer:alice', 'USD', D(1)),
                    Posting('independent-source', 'USD', D(-1))], connection=connection)
                self.tick += 1_000_000_000
        self.assertEqual(failure.exception.code, 'lease_expired')
        self.assertEqual((self.old_service.account('alice'), self.old_service.ledger.journal()), before)
        with self.assertRaises(self.FenceError):
            self.fence.renew(token, ttl_seconds=1)
        replacement, _, current = self.acquire('replacement-owner')
        self.assertGreater(replacement.generation, token.generation)
        with self.assertRaises(self.FenceError):
            writer.deposit('alice', 'superseded', 'USD', D(1))
        current.deposit('alice', 'once', 'USD', D(1))
        current.deposit('alice', 'once', 'USD', D('1.00'))
        self.assertEqual(F(self.old_service.account('alice')['balances']['USD']), F('21.08'))

    def test_competing_lease_and_read_transaction_never_grant_financial_authority(self):
        token, _, writer = self.acquire()
        with self.assertRaises(self.FenceError) as failure:
            self.fence.acquire('other-owner', ttl_seconds=1)
        self.assertEqual(failure.exception.code, 'lease_busy')
        with self.assertRaises((self.FenceError, sqlite3.DatabaseError)):
            with self.database.read_transaction() as connection:
                self.assertEqual(connection.execute('SELECT COUNT(*) FROM uta_orders').fetchone()[0], 1)
                connection.execute("DELETE FROM uta_orders WHERE order_id='existing'")
        self.assertEqual(len(writer.orders('alice')), 1)
        self.fence.release(token)
        with self.assertRaises(self.FenceError):
            writer.cancel_order('alice', 'existing')
        replacement, _, _ = self.acquire('next-owner')
        self.assertGreater(replacement.generation, token.generation)

    def test_clock_high_water_regression_and_invalid_ttl_fail_closed(self):
        _, _, writer = self.acquire()
        self.tick += 100
        writer.deposit('alice', 'valid', 'USD', D(1))
        before = self.old_service.account('alice'), self.old_service.ledger.journal()
        self.tick -= 1
        with self.assertRaises(self.FenceError) as failure:
            writer.deposit('alice', 'clock-regressed', 'USD', D(1))
        self.assertEqual(failure.exception.code, 'fence_clock_regressed')
        self.assertEqual((self.old_service.account('alice'), self.old_service.ledger.journal()), before)
        for ttl in (True, 0, .000999, 3601, float('inf'), float('nan')):
            with self.subTest(ttl=ttl), self.assertRaises((ValueError, self.FenceError)):
                self.fence.acquire('invalid-ttl', ttl_seconds=ttl)

    def test_boot_change_requires_new_generation_and_minimum_ttl_expires_at_equality(self):
        token, _, old_writer = self.acquire()
        next_database = Database(self.path, fence_clock_ns=lambda: self.tick,
            fence_boot_id='22222222-2222-2222-2222-222222222222')
        next_fence = self.WriterFence(next_database)
        current_token = next_fence.acquire('new-boot-owner', ttl_seconds=.001)
        self.assertGreater(current_token.generation, token.generation)
        current = self.open_service(next_database.for_writer(current_token))
        with self.assertRaises(self.FenceError):
            old_writer.deposit('alice', 'old-boot', 'USD', D(1))
        self.tick += 999_999
        current.deposit('alice', 'just-before-expiry', 'USD', D(1))
        self.tick += 1
        with self.assertRaises(self.FenceError) as failure:
            current.deposit('alice', 'exact-expiry', 'USD', D(1))
        self.assertEqual(failure.exception.code, 'lease_expired')
        self.assertEqual(F(self.old_service.account('alice')['balances']['USD']), F('21.08'))


class IndependentProcessReceiptTests(unittest.TestCase):
    def test_real_pid_restart_retains_queued_terminal_and_exact_cash_capacity(self):
        from uta.durable_process import DurableProcessRouter
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        path = Path(temporary.name) / 'process-authority'
        catalog, rules = synthetic_policy()
        def bootstrap(router):
            router.create_account('cash')
            router.deposit('cash', 'source-capital', 'USD', D('10.04'))
        router = DurableProcessRouter.initialize(path, 1, {'USD': 8, 'BTC': 8}, managed=True,
            bootstrap=bootstrap, product_catalog=catalog, portfolio_rules=rules,
            lease_seconds=.6, poll_interval=.01, background_interval=.05)
        self.addCleanup(router.close)
        router.start()
        market = MarketSnapshot(1, datetime.now(timezone.utc),
            {'USD': AssetSpec(D(1), D(1)), 'BTC': AssetSpec(D(100), D('.8'))},
            {'BTC-PERP': InstrumentSpec(D(100), D('.1'), D('.05'))})
        self.assertFalse(router.publish_market(market, timeout=10)['publishing'])
        self.assertFalse(router.set_kill_switch(False, timeout=10)['halted'])
        self.assertNotEqual(router.worker_pid(0), os.getpid())
        self.assertIsNotNone(router.worker_pid(0))
        router.close()
        queued = router.submit_order('cash', 'survive-parent', 'first-order', 'BTC-PERP', D(1), D(100))
        self.assertEqual((queued['ack'], queued['state'], queued['result']), ('durably_queued', 'PENDING', None))
        with router._database(0).read_transaction() as connection:
            self.assertEqual(connection.execute('SELECT COUNT(*) FROM uta_orders').fetchone()[0], 0)
            self.assertEqual(int(connection.execute("SELECT units FROM ledger_balances WHERE account='customer:cash' AND asset='USD'").fetchone()[0]), 1_004_000_000)
        reopened = DurableProcessRouter(path, lease_seconds=.6, poll_interval=.01, background_interval=.05)
        self.addCleanup(reopened.close)
        self.assertEqual(reopened.status('survive-parent', account_id='cash'), queued)
        reopened.start()
        accepted = reopened.wait('survive-parent', account_id='cash', timeout=10)
        self.assertEqual(accepted['state'], 'SUCCEEDED')
        self.assertEqual(F(accepted['result']['reserved_margin']), F('10.04'))
        reopened.submit_order('cash', 'cannot-double-spend', 'second-order', 'BTC-PERP', D(1), D(100))
        rejected = reopened.wait('cannot-double-spend', account_id='cash', timeout=10)
        self.assertEqual((rejected['state'], rejected['error']['code']), ('REJECTED', 'insufficient_margin'))
        previous = reopened.diagnostics()['workers'][0]
        old_pid, old_generation = reopened.worker_pid(0), previous['generation']
        self.assertNotEqual(old_pid, os.getpid())
        reopened.terminate_worker(0)
        deadline = monotonic() + 10
        while monotonic() < deadline:
            current = reopened.diagnostics()['workers'][0]
            if (current['pid'] not in (None, old_pid, os.getpid()) and current['lease_active']
                    and current['owner_pid'] == current['pid'] and current['generation'] > old_generation):
                break
            sleep(.02)
        else:
            self.fail('actual killed worker did not recover with a new fenced PID')
        self.assertEqual(reopened.submit_order('cash', 'survive-parent', 'first-order', 'BTC-PERP', D('1.00'), D('100.00')), accepted)
        self.assertEqual(reopened.submit_order('cash', 'cannot-double-spend', 'second-order', 'BTC-PERP', D(1), D(100)), rejected)
        with reopened._database(0).read_transaction() as connection:
            self.assertEqual(connection.execute('SELECT COUNT(*) FROM uta_orders').fetchone()[0], 1)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM uta_events WHERE event_type='ORDER_ACCEPTED'").fetchone()[0], 1)
            self.assertEqual(connection.execute('SELECT COUNT(*) FROM ledger_events').fetchone()[0], 1)
            self.assertEqual(int(connection.execute("SELECT units FROM ledger_balances WHERE account='customer:cash' AND asset='USD'").fetchone()[0]), 1_004_000_000)
            self.assertEqual(sum(int(row[0]) for row in connection.execute("SELECT units FROM ledger_balances WHERE asset='USD'")), 0)
