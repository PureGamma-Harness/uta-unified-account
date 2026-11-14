"""Synthetic M1: classic handover, credit, real spot/perp matching and recovery."""
from datetime import datetime, timezone
from decimal import Decimal as D
from pathlib import Path
from tempfile import TemporaryDirectory

from .credit import CreditService
from .cutover import ClassicImporter
from .examples import synthetic_policy
from .market import MarketSnapshot
from .matching import Matcher
from .migration import build_shadow
from .models import AssetSpec, InstrumentSpec
from .reconciliation import reconcile_exchange
from .service import ExchangeService
from .spot import SpotExchange
from .storage import Database
from .supervisor import ExchangeWorker


def run_vertical_acceptance() -> dict:
    def require(condition, message):
        if not condition:
            raise RuntimeError("vertical acceptance failed: " + message)
    now = datetime(2026, 11, 14, tzinfo=timezone.utc)
    catalog, rules = synthetic_policy()
    scales = {"USD": 8, "BTC": 8}
    checks = []
    with TemporaryDirectory(prefix="uta-vertical-synthetic-") as directory:
        path = Path(directory) / "authority.sqlite3"
        def reopen():
            exchange = ExchangeService(Database(path), scales, clock=lambda: now,
                                       product_catalog=catalog, portfolio_rules=rules)
            exchange.credit = CreditService(exchange)
            exchange.matcher = Matcher(exchange)
            exchange.spot = SpotExchange(exchange, catalog)
            return exchange
        exchange = reopen()
        def publish(version, mark):
            exchange.publish_market(MarketSnapshot(version, now,
                {"USD": AssetSpec(D(1), D(1)), "BTC": AssetSpec(D(mark), D(".8"))},
                {"BTC-PERP": InstrumentSpec(D(mark), D(".1"), D(".05"))}))
        publish(1, 100)
        shadow = build_shadow({"account_id": "classic", "version": 7, "captured_at": now.isoformat(),
            "compartments": {
                "spot": {"balances": [{"asset": asset, "free": amount, "locked": "0", "borrowed": "0", "interest": "0"}
                                       for asset, amount in (("USD", "1000"), ("BTC", "1"))]},
                "margin": {"balances": []}, "futures": {"balances": [], "positions": []}}}, now=now)
        importer = ClassicImporter(exchange)
        importer.import_shadow(shadow, "synthetic-cutover", source_fence_reference="synthetic-offline-source-epoch7",
                               open_orders=[], conditional_orders=[], pending_settlements=[], transfers_in_flight=[])
        require(exchange.supervise_account("classic")["state"] == "NORMAL", "import must be re-evaluated before trading")
        checks.append("classic gross snapshot handover, retained source evidence and initial freeze")
        exchange.create_account("liquidity")
        exchange.deposit("liquidity", "fund-usd", "USD", D(100000))
        exchange.deposit("liquidity", "fund-btc", "BTC", D(100))
        exchange.set_kill_switch(False)
        credit = exchange.credit
        credit.configure_asset_limit("BTC", D(10))
        credit.configure_limit("classic", "BTC", D(1))
        credit.fund_pool("capital", "BTC", D(1), source_reference="synthetic-authorized-capital-line1")
        loan = credit.borrow("classic", "borrow", "BTC", D(".1"))
        require(loan["risk_evidence"]["rule_version"] == rules.version, "borrow must use the same rule version")
        credit.accrue_interest("classic", "synthetic-interest", "BTC", D(".001"))
        exchange.spot.submit_order("classic", "sell-borrowed", "BTC-USD", D("-.1"), D(100))
        exchange.spot.submit_order("liquidity", "buy-spot", "BTC-USD", D(".1"), D(100))
        require(exchange.spot.match_once("BTC-USD")["confirmed_trades"] == 1, "funded two-sided spot sale")
        exchange.spot.submit_order("classic", "buy-back", "BTC-USD", D(".1"), D(100))
        exchange.spot.submit_order("liquidity", "sell-spot", "BTC-USD", D("-.1"), D(100))
        require(exchange.spot.match_once("BTC-USD")["confirmed_trades"] == 1, "funded two-sided spot purchase")
        credit.repay("classic", "repay", "BTC", D(".101"))
        require(D(exchange.account("classic")["balances"]["USD"]) == D("999.992"), "spot cash flow and cumulative fees")
        require(D(exchange.account("classic")["balances"]["BTC"]) == D(".999"), "principal and interest repayment")
        checks.append("explicit funded borrowing, spot asset locks, real cash matching, separate interest and repayment")
        exchange.submit_order("classic", "open", "BTC-PERP", D(90), D(100))
        exchange.submit_order("liquidity", "open-short", "BTC-PERP", D(-90), D(100))
        worker = ExchangeWorker(exchange)
        require(worker.run_once()["linear_trades"] == 1, "actual opposing perpetual orders")
        publish(2, 90)
        exchange.submit_order("liquidity", "first-depth", "BTC-PERP", D(45), D(90))
        require(worker.run_once()["linear_trades"] == 1, "first confirmed partial liquidation")
        require(D(exchange.account("classic")["positions"]["BTC-PERP"]["quantity"]) == 45, "unfilled half remains risk")
        require(worker.run_once()["linear_trades"] == 0, "no liquidity must not fabricate fills")
        checks.append("market shock, automatic risk freeze, real partial liquidation and residual-risk preservation")
        exchange = reopen()
        exchange.submit_order("liquidity", "second-depth", "BTC-PERP", D(45), D(90))
        worker = ExchangeWorker(exchange)
        require(worker.run_once()["linear_trades"] == 1, "restarted worker resumes remaining liquidation")
        worker.run_once()
        final = exchange.account("classic")
        require(not final["positions"], "confirmed liquidation closes only the remaining quantity")
        # Independent cashflow: 1000 - spot fees .008 - realized loss 900
        # - opening fee 3.6 - closing fee 3.24 = 93.152 USD; BTC interest .001.
        require(D(final["balances"]["USD"]) == D("93.152"), "hand-computed final USD")
        require(D(final["balances"]["BTC"]) == D(".999"), "hand-computed BTC interest")
        checks.append("worker restart, second matched liquidation, recovery and hand-computed terminal balances")
        reconciliation = reconcile_exchange(exchange, matching_only=True)
        spot_check = exchange.spot.verify()
        require(spot_check["matches"] == 2, "spot receipt and double-entry reconciliation")
        require(ClassicImporter(exchange).verify() == 1, "source receipt and original postings remain verifiable")
        require(exchange.credit.verify()["nonzero_liabilities"] == 0, "no residual debt after complete repayment")
        checks.append("read-only four-side replay plus source, spot and debt reconciliation after reopening storage")
        return {"status": "passed", "production_approved": False, "checks": checks,
                "linear_matches": 3, "spot_matches": 2,
                "final_balances": final["balances"], "reconciliation": reconciliation,
                "source_fence_verified": False,
                "scope": "synthetic single-node Cross; not production capacity or real-source cutover approval"}
