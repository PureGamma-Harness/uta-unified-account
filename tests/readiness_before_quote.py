"""Test-only startup barrier; a READY frame is not a financial-ready ACK.

Wait for parent-consumed frames without diagnostic SQL, then accept exactly one
native owner observation. A failed or unknown observation is retained and fails
this attempt; a later possible success is never used to replace it.
"""
from datetime import datetime, timezone
import json
from time import monotonic, sleep


def complete_owner_observation(report, shards):
    """Check a native diagnostics dict, without claiming financial readiness.

    The input domain is the production diagnostics shape, not arbitrary parser
    input. Identity integers are checked exactly so bool/float equality cannot
    stand in for a native shard, PID or generation.
    """
    rows = report.get("workers", [])
    if (report.get("state_observed") is not True
            or report.get("reason") not in {"publication_incomplete", "router_halted", "ready", "local_halt"}
            or "observation_error" in report
            or not isinstance(report.get("state"), dict)
            or report.get("supervisor_alive") is not True
            or report.get("workers_alive") is not True
            or not isinstance(rows, list)
            or [row.get("shard") for row in rows] != list(shards)):
        return False
    for row in rows:
        frame = row.get("report", {})
        pid, generation = row.get("pid"), row.get("generation")
        expected_missing = (row.get("reason") == "market_missing"
                            and report["state"].get("market_version") is None)
        if (row.get("reason") != "ready" and not expected_missing
                or type(row.get("shard")) is not int
                or type(pid) is not int or pid <= 0
                or type(generation) is not int or generation <= 0
                or row.get("alive") is not True
                or row.get("lease_active") is not True
                or row.get("owner_ready") is not True
                or type(row.get("owner_pid")) is not int
                or row.get("owner_pid") != pid
                or frame.get("state") != "ready"
                or type(frame.get("shard")) is not int
                or frame.get("shard") != row["shard"]
                or type(frame.get("pid")) is not int
                or frame.get("pid") != pid
                or type(frame.get("generation")) is not int
                or frame.get("generation") != generation):
            return False
    return True


def current_quote_after_owner_ready(testcase, router, make_quote, *, timeout=1):
    """Create a default current quote only after a real bounded owner witness.

    This helper never publishes, activates, renews, rewrites a quote, consumes a
    pipe, or sets a report. The monitor remains the sole READY-frame consumer.
    The one-second total budget matches the existing readiness sampler.
    """
    deadline = monotonic() + timeout
    shards = tuple(range(router.layout["shard_count"]))
    evidence = {"deadline_monotonic": deadline, "parent_samples": [], "native_observations": []}
    testcase.owner_before_quote_evidence = evidence
    while monotonic() < deadline:
        acquired = router._mutex.acquire(timeout=max(0, deadline - monotonic()))
        if not acquired:
            break
        try:
            frames = []
            for shard in shards:
                worker = router._workers.get(shard)
                alive = worker is not None and worker[0].is_alive()
                report = router._reports.get(shard, {})
                frames.append({"shard": shard,
                    "pid": worker[0].pid if alive else None, "alive": alive,
                    "report": {key: report[key] for key in ("state", "shard", "pid", "generation")
                               if key in report}})
        finally:
            router._mutex.release()
        evidence["parent_samples"].append(frames)
        frames_match = all(row["alive"] and row["report"].get("state") == "ready"
            and type(row["pid"]) is int and row["pid"] > 0
            and type(row["report"].get("shard")) is int
            and row["report"].get("shard") == row["shard"]
            and type(row["report"].get("pid")) is int
            and row["report"].get("pid") == row["pid"]
            and type(row["report"].get("generation")) is int
            and row["report"]["generation"] > 0 for row in frames)
        if frames_match:
            remaining = deadline - monotonic()
            if remaining <= 0:
                break
            observation = router.diagnostics(timeout=min(.1, remaining))
            evidence["native_observations"].append(observation)
            evidence["native_completed_monotonic"] = monotonic()
            testcase.assertLess(evidence["native_completed_monotonic"], deadline,
                "first before-quote owner observation completed outside total budget: "
                + json.dumps(evidence, sort_keys=True))
            testcase.assertTrue(complete_owner_observation(observation, shards),
                "first before-quote owner observation failed: " + json.dumps(evidence, sort_keys=True))
            evidence["witness_utc"] = datetime.now(timezone.utc).isoformat()
            return make_quote()
        sleep(min(.01, max(0, deadline - monotonic())))
    testcase.fail("before-quote READY frame budget exhausted: " + json.dumps(evidence, sort_keys=True))
