"""Read-only, independent integer/Fraction checks for nine synthetic namespaces.

No UTA calculation, hashing helper, fixture expected-value function or writer is
called here. Component verifiers are separately reported by the entry driver.
Full rows, claim nonces and financial snapshots remain in the private namespace.
"""
from collections import Counter
from decimal import Decimal
from fractions import Fraction
from hashlib import sha256
import json


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value):
    return sha256(canonical(value).encode()).hexdigest()


def fraction(value):
    if type(value) is not str:
        raise ValueError("oracle requires stored decimal text")
    return Fraction(Decimal(value))


def integer(value):
    if type(value) is not str or str(int(value)) != value:
        raise ValueError("noncanonical integer units")
    return int(value)


def unpack(raw):
    value = json.loads(raw)
    if canonical(value) != raw:
        raise ValueError("noncanonical archived JSON")
    return value


def independent_journal(connection, expected):
    balances, journals, previous = {}, {}, "0" * 64
    events = list(connection.execute("SELECT * FROM ledger_events ORDER BY sequence"))
    if len(events) != expected["journals"] or dict(connection.execute("SELECT asset,scale FROM ledger_assets")) != {"USD": 2}:
        raise ValueError("manual journal count or currency scale differs")
    for ordinal, event in enumerate(events, 1):
        if event["sequence"] != ordinal or event["sealed"] != 1 or event["previous_hash"] != previous:
            raise ValueError("journal sequence/seal/prior differs")
        rows = list(connection.execute("SELECT ordinal,account,asset,units FROM ledger_postings WHERE sequence=? ORDER BY ordinal", (ordinal,)))
        if [row[0] for row in rows] != list(range(len(rows))):
            raise ValueError("journal posting ordinals differ")
        postings = [(r[1], r[2], integer(r[3])) for r in rows]
        if not postings or postings != sorted(postings) or any(not p[2] for p in postings):
            raise ValueError("noncanonical journal postings")
        currency = Counter()
        for account, asset, units in postings:
            if asset != "USD":
                raise ValueError("unexpected currency")
            currency[asset] += units
            balances[account, asset] = balances.get((account, asset), 0) + units
        if any(currency.values()):
            raise ValueError("per-currency double-entry imbalance")
        fingerprint = sha256(json.dumps(postings, ensure_ascii=True, separators=(",", ":")).encode()).hexdigest()
        event_hash = sha256(json.dumps([ordinal, event["event_id"], previous, fingerprint], ensure_ascii=True, separators=(",", ":")).encode()).hexdigest()
        if event["fingerprint"] != fingerprint or event["event_hash"] != event_hash:
            raise ValueError("independent journal hash differs")
        journals[event["event_id"]] = postings
        previous = event_hash
    actual = {(r["account"], r["asset"]): integer(r["units"]) for r in connection.execute("SELECT * FROM ledger_balances")}
    if balances != actual:
        raise ValueError("full materialized balances differ from independent replay")
    manual = {("customer:" + k, "USD"): int(fraction(v) * 100) for k, v in expected["cash"].items()}
    manual.update({(k, "USD"): int(fraction(v) * 100) for k, v in expected["system"].items()})
    if {k: v for k, v in actual.items() if v} != {k: v for k, v in manual.items() if v}:
        raise ValueError("full nonzero balances differ from manual oracle")
    return journals


