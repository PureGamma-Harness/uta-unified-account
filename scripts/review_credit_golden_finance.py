#!/usr/bin/env python3
"""Independent, small Fraction oracle for the frozen credit design, not runtime.

Only stdlib arithmetic is used. No production modules, SQL, service, clocks,
borrow executor, native guard, or receipt store is invoked. Input snapshots are
rebuilt from assumptions and requests; fixture expected values are read only
after the independent calculations, for field-by-field comparison.
"""

import argparse
from collections import deque
from copy import deepcopy
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[1]
FROZEN_COMMIT = "7aa48202ddc4663a1e815609716c1a6b7110289f"
FROZEN_HASHES = {
    "docs/managed-credit-capability-design.md":
        "3a8e70a261d8d11291f9cb634955e3ea6931037d5c8c13d6e0269b756efbd7dd",
    "tests/fixtures/managed_credit_v1_golden.json":
        "494a6a88397f9677cdb82bb1bcedf9338a0441cd5df6cd5acfe2fd28209be260",
}


def f(value):
    if not isinstance(value, str) or not re.fullmatch(r"-?(0|[1-9][0-9]*)(\.[0-9]+)?", value):
        raise ValueError("reference financial input must be an ASCII decimal string")
    return Fraction(value)


def exact(value):
    """Decimal if terminating; explicit rational otherwise, with no rounding."""
    if not isinstance(value, Fraction):
        return value
    n, d = value.numerator, value.denominator
    twos = fives = 0
    while d % 2 == 0:
        twos += 1
        d //= 2
    while d % 5 == 0:
        fives += 1
        d //= 5
    if d != 1:
        return str(value)
    places = max(twos, fives)
    scaled = abs(n) * 2 ** (places - twos) * 5 ** (places - fives)
    if not places:
        return str(n)
    digits = str(scaled).zfill(places + 1)
    result = ("-" if n < 0 else "") + digits[:-places] + "." + digits[-places:]
    return result.rstrip("0").rstrip(".")


