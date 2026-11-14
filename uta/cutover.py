"""Atomic, explicitly limited transfer of a reconciled classic snapshot.

This is an operator-only, offline handover primitive. A fence reference is an
attestation to retained external evidence, not proof that an old writer stopped.
Real cutover requires a source adapter to establish that proof and the snapshot
plus incremental-event boundary. Unsupported in-flight state is rejected.
"""
from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from fractions import Fraction
from hashlib import sha256
import json

from .bridge import shadow_to_account
from .ledger import Posting
from .migration import MigrationError, ShadowAccount
from .models import RiskInputError
from .products import AccountMode, ProductKind
from .risk import calculate_risk
from .service import ExchangeService, ServiceError, _amount, _exact, _json, _name, _text


_SCHEMA = (
    """CREATE TABLE IF NOT EXISTS migration_schema (
        singleton INTEGER PRIMARY KEY CHECK(singleton=1), version INTEGER NOT NULL)""",
    """CREATE TABLE IF NOT EXISTS migration_imports (
        command_id TEXT PRIMARY KEY, source_account_id TEXT NOT NULL UNIQUE,
        request_digest TEXT NOT NULL, receipt TEXT NOT NULL, receipt_hash TEXT NOT NULL)""",
    """CREATE TABLE IF NOT EXISTS migration_reversals (
        reversal_id TEXT PRIMARY KEY, command_id TEXT NOT NULL UNIQUE
        REFERENCES migration_imports(command_id),
        receipt TEXT NOT NULL, receipt_hash TEXT NOT NULL)""",
    """CREATE TRIGGER IF NOT EXISTS migration_imports_no_update BEFORE UPDATE ON migration_imports
        BEGIN SELECT RAISE(ABORT,'migration receipts are immutable'); END""",
    """CREATE TRIGGER IF NOT EXISTS migration_imports_no_delete BEFORE DELETE ON migration_imports
        BEGIN SELECT RAISE(ABORT,'migration receipts are immutable'); END""",
    """CREATE TRIGGER IF NOT EXISTS migration_reversals_no_update BEFORE UPDATE ON migration_reversals
        BEGIN SELECT RAISE(ABORT,'migration reversals are immutable'); END""",
    """CREATE TRIGGER IF NOT EXISTS migration_reversals_no_delete BEFORE DELETE ON migration_reversals
        BEGIN SELECT RAISE(ABORT,'migration reversals are immutable'); END""",
)


