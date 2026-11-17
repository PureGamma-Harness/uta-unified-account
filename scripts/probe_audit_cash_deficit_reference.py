#!/usr/bin/env python3
"""Independent a35 reference cases, recording the actual tested source identity."""

import argparse
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from decimal import Decimal as D
from fractions import Fraction as F
import hashlib
import json
from pathlib import Path
import platform
import sqlite3
import sys
from tempfile import TemporaryDirectory
import time
import subprocess

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from uta.decision_audit import DecisionAudit
from uta.market import MarketSnapshot
from uta.models import AssetSpec, InstrumentSpec
from uta.portfolio import (BorrowLimits, CollateralRule, CollateralTier, LinearMarginRule,
                           LoanAccount, PortfolioRules, calculate_cross_risk)
from uta.products import AccountMode, ProductCatalog, ProductKind, ProductSpec, TradingStatus


FROZEN_COMMIT = "a35fd56fc98126b3e5cced8a459bd04ca580e537"
SOURCE_HASHES = {
    "uta/decision_audit.py": "50671902d688cfe371e320d79d6fd5c329014ce9291dc522e5bc8f828424d5e6",
    "uta/service.py": "76e666497bd37c4955d0ac67bc7fd751387fa585047c3ed28c24565add13e0bd",
    "uta/portfolio.py": "c707d1bc45d8e73e671552bcd31fba582780974f1bb0da434ac2b8cee7c46879",
}
NOW = datetime(2026, 11, 17, tzinfo=timezone.utc)


def configuration():
    catalog = ProductCatalog(1, {"BTC-PERP": ProductSpec("BTC-PERP", ProductKind.LINEAR_PERPETUAL,
        "BTC", "USD", "USD", D(".01"), D(".01"), D(1), multiplier=D(1), status=TradingStatus.ACTIVE)})
    rules = PortfolioRules(1,
        {"USD": CollateralRule("USD", (CollateralTier(None, D(1)),), D(".5")),
         "BTC": CollateralRule("BTC", (CollateralTier(None, D(".8")),), D(".5"))},
        {"BTC": BorrowLimits("BTC", D(10), D(".2"), D(".1"), D(".00000001"))},
        {"tier-1": LinearMarginRule("tier-1", D(".1"), D(".05"))}, D(10000))
    market = MarketSnapshot(1, NOW,
        {"USD": AssetSpec(D(1), D(1)), "BTC": AssetSpec(D(100), D(".8"))},
        {"BTC-PERP": InstrumentSpec(D(100), D(".1"), D(".05"))})
    policy = {"format": 1, "risk_mode": "phase1_cross", "catalog": json.loads(catalog.to_json()),
              "rules": json.loads(rules.to_json()), "scales": {"USD": 2, "BTC": 8},
              "fee_rate": "0.01", "max_price_age_us": 5000000}
    return catalog, rules, market, policy