def independent_matching(connection, expected, journals):
    if not expected["matches"]:
        if connection.execute("SELECT 1 FROM sqlite_master WHERE name='uta_matches'").fetchone() is not None:
            raise ValueError("empty capability fixture unexpectedly has matching schema")
        if connection.execute("SELECT COUNT(*) FROM uta_fills").fetchone()[0]:
            raise ValueError("empty namespace has fills")
        return
    matches = list(connection.execute("SELECT * FROM uta_matches ORDER BY sequence"))
    fills = {(r["account_id"], r["fill_id"]): r for r in connection.execute("SELECT * FROM uta_fills")}
    if len(matches) != len(expected["trades"]) or len(fills) != 2 * expected["matches"]:
        raise ValueError("manual matches/fills differ")
    paired = set()
    for index, (match, trade) in enumerate(zip(matches, expected["trades"]), 1):
        buyer, seller, quantity, price, fee, buy_pnl, sell_pnl = trade
        if (match["sequence"] != index or match["symbol"] != "BTC-PERP"
                or match["buy_account_id"] != buyer or match["sell_account_id"] != seller
                or fraction(match["quantity"]) != fraction(quantity) or fraction(match["price"]) != fraction(price)):
            raise ValueError("manual matched economic terms differ")
        for side, account, sign, pnl in (("buy", buyer, 1, buy_pnl), ("sell", seller, -1, sell_pnl)):
            key = account, match[side + "_fill_id"]
            if key in paired or key not in fills:
                raise ValueError("duplicate/unpaired fill")
            paired.add(key)
            fill = fills[key]
            order = connection.execute("SELECT * FROM uta_orders WHERE account_id=? AND order_id=?", (account, match[side + "_order_id"])).fetchone()
            if (order is None or fill["order_id"] != order["order_id"] or order["symbol"] != "BTC-PERP"
                    or order["status"] != "FILLED" or fraction(order["quantity"]) != fraction(order["filled_quantity"])
                    or fraction(fill["quantity"]) != sign * fraction(quantity)
                    or fraction(fill["price"]) != fraction(price) or fraction(fill["fee"]) != fraction(fee)
                    or fraction(fill["realized_pnl"]) != fraction(pnl)):
                raise ValueError("order/fill/manual cash linkage differs")
            key_hash = sha256(canonical([account, fill["fill_id"]]).encode()).hexdigest()
            wanted = []
            if fraction(fee):
                wanted += [("customer:" + account, "USD", -int(fraction(fee) * 100)), ("system:fees", "USD", int(fraction(fee) * 100))]
            if fraction(pnl):
                wanted += [("customer:" + account, "USD", int(fraction(pnl) * 100)), ("system:realized-pnl", "USD", -int(fraction(pnl) * 100))]
            if journals.get("fill:" + key_hash) != sorted(wanted):
                raise ValueError("confirmed fill/journal differs")
    if paired != set(fills):
        raise ValueError("orphan fill")


