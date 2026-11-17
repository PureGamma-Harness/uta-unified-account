"""Explicit, funded cross-account spot credit with gross debt accounting.

These are privileged accounting commands, not a public lending API. A trusted
operator must confirm external pool funding and supplied interest events. There
is no automatic borrowing, fabricated interest clock, isolated margin, or PM.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from fractions import Fraction
import json
import sqlite3

from .ledger import Ledger, LedgerError, Posting
from .service import ExchangeService, ServiceError, _json, _key, _name, _text
from .storage import StorageError


_POOL = "system:credit-pool"
_CAPITAL = "system:credit-capital"
_PRINCIPAL_RECEIVABLE = "system:credit-principal-receivable"
_INTEREST_RECEIVABLE = "system:credit-interest-receivable"
_INTEREST_CASH = "system:credit-interest-cash"


class CreditService:
    """One transaction spans cash, principal, interest, limits, and audit events.

    Borrowing is disabled until both the asset-wide and account/asset limits have
    been explicitly configured and the pool funded. Limits cannot be silently
    amended. Accrued interest is recognized even if it exceeds a credit limit;
    it then blocks further borrowing. Repayment consumes settled available cash,
    paying interest before principal, and is available during halts/price outages.
    """

    def __init__(self, exchange: ExchangeService, *, _startup=None):
        if not isinstance(exchange, ExchangeService):
            raise ServiceError("invalid_configuration", "exchange must be an ExchangeService")
        self.exchange = exchange
        self.database = exchange.database
        self.ledger = exchange.ledger
        self._codec = Ledger(exchange.scales)
        if _startup is not None:
            from .startup import _OwnedStartup
            if type(_startup) is not _OwnedStartup:
                raise ServiceError("invalid_configuration", "invalid internal startup context")
            _startup.require_ledger(exchange)
        if _startup is None:
            with exchange._transaction() as connection:
                self._schema(connection)
                if connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='uta_liabilities'").fetchone() is None:
                    raise ServiceError("credit_integration_missing", "exchange schema must include gross principal and interest liabilities", 503)
                self._verify(connection)
        else:
            # All fixed schemas were prepared before the ledger RO snapshot;
            # post-freeze construction executes verification only, never DDL.
            _startup.verify_credit(self)

    @staticmethod
    def principal_account(account_id: str) -> str:
        return "liability:principal:" + account_id

    @staticmethod
    def interest_account(account_id: str) -> str:
        return "liability:interest:" + account_id

    @staticmethod
    def _schema_statements() -> tuple[str, ...]:
        return (
            "CREATE TABLE IF NOT EXISTS credit_schema (singleton INTEGER PRIMARY KEY CHECK(singleton=1), version INTEGER NOT NULL)",
            "CREATE TABLE IF NOT EXISTS credit_asset_limits (asset TEXT PRIMARY KEY REFERENCES ledger_assets(asset), units TEXT NOT NULL)",
            """CREATE TABLE IF NOT EXISTS credit_account_limits (
                account_id TEXT NOT NULL REFERENCES uta_accounts(account_id),
                asset TEXT NOT NULL REFERENCES ledger_assets(asset), units TEXT NOT NULL,
                PRIMARY KEY(account_id,asset))""",
            """CREATE TABLE IF NOT EXISTS credit_commands (
                scope TEXT NOT NULL, command_id TEXT NOT NULL, kind TEXT NOT NULL,
                asset TEXT NOT NULL REFERENCES ledger_assets(asset), amount TEXT NOT NULL,
                source_reference TEXT, result TEXT NOT NULL,
                journal_event_id TEXT NOT NULL UNIQUE REFERENCES ledger_events(event_id),
                created_at TEXT NOT NULL, PRIMARY KEY(scope,command_id))""",
            "CREATE TRIGGER IF NOT EXISTS credit_commands_no_update BEFORE UPDATE ON credit_commands BEGIN SELECT RAISE(ABORT,'credit commands are immutable'); END",
            "CREATE TRIGGER IF NOT EXISTS credit_commands_no_delete BEFORE DELETE ON credit_commands BEGIN SELECT RAISE(ABORT,'credit commands are immutable'); END",
            "CREATE TRIGGER IF NOT EXISTS credit_asset_limits_no_update BEFORE UPDATE ON credit_asset_limits BEGIN SELECT RAISE(ABORT,'credit limits are immutable'); END",
            "CREATE TRIGGER IF NOT EXISTS credit_asset_limits_no_delete BEFORE DELETE ON credit_asset_limits BEGIN SELECT RAISE(ABORT,'credit limits are immutable'); END",
            "CREATE TRIGGER IF NOT EXISTS credit_account_limits_no_update BEFORE UPDATE ON credit_account_limits BEGIN SELECT RAISE(ABORT,'credit limits are immutable'); END",
            "CREATE TRIGGER IF NOT EXISTS credit_account_limits_no_delete BEFORE DELETE ON credit_account_limits BEGIN SELECT RAISE(ABORT,'credit limits are immutable'); END",
        )
    @staticmethod
    def _pool_index() -> str:
        return ("CREATE UNIQUE INDEX IF NOT EXISTS credit_pool_source_unique "
                "ON credit_commands(source_reference) WHERE kind='pool_funded'")

    @staticmethod
    def _schema(connection: sqlite3.Connection) -> None:
        for statement in CreditService._schema_statements():
            connection.execute(statement)
        row = connection.execute("SELECT version FROM credit_schema WHERE singleton=1").fetchone()
        if row is not None and row[0] not in (1, 2):
            raise ServiceError("credit_schema_version", "unsupported credit schema version", 503)
        try:
            connection.execute(CreditService._pool_index())
        except sqlite3.IntegrityError as exc:
            raise ServiceError("credit_corrupt", "duplicate historical pool funding references require reconciliation", 503) from exc
        if row is None:
            connection.execute("INSERT INTO credit_schema VALUES (1,2)")
        elif row[0] == 1:
            connection.execute("UPDATE credit_schema SET version=2 WHERE singleton=1")

    def _asset(self, asset: str) -> str:
        _name(asset, "asset")
        if asset not in self.exchange.scales:
            raise ServiceError("unknown_asset", "asset is not configured")
        return asset

    def _units(self, asset: str, amount: Decimal, *, positive: bool = True) -> int:
        try:
            result = self._codec._units(asset, amount)
        except LedgerError as exc:
            raise ServiceError("invalid_input", str(exc)) from exc
        if result < 0 or positive and result == 0:
            raise ServiceError("invalid_input", "amount must be positive" if positive else "amount must be nonnegative")
        return result

    def _stored(self, asset: str, amount: str) -> int:
        if not isinstance(amount, str) or len(amount) > 80:
            raise ServiceError("credit_corrupt", "invalid persisted debt amount", 503)
        try:
            return self._units(asset, Decimal(amount), positive=False)
        except (InvalidOperation, ServiceError) as exc:
            raise ServiceError("credit_corrupt", "invalid persisted debt amount", 503) from exc

    def _value(self, asset: str, units: int) -> Decimal:
        if abs(units) >= Ledger._LIMIT:
            raise ServiceError("credit_limit", "credit amount exceeds supported ledger range", 409)
        return self._codec._amount(asset, units)

    def _limit(self, value: str) -> int:
        try:
            result = self.ledger._stored_units(value)
        except LedgerError as exc:
            raise ServiceError("credit_corrupt", "invalid persisted credit limit", 503) from exc
        if result < 0:
            raise ServiceError("credit_corrupt", "invalid persisted credit limit", 503)
        return result

    def _debt(self, connection, account_id: str, asset: str) -> tuple[int, int]:
        row = connection.execute("SELECT principal,interest FROM uta_liabilities WHERE account_id=? AND asset=?",
                                 (account_id, asset)).fetchone()
        principal, interest = (self._stored(asset, row["principal"]), self._stored(asset, row["interest"])) if row else (0, 0)
        expected = (self.principal_account(account_id), self.interest_account(account_id))
        for account, amount in zip(expected, (principal, interest)):
            balance = self._codec._units(asset, self.ledger.balance(account, asset, connection=connection))
            if balance != -amount:
                raise ServiceError("credit_corrupt", "gross debt projection differs from its journal accounts", 503)
        return principal, interest

    def _write_debt(self, connection, account_id: str, asset: str, principal: int, interest: int) -> None:
        connection.execute("INSERT INTO uta_liabilities(account_id,asset,principal,interest) VALUES (?,?,?,?) "
                           "ON CONFLICT(account_id,asset) DO UPDATE SET principal=excluded.principal,interest=excluded.interest",
                           (account_id, asset, _text(self._value(asset, principal)), _text(self._value(asset, interest))))

    def _replay(self, connection, scope: str, command_id: str, kind: str, asset: str,
                amount: str, source_reference: str | None = None) -> dict | None:
        self._check_schema(connection)
        row = connection.execute("SELECT * FROM credit_commands WHERE scope=? AND command_id=?",
                                 (scope, command_id)).fetchone()
        if row is None:
            return None
        if (row["kind"], row["asset"], row["amount"], row["source_reference"]) != (kind, asset, amount, source_reference):
            raise ServiceError("idempotency_conflict", "credit command ID was reused with different content", 409)
        return self._read_result(row)

    def _read_result(self, row) -> dict:
        try:
            result = json.loads(row["result"])
        except (TypeError, json.JSONDecodeError) as exc:
            raise ServiceError("credit_corrupt", "invalid persisted credit command result", 503) from exc
        if (not isinstance(result, dict) or _json(result) != row["result"]
                or result.get("command_id") != row["command_id"] or result.get("asset") != row["asset"]
                or result.get("amount") != row["amount"] or result.get("journal_event_id") != row["journal_event_id"]
                or row["journal_event_id"] != _key("credit", row["scope"], row["command_id"])):
            raise ServiceError("credit_corrupt", "credit command result differs from its immutable identity", 503)
        return result

    def _record(self, connection, scope: str, command_id: str, kind: str, asset: str,
                amount: str, result: dict, *, source_reference: str | None = None) -> dict:
        connection.execute("INSERT INTO credit_commands VALUES (?,?,?,?,?,?,?,?,?)",
                           (scope, command_id, kind, asset, amount, source_reference, _json(result),
                            result["journal_event_id"], self.exchange._now().isoformat()))
        self.exchange._event(connection, "CREDIT_" + kind.upper(), result.get("account_id"), result)
        return result

    def configure_asset_limit(self, asset: str, limit: Decimal) -> dict:
        """Privileged, immutable aggregate gross-debt limit for one asset."""
        self._asset(asset)
        units = self._units(asset, limit, positive=False)
        result = {"asset": asset, "limit": _text(self._value(asset, units))}
        with self.exchange._transaction() as connection:
            self._check_schema(connection)
            previous = connection.execute("SELECT units FROM credit_asset_limits WHERE asset=?", (asset,)).fetchone()
            if previous is not None:
                if self._limit(previous["units"]) != units:
                    raise ServiceError("configuration_conflict", "asset credit limit is already fixed", 409)
                return result
            connection.execute("INSERT INTO credit_asset_limits VALUES (?,?)", (asset, str(units)))
            self.exchange._event(connection, "CREDIT_ASSET_LIMIT_CONFIGURED", None, result)
            return result

    def configure_limit(self, account_id: str, asset: str, limit: Decimal) -> dict:
        """Privileged, immutable gross-debt limit for one account and asset."""
        _name(account_id, "account_id")
        self._asset(asset)
        units = self._units(asset, limit, positive=False)
        result = {"account_id": account_id, "asset": asset, "limit": _text(self._value(asset, units))}
        with self.exchange._transaction() as connection:
            self._check_schema(connection)
            self.exchange._require_account(connection, account_id)
            previous = connection.execute("SELECT units FROM credit_account_limits WHERE account_id=? AND asset=?",
                                          (account_id, asset)).fetchone()
            if previous is not None:
                if self._limit(previous["units"]) != units:
                    raise ServiceError("configuration_conflict", "account credit limit is already fixed", 409)
                return result
            connection.execute("INSERT INTO credit_account_limits VALUES (?,?,?)", (account_id, asset, str(units)))
            self.exchange._event(connection, "CREDIT_ACCOUNT_LIMIT_CONFIGURED", account_id, result)
            return result

    def fund_pool(self, command_id: str, asset: str, amount: Decimal, *, source_reference: str) -> dict:
        """Record externally confirmed pool capital; never infer real funding."""
        _name(command_id, "command_id")
        _name(source_reference, "source_reference")
        self._asset(asset)
        units = self._units(asset, amount)
        value, scope = self._value(asset, units), "pool"
        amount_text = _text(value)
        with self.exchange._transaction() as connection:
            previous = self._replay(connection, scope, command_id, "pool_funded", asset, amount_text, source_reference)
            if previous is not None:
                return previous
            if connection.execute("SELECT 1 FROM credit_commands WHERE kind='pool_funded' AND source_reference=?",
                                  (source_reference,)).fetchone() is not None:
                raise ServiceError("duplicate_external_reference", "funding source business line was already credited", 409)
            event_id = _key("credit", scope, command_id)
            self.ledger.post(event_id, [Posting(_POOL, asset, value), Posting(_CAPITAL, asset, value.copy_negate())], connection=connection)
            result = {"command_id": command_id, "asset": asset, "amount": amount_text,
                      "source_reference": source_reference, "journal_event_id": event_id,
                      "pool_balance": _text(self.ledger.balance(_POOL, asset, connection=connection))}
            return self._record(connection, scope, command_id, "pool_funded", asset, amount_text, result,
                                source_reference=source_reference)

    def _prepare(self, account_id: str, command_id: str, asset: str, amount: Decimal) -> tuple[int, str, str]:
        _name(account_id, "account_id")
        _name(command_id, "command_id")
        self._asset(asset)
        units = self._units(asset, amount)
        return units, _text(self._value(asset, units)), "account:" + account_id

    def _result(self, account_id: str, command_id: str, asset: str, amount: str,
                principal: int, interest: int, version: int, event_id: str) -> dict:
        return {"account_id": account_id, "command_id": command_id, "asset": asset, "amount": amount,
                "principal": _text(self._value(asset, principal)), "interest": _text(self._value(asset, interest)),
                "total": _text(self._value(asset, principal + interest)), "account_version": version,
                "journal_event_id": event_id}

    def borrow(self, account_id: str, command_id: str, asset: str, amount: Decimal) -> dict:
        """Explicitly borrow funded cash after fresh, atomic gross-debt risk checks."""
        self._prepare(account_id, command_id, asset, amount)
        with self.exchange._transaction() as connection:
            return self._borrow(connection, account_id, command_id, asset, amount)

    def _borrow(self, connection, account_id: str, command_id: str, asset: str, amount: Decimal) -> dict:
        """Join an existing financial transaction; never commit or open one.

        This internal interface adds no managed borrowing or ingress capability.
        Its caller owns rollback if a later receipt or another action fails.
        """
        if connection is None:
            raise StorageError("borrowing requires an existing financial transaction")
        with self.database._using(connection):
            from .writer_fence import _assert_financial_joinable
            _assert_financial_joinable(self.database, connection)
            units, amount_text, scope = self._prepare(account_id, command_id, asset, amount)
            self.exchange._require_account(connection, account_id)
            previous = self._replay(connection, scope, command_id, "borrowed", asset, amount_text)
            if previous is not None:
                return previous
            # The shared exposure guard includes the global halt and any
            # durable liquidation/supervisor account freeze.
            self.exchange._require_exposure_allowed(connection, account_id)
            market = self.exchange._market(connection)
            if asset not in market.assets:
                raise ServiceError("market_incomplete", "borrowed asset has no trusted price", 503)
            rules = getattr(self.exchange, "portfolio_rules", None)
            if rules is not None:
                rule = rules.borrow_limits.get(asset)
                if rule is None:
                    raise ServiceError("credit_disabled", "asset is not enabled by the versioned borrow policy", 409)
                if (Fraction(self._value(asset, units)) / Fraction(rule.quantity_step)).denominator != 1:
                    raise ServiceError("invalid_input", "borrow amount violates the configured quantity step")
                before = self.exchange._risk(connection, account_id, market)
                quotes = before.get("borrowable")
                if not isinstance(quotes, dict) or asset not in quotes:
                    raise ServiceError("credit_policy_unavailable", "versioned risk did not provide a borrow quote", 503)
                if self._value(asset, units) > Decimal(quotes[asset]):
                    raise ServiceError("credit_limit", "borrow exceeds collateral LTV or the versioned debt policy", 409)
            principal, interest = self._debt(connection, account_id, asset)
            account_limit = connection.execute("SELECT units FROM credit_account_limits WHERE account_id=? AND asset=?",
                                               (account_id, asset)).fetchone()
            asset_limit = connection.execute("SELECT units FROM credit_asset_limits WHERE asset=?", (asset,)).fetchone()
            if account_limit is None or asset_limit is None:
                raise ServiceError("credit_disabled", "explicit account and asset credit limits are required", 409)
            if principal + interest + units > self._limit(account_limit["units"]):
                raise ServiceError("credit_limit", "account credit limit exceeded", 409)
            total = sum(self._stored(asset, row["principal"]) + self._stored(asset, row["interest"])
                        for row in connection.execute("SELECT principal,interest FROM uta_liabilities WHERE asset=?", (asset,)))
            if total + units > self._limit(asset_limit["units"]):
                raise ServiceError("credit_limit", "aggregate asset credit limit exceeded", 409)
            available = self._codec._units(asset, self.ledger.balance(_POOL, asset, connection=connection))
            if available < units:
                raise ServiceError("credit_pool_empty", "funded credit pool has insufficient liquidity", 409)
            value, event_id = self._value(asset, units), _key("credit", scope, command_id)
            self.ledger.post(event_id, [Posting(_POOL, asset, value.copy_negate()),
                Posting(self.exchange._customer(account_id), asset, value),
                Posting(self.principal_account(account_id), asset, value.copy_negate()),
                Posting(_PRINCIPAL_RECEIVABLE, asset, value)], connection=connection)
            principal += units
            self._write_debt(connection, account_id, asset, principal, interest)
            projected = self.exchange._risk(connection, account_id, market)
            if Decimal(projected["available_margin"]) < 0:
                raise ServiceError("insufficient_margin", "borrow would leave insufficient initial margin", 409)
            # Revalidate at the end of admission as well as after lock acquisition.
            self.exchange._market(connection)
            version = self.exchange._bump(connection, account_id)
            result = self._result(account_id, command_id, asset, amount_text, principal, interest, version, event_id)
            result["risk_evidence"] = {
                "market_version": market.version, "market_observed_at": market.observed_at.isoformat(),
                "borrowable_before": quotes[asset] if rules is not None else None,
                **{key: projected[key] for key in ("equity", "initial_margin", "maintenance_margin",
                                                  "open_order_margin", "available_margin", "rule_id",
                                                  "rule_version", "catalog_version") if key in projected},
            }
            return self._record(connection, scope, command_id, "borrowed", asset, amount_text, result)

    def accrue_interest(self, account_id: str, command_id: str, asset: str, amount: Decimal) -> dict:
        """Recognize a supplied interest event; no clock/rate or compounding is inferred."""
        units, amount_text, scope = self._prepare(account_id, command_id, asset, amount)
        with self.exchange._transaction() as connection:
            self.exchange._require_account(connection, account_id)
            previous = self._replay(connection, scope, command_id, "interest_accrued", asset, amount_text)
            if previous is not None:
                return previous
            principal, interest = self._debt(connection, account_id, asset)
            if not principal:
                raise ServiceError("no_principal", "interest event requires outstanding principal", 409)
            interest += units
            value, event_id = self._value(asset, units), _key("credit", scope, command_id)
            self.ledger.post(event_id, [Posting(self.interest_account(account_id), asset, value.copy_negate()),
                                       Posting(_INTEREST_RECEIVABLE, asset, value)], connection=connection)
            self._write_debt(connection, account_id, asset, principal, interest)
            version = self.exchange._bump(connection, account_id)
            result = self._result(account_id, command_id, asset, amount_text, principal, interest, version, event_id)
            return self._record(connection, scope, command_id, "interest_accrued", asset, amount_text, result)

    def repay(self, account_id: str, command_id: str, asset: str, amount: Decimal) -> dict:
        """Pay interest then principal using settled available cash of the same asset.

        With nonnegative cash and collateral factors in [0,1], an equal cash/debt
        reduction cannot lower equity or margin surplus. It therefore needs no
        current price and remains available during a trading halt.
        """
        self._prepare(account_id, command_id, asset, amount)
        with self.exchange._transaction() as connection:
            return self._repay(connection, account_id, command_id, asset, amount)

    def _repay(self, connection, account_id: str, command_id: str, asset: str, amount: Decimal) -> dict:
        """Join an owned financial transaction; preserve interest-first repayment.

        Durable dispatch stores this result with the postings in the same COMMIT.
        The public method validates before opening storage and uses this path too.
        """
        units, amount_text, scope = self._prepare(account_id, command_id, asset, amount)
        self.exchange._require_account(connection, account_id)
        previous = self._replay(connection, scope, command_id, "repaid", asset, amount_text)
        if previous is not None:
            return previous
        principal, interest = self._debt(connection, account_id, asset)
        if units > principal + interest:
            raise ServiceError("repayment_exceeds_debt", "repayment exceeds outstanding principal and interest", 409)
        available = self.exchange._available_asset(connection, account_id, asset)
        if self._codec._units(asset, available) < units:
            raise ServiceError("insufficient_cash", "settled available cash is insufficient for repayment", 409)
        paid_interest = min(units, interest)
        paid_principal = units - paid_interest
        value, event_id = self._value(asset, units), _key("credit", scope, command_id)
        postings = [Posting(self.exchange._customer(account_id), asset, value.copy_negate())]
        for paid, cash_account, debt_account, receivable in (
            (paid_interest, _INTEREST_CASH, self.interest_account(account_id), _INTEREST_RECEIVABLE),
            (paid_principal, _POOL, self.principal_account(account_id), _PRINCIPAL_RECEIVABLE)):
            if paid:
                part = self._value(asset, paid)
                postings.extend((Posting(cash_account, asset, part), Posting(debt_account, asset, part),
                                 Posting(receivable, asset, part.copy_negate())))
        self.ledger.post(event_id, postings, connection=connection)
        principal, interest = principal - paid_principal, interest - paid_interest
        self._write_debt(connection, account_id, asset, principal, interest)
        version = self.exchange._bump(connection, account_id)
        result = self._result(account_id, command_id, asset, amount_text, principal, interest, version, event_id)
        result.update({"principal_repaid": _text(self._value(asset, paid_principal)),
                       "interest_repaid": _text(self._value(asset, paid_interest))})
        return self._record(connection, scope, command_id, "repaid", asset, amount_text, result)

    @staticmethod
    def _check_schema(connection) -> None:
        version = connection.execute("SELECT version FROM credit_schema WHERE singleton=1").fetchone()
        if version is None or version[0] != 2:
            raise ServiceError("credit_schema_version", "unsupported credit schema version", 503)

    def _verify(self, connection) -> int:
        self._check_schema(connection)
        for row in connection.execute("SELECT DISTINCT asset FROM uta_liabilities"):
            if row["asset"] not in self.exchange.scales:
                raise ServiceError("credit_corrupt", "unknown liability asset", 503)
        count = 0
        for row in connection.execute("SELECT account_id FROM uta_accounts"):
            for asset in self.exchange.scales:
                principal, interest = self._debt(connection, row["account_id"], asset)
                count += int(bool(principal or interest))
        for row in connection.execute("SELECT units FROM credit_asset_limits UNION ALL SELECT units FROM credit_account_limits"):
            self._limit(row["units"])
        for row in connection.execute("SELECT * FROM credit_commands"):
            result = self._read_result(row)
            self._asset(row["asset"])
            if self._stored(row["asset"], row["amount"]) <= 0:
                raise ServiceError("credit_corrupt", "nonpositive credit command amount", 503)
            if row["scope"] == "pool":
                if (row["kind"] != "pool_funded" or not isinstance(row["source_reference"], str)
                        or not row["source_reference"] or result.get("source_reference") != row["source_reference"]):
                    raise ServiceError("credit_corrupt", "pool command lacks its funding source", 503)
            elif (not row["scope"].startswith("account:") or row["kind"] not in ("borrowed", "repaid", "interest_accrued")
                  or result.get("account_id") != row["scope"][8:] or row["source_reference"] is not None):
                raise ServiceError("credit_corrupt", "credit command scope is inconsistent", 503)
        for asset in self.exchange.scales:
            if self.ledger.balance(_POOL, asset, connection=connection) < 0:
                raise ServiceError("credit_corrupt", "credit pool has a negative cash balance", 503)
        return count

    def verify(self) -> dict:
        """Verify journal replay and each gross debt projection against its accounts."""
        with self.exchange._transaction() as connection:
            events = self.ledger.verify(connection=connection)
            return {"journal_events": events, "nonzero_liabilities": self._verify(connection)}
