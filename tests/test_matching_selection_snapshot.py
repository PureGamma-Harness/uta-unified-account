"""Selected real selector/guard AST against memory rows; no UTA import or SQL.

This independently sorts every current book for the expected priority. It does
not validate settlement, SQLite locking, financial arithmetic or performance.
"""
import ast
from copy import deepcopy
from contextlib import contextmanager
from datetime import timedelta
from decimal import Decimal, localcontext
from fractions import Fraction
from itertools import permutations
from pathlib import Path
import random
from types import CodeType, FunctionType, MethodType
import unittest


ROOT = Path(__file__).resolve().parents[1]


class Error(ValueError):
    def __init__(self, code, message, status=400):
        super().__init__(message)
        self.code, self.status = code, status


def never_call(*args, **kwargs):
    raise AssertionError("native effect or clock callback must not execute")


@contextmanager
def memory_transaction(exchange):
    yield exchange._memory


def memory_market(exchange, connection):
    exchange._market_reads += 1
    raise Error(exchange._market_error, "synthetic trusted-market failure", 503)


def load_selected():
    tree = ast.parse((ROOT / "uta/matching.py").read_text())
    service = ast.parse((ROOT / "uta/service.py").read_text())
    service_class = next(node for node in service.body if isinstance(node, ast.ClassDef)
                         and node.name == "ExchangeService")
    constructor = next(node for node in service_class.body if isinstance(node, ast.FunctionDef)
                       and node.name == "__init__")
    future = ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0)
    ctor_namespace = {"timedelta": timedelta, "Decimal": Decimal}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[future, constructor], type_ignores=[])),
                 "selected-service-constructor-declaration", "exec"), ctor_namespace)
    native_classes = {name: type(name, (), {}) for name in
                      ("ExchangeService", "Database", "DurableLedger", "DecisionAudit")}
    native_classes["ExchangeService"].__init__ = ctor_namespace["__init__"]
    native_classes["ExchangeService"]._transaction = memory_transaction
    native_classes["ExchangeService"]._market = memory_market
    selected, matcher_init = [], None
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            name = node.targets[0].id
            if name in {"_LIVE", "_TRANSIENT", "_CANCEL_REJECTIONS", "_BOOK_QUERY", "_BOOK_POINT_QUERY", "_BOOK_FIXED_FIELDS", "_BOOK_CLOCK_CODES"}:
                selected.append(node)
            elif name in {"_BOOK_SERVICE_BINDINGS", "_BOOK_DATABASE_BINDINGS", "_BOOK_LEDGER_BINDINGS", "_BOOK_AUDIT_BINDINGS"}:
                cls = native_classes[node.value.args[0].id]
                for method in ast.literal_eval(node.value.args[1]):
                    static = method == "market_ref"
                    if method not in vars(cls):
                        setattr(cls, method, staticmethod(never_call) if static else never_call)
                selected.append(node)
        elif isinstance(node, ast.FunctionDef) and node.name in {
                "_native_bindings", "_require_native_bindings", "_require_snapshot_native"}:
            selected.append(node)
        elif isinstance(node, ast.ClassDef) and node.name == "_TransactionBook":
            selected.append(node)
        elif isinstance(node, ast.ClassDef) and node.name == "Matcher":
            matcher_init = [value for value in node.body if isinstance(value, ast.FunctionDef)
                            and value.name in {"__init__", "_remaining", "_identity", "_receipt", "match_once"}]
    selected.append(ast.ClassDef(name="Matcher", bases=[], keywords=[], body=matcher_init, decorator_list=[]))
    namespace = {"Decimal": Decimal, "Fraction": Fraction, "CodeType": CodeType,
                 "FunctionType": FunctionType, "MethodType": MethodType,
                 "ServiceError": Error, "_name": lambda value, field: None, **native_classes}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[future, *selected], type_ignores=[])),
                 "selected-matching-selector-and-guards", "exec"), namespace)
    return namespace


def row(sequence, quantity, price, account=None, filled="0", status="OPEN"):
    return {"book_sequence": sequence, "account_id": account or "account-" + str(sequence),
            "order_id": "order-" + str(sequence), "symbol": "BTC-PERP",
            "quantity": str(quantity), "limit_price": str(price), "reduce_only": 0,
            "created_at": "synthetic", "filled_quantity": str(filled), "status": status}


