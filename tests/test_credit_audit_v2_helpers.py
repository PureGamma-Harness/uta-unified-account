"""Actual preseal reads and clock/journal helpers, without a V2 loan claim."""
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal as D
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from uta.credit import CreditService
from uta.credit_audit_v2 import (CreditAuditError, audit_policy, journal_record, read_credit_snapshot,
    strict_json, utc_checkpoint, validate_checkpoints, verify_journal)
from uta.market import MarketSnapshot
from uta.portfolio import PortfolioRules
from uta.products import ProductCatalog
from uta.service import ExchangeService
from uta.storage import Database


class CreditAuditV2HelperTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory(prefix="credit-v2-audit-helpers-")
        self.addCleanup(self.temp.cleanup)
        self.now = datetime(2026, 11, 17, tzinfo=timezone.utc)
        fixture = json.loads(Path("tests/fixtures/managed_credit_v1_canonical_example.json").read_text())["documents"]
        self.market = MarketSnapshot.from_json(fixture["market_snapshot"]["canonical_payload"])
        self.service = ExchangeService(Database(Path(self.temp.name) / "synthetic.sqlite3"), {"USD": 8, "BTC": 8},
            product_catalog=ProductCatalog.from_json(fixture["catalog"]["canonical_payload"]),
            portfolio_rules=PortfolioRules.from_json(fixture["risk_rules"]["canonical_payload"]),
            fee_rate=D(0), clock=lambda: self.now)
        self.service.create_account("alice")
        self.service.deposit("alice", "cash", "USD", D(100))
        self.service.publish_market(self.market)
        self.service.set_kill_switch(False)
        self.credit = CreditService(self.service)
        self.credit.configure_asset_limit("BTC", D(".5"))
        self.credit.configure_limit("alice", "BTC", D(".5"))
        self.credit.fund_pool("pool", "BTC", D(1), source_reference="synthetic:helper:pool")

    def test_actual_read_preserves_gross_components_and_requires_real_connection(self):
        with self.service._transaction() as connection:
            before, limits = read_credit_snapshot(self.service, self.credit, connection, "alice", "BTC")
            self.assertEqual((before["principal_units"], before["cash_units"], before["pool_units"]),
                             ("0", "0", "100000000"))
            self.assertEqual(limits, {"account_limit_units": "50000000", "local_asset_limit_units": "50000000"})
        with self.assertRaises(CreditAuditError):
            read_credit_snapshot(self.service, self.credit, None, "alice", "BTC")
        self.credit.borrow("alice", "preseal-reference", "BTC", D(".4"))
        self.credit.accrue_interest("alice", "preseal-interest", "BTC", D(".05"))
        with self.service._transaction() as connection:
            after, _ = read_credit_snapshot(self.service, self.credit, connection, "alice", "BTC")
            self.assertEqual((after["cash_units"], after["principal_units"], after["interest_units"],
                after["principal_receivable_units"], after["interest_receivable_units"]),
                ("40000000", "40000000", "5000000", "40000000", "5000000"))

    def test_repayment_read_avoids_all_borrow_limit_queries_and_fresh_market(self):
        self.credit.borrow("alice", "preseal-reference", "BTC", D(".4"))
        self.credit.accrue_interest("alice", "preseal-interest", "BTC", D(".05"))
        self.now += timedelta(days=1)
        self.service.set_kill_switch(True)
        self.credit.repay("alice", "preseal-repay", "BTC", D(".1"))
        with self.service._transaction() as connection:
            trace = []
            connection.set_trace_callback(trace.append)
            snapshot, limits = read_credit_snapshot(self.service, self.credit, connection, "alice", "BTC", require_limits=False)
            connection.set_trace_callback(None)
            self.assertIsNone(limits)
            self.assertEqual((snapshot["cash_units"], snapshot["principal_units"], snapshot["interest_units"], snapshot["pool_units"]),
                             ("30000000", "35000000", "0", "65000000"))
            self.assertFalse(any("credit_account_limits" in statement or "credit_asset_limits" in statement
                                 or "uta_market" in statement for statement in trace))

    def test_actual_journal_links_to_pre_head_and_has_all_ordered_legs(self):
        with self.service.database.read_transaction() as connection:
            head = dict(connection.execute("SELECT sequence,event_hash FROM ledger_events ORDER BY sequence DESC LIMIT 1").fetchone())
        receipt = self.credit.borrow("alice", "preseal-reference", "BTC", D(".4"))
        legs = [{"ordinal": ordinal, "account": account, "asset": "BTC", "units": units}
            for ordinal, (account, units) in enumerate((("customer:alice", "40000000"),
                ("liability:principal:alice", "-40000000"), ("system:credit-pool", "-40000000"),
                ("system:credit-principal-receivable", "40000000")))]
        with self.service.database.read_transaction() as connection:
            actual = journal_record(connection, receipt["journal_event_id"])
        self.assertTrue(verify_journal(actual, expected_event_id=receipt["journal_event_id"], expected_postings=legs, journal_head=head))
        for field in ("event_hash", "previous_hash", "fingerprint"):
            changed = deepcopy(actual)
            changed[field] = "f"*64
            with self.subTest(field=field), self.assertRaises(CreditAuditError):
                verify_journal(changed, expected_event_id=receipt["journal_event_id"], expected_postings=legs, journal_head=head)
        changed = deepcopy(actual)
        changed["postings"][0]["ordinal"] = False
        with self.assertRaises(CreditAuditError):
            verify_journal(changed, expected_event_id=receipt["journal_event_id"], expected_postings=legs, journal_head=head)

    def test_actual_policy_is_pinned_to_persisted_rules(self):
        with self.service._transaction() as connection:
            policy = audit_policy(self.service, connection)
            self.assertEqual(policy["format"], 2)
            self.assertFalse(policy["physical_commit_time_captured"])
        original = self.service._portfolio_rules
        self.service._portfolio_rules = replace(original, max_total_debt=D(9999))
        try:
            with self.service._transaction() as connection:
                with self.assertRaises(CreditAuditError) as rejected:
                    audit_policy(self.service, connection)
                self.assertEqual(rejected.exception.code, "credit_audit_policy_mismatch")
        finally:
            self.service._portfolio_rules = original

    def test_recorded_freshness_and_future_equalities_use_original_clock(self):
        with self.service._transaction() as connection:
            policy = audit_policy(self.service, connection)
        start = self.now.isoformat()
        edge = (self.now + timedelta(seconds=5)).isoformat()
        validate_checkpoints(self.market, policy, selected_at=start, last_checked_at=edge, recorded_at=edge)
        with self.assertRaises(CreditAuditError):
            validate_checkpoints(self.market, policy, selected_at=start,
                last_checked_at=(self.now+timedelta(seconds=5,microseconds=1)).isoformat(),
                recorded_at=(self.now+timedelta(seconds=5,microseconds=1)).isoformat())
        future = MarketSnapshot(self.market.version, self.now+timedelta(seconds=1), self.market.assets, self.market.instruments)
        validate_checkpoints(future, policy, selected_at=start, last_checked_at=start, recorded_at=start)
        future_bad = MarketSnapshot(self.market.version, self.now+timedelta(seconds=1,microseconds=1), self.market.assets, self.market.instruments)
        with self.assertRaises(CreditAuditError):
            validate_checkpoints(future_bad, policy, selected_at=start, last_checked_at=start, recorded_at=start)
        with self.assertRaises(CreditAuditError):
            validate_checkpoints(self.market, policy, selected_at=edge, last_checked_at=start, recorded_at=edge)

    def test_strict_utc_and_json_do_not_normalize_invalid_evidence(self):
        for value in ("2026-11-17T00:00:00Z", "2026-11-17T01:00:00+01:00", "2026-11-17T00:00:00.1+00:00", True):
            with self.subTest(value=value), self.assertRaises(CreditAuditError):
                utc_checkpoint(value)
        self.assertEqual(utc_checkpoint("2026-11-17T00:00:00.000000+00:00"), self.now)
        self.assertEqual(strict_json('{"value":"0.4"}'), {"value": "0.4"})
        for value in ('{"format":2,"format":2}', '{"value":NaN}', '{"value":0.4}',
                      '{"version":'+'9'*1000+'}', ' {"value":"0.4"}'):
            with self.subTest(value=value[:20]), self.assertRaises(CreditAuditError):
                strict_json(value)