def text(value):
    value = F(value)
    numerator, denominator = value.numerator, value.denominator
    scale = 0
    while 10 ** scale % denominator:
        scale += 1
        if scale > 40:
            return str(value)
    scaled = abs(numerator) * (10 ** scale // denominator)
    if not scale:
        return str(numerator)
    digits = str(scaled).zfill(scale + 1)
    return (("-" if numerator < 0 else "") + digits[:-scale] + "." + digits[-scale:]).rstrip("0").rstrip(".")


def hand_risk(state):
    """Exact independent USD arithmetic; fixed declared price/rates, multiplier1."""
    prices = {"USD": F(1), "BTC": F(100)}
    factors = {"USD": F(1), "BTC": F(4, 5)}
    balances = {asset: F(value) for asset, value in state["balances"].items()}
    frozen = {asset: F(value) for asset, value in state["frozen_assets"].items()}
    principal = sum((F(row["principal"]) * prices[row["asset"]] for row in state["liabilities"]), F(0))
    interest = sum((F(row["interest"]) * prices[row["asset"]] for row in state["liabilities"]), F(0))
    deficits = sum((-min(F(0), value) * prices[asset] for asset, value in balances.items()), F(0))
    gross = sum((max(F(0), value) * prices[asset] for asset, value in balances.items()), F(0))
    collateral = sum(((max(F(0), value) - frozen.get(asset, F(0))) * prices[asset] * factors[asset]
                      for asset, value in balances.items()), F(0))
    pnl = sum((F(position["quantity"]) * 100 - F(position["cost_basis"]) for position in state["positions"].values()), F(0))
    marked_notional = sum((abs(F(position["quantity"])) * 100 for position in state["positions"].values()), F(0))
    loan_im, loan_mm = (principal + interest) / 5, (principal + interest) / 10
    im, mm = loan_im + marked_notional / 10, loan_mm + marked_notional / 20
    reserve = F(0)
    for order in state["orders"]:
        remaining = F(order["quantity"]) - F(order["filled_quantity"])
        limit, mark = F(order["limit_price"]), F(100)
        fee_raw = (F(order["fee_notional"]) + abs(remaining) * limit) / 100
        fee_cents = -((-fee_raw * 100) // 1)
        fee = F(fee_cents, 100) - F(order["charged_fee"])
        reserve += (F(0) if order["reduce_only"] else abs(remaining) * max(mark, limit) / 10)
        reserve += max(F(0), remaining * (limit - mark)) + fee
    debt = principal + interest + deficits
    result = {"accounting_equity": gross - debt + pnl, "collateral_value": collateral,
              "risk_equity": collateral - debt + pnl, "loan_value": collateral / 2,
              "principal_value": principal, "interest_value": interest, "cash_deficit_value": deficits,
              "debt_value": debt, "unrealized_pnl": pnl,
              "frozen_value": sum((value * prices[asset] for asset, value in frozen.items()), F(0)),
              "initial_margin": im, "maintenance_margin": mm,
              "available_margin": collateral - debt + pnl - im - reserve,
              "equity": collateral - debt + pnl, "open_order_margin": reserve}
    return {key: text(value) for key, value in result.items()}


def pure_probe():
    catalog, rules, market, policy = configuration()
    state = {"balances": {"USD": "-1", "BTC": "1"}, "frozen_assets": {},
             "positions": {}, "orders": [], "liabilities": [], "version": 1}
    results = []
    start = time.perf_counter()
    for name, liabilities in (("no_loan_debt", []), ("explicit_principal_and_interest", [{"asset": "BTC", "principal": "0.1", "interest": "0.01"}])):
        current = deepcopy(state)
        current["liabilities"] = liabilities
        expected = hand_risk(current)
        replayed = DecisionAudit._replay_state(current, market, policy)
        account = LoanAccount(gross_assets={"BTC": D(1)}, cash_deficits={"USD": D(1)},
            principal={row["asset"]: D(row["principal"]) for row in liabilities},
            interest={row["asset"]: D(row["interest"]) for row in liabilities}, mode=AccountMode.CROSS)
        cross = calculate_cross_risk(account, market, catalog, rules, now=NOW, max_age=timedelta(seconds=5))
        cross_values = {key: text(F(getattr(cross, key))) for key in expected if key not in ("equity", "open_order_margin")}
        matches = replayed == expected and all(cross_values[key] == expected[key] for key in cross_values)
        results.append({"id": name, "archival_state": current, "independent_fraction": expected,
                        "actual_replay_state": replayed, "actual_cross_calculator": cross_values,
                        "matches_independent": matches})
    all_match = all(case["matches_independent"] for case in results)
    return {"status": "NO_DIFFERENCE_REPRODUCED_IN_ACTUAL_FROZEN_PURE_HELPER" if all_match else "DIFFERENCE_REQUIRES_CLASSIFICATION", "policy": policy,
            "market": json.loads(market.to_json()), "cases": results,
            "arithmetic_elapsed_seconds": round(time.perf_counter() - start, 6),
            "all_match": all_match,
            "scope": "pure archival state/helper/Cross; no actual service transaction or audit archive reachability proved by this phase"}


def service_probe():
    """Real approved local controller commands; never hand-written account SQL."""
    from uta.credit import CreditService
    from uta.service import ExchangeService
    from uta.storage import Database

    catalog, rules, market, _ = configuration()
    started = time.perf_counter()
    with TemporaryDirectory(prefix="uta-a35-cash-deficit-reference-") as temporary:
        path = Path(temporary) / "local.sqlite3"
        db = Database(path)
        kwargs = {"product_catalog": catalog, "portfolio_rules": rules,
                  "fee_rate": D(".01"), "clock": lambda: NOW}
        bootstrap = ExchangeService(db, {"USD": 2, "BTC": 8}, **kwargs)
        bootstrap.create_account("alice")
        bootstrap.deposit("alice", "owned-btc", "BTC", D(".9"))
        bootstrap.publish_market(market)
        bootstrap.set_kill_switch(False)
        credit = CreditService(bootstrap)
        credit.configure_asset_limit("BTC", D(10))
        credit.configure_limit("alice", "BTC", D(10))
        funded = credit.fund_pool("pool", "BTC", D(1), source_reference="synthetic:a35:independent-pool")
        # These are pre-seal bootstrap obligations. No managed owner/cap exists.
        borrowed = credit.borrow("alice", "bootstrap-loan", "BTC", D(".1"))
        accrued = credit.accrue_interest("alice", "opening-interest", "BTC", D(".01"))
        service = ExchangeService(db, {"USD": 2, "BTC": 8}, decision_audit=True, **kwargs)
        opening = service.account("alice")
        order = service.submit_order("alice", "fee-order", "BTC-PERP", D(1), D(100))
        fill = service.apply_fill("alice", "fee-order", "fee-fill", D(1), D(100))
        decisions = []
        for identity in (order["decision_id"], fill["execution_decision_id"]):
            archived = service.audit.decision(identity)
            replayed = service.audit.replay(identity)
            sides = {}
            for side in ("before", "after"):
                expected = hand_risk(archived["inputs"][side])
                recorded = archived["summary"]["risk_" + side]
                compared = {key: recorded[key] for key in expected}
                helper = DecisionAudit._replay_state(archived["inputs"][side], market, DecisionAudit.policy(service))
                sides[side] = {"independent_fraction": expected, "actual_recorded_risk": compared,
                               "actual_replay_helper": helper,
                               "all_match": expected == compared == helper == replayed["values"][side]}
            decisions.append({"decision_id": identity, "kind": archived["kind"],
                              "actual_archival_decision": archived, "actual_full_replay": replayed,
                              "independent_comparisons": sides,
                              "matches": replayed["matches"] and all(s["all_match"] for s in sides.values())})
        with db.read_transaction() as connection:
            final_state = service._audit_state(connection, "alice")
            final_risk = service._risk(connection, "alice", service._market(connection))
        expected_final = hand_risk(final_state)
        actual_final = {key: final_risk[key] for key in expected_final}
        journal = [{"event_id": event.event_id, "sequence": event.sequence,
                    "postings": [{"account": p.account, "asset": p.asset, "amount": text(F(p.amount))} for p in event.postings]}
                   for event in service.ledger.journal()]
        credit_verification = CreditService(service).verify()
        all_match = (all(d["matches"] for d in decisions) and expected_final == actual_final
                     and final_state["balances"]["USD"] == "-1" and final_state["balances"]["BTC"] == "1"
                     and final_state["liabilities"] == [{"asset": "BTC", "principal": "0.1", "interest": "0.01"}])
        data = {"status": "NO_DIFFERENCE_REPRODUCED_ON_REAL_REACHABLE_ORDER_FILL_ARCHIVES" if all_match else "ACTUAL_ARCHIVAL_DIFFERENCE_REQUIRES_CLASSIFICATION",
                "temp_path": str(path), "opening_account": opening, "actual_controller_results": {
                    "pool_funding": funded, "preseal_borrow": borrowed, "opening_interest": accrued, "order": order, "fill": fill},
                "actual_decisions": decisions, "final_archival_state": final_state,
                "actual_final_service_risk": actual_final, "independent_final_risk": expected_final,
                "journal": journal, "actual_ledger_credit_verification": credit_verification,
                "actual_policy": DecisionAudit.policy(service), "actual_market_payload": market.to_json(),
                "actual_artifact_manifest": service.audit.artifact(service.audit.artifact_id),
                "all_match": all_match,
                "scope": "privileged local synthetic pre-seal credit bootstrap then actual audited submit_order/apply_fill; no HMAC, managed BORROW, new capability or external executed trade claim"}
    data["temp_directory_cleaned"] = not Path(temporary).exists()
    data["service_elapsed_seconds"] = round(time.perf_counter() - started, 6)
    data["sqlite_version"] = sqlite3.sqlite_version
    return data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--phase", choices=("pure", "service"), default="pure")
    args = parser.parse_args()
    hashes = {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest() for path in SOURCE_HASHES}
    if hashes != SOURCE_HASHES:
        raise SystemExit("frozen source hashes changed; stop")
    started = time.perf_counter()
    result = pure_probe() if args.phase == "pure" else service_probe()
    checkout = subprocess.run(["git", "rev-parse", "--show-toplevel", "HEAD"], cwd=ROOT,
                              capture_output=True, text=True)
    identity = checkout.stdout.splitlines()
    actual_commit = (identity[1] if checkout.returncode == 0 and len(identity) == 2
                     and Path(identity[0]).resolve() == ROOT.resolve() else None)
    result.update(reference_commit=FROZEN_COMMIT, code_commit=actual_commit,
                  python=platform.python_version(), source_sha256=hashes,
                  probe_source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  all_uta_source_sha256={str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
                                         for path in sorted((ROOT / "uta").rglob("*.py"))},
                  elapsed_after_imports_seconds=round(time.perf_counter() - started, 6),
                  native_or_production_credit_go=False)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"all_match": result["all_match"], "phase": args.phase,
                      "elapsed_after_imports_seconds": result["elapsed_after_imports_seconds"]}))
    return not result["all_match"]


if __name__ == "__main__":
    raise SystemExit(main())