def decimal_text(value):
    """Independent exact finite-rational rendering for memory mutations only."""
    value = Fraction(value)
    denominator, twos, fives = value.denominator, 0, 0
    while denominator % 2 == 0:
        denominator //= 2
        twos += 1
    while denominator % 5 == 0:
        denominator //= 5
        fives += 1
    if denominator != 1:
        raise AssertionError("fixture supports finite decimal inputs only")
    scale = max(twos, fives)
    units = value.numerator * 2 ** (scale - twos) * 5 ** (scale - fives)
    sign = "-" if units < 0 else ""
    digits = str(abs(units)).rjust(scale + 1, "0")
    return sign + (digits[:-scale] + "." + digits[-scale:] if scale else digits)


class Cursor:
    def __init__(self, values):
        self.values = deepcopy(values)

    def fetchall(self):
        return self.values

    def fetchone(self):
        return self.values[0] if self.values else None


class MemoryConnection:
    def __init__(self, rows, namespace):
        self.rows = {(value["account_id"], value["order_id"]): deepcopy(value) for value in rows}
        self.namespace = namespace
        self.in_transaction = True
        self.full_reads = self.point_reads = self.rows_scanned = 0

    def execute(self, statement, arguments):
        if statement == self.namespace["_BOOK_QUERY"]:
            self.full_reads += 1
            self.rows_scanned += len(self.rows)
            return Cursor([value for value in self.rows.values() if value["symbol"] == arguments[0]
                           and value["status"] in ("OPEN", "PARTIALLY_FILLED")])
        if statement == self.namespace["_BOOK_POINT_QUERY"]:
            self.point_reads += 1
            value = self.rows.get(tuple(arguments))
            return Cursor([value] if value else [])
        raise AssertionError("unexpected SQL-shaped operation in memory fixture")


def reference(rows, side):
    candidates = []
    for value in rows.values():
        if value["status"] not in ("OPEN", "PARTIALLY_FILLED") or value["symbol"] != "BTC-PERP":
            continue
        remaining = Fraction(Decimal(value["quantity"])) - Fraction(Decimal(value["filled_quantity"]))
        if remaining and (remaining > 0) == (side > 0):
            candidates.append(value)
    # Exact Decimal comparison and copy_negate avoid both the production
    # Fraction priority key and the ambient Decimal context's unary minus.
    candidates.sort(key=lambda value: (Decimal(value["limit_price"]).copy_negate()
                    if side > 0 else Decimal(value["limit_price"]), value["book_sequence"]))
    return deepcopy(candidates[0]) if candidates else None


def advance(value, amount):
    filled = Fraction(Decimal(value["filled_quantity"])) + Fraction(amount)
    value["filled_quantity"] = decimal_text(filled)
    value["status"] = "FILLED" if filled == Fraction(Decimal(value["quantity"])) else "PARTIALLY_FILLED"


class SnapshotSelectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.namespace = load_selected()

    def book(self, rows):
        connection = MemoryConnection(rows, self.namespace)
        return connection, self.namespace["_TransactionBook"](connection, "BTC-PERP")

    def compare(self, connection, book):
        for side in (1, -1):
            self.assertEqual(book.best(side), reference(connection.rows, side))

    def native(self, audit=False):
        namespace = self.namespace
        exchange = object.__new__(namespace["ExchangeService"])
        exchange.database = namespace["Database"]()
        exchange.database._fence_clock_ns = None
        exchange.ledger = namespace["DurableLedger"]()
        exchange.ledger.database = exchange.database
        exchange.audit = namespace["DecisionAudit"]() if audit else None
        exchange.product_catalog = exchange.portfolio_rules = None
        if audit:
            exchange.audit.database = exchange.database
        self.assertEqual(len(namespace["_BOOK_CLOCK_CODES"]), 2)
        exchange.clock = FunctionType(namespace["_BOOK_CLOCK_CODES"][0],
                                      namespace["ExchangeService"].__init__.__globals__)
        return exchange

    def test_numeric_priority_and_fifo_all_twenty_four_input_permutations(self):
        values = [row(1, 1, "9"), row(2, 1, "1000000000"), row(3, 1, "1000000000.00000001"), row(4, -1, "99")]
        for values in permutations(values):
            with self.subTest(sequence=[value["book_sequence"] for value in values]), localcontext() as context:
                context.prec = 3
                connection, book = self.book(values)
                self.compare(connection, book)
                for target in (3, 2, 1):
                    current = next(value for value in connection.rows.values() if value["book_sequence"] == target)
                    current["status"] = "CANCELLED"
                    self.compare(connection, book)
        # Stable insertion order alone is insufficient: both sides arrive in
        # reverse rowid order at one exact price, so the time key is essential.
        connection, book = self.book([row(2, 1, 100), row(1, 1, 100),
                                      row(4, -1, 100), row(3, -1, 100)])
        self.compare(connection, book)
        self.assertEqual((book.best(1)["book_sequence"], book.best(-1)["book_sequence"]), (1, 3))
        connection.rows[("account-1", "order-1")]["status"] = "CANCELLED"
        connection.rows[("account-3", "order-3")]["status"] = "CANCELLED"
        self.compare(connection, book)

    def test_empty_one_sided_uncrossed_and_zero_remaining_books(self):
        for values in ([], [row(1, 1, 90)], [row(1, 1, 90), row(2, -1, 110)],
                       [row(1, 1, 100, filled="1"), row(2, -1, 100, filled="-1")]):
            connection, book = self.book(values)
            self.compare(connection, book)
        # Run the actual selected match_once pre-market branch with inert
        # native-component stand-ins: a stale/unavailable market reads no book.
        for code in ("market_unavailable", "trading_halted", "invalid_clock"):
            exchange = self.native()
            exchange._memory = MemoryConnection([row(1, 1, 100)], self.namespace)
            exchange._market_reads, exchange._market_error = 0, code
            matcher = self.namespace["Matcher"](exchange, initialize=False, book_selection="snapshot")
            result = matcher.match_once("BTC-PERP", 1)
            self.assertEqual(result["blocked"], [{"code": code}])
            self.assertEqual((exchange._market_reads, exchange._memory.full_reads, exchange._memory.point_reads), (1, 0, 0))

    def test_seeded_two_hundred_fifty_six_mutation_traces(self):
        for seed in range(256):
            rng = random.Random(seed)
            values = [row(index + 1, rng.choice((-3, -2, -1, 1, 2, 3)), rng.choice(("9", "99.99", "100", "100.01", "1000")),
                          account="account-" + str(rng.randrange(3))) for index in range(8)]
            connection, book = self.book(values)
            for step in range(12):
                self.compare(connection, book)
                current = rng.choice(list(connection.rows.values()))
                if current["status"] not in ("OPEN", "PARTIALLY_FILLED"):
                    continue
                if step % 3 == 0:
                    current["status"] = "CANCELLED"
                else:
                    remaining = Fraction(Decimal(current["quantity"])) - Fraction(Decimal(current["filled_quantity"]))
                    advance(current, remaining / (2 if step % 2 else 1))
            self.compare(connection, book)

    def test_cross_cancelled_reduce_only_heads_are_never_reused(self):
        for cancelled in ((1,), (2,), (1, 2), (1, 2, 3)):
            connection, book = self.book([row(1, 1, 102, "same"), row(2, 1, 101, "same"),
                                          row(3, -1, 99, "same"), row(4, -1, 100)])
            self.compare(connection, book)
            for value in connection.rows.values():
                if value["book_sequence"] in cancelled:
                    value["status"] = "CANCELLED"
            self.compare(connection, book)

    def test_second_leg_rollback_restores_first_leg_before_next_peek(self):
        for rejected_side in (1, -1):
            connection, book = self.book([row(1, 3, 101), row(2, -3, 99)])
            before = deepcopy(connection.rows)
            first = reference(connection.rows, 1)
            advance(connection.rows[(first["account_id"], first["order_id"])], 1)
            connection.rows = before  # Savepoint rollback occurs before any next peek.
            rejected = reference(connection.rows, rejected_side)
            connection.rows[(rejected["account_id"], rejected["order_id"])]["status"] = "CANCELLED"
            self.compare(connection, book)

    def test_self_trade_cancel_partial_fill_and_later_heads(self):
        connection, book = self.book([row(1, 3, 101, "same"), row(2, -2, 99, "same"),
                                      row(3, -4, 100, "other")])
        connection.rows[("same", "order-2")]["status"] = "CANCELLED"
        self.compare(connection, book)
        for amount in (1, 2):
            advance(connection.rows[("same", "order-1")], amount)
            advance(connection.rows[("other", "order-3")], -amount)
            self.compare(connection, book)

    def test_transaction_boundary_and_fresh_next_batch(self):
        connection, book = self.book([row(1, 1, 100)])
        connection.in_transaction = False
        with self.assertRaises(Error):
            book.best(1)
        connection.in_transaction = True
        connection.rows[("new", "new")] = dict(row(2, 1, 200, "new"), order_id="new")
        # New orders are expressly outside a live snapshot's native contract;
        # the next transaction constructs a fresh inventory and sees them.
        next_book = self.namespace["_TransactionBook"](connection, "BTC-PERP")
        self.compare(connection, next_book)

    def test_identity_priority_reversal_and_quantity_increase_fail_closed(self):
        changes = (("book_sequence", 9), ("account_id", "other"), ("order_id", "other"),
                   ("symbol", "OTHER"), ("quantity", "2"), ("limit_price", "101"),
                   ("reduce_only", 1), ("created_at", "changed"), ("filled_quantity", "-1"),
                   ("filled_quantity", "2"))
        for field, value in changes:
            connection, book = self.book([row(1, 1, 100)])
            connection.rows[("account-1", "order-1")][field] = value
            with self.subTest(field=field, value=value), self.assertRaises(Error) as caught:
                book.best(1)
            self.assertEqual(caught.exception.code, "matching_corruption")
        connection, book = self.book([row(1, 1, 100)])
        connection.rows.clear()
        with self.assertRaises(Error):
            book.best(1)
        connection, book = self.book([row(1, 1, 100)])
        connection.rows[("account-1", "order-1")]["filled_quantity"] = ".5"
        book.best(1)
        connection.rows[("account-1", "order-1")]["filled_quantity"] = "0"
        with self.assertRaises(Error):
            book.best(1)

    def test_native_guard_accepts_both_original_default_clock_declarations(self):
        for audit in (False, True):
            for code in self.namespace["_BOOK_CLOCK_CODES"]:
                exchange = self.native(audit=audit)
                exchange.clock = FunctionType(code, self.namespace["ExchangeService"].__init__.__globals__)
                self.namespace["_require_snapshot_native"](exchange)

    def test_native_guard_rejects_callbacks_overrides_and_unknown_components(self):
        for mutation in (lambda value: setattr(value, "clock", never_call),
                         lambda value: setattr(value, "_apply_fill", never_call),
                         lambda value: setattr(value.database, "_connect", never_call),
                         lambda value: setattr(value.database, "_fence_clock_ns", never_call),
                         lambda value: setattr(value, "product_catalog", object()),
                         lambda value: setattr(value, "portfolio_rules", object()),
                         lambda value: setattr(value.ledger, "post", never_call),
                         lambda value: setattr(value.ledger, "database", object()),
                         lambda value: setattr(value.audit, "record", never_call),
                         lambda value: setattr(value.audit, "database", object())):
            exchange = self.native(audit=True)
            mutation(exchange)
            with self.assertRaises(Error) as caught:
                self.namespace["_require_snapshot_native"](exchange)
            self.assertEqual(caught.exception.code, "matching_snapshot_unsupported")
        for component in ("exchange", "database", "ledger", "audit"):
            exchange = self.native(audit=True)
            value = exchange if component == "exchange" else getattr(exchange, component)
            replacement = object.__new__(type("Unknown", (type(value),), {}))
            replacement.__dict__.update(vars(value))
            if component == "exchange":
                exchange = replacement
            else:
                setattr(exchange, component, replacement)
            with self.assertRaises(Error):
                self.namespace["_require_snapshot_native"](exchange)

    def test_constructor_default_scan_compatibility_and_explicit_mode_validation(self):
        matcher = self.namespace["Matcher"]
        exchange = self.native()
        exchange.clock = never_call
        self.assertEqual(matcher(exchange, initialize=False)._book_selection, "scan")
        with self.assertRaises(Error):
            matcher(exchange, initialize=False, book_selection="snapshot")
        for mode in (None, True, 1, "", "unknown", type("Alias", (str,), {})("snapshot")):
            with self.subTest(mode_type=type(mode).__name__), self.assertRaises(ValueError):
                matcher(exchange, initialize=False, book_selection=mode)
        supported = self.native()
        self.assertEqual(matcher(supported, initialize=False, book_selection="snapshot")._book_selection, "snapshot")
        derived = type("DerivedMatcher", (matcher,), {})
        with self.assertRaises(Error):
            derived(supported, initialize=False, book_selection="snapshot")

    def test_component_operation_counts_do_not_claim_end_to_end_throughput(self):
        connection, book = self.book([row(index + 1, 1 if index < 64 else -1, 100) for index in range(128)])
        for _ in range(20):
            self.compare(connection, book)
            for side in (1, -1):
                current = reference(connection.rows, side)
                connection.rows[(current["account_id"], current["order_id"])]["status"] = "FILLED"
        self.assertEqual(connection.full_reads, 1)
        self.assertEqual(connection.rows_scanned, 128)
        self.assertEqual(connection.point_reads, 78)  # 40 current heads +38 discarded terminal heads.


if __name__ == "__main__":
    unittest.main(verbosity=2)
