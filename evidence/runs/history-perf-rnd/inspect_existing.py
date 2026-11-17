"""Read existing public JSON/text and source only; never import UTA or open SQL.

Reproduce with: python evidence/runs/history-perf-rnd/inspect_existing.py
Historical profiles remain measurements of their original source and workload.
"""
import ast
from hashlib import sha256
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
BASE = "c30457227e2bfc0a1e665ff67c9c148855ac624a"


def read(relative):
    material = ("evidence/runs/history-perf-rnd/original-storage.py.txt"
                if relative == "uta/storage.py" else relative)
    data = (ROOT / material).read_bytes()
    if relative == "uta/storage.py":
        assert sha256(data).hexdigest() == "9eee296159d0b0347feac3fd2f2b99b3216e8247e579e159e5adda8cbcb08a08"
    return data, {"path": relative, "bytes": len(data), "sha256": sha256(data).hexdigest(),
                  "material_path": material}


def main():
    paths = [
        "benchmarks/results/20261116-managed-inbox-profile/analysis.json",
        "benchmarks/results/20261116-managed-inbox-profile/raw/profiles/worker-0-pid-18157.txt",
        "benchmarks/results/20261116-managed-inbox-profile/raw/profiles/worker-1-pid-18158.txt",
        "benchmarks/results/20261117-recovery-scaling/250000/summary.json",
        "benchmarks/results/20261117-recovery-763-authorized/250k/analysis-independent.json",
        "docs/recovery-763-setup-attribution.md",
        "uta/storage.py", "uta/writer_fence.py", "uta/durable_process.py",
        "uta/durable_batches.py", "uta/decision_audit.py", "uta/supervisor.py",
    ]
    contents, identities = {}, []
    for path in paths:
        data, identity = read(path)
        contents[path] = data
        identities.append(identity)
    old_profile = json.loads(contents[paths[0]])
    old_250k = json.loads(contents[paths[3]])
    new_250k = json.loads(contents[paths[4]])
    source = contents["uta/storage.py"].decode()
    tree = ast.parse(source)
    ledger = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "DurableLedger")
    verify = next(node for node in ledger.body if isinstance(node, ast.FunctionDef) and node.name == "verify")
    event_loop = next(node for node in ast.walk(verify) if isinstance(node, ast.For)
                      and isinstance(node.iter, ast.Call) and isinstance(node.iter.func, ast.Name)
                      and node.iter.func.id == "enumerate")
    posting_sql = [node.value for node in ast.walk(event_loop) if isinstance(node, ast.Constant)
                   and isinstance(node.value, str) and "FROM ledger_postings" in node.value]
    assert posting_sql == ["SELECT ordinal, account, asset, units FROM ledger_postings WHERE sequence = ? ORDER BY ordinal"]
    extracted = ast.get_source_segment(source, verify).encode()
    result = {
        "format": 1, "source_base": BASE, "scope": "existing-data-and-static-source-only",
        "new_sql_or_profile_executed": False, "runtime_changed": False,
        "production_qualified": False, "independent_author_signoff": False,
        "inputs": identities,
        "historical_profile": {
            "source": old_profile["source_commit"],
            "workers": old_profile["independent_worker_profiles"],
            "parent_mixed_thread_profile_eligible_for_cpu_attribution": False,
            "cumulative_times_are_additive_cpu_percentages": False,
        },
        "old_250k": {
            "tool_source": old_250k["environment"]["code_commit"],
            "capacity_passed": old_250k["capacity_passed"],
            "financial_ready": old_250k["diagnostics"]["financial_ready"],
            "observed_generation": old_250k["diagnostics"]["workers"][0]["generation"],
            "interpretation": "owned replay crossed ordinary lease; not proof of permanent crashloop",
        },
        "later_250k": {key: new_250k[key] for key in (
            "driver_sha", "capacity_passed", "cause_boundary", "driver_summary_present",
            "first_independent_replay_completion", "full_final_independent_replay", "all_persisted_cids")},
        "current_ledger_verify": {
            "line": verify.lineno, "end_line": verify.end_lineno,
            "function_sha256": sha256(extracted).hexdigest(),
            "postings_sql_inside_event_loop": posting_sql,
            "postings_select_calls_for_valid_N_event_history": "N",
            "complexity": "complete O(N+P) application replay plus N indexed postings SELECT statements",
            "proposed_statement_count": "1 ordered postings SELECT; all N events and P postings retained",
            "measured_gain": None,
        },
    }
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
