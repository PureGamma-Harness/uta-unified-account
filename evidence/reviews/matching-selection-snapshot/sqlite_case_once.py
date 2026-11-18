"""Unexecuted four-case real SQLite paired functional probe; synthetic only.

No worker, clock substitution, model injection or method monkeypatch is used.
This file has no execution entry point without the separately scoped driver.
"""
from datetime import datetime, timezone
from decimal import Decimal
from hashlib import sha256
import json
from pathlib import Path

from uta.market import MarketSnapshot
from uta.matching import Matcher
from uta.models import AssetSpec, InstrumentSpec
from uta.reconciliation import reconcile_exchange
from uta.service import ExchangeService
from uta.storage import Database


CASES = ("fifo-stp-partial", "reduce-only-cross-cancel", "second-leg-freeze", "no-liquidity-halt")
MODES = ("scan", "snapshot")
TABLES = ("ledger_events", "ledger_postings", "ledger_balances", "uta_accounts", "uta_orders",
          "uta_positions", "uta_fills", "uta_matches", "uta_liabilities", "uta_deposits",
          "uta_liquidation_accounts", "uta_events", "uta_risk_decisions", "uta_market_history",
          "uta_code_artifacts", "uta_risk_policies")
ORDER_BY = {"ledger_events": "sequence", "ledger_postings": "sequence,ordinal", "ledger_balances": "account,asset",
            "uta_accounts": "account_id", "uta_orders": "rowid", "uta_positions": "account_id,symbol",
            "uta_fills": "account_id,fill_id", "uta_matches": "sequence", "uta_liabilities": "account_id,asset",
            "uta_deposits": "account_id,event_id", "uta_liquidation_accounts": "account_id", "uta_events": "sequence",
            "uta_risk_decisions": "decision_id", "uta_market_history": "snapshot_id",
            "uta_code_artifacts": "artifact_id", "uta_risk_policies": "policy_id"}
TIME_FIELDS = frozenset({"created_at", "observed_at", "recorded_at"})


def require(value, message):
    if not value:
        raise AssertionError(message)


def without_times(value):
    if isinstance(value, dict):
        return {key: without_times(item) for key, item in value.items() if key not in TIME_FIELDS}
    if isinstance(value, list):
        return [without_times(item) for item in value]
    return value


def only_new_quote(before, after, version):
    old, new = before["events"], after["events"]
    require(len(new) == len(old) + 1 and new[:-1] == old, "unexpected event during no-effect matching")
    require(new[-1] == {"sequence": old[-1]["sequence"] + 1, "event_type": "MARKET_PUBLISHED",
                        "account_id": None, "payload": {"version": version}}, "missing exact single new quote event")
    require({key: value for key, value in before.items() if key != "events"}
            == {key: value for key, value in after.items() if key != "events"}, "no-effect matching changed financial state")


