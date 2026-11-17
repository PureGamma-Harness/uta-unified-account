"""Read archived 720 P1 profiles; do not execute or import financial runtime.

Only this repository's manifest-pinned marshal profiles are accepted. The
derived role counts are generator-resume estimates, not transaction logs.
No load, live database, worker, network request, or performance trial is run.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import pstats


ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "benchmarks/results/20261117-managed-corrected-7200097"
P1 = DATASET / "raw/P1"
SOURCE = "7200097ce9f92fa678907bee9a99933f60d65bc3"


def _digest(path):
    return sha256(path.read_bytes()).hexdigest()


def _key(stats, filename, function, line=None):
    found = [key for key in stats if key[0].endswith(filename) and key[2] == function
             and (line is None or key[1] == line)]
    if len(found) != 1:
        raise ValueError(f"archived function identity is ambiguous: {filename}:{function}")
    return found[0]


def _metric(stats, key):
    primitive, calls, own, cumulative, _ = stats[key]
    return {"function": list(key), "primitive_calls": primitive, "calls": calls,
            "self_profile_seconds": own, "cumulative_profile_seconds": cumulative}


def _callers(stats, key):
    output = []
    for caller, value in sorted(stats[key][4].items()):
        if not isinstance(value, tuple) or len(value) != 4:
            raise ValueError("unsupported archived caller-edge encoding")
        output.append({"caller": list(caller), "primitive_calls": value[0],
                       "calls": value[1], "self_profile_seconds": value[2],
                       "cumulative_profile_seconds": value[3]})
    return output


def _resumed_contexts(stats, name):
    matches = [key for key in stats if key[0].endswith("/uta/storage.py") and key[2] == name]
    if not matches:
        return {"generator_resumes": 0, "estimated_completed_contexts": 0}
    if len(matches) != 1:
        raise ValueError("multiple archived storage wrappers")
    calls = stats[matches[0]][1]
    if calls % 2:
        raise ValueError("generator resumes do not support the two-resume estimate")
    return {"generator_resumes": calls, "estimated_completed_contexts": calls // 2}


def _profile(name, manifest):
    relative = "profiles/" + name
    path = P1 / relative
    expected = manifest["files"][relative]
    if path.stat().st_size != expected["bytes"] or _digest(path) != expected["sha256"]:
        raise ValueError("profile bytes differ from the original P1 manifest")
    # pstats reads marshal data, not runtime source. Inputs are fixed above and
    # checked before loading, rather than accepting arbitrary profile paths.
    profile = pstats.Stats(str(path))
    stats = profile.stats
    anomalies = [{"function": list(key), "self_profile_seconds": value[2],
                  "cumulative_profile_seconds": value[3]}
                 for key, value in stats.items() if value[2] > value[3]]
    report = {"path": path.relative_to(ROOT).as_posix(), "sha256": _digest(path),
              "total_profile_self_seconds": profile.total_tt,
              "self_exceeds_cumulative": anomalies, "function_count": len(stats)}
    if not name.startswith("worker-"):
        report["use"] = "parent timing attribution excluded: mixed-thread clock anomalies"
        return report
    selectors = {
        "connection_open": ("/uta/storage.py", "_connect"),
        "transaction_scope": ("/uta/storage.py", "_role_transaction"),
        "guard_before_commit": ("/uta/writer_fence.py", "before_commit"),
        "guard_constructor": ("/uta/writer_fence.py", "__init__", 405),
        "data_guard_validation": ("/uta/writer_fence.py", "_verify_data_guards"),
        "control_schema_validation": ("/uta/writer_fence.py", "_verify_control_schema"),
        "risk": ("/uta/service.py", "_risk"),
        "admission": ("/uta/service.py", "_admit_order"),
        "supervision": ("/uta/service.py", "supervise_account"),
        "queue_processing": ("/uta/durable_commands.py", "process_one"),
        "json_serialization": ("/json/__init__.py", "dumps"),
        "json_deserialization": ("/json/__init__.py", "loads"),
    }
    metrics = {label: _metric(stats, _key(stats, *selector))
               for label, selector in selectors.items()}
    for label, namepart in (("sqlite_execute", "execute"), ("sqlite_commit", "commit"),
                            ("sqlite_close", "close")):
        key = _key(stats, "~", f"<method '{namepart}' of 'sqlite3.Connection' objects>")
        metrics[label] = {**_metric(stats, key), "callers": _callers(stats, key)}
    report["metrics"] = metrics
    roles = {"financial": _resumed_contexts(stats, "transaction"),
             "read": _resumed_contexts(stats, "read_transaction"),
             "control": _resumed_contexts(stats, "_fence_transaction"),
             "inbox": _resumed_contexts(stats, "inbox_transaction")}
    estimated = sum(value["estimated_completed_contexts"] for value in roles.values())
    report["role_context_count_estimates"] = roles
    report["role_estimate_assumption"] = (
        "720 storage wrappers each yield once; two generator resumes estimate a completed scope. "
        "Counts are checked against observed connects; they are not per-role timing traces.")
    if estimated != metrics["connection_open"]["calls"]:
        raise ValueError("role count estimate does not reconcile to recorded connection opens")
    report["role_estimate_reconciles_to_connect_count"] = True
    report["per_role_connect_close_seconds"] = None
    report["per_role_timing_gap"] = (
        "All role opens/closes have the same _role_transaction caller; cProfile does not preserve "
        "the role argument or individual invocations. No financial-only timing allocation is established.")
    execute_edges = metrics["sqlite_execute"]["callers"]
    report["connection_setup_sql"] = [edge for edge in execute_edges
        if edge["caller"][0].endswith("/uta/storage.py") and edge["caller"][2] == "_connect"]
    report["close_outside_transaction_scope"] = [edge for edge in metrics["sqlite_close"]["callers"]
        if edge["caller"][2] != "_role_transaction"]
    return report


def analyze():
    artifact = json.loads((DATASET / "artifact-manifest.json").read_text())
    if artifact["source_sha"] != SOURCE:
        raise ValueError("unexpected original source")
    manifest_path = P1 / "manifest.json"
    if _digest(manifest_path) != artifact["files"]["raw/P1/manifest.json"]["sha256"]:
        raise ValueError("original P1 manifest differs")
    manifest = json.loads(manifest_path.read_text())
    return {"kind": "read_only_existing_profile_attribution", "original_source": SOURCE,
            "analysis_script_sha256": _digest(Path(__file__)),
            "original_manifest_sha256": _digest(manifest_path),
            "new_workload_executed": False, "runtime_changed": False,
            "financial_session_approved": False, "production_approved": False,
            "performance_improvement_measured": False,
            "timing_policy": "self/cumulative include native waiting; nested cumulative values are never added as savings",
            "profiles": [_profile(name, manifest) for name in
                         ("worker-0-pid-57001.prof", "worker-1-pid-57002.prof", "dispatcher-0.prof")]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path, help="new derived JSON file")
    args = parser.parse_args()
    result = analyze()
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps({"original_source": SOURCE, "profiles": len(result["profiles"]),
                      "new_workload_executed": False, "financial_session_approved": False}))


if __name__ == "__main__":
    main()