def independent_obligations(connection, expected, journals):
    if expected["capability"] == "old":
        if connection.execute("SELECT 1 FROM sqlite_master WHERE name='funding_obligations_tasks'").fetchone() is not None:
            raise ValueError("old capability unexpectedly migrated")
        return {"tasks": 0, "applied": 0, "outstanding": 0}
    tasks = {r["obligation_id"]: dict(r) for r in connection.execute("SELECT * FROM funding_obligations_tasks")}
    if {k: v["state"] for k, v in tasks.items()} != expected["tasks"]:
        raise ValueError("manual task state inventory differs")
    commands = {r["command_id"]: r for r in connection.execute("SELECT * FROM funding_obligations_commands")}
    previous, tails, event_count = "0" * 64, {}, 0
    for index, event in enumerate(connection.execute("SELECT * FROM funding_obligations_events ORDER BY sequence"), 1):
        payload = unpack(event["payload"])
        command = commands.get(event["command_id"])
        if command is None:
            raise ValueError("event has no command")
        result = unpack(command["result"])
        unpack(command["request"])
        if (event["sequence"] != index or event["previous_hash"] != previous
                or event["event_hash"] != digest([previous, event["obligation_id"], event["command_id"], payload])
                or command["result_sha"] != digest(result) or payload["command_result_sha"] != digest(result)
                or command["obligation_id"] != event["obligation_id"] or result["obligation_id"] != event["obligation_id"]):
            raise ValueError("independent obligation command/hash chain differs")
        tails[event["obligation_id"]] = payload["task"]
        previous, event_count = event["event_hash"], index
    if event_count != len(commands) or set(tails) != set(tasks):
        raise ValueError("command/event/task inventory differs")
    for identifier, task in tasks.items():
        view = {k: task[k] for k in ("obligation_id", "symbol", "period_end", "rate", "schedule_command_id", "config_sha", "state", "reason", "revision", "generation", "owner", "until_at", "cut_sha", "receipt_sha")}
        view.update(outstanding=task["state"] != "APPLIED", nonce_digest=None if task["nonce"] is None else sha256(task["nonce"].encode()).hexdigest())
        if tails[identifier] != view:
            raise ValueError("task differs from independent event tail")
    cuts = {r["obligation_id"]: r for r in connection.execute("SELECT * FROM funding_obligations_cuts")}
    if set(cuts) != set(expected["cuts"]):
        raise ValueError("manual immutable cut inventory differs")
    for identifier, row in cuts.items():
        cut = unpack(row["payload"])
        if row["digest"] != digest(cut) or tasks[identifier]["cut_sha"] != row["digest"]:
            raise ValueError("immutable cut digest differs")
        plan = cut["plan"]
        quantities = {p["account_id"]: fraction(p["quantity"]) for p in cut["positions"]}
        manual_cut = expected["cuts"][identifier]
        if (fraction(plan["mark"]) != fraction(manual_cut["mark"]) or fraction(plan["rate"]) != fraction(manual_cut["rate"])
                or quantities != {k: fraction(v) for k, v in manual_cut["quantities"].items()}
                or json.loads(cut["market_payload"])["version"] != manual_cut["market_version"]
                or cut["market_snapshot_id"] != "sha256:" + sha256(cut["market_payload"].encode()).hexdigest()):
            raise ValueError("manual cut economic terms or market identity differs")
        if sum(quantities.values(), Fraction()) or len(quantities) != len(cut["positions"]):
            raise ValueError("trusted cut inventory is not uniquely net flat")
        for leg in plan["legs"]:
            exact = -quantities[leg["account_id"]] * fraction(plan["mark"]) * fraction(plan["rate"]) * 100
            truncated = abs(exact.numerator) // exact.denominator * (-1 if exact < 0 else 1)
            if integer(leg["cash_units"]) != truncated:
                raise ValueError("independent toward-zero funding leg differs")
    receipts = {r["obligation_id"]: r for r in connection.execute("SELECT * FROM funding_obligations_receipts")}
    if set(receipts) != {k for k, t in tasks.items() if t["state"] == "APPLIED"}:
        raise ValueError("APPLIED task/receipt inventory differs")
    for identifier, row in receipts.items():
        receipt, cut = unpack(row["payload"]), unpack(cuts[identifier]["payload"])
        if row["digest"] != digest(receipt) or tasks[identifier]["receipt_sha"] != row["digest"] or receipt["cut_sha"] != cuts[identifier]["digest"]:
            raise ValueError("immutable receipt/cut reference differs")
        risk_market = json.loads(receipt["risk_market_payload"])
        if (risk_market["version"] != expected["receipt_risk_market_version"]
                or receipt["risk_market_snapshot_id"] != "sha256:" + sha256(receipt["risk_market_payload"].encode()).hexdigest()):
            raise ValueError("manual current-risk market identity differs from frozen cut")
        if expected["receipt_risk_market_version"] == 4 and expected["positions"] == {} and risk_market["instruments"] != {}:
            raise ValueError("real flatting cash-only risk quote differs")
        if expected["cash"].get("treasury") == ".99":
            capital = receipt["capital_transfer"]
            if (capital is None or capital["source_account_id"] != "treasury" or capital["deposit_reference"] != "approved-synthetic-capital"
                    or integer(capital["units"]) != 1 or fraction(capital["amount"]) != Fraction(1, 100)):
                raise ValueError("manual real treasury transfer differs")
            deposit = connection.execute("SELECT amount FROM uta_deposits WHERE account_id='treasury' AND event_id='approved-synthetic-capital'").fetchone()
            if deposit is None or fraction(deposit[0]) != 1:
                raise ValueError("treasury capital lacks actual deposit")
        elif receipt["capital_transfer"] is not None:
            raise ValueError("unexpected capital transfer")
        for leg in cut["plan"]["legs"]:
            account, units = leg["account_id"], integer(leg["cash_units"])
            before, after = receipt["account_inputs_before"][account], receipt["account_inputs_after"][account]
            if (fraction(after["balances"]["USD"]) - fraction(before["balances"]["USD"]) != Fraction(units, 100)
                    or before["positions"] != after["positions"] or before["liabilities"] != after["liabilities"]):
                raise ValueError("frozen funding/current position cash movement differs")
            if units:
                event_id = "funding-obligations:leg:" + digest([identifier, account])
                if journals.get(event_id) != sorted([("customer:" + account, "USD", units), ("system:funding-obligations-clearing", "USD", -units)]):
                    raise ValueError("funding leg/journal linkage differs")
            if account in expected.get("risk", {}):
                for field, wanted in expected["risk"][account].items():
                    if fraction(receipt["risk_after"][account][field]) != fraction(wanted):
                        raise ValueError("manual healthy risk value differs")
    return {"tasks": len(tasks), "applied": len(receipts), "outstanding": len(tasks) - len(receipts)}


