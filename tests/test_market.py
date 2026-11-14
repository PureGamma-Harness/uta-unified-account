import json
import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal as D, ROUND_FLOOR, localcontext

from uta.market import MarketSnapshot
from uta.models import AssetSpec, InstrumentSpec, RiskInputError


class MarketSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 11, 14, 10, 20, tzinfo=timezone.utc)
        self.assets = {"USD": AssetSpec(D("1"), D("1"))}
        self.instruments = {"BTC-PERP": InstrumentSpec(D("100"), D("0.1"), D("0.05"))}

    def snapshot(self, **changes):
        values = dict(version=3, observed_at=self.now, assets=self.assets, instruments=self.instruments)
        values.update(changes)
        return MarketSnapshot(**values)

    def test_defensive_copy_prevents_parameter_mutation(self):
        market = self.snapshot()
        self.assets["USD"] = AssetSpec(D("0.1"), D("0"))
        self.instruments.clear()
        self.assertEqual(market.assets["USD"].price, D("1"))
        self.assertIn("BTC-PERP", market.instruments)
        with self.assertRaises(TypeError):
            market.assets["USD"] = self.assets["USD"]
        with self.assertRaises(TypeError):
            market.instruments["ETH-PERP"] = market.instruments["BTC-PERP"]

    def test_freshness_exact_boundaries_and_clock_policy(self):
        market = self.snapshot()
        market.validate(now=self.now + timedelta(seconds=5))
        market.validate(now=self.now - timedelta(seconds=1))
        for now in (self.now + timedelta(seconds=5, microseconds=1),
                    self.now - timedelta(seconds=1, microseconds=1),
                    self.now.replace(tzinfo=None), None):
            with self.subTest(now=now), self.assertRaises(RiskInputError):
                market.validate(now=now)
        for policy in (timedelta(microseconds=-1), 5, None):
            with self.subTest(policy=policy), self.assertRaises(RiskInputError):
                market.validate(now=self.now, max_age=policy)

    def test_round_trip_and_equal_numeric_spelling_canonicalize(self):
        market = self.snapshot()
        alternate = self.snapshot(
            assets={"USD": AssetSpec(D("1.000"), D("1.00"))},
            instruments={"BTC-PERP": InstrumentSpec(D("100.00"), D("0.1000"), D("0.050"))},
            observed_at=self.now.astimezone(timezone(timedelta(hours=5, minutes=30))))
        self.assertEqual(market.to_json(), alternate.to_json())
        self.assertEqual(MarketSnapshot.from_json(market.to_json()), market)
        self.assertEqual(MarketSnapshot.from_json(market.to_json()).to_json(), market.to_json())

    def test_json_precision_independent_of_callers_context(self):
        price = D("123456789012345678901234567890.12345678901234567890123456789")
        market = self.snapshot(assets={"USD": AssetSpec(price, D("0.12345678901234567890123456789"))})
        canonical = market.to_json()
        with localcontext() as context:
            context.prec = 2
            context.rounding = ROUND_FLOOR
            self.assertEqual(market.to_json(), canonical)
            self.assertEqual(MarketSnapshot.from_json(canonical), market)
        for price in (D("1e100"), D("1e-100"), D("1" * 80)):
            market = self.snapshot(assets={"USD": AssetSpec(price, D("1"))})
            self.assertEqual(MarketSnapshot.from_json(market.to_json()), market)

    def test_invalid_constructor_fields_fail_closed(self):
        for version in (True, False, -1, 2**63, "1", 1.0):
            with self.subTest(version=version), self.assertRaises(RiskInputError):
                self.snapshot(version=version)
        for assets in ({}, [], None, {"USD": {"price": "1"}}, {" USD": self.assets["USD"]}):
            with self.subTest(assets=assets), self.assertRaises(RiskInputError):
                self.snapshot(assets=assets)
        for instruments in ({"X": None}, {1: next(iter(self.instruments.values()))}):
            with self.subTest(instruments=instruments), self.assertRaises(RiskInputError):
                self.snapshot(instruments=instruments)
        with self.assertRaises(RiskInputError):
            self.snapshot(observed_at=self.now.replace(tzinfo=None))
        self.snapshot(instruments={})  # Cash-only deployments are valid.

    def test_untrusted_json_rejects_duplicates_extra_fields_and_numeric_amounts(self):
        payload = json.loads(self.snapshot().to_json())
        variants = []
        for value in (1, 1.0, None, True, "NaN", "Infinity", "1e101", "1e-101", " 1", "1_0", "１"):
            candidate = json.loads(self.snapshot().to_json())
            candidate["assets"]["USD"]["price"] = value
            variants.append(json.dumps(candidate))
        payload["extra"] = 0
        variants.extend((json.dumps(payload), "[]", "null", "{", "NaN",
                         '{"version":1,"version":2}',
                         self.snapshot().to_json().replace('"USD":{', '"USD":{"price":"2",'),
                         "[" * 2000 + "]" * 2000))
        for value in variants:
            with self.subTest(value=value[:100]), self.assertRaises(RiskInputError):
                MarketSnapshot.from_json(value)

    def test_extreme_time_unicode_and_input_size_fail_closed(self):
        for value in (None, 1, b"{}", "\ud800", " " * (1024 * 1024 + 1)):
            with self.subTest(type=type(value)), self.assertRaises(RiskInputError):
                MarketSnapshot.from_json(value)
        outside_utc = datetime(1, 1, 1, tzinfo=timezone(timedelta(hours=1)))
        with self.assertRaises(RiskInputError):
            self.snapshot(observed_at=outside_utc)
        with self.assertRaises(RiskInputError):
            self.snapshot().validate(now=outside_utc)


if __name__ == "__main__":
    unittest.main()
