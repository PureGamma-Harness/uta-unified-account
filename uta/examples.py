"""Reviewable synthetic policies for tests and isolated local demonstrations.

These parameters are not calibrated to a real exchange or authorized for funds.
Nothing imports or activates them unless a caller explicitly requests them.
"""
from decimal import Decimal as D

from .portfolio import BorrowLimits, CollateralRule, CollateralTier, LinearMarginRule, PortfolioRules
from .products import ProductCatalog, ProductKind, ProductSpec, TradingStatus


def synthetic_policy() -> tuple[ProductCatalog, PortfolioRules]:
    catalog = ProductCatalog(1, {
        "BTC-USD": ProductSpec("BTC-USD", ProductKind.SPOT_MARGIN, "BTC", "USD", "USD",
                               D(".01"), D(".01"), D(".01"), status=TradingStatus.ACTIVE),
        "BTC-PERP": ProductSpec("BTC-PERP", ProductKind.LINEAR_PERPETUAL, "BTC", "USD", "USD",
                                D(".01"), D(".01"), D(1), funding_interval_seconds=28800,
                                status=TradingStatus.ACTIVE),
    })
    rules = PortfolioRules(1, {
        "USD": CollateralRule("USD", (CollateralTier(None, D(1)),), D(1)),
        "BTC": CollateralRule("BTC", (CollateralTier(None, D(".8")),), D(".5")),
    }, {
        "USD": BorrowLimits("USD", D(100000), D(".1"), D(".05"), D(".01")),
        "BTC": BorrowLimits("BTC", D(1000), D(".1"), D(".05"), D(".00000001")),
    }, {"tier-1": LinearMarginRule("tier-1", D(".1"), D(".05"))}, D(1000000))
    return catalog, rules