def independent_healthy_risk(connection, expected):
    """Narrow final-state formula, rejected outside the registered USD cases."""
    if not expected["cash"]:
        return
    policy = json.loads(connection.execute("SELECT value FROM uta_config WHERE key='risk_policy'").fetchone()[0])
    rules, catalog = policy["rules"], policy["catalog"]
    if (policy["mode"] != "phase1_cross" or catalog["settlement_asset"] != "USD"
            or rules["borrow_limits"] != {} or set(rules["collaterals"]) != {"USD"}
            or rules["collaterals"]["USD"] != {"loan_to_value": "1", "tiers": [{"up_to": None, "factor": "1"}]}
            or set(rules["linear_margin"]) != {"tier-1"}
            or rules["linear_margin"]["tier-1"] != {"initial_margin_rate": "0.1", "maintenance_margin_rate": "0.05"}
            or set(catalog["products"]) != {"BTC-PERP"}):
        raise ValueError("independent narrow risk oracle UNSUPPORTED policy")
    product = catalog["products"]["BTC-PERP"]
    if (product["kind"] != "linear_perpetual" or fraction(product["multiplier"]) != 1
            or product["quote_asset"] != "USD" or product["settlement_asset"] != "USD" or product["risk_tier"] != "tier-1"):
        raise ValueError("independent narrow risk oracle UNSUPPORTED product")
    if connection.execute("SELECT COUNT(*) FROM uta_orders WHERE status IN ('OPEN','PARTIALLY_FILLED')").fetchone()[0]:
        raise ValueError("independent narrow risk oracle UNSUPPORTED live reservation")
    market = json.loads(connection.execute("SELECT payload FROM uta_market WHERE singleton=1").fetchone()[0])
    if market["assets"] != {"USD": {"price": "1", "collateral_factor": "1"}}:
        raise ValueError("independent narrow risk oracle UNSUPPORTED collateral")
    # These inputs come from actual final ledger/position/market rows. Receipt
    # inputs and risk output never supply the independent calculation.
    for account, manual in expected.get("risk", {}).items():
        row = connection.execute("SELECT units FROM ledger_balances WHERE account=? AND asset='USD'", ("customer:" + account,)).fetchone()
        cash = Fraction(integer(row[0]), 100) if row else Fraction()
        equity, im, mm = cash, Fraction(), Fraction()
        for position in connection.execute("SELECT * FROM uta_positions WHERE account_id=?", (account,)):
            if position["symbol"] != "BTC-PERP":
                raise ValueError("independent narrow risk oracle UNSUPPORTED symbol")
            mark = fraction(market["instruments"]["BTC-PERP"]["mark_price"])
            quantity, cost = fraction(position["quantity"]), fraction(position["cost_basis"])
            equity += quantity * mark - cost
            im += abs(quantity * mark) / 10
            mm += abs(quantity * mark) / 20
        computed = {"equity": equity, "initial_margin": im, "maintenance_margin": mm, "available_margin": equity - im}
        if any(computed[key] != fraction(value) for key, value in manual.items()):
            raise ValueError("actual final-state independent healthy risk differs from manual case")


def check(connection, label, expected):
    if connection.execute("PRAGMA query_only").fetchone()[0] != 1:
        raise ValueError("independent oracle requires readonly snapshot")
    if [r[0] for r in connection.execute("PRAGMA integrity_check")] != ["ok"] or connection.execute("PRAGMA foreign_key_check").fetchone() is not None:
        raise ValueError("SQLite integrity/foreign-key failure")
    journals = independent_journal(connection, expected)
    if {r[0] for r in connection.execute("SELECT account_id FROM uta_accounts")} != set(expected["cash"]):
        raise ValueError("manual account inventory differs")
    positions = {(r["account_id"], r["symbol"]): [fraction(r["quantity"]), fraction(r["cost_basis"])] for r in connection.execute("SELECT * FROM uta_positions")}
    if positions != {(account, "BTC-PERP"): [fraction(v) for v in pair] for account, pair in expected["positions"].items()}:
        raise ValueError("manual current quantity/cost differs")
    if connection.execute("SELECT COUNT(*) FROM uta_liabilities").fetchone()[0]:
        raise ValueError("unplanned borrowing/principal")
    independent_healthy_risk(connection, expected)
    independent_matching(connection, expected, journals)
    obligations = independent_obligations(connection, expected, journals)
    return {"label": label, "journals": len(journals), "matches": expected["matches"], "paired_fills": expected["matches"] * 2,
            **obligations, "independent_full_balances_positions_hashchains_and_cash_legs_equal": True,
            "risk_values_are_preregistered_healthy_manual_cases_only": True, "risk_eligibility_replayed": False}