def _digest(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


def _receipt(row) -> dict:
    if _digest(row["receipt"]) != row["receipt_hash"]:
        raise ServiceError("migration_corrupt", "migration receipt checksum failed", 503)
    try:
        result = json.loads(row["receipt"])
    except (TypeError, ValueError) as exc:
        raise ServiceError("migration_corrupt", "migration receipt is invalid", 503) from exc
    if not isinstance(result, dict):
        raise ServiceError("migration_corrupt", "migration receipt is invalid", 503)
    return result


class ClassicImporter:
    """Join all imported balances, debt, positions and receipt in one transaction.

    Only known linear USD-settled positions, gross cash and gross principal /
    interest are accepted. Every required in-flight collection must explicitly
    be empty. Imported accounts begin BLOCKED until a fresh supervisor decision.
    Source versions are snapshot versions, not independently verified event
    cursors. Public REST clients must not be given this operator-only object.
    """

    def __init__(self, exchange: ExchangeService, *, max_source_age: timedelta = timedelta(seconds=30)):
        if not isinstance(exchange, ExchangeService):
            raise ValueError("exchange must be an ExchangeService")
        if (not isinstance(max_source_age, timedelta) or max_source_age <= timedelta(0)
                or max_source_age > timedelta(minutes=5)):
            raise ValueError("max_source_age must be positive and at most five minutes")
        self.exchange, self.max_source_age = exchange, max_source_age
        with exchange._transaction() as conn:
            for statement in _SCHEMA:
                conn.execute(statement)
            row = conn.execute("SELECT version FROM migration_schema WHERE singleton=1").fetchone()
            if row is None:
                conn.execute("INSERT INTO migration_schema VALUES (1,1)")
            elif row["version"] != 1:
                raise ServiceError("migration_schema", "unsupported migration schema version", 503)

    def import_shadow(self, shadow: ShadowAccount, command_id: str, *,
                      source_fence_reference: str, open_orders, conditional_orders,
                      pending_settlements, transfers_in_flight) -> dict:
        """Transfer one fully quiesced source account, or replay its exact receipt.

        Completed receipts can be retried after source/market expiry because the
        retry cannot repeat the transfer. New transfers require both to be fresh.
        A different command ID may never import the same source account again.
        """
        _name(command_id, "command_id")
        _name(source_fence_reference, "source_fence_reference")
        if not isinstance(shadow, ShadowAccount):
            raise ServiceError("invalid_migration", "a reconciled ShadowAccount is required")
        if not isinstance(shadow.balances, tuple) or not isinstance(shadow.positions, tuple):
            raise ServiceError("invalid_migration", "shadow collections must be immutable tuples")
        _name(shadow.account_id, "account_id")
        for name, collection in (("open_orders", open_orders), ("conditional_orders", conditional_orders),
                                 ("pending_settlements", pending_settlements),
                                 ("transfers_in_flight", transfers_in_flight)):
            if not isinstance(collection, (tuple, list)):
                raise ServiceError("invalid_migration", f"{name} must be an explicit list")
            if collection:
                raise ServiceError("unsupported_migration_state", f"nonempty {name} cannot be transferred by this version", 409)
        if len(shadow.balances) > 3000 or len(shadow.positions) > 1000:
            raise ServiceError("migration_limit", "snapshot exceeds supported migration size", 409)
        # Recompute digest and exact amounts even for an idempotent retry; only
        # time freshness is deferred until a new transfer is actually necessary.
        try:
            account = shadow_to_account(shadow, open_order_margin=Decimal(0), now=shadow.captured_at)
        except (MigrationError, ValueError, TypeError, AttributeError) as exc:
            raise ServiceError("invalid_migration", "shadow contents or digest are invalid") from exc
        if any(balance.locked for balance in shadow.balances):
            raise ServiceError("unsupported_lock", "locked balances require per-object freeze reasons and cannot be imported", 409)
        request_digest = _digest(_json({"source_digest": shadow.source_digest,
                                       "source_fence_reference": source_fence_reference,
                                       "empty_in_flight_policy": 1}))
        service = self.exchange
        with service._transaction() as conn:
            previous = conn.execute("SELECT * FROM migration_imports WHERE command_id=?", (command_id,)).fetchone()
            if previous is not None:
                if previous["source_account_id"] != shadow.account_id or previous["request_digest"] != request_digest:
                    raise ServiceError("idempotency_conflict", "migration command ID was reused with different contents", 409)
                return _receipt(previous)
            if conn.execute("SELECT 1 FROM migration_imports WHERE source_account_id=?", (shadow.account_id,)).fetchone():
                raise ServiceError("source_already_imported", "source account already has an authoritative handover", 409)
            try:
                shadow_to_account(shadow, open_order_margin=Decimal(0), now=service._now(),
                                  max_age=self.max_source_age)
            except MigrationError as exc:
                raise ServiceError("stale_migration", "source snapshot is stale or from the future", 409) from exc
            market = service._market(conn)
            for asset in set(account.balances) | set(account.liabilities):
                if asset not in service.scales or asset not in market.assets:
                    raise ServiceError("migration_asset", "every imported asset requires scale and trusted price", 409)
            for symbol, position in account.positions.items():
                if symbol not in market.instruments:
                    raise ServiceError("migration_product", "only known linear USD instruments can be imported", 409)
                if service.product_catalog is not None:
                    try:
                        product = service.product_catalog.require_risk_supported(symbol, mode=AccountMode.CROSS)
                    except RiskInputError as exc:
                        raise ServiceError("migration_product", "catalog does not support this existing exposure", 409) from exc
                    if (product.kind is not ProductKind.LINEAR_PERPETUAL or product.multiplier != 1
                            or product.settlement_asset != "USD" or product.quote_asset != "USD"):
                        raise ServiceError("migration_product", "migration requires linear perpetual USD products with multiplier one", 409)
                _amount(position.quantity, "migration position quantity", nonzero=True)
                _amount(position.entry_price, "migration entry price", positive=True)
            self._empty_destination(conn, shadow.account_id)
            if conn.execute("SELECT 1 FROM uta_accounts WHERE account_id=?", (shadow.account_id,)).fetchone() is None:
                conn.execute("INSERT INTO uta_accounts VALUES (?,0)", (shadow.account_id,))
                service._event(conn, "ACCOUNT_CREATED", shadow.account_id, {"account_id": shadow.account_id, "origin": "classic_migration"})

            principal: dict[str, Fraction] = {}
            interest: dict[str, Fraction] = {}
            for balance in shadow.balances:
                principal[balance.asset] = principal.get(balance.asset, Fraction(0)) + Fraction(balance.borrowed)
                interest[balance.asset] = interest.get(balance.asset, Fraction(0)) + Fraction(balance.interest)
            postings = []
            for asset, amount in sorted(account.balances.items()):
                if amount:
                    postings.extend((Posting(service._customer(shadow.account_id), asset, amount),
                                     Posting("system:migration-custody", asset, amount.copy_negate())))
            for asset in sorted(principal.keys() | interest.keys()):
                p, i = _exact(principal[asset]), _exact(interest[asset])
                if p:
                    postings.extend((Posting("liability:principal:" + shadow.account_id, asset, p.copy_negate()),
                                     Posting("system:credit-principal-receivable", asset, p)))
                if i:
                    postings.extend((Posting("liability:interest:" + shadow.account_id, asset, i.copy_negate()),
                                     Posting("system:credit-interest-receivable", asset, i)))
                if p or i:
                    conn.execute("INSERT INTO uta_liabilities VALUES (?,?,?,?)", (shadow.account_id, asset, _text(p), _text(i)))
            ledger_id = "migration:" + _digest(_json([shadow.account_id, command_id])) if postings else None
            if postings:
                service.ledger.post(ledger_id, postings, connection=conn)
            for symbol, position in sorted(account.positions.items()):
                cost = _exact(Fraction(position.quantity) * Fraction(position.entry_price))
                conn.execute("INSERT INTO uta_positions VALUES (?,?,?,?)",
                             (shadow.account_id, symbol, _text(position.quantity), _text(cost)))
            conn.execute("""INSERT INTO uta_liquidation_accounts VALUES (?,'BLOCKED',0,0,NULL,NULL)
                ON CONFLICT(account_id) DO UPDATE SET state='BLOCKED',cycle=0,revision=0,
                plan_market_version=NULL,plan_position_digest=NULL""", (shadow.account_id,))
            version = service._bump(conn, shadow.account_id)
            actual = service._risk(conn, shadow.account_id, market)
            expected_assets = {asset: _text(amount) for asset, amount in account.balances.items()}
            expected_debt = {asset: {"principal": _text(_exact(principal[asset])),
                                     "interest": _text(_exact(interest[asset]))}
                             for asset in sorted(principal.keys() | interest.keys()) if principal[asset] or interest[asset]}
            expected_positions = {symbol: {"quantity": _text(position.quantity),
                                            "cost_basis": _text(_exact(Fraction(position.quantity) * Fraction(position.entry_price)))}
                                  for symbol, position in sorted(account.positions.items())}
            self._check_unchanged(conn, {"account_id": shadow.account_id, "assets": expected_assets,
                                         "liabilities": expected_debt, "positions": expected_positions})
            if service.product_catalog is None:
                # The legacy reference has identical fixed-rate risk semantics.
                # Keep its historical full-risk comparison for reference users.
                expected = calculate_risk(account, market.assets, market.instruments)
                if any(Decimal(actual[name]) != getattr(expected, name)
                       for name in ("equity", "initial_margin", "maintenance_margin", "open_order_margin", "available_margin")):
                    raise ServiceError("migration_reconciliation", "imported risk differs from reconciled source", 409)
                reconciliation_basis = "legacy_reference_risk"
            else:
                # Source accounting and configured Cross margin are different
                # contracts: borrow IM/MM and tiered haircuts must not cause a
                # valid, already-confirmed source balance to disappear. Reconcile
                # unhaircutted accounting equity with an independent cash-flow
                # expression; the configured calculator reports its own margin.
                expected_accounting = sum((Fraction(amount) * Fraction(market.assets[asset].price)
                                           for asset, amount in account.balances.items()), Fraction(0))
                expected_accounting -= sum((Fraction(amount) * Fraction(market.assets[asset].price)
                                            for asset, amount in account.liabilities.items()), Fraction(0))
                expected_accounting += sum((Fraction(position.quantity) * Fraction(market.instruments[symbol].mark_price)
                                             - Fraction(position.quantity) * Fraction(position.entry_price)
                                             for symbol, position in account.positions.items()), Fraction(0))
                if Fraction(Decimal(actual["accounting_equity"])) != expected_accounting:
                    raise ServiceError("migration_reconciliation", "imported accounting equity differs from gross source components", 409)
                reconciliation_basis = "configured_gross_accounting_equity"
            receipt = {
                "command_id": command_id, "account_id": shadow.account_id,
                "source_version": shadow.source_version, "source_digest": shadow.source_digest,
                "source_event_cursor": None, "incremental_events_verified": False,
                "captured_at": shadow.captured_at.isoformat(),
                "source_fence_reference": source_fence_reference, "source_fence_verified": False,
                "market_version": market.version, "account_version": version,
                "imported_at": service._now().isoformat(), "state": "BLOCKED",
                "ledger_event_id": ledger_id,
                "journal_postings": [{"account": posting.account, "asset": posting.asset,
                                      "amount": _text(posting.amount)} for posting in postings],
                "assets": expected_assets, "liabilities": expected_debt, "positions": expected_positions,
                "risk_at_import": actual, "reconciliation_basis": reconciliation_basis,
            }
            encoded = _json(receipt)
            conn.execute("INSERT INTO migration_imports VALUES (?,?,?,?,?)",
                         (command_id, shadow.account_id, request_digest, encoded, _digest(encoded)))
            service._event(conn, "MIGRATION_IMPORTED", shadow.account_id,
                           {key: receipt[key] for key in ("command_id", "source_version", "source_digest",
                                                         "market_version", "account_version", "ledger_event_id", "state")})
            return receipt

    def _empty_destination(self, conn, account_id: str) -> None:
        service = self.exchange
        existing = conn.execute("SELECT version FROM uta_accounts WHERE account_id=?", (account_id,)).fetchone()
        if existing is not None and existing["version"] != 0:
            raise ServiceError("destination_not_empty", "destination has already changed", 409)
        for table in ("uta_positions", "uta_orders", "uta_fills", "uta_deposits", "uta_liabilities"):
            if conn.execute(f"SELECT 1 FROM {table} WHERE account_id=? LIMIT 1", (account_id,)).fetchone():
                raise ServiceError("destination_not_empty", "destination contains financial state or history", 409)
        for account in (service._customer(account_id), "liability:principal:" + account_id,
                        "liability:interest:" + account_id):
            if conn.execute("SELECT 1 FROM ledger_postings WHERE account=? LIMIT 1", (account,)).fetchone():
                raise ServiceError("destination_not_empty", "destination contains financial journal history", 409)

    def receipt(self, command_id: str) -> dict:
        _name(command_id, "command_id")
        with self.exchange._transaction() as conn:
            row = conn.execute("SELECT * FROM migration_imports WHERE command_id=?", (command_id,)).fetchone()
            if row is None:
                raise ServiceError("migration_not_found", "unknown migration command", 404)
            return _receipt(row)

    def status(self, command_id: str) -> dict:
        """Query historical handover and any later handback without ambiguity."""
        _name(command_id, "command_id")
        with self.exchange._transaction() as conn:
            row = conn.execute("SELECT * FROM migration_imports WHERE command_id=?", (command_id,)).fetchone()
            if row is None:
                raise ServiceError("migration_not_found", "unknown migration command", 404)
            original = _receipt(row)
            reverse_row = conn.execute("SELECT * FROM migration_reversals WHERE command_id=?", (command_id,)).fetchone()
            return {"import": original, "handback": _receipt(reverse_row) if reverse_row is not None else None,
                    "active": reverse_row is None,
                    "current_account_version": self.exchange._require_account(conn, original["account_id"])["version"]}

    def reverse_import(self, command_id: str, reversal_id: str, *, source_handback_reference: str) -> dict:
        """Append a compensating handback only before any post-import mutation.

        An external operator must establish source authority before using this
        receipt. Once new trading/credit/state changes occur, forward recovery
        and reconciliation are required; an old database backup is not rollback.
        """
        for value, name in ((command_id, "command_id"), (reversal_id, "reversal_id"),
                            (source_handback_reference, "source_handback_reference")):
            _name(value, name)
        service = self.exchange
        with service._transaction() as conn:
            previous = conn.execute("SELECT * FROM migration_reversals WHERE reversal_id=?", (reversal_id,)).fetchone()
            if previous is not None:
                receipt = _receipt(previous)
                if receipt["command_id"] != command_id or receipt["source_handback_reference"] != source_handback_reference:
                    raise ServiceError("idempotency_conflict", "reversal ID was reused with different contents", 409)
                return receipt
            original_row = conn.execute("SELECT * FROM migration_imports WHERE command_id=?", (command_id,)).fetchone()
            if original_row is None:
                raise ServiceError("migration_not_found", "unknown migration command", 404)
            if conn.execute("SELECT 1 FROM migration_reversals WHERE command_id=?", (command_id,)).fetchone():
                raise ServiceError("migration_already_reversed", "migration already has a handback", 409)
            original = _receipt(original_row)
            account_id = original["account_id"]
            if service._require_account(conn, account_id)["version"] != original["account_version"]:
                raise ServiceError("migration_forward_recovery_required", "post-import mutation prevents automatic handback", 409)
            if service._live_orders(conn, account_id):
                raise ServiceError("migration_forward_recovery_required", "live orders prevent handback", 409)
            self._check_unchanged(conn, original)
            postings = [Posting(item["account"], item["asset"], Decimal(item["amount"]).copy_negate())
                        for item in original["journal_postings"]]
            ledger_id = "migration-reversal:" + _digest(_json([command_id, reversal_id])) if postings else None
            if postings:
                service.ledger.post(ledger_id, postings, connection=conn)
            conn.execute("DELETE FROM uta_positions WHERE account_id=?", (account_id,))
            conn.execute("DELETE FROM uta_liabilities WHERE account_id=?", (account_id,))
            version = service._bump(conn, account_id)
            receipt = {"reversal_id": reversal_id, "command_id": command_id, "account_id": account_id,
                       "source_handback_reference": source_handback_reference, "source_fence_verified": False,
                       "account_version": version, "ledger_event_id": ledger_id,
                       "reversed_at": service._now().isoformat(), "state": "BLOCKED"}
            encoded = _json(receipt)
            conn.execute("INSERT INTO migration_reversals VALUES (?,?,?,?)",
                         (reversal_id, command_id, encoded, _digest(encoded)))
            service._event(conn, "MIGRATION_REVERSED", account_id, receipt)
            return receipt

    def _check_unchanged(self, conn, original: dict) -> None:
        service, account_id = self.exchange, original["account_id"]
        actual = service._account(conn, account_id)
        expected_assets = {asset: Decimal(original["assets"].get(asset, "0")) for asset in service.scales}
        actual_debt = {asset: {key: value[key] for key in ("principal", "interest")}
                       for asset, value in actual["liabilities"].items()}
        actual_positions = {symbol: {key: value[key] for key in ("quantity", "cost_basis")}
                            for symbol, value in actual["positions"].items()}
        if ({asset: Decimal(value) for asset, value in actual["balances"].items()} != expected_assets
                or actual_debt != original["liabilities"] or actual_positions != original["positions"]):
            raise ServiceError("migration_reconciliation", "destination differs from imported state", 409)

    def verify(self) -> int:
        """Check receipt checksums, original/reversal postings and unchanged books.

        This verifies retained local evidence. It cannot establish source-side
        funds, the external fence, or missing incremental source events.
        """
        service = self.exchange
        with service._transaction() as conn:
            service.ledger.verify(connection=conn)
            version = conn.execute("SELECT version FROM migration_schema WHERE singleton=1").fetchone()
            guards = {statement.split("EXISTS ", 1)[1].split()[0]
                      for statement in _SCHEMA if statement.startswith("CREATE TRIGGER")}
            installed = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='trigger'")}
            if version is None or version[0] != 1 or not guards <= installed:
                raise ServiceError("migration_corrupt", "migration schema or receipt guard is missing", 503)
            count = 0
            for row in conn.execute("SELECT * FROM migration_imports ORDER BY command_id").fetchall():
                receipt = _receipt(row)
                expected_request = _digest(_json({"source_digest": receipt["source_digest"],
                                                   "source_fence_reference": receipt["source_fence_reference"],
                                                   "empty_in_flight_policy": 1}))
                if (row["command_id"] != receipt["command_id"] or row["source_account_id"] != receipt["account_id"]
                        or row["request_digest"] != expected_request):
                    raise ServiceError("migration_corrupt", "migration identity differs from receipt", 503)
                actual_postings = []
                if receipt["ledger_event_id"] is not None:
                    event = conn.execute("SELECT sequence FROM ledger_events WHERE event_id=?", (receipt["ledger_event_id"],)).fetchone()
                    if event is None:
                        raise ServiceError("migration_corrupt", "migration journal event is missing", 503)
                    journal = service.ledger._event(conn, event["sequence"], receipt["ledger_event_id"])
                    actual_postings = sorted((p.account, p.asset, _text(p.amount)) for p in journal.postings)
                expected_postings = sorted((p["account"], p["asset"], p["amount"]) for p in receipt["journal_postings"])
                if actual_postings != expected_postings:
                    raise ServiceError("migration_corrupt", "migration receipt differs from original journal", 503)
                reverse_row = conn.execute("SELECT * FROM migration_reversals WHERE command_id=?", (row["command_id"],)).fetchone()
                if reverse_row is not None:
                    reversal = _receipt(reverse_row)
                    if reversal["ledger_event_id"] is not None:
                        event = conn.execute("SELECT sequence FROM ledger_events WHERE event_id=?", (reversal["ledger_event_id"],)).fetchone()
                        if event is None:
                            raise ServiceError("migration_corrupt", "reversal journal event is missing", 503)
                        journal = service.ledger._event(conn, event["sequence"], reversal["ledger_event_id"])
                        reversed_postings = sorted((p.account, p.asset, _text(p.amount.copy_negate())) for p in journal.postings)
                        if reversed_postings != expected_postings:
                            raise ServiceError("migration_corrupt", "reversal is not the exact compensating journal", 503)
                elif service._require_account(conn, receipt["account_id"])["version"] == receipt["account_version"]:
                    self._check_unchanged(conn, receipt)
                count += 1
            return count
