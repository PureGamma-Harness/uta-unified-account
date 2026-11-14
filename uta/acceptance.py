"""Deterministic synthetic acceptance of the durable single-node foundation.

This command never connects to a venue or uses existing account state. It is a
functional smoke gate, not the 30-minute capacity/HA/real-funds acceptance gate.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal as D
from pathlib import Path
from tempfile import TemporaryDirectory

from .market import MarketSnapshot
from .models import AssetSpec, InstrumentSpec
from .ops import backup_database, restore_database
from .service import ExchangeService
from .storage import Database
from .worker import OutboxConsumer


def _require(condition: bool, message: str) -> None:
    # Assertions must remain active under python -O in an acceptance command.
    if not condition:
        raise RuntimeError("acceptance failed: " + message)


def _foundation_acceptance() -> dict:
    now = datetime(2026, 11, 14, tzinfo=timezone.utc)
    scales = {"USD": 8}
    checks = []
    with TemporaryDirectory(prefix="uta-synthetic-") as directory:
        database = Database(Path(directory) / "exchange.sqlite3")
        service = ExchangeService(database, scales, clock=lambda: now)
        service.create_account("synthetic")
        service.deposit("synthetic", "funding-1", "USD", D(10000))
        market = MarketSnapshot(1, now, {"USD": AssetSpec(D(1), D(1))},
                                {"BTC-PERP": InstrumentSpec(D(20000), D(".1"), D(".05"))})
        service.publish_market(market)
        _require(not service.readiness()["ready"], "new database must start halted")
        service.set_kill_switch(False)
        service.submit_order("synthetic", "open", "BTC-PERP", D(".1"), D(20000))
        service.apply_fill("synthetic", "open", "open-fill", D(".1"), D(20000))
        checks.append("durable admission, reservation and atomic local settlement")
        service.publish_market(MarketSnapshot(2, now, market.assets,
                               {"BTC-PERP": InstrumentSpec(D(21000), D(".1"), D(".05"))}))
        service.submit_order("synthetic", "close", "BTC-PERP", D("-.1"), D(21000), reduce_only=True)
        service.apply_fill("synthetic", "close", "close-1", D("-.04"), D(21000))
        service.apply_fill("synthetic", "close", "close-2", D("-.06"), D(21000))
        account = service.account("synthetic")
        _require(not account["positions"], "round trip must leave no position")
        _require(D(account["balances"]["USD"]) == D("10098.36"), "independent round-trip cash flow")
        _require(D(account["open_order_margin"]) == 0, "terminal orders must release reserve")
        checks.append("partial fills, cumulative fees and hand-computed round-trip balance")
        before = (service.ledger.journal(), service.events(limit=1000))
        restarted = ExchangeService(Database(database.path), scales, clock=lambda: now)
        restarted.apply_fill("synthetic", "close", "close-2", D("-.06"), D(21000))
        restarted.deposit("synthetic", "funding-1", "USD", D("10000.0"))
        _require(before == (restarted.ledger.journal(), restarted.events(limit=1000)), "restart idempotency")
        checks.append("restart recovery and immutable command deduplication")
        seen = []
        consumer = OutboxConsumer(database, restarted, "acceptance-audit", seen.append, clock=lambda: now)
        delivered = consumer.run_once()
        _require(delivered == len(before[1]), "all committed events must be delivered")
        _require(OutboxConsumer(database, restarted, "acceptance-audit", seen.append,
                               clock=lambda: now).run_once() == 0, "durable event checkpoint")
        checks.append("recoverable event consumption with persistent checkpoint")
        backup_path = Path(directory) / "backup.sqlite3"
        backup_database(database.path, backup_path)
        restored_path = Path(directory) / "restored.sqlite3"
        restore_database(backup_path, restored_path)
        restored = ExchangeService(Database(restored_path), scales, clock=lambda: now)
        _require(restored.account("synthetic") == account, "restored financial state must match")
        ledger_events = restored.ledger.verify()
        checks.append("consistent backup, offline restore and exact ledger replay")
        return {"status": "passed", "scope": "synthetic single-node functional foundation",
                "production_approved": False, "checks": checks,
                "ledger_events": ledger_events, "outbox_events": delivered}


def run_acceptance() -> dict:
    from .vertical import run_vertical_acceptance
    result = _foundation_acceptance()
    result["vertical"] = run_vertical_acceptance()
    result["checks"].append("M1 classic / credit / spot / paired perpetual / liquidation / restart / reconciliation")
    return result


if __name__ == "__main__":
    import json
    print(json.dumps(run_acceptance(), indent=2))
