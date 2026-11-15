"""Independent rational oracles for opt-in arithmetic and market caches.

Expected reserves, fees and cash capacity never call a production calculator.
The private reserve entry point is an actual-under-test only; public durable
commands additionally prove that a cached amount is not an admission decision.
All examples are synthetic and have no production activation authority.
"""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal as D, Inexact, Rounded, localcontext
from fractions import Fraction as F
import json
from pathlib import Path
import random
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from uta.admission import AdmissionBatcher
from uta.examples import synthetic_policy
from uta.ledger import LedgerError
from uta.market import MarketSnapshot
from uta.market_cache import MarketDecodeCache
from uta.models import AssetSpec, InstrumentSpec, RiskInputError
from uta.portfolio import LinearMarginRule
from uta.products import AccountMode, ProductCatalog, UnsupportedProduct
from uta.reserve_kernel import ReserveInputs, ReserveKernel
from uta.service import ExchangeService, ServiceError
from uta.storage import Database


SEED = 15112026
NOW = datetime(2026, 11, 15, tzinfo=timezone.utc)


def units(value, scale=2):
    """Fixture Decimal construction independent of the ambient context."""
    return D((int(value < 0), tuple(map(int, str(abs(value)))), -scale))


def ceiling_fee(notional, rate, scale):
    whole, residue = divmod(F(notional) * F(rate) * 10**scale, 1)
    return F(int(whole) + bool(residue), 10**scale)


def reference(inputs):
    """Reviewable three-component policy, evaluated entirely as rationals."""
    outstanding = F(inputs.quantity) - F(inputs.filled_quantity)
    limit, mark = F(inputs.limit_price), F(inputs.mark_price)
    basis = mark if mark > limit else limit
    initial = F(0) if inputs.reduce_only else abs(outstanding) * basis * F(inputs.initial_margin_rate)
    adverse = outstanding * (limit - mark)
    slippage = adverse if adverse > 0 else F(0)
    future_notional = abs(outstanding) * limit
    unpaid = ceiling_fee(F(inputs.fee_notional) + future_notional,
                         inputs.fee_rate, inputs.usd_scale) - F(inputs.charged_fee)
    return initial + slippage + unpaid


def inputs(**changes):
    values = dict(quantity=D(2), filled_quantity=D('.5'), limit_price=D(101),
                  mark_price=D(100), reduce_only=False, initial_margin_rate=D('.1'),
                  fee_notional=D(50), charged_fee=D('.02'), fee_rate=D('.0004'), usd_scale=8)
    values.update(changes)
    return ReserveInputs(**values)


def order_row(values):
    return dict(symbol='BTC-PERP', quantity=str(values.quantity),
                filled_quantity=str(values.filled_quantity), limit_price=str(values.limit_price),
                reduce_only=values.reduce_only, fee_notional=str(values.fee_notional),
                charged_fee=str(values.charged_fee))


