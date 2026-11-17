#!/usr/bin/env python3
"""Small read-only check of 83d595f design JSON; no production or SQL imports."""

import argparse
import csv
from datetime import datetime
from fractions import Fraction as F
import hashlib
import io
import json
from pathlib import Path
import subprocess


SOURCE_COMMIT = "83d595f4eef4eb92203dc0d988fc4e36c121b453"
SOURCE_HASHES = {
    "docs/managed-credit-capability-design.md": "3a8e70a261d8d11291f9cb634955e3ea6931037d5c8c13d6e0269b756efbd7dd",
    "tests/fixtures/managed_credit_v1_golden.json": "494a6a88397f9677cdb82bb1bcedf9338a0441cd5df6cd5acfe2fd28209be260",
    "docs/managed-credit-capability-review-v2.md": "03dfd40834f85fe807a58224ea196aa4333d5b08c6394d67bca834b5ce2e9f92",
    "docs/managed-credit-native-contract-v3.md": "bbf332fcefe7b690b7c811b70bb4be8eb9f01c1c21f1666b03426fbc9d533ff4",
    "tests/fixtures/managed_credit_v1_canonical_example.json": "3ffcfeae20081bb8f9753999790cc641138a1048c7f58e26d8fc407165d869ab",
    "evidence/rules-managed-credit-proposed-v1.csv": "e282890e38b42f7c65ef5f04cfb58975ab533feecd63208e76207ebd205b8cbf",
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path("/workspace/uta-managed-credit-capability"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    # The integration worktree may advance during review; read immutable blobs,
    # always with an explicit source cwd, rather than mixing mutable revisions.
    raw = {name: subprocess.run(["git", "show", f"{SOURCE_COMMIT}:{name}"],
                               cwd=args.source, capture_output=True, check=True).stdout
           for name in SOURCE_HASHES}
    hashes = {name: hashlib.sha256(value).hexdigest() for name, value in raw.items()}
    if hashes != SOURCE_HASHES:
        raise SystemExit("source file differs from immutable reviewed snapshot; stop")
    canonical = json.loads(raw["tests/fixtures/managed_credit_v1_canonical_example.json"])
    golden = json.loads(raw["tests/fixtures/managed_credit_v1_golden.json"])
    records = []

    def check(name, observed, expected):
        records.append({"check": name, "observed": observed, "expected": expected, "matches": observed == expected})

    documents = canonical["documents"]
    for name, document in documents.items():
        encoded = json.dumps(document["payload"], sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        check(name + ".canonical_payload", document["canonical_payload"], encoded)
        check(name + ".content_hash", document["id"].split(":", 1)[1], hashlib.sha256(encoded.encode()).hexdigest())
    request = canonical["request"]
    business = json.loads(request["canonical_business_payload"])
    check("business.canonical_payload", request["canonical_business_payload"], json.dumps(business, sort_keys=True, separators=(",", ":")))
    check("business.sha256", request["business_payload_sha256"], hashlib.sha256(request["canonical_business_payload"].encode()).hexdigest())
    check("business.account_matches_initial", business["account_id"], canonical["initial_state"]["account_id"])
    check("business.account_matches_source", business["account_id"], documents["source_template"]["payload"]["account_id"])

    layout, budget = documents["layout"]["payload"], documents["global_budget"]["payload"]
    check("budget.layout_reference", budget["layout_id"], documents["layout"]["id"])
    check("budget.credit_policy_reference", budget["credit_policy_id"], documents["credit_policy"]["id"])
    check("budget.asset_scale", budget["asset_scale"], layout["asset_scales"][budget["asset"]])
    check("budget.complete_shard_set", sorted(a["shard"] for a in budget["allocations"]), list(range(layout["shard_count"])))
    check("budget.unique_fixture_funding_references", len({a["funding_reference"] for a in budget["allocations"]}), layout["shard_count"])
    allocation_sum = sum(int(a["limit_units"]) for a in budget["allocations"])
    check("budget.allocation_sum_le_global", allocation_sum <= int(budget["global_limit_units"]), True)
    for allocation in budget["allocations"]:
        shard = allocation["shard"]
        check(f"budget.shard{shard}.authority", allocation["authority_id"], layout["authorities"][str(shard)])
        check(f"budget.shard{shard}.opening_gross_le_allocation", int(allocation["opening_principal_units"]) + int(allocation["opening_interest_units"]) <= int(allocation["limit_units"]), True)
        check(f"budget.shard{shard}.funding_is_synthetic", allocation["funding_proof_kind"], "SYNTHETIC_FIXTURE_NOT_EXTERNAL_CONFIRMATION")

    rules, market = documents["risk_rules"]["payload"], documents["market_snapshot"]["payload"]
    initial, policy = canonical["initial_state"], documents["credit_policy"]["payload"]
    product = documents["catalog"]["payload"]["products"]["BTC-PERP"]
    scale, quantity, price = layout["asset_scales"]["BTC"], F(business["amount"]), F(market["assets"]["BTC"]["price"])
    check("request.exact_minor_units", str(quantity * 10 ** scale), request["amount_units"])
    check("case001.empty_positions", initial["positions"], {})
    check("case001.empty_orders", initial["open_orders"], [])
    check("case001.empty_freezes", initial["frozen_assets"], {})
    cash_usd = F(initial["cash"]["USD"])
    cash_btc = F(initial["cash"]["BTC"]) + quantity
    principal = F(initial["principal"]["BTC"]) + quantity
    interest = F(initial["interest"]["BTC"])
    usd_factor = F(rules["collaterals"]["USD"]["tiers"][0]["factor"])
    btc_factor = F(rules["collaterals"]["BTC"]["tiers"][0]["factor"])
    collateral = cash_usd * usd_factor + cash_btc * price * btc_factor
    loan_value = cash_usd * usd_factor * F(rules["collaterals"]["USD"]["loan_to_value"]) + cash_btc * price * btc_factor * F(rules["collaterals"]["BTC"]["loan_to_value"])
    debt = (principal + interest) * price
    im_rate = F(rules["borrow_limits"]["BTC"]["initial_margin_rate"])
    mm_rate = F(rules["borrow_limits"]["BTC"]["maintenance_margin_rate"])
    equity, im, mm = collateral - debt, debt * im_rate, debt * mm_rate
    available = equity - im
    numeric = {"collateral_value_USD": collateral, "loan_value_USD": loan_value, "debt_value_USD": debt,
               "risk_equity_USD": equity, "initial_margin_USD": im, "maintenance_margin_USD": mm,
               "available_margin_USD": available, "accounting_equity_USD": cash_usd + cash_btc * price - debt}
    for key, value in numeric.items():
        check("case001." + key, str(value), str(F(golden["cases"][0]["expected"][key])))
    extra = golden["cases"][3]["extra_state"]
    reserve = F(extra["linear_limit_order_quantity"]) * F(product["multiplier"]) * F(extra["linear_mark_and_limit"]) * F(rules["linear_margin"][product["risk_tier"]]["initial_margin_rate"])
    step = F(rules["borrow_limits"]["BTC"]["quantity_step"])
    quote_bounds = [F(rules["borrow_limits"]["BTC"]["max_principal"]) - principal,
                    (F(rules["max_total_debt"]) - debt) / price, (loan_value - debt) / price,
                    (available - reserve) / (price * (1 + im_rate))]
    quote004 = max(F(0), min(quote_bounds) // step * step)
    check("case004.reserve_with_explicit_multiplier", str(reserve), str(F(extra["reserved_margin_USD"])))
    check("case004.available_margin", str(available - reserve), str(F(golden["cases"][3]["expected"]["available_margin_USD"])))
    check("case004.conservative_quote", str(quote004), str(F(golden["cases"][3]["expected"]["next_conservative_borrow_quote_BTC"])))
    check("product.status", product["status"], "active")
    check("product.quantity_step_matches_borrow", product["quantity_step"], rules["borrow_limits"]["BTC"]["quantity_step"])
    check("policy.zero_new_interest", policy["new_interest_rate"], "0")
    check("policy.zero_new_fee", policy["new_borrow_fee_rate"], "0")
    check("policy.cash_deficits_outside_quantity_budget", policy["cash_deficits_in_credit_quantity_budget"], False)
    check("policy.new_interest_disabled", policy["allow_new_interest_accrual"], False)
    check("policy.post_cap_funding_disabled", policy["allow_post_cap_pool_funding"], False)
    check("policy.batch_size", policy["batch_size_required"], 0)
    observed = datetime.fromisoformat(market["observed_at"])
    ages = {}
    for key in ("selected_at", "last_checked_at"):
        age = int((datetime.fromisoformat(canonical["decision_time_example"][key]) - observed).total_seconds())
        ages[key] = age
        check("design_time." + key + ".age_within_limit", 0 <= age <= canonical["decision_time_example"]["max_price_age_seconds"], True)
    check("design_time.physical_commit_is_null", canonical["decision_time_example"]["physical_commit_time"], None)
    check("design_time.not_actual_execution", canonical["decision_time_example"]["is_actual_execution"], False)
    for key in ("actual_source_manifest", "actual_loaded_engine_digest", "actual_python_sqlite_runtime"):
        check("artifact." + key + ".null_template", canonical["code_artifact_template"][key], None)
    check("artifact.reject_real_decision", canonical["code_artifact_template"]["qualification_status"], "NOT_IMPLEMENTED_MUST_REJECT_AS_REAL_DECISION")
    check("source.synthetic", documents["source_template"]["payload"]["kind"], "synthetic_fixture")
    check("source.not_authentication_receipt", documents["source_template"]["payload"]["not_a_real_authentication_receipt"], True)
    rows = list(csv.DictReader(io.StringIO(raw["evidence/rules-managed-credit-proposed-v1.csv"].decode())))
    check("proposed_rules.row_count", len(rows), 4)
    for row in rows:
        check("proposed_rules." + row["rule_id"] + ".not_effective", row["effective_from"], "NOT_EFFECTIVE_DESIGN_ONLY")
    result = {
        "status": "DESIGN_CLOSURE_AND_SMALL_JSON_ARITHMETIC_ONLY_NATIVE_NOT_EXECUTED_NO_GO",
        "source_commit": SOURCE_COMMIT, "source_root_read_only": str(args.source),
        "source_access": "read-only git show of immutable commit blobs with explicit cwd",
        "source_sha256": hashes,
        "checks": records, "check_count": len(records), "mismatches": sum(not r["matches"] for r in records),
        "design_time_ages_seconds": ages,
        "arithmetic_scope": "canonical case001 and case004 reserve/quote under explicit product metadata and original golden extra-state; no rerun of 36-state graph or production tests",
        "canonical_template_remaining_scope": [
            "case001 snapshot only; case004 quantity8 and limit100 still come from original golden JSON plus v2 prose, not a complete canonical live order row",
            "no separate persisted account-credit/local-asset-limit documents, complete journal/intent/decision/source receipts or actual code artifact",
            "unique synthetic funding references do not prove real funds or native source ownership",
            "source/hash checks do not establish that any native UDF or trigger is deployed",
        ],
        "manual_design_closure": {
            "prior_complete_tuple_late_gate_block": "CLOSED_AS_SPECIFICATION_ONLY: v3 lines73-87; native effect pending real tests",
            "prior_pending_missing_tuple_block": "CLOSED_AS_SPECIFICATION_ONLY: v3 lines93-105; native recovery pending real tests",
            "additional_confirmed_financial_formula_contradiction": "NONE_FOUND_IN_REVIEWED_ADDITIONS",
            "legacy_post_boundary": "v3 lines102-105 still explicitly leaves old credit receipt/no durable inbox POST behavior to define; prefer rejecting POST and retaining read-only receipt query until specified",
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    print(f"JSON/design only: documents={len(documents)}; checks={len(records)}; mismatches={result['mismatches']}; NATIVE NOT EXECUTED; NO-GO")
    return bool(result["mismatches"])


if __name__ == "__main__":
    raise SystemExit(main())