class Fixture:
    def __init__(self, business, case, mode, checkpoint):
        self.case, self.mode, self.checkpoint = case, mode, checkpoint
        self.path = Path(business) / (case + "-" + mode + ".sqlite3")
        require(not self.path.exists(), "new authority path already exists")
        self.exchange = ExchangeService(Database(self.path), {"USD": 8}, decision_audit=True)
        self.matcher = Matcher(self.exchange, book_selection=mode)
        self.version = 0
        self.actions = []
        self.observations = []
        self.quote()
        self.step("unhalt", self.exchange.set_kill_switch, False)

    def step(self, label, function, *args, **kwargs):
        self.checkpoint(self.case, self.mode, label, "before")
        result = function(*args, **kwargs)
        if type(result) is ExchangeService:
            recorded = {"native_type": "uta.service.ExchangeService", "database": result.database.path}
        elif label.endswith("capture"):
            recorded = {"full_original_retained_separately": True,
                        "ledger_events_verified": result["ledger_events_verified"],
                        "table_rows": {name: len(rows) for name, rows in result["tables"].items()}}
        else:
            recorded = result
        self.actions.append({"label": label, "result": recorded})
        self.checkpoint(self.case, self.mode, label, "after")
        return result

    def quote(self):
        self.version += 1
        return self.step("publish-" + str(self.version), self.exchange.publish_market,
                         MarketSnapshot(self.version, datetime.now(timezone.utc),
                                        {"USD": AssetSpec(Decimal(1), Decimal(1))},
                                        {"BTC-PERP": InstrumentSpec(Decimal(100), Decimal(".1"), Decimal(".05"))}))

    def fund(self, account):
        self.step("create-" + account, self.exchange.create_account, account)
        self.step("fund-" + account, self.exchange.deposit, account, "funding", "USD", Decimal(10000))

    def order(self, account, identifier, quantity, price="100", reduce_only=False):
        self.quote()
        return self.step("order-" + identifier, self.exchange.submit_order, account, identifier,
                         "BTC-PERP", Decimal(quantity), Decimal(price), reduce_only=reduce_only)

    def match(self, label):
        self.quote()
        return self.step(label, self.matcher.match_once, "BTC-PERP", 100)

    def capture(self, include_risk=False):
        # Inspect the same native WAL/FULL financial transaction configuration;
        # a read-only connection's default synchronous setting is not evidence
        # of the writer's actual durability settings.
        with self.exchange.database.transaction() as connection:
            tables = {table: [dict(row) for row in connection.execute(
                "SELECT " + ("rowid AS book_sequence,*" if table == "uta_orders" else "*")
                + " FROM " + table + " ORDER BY " + ORDER_BY[table])] for table in TABLES}
            accounts = [self.exchange._account(connection, row["account_id"])
                        for row in connection.execute("SELECT account_id FROM uta_accounts ORDER BY account_id")]
            risks = None
            if include_risk:
                market = self.exchange._market(connection)  # Fresh native check; no TTL override.
                risks = {value["account_id"]: self.exchange._risk(connection, value["account_id"], market)
                         for value in accounts}
            journal_count = self.exchange.ledger.verify(connection=connection)
            settings = {"journal_mode": connection.execute("PRAGMA journal_mode").fetchone()[0],
                        "synchronous": connection.execute("PRAGMA synchronous").fetchone()[0]}
        require(settings == {"journal_mode": "wal", "synchronous": 2}, "WAL/FULL changed")
        projection = {name: tables[name] for name in (
            "ledger_events", "ledger_postings", "ledger_balances", "uta_accounts", "uta_positions",
            "uta_fills", "uta_liabilities", "uta_deposits", "uta_liquidation_accounts")}
        projection["accounts"] = accounts
        projection["orders"] = without_times(tables["uta_orders"])
        projection["matches"] = without_times(tables["uta_matches"])
        markets = {}
        for value in tables["uta_market_history"]:
            digest = sha256(value["payload"].encode()).hexdigest()
            require(value["snapshot_id"] == "market:" + digest and value["content_digest"] == digest,
                    "historical quote content identity differs")
            markets[value["snapshot_id"]] = json.loads(value["payload"])
        projection["events"] = []
        for value in tables["uta_events"]:
            payload = json.loads(value["payload"])
            if value["event_type"] == "MARKET_PUBLISHED":
                original = markets[payload["market_snapshot_id"]]
                require(original["version"] == payload["version"] and original["observed_at"] == payload["observed_at"],
                        "market event differs from its own original quote")
                # This reference is time-dependent, not a financial business ID.
                # Verify it against its own full raw record instead of comparing
                # different real timestamps in the two independent authorities.
                payload = {"version": payload["version"]}
            projection["events"].append({"sequence": value["sequence"], "event_type": value["event_type"],
                                         "account_id": value["account_id"], "payload": without_times(payload)})
        projection["decisions"] = []
        for value in tables["uta_risk_decisions"]:
            item = {key: field for key, field in value.items()
                    if key not in {"market_snapshot_id", "recorded_at", "input_payload", "summary_payload"}}
            item["inputs"] = without_times(json.loads(value["input_payload"]))
            item["summary"] = without_times(json.loads(value["summary_payload"]))
            require(value["market_snapshot_id"] in markets, "decision has no retained historical quote")
            projection["decisions"].append(item)
        return {"tables": tables, "accounts": accounts, "risks": risks,
                "economic_projection": projection, "ledger_events_verified": journal_count, "settings": settings}

    def finish(self, expected_matches):
        self.quote()
        before = self.step("pre-reopen-capture", self.capture)
        require(len(before["tables"]["uta_matches"]) == expected_matches, "unexpected actual matched count")
        require(len(before["tables"]["uta_fills"]) == 2 * expected_matches, "unpaired or missing fill")
        require(len({value["trade_id"] for value in before["tables"]["uta_matches"]}) == expected_matches,
                "duplicate actual trade ID inside authority")
        # Every transaction/connection from the operations above has closed.
        # Reconstruct native services on the existing file without touching data.
        self.exchange = self.step("reopen-native-service", ExchangeService, Database(self.path),
                                  {"USD": 8}, decision_audit=True)
        self.matcher = Matcher(self.exchange, initialize=False, book_selection=self.mode)
        after = self.step("post-reopen-capture", self.capture)
        require(before["economic_projection"] == after["economic_projection"], "reopen changed financial projection")
        strict = self.step("strict-matching-reconcile", self.matcher.verify, strict=True)
        require((strict["matches"], strict["paired_fills"], strict["unpaired_fills"])
                == (expected_matches, 2 * expected_matches, 0), "strict matching correspondence failed")
        independent = self.step("independent-cashflow-replay", reconcile_exchange, self.exchange)
        require(independent["status"] == "passed", "independent financial replay failed")
        fill_decisions = [value for value in after["tables"]["uta_risk_decisions"] if value["kind"] == "FILL_CONFIRMED"]
        valuation_replay = None
        if fill_decisions:
            valuation_replay = self.step("one-historical-valuation-replay", self.exchange.audit.replay,
                                         fill_decisions[0]["decision_id"])
            require(valuation_replay["matches"] is True, "historical valuation differs")
        self.quote()
        final = self.step("final-fresh-risk-capture", self.capture, include_risk=True)
        return {"case": self.case, "mode": self.mode, "path": str(self.path),
                "before_reopen": before, "after_reopen": after, "final": final,
                "strict": strict, "independent": independent, "valuation_replay": valuation_replay,
                "actions": self.actions, "intermediate_originals": self.observations,
                "actual_unique_matches_in_authority": expected_matches,
                "actual_fills_in_authority": 2 * expected_matches}


