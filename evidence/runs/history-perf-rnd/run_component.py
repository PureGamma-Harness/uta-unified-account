"""One opt-in synthetic component, NOT a load generator or service.

Do not run without the exact-source root GO and CPU4 release. Example approved
invocation would be: taskset -c 4 python .../run_component.py --output NEW_DIR
The outside controller must enforce its own total 15s wall cap, including import,
startup, output, cleanup and final evidence. No internal timer proves that cap.
"""
import time

ENTERED_NS = time.monotonic_ns()

import argparse
import cProfile
from decimal import Decimal
from hashlib import sha256
import importlib.util
import io
import json
import os
from pathlib import Path
import platform
import pstats
import signal
import sqlite3
import sys
from tempfile import TemporaryDirectory
import unittest


ROOT = Path(__file__).resolve().parents[3]
N = 512
RUNTIME_COMMIT = "56de743"


def sources():
    paths = sorted((ROOT / "uta").glob("*.py"))
    paths.extend([Path(__file__).resolve(), ROOT / "tests/test_history_postings_stream.py"])
    return {path.relative_to(ROOT).as_posix(): sha256(path.read_bytes()).hexdigest() for path in paths}


def proc_io():
    wanted = {"rchar", "syscr", "read_bytes", "wchar", "syscw", "write_bytes"}
    return {key: int(value) for line in Path("/proc/self/io").read_text().splitlines()
            for key, value in [line.split(":", 1)] if key in wanted}


