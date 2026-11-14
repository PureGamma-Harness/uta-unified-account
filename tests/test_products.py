from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal as D, Inexact, Rounded, localcontext
import json
import unittest

from uta.products import (AccountMode, ProductCatalog, ProductError, ProductKind,
                          ProductSpec, TradingStatus, UnsupportedProduct)


def product(symbol="X", **changes):
    values = dict(symbol=symbol, kind=ProductKind.LINEAR_PERPETUAL, underlying="BTC",
                  quote_asset="USD", settlement_asset="USD", price_tick=D("0.01"),
                  quantity_step=D("0.001"), min_notional=D("10"), multiplier=D("2"),
                  risk_tier="tier-1", status=TradingStatus.ACTIVE, funding_interval_seconds=28800)
    values.update(changes)
    return ProductSpec(**values)


class ProductCatalogTests(unittest.TestCase):
    def test_catalog_round_trip_and_metadata_immutability(self):
        raw = {"X": product()}
        catalog = ProductCatalog(3, raw)
        raw.clear()
        self.assertEqual(catalog.products["X"].multiplier, D("2"))
        self.assertEqual(ProductCatalog.from_json(catalog.to_json()), catalog)
        with self.assertRaises(TypeError):
            catalog.products["X"] = product()
        self.assertEqual(catalog.products["X"].risk_unit, ("BTC", "linear_perpetual", "perpetual-or-spot", "USD", "X"))

    def test_only_explicit_cross_first_batch_products_can_be_activated(self):
        for kind in ProductKind:
            expiry = datetime(2027, 1, 1, tzinfo=timezone.utc) if kind in (ProductKind.OPTION, ProductKind.DATED_FUTURE) else None
            spec = product(kind=kind, expiry=expiry, funding_interval_seconds=None)
            catalog = ProductCatalog(1, {"X": spec})
            if kind in (ProductKind.SPOT, ProductKind.SPOT_MARGIN, ProductKind.LINEAR_PERPETUAL):
                self.assertEqual(catalog.require_supported("X"), spec)
            else:
                with self.assertRaisesRegex(UnsupportedProduct, "phase1_product_unsupported"):
                    catalog.require_supported("X")
        for mode in (AccountMode.ISOLATED, AccountMode.PM, "cross", None):
            with self.subTest(mode=mode), self.assertRaisesRegex(UnsupportedProduct, "account_mode_unsupported"):
                ProductCatalog(1, {"X": product()}).require_supported("X", mode=mode)

    def test_halt_delist_and_reduce_only_are_execution_gates(self):
        for status in TradingStatus:
            spec = product(status=status)
            catalog = ProductCatalog(1, {"X": spec})
            self.assertEqual(catalog.require_risk_supported("X"), spec)
            if status is TradingStatus.ACTIVE:
                catalog.require_supported("X")
            else:
                with self.assertRaisesRegex(UnsupportedProduct, "product_not_active"):
                    catalog.require_supported("X")
            if status is TradingStatus.REDUCE_ONLY:
                catalog.require_supported("X", reduce_only=True)
        with self.assertRaises(UnsupportedProduct):
            ProductCatalog(1, {"X": product(settlement_asset="USDT")}).require_supported("X")
        with self.assertRaisesRegex(UnsupportedProduct, "hedge_offsets_disabled"):
            ProductCatalog(1, {"X": product(eligible_hedges=("BTC-USD",))}).require_supported("X")

    def test_order_tick_step_and_notional_use_exact_decimals(self):
        catalog = ProductCatalog(1, {"X": product()})
        catalog.check_order("X", D("0.5"), D("10"))  # 0.5 * 10 * multiplier 2 == minimum 10.
        for quantity, price, error in (("0.5001", "10", "quantity_step"),
                                        ("0.5", "10.001", "price_tick"),
                                        ("0.499", "10", "minimum_notional")):
            with self.subTest(quantity=quantity, price=price), self.assertRaisesRegex(ProductError, error):
                catalog.check_order("X", D(quantity), D(price))
        with localcontext() as context:
            context.prec = 2
            context.traps[Inexact] = True
            context.traps[Rounded] = True
            catalog.check_order("X", D("1000.001"), D("12345.67"))

    def test_malformed_metadata_and_json_fail_closed(self):
        for changes in ({"price_tick": D("0")}, {"quantity_step": D("NaN")},
                        {"multiplier": D("-1")}, {"status": "active"}, {"kind": "linear_perpetual"},
                        {"expiry": datetime(2027, 1, 1)}, {"funding_interval_seconds": True}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                product(**changes)
        raw = json.loads(ProductCatalog(1, {"X": product()}).to_json())
        raw["products"]["X"]["price_tick"] = 0.01
        for value in (json.dumps(raw), '{"version":1,"version":2}', "NaN", "[]"):
            with self.subTest(value=value[:100]), self.assertRaises(ValueError):
                ProductCatalog.from_json(value)


if __name__ == "__main__":
    unittest.main()