class IndependentKernelMathTests(unittest.TestCase):
    def test_hand_calculable_fee_rounding_and_reduce_only_examples(self):
        common = dict(quantity=D(1), filled_quantity=D(0), fee_notional=D(0),
                      charged_fee=D(0), usd_scale=2)
        cases = [
            (inputs(**common, limit_price=D(100)), F('10.04')),
            (inputs(**common, limit_price=D(101)), F('11.15')),
            (inputs(**{**common, 'quantity': D(-1)}, limit_price=D(99)), F('11.04')),
            (inputs(**{**common, 'quantity': D(-1)}, limit_price=D(99), reduce_only=True), F('1.04')),
            (inputs(**{**common, 'filled_quantity': D('.99'), 'fee_notional': D(99),
                       'charged_fee': D('.04')}, limit_price=D(100)), F('.1')),
        ]
        kernel = ReserveKernel(8)
        for value, expected in cases:
            with self.subTest(value=value):
                self.assertEqual(reference(value), expected)
                self.assertEqual(F(kernel.calculate(value)), expected)
                self.assertEqual(F(kernel.calculate(value)), expected)

    def test_each_economic_key_dimension_affects_the_answer_without_poisoning_prior_key(self):
        base = inputs()
        changes = dict(quantity=D('2.25'), filled_quantity=D('.75'), limit_price=D(102),
                       mark_price=D(120), reduce_only=True, initial_margin_rate=D('.2'),
                       fee_notional=D(55), charged_fee=D('.01'), fee_rate=D('.001'), usd_scale=2)
        kernel = ReserveKernel(32)
        self.assertEqual(F(kernel.calculate(base)), reference(base))
        for field, value in changes.items():
            candidate = replace(base, **{field: value})
            with self.subTest(field=field):
                self.assertNotEqual(reference(candidate), reference(base))
                self.assertEqual(F(kernel.calculate(candidate)), reference(candidate))
                self.assertEqual(F(kernel.calculate(base)), reference(base))
        self.assertEqual(kernel.stats()['size'], 11)
        self.assertGreaterEqual(kernel.stats()['hits'], 10)

    def test_896_seeded_cases_match_fraction_reference_under_hostile_decimal_context(self):
        generator = random.Random(SEED)
        values = []
        for scale in range(2, 9):
            for rate in (D(0), D('.00000001'), D('.0004'), D('.01')):
                for _ in range(32):
                    magnitude = generator.randint(1, 1000000)
                    sign = generator.choice((-1, 1))
                    filled = generator.randint(0, magnitude)
                    fill_price = generator.randint(1, 20000)
                    prior = units(filled * fill_price, 6)
                    values.append(inputs(quantity=units(sign * magnitude, 4),
                        filled_quantity=units(sign * filled, 4),
                        limit_price=units(generator.randint(1, 20000)),
                        mark_price=units(generator.randint(1, 20000)),
                        reduce_only=generator.choice((False, True)),
                        initial_margin_rate=generator.choice((D('.01'), D('.1'), D('.9'))),
                        fee_notional=prior, charged_fee=units(int(ceiling_fee(prior, rate, scale) * 10**scale), scale),
                        fee_rate=rate, usd_scale=scale))
        kernel = ReserveKernel(2048)
        expected = [reference(value) for value in values]
        with localcontext() as context:
            context.prec, context.Emax, context.Emin = 1, 2, -2
            context.traps[Inexact] = context.traps[Rounded] = True
            for index, (value, wanted) in enumerate(zip(values, expected)):
                with self.subTest(seed=SEED, index=index):
                    self.assertEqual(F(kernel.calculate(value)), wanted)
                    self.assertEqual(F(kernel.calculate(value)), wanted)
        self.assertEqual(len(values), 896)
        self.assertGreaterEqual(kernel.stats()['hits'], 896)

    def test_lru_eviction_disabled_mode_and_clearing_preserve_exact_values(self):
        kernel = ReserveKernel(2)
        values = [inputs(quantity=D(value)) for value in (1, 2, 3)]
        for value in values:
            self.assertEqual(F(kernel.calculate(value)), reference(value))
            self.assertLessEqual(kernel.stats()['size'], 2)
        self.assertEqual(kernel.stats()['evictions'], 1)
        self.assertEqual(F(kernel.calculate(values[0])), reference(values[0]))
        self.assertEqual(kernel.stats()['misses'], 4)
        previous = kernel.stats()
        kernel.clear()
        self.assertEqual(kernel.stats()['size'], 0)
        self.assertEqual(kernel.stats()['misses'], previous['misses'])
        kernel.clear(reset_stats=True)
        self.assertEqual(kernel.stats(), dict(capacity=2, size=0, hits=0, misses=0, evictions=0))
        disabled = ReserveKernel(0)
        for _ in range(2):
            self.assertEqual(F(disabled.calculate(values[0])), reference(values[0]))
        self.assertEqual((disabled.stats()['size'], disabled.stats()['hits']), (0, 0))


class IndependentKernelAuthorityTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.now = NOW
        self.catalog, self.rules = synthetic_policy()

    def service(self, name, *, configured=True, reserve=32, market=4, scale=8, rate=D('.0004')):
        kwargs = dict(product_catalog=self.catalog, portfolio_rules=self.rules) if configured else {}
        return ExchangeService(Database(self.directory / (name + '.sqlite3')), {'USD': scale, 'BTC': 8},
            clock=lambda: self.now, fee_rate=rate, reserve_cache_size=reserve, market_cache_size=market, **kwargs)

    def snapshot(self, *, version=1, mark=D(100), initial=D('.1'), observed=None):
        return MarketSnapshot(version, self.now if observed is None else observed,
            {'USD': AssetSpec(D(1), D(1)), 'BTC': AssetSpec(D(100), D('.8'))},
            {'BTC-PERP': InstrumentSpec(mark, initial, D('.05'))})

    def prepare(self, name, *, cash='100000', **kwargs):
        service = self.service(name, **kwargs)
        service.publish_market(self.snapshot())
        service.set_kill_switch(False)
        service.create_account('alice')
        service.deposit('alice', 'funding', 'USD', D(cash))
        return service

    def assert_error(self, code, call, *args, **kwargs):
        with self.assertRaises(ServiceError) as failure:
            call(*args, **kwargs)
        self.assertEqual(failure.exception.code, code)

    @staticmethod
    def financial_rows(service):
        with service.database.transaction() as connection:
            return {table: [tuple(row) for row in connection.execute('SELECT * FROM ' + table)]
                    for table in ('uta_accounts', 'uta_orders', 'uta_positions', 'uta_fills',
                                  'uta_events', 'ledger_events', 'ledger_balances')}

    @staticmethod
    def persist_payload(service, payload):
        with service.database.transaction() as connection:
            connection.execute('UPDATE uta_market SET payload=? WHERE singleton=1', (payload,))

    def test_service_cached_and_disabled_reserves_match_independent_oracle_across_policies(self):
        for scale, rate in ((2, D('.01')), (4, D('.0004')), (8, D('.00000001'))):
            cached = self.service('cached-' + str(scale), configured=False, scale=scale, rate=rate)
            disabled = self.service('plain-' + str(scale), configured=False, reserve=0, market=0, scale=scale, rate=rate)
            for sign in (-1, 1):
                for mark in (D(90), D(100), D(110)):
                    for reduce in (False, True):
                        value = inputs(quantity=D(sign), filled_quantity=units(sign * 37),
                            limit_price=D(101), mark_price=mark, reduce_only=reduce,
                            initial_margin_rate=D('.2'), fee_notional=D('36.63'),
                            charged_fee=D(0), fee_rate=rate, usd_scale=scale)
                        snapshot = self.snapshot(mark=mark, initial=D('.2'))
                        for service in (cached, disabled):
                            with self.subTest(scale=scale, sign=sign, mark=mark, reduce_only=reduce):
                                self.assertEqual(F(service._reserve(order_row(value), snapshot)), reference(value))
                                self.assertEqual(F(service._reserve(order_row(value), snapshot)), reference(value))
            self.assertEqual(disabled.reserve_cache_stats()['size'], 0)
            self.assertGreater(cached.reserve_cache_stats()['hits'], 0)

    def test_public_partial_fill_trace_recomputes_remaining_reserve_and_cumulative_fees(self):
        service = self.prepare('partial', scale=2)
        generator = random.Random(SEED)
        book = {}
        for index in range(16):
            quantity, price = units(generator.randint(2, 30)), D(generator.choice((99, 100, 101)))
            identifier = 'order-' + str(index)
            value = inputs(quantity=quantity, filled_quantity=D(0), limit_price=price,
                           fee_notional=D(0), charged_fee=D(0), usd_scale=2)
            book[identifier] = value
            service.submit_order('alice', identifier, 'BTC-PERP', quantity, price)
        for index in range(48):
            identifier = generator.choice(tuple(book))
            old = book[identifier]
            remaining_units = int((F(old.quantity) - F(old.filled_quantity)) * 100)
            if not remaining_units:
                continue
            amount = units(generator.randint(1, remaining_units))
            next_filled = units(int(F(old.filled_quantity) * 100) + int(F(amount) * 100))
            notional = F(old.fee_notional) + F(amount) * F(old.limit_price)
            charged = ceiling_fee(notional, old.fee_rate, old.usd_scale)
            value = replace(old, filled_quantity=next_filled,
                fee_notional=units(int(notional * 10000), 4), charged_fee=units(int(charged * 100), 2))
            result = service.apply_fill('alice', identifier, 'fill-' + str(index), amount, old.limit_price)
            self.assertEqual(F(result['reserved_margin']), reference(value))
            book[identifier] = value
            expected = sum((reference(entry) for entry in book.values()), F(0))
            self.assertEqual(F(service.account('alice')['open_order_margin']), expected)
        with service.database.transaction() as connection:
            rows = connection.execute('SELECT order_id,fee_notional,charged_fee FROM uta_orders').fetchall()
        for row in rows:
            self.assertEqual(F(row['fee_notional']), F(book[row['order_id']].fee_notional))
            self.assertEqual(F(row['charged_fee']), F(book[row['order_id']].charged_fee))
        self.assertGreater(service.reserve_cache_stats()['hits'], 0)
        service.ledger.verify()

    def test_same_cached_amount_is_not_a_balance_halt_or_frozen_account_decision(self):
        service = self.prepare('capacity', cash='10.04')
        service.submit_order('alice', 'first', 'BTC-PERP', D(1), D(100))
        before = self.financial_rows(service)
        self.assert_error('insufficient_margin', service.submit_order, 'alice', 'second', 'BTC-PERP', D(1), D(100))
        self.assertEqual(self.financial_rows(service), before)
        service.cancel_order('alice', 'first')
        self.assertEqual(service.submit_order('alice', 'second', 'BTC-PERP', D(1), D(100))['status'], 'OPEN')
        service.deposit('alice', 'more', 'USD', D('10.04'))
        service.set_kill_switch(True)
        self.assert_error('trading_halted', service.submit_order, 'alice', 'halted', 'BTC-PERP', D(1), D(100))
        service.set_kill_switch(False)
        with service.database.transaction() as connection:
            connection.execute("INSERT INTO uta_liquidation_accounts VALUES ('alice','BLOCKED',0,0,NULL,NULL)")
        self.assert_error('account_frozen', service.submit_order, 'alice', 'frozen', 'BTC-PERP', D(1), D(100))
        self.assertEqual(F(service.account('alice')['open_order_margin']), F('10.04'))

    def test_public_warm_and_cold_partial_fills_ignore_hostile_decimal_context(self):
        service = self.prepare('hostile', configured=False)
        service.submit_order('alice', 'live', 'BTC-PERP', D(1), D(100))
        with localcontext() as context:
            context.prec, context.Emax, context.Emin = 1, 2, -2
            context.traps[Inexact] = context.traps[Rounded] = True
            partial = service.apply_fill('alice', 'live', 'almost-all', D('.99999999'), D(100))
            self.assertEqual(F(partial['reserved_margin']), F(1, 10**7))
            self.assertEqual(F(service.account('alice')['open_order_margin']), F(1, 10**7))
            service.clear_reserve_cache()
            service.clear_market_cache()
            self.assertEqual(F(service.account('alice')['open_order_margin']), F(1, 10**7))
            final = service.apply_fill('alice', 'live', 'last-unit', D('.00000001'), D(100))
            self.assertEqual(final['status'], 'FILLED')
            self.assertEqual(F(service.account('alice')['open_order_margin']), F(0))
        with service.database.transaction() as connection:
            fees = sum((F(row[0]) for row in connection.execute('SELECT fee FROM uta_fills')), F(0))
        self.assertEqual(fees, F('.04'))
        service.ledger.verify()

    def test_concurrent_batchers_and_sync_share_capacity_even_on_repeated_kernel_hits(self):
        service = self.prepare('concurrent', cash='30.12')
        # Fill the mathematical cache without reserving financial capacity.
        for _ in range(3):
            self.assertEqual(F(service._reserve(order_row(inputs(quantity=D(1), filled_quantity=D(0),
                limit_price=D(100), fee_notional=D(0), charged_fee=D(0))), self.snapshot())), F('10.04'))
        with AdmissionBatcher(service, max_delay_ms=10) as first, AdmissionBatcher(service, max_delay_ms=10) as second:
            def attempt(index):
                try:
                    if index % 3 == 0:
                        return service.submit_order('alice', 'order-' + str(index), 'BTC-PERP', D(1), D(100))['status']
                    batcher = first if index % 3 == 1 else second
                    return batcher.submit_order('alice', 'order-' + str(index), 'BTC-PERP', D(1), D(100)).result(timeout=10)['status']
                except ServiceError as error:
                    return error.code
            with ThreadPoolExecutor(max_workers=18) as pool:
                results = list(pool.map(attempt, range(18)))
        self.assertEqual(results.count('OPEN'), 3)
        self.assertEqual(results.count('insufficient_margin'), 15)
        self.assertEqual(F(service.account('alice')['open_order_margin']), F('30.12'))

    def test_new_version_and_same_version_changed_payload_revalue_live_orders(self):
        service = self.prepare('revalue')
        service.submit_order('alice', 'live', 'BTC-PERP', D(1), D(100))
        self.assertEqual(F(service.risk('alice')['open_order_margin']), F('10.04'))
        service.publish_market(self.snapshot(version=2, mark=D(90)))
        self.assertEqual(F(service.risk('alice')['open_order_margin']), F('20.04'))
        changed = self.snapshot(version=2, mark=D(80))
        self.persist_payload(service, changed.to_json())
        self.assertEqual(F(service.risk('alice')['open_order_margin']), F('30.04'))
        self.assertEqual(service.risk('alice')['market_version'], 2)
        self.assertGreater(service.market_cache_stats()['hits'], 0)

    def test_warm_market_hit_rechecks_clock_staleness_and_missing_instrument(self):
        service = self.prepare('freshness')
        service.submit_order('alice', 'live', 'BTC-PERP', D(1), D(100))
        service.risk('alice')
        self.now = NOW + timedelta(seconds=5)
        service.risk('alice')  # Equality remains valid.
        self.now += timedelta(microseconds=1)
        self.assert_error('market_unavailable', service.risk, 'alice')
        self.assertEqual(F(service.account('alice')['open_order_margin']), F('10.04'))
        self.now = NOW
        missing = json.loads(self.snapshot().to_json())
        missing['instruments'] = {}
        self.persist_payload(service, json.dumps(missing))
        self.assert_error('market_incomplete', service.risk, 'alice')
        self.persist_payload(service, self.snapshot(observed=NOW + timedelta(seconds=2)).to_json())
        self.assert_error('market_unavailable', service.risk, 'alice')
        self.assertEqual(service.cancel_order('alice', 'live')['status'], 'CANCELLED')

    def test_same_version_corruption_and_margin_conflict_are_not_hidden_by_warm_cache(self):
        service = self.prepare('corrupt')
        service.submit_order('alice', 'live', 'BTC-PERP', D(1), D(100))
        original = self.snapshot().to_json()
        service.risk('alice')
        bad_number = json.loads(original)
        bad_number['instruments']['BTC-PERP']['mark_price'] = 100
        conflict = json.loads(original)
        conflict['instruments']['BTC-PERP']['initial_margin_rate'] = '.2'
        variants = [(original.replace('"version":1', '"version":1,"version":1'), 'market_unavailable'),
                    (json.dumps(bad_number), 'market_unavailable'),
                    (original[:-1], 'market_unavailable'),
                    (json.dumps(conflict), 'margin_rule_conflict')]
        before = self.financial_rows(service)
        for payload, code in variants:
            with self.subTest(code=code, payload=payload[-100:]):
                self.persist_payload(service, payload)
                self.assert_error(code, service.submit_order, 'alice', 'new', 'BTC-PERP', D(1), D(100))
                self.assertEqual(self.financial_rows(service), before)
                self.persist_payload(service, original)
                service.risk('alice')

    def test_warm_reserve_cannot_bypass_current_catalog_or_configuration_mode(self):
        service = self.prepare('catalog')
        value = inputs(quantity=D(1), filled_quantity=D(0), limit_price=D(100),
                       fee_notional=D(0), charged_fee=D(0))
        row = order_row(value)
        self.assertEqual(F(service._reserve(row, self.snapshot())), F('10.04'))
        altered = ProductCatalog(self.catalog.version,
            {name: replace(product, multiplier=D(2)) if name == 'BTC-PERP' else product
             for name, product in self.catalog.products.items()})
        with patch.object(service, '_product_catalog', altered):
            self.assert_error('unsupported_product', service._reserve, row, self.snapshot())
        missing = ProductCatalog(self.catalog.version,
            {name: product for name, product in self.catalog.products.items() if name != 'BTC-PERP'})
        with patch.object(service, '_product_catalog', missing):
            self.assert_error('risk_unavailable', service._reserve, row, self.snapshot())
        for mode in (AccountMode.PM, AccountMode.ISOLATED):
            with self.subTest(mode=mode), self.assertRaises(UnsupportedProduct):
                self.catalog.require_supported('BTC-PERP', mode=mode)
        self.assert_error('configuration_conflict', self.service, 'catalog', configured=False)
        self.assert_error('configuration_conflict', self.service, 'catalog', rate=D('.001'))
        with self.assertRaisesRegex(LedgerError, 'asset scales differ'):
            self.service('catalog', scale=2)
        for identifier, symbol, quantity, price, code in (
                ('spot', 'BTC-USD', D(1), D(100), 'unsupported_product'),
                ('step', 'BTC-PERP', D('.001'), D(100), 'product_rejected'),
                ('tick', 'BTC-PERP', D(1), D('100.001'), 'product_rejected')):
            self.assert_error(code, service.submit_order, 'alice', identifier, symbol, quantity, price)

    def test_market_cache_hit_revalidates_current_policy_without_reparsing(self):
        service = self.prepare('policy-hit')
        service.risk('alice')
        changed = replace(self.rules, linear_margin={
            'tier-1': LinearMarginRule('tier-1', D('.2'), D('.05'))})
        before = self.financial_rows(service)
        hits = service.market_cache_stats()['hits']
        # Test-only policy replacement simulates an invalid in-process update;
        # it is not a supported way to modify the persisted rule registry.
        with patch.object(service, '_portfolio_rules', changed):
            self.assert_error('margin_rule_conflict', service.risk, 'alice')
        self.assertGreater(service.market_cache_stats()['hits'], hits)
        self.assertEqual(self.financial_rows(service), before)

    def test_restart_cold_caches_and_disabled_service_have_same_durable_results(self):
        service = self.prepare('restart')
        service.submit_order('alice', 'live', 'BTC-PERP', D(1), D(100))
        service.apply_fill('alice', 'live', 'partial', D('.37'), D(99))
        expected = service.account('alice'), service.risk('alice'), service.orders('alice')
        self.assertGreater(service.reserve_cache_stats()['size'], 0)
        self.assertGreater(service.market_cache_stats()['size'], 0)
        reopened = self.service('restart')
        self.assertEqual((reopened.reserve_cache_stats()['size'], reopened.market_cache_stats()['size']), (0, 0))
        self.assertEqual((reopened.account('alice'), reopened.risk('alice'), reopened.orders('alice')), expected)
        plain = self.service('restart', reserve=0, market=0)
        self.assertEqual((plain.account('alice'), plain.risk('alice'), plain.orders('alice')), expected)
        self.assertEqual((plain.reserve_cache_stats()['size'], plain.market_cache_stats()['size']), (0, 0))
        before = self.financial_rows(reopened)
        reopened.submit_order('alice', 'live', 'BTC-PERP', D(1), D(100))
        reopened.apply_fill('alice', 'live', 'partial', D('.37'), D(99))
        self.assertEqual(self.financial_rows(reopened), before)