def fifo_stp_partial(fixture):
    for account in ("a", "b", "c", "d"):
        fixture.fund(account)
    fixture.order("a", "self-maker", "-1")
    fixture.order("a", "self-taker", "1")
    fixture.order("b", "first-buyer", "1")
    fixture.order("c", "second-buyer", "1")
    fixture.order("d", "partial-seller", "-3")
    matched = fixture.match("fifo-stp-partial-match")
    require(matched["confirmed_trades"] == 2 and matched["attempts"] == 3, "STP or partial count differs")
    require([(value["buy_order_id"], value["sell_order_id"], value["quantity"], value["price"])
             for value in matched["trades"]] == [("first-buyer", "self-maker", "1", "100"),
                                                 ("second-buyer", "partial-seller", "1", "100")], "FIFO/maker differs")
    require([value["order_id"] for value in matched["cancelled_orders"]] == ["self-taker"], "STP did not cancel newer order")
    for account in ("a", "b", "c", "d"):
        require(fixture.exchange.account(account)["balances"]["USD"] == "9999.96", "hand-computed fee differs")
    require(fixture.exchange.order("d", "partial-seller")["reserved_margin"] == "20.08", "partial reserve differs")
    before = fixture.capture()
    empty = fixture.match("no-more-liquidity")
    require(empty["confirmed_trades"] == 0, "one-sided book created a trade")
    after = fixture.capture()
    # Publishing the new genuine quote has one MARKET_PUBLISHED event; all
    # economics and other immutable records must remain identical.
    only_new_quote(before["economic_projection"], after["economic_projection"], fixture.version)
    fixture.observations.append({"kind": "no-liquidity", "before": before, "after": after})
    return fixture.finish(2)


def reduce_only_cross_cancel(fixture):
    for account in ("victim", "opening-counterparty", "closing-buyer"):
        fixture.fund(account)
    fixture.order("victim", "opening", "3")
    fixture.order("opening-counterparty", "opening-sell", "-3")
    require(fixture.match("open-real-position")["confirmed_trades"] == 1, "opening match missing")
    fixture.order("victim", "first-ro", "-1", "99", reduce_only=True)
    fixture.order("victim", "later-ro", "-2", "100", reduce_only=True)
    fixture.order("victim", "ordinary-close", "-1", "98")
    fixture.order("closing-buyer", "closing-liquidity", "2")
    matched = fixture.match("ordinary-close-invalidates-later-ro")
    require([value["sell_order_id"] for value in matched["trades"]] == ["ordinary-close", "first-ro"],
            "cross-cancelled RO entered matching")
    later = fixture.exchange.order("victim", "later-ro")
    require((later["status"], later["filled_quantity"]) == ("CANCELLED", "0"), "later RO was consumed or retained")
    account = fixture.exchange.account("victim")
    require(account["positions"]["BTC-PERP"]["quantity"] == "1", "reduction reversed or widened position")
    require(account["positions"]["BTC-PERP"]["cost_basis"] == "100", "remaining basis differs")
    require(account["balances"]["USD"] == "9996.8012", "hand-computed closing PnL/fee differs")
    return fixture.finish(3)


