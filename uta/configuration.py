"""Explicit, bounded configuration loading for the durable Cross service."""
from pathlib import Path

from .portfolio import PortfolioRules
from .products import ProductCatalog


def load_policy(catalog_path=None, rules_path=None) -> dict:
    if (catalog_path is None) != (rules_path is None):
        raise ValueError("--catalog and --risk-rules must be provided together")
    if catalog_path is None:
        return {}
    def read(path):
        with Path(path).open("rb") as source:
            raw = source.read(1024 * 1024 + 1)
        if len(raw) > 1024 * 1024:
            raise ValueError("risk configuration exceeds 1 MiB")
        return raw.decode("utf-8")
    return {"product_catalog": ProductCatalog.from_json(read(catalog_path)),
            "portfolio_rules": PortfolioRules.from_json(read(rules_path))}
