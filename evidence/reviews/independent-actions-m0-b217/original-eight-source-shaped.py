"""Independent synthetic parser controls only; no native/SQL/profile/workload.

Only immutable Git blobs are read before patching all process entry points.
The production financial modules, benchmark and author test module are never
imported or executed. The author's literal shape fixture is extracted by AST;
mutations and recomputed population checks are independent review code.
"""
import ast
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
import gzip
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import time
from types import ModuleType
from unittest.mock import patch

CONTROL = "b2175525fa90595c530999f44140e9411421528d"
REPO = Path(__file__).resolve().parents[3]


def main():
    started = datetime.now(timezone.utc).isoformat()
    began = time.monotonic_ns()
    controller = subprocess.check_output(["git", "show", CONTROL + ":tools/independent_m0_controller.py"], cwd=REPO)
    tests = subprocess.check_output(["git", "show", "e44493f67846adbdee0ff1064743cd1444c5cb4e:tests/test_independent_m0_controller.py"], cwd=REPO)
    assert sha256(controller).hexdigest() == "df7e8d3dfc9d22a65b197eda5cf1a0469c7e231eb1ee5ab02b03dca2869723db"
    author_tree = ast.parse(tests)
    fixture = next(node for cls in author_tree.body if isinstance(cls, ast.ClassDef)
                   for node in cls.body if isinstance(node, ast.FunctionDef) and node.name == "summary")
    fixture_module = ast.Module(body=[fixture], type_ignores=[])
    module = ModuleType("immutable_m0_controller_for_pure_review")
    module.__file__ = "/synthetic/review/control/tools/independent_m0_controller.py"
    forbidden = []

    def prohibit(*args, **kwargs):
        forbidden.append("process-entry-called")
        raise AssertionError("native/SQL/workload entry is prohibited in pure review")

    checks = []
    with patch.object(subprocess, "Popen", prohibit), patch.object(subprocess, "run", prohibit), \
            patch.object(subprocess, "check_output", prohibit), patch.object(subprocess, "call", prohibit):
        exec(compile(controller, module.__file__, "exec"), module.__dict__)
        scope = {"m": module}
        exec(compile(fixture_module, "immutable-author-literal-shape-only", "exec"), scope)
        baseline = scope["summary"](None)
        baseline["latency_ms"]["enqueue_ack"] = {key: .003 for key in ("p50", "p95", "p99", "p99_9")}
        assert module.project_summary(deepcopy(baseline), False)["counts"]["financial_succeeded"] == 160
        checks.append({"case": "coherent_summary_positive", "expected": "ACCEPT", "observed": "ACCEPT", "red": False})

        def summary_negative(name, mutate, explanation):
            candidate = deepcopy(baseline)
            mutate(candidate)
            try:
                projected = module.project_summary(candidate, False)
                checks.append({"case": name, "expected": "REJECT", "observed": "ACCEPT", "red": True,
                               "explanation": explanation, "accepted_projection": projected})
            except module.GateError as error:
                checks.append({"case": name, "expected": "REJECT", "observed": "REJECT", "red": False,
                               "error_code": str(error)})

        summary_negative("outcomes_vs_counts_disagree",
                         lambda s: s["outcome_counts"].update(financial_succeeded=159, control_or_market_rejected=21),
                         "outcomes says159 financial while counts and persistent reopen say160; each partitions200")
        summary_negative("negative_elapsed_seconds",
                         lambda s: s.update(duration_including_terminal_observation_drain=-1),
                         "elapsed is negative although fixed planned duration is10 seconds")
        summary_negative("throughput_not_count_over_elapsed",
                         lambda s: s.update(unique_observed_financial_success_per_s=9999),
                         "160 confirmed admissions /10 seconds is16 per second, not9999")
        summary_negative("impossible_latency_quantile_order",
                         lambda s: s["latency_ms"]["all"].update(p50=100, p95=1),
                         "P50 cannot exceed P95 within one population")

        rows = []
        for sequence in range(200):
            planned = 1_000_000_000 + sequence * 50_000_000
            outcome = ("business_rejected" if sequence % 10 == 0 else
                       "control_or_market_rejected" if sequence % 10 == 1 else "financial_succeeded")
            rows.append({"sequence": sequence, "command_id": "bench:" + str(sequence),
                         "order_id": "order:" + str(sequence), "outcome": outcome,
                         "planned_ns": planned, "offered_ns": planned + 1000,
                         "enqueue_started_ns": planned + 2000, "enqueue_ack_ns": planned + 3000,
                         "enqueue_call_finished_ns": planned + 4000,
                         "observed_completion_ns": planned + 1_000_000, "latency_ns": 1_000_000,
                         "deadline_exceeded": False, "intended_product_rejection": sequence % 10 == 0,
                         "receipt": {"command_id": "bench:" + str(sequence), "attempts": 0,
                                     "state": "SUCCEEDED" if outcome == "financial_succeeded" else "REJECTED",
                                     "last_error": None, "error": None if outcome == "financial_succeeded" else {"code": "synthetic-only", "message": "synthetic source-shaped receipt", "status": 400 if outcome == "business_rejected" else 503}}})
        assert Counter(r["outcome"] for r in rows) == Counter(baseline["outcome_counts"])
        with TemporaryDirectory(prefix="m0-pure-parser-review-") as directory:
            path = Path(directory) / "synthetic-arrivals.jsonl.gz"

            def parsed(candidate):
                path.write_bytes(gzip.compress(b"".join((json.dumps(row) + "\n").encode() for row in candidate), mtime=0))
                return module.project_arrivals(path)

            assert len(parsed(rows)) == 200
            checks.append({"case": "coherent200_population_positive", "expected": "ACCEPT", "observed": "ACCEPT", "red": False})

            def arrivals_negative(name, mutate, explanation):
                candidate = deepcopy(rows)
                mutate(candidate)
                try:
                    projection = parsed(candidate)
                    checks.append({"case": name, "expected": "REJECT", "observed": "ACCEPT", "red": True,
                                   "explanation": explanation, "accepted_row2": projection[2],
                                   "actual_outcome_population": dict(Counter(r["outcome"] for r in projection))})
                except module.GateError as error:
                    checks.append({"case": name, "expected": "REJECT", "observed": "REJECT", "red": False,
                                   "error_code": str(error)})

            arrivals_negative("receipt_wrong_original_command_id",
                              lambda r: r[2]["receipt"].update(command_id="bench:199"),
                              "financial success for bench:2 carries receipt for bench:199")
            arrivals_negative("financial_success_with_rejected_receipt",
                              lambda r: r[2]["receipt"].update(state="REJECTED"),
                              "financial_succeeded row has only a REJECTED receipt")
            arrivals_negative("latency_not_completion_minus_planned",
                              lambda r: r[2].update(latency_ns=1, enqueue_ack_ns=r[2]["planned_ns"] - 1),
                              "claimed latency1ns differs from actual timestamp delta1ms and ACK predates start")
            candidate = deepcopy(rows)
            candidate[199]["outcome"] = "business_rejected"
            candidate[199]["receipt"]["state"] = "REJECTED"
            candidate[199]["receipt"]["error"] = {"code": "synthetic-only", "message": "synthetic source-shaped receipt", "status": 400}
            projected_rows = parsed(candidate)
            projected_summary = module.project_summary(deepcopy(baseline), False)
            histogram = dict(Counter(row["outcome"] for row in projected_rows))
            assert histogram != projected_summary["outcome_counts"]
            try:
                module.verify_population(projected_summary, projected_rows)
                checks.append({"case": "summary_and200_rows_population_disagree", "expected": "REJECT", "observed": "ACCEPT",
                               "red": True, "summary_counts": projected_summary["outcome_counts"], "actual_rows_counts": histogram})
            except module.GateError as error:
                checks.append({"case": "summary_and200_rows_population_disagree", "expected": "REJECT", "observed": "REJECT",
                               "red": False, "summary_counts": projected_summary["outcome_counts"], "actual_rows_counts": histogram,
                               "error_code": str(error), "adapter": "call new actual cross-file join; original200 row mutation unchanged"})
        assert not forbidden
        assert not any(name == "uta" or name.startswith("uta.") or name == "sqlite3" for name in sys.modules)
    result = {"control_commit": CONTROL, "controller_sha256": sha256(controller).hexdigest(),
              "started_at_utc": started, "finished_at_utc": datetime.now(timezone.utc).isoformat(),
              "elapsed_monotonic_ns": time.monotonic_ns() - began,
              "cases": checks, "red_count": sum(row["red"] for row in checks),
              "process_entry_calls": forbidden, "actual_SQL_native_profile_workload_Actions": False,
              "production_approved": False, "execution_authorized": False}
    print(json.dumps(result, indent=2, sort_keys=True))
    return 1 if result["red_count"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
