"""Offline accounting arithmetic plus a real preseal borrow positive control."""
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal as D, Inexact, localcontext
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import MappingProxyType
import unittest

from tests.credit_policy_cases import descriptor, reseal
from uta.credit import CreditService
from uta.credit_policy import validate_native_descriptor
from uta.credit_transition import (CreditTransitionError, calculate_borrow_transition,
                                   compare_borrow_transition)
from uta.market import MarketSnapshot
from uta.portfolio import PortfolioRules
from uta.products import ProductCatalog
from uta.service import ExchangeService
from uta.storage import Database


def state(**changes):
    result = {"version": 1, "cash_units": "0", "principal_units": "0", "interest_units": "0",
        "principal_ledger_units": "0", "interest_ledger_units": "0", "shard_principal_units": "0",
        "shard_interest_units": "0", "pool_units": "100000000", "principal_receivable_units": "0",
        "interest_receivable_units": "0"}
    result.update(changes)
    return result


class CreditTransitionTests(unittest.TestCase):
    def calculate(self, **changes):
        args = {"descriptor": validate_native_descriptor(descriptor(), expected_authority_id="credit:shard0"),
            "account_id": "alice", "asset": "BTC", "amount_units": "40000000", "before": state(),
            "limits": {"account_limit_units": "50000000", "local_asset_limit_units": "50000000"},
            "quote_units": "50000000", "quantity_step_units": "1000000"}
        args.update(changes)
        return calculate_borrow_transition(**args)

    def test_manual_four_leg_gross_transition_and_static_allocation(self):
        expected = self.calculate()
        wire = expected.wire()
        self.assertEqual((wire["after"]["cash_units"], wire["after"]["principal_units"],
                          wire["after"]["pool_units"], wire["after"]["principal_receivable_units"]),
                         ("40000000", "40000000", "60000000", "40000000"))
        self.assertEqual(wire["after"]["version"], 2)
        self.assertEqual([row["units"] for row in wire["postings"]],
                         ["40000000", "-40000000", "-40000000", "40000000"])
        answer = compare_borrow_transition(expected, after=wire["after"], postings=wire["postings"])
        self.assertTrue(answer["accounting_matches"])
        self.assertFalse(answer["operation_authorized"])
        self.assertFalse(hasattr(expected, "accepted"))
        with self.assertRaises(TypeError):
            expected.after["cash_units"] = 0

    def test_gross_interest_never_nets_against_same_asset_cash(self):
        before = state(cash_units="30000000", principal_units="20000000", interest_units="1000000",
            principal_ledger_units="-20000000", interest_ledger_units="-1000000",
            shard_principal_units="20000000", shard_interest_units="1000000",
            principal_receivable_units="20000000", interest_receivable_units="1000000")
        with self.assertRaises(CreditTransitionError) as refused:
            self.calculate(before=before, amount_units="30000000")
        self.assertEqual((refused.exception.code, refused.exception.status), ("credit_limit", 409))
        result = self.calculate(before=before, amount_units="29000000")
        self.assertEqual(result.after["principal_units"] + result.after["interest_units"], 50000000)
        self.assertEqual(result.after["cash_units"], 59000000)
        self.assertEqual(result.after["interest_units"], 1000000)

    def test_other_accounts_consume_same_local_allocation_at_equality(self):
        before = state(shard_principal_units="30000000", principal_receivable_units="30000000")
        self.calculate(before=before, amount_units="20000000")
        with self.assertRaises(CreditTransitionError) as refused:
            self.calculate(before=before, amount_units="21000000")
        self.assertEqual(refused.exception.code, "credit_limit")

    def test_unreachable_other_shard_budget_is_never_borrowed_or_reassigned(self):
        doc = descriptor()
        allocations = doc["certificate"]["assets"]["BTC"]["allocations"]
        allocations[0]["limit_units"], allocations[1]["limit_units"] = "0", "100000000"
        parsed = validate_native_descriptor(reseal(doc), expected_authority_id="credit:shard0")
        with self.assertRaises(CreditTransitionError) as refused:
            self.calculate(descriptor=parsed, amount_units="1000000")
        self.assertEqual(refused.exception.code, "credit_limit")

    def test_constructed_descriptor_fields_cannot_enlarge_canonical_budget(self):
        parsed = validate_native_descriptor(descriptor(), expected_authority_id="credit:shard0")
        budget = parsed.assets[0]
        raised = replace(budget.allocations[0], limit_units=100000000)
        forged = replace(parsed, assets=(replace(budget, allocations=(raised, budget.allocations[1])),))
        with self.assertRaises(CreditTransitionError) as refused:
            self.calculate(descriptor=forged, amount_units="60000000", quote_units="100000000",
                limits={"account_limit_units": "100000000", "local_asset_limit_units": "100000000"})
        self.assertEqual(refused.exception.code, "credit_limit")

    def test_final_integer_version_roundtrip_requires_no_further_advance(self):
        expected = self.calculate(before=state(version=2**63-2))
        self.assertEqual(expected.after["version"], 2**63-1)
        wire = expected.wire()
        self.assertTrue(compare_borrow_transition(expected, after=wire["after"],
            postings=wire["postings"])["accounting_matches"])
        self.assertRaises(CreditTransitionError, self.calculate, before=state(version=2**63-1))

    def test_public_result_is_recomputed_instead_of_being_a_verification_seal(self):
        expected = self.calculate()
        after = dict(expected.after)
        after["cash_units"] += 1
        forged = replace(expected, after=MappingProxyType(after))
        wire = forged.wire()
        with self.assertRaises(CreditTransitionError) as refused:
            compare_borrow_transition(forged, after=wire["after"], postings=wire["postings"])
        self.assertEqual(refused.exception.code, "credit_transition_mismatch")
        forged = replace(expected, postings=tuple((account, units*2) for account, units in expected.postings))
        wire = forged.wire()
        with self.assertRaises(CreditTransitionError) as refused:
            compare_borrow_transition(forged, after=wire["after"], postings=wire["postings"])
        self.assertEqual(refused.exception.code, "credit_transition_mismatch")
        for raw in ("{}", expected.inputs_payload+" ", "\ud800",
                    expected.inputs_payload[:-1]+',"account_id":"alice"}'):
            with self.subTest(raw=raw[:8]), self.assertRaises(CreditTransitionError):
                compare_borrow_transition(replace(expected, inputs_payload=raw),
                    after=expected.wire()["after"], postings=expected.wire()["postings"])

    def test_missing_allocation_is_internal_invalid_evidence_with_status(self):
        with self.assertRaises(CreditTransitionError) as refused:
            self.calculate(asset="UNKNOWN")
        self.assertEqual((refused.exception.code, refused.exception.status), ("credit_transition_invalid", 503))

    def test_pool_quote_step_and_explicit_limits_each_block_the_transition(self):
        for changes, code in (({"before": state(pool_units="39999999")}, "credit_pool_empty"),
            ({"quote_units": "39999999"}, "credit_limit"),
            ({"amount_units": "40000001"}, "credit_transition_invalid"),
            ({"quantity_step_units": "0"}, "credit_transition_invalid"),
            ({"limits": {}}, "credit_transition_invalid"),
            ({"limits": {"account_limit_units": "39999999", "local_asset_limit_units": "50000000"}}, "credit_limit"),
            ({"limits": {"account_limit_units": "50000000", "local_asset_limit_units": "39999999"}}, "credit_limit")):
            with self.subTest(changes=changes), self.assertRaises(CreditTransitionError) as refused:
                self.calculate(**changes)
            self.assertEqual(refused.exception.code, code)

    def test_journal_mismatch_shard_gross_components_and_overflow_fail(self):
        for changes in ({"principal_units": "1"}, {"interest_units": "1"},
                {"shard_principal_units": "1"}, {"principal_receivable_units": "1"},
                {"cash_units": str(10**38-1)}, {"version": 2**63-1}):
            with self.subTest(changes=changes), self.assertRaises(CreditTransitionError):
                self.calculate(before=state(**changes))

    def test_negative_cash_is_preserved_as_a_separate_gross_component(self):
        expected = self.calculate(before=state(cash_units="-50000000"))
        self.assertEqual(expected.after["cash_units"], -10000000)
        self.assertEqual(expected.after["principal_units"], 40000000)

    def test_no_float_bool_noncanonical_unicode_or_unbounded_integer_coercion(self):
        for value in (1, True, 1.0, "-0", "+1", "01", "1.0", "1e8", "１", "9"*10000):
            with self.subTest(kind=type(value).__name__), self.assertRaises(CreditTransitionError):
                self.calculate(amount_units=value)
        self.assertRaises(CreditTransitionError, self.calculate, before=state(version=True))

    def test_every_recorded_post_state_field_and_posting_is_compared(self):
        expected = self.calculate()
        wire = expected.wire()
        for field in wire["after"]:
            after = deepcopy(wire["after"])
            after[field] = after[field] + 1 if field == "version" else str(int(after[field]) + 1)
            with self.subTest(field=field), self.assertRaises(CreditTransitionError):
                compare_borrow_transition(expected, after=after, postings=wire["postings"])
        for change in ("missing", "units", "ordinal", "account", "asset", "bool_ordinal"):
            postings = deepcopy(wire["postings"])
            if change == "missing": postings.pop()
            elif change == "bool_ordinal": postings[0]["ordinal"] = False
            elif change == "ordinal": postings[0]["ordinal"] = 1
            elif change == "units": postings[0]["units"] = "40000001"
            else: postings[0][change] = "wrong"
            with self.subTest(change=change), self.assertRaises(CreditTransitionError):
                compare_borrow_transition(expected, after=wire["after"], postings=postings)

    def test_decimal_context_cannot_round_integer_transition(self):
        with localcontext() as context:
            context.prec = 1
            context.traps[Inexact] = True
            self.assertEqual(self.calculate().after["principal_units"], 40000000)

    def test_actual_preseal_borrow_full_cash_debt_pool_and_ordered_journal_control(self):
        fixture = json.loads(Path("tests/fixtures/managed_credit_v1_canonical_example.json").read_text())
        documents = fixture["documents"]
        now = datetime(2026, 11, 17, tzinfo=timezone.utc)
        with TemporaryDirectory(prefix="credit-transition-") as directory:
            service = ExchangeService(Database(Path(directory)/"reference.sqlite3"), {"USD": 8, "BTC": 8},
                product_catalog=ProductCatalog.from_json(documents["catalog"]["canonical_payload"]),
                portfolio_rules=PortfolioRules.from_json(documents["risk_rules"]["canonical_payload"]), clock=lambda: now)
            service.create_account("alice")
            service.deposit("alice", "synthetic-cash", "USD", D(100))
            service.publish_market(MarketSnapshot.from_json(documents["market_snapshot"]["canonical_payload"]))
            service.set_kill_switch(False)
            credit = CreditService(service)
            credit.configure_asset_limit("BTC", D(".5"))
            credit.configure_limit("alice", "BTC", D(".5"))
            credit.fund_pool("pool:0", "BTC", D(1), source_reference="synthetic:credit-pool:0")
            def snapshot(connection):
                principal, interest = credit._debt(connection, "alice", "BTC")
                totals = [tuple(credit._stored("BTC", row[key]) for key in ("principal", "interest"))
                    for row in connection.execute("SELECT principal,interest FROM uta_liabilities WHERE asset='BTC'")]
                def balance(account):
                    return str(credit._codec._units("BTC", service.ledger.balance(account,"BTC",connection=connection)))
                return {"version": service._require_account(connection,"alice")["version"],
                    "cash_units": balance("customer:alice"), "principal_units": str(principal),
                    "interest_units": str(interest), "principal_ledger_units": balance("liability:principal:alice"),
                    "interest_ledger_units": balance("liability:interest:alice"),
                    "shard_principal_units": str(sum(row[0] for row in totals)),
                    "shard_interest_units": str(sum(row[1] for row in totals)),
                    "pool_units": balance("system:credit-pool"),
                    "principal_receivable_units": balance("system:credit-principal-receivable"),
                    "interest_receivable_units": balance("system:credit-interest-receivable")}
            with service._transaction() as connection:
                before = snapshot(connection)
                quote = service._risk(connection,"alice",service._market(connection))["borrowable"]["BTC"]
                expected = self.calculate(before=before,quote_units=str(credit._codec._units("BTC",D(quote))))
                receipt = credit._borrow(connection,"alice","synthetic-loan","BTC",D(".4"))
                after = snapshot(connection)
                postings = [dict(row) for row in connection.execute("SELECT ordinal,account,asset,units FROM ledger_postings WHERE sequence=(SELECT sequence FROM ledger_events WHERE event_id=?) ORDER BY ordinal",(receipt["journal_event_id"],))]
                comparison = compare_borrow_transition(expected,after=after,postings=postings)
                self.assertTrue(comparison["accounting_matches"])
                self.assertFalse(comparison["operation_authorized"])
            # Reopen the actual committed store; this does not manufacture any
            # managed inbox/source/decision or promote the reference loan.
            with service.database.read_transaction() as connection:
                self.assertEqual(snapshot(connection),after)
                self.assertEqual(connection.execute("SELECT COUNT(*) FROM credit_commands WHERE kind='borrowed'").fetchone()[0],1)
                service.ledger.verify(connection=connection)
                credit._verify(connection)