def serial(value):
    if isinstance(value, dict):
        return {k: serial(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [serial(v) for v in value]
    return exact(value)


def units(quantity, scale):
    result = quantity * 10 ** scale
    if result.denominator != 1:
        raise ValueError("amount does not fit asset minor units")
    return result.numerator


def floor_step(quantity, step):
    return max(Fraction(0), quantity // step * step)


class Reference:
    def __init__(self, assumptions):
        self.a = assumptions
        self.price = f(assumptions["prices"]["BTC"])
        self.step = f(assumptions["borrow_quantity_step_BTC"])
        self.im = f(assumptions["borrow_initial_margin_rate_BTC"])
        self.mm = f(assumptions["borrow_maintenance_margin_rate_BTC"])
        self.allocations = {k: f(v) for k, v in assumptions["shard_allocations_BTC"].items()}
        self.global_budget = f(assumptions["global_budget_BTC"])
        if any(v < 0 for v in self.allocations.values()) or sum(self.allocations.values()) > self.global_budget:
            raise ValueError("invalid static allocation certificate")
        if self.im < self.mm or self.mm < 0 or self.step <= 0 or self.price <= 0:
            raise ValueError("unsupported reference risk parameters")
        if f(assumptions["fee_rate"]) or f(assumptions["interest_rate"]):
            raise ValueError("this reference only models zero new interest and fees")

    def baseline(self):
        a = self.a
        principal = f(a["baseline_customer_principal"]["BTC"])
        interest = f(a["baseline_customer_interest"]["BTC"])
        return {
            "customer_USD": f(a["baseline_customer_cash"]["USD"]),
            "customer_BTC": f(a["baseline_customer_cash"]["BTC"]),
            "principal_BTC": principal,
            "interest_BTC": interest,
            "pool_BTC": f(a["baseline_shard_pool_cash_BTC"]),
            "principal_receivable_BTC": principal,
            "interest_receivable_BTC": interest,
            "interest_cash_BTC": Fraction(0),
            "shard_used_BTC": principal + interest,
            "order_reserve_USD": Fraction(0),
        }

    def risk(self, state):
        a, p = self.a, self.price
        debt = (state["principal_BTC"] + state["interest_BTC"]) * p
        gross = state["customer_USD"] + state["customer_BTC"] * p
        usd_collateral = state["customer_USD"] * f(a["collateral_factor"]["USD"])
        btc_collateral = state["customer_BTC"] * p * f(a["collateral_factor"]["BTC"])
        collateral = usd_collateral + btc_collateral
        loan = (usd_collateral * f(a["loan_to_value"]["USD"])
                + btc_collateral * f(a["loan_to_value"]["BTC"]))
        equity = collateral - debt
        im, mm = debt * self.im, debt * self.mm
        available = equity - im - state["order_reserve_USD"]
        bounds = {
            "account_principal_BTC": f(a["account_principal_limit_BTC"]) - state["principal_BTC"],
            "account_total_debt_BTC": (f(a["account_total_debt_limit_USD"]) - debt) / p,
            "loan_to_value_BTC": (loan - debt) / p,
            "conservative_available_margin_BTC": available / (p * (1 + self.im)),
        }
        quote = floor_step(min(bounds.values()), self.step)
        # Strict MM uses the conservative assumption that proceeds leave assets.
        if equity - quote * p <= mm + quote * p * self.mm:
            strict_bound_steps = (equity - mm) / (p * (1 + self.mm) * self.step)
            ceiling = -(-strict_bound_steps.numerator // strict_bound_steps.denominator)
            quote = max(Fraction(0), min(quote, (ceiling - 1) * self.step))
        shard_headroom = self.allocations["0"] - state["shard_used_BTC"]
        local_headroom = f(a["local_credit_asset_limit_BTC"]) - state["shard_used_BTC"]
        authorized = floor_step(min(quote, state["pool_BTC"], shard_headroom, local_headroom), self.step)
        return {
            "gross_asset_value_USD": gross,
            "accounting_equity_USD": gross - debt,
            "collateral_value_USD": collateral,
            "loan_value_USD": loan,
            "debt_value_USD": debt,
            "risk_equity_USD": equity,
            "initial_margin_USD": im,
            "maintenance_margin_USD": mm,
            "order_reserve_USD": state["order_reserve_USD"],
            "available_margin_USD": available,
            "portfolio_quote_bounds_BTC": bounds,
            "portfolio_quote_BTC": quote,
            "shard_budget_headroom_BTC": shard_headroom,
            "local_asset_headroom_BTC": local_headroom,
            "authorized_quote_BTC": authorized,
        }

    def borrow_predicates(self, state, amount):
        units(amount, self.a["currency_scale"]["BTC"])
        r = self.risk(state)
        return {
            "positive_amount": amount > 0,
            "quantity_step": (amount / self.step).denominator == 1,
            "portfolio_quote": amount <= r["portfolio_quote_BTC"],
            "shard_budget": state["shard_used_BTC"] + amount <= self.allocations["0"],
            "local_asset_limit": state["shard_used_BTC"] + amount <= f(self.a["local_credit_asset_limit_BTC"]),
            "pool_cash": amount <= state["pool_BTC"],
        }

    def borrow(self, state, amount):
        if not all(self.borrow_predicates(state, amount).values()):
            raise ValueError("reference borrow is ineligible")
        result = deepcopy(state)
        for key in ("customer_BTC", "principal_BTC", "principal_receivable_BTC", "shard_used_BTC"):
            result[key] += amount
        result["pool_BTC"] -= amount
        return result

    def repay(self, state, amount):
        if amount < 0 or amount > state["customer_BTC"] or amount > state["principal_BTC"] + state["interest_BTC"]:
            raise ValueError("reference repayment exceeds cash or debt")
        units(amount, self.a["currency_scale"]["BTC"])
        interest_paid = min(amount, state["interest_BTC"])
        principal_paid = amount - interest_paid
        result = deepcopy(state)
        result["customer_BTC"] -= amount
        result["interest_BTC"] -= interest_paid
        result["interest_receivable_BTC"] -= interest_paid
        result["interest_cash_BTC"] += interest_paid
        result["principal_BTC"] -= principal_paid
        result["principal_receivable_BTC"] -= principal_paid
        result["pool_BTC"] += principal_paid
        result["shard_used_BTC"] -= amount
        return result, interest_paid, principal_paid

    def snapshot(self, state):
        return {"state": deepcopy(state), "risk": self.risk(state)}


def tiny_budget_graph():
    """36-state truth graph, intentionally no database/native/FIFO model."""
    allocations, budget = (2, 2), 4
    start = ((0, 0), (False, False))
    queue, seen, edges = deque([start]), {start}, 0
    while queue:
        debts, unknown = queue.popleft()
        assert all(0 <= d <= a for d, a in zip(debts, allocations))
        assert sum(debts) <= budget
        for shard in range(2):
            for operation in ("borrow", "repay"):
                for amount in range(3):
                    changed = debts[shard] + (amount if operation == "borrow" else -amount)
                    if not 0 <= changed <= allocations[shard]:
                        continue
                    for committed in (False, True):
                        for reply_unknown in (False, True):
                            after_debts, after_unknown = list(debts), list(unknown)
                            if committed:
                                after_debts[shard] = changed
                            after_unknown[shard] = reply_unknown
                            target = (tuple(after_debts), tuple(after_unknown))
                            edges += 1
                            if target not in seen:
                                seen.add(target)
                                queue.append(target)
    return {
        "unit": "abstract integer asset minor units; not BTC .01 quantity steps",
        "allocations": list(allocations), "global_budget": budget,
        "assumptions": [
            "fixed, complete, identity-bound, nonnegative allocations whose sum is <= global budget",
            "opening principal+interest debt fits each allocation; no new interest, adjustment, transfer, or outside writer",
            "each local committed borrow checks actual staged gross debt; committed repay reduces actual debt",
            "UNKNOWN changes observation only, never actual debt or an allocation; rollback changes no debt",
            "zero amount is a budget-model no-op, not permission for a zero-amount production request",
        ],
        "reachable_states": len(seen), "transitions": edges,
        "all_truth_states_within_local_and_global_caps": True,
        "truth_debt_pairs": sorted({debts for debts, _ in seen}),
        "unsafe_reclamation_counterexample": [
            {"action": "both shards commit 2; shard0 reply is UNKNOWN", "actual_debts": [2, 2], "allocations": [2, 2], "actual_global_debt": 4},
            {"action": "UNSAFE: discard shard0 unknown obligation and move its allocation", "actual_debts": [2, 2], "allocations": [0, 4], "actual_global_debt": 4},
            {"action": "UNSAFE: shard1 commits 2 more using enlarged local allocation", "actual_debts": [2, 4], "allocations": [0, 4], "actual_global_debt": 6, "exceeds_global_by": 2},
        ],
        "unsafe_model_dropped_required_check": "actual shard0 debt 2 no longer fits its purported allocation 0; retaining that check rejects reclamation",
        "scope": "principal+interest in one original asset only; no cash deficits, native guards, transactions, scheduler, HA or real funding proof",
    }


def build_report(fixture):
    ref = Reference(fixture["assumptions"])
    cases = {case["id"]: case for case in fixture["cases"]}
    calculations, comparisons = {}, []

    def compare(case_id, path, computed, conditional=False):
        value = cases[case_id]
        for key in path.split("."):
            value = value[int(key)] if isinstance(value, list) else value[key]
        equal = f(value) == computed if isinstance(computed, Fraction) else value == computed
        comparisons.append({"case": case_id, "field": path, "fixture": value,
                            "computed": computed, "matches": equal,
                            "kind": "conditional_arithmetic" if conditional else "arithmetic"})

    base = ref.baseline()
    # Each starting_after is a fresh independent branch of this snapshot.
    c1 = "CREDIT-MANUAL-001"
    q1 = f(cases[c1]["request"]["amount"])
    one = ref.borrow(base, q1)
    r1 = ref.risk(one)
    calculations[c1] = {"before": ref.snapshot(base), "request_BTC": q1, "after": ref.snapshot(one),
                        "predicates": ref.borrow_predicates(base, q1),
                        "reference_BTC_postings": {"customer_cash": q1, "pool_cash": -q1,
                                                   "principal_receivable": q1, "principal_liability": -q1},
                        "posting_sum_BTC": q1 - q1 + q1 - q1}
    mapping1 = {
        "borrow_units": str(units(q1, fixture["assumptions"]["currency_scale"]["BTC"])),
        "cash.USD": one["customer_USD"], "cash.BTC": one["customer_BTC"],
        "principal_BTC": one["principal_BTC"], "interest_BTC": one["interest_BTC"],
        "pool_cash_BTC": one["pool_BTC"], "principal_receivable_BTC": one["principal_receivable_BTC"],
        "principal_liability_ledger_BTC": -one["principal_BTC"],
        **{key: r1[key] for key in ("accounting_equity_USD", "collateral_value_USD", "loan_value_USD", "debt_value_USD", "risk_equity_USD", "initial_margin_USD", "maintenance_margin_USD", "available_margin_USD", "shard_budget_headroom_BTC")},
        "new_order_margin_USD": one["order_reserve_USD"],
        "next_portfolio_quote_BTC": r1["portfolio_quote_BTC"],
        "next_authorized_quote_including_budget_BTC": r1["authorized_quote_BTC"],
    }
    for key, value in mapping1.items():
        compare(c1, "expected." + key, value)

    c2 = "CREDIT-MANUAL-002"
    q2 = f(cases[c2]["request"]["amount"])
    p2 = ref.borrow_predicates(deepcopy(one), q2)
    calculations[c2] = {"before_and_after_if_rejected": ref.snapshot(one), "request_BTC": q2,
                        "predicates": p2, "attempted_shard_debt_BTC": one["shard_used_BTC"] + q2,
                        "mathematical_rejection": not p2["shard_budget"]}

    c3 = "CREDIT-MANUAL-003"
    q3 = f(cases[c3]["request"]["amount"])
    three = ref.borrow(deepcopy(one), q3)
    r3 = ref.risk(three)
    calculations[c3] = {"before": ref.snapshot(one), "request_BTC": q3, "after": ref.snapshot(three)}
    for key, value in {"principal_BTC": three["principal_BTC"], "cash_BTC": three["customer_BTC"], "pool_cash_BTC": three["pool_BTC"],
                       **{key: r3[key] for key in ("risk_equity_USD", "initial_margin_USD", "maintenance_margin_USD", "available_margin_USD", "shard_budget_headroom_BTC")}}.items():
        compare(c3, "expected." + key, value)

    c4 = "CREDIT-MANUAL-004"
    extra = cases[c4]["extra_state"]
    reserve = abs(f(extra["linear_limit_order_quantity"])) * f(extra["linear_mark_and_limit"]) * 1 * f(fixture["assumptions"]["linear_initial_margin_rate"])
    four = deepcopy(one)
    four["order_reserve_USD"] = reserve
    r4 = ref.risk(four)
    compare(c4, "extra_state.reserved_margin_USD", reserve, True)
    compare(c4, "expected.available_margin_USD", r4["available_margin_USD"], True)
    compare(c4, "expected.next_conservative_borrow_quote_BTC", r4["portfolio_quote_BTC"], True)
    request4a, request4b = cases[c4]["requests"]
    q4a, q4b = f(request4a["amount_BTC"]), f(request4b["amount_BTC"])
    four_after = ref.borrow(four, q4b)
    r4after = ref.risk(four_after)
    calculations[c4] = {"before": ref.snapshot(four), "computed_order_reserve_USD": reserve,
                        "implicit_multiplier": "1; instrument/symbol/side/product status/tick/min-notional are not supplied",
                        "request_0_predicates": ref.borrow_predicates(four, q4a),
                        "request_1_predicates": ref.borrow_predicates(four, q4b),
                        "after_request_1": ref.snapshot(four_after),
                        "pre_step_margin_bound_BTC": r4["portfolio_quote_bounds_BTC"]["conservative_available_margin_BTC"]}
    for key, value in {"post_principal_BTC": four_after["principal_BTC"], "post_risk_equity_USD": r4after["risk_equity_USD"],
                       "post_IM_USD": r4after["initial_margin_USD"], "post_available_margin_USD": r4after["available_margin_USD"]}.items():
        compare(c4, "requests.1." + key, value, True)

    c5 = "CREDIT-MANUAL-005"
    # These amounts come from scenario prose, never from its expected object.
    q5first, q5second = f("0.3"), f("0.3")
    first = ref.borrow(ref.baseline(), q5first)
    second = ref.baseline()
    second["pool_BTC"], second["shard_used_BTC"] = first["pool_BTC"], first["shard_used_BTC"]
    second["principal_receivable_BTC"] = first["principal_receivable_BTC"]
    maximum5 = ref.risk(second)["authorized_quote_BTC"]
    calculations[c5] = {"normalized_inputs_not_machine_supplied": {
        "accounts": "two distinct accounts, each USD100, no BTC/debt/interest/freeze/positions/orders",
        "shard": 0, "opening_shard_debt_BTC": "0", "opening_pool_BTC": "1", "requests_BTC": ["0.3", "0.3"]},
        "first_after": ref.snapshot(first), "second_before": ref.snapshot(second),
        "second_request_predicates": ref.borrow_predicates(second, q5second),
        "alternative_second_after": ref.snapshot(ref.borrow(second, maximum5))}
    for key, value in {"first_loan_BTC": q5first, "second_request_BTC": q5second, "shard_used_BTC": first["shard_used_BTC"],
                       "pool_cash_BTC": first["pool_BTC"], "alternative_second_maximum_BTC": maximum5}.items():
        compare(c5, "expected." + key, value, True)

    c6 = "CREDIT-MANUAL-006"
    used6, request6 = {"0": f("0.5"), "1": f("0")}, f(cases[c6]["request"]["amount_BTC"])
    calculations[c6] = {"normalized_prose_gross_debt_BTC": used6,
                        "allocation_sum_BTC": sum(ref.allocations.values()), "global_budget_BTC": ref.global_budget,
                        "current_global_gross_debt_BTC": sum(used6.values()),
                        "hypothetical_after_global_gross_debt_BTC": sum(used6.values()) + request6,
                        "local_shard0_headroom_BTC": ref.allocations["0"] - used6["0"],
                        "local_budget_predicate": used6["0"] + request6 <= ref.allocations["0"],
                        "other_gates": "not evaluable: customer, principal/interest split, pool, receipts and risk state are absent"}

    c7 = "CREDIT-MANUAL-007"
    q7 = f(cases[c7]["request"]["repay_BTC"])
    seven, i7, p7 = ref.repay(deepcopy(one), q7)
    calculations[c7] = {"before": ref.snapshot(one), "repay_BTC": q7, "after": ref.snapshot(seven),
                        "repay_arithmetic_market_reads": 0,
                        "risk_values_note": "reference valuation at fixed fixture price; repayment arithmetic does not call risk or need a live price"}
    for key, value in {"principal_BTC": seven["principal_BTC"], "customer_cash_BTC": seven["customer_BTC"],
                       "pool_cash_BTC": seven["pool_BTC"], "interest_repaid_BTC": i7, "principal_repaid_BTC": p7}.items():
        compare(c7, "expected." + key, value)

    c8 = "CREDIT-MANUAL-008"
    calculations[c8] = {"arithmetic_status": "NOT_COMPUTABLE_FROM_CASE_INPUT",
                        "missing_inputs": ["initial account/shard/pool snapshot", "attempted asset/amount", "exact failure stage", "actual persisted tuple and transaction status"],
                        "native_status": "NOT_EXECUTED: every expected boolean requires actual native/COMMIT/rollback/reopen evidence"}

    c9 = "CREDIT-MANUAL-009"
    calculations[c9] = {"conditional_original_commit_truth": ref.snapshot(one),
                        "reference_retry": "identity operation only if original canonical CID is proven committed; no executor was called",
                        "unknown_query_branch": "NO RESULT / BLOCK DEPENDENT ACTIONS; do not assume zero debt or allocate a new CID",
                        "rollback_branch": "cannot reuse committed snapshot; confirm authoritative PENDING before a new transaction on original CID"}
    compare(c9, "expected.additional_loan_count", 0, True)
    compare(c9, "expected.principal_BTC", one["principal_BTC"], True)
    compare(c9, "expected.pool_cash_BTC", one["pool_BTC"], True)

    c10 = "CREDIT-MANUAL-010"
    q10 = f(cases[c10]["request"]["amount"])
    calculations[c10] = {"request_BTC": q10, "request_minor_units": units(q10, fixture["assumptions"]["currency_scale"]["BTC"]),
                         "step_minor_units": units(ref.step, fixture["assumptions"]["currency_scale"]["BTC"]),
                         "predicates": ref.borrow_predicates(ref.baseline(), q10),
                         "reference_policy": "reject without changing amount; actual no-effect guarantee is unexecuted"}

    # Extra input supplied to reviewer without expected values; not an edit of the frozen ten cases.
    opening = ref.baseline()
    opening.update({"customer_BTC": f("0.5"), "principal_BTC": f("0.4"), "interest_BTC": f("0.05"),
                    "pool_BTC": f("0.6"), "principal_receivable_BTC": f("0.4"),
                    "interest_receivable_BTC": f("0.05"), "shard_used_BTC": f("0.45")})
    repaid, interest_paid, principal_paid = ref.repay(opening, f("0.1"))
    repayment_postings = {
        "customer_cash": f("-0.1"), "principal_liability": principal_paid, "interest_liability": interest_paid,
        "principal_receivable": -principal_paid, "interest_receivable": -interest_paid,
        "pool_cash": principal_paid, "interest_cash": interest_paid,
    }
    historical_interest = {"id": "REVIEW-OPENING-INTEREST-001", "input_provenance": "review task supplied complete new numeric input without expected values",
                           "before": ref.snapshot(opening), "repay_BTC": f("0.1"),
                           "interest_repaid_BTC": interest_paid, "principal_repaid_BTC": principal_paid,
                           "after": ref.snapshot(repaid), "reference_BTC_postings": repayment_postings,
                           "posting_sum_BTC": sum(repayment_postings.values()),
                           "allocation_headroom_release_BTC": opening["shard_used_BTC"] - repaid["shard_used_BTC"],
                           "pool_cash_increase_BTC": repaid["pool_BTC"] - opening["pool_BTC"],
                           "interest_cash_increase_BTC": repaid["interest_cash_BTC"] - opening["interest_cash_BTC"],
                           "opening_source_note": "USD100/BTC.5 with debt .45 is an externally supplied opening snapshot; not reconstructed as a fresh .4 loan from the ten-case baseline"}

    # Enumerate every expected leaf, so runtime and narrative fields cannot disappear from coverage.
    covered = {(c["case"], c["field"]) for c in comparisons}
    unverified = []
    def leaves(value, prefix):
        if isinstance(value, dict):
            for key, child in value.items():
                yield from leaves(child, prefix + "." + key)
        else:
            yield prefix, value
    for case_id, case in cases.items():
        for path, value in leaves(case["expected"], "expected"):
            if (case_id, path) not in covered:
                unverified.append({"case": case_id, "field": path, "fixture": value,
                                   "status": "NOT_EXECUTED_RUNTIME_OR_POLICY_LABEL",
                                   "note": "arithmetic predicates may support eligibility/rejection; no native effect, API reason string, source or receipt behavior was tested"})
        if "requests" in case:
            for i, request in enumerate(case["requests"]):
                for path, value in leaves(request, "requests." + str(i)):
                    if not path.endswith("amount_BTC") and (case_id, path) not in covered:
                        unverified.append({"case": case_id, "field": path, "fixture": value,
                                           "status": "NOT_EXECUTED_RUNTIME_OR_POLICY_LABEL"})
    return serial({
        "review_format": 1, "frozen_commit": FROZEN_COMMIT,
        "status": "INDEPENDENT_ARITHMETIC_ONLY_RUNTIME_NOT_EXECUTED_NO_GO",
        "production_approved": False,
        "scope": "synthetic original-asset principal+interest budgets; no cash-deficit cap, external funding confirmation or production/native proof",
        "explicit_reference_assumptions": [
            "all starting_after references branch independently from a freshly recalculated case001, never cumulative file order",
            "default shard0; complete immutable two-shard allocation certificate .5+.5<=1; no additional local debt",
            "zero frozen assets, deficits, unrealized PnL, positions and fees unless explicitly introduced",
            "flat collateral factors, USD reporting/settlement, linear contract multiplier1 for case004",
            "pool and matching opening receivable amounts are assumed reconciled; funding-source ownership is not supplied",
            "case005 prose is normalized explicitly; case006 validates budget predicate only; case008 has no numeric oracle",
            "reason strings/outcomes are design labels, not an implemented API contract",
        ],
        "allocation_certificate": {"allocations_BTC": ref.allocations, "sum_BTC": sum(ref.allocations.values()),
                                   "global_budget_BTC": ref.global_budget, "sum_le_global": sum(ref.allocations.values()) <= ref.global_budget},
        "cases": calculations, "numeric_field_comparisons": comparisons,
        "numeric_fields_compared": len(comparisons), "numeric_mismatches": sum(not c["matches"] for c in comparisons),
        "unexecuted_expected_fields": unverified,
        "supplemental_opening_interest_repayment": historical_interest,
        "tiny_static_budget_graph": tiny_budget_graph(),
    })


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    hashes = {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest() for path in FROZEN_HASHES}
    if hashes != FROZEN_HASHES:
        raise SystemExit("frozen source bytes changed; stop this review")
    fixture = json.loads((ROOT / "tests/fixtures/managed_credit_v1_golden.json").read_text())
    report = build_report(fixture)
    report["source_sha256"] = {
        **hashes,
        "docs/margin-rules.md": hashlib.sha256((ROOT / "docs/margin-rules.md").read_bytes()).hexdigest(),
        "scripts/review_credit_golden_finance.py": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    }
    payload = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload)
    else:
        sys.stdout.write(payload)
    print(f"ARITHMETIC ONLY: cases={len(report['cases'])}; numeric_fields={report['numeric_fields_compared']}; "
          f"mismatches={report['numeric_mismatches']}; budget_states={report['tiny_static_budget_graph']['reachable_states']}; "
          "NATIVE/PRODUCTION NOT EXECUTED; NO-GO", file=sys.stderr)
    return bool(report["numeric_mismatches"])


if __name__ == "__main__":
    raise SystemExit(main())
