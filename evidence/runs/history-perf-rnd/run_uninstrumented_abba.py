"""Prepared only: requires new exact-source GO and one outside 15s controller.

One private authority per fixed scale, 27 separate correctness controls, untimed
A/B warmups, then exactly three ABBA blocks/scale. No profile/trace/row callback
is installed for timed calls. This is not a service or capacity load generator.
"""
import time

ENTERED_NS = time.monotonic_ns()

import argparse
from datetime import datetime, timezone
from decimal import Decimal
from fractions import Fraction
from hashlib import sha256
import importlib.util
import json
import os
from pathlib import Path
import platform
import signal
import sqlite3
import sys
from tempfile import TemporaryDirectory
import unittest


ROOT = Path(__file__).resolve().parents[3]
RUNTIME = "dd502ae538618c6d17a3bd2eae708e09526e9d4c"
OBSERVED = "3a48aa4eb27b8c7a61241c7045b25faf24a8737c"
SCALES = (512, 4096)
BLOCKS = 3
ORDER = (False, True, True, False)


def source_hashes():
    paths = sorted((ROOT / "uta").glob("*.py"))
    paths += [ROOT / "tests/test_history_postings_stream.py", Path(__file__).resolve()]
    return {p.relative_to(ROOT).as_posix(): sha256(p.read_bytes()).hexdigest() for p in paths}


def literal_reference(connection, count):
    """Exact fixed-fixture reference; no production hash/codec/normalizer used."""
    assert [row[0] for row in connection.execute("PRAGMA integrity_check")] == ["ok"]
    assert connection.execute("PRAGMA foreign_key_check").fetchone() is None
    events = list(map(tuple, connection.execute("SELECT * FROM ledger_events ORDER BY sequence")))
    postings = list(map(tuple, connection.execute("SELECT * FROM ledger_postings ORDER BY sequence,ordinal")))
    balances = list(map(tuple, connection.execute("SELECT * FROM ledger_balances ORDER BY account,asset")))
    assert len(events) == count and len(postings) == 2*count
    assert balances == [("a", "USD", str(-count)), ("b", "USD", str(count))]
    previous = "0" * 64
    fingerprint = sha256(json.dumps([["a","USD",-1],["b","USD",1]],
        ensure_ascii=True, separators=(",", ":")).encode()).hexdigest()
    for sequence, actual in enumerate(events, 1):
        event_id = "component:" + str(sequence-1)
        event_hash = sha256(json.dumps([sequence,event_id,previous,fingerprint],
            ensure_ascii=True, separators=(",", ":")).encode()).hexdigest()
        assert actual == (sequence,event_id,fingerprint,previous,event_hash,1)
        assert postings[(sequence-1)*2:sequence*2] == [
            (sequence,0,"a","USD","-1"), (sequence,1,"b","USD","1")]
        previous = event_hash
    return dict(events=count, postings=2*count, head=previous,
                balances_units={"a/USD":-count,"b/USD":count})


def fraction_record(value):
    return dict(numerator=value.numerator, denominator=value.denominator)


