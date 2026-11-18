"""Bounded offline decoder for five sealed synthetic funding SQLite main files.

No sqlite3 import, SQL engine, target import, process action or input write.
Only UTF-8 SQLite3 rowid-table leaf/interior pages and overflow records used by
the fixed scenario are supported. Index/freelist/WAL recovery and arbitrary
databases are deliberately outside this reader; unsupported layouts fail.
"""
from collections import defaultdict
from fractions import Fraction
from hashlib import sha256
import json
import re
import struct


MAX_BYTES = 4 * 1024 * 1024
MAX_ROWS = 4096


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value):
    return sha256(canonical(value).encode()).hexdigest()


def units(text):
    result = int(text)
    assert type(text) is str and str(result) == text
    return result


def fraction(text):
    return Fraction(text)


def cash_units(text):
    result = fraction(text) * 100
    assert result.denominator == 1
    return result.numerator


def business_key(kind, *parts):
    return kind + ":" + digest(parts)


def funding_key(kind, *parts):
    return "funding-local:" + kind + ":" + digest(parts)


class MainFile:
    def __init__(self, raw):
        assert type(raw) is bytes and 100 <= len(raw) <= MAX_BYTES
        assert raw[:16] == b"SQLite format 3\x00"
        self.raw = raw
        size = int.from_bytes(raw[16:18], "big")
        self.page_size = 65536 if size == 1 else size
        assert self.page_size >= 512 and self.page_size & (self.page_size - 1) == 0
        assert raw[20] == 0 and int.from_bytes(raw[56:60], "big") == 1
        assert raw[18] == raw[19] == 2  # Fixed native WAL-format main files.
        assert len(raw) % self.page_size == 0
        self.pages = len(raw) // self.page_size
        assert self.pages == int.from_bytes(raw[28:32], "big")
        assert raw[24:28] == raw[92:96]  # Header size belongs to current version.
        self.touched = set()
        self.schema = {}
        for rowid, values in self.table_records(1):
            assert len(values) == 5
            kind, name, table, root, sql = values
            if kind == "table":
                assert name not in self.schema
                self.schema[name] = (root, sql)

    def page(self, number):
        assert type(number) is int and 1 <= number <= self.pages
        self.touched.add(number)
        offset = (number - 1) * self.page_size
        return self.raw[offset:offset + self.page_size]

    @staticmethod
    def varint(raw, offset, end):
        value = 0
        for index in range(9):
            assert offset < end
            byte = raw[offset]
            offset += 1
            if index == 8:
                return (value << 8) | byte, offset
            value = (value << 7) | (byte & 127)
            if byte < 128:
                return value, offset
        raise AssertionError("invalid varint")

    def payload(self, page, offset, length):
        assert 0 <= length <= MAX_BYTES
        usable = self.page_size
        minimum, maximum = ((usable - 12) * 32 // 255) - 23, usable - 35
        local = length
        if length > maximum:
            candidate = minimum + (length - minimum) % (usable - 4)
            local = candidate if candidate <= maximum else minimum
        assert offset + local <= usable
        result = page[offset:offset + local]
        if local == length:
            return result
        assert offset + local + 4 <= usable
        next_page = int.from_bytes(page[offset + local:offset + local + 4], "big")
        seen = set()
        while len(result) < length:
            assert next_page not in seen and len(seen) < self.pages
            seen.add(next_page)
            overflow = self.page(next_page)
            next_page = int.from_bytes(overflow[:4], "big")
            result += overflow[4:4 + min(length - len(result), usable - 4)]
        assert next_page == 0 and len(result) == length
        return result

    @classmethod
    def record(cls, payload):
        header_end, offset = cls.varint(payload, 0, len(payload))
        assert offset <= header_end <= len(payload)
        serials = []
        while offset < header_end:
            serial, offset = cls.varint(payload, offset, header_end)
            serials.append(serial)
        offset, values = header_end, []
        sizes = {0: 0, 1: 1, 2: 2, 3: 3, 4: 4, 5: 6, 6: 8, 7: 8, 8: 0, 9: 0}
        for serial in serials:
            assert serial not in (10, 11)
            size = sizes[serial] if serial < 12 else (serial - 12) // 2
            assert offset + size <= len(payload)
            value = payload[offset:offset + size]
            offset += size
            if serial == 0:
                values.append(None)
            elif serial in (8, 9):
                values.append(serial - 8)
            elif 1 <= serial <= 6:
                values.append(int.from_bytes(value, "big", signed=True))
            elif serial == 7:
                values.append(struct.unpack(">d", value)[0])
            elif serial % 2:
                values.append(value.decode("utf-8", "strict"))
            else:
                values.append(value)
        assert offset == len(payload)
        return values

    def table_records(self, root):
        result, seen = [], set()

        def visit(number):
            assert number not in seen and len(seen) < self.pages
            seen.add(number)
            page = self.page(number)
            start = 100 if number == 1 else 0
            kind = page[start]
            assert kind in (5, 13), "only rowid tables are supported"
            count = int.from_bytes(page[start + 3:start + 5], "big")
            pointer_start = start + (12 if kind == 5 else 8)
            assert pointer_start + 2 * count <= self.page_size
            for index in range(count):
                pointer = int.from_bytes(page[pointer_start + index * 2:pointer_start + index * 2 + 2], "big")
                assert pointer_start + 2 * count <= pointer < self.page_size
                if kind == 5:
                    visit(int.from_bytes(page[pointer:pointer + 4], "big"))
                else:
                    length, offset = self.varint(page, pointer, self.page_size)
                    rowid, offset = self.varint(page, offset, self.page_size)
                    values = self.record(self.payload(page, offset, length))
                    result.append((rowid, values))
                    assert len(result) <= MAX_ROWS
            if kind == 5:
                visit(int.from_bytes(page[start + 8:start + 12], "big"))

        visit(root)
        assert len({rowid for rowid, _ in result}) == len(result)
        return sorted(result)

    @staticmethod
    def columns(sql):
        assert type(sql) is str and "WITHOUT ROWID" not in sql.upper()
        body = sql[sql.index("(") + 1:sql.rindex(")")]
        pieces, start, depth, quote = [], 0, 0, None
        for index, char in enumerate(body):
            if quote:
                if char == quote:
                    quote = None
            elif char in "\"'`":
                quote = char
            elif char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
            elif char == "," and depth == 0:
                pieces.append(body[start:index].strip())
                start = index + 1
        pieces.append(body[start:].strip())
        columns, aliases = [], set()
        for piece in pieces:
            if re.match(r"^(?:CONSTRAINT|PRIMARY|UNIQUE|CHECK|FOREIGN)\b", piece, re.I):
                continue
            name = piece.split()[0].strip('"`[]')
            if name.upper() in {"CONSTRAINT", "PRIMARY", "UNIQUE", "CHECK", "FOREIGN"}:
                continue
            assert re.fullmatch(r"[A-Za-z_][A-Za-z_0-9]*", name)
            columns.append(name)
            if re.match(r"^\w+\s+INTEGER\s+PRIMARY\s+KEY\b", piece, re.I):
                aliases.add(name)
        assert len(set(columns)) == len(columns)
        return columns, aliases

    def rows(self, table):
        root, sql = self.schema[table]
        columns, aliases = self.columns(sql)
        rows = []
        for rowid, values in self.table_records(root):
            assert len(values) == len(columns), "sparse ALTER/default rows unsupported"
            row = dict(zip(columns, values))
            for name in aliases:
                assert row[name] is None
                row[name] = rowid
            rows.append(row)
        return rows


def verify_case(raw, expected, label, oracle):
    db = MainFile(raw)
    tables = {name: db.rows(name) for name in (
        "ledger_assets", "ledger_events", "ledger_postings", "ledger_balances",
        "uta_accounts", "uta_positions", "uta_liabilities", "uta_deposits",
        "uta_orders", "uta_fills", "uta_matches", "uta_events",
        "funding_local_config", "funding_local_periods", "uta_liquidation_accounts")}
    assert tables["ledger_assets"] == [{"asset": "USD", "scale": 2}]
    events = {row["sequence"]: row for row in tables["ledger_events"]}
    assert list(events) == list(range(1, expected["ledger_events"] + 1))
    assert len({row["event_id"] for row in events.values()}) == len(events)
    postings = defaultdict(list)
    for row in tables["ledger_postings"]:
        assert row["sequence"] in events
        postings[row["sequence"]].append(row)
    balances, event_postings, previous = {}, {}, "0" * 64
    for sequence, event in events.items():
        rows = sorted(postings[sequence], key=lambda row: row["ordinal"])
        assert [row["ordinal"] for row in rows] == list(range(len(rows)))
        canonical_postings = [[row["account"], row["asset"], units(row["units"])] for row in rows]
        assert len(rows) >= 2 and canonical_postings == sorted(canonical_postings)
        per_asset = defaultdict(int)
        for account, asset, amount in canonical_postings:
            assert amount and asset == "USD"
            per_asset[asset] += amount
            balances[(account, asset)] = balances.get((account, asset), 0) + amount
        assert all(total == 0 for total in per_asset.values())
        fingerprint = sha256(json.dumps(canonical_postings, ensure_ascii=True, separators=(",", ":")).encode()).hexdigest()
        assert event["sealed"] == 1 and event["fingerprint"] == fingerprint
        assert event["previous_hash"] == previous
        expected_hash = sha256(json.dumps([sequence, event["event_id"], previous, fingerprint], ensure_ascii=True, separators=(",", ":")).encode()).hexdigest()
        assert event["event_hash"] == expected_hash
        previous = expected_hash
        event_postings[event["event_id"]] = (sequence, canonical_postings)
    assert {(row["account"], row["asset"]): units(row["units"]) for row in tables["ledger_balances"]} == balances
    manual = {"customer:" + account: cash_units(value) for account, value in expected["customers"].items()}
    manual.update({account: cash_units(value) for account, value in expected["system"].items()})
    assert {key: value for key, value in balances.items() if value} == {(account, "USD"): value for account, value in manual.items() if value}
    assert all(balances.get((account, "USD"), 0) == 0 for account in (
        "system:perpetual-funding-clearing", "system:funding-rounding-reserve", "system:realized-pnl"))
    assert {row["account_id"] for row in tables["uta_accounts"]} == set(expected["customers"])
    positions = {(row["account_id"], row["symbol"]): (fraction(row["quantity"]), fraction(row["cost_basis"])) for row in tables["uta_positions"]}
    assert len(positions) == len(tables["uta_positions"])
    assert positions == {(account, "BTC-PERP"): tuple(map(fraction, pair)) for account, pair in expected["positions"].items()}
    assert tables["uta_liabilities"] == []
    for deposit in tables["uta_deposits"]:
        amount = cash_units(deposit["amount"])
        assert deposit["asset"] == "USD" and amount > 0
        event_id = business_key("deposit", deposit["account_id"], deposit["event_id"])
        assert event_postings[event_id][1] == sorted([
            ["customer:" + deposit["account_id"], "USD", amount], ["system:custody", "USD", -amount]])
    orders = {(row["account_id"], row["order_id"]): row for row in tables["uta_orders"]}
    fills = {(row["account_id"], row["fill_id"]): row for row in tables["uta_fills"]}
    assert len(fills) == expected["paired_fills"]
    matches = tables["uta_matches"]
    assert len(matches) == expected["matches"] and len({row["trade_id"] for row in matches}) == len(matches)
    assert [(fraction(row["quantity"]), fraction(row["price"])) for row in matches] == [(Fraction(1), Fraction(100))] + ([(Fraction(3, 5), Fraction(100))] if label == "capital" else [])
    matched_fills = set()
    fill_by_order = defaultdict(Fraction)
    for match in matches:
        identity = [match["symbol"], match["buy_account_id"], match["buy_order_id"],
                    match["sell_account_id"], match["sell_order_id"], match["buy_filled_before"],
                    match["sell_filled_before"], match["quantity"], match["price"]]
        trade_id = "match:" + sha256(json.dumps(identity, separators=(",", ":"), ensure_ascii=True).encode()).hexdigest()
        assert match["trade_id"] == trade_id
        for side, sign, suffix in (("buy", 1, ":b"), ("sell", -1, ":s")):
            account, fill_id, order_id = (match[side + field] for field in ("_account_id", "_fill_id", "_order_id"))
            assert fill_id == trade_id + suffix and (account, fill_id) not in matched_fills
            matched_fills.add((account, fill_id))
            fill, order = fills[(account, fill_id)], orders[(account, order_id)]
            quantity, price = fraction(match["quantity"]), fraction(match["price"])
            assert fill["order_id"] == order_id and order["symbol"] == match["symbol"] == "BTC-PERP"
            assert fraction(fill["quantity"]) == sign * quantity and fraction(fill["price"]) == price
            assert fraction(fill["realized_pnl"]) == 0
            exact_fee_units = quantity * price * Fraction(4, 10000) * 100
            fee_units = -((-exact_fee_units.numerator) // exact_fee_units.denominator)
            assert cash_units(fill["fee"]) == fee_units
            assert event_postings[business_key("fill", account, fill_id)][1] == sorted([
                ["customer:" + account, "USD", -fee_units], ["system:fees", "USD", fee_units]])
            fill_by_order[(account, order_id)] += sign * quantity
    assert matched_fills == set(fills)
    assert all(fraction(row["filled_quantity"]) == fill_by_order.get(key, Fraction()) for key, row in orders.items())
    config = json.loads(tables["funding_local_config"][0]["payload"])
    assert config["capital_account_id"] == "funding-treasury" and config["usd_scale"] == 2
    artifact = config["artifact"]
    assert artifact["funding_loaded_functions"] and artifact["funding_loaded_constants"]
    assert any(key.startswith("uta.perpetual_funding.") for key in artifact["funding_loaded_functions"])
    assert any(key.startswith("uta.funding_local.") for key in artifact["funding_loaded_functions"])
    periods = tables["funding_local_periods"]
    assert len(periods) == expected["periods"]
    expected_funding = {}
    for row in periods:
        receipt = json.loads(row["receipt"])
        assert canonical(receipt) == row["receipt"] and sha256(row["receipt"].encode()).hexdigest() == row["receipt_sha256"]
        request = json.loads(row["request"])
        assert canonical(request) == row["request"]
        assert row["command_id"] == receipt["command_id"] == expected["command"]
        assert row["symbol"] == receipt["symbol"] == "BTC-PERP" and row["period_end"] == receipt["period_end"]
        assert receipt["artifact_digest"] == digest(artifact) and receipt["policy"] == config["policy"] == request["policy"]
        assert request["command_id"] == row["command_id"] and request["period_end"] == row["period_end"] and request["symbol"] == row["symbol"]
        plan = receipt["plan"]
        assert plan["settlement_asset"] == "USD" and plan["usd_scale"] == 2
        assert fraction(plan["rate"]) == fraction(expected["rate"]) == fraction(request["rate"])
        assert fraction(plan["mark"]) == fraction(expected["mark"])
        assert receipt["market_snapshot_id"] == request["market_snapshot_id"] == "sha256:" + sha256(receipt["market_payload"].encode()).hexdigest()
        frozen = {item["account_id"]: item for item in receipt["freeze_positions"]}
        assert len(frozen) == len(receipt["freeze_positions"]) == len(plan["legs"])
        assert sum((fraction(item["quantity"]) for item in frozen.values()), Fraction()) == 0
        total = 0
        for leg in plan["legs"]:
            account = leg["account_id"]
            exact = -fraction(leg["quantity"]) * fraction(plan["mark"]) * fraction(plan["rate"])
            scaled = exact * 100
            amount = abs(scaled.numerator) // scaled.denominator * (-1 if scaled < 0 else 1)
            assert leg["cash_units"] == expected["funding_cash_units"][account] == str(amount)
            assert cash_units(leg["cash"]) == amount
            assert Fraction(int(leg["exact_cash"]["numerator"]), int(leg["exact_cash"]["denominator"])) == exact
            assert Fraction(int(leg["waived_exact_minus_actual"]["numerator"]), int(leg["waived_exact_minus_actual"]["denominator"])) == exact - Fraction(amount, 100)
            assert fraction(leg["quantity"]) == fraction(frozen[account]["quantity"])
            total += amount
            if amount:
                event_id = funding_key("leg", row["symbol"], row["period_end"], account)
                expected_funding[event_id] = sorted([["customer:" + account, "USD", amount], ["system:perpetual-funding-clearing", "USD", -amount]])
        assert int(plan["clearing_units"]) == -total
        if total:
            expected_funding[funding_key("variance", row["symbol"], row["period_end"])] = sorted([
                ["system:funding-rounding-reserve", "USD", -total], ["system:perpetual-funding-clearing", "USD", total]])
        topup = receipt["capital_transfer"]
        if label == "capital":
            assert topup["source_account_id"] == "funding-treasury"
            assert topup["deposit_reference"] == row["capital_deposit_reference"] == expected["capital_reference"]
            assert topup["units"] == "1" and cash_units(topup["amount"]) == 1
            assert any(item["account_id"] == "funding-treasury" and item["event_id"] == topup["deposit_reference"] and cash_units(item["amount"]) == 100 for item in tables["uta_deposits"])
            expected_funding[funding_key("capital", row["symbol"], row["period_end"])] = sorted([
                ["customer:funding-treasury", "USD", -1], ["system:funding-rounding-reserve", "USD", 1]])
        else:
            assert topup is None and row["capital_deposit_reference"] is None
        assert cash_units(receipt["rounding_reserve_before"]) == cash_units(receipt["rounding_reserve_after"]) == 0
        assert {item["event_id"] for item in receipt["journals"]} == set(expected_funding)
        for item in receipt["journals"]:
            assert event_postings[item["event_id"]] == (item["sequence"], expected_funding[item["event_id"]])
        if label == "distress":
            risk, action = receipt["risk_after"]["a"], receipt["risk_actions"]["a"]
            assert [fraction(risk[key]) for key in ("cash_deficit_value", "principal_value", "equity", "maintenance_margin")] == [Fraction(1), Fraction(0), Fraction(-1), Fraction(1, 2)]
            assert (action["state"], action["cycle"], action["revision"]) == ("LIQUIDATING", 1, 1)
            old = orders[("a", "synthetic-pending-ro")]
            assert old["status"] == "CANCELLED" and old["reduce_only"] == 1 and fraction(old["quantity"]) == Fraction(-1, 10) and fraction(old["filled_quantity"]) == 0
            live = [item for item in orders.values() if item["account_id"] == "a" and item["status"] in ("OPEN", "PARTIALLY_FILLED")]
            assert len(live) == 1 and live[0]["reduce_only"] == 1 and live[0]["status"] == "OPEN"
            assert live[0]["order_id"].startswith("liq:1:1:") and fraction(live[0]["quantity"]) == -1 and fraction(live[0]["limit_price"]) == 100 and fraction(live[0]["filled_quantity"]) == 0
            assert {item["order_id"] for item in action["cancelled_orders"]} == {old["order_id"]}
            assert [item["order_id"] for item in action["created_orders"]] == [live[0]["order_id"]]
            state = next(item for item in tables["uta_liquidation_accounts"] if item["account_id"] == "a")
            assert (state["state"], state["cycle"], state["revision"]) == ("LIQUIDATING", 1, 1)
    actual_funding = {name for name in event_postings if name.startswith("funding-local:")}
    if label == "rollback":
        assert len(actual_funding) == 1 and not expected_funding
        assert event_postings[next(iter(actual_funding))][1] == sorted([
            ["system:test-source", "USD", -100], ["system:test-sink", "USD", 100]])
    else:
        assert actual_funding == set(expected_funding)
    return {
        "label": label, "main_pages": db.pages, "decoded_pages_touched": len(db.touched),
        "independent_ledger_hash_chain_and_postings_balanced": True,
        "independent_full_materialized_balances_and_composite_positions_equal": True,
        "deposit_original_sealed_double_entries_checked": True,
        "matching_fill_fee_PnL_and_ledger_links_checked": True,
        "funding_receipt_rational_cash_and_capital_postings_checked": True,
        "expected_orphan_count": 1 if label == "rollback" else 0,
        "committed_periods": len(periods), "ledger_events": len(events),
        "matches": len(matches), "paired_fills": len(fills),
        "qualified_trade_ids": [(label, row["trade_id"]) for row in matches],
        "raw_trade_ids": [row["trade_id"] for row in matches],
        "raw_period_keys": [(row["symbol"], row["period_end"]) for row in periods],
        "fee_units": balances[("system:fees", "USD")],
        "custody_units": balances[("system:custody", "USD")],
    }