class IndependentMarketCacheTests(unittest.TestCase):
    def test_full_payload_key_bounded_lru_and_immutable_results(self):
        cache = MarketDecodeCache(2)
        def payload(mark):
            return MarketSnapshot(1, NOW, {'USD': AssetSpec(D(1), D(1))},
                {'BTC-PERP': InstrumentSpec(D(mark), D('.1'), D('.05'))}).to_json()
        first = cache.parse(payload(100))
        self.assertEqual(cache.parse(payload(100)).instruments['BTC-PERP'].mark_price, D(100))
        with self.assertRaises(TypeError):
            first.instruments['BTC-PERP'] = InstrumentSpec(D(1), D('.1'), D('.05'))
        for mark in (90, 80):
            self.assertEqual(cache.parse(payload(mark)).instruments['BTC-PERP'].mark_price, D(mark))
            self.assertLessEqual(cache.stats()['size'], 2)
        self.assertEqual(cache.stats()['evictions'], 1)
        self.assertEqual(cache.parse(payload(100)).instruments['BTC-PERP'].mark_price, D(100))
        self.assertEqual(cache.stats()['misses'], 4)

    def test_invalid_payload_is_not_cached_and_service_instances_do_not_share_entries(self):
        first, second = MarketDecodeCache(2), MarketDecodeCache(2)
        for _ in range(2):
            with self.assertRaises(RiskInputError):
                first.parse('{"version":1}')
        self.assertEqual((first.stats()['size'], first.stats()['hits'], first.stats()['errors']), (0, 0, 2))
        self.assertEqual((second.stats()['size'], second.stats()['hits'], second.stats()['errors']), (0, 0, 0))
        first.clear(reset_stats=True)
        self.assertEqual(first.stats(), dict(capacity=2, size=0, hits=0, misses=0, errors=0, evictions=0))