def second_leg_freeze(fixture):
    fixture.fund("buyer"); fixture.fund("seller")
    fixture.order("buyer", "buyer-order", "1")
    fixture.order("seller", "seller-order", "-1")
    # Explicit test-only risk-control fault: use the original native writer and
    # existing transition method, not a replacement _apply_fill or direct fill.
    with fixture.exchange._transaction() as connection:
        fixture.exchange._liquidation_state(connection, "seller", "LIQUIDATING", 1, 1,
                                            fixture.version, None, "NORMAL", reason="synthetic-seller-freeze")
    fixture.checkpoint(fixture.case, fixture.mode, "seller-native-freeze", "after")
    buyer_before = fixture.exchange.account("buyer")
    ledger_before = fixture.exchange.ledger.journal()
    before = fixture.capture()
    matched = fixture.match("second-leg-real-account-frozen")
    require(matched["confirmed_trades"] == 0, "frozen seller produced a confirmed trade")
    require([(value["code"], value["account_id"]) for value in matched["blocked"]]
            == [("account_frozen", "seller")], "did not exercise real second-leg rejection")
    require(fixture.exchange.account("buyer") == buyer_before, "first buyer leg was not rolled back")
    require(fixture.exchange.ledger.journal() == ledger_before, "first-leg ledger effects survived rollback")
    require(fixture.exchange.order("seller", "seller-order")["status"] == "CANCELLED", "rejected seller was not cancelled")
    require(fixture.exchange.order("buyer", "buyer-order")["status"] == "OPEN", "buyer reservation released incorrectly")
    fixture.observations.append({"kind": "second-leg-rollback", "before": before, "after": fixture.capture(),
                                 "buyer_before": buyer_before, "buyer_after": fixture.exchange.account("buyer")})
    return fixture.finish(0)


def no_liquidity_halt(fixture):
    fixture.fund("buyer"); fixture.fund("seller")
    fixture.order("buyer", "buy", "2", "99")
    require(fixture.match("one-sided-no-match")["confirmed_trades"] == 0, "no-liquidity created a trade")
    require(fixture.exchange.order("buyer", "buy")["reserved_margin"] == "20.0792", "unfilled reserve differs")
    fixture.order("seller", "sell", "-2", "99")
    fixture.step("halt", fixture.exchange.set_kill_switch, True)
    before = fixture.capture()
    halted = fixture.match("halted-crossing-book")
    require(halted["confirmed_trades"] == 0 and [value["code"] for value in halted["blocked"]] == ["trading_halted"],
            "halt was not enforced by original execution gate")
    after = fixture.capture()
    only_new_quote(before["economic_projection"], after["economic_projection"], fixture.version)
    fixture.observations.append({"kind": "halted-no-effect", "before": before, "after": after})
    fixture.step("resume", fixture.exchange.set_kill_switch, False)
    require(fixture.match("resume-real-match")["confirmed_trades"] == 1, "resumed book did not actually match")
    for account in ("buyer", "seller"):
        require(fixture.exchange.account(account)["balances"]["USD"] == "9999.9208", "hand fee on actual99 execution differs")
    return fixture.finish(1)


FUNCTIONS = (fifo_stp_partial, reduce_only_cross_cancel, second_leg_freeze, no_liquidity_halt)


def run_cases(business, checkpoint, save_report):
    outputs, paired = [], []
    for case, function in zip(CASES, FUNCTIONS):
        results = []
        for mode in MODES:
            checkpoint(case, mode, "case-start", "before")
            result = function(Fixture(business, case, mode, checkpoint))
            save_report(case + "-" + mode + ".json", result)
            results.append(result)
            outputs.append({"case": case, "mode": mode,
                            "matches": result["actual_unique_matches_in_authority"],
                            "fills": result["actual_fills_in_authority"],
                            "strict": result["strict"], "independent": result["independent"]})
            checkpoint(case, mode, "case-complete", "after")
        for field in ("economic_projection", "risks"):
            left, right = (without_times(value["final"][field]) for value in results)
            require(left == right, case + " paired exact financial projection differs: " + field)
        paired.append({"case": case, "exact_financial_projection_equal": True,
                       "exact_fresh_risk_equal_except_observed_at": True,
                       "full_original_reports_retained": True})
    return {"cases": outputs, "paired": paired, "authorities": 8,
            "matches_per_mode": 6, "paired_fills_per_mode": 12,
            "scope": "real single-process native SQLite functional matching only; no worker/managed fence/HA/capacity acceptance",
            "performance_accepted": False, "production_approved": False}