def literal_reference(connection):
    """Integer/hash verifier with no production codec or financial helper calls."""
    previous, balances, posting_count = "0" * 64, {}, 0
    rows = list(connection.execute("SELECT * FROM ledger_events ORDER BY sequence"))
    logical = 0
    for expected, row in enumerate(rows, 1):
        sequence, event_id, fingerprint, prior, event_hash, sealed = tuple(row)
        assert sequence == expected and sealed == 1 and prior == previous
        postings = list(connection.execute("SELECT ordinal,account,asset,units FROM ledger_postings WHERE sequence=? ORDER BY ordinal", (sequence,)))
        assert len(postings) >= 2 and [r[0] for r in postings] == list(range(len(postings)))
        canonical, totals = [], {}
        for _, account, asset, text in postings:
            units = int(text)
            assert type(text) is str and str(units) == text and 0 < abs(units) < 10**38
            canonical.append((account, asset, units))
            totals[asset] = totals.get(asset, 0) + units
            key = account, asset
            balances[key] = balances.get(key, 0) + units
            assert abs(balances[key]) < 10**38
        assert canonical == sorted(canonical) and not any(totals.values())
        assert fingerprint == sha256(json.dumps(canonical, ensure_ascii=True, separators=(",", ":")).encode()).hexdigest()
        assert event_hash == sha256(json.dumps([sequence, event_id, prior, fingerprint], ensure_ascii=True, separators=(",", ":")).encode()).hexdigest()
        logical += len(json.dumps([tuple(row), [tuple(r) for r in postings]], separators=(",", ":")).encode())
        posting_count += len(postings)
        previous = event_hash
    stored = {(a, s): int(u) for a, s, u in connection.execute("SELECT * FROM ledger_balances")}
    assert balances == stored == {("a", "USD"): -N, ("b", "USD"): N}
    assert connection.execute("SELECT COUNT(*) FROM ledger_postings").fetchone()[0] == posting_count == 2*N
    assert len(rows) == N
    return {"events": N, "postings": posting_count, "head": previous,
            "balances_units": {a + "/" + s: u for (a, s), u in sorted(stored.items())},
            "logical_event_and_posting_json_bytes": logical,
            "logical_byte_definition": "UTF-8 compact JSON of selected event row plus its selected posting rows; not SQL/table/OS read bytes"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if sorted(os.sched_getaffinity(0)) != [4]:
        raise RuntimeError("exact CPU4 affinity required before component startup")
    args.output.mkdir(mode=0o700, parents=False, exist_ok=False)
    result = {"scope": "single-synthetic-full-replay-component", "runtime_commit": RUNTIME_COMMIT,
              "profile_is_instrumented": True, "capacity_qualified": False,
              "independent_author_signoff": False, "success": False,
              "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
              "pid": os.getpid(), "affinity": sorted(os.sched_getaffinity(0)),
              "python": sys.version, "platform": platform.platform(),
              "sqlite": sqlite3.sqlite_version, "configured_outer_cap_seconds": 15,
              "before_sources": sources(), "calls": []}
    events = (args.output / "phases.jsonl").open("x")

    def phase(name, **values):
        record = dict(phase=name, monotonic_ns=time.monotonic_ns(),
                      elapsed_ns=time.monotonic_ns()-ENTERED_NS,
                      process_cpu_ns=time.process_time_ns(), **values)
        events.write(json.dumps(record, sort_keys=True) + "\n")
        events.flush()

    def expired(signum, frame):
        raise TimeoutError("internal 14s component budget expired; outside 15s cap still required")

    signal.signal(signal.SIGALRM, expired)
    signal.setitimer(signal.ITIMER_REAL, max(.001, 14 - (time.monotonic_ns()-ENTERED_NS)/1e9))
    try:
        sys.path.insert(0, str(ROOT))
        spec = importlib.util.spec_from_file_location("history_postings_stream_tests", ROOT / "tests/test_history_postings_stream.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        phase("differential.begin")
        with (args.output / "unittest.txt").open("x") as log:
            test_result = unittest.TextTestRunner(stream=log, verbosity=2).run(
                unittest.defaultTestLoader.loadTestsFromTestCase(module.HistoryPostingsStreamTests))
        result["differential"] = dict(tests=test_result.testsRun, failures=len(test_result.failures), errors=len(test_result.errors), skipped=len(test_result.skipped))
        phase("differential.end", **result["differential"])
        assert test_result.wasSuccessful(), "differential red: profile not started"
        from uta.storage import Database, DurableLedger
        from uta.ledger import Posting
        with TemporaryDirectory(prefix="uta-history-component-") as temporary:
            database = module.TraceDatabase(Path(temporary) / "authority.sqlite3")
            ledger = DurableLedger(database, {"USD": 2})
            phase("fixture.begin", planned_events=N, planned_postings=2*N)
            commits = 0
            for first in range(0, N, 256):
                with database.transaction() as connection:
                    for index in range(first, min(N, first+256)):
                        ledger.post("component:" + str(index),
                            [Posting("a", "USD", Decimal("-0.01")), Posting("b", "USD", Decimal("0.01"))], connection=connection)
                commits += 1
                phase("fixture.batch_commit_return", committed_batches=commits, committed_events=min(N, first+256))
            phase("fixture.end", committed_events=N, committed_postings=2*N, commits=commits)
            with database.read_transaction() as connection:
                result["initial_literal_reference"] = literal_reference(connection)
            for index, mode in enumerate((False, True, False, True)):
                database.statements.clear()
                before_io, wall, cpu = proc_io(), time.monotonic_ns(), time.process_time_ns()
                profiler = cProfile.Profile()
                phase("verify.begin", index=index, ordered_postings=mode)
                profiler.enable()
                try:
                    count = ledger.verify(ordered_postings=mode)
                finally:
                    profiler.disable()
                end_wall, end_cpu, after_io = time.monotonic_ns(), time.process_time_ns(), proc_io()
                assert count == N
                posting_sql = [sql for sql in database.statements if sql.startswith("SELECT") and "FROM ledger_postings" in sql]
                assert len(posting_sql) == (1 if mode else N)
                report = dict(index=index, ordered_postings=mode, returned_events=count,
                    selected_events=N, selected_postings=2*N, wall_ns=end_wall-wall,
                    cpu_ns=end_cpu-cpu, sql_statements=len(database.statements),
                    posting_select_statements=len(posting_sql),
                    observation_class="first_measured_after_fixture_and_reference" if index == 0 else "repeated_after_previous_complete_replay",
                    physical_cold_io_established=False,
                    proc_io_delta={key: after_io[key]-before_io[key] for key in before_io},
                    logical_selected_row_bytes=result["initial_literal_reference"]["logical_event_and_posting_json_bytes"])
                result["calls"].append(report)
                stream = io.StringIO()
                pstats.Stats(profiler, stream=stream).sort_stats("cumulative").print_stats(35)
                (args.output / ("profile-" + str(index) + ".txt")).write_text(stream.getvalue())
                phase("verify.end", **report)
            phase("final_default_cold_reopen.begin")
            restored = DurableLedger(Database(database.path), {"USD": 2})
            assert restored.verify() == N
            with restored.database.read_transaction() as connection:
                final = literal_reference(connection)
            assert final == result["initial_literal_reference"]
            result["final_default_cold_reference"] = final
            phase("final_default_cold_reopen.end", events=N, postings=2*N,
                  physical_cold_io_established=False)
        phase("scratch.cleanup_complete")
        result["success"] = True
    except BaseException as error:
        result["error"] = {"type": type(error).__name__, "message": str(error)}
        phase("failed", **result["error"])
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        result["after_sources"] = sources()
        result["source_unchanged"] = result["after_sources"] == result["before_sources"]
        result["success"] = result["success"] and result["source_unchanged"]
        result["elapsed_ns_before_summary_write"] = time.monotonic_ns()-ENTERED_NS
        (args.output / "summary.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
        events.close()
    print(json.dumps({"success": result["success"], "differential": result.get("differential"),
                      "calls": len(result["calls"]), "elapsed_ns": result["elapsed_ns_before_summary_write"]}, sort_keys=True))
    return 0 if result["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