def block_report(samples):
    assert [sample["ordered_postings"] for sample in samples] == list(ORDER)
    report = {}
    for metric in ("wall_ns", "cpu_ns"):
        a_sum = samples[0][metric] + samples[3][metric]
        b_sum = samples[1][metric] + samples[2][metric]
        assert a_sum > 0 and b_sum > 0
        report[metric] = dict(a_mean=fraction_record(Fraction(a_sum,2)),
            b_mean=fraction_record(Fraction(b_sum,2)),
            b_over_a=fraction_record(Fraction(b_sum,a_sum)),
            b_minus_a_mean=fraction_record(Fraction(b_sum-a_sum,2)))
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    assert sorted(os.sched_getaffinity(0)) == [4], "exact assigned CPU4 required"
    assert sys.getprofile() is None and sys.gettrace() is None, "external profiler/trace present"
    args.output.mkdir(mode=0o700, parents=False, exist_ok=False)
    result = dict(scope="uninstrumented-bounded-synthetic-ABBA", success=False,
        runtime_commit=RUNTIME, prior_observed_candidate=OBSERVED,
        started_utc=datetime.now(timezone.utc).isoformat(), pid=os.getpid(),
        affinity=sorted(os.sched_getaffinity(0)), python=sys.version,
        platform=platform.platform(), sqlite=sqlite3.sqlite_version,
        outside_wall_cap_seconds=15, internal_alarm_seconds=14,
        physical_cold_io_established=False, independent_acceptance=False,
        production_qualified=False, before_sources=source_hashes(), scales=[])
    events = (args.output / "phases.jsonl").open("x")
    samples_file = (args.output / "samples.jsonl").open("x")

    def phase(name, **values):
        events.write(json.dumps(dict(phase=name, monotonic_ns=time.monotonic_ns(),
            elapsed_ns=time.monotonic_ns()-ENTERED_NS, **values), sort_keys=True)+"\n")
        events.flush()

    def expired(signum, frame):
        raise TimeoutError("internal 14s alarm; outside 15s controller still required")

    signal.signal(signal.SIGALRM, expired)
    signal.setitimer(signal.ITIMER_REAL, max(.001, 14-(time.monotonic_ns()-ENTERED_NS)/1e9))
    try:
        expected = json.loads((ROOT / "evidence/runs/history-perf-rnd/attempt-02-v2/summary.json").read_text())["before_sources"]
        assert all(result["before_sources"].get(name) == digest for name,digest in expected.items()
                   if name.startswith("uta/") or name == "tests/test_history_postings_stream.py")
        sys.path.insert(0, str(ROOT))
        spec = importlib.util.spec_from_file_location("history_stream_controls", ROOT / "tests/test_history_postings_stream.py")
        control = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(control)
        phase("correctness_controls.begin", outside_timed_intervals=True)
        with (args.output / "unittest.txt").open("x") as log:
            checked = unittest.TextTestRunner(stream=log, verbosity=2).run(
                unittest.defaultTestLoader.loadTestsFromTestCase(control.HistoryPostingsStreamTests))
        result["correctness_controls"] = dict(tests=checked.testsRun,
            failures=len(checked.failures), errors=len(checked.errors), skipped=len(checked.skipped))
        phase("correctness_controls.end", **result["correctness_controls"])
        assert checked.wasSuccessful() and result["correctness_controls"] == dict(tests=27,failures=0,errors=0,skipped=0)
        from uta.storage import Database, DurableLedger
        from uta.ledger import Posting
        with TemporaryDirectory(prefix="uta-history-abba-private-") as temporary:
            for count in SCALES:
                scale = dict(events=count, expected_postings=2*count, samples=[], blocks=[])
                result["scales"].append(scale)
                database = Database(Path(temporary) / ("authority-"+str(count)+".sqlite3"))
                assert type(database) is Database
                ledger = DurableLedger(database, {"USD":2})
                phase("fixture.begin", events=count)
                committed = 0
                for first in range(0,count,256):
                    with database.transaction() as connection:
                        for index in range(first,min(count,first+256)):
                            ledger.post("component:"+str(index), [Posting("a","USD",Decimal("-0.01")),
                                Posting("b","USD",Decimal("0.01"))], connection=connection)
                    committed += 1
                    phase("fixture.batch_commit_return", events=count,
                        committed_batches=committed, committed_events=min(count,first+256))
                assert committed == count//256
                with database.read_transaction() as connection:
                    scale["initial_reference"] = literal_reference(connection,count)
                phase("initial_reference.complete", events=count, **{"reference":scale["initial_reference"]})
                for mode in (False,True):
                    assert ledger.verify(ordered_postings=mode) == count
                    phase("untimed_warmup.complete", events=count, ordered_postings=mode)
                for block in range(BLOCKS):
                    phase("ABBA_block.begin", events=count, block=block)
                    block_samples = []
                    for slot,mode in enumerate(ORDER):
                        assert sys.getprofile() is None and sys.gettrace() is None
                        phase("timed_verify.begin", events=count, block=block,
                              slot=slot, ordered_postings=mode)
                        # Timers include the complete ordinary verifier call,
                        # including native SQL, guards, connection/commit/close.
                        wall_start = time.monotonic_ns()
                        cpu_start = time.process_time_ns()
                        returned = ledger.verify(ordered_postings=mode)
                        cpu_end = time.process_time_ns()
                        wall_end = time.monotonic_ns()
                        assert returned == count
                        sample = dict(scale_events=count, block=block, slot=slot,
                            ordered_postings=mode, returned_events=returned,
                            wall_ns=wall_end-wall_start, cpu_ns=cpu_end-cpu_start)
                        scale["samples"].append(sample)
                        block_samples.append(sample)
                        samples_file.write(json.dumps(sample,sort_keys=True)+"\n")
                        samples_file.flush()
                        phase("timed_verify.end", **sample)
                    scale["blocks"].append(block_report(block_samples))
                    phase("ABBA_block.end", events=count, block=block)
                phase("final_default_reopen.begin", events=count)
                restored = DurableLedger(Database(database.path), {"USD":2})
                assert restored.verify() == count
                with restored.database.read_transaction() as connection:
                    scale["final_reference"] = literal_reference(connection,count)
                assert scale["initial_reference"] == scale["final_reference"]
                phase("final_default_reopen.end", events=count, reference=scale["final_reference"])
                scale["median_block_ratios"] = {}
                for metric in ("wall_ns","cpu_ns"):
                    ratios = [Fraction(item[metric]["b_over_a"]["numerator"],
                                       item[metric]["b_over_a"]["denominator"]) for item in scale["blocks"]]
                    scale["median_block_ratios"][metric] = fraction_record(sorted(ratios)[1])
                assert len(scale["samples"]) == 12
        phase("scratch.cleanup_complete")
        assert len(result["scales"]) == 2 and sum(len(s["samples"]) for s in result["scales"]) == 24
        result["success"] = True
    except BaseException as error:
        result["error"] = dict(type=type(error).__name__, message=str(error))
        phase("failed", **result["error"])
    finally:
        signal.setitimer(signal.ITIMER_REAL,0)
        result["after_sources"] = source_hashes()
        result["source_unchanged"] = result["before_sources"] == result["after_sources"]
        result["success"] = result["success"] and result["source_unchanged"]
        result["elapsed_ns_before_summary_write"] = time.monotonic_ns()-ENTERED_NS
        (args.output / "summary.json").write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
        events.close()
        samples_file.close()
    print(json.dumps(dict(success=result["success"],
        samples=sum(len(scale["samples"]) for scale in result["scales"]),
        elapsed_ns=result["elapsed_ns_before_summary_write"]), sort_keys=True))
    return 0 if result["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
