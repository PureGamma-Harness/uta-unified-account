"""CODE-only three-authority native matching cases; root GO is separate."""
from datetime import datetime, timezone
from decimal import Decimal as D
from fractions import Fraction
import json
from pathlib import Path
import re
import sys

from uta.market import MarketSnapshot
from uta.matching import Matcher
from uta.models import AssetSpec, InstrumentSpec
from uta.portfolio import CollateralRule, CollateralTier, LinearMarginRule, PortfolioRules
from uta.products import ProductCatalog, ProductKind, ProductSpec, TradingStatus
from uta.reconciliation import reconcile_exchange
from uta.service import ExchangeService, ServiceError
from uta.storage import Database


def require(value, message):
    if not value:
        raise AssertionError(message)


class Fixture:
    def __init__(self, directory, name, *, symbols, mm, scale, checkpoint):
        self.name, self.checkpoint = name, checkpoint
        self.path = Path(directory) / (name + ".sqlite3")
        require(not self.path.exists(), "authority must be new")
        self.scale, self.version, self.actions = scale, 0, []
        self.invocations = {}
        self.prices = dict(symbols)
        self.catalog = ProductCatalog(3, {symbol: ProductSpec(
            symbol, ProductKind.LINEAR_PERPETUAL, symbol.split("-", 1)[0], "USD", "USD",
            D("0.01") if scale == 2 else D("0.00000001"),
            D("0.1") if scale == 2 else D("0.00000001"), D("0.1"), status=TradingStatus.ACTIVE)
            for symbol in symbols})
        self.rules = PortfolioRules(5,
            {"USD": CollateralRule("USD", (CollateralTier(None, D(1)),), D(1))},
            {}, {"tier-1": LinearMarginRule("tier-1", D("0.1"), D(mm))}, D(0))
        self.mm = D(mm)
        self.exchange = ExchangeService(Database(self.path), {"USD": scale},
            product_catalog=self.catalog, portfolio_rules=self.rules, decision_audit=True)
        self.matcher = Matcher(self.exchange)
        self.quote("initial")
        self.step("unhalt", self.exchange.set_kill_switch, False)

    def step(self, label, function, *args, **kwargs):
        self.checkpoint(self.name, "native", label, "before")
        key = function.__qualname__
        self.invocations[key] = self.invocations.get(key, 0) + 1
        value = function(*args, **kwargs)
        self.actions.append({"label": label, "result": value})
        self.checkpoint(self.name, "native", label, "after")
        return value

    def quote(self, label, **prices):
        self.prices.update(prices)
        self.version += 1
        return self.step("quote-" + label, self.exchange.publish_market,
            MarketSnapshot(self.version, datetime.now(timezone.utc), {"USD": AssetSpec(D(1), D(1))},
                {symbol: InstrumentSpec(D(price), D("0.1"), self.mm)
                 for symbol, price in self.prices.items()}))

    def fund(self, account, amount):
        self.step("create-" + account, self.exchange.create_account, account)
        self.step("deposit-" + account, self.exchange.deposit, account, "synthetic-custody-" + account, "USD", D(amount))

    def order(self, account, identifier, symbol, quantity, price, *, reduce_only=False):
        self.quote("before-order-" + identifier)
        return self.step("order-" + identifier, self.exchange.submit_order, account, identifier,
                         symbol, D(quantity), D(price), reduce_only=reduce_only)

    def match(self, label, symbol, maximum=10):
        self.quote("before-match-" + label)
        return self.step(label, self.matcher.match_once, symbol, maximum)

    def capture(self):
        with self.exchange.database.transaction() as connection:
            names = [row[0] for row in connection.execute(
                "SELECT name FROM main.sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
            require(all(re.fullmatch(r"[a-z][a-z0-9_]{0,127}", name) for name in names), "unexpected table identity")
            tables = {}
            for name in names:
                select = "rowid AS book_sequence,*" if name == "uta_orders" else "*"
                rows = [dict(row) for row in connection.execute('SELECT ' + select + ' FROM main."' + name + '"')]
                tables[name] = sorted(rows, key=lambda row: json.dumps(row, sort_keys=True, separators=(",", ":")))
            schema = [tuple(row) for row in connection.execute(
                "SELECT type,name,tbl_name,sql FROM main.sqlite_master ORDER BY type,name")]
            count = self.exchange.ledger.verify(connection=connection)
            settings = {"journal_mode": connection.execute("PRAGMA journal_mode").fetchone()[0],
                        "synchronous": connection.execute("PRAGMA synchronous").fetchone()[0]}
        require(settings == {"journal_mode": "wal", "synchronous": 2}, "WAL/FULL changed")
        return {"tables": tables, "schema": schema, "ledger_events_verified": count, "settings": settings}

    def reject_without_effect(self, label, code, function, *args):
        before = self.capture()
        try:
            self.step(label, function, *args)
        except ServiceError as error:
            require((error.code, error.status) == (code, 409), "unexpected business rejection")
            outcome = {"code": error.code, "status": error.status, "message": str(error)}
            self.actions.append({"label": label, "expected_business_rejection": outcome})
            self.checkpoint(self.name, "native", label, "expected-business-rejection-after")
        else:
            raise AssertionError("expected native business rejection did not occur")
        after = self.capture()
        require(before == after, "rejected command left a durable business effect")
        return {"before": before, "after": after, "error": outcome}

    def replay_without_effect(self, label, function, *args):
        before = self.capture()
        value = self.step(label, function, *args)
        after = self.capture()
        require(before == after, "known accepted ID replay changed durable state")
        return {"before": before, "after": after, "result": value}

    def finish(self, expected_matches, cash, fees, custody, positions):
        self.quote("before-reopen")
        before = self.capture()
        self.exchange = ExchangeService(Database(self.path), {"USD": self.scale},
            product_catalog=self.catalog, portfolio_rules=self.rules, decision_audit=True)
        self.matcher = Matcher(self.exchange, initialize=False)
        after = self.capture()
        require(before == after, "native reopen changed saved business or guard state")
        expected_journals = {"maintenance-equality-rollback": 4, "IM-equality-lower-MM": 6,
                             "USD2-cumulative-partial-fee": 5}[self.name]
        require(after["ledger_events_verified"] == expected_journals
                and len(after["tables"]["ledger_postings"]) == 2 * expected_journals,
                "unexpected journal event/posting beyond the manual deposit/fee legs")
        strict = self.step("strict-matching", self.matcher.verify, strict=True)
        require((strict["matches"], strict["paired_fills"], strict["unpaired_fills"])
                == (expected_matches, 2 * expected_matches, 0), "actual matching correspondence failed")
        independent = self.step("independent-cashflow", reconcile_exchange, self.exchange)
        require(independent["status"] == "passed" and independent["matching_only"] is True,
                "independent journal/position cashflow replay failed")
        scale = 10 ** self.scale
        balances = {(row["account"], row["asset"]): int(row["units"]) for row in after["tables"]["ledger_balances"]}
        expected = {("customer:" + account, "USD"): Fraction(D(amount)) * scale for account, amount in cash.items()}
        expected.update({("system:fees", "USD"): Fraction(D(fees)) * scale,
                         ("system:custody", "USD"): -Fraction(D(custody)) * scale})
        require(all(value.denominator == 1 for value in expected.values()) and balances == expected,
                "independent hand cash/fees/custody table differs")
        actual_positions = {(row["account_id"], row["symbol"]): (D(row["quantity"]), D(row["cost_basis"]))
                            for row in after["tables"]["uta_positions"]}
        require(actual_positions == positions, "hand-computed final position/cost differs")
        require(not after["tables"]["uta_liabilities"], "unexpected debt in this linear-only scope")
        require(all(row["status"] in ("FILLED", "CANCELLED") for row in after["tables"]["uta_orders"]),
                "unexpected unfinished order")
        original_fill = next(row for row in after["tables"]["uta_risk_decisions"] if row["kind"] == "FILL_CONFIRMED")
        replay = self.step("one-old-audit-numeric-replay", self.exchange.audit.replay, original_fill["decision_id"])
        require(replay["matches"] is True, "original captured FILL numerical replay differs")
        self.quote("final-risk")
        risks = {account: self.step("risk-" + account, self.exchange.risk, account) for account in cash}
        final = self.capture()
        return {"case": self.name, "path": str(self.path), "before_reopen": before, "after_reopen": after,
                "final": final, "risks": risks, "strict": strict, "independent": independent,
                "numeric_replay": replay, "numeric_replay_proves_new_MM_eligibility": False,
                "actual_unique_matches": expected_matches, "actual_paired_fills": 2 * expected_matches,
                "top_level_step_invocations": self.invocations,
                "actions": self.actions, "performance_accepted": False, "production_approved": False}


def rollback_case(directory, checkpoint):
    f = Fixture(directory, "maintenance-equality-rollback", symbols={"ETH-PERP": "10", "BTC-PERP": "100"},
                mm="0.1", scale=8, checkpoint=checkpoint)
    f.fund("A", "11.04400009"); f.fund("B", "1000")
    f.order("A", "eth-A", "ETH-PERP", "1", "10")
    f.order("B", "eth-B", "ETH-PERP", "-1", "10")
    opened = f.match("open-real-ETH", "ETH-PERP", 1)
    require(opened["confirmed_trades"] == 1, "opening real ETH match missing")
    eth = opened["trades"][0]
    f.order("A", "btc-A", "BTC-PERP", "-1", "100")
    f.order("B", "btc-B", "BTC-PERP", "1", "100")
    f.quote("actual-ETH-price-change", **{"ETH-PERP": "9.9999999"})
    direct = f.reject_without_effect("direct-fresh-fill-equality", "insufficient_margin",
        f.exchange.apply_fill, "A", "btc-A", "direct-MM-equality", D(-1), D(100))
    require(direct["error"]["message"] == "new exposure requires positive maintenance margin surplus",
            "direct fresh fill did not reach the strict MM guard")
    before = f.capture()
    observed = []
    fill_code = ExchangeService._apply_fill.__code__
    guard_code = ExchangeService._require_maintenance_surplus.__code__
    def observe(frame, event, argument):
        if event not in ("call", "return") or frame.f_code is not fill_code and frame.f_code is not guard_code:
            return
        require(len(observed) < 32, "bounded native call observation overflow")
        parent = frame if frame.f_code is fill_code else frame.f_back
        item = {"event": event, "method": frame.f_code.co_name, "account": parent.f_locals.get("account_id")}
        if frame.f_code is guard_code and event == "call":
            projected = frame.f_locals["projected"]
            item["projected"] = {key: projected[key] for key in ("equity", "maintenance_margin", "available_margin")}
        if frame.f_code is fill_code and event == "return":
            item["returned_status"] = argument.get("status") if type(argument) is dict else None
        observed.append(item)
    require(sys.getprofile() is None, "do not overwrite another profiler")
    sys.setprofile(observe)
    try:
        # Use the same already-fresh quote: no added publication between snapshots.
        rejected_match = f.step("real-second-leg-MM-reject", f.matcher.match_once, "BTC-PERP", 1)
    finally:
        sys.setprofile(None)
    after = f.capture()
    require(rejected_match["confirmed_trades"] == 0 and rejected_match["attempts"] == 1,
            "unsafe BTC match was committed or did not reach an actual attempt")
    require(rejected_match["blocked"] == [{"code": "insufficient_margin", "account_id": "A", "order_id": "btc-A"}],
            "wrong second-leg rejection")
    require([(value["account_id"], value["order_id"], value["reason"]) for value in rejected_match["cancelled_orders"]]
            == [("A", "btc-A", "matching_rejected:insufficient_margin")], "wrong native cancellation")
    calls = [item for item in observed if item["event"] == "call" and item["method"] == "_apply_fill"]
    require([item["account"] for item in calls] == ["B", "A"], "did not observe buyer-first/seller-second native legs")
    b_return = next(index for index, item in enumerate(observed) if item["method"] == "_apply_fill"
                    and item["event"] == "return" and item["account"] == "B" and item["returned_status"] == "FILLED")
    a_call = next(index for index, item in enumerate(observed) if item["method"] == "_apply_fill"
                  and item["event"] == "call" and item["account"] == "A")
    require(b_return < a_call, "first leg did not actually return before rejected second leg")
    a_guard = [item["projected"] for item in observed if item["method"] == "_require_maintenance_surplus"
               and item["event"] == "call" and item["account"] == "A"]
    require(a_guard == [{"equity": "10.99999999", "maintenance_margin": "10.99999999", "available_margin": "0"}],
            "native seller guard did not observe the exact manual MM equality")
    for name, rows in before["tables"].items():
        if name not in {"uta_accounts", "uta_orders", "uta_events"}:
            require(after["tables"][name] == rows, "first-leg/second-leg financial or audit rows survived rollback: " + name)
    require(before["schema"] == after["schema"], "matching rejection changed schema")
    old_accounts = {row["account_id"]: row for row in before["tables"]["uta_accounts"]}
    new_accounts = {row["account_id"]: row for row in after["tables"]["uta_accounts"]}
    require(new_accounts["B"] == old_accounts["B"] and new_accounts["A"] == dict(old_accounts["A"], version=old_accounts["A"]["version"] + 1),
            "buyer mutation survived or seller cancellation version differs")
    old_orders = {(row["account_id"], row["order_id"]): row for row in before["tables"]["uta_orders"]}
    new_orders = {(row["account_id"], row["order_id"]): row for row in after["tables"]["uta_orders"]}
    require(set(new_orders) == set(old_orders), "matching rejection created/deleted an order")
    for key, row in old_orders.items():
        expected = dict(row, status="CANCELLED", version=new_accounts["A"]["version"]) if key == ("A", "btc-A") else row
        require(new_orders[key] == expected, "non-cancellation order mutation survived rollback")
    old_events = {row["sequence"]: row for row in before["tables"]["uta_events"]}
    new_events = {row["sequence"]: row for row in after["tables"]["uta_events"]}
    require(all(new_events.get(key) == row for key, row in old_events.items()), "past event changed")
    extra = [row for key, row in new_events.items() if key not in old_events]
    require(len(extra) == 1 and extra[0]["event_type"] == "ORDER_CANCELLED" and extra[0]["account_id"] == "A"
            and json.loads(extra[0]["payload"])["reason"] == "matching_rejected:insufficient_margin", "unexpected committed event after rollback")
    fresh_admission = f.reject_without_effect("fresh-new-order-equality", "insufficient_margin",
        f.exchange.submit_order, "A", "new-MM-equality", "BTC-PERP", D(-1), D(100))
    require(fresh_admission["error"]["message"] == "new exposure requires positive maintenance margin surplus",
            "fresh admission did not reach the strict MM guard")
    replay_order = f.replay_without_effect("known-accepted-order-ID", f.exchange.submit_order,
        "A", "eth-A", "ETH-PERP", D(1), D(10))
    replay_fill = f.replay_without_effect("known-accepted-fill-ID", f.exchange.apply_fill,
        "A", "eth-A", eth["buy_fill_id"], D(1), D(10))
    conflict = f.reject_without_effect("existing-fill-ID-conflict", "idempotency_conflict",
        f.exchange.apply_fill, "A", "eth-A", eth["buy_fill_id"], D("0.5"), D(10))
    f.step("cancel-unfilled-buyer", f.exchange.cancel_order, "B", "btc-B")
    result = f.finish(1, {"A": "11.04000009", "B": "999.996"}, ".008", "1011.04400009",
                      {("A", "ETH-PERP"): (D(1), D(10)), ("B", "ETH-PERP"): (D(-1), D(-10))})
    result["observations"] = {"direct_reject": direct, "matching_before": before, "matching_after": after,
        "actual_native_leg_profile": observed, "matching_rejection": rejected_match, "new_admission_reject": fresh_admission,
        "accepted_order_replay": replay_order, "accepted_fill_replay": replay_fill, "existing_fill_conflict": conflict}
    return result


def im_equality_case(directory, checkpoint):
    f = Fixture(directory, "IM-equality-lower-MM", symbols={"BTC-PERP": "100"}, mm="0.05", scale=8, checkpoint=checkpoint)
    f.fund("A", "10.04"); f.fund("B", "1000")
    f.order("A", "buy-A", "BTC-PERP", "1", "100")
    f.order("B", "sell-B", "BTC-PERP", "-1", "100")
    require(f.match("valid-zero-IM-availability", "BTC-PERP", 1)["confirmed_trades"] == 1, "valid IM equality rejected")
    risk = f.exchange.risk("A")
    require((risk["equity"], risk["initial_margin"], risk["maintenance_margin"], risk["available_margin"])
            == ("10", "10", "5", "0"), "manual valid IM equality differs")
    f.order("A", "RO-A", "BTC-PERP", "-1", "100", reduce_only=True)
    f.order("B", "RO-B", "BTC-PERP", "1", "100", reduce_only=True)
    require(f.match("original-RO-close", "BTC-PERP", 1)["confirmed_trades"] == 1, "original reduce-only close blocked")
    result = f.finish(2, {"A": "9.96", "B": "999.92"}, ".16", "1010.04", {})
    result["valid_IM_equality_original_risk"] = risk
    return result


def partial_fee_case(directory, checkpoint):
    f = Fixture(directory, "USD2-cumulative-partial-fee", symbols={"BTC-PERP": "1"}, mm="0.05", scale=2, checkpoint=checkpoint)
    f.fund("A", ".11"); f.fund("B", "10")
    f.order("A", "sell-A", "BTC-PERP", "-1", "1")
    f.order("B", "buy-B1", "BTC-PERP", ".4", "1")
    f.order("B", "buy-B2", "BTC-PERP", ".6", "1")
    matched = f.match("two-distinct-real-partial-matches", "BTC-PERP", 2)
    require(matched["confirmed_trades"] == 2 and matched["attempts"] == 2, "two original resting orders did not yield two matches")
    with f.exchange.database.read_transaction() as connection:
        fills = [dict(row) for row in connection.execute("SELECT * FROM uta_fills ORDER BY rowid")]
    require([row["fee"] for row in fills if row["account_id"] == "A"] == ["0.01", "0"], "one order's cumulative fee charged twice")
    require([row["fee"] for row in fills if row["account_id"] == "B"] == ["0.01", "0.01"], "two distinct orders' fees were incorrectly netted")
    result = f.finish(2, {"A": ".1", "B": "9.98"}, ".03", "10.11",
        {("A", "BTC-PERP"): (D(-1), D(-1)), ("B", "BTC-PERP"): (D(1), D(1))})
    a = result["risks"]["A"]
    require((a["equity"], a["initial_margin"], a["maintenance_margin"], a["available_margin"])
            == ("0.1", "0.1", "0.05", "0"), "partial cumulative fee did not preserve valid IM equality")
    result["original_partial_matches"] = matched
    result["actual_fill_fee_rows"] = fills
    return result


def run_cases(business, checkpoint, save_report):
    results = []
    matching_attempts = automatic_cancels = explicit_cancels = known_replays = rejected_commands = 0
    top_level_invocations, unique_keys = {}, []
    for function in (rollback_case, im_equality_case, partial_fee_case):
        result = function(business, checkpoint)
        save_report(result["case"] + ".json", result)
        results.append({"case": result["case"], "actual_unique_matches": result["actual_unique_matches"],
            "actual_paired_fills": result["actual_paired_fills"], "strict": result["strict"],
            "independent": result["independent"]})
        for action in result["actions"]:
            value = action.get("result")
            if isinstance(value, dict) and "confirmed_trades" in value:
                matching_attempts += value["attempts"]
                automatic_cancels += len(value["cancelled_orders"])
            explicit_cancels += action["label"] == "cancel-unfilled-buyer"
            known_replays += action["label"] in ("known-accepted-order-ID", "known-accepted-fill-ID")
            rejected_commands += "expected_business_rejection" in action
        for name, count in result["top_level_step_invocations"].items():
            top_level_invocations[name] = top_level_invocations.get(name, 0) + count
        unique_keys += [[result["case"], row["trade_id"]] for row in result["final"]["tables"]["uta_matches"]]
    require(sum(value["actual_unique_matches"] for value in results) == 5, "wrong planned committed match count")
    require((matching_attempts, automatic_cancels, explicit_cancels, known_replays, rejected_commands) == (6, 1, 1, 2, 3),
            "actual attempt/cancel/replay/rejection counts differ")
    require(len({tuple(key) for key in unique_keys}) == 5, "duplicate authority-qualified match identity")
    return {"cases": results, "authorities": 3, "actual_matches": 5, "actual_paired_fills": 10,
        "actual_matching_attempts": matching_attempts, "actual_matching_rejection_attempts": matching_attempts - 5,
        "actual_expected_direct_command_rejections": rejected_commands,
        "actual_known_accepted_ID_replays": known_replays,
        "actual_native_matching_auto_cancels": automatic_cancels, "actual_explicit_cleanup_cancels": explicit_cancels,
        "actual_top_level_step_invocations": top_level_invocations, "actual_unique_match_keys": unique_keys,
        "scope": "three fresh synchronous native Cross matching authorities; no capacity/HA/managed-worker acceptance",
        "funding_API_status": "NOT_IMPLEMENTED_IN_THIS_RUNTIME; genuine market publication used, no fabricated funding",
        "full_audit_admission_eligibility_model": "OPEN; three actual FILL numeric replays only",
        "performance_accepted": False, "production_approved": False}
