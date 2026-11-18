"""One fixed pure enumeration capture; actual host exit must be observed outside.

Derived from the reviewed cross_pilot_pure_capture at31fe46fd. Trusted local
sources and cooperative deadlines are not a filesystem sandbox or hard I/O SLA.
"""
import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import selectors
import stat
import subprocess
import sys
from time import monotonic_ns


ROOT = Path(__file__).resolve().parents[1]
PLAN = "evidence/reviews/cross-enumeration-capture/capture-plan.json"
SELF = "tools/run_cross_enumeration_capture.py"
TARGET_PLAN = "evidence/reviews/cross-decimal-enumeration/pure-once-plan.json"
CAPTURE_RAW, TOTAL_RAW, FILE_LIMIT = 30720, 32768, 4 * 1024 * 1024
CONTROL_LIMIT, CONTROL_RESERVED = 512 * 1024, 0


def read_regular(path, limit=2 * 1024 * 1024):
    if path.resolve() != path or not stat.S_ISREG(path.lstat().st_mode):
        raise ValueError("canonical regular file required")
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW), "rb") as stream:
        before = os.fstat(stream.fileno())
        value = stream.read(limit + 1)
        after = os.fstat(stream.fileno())
    keys = ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns")
    if len(value) > limit or any(getattr(before, k) != getattr(after, k) for k in keys):
        raise ValueError("bounded source changed during read")
    return value


def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()


def fresh(directory, name, data):
    global CONTROL_RESERVED
    if len(data) > FILE_LIMIT or CONTROL_RESERVED + len(data) > CONTROL_LIMIT:
        raise ValueError("parent control reservation exhausted")
    CONTROL_RESERVED += len(data)
    fd = os.open(directory / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "wb") as stream:
        if stream.write(data) != len(data):
            raise OSError("short parent control write")
        stream.flush()
        os.fsync(stream.fileno())


def record(directory, name, value):
    fresh(directory, name, encoded(value))


def git(*arguments, data=None):
    # Read-only source-control children are separate from the sole target
    # prefix. No timeout/kill/PID discovery is added to this control helper.
    result = subprocess.run(["/usr/bin/git", "--no-optional-locks", "-C", str(ROOT), *arguments],
        input=data, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True,
        env={**os.environ, "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": "/dev/null"})
    if result.stderr or len(result.stdout) > 4 * 1024 * 1024:
        raise ValueError("unexpected source-control output")
    return result.stdout


def pins(plan, source, plan_raw):
    if git("rev-parse", "HEAD").decode().strip() != source:
        raise ValueError("actual invocation HEAD changed")
    requests = b"".join((source + ":" + name + "\n").encode() for name in plan["input_files"])
    objects = git("cat-file", "--batch", data=requests)
    observed, offset = {}, 0
    for name, expected in plan["input_files"].items():
        if name.startswith("/") or ".." in Path(name).parts:
            raise ValueError("source escaped checkout")
        end = objects.index(b"\n", offset)
        header = objects[offset:end].split()
        if len(header) != 3 or header[1] != b"blob" or int(header[2]) != expected["bytes"]:
            raise ValueError("unexpected Git blob framing")
        start, stop = end + 1, end + 1 + expected["bytes"]
        value = read_regular(ROOT / name)
        fact = {"bytes": len(value), "sha256": sha256(value).hexdigest()}
        if fact != expected or objects[start:stop] != value or objects[stop:stop + 1] != b"\n":
            raise ValueError("physical/Git source pin differs: " + name)
        observed[name], offset = fact, stop + 1
    if offset != len(objects) or read_regular(ROOT / PLAN) != plan_raw:
        raise ValueError("extra Git bytes or changed approved plan")
    if git("show", source + ":" + PLAN) != plan_raw:
        raise ValueError("approved plan differs from invocation Git")
    return observed


def verify_target(target, stdout, plan, source):
    records = [json.loads(line) for line in stdout.splitlines()]
    if len(records) != 2:
        raise ValueError("missing or extra BEGIN/END rows")
    intent = json.loads(read_regular(target / "intent.json"))
    receipt = json.loads(read_regular(target / "first.execution.json"))
    vectors_raw = read_regular(target / "vectors.json", FILE_LIMIT)
    vectors = json.loads(vectors_raw)
    expected_ids = ["test_cross_decimal_enumeration.CrossDecimalEnumerationTests." + name for name in plan["methods"]]
    if (records[0] != {"event": "CROSS_ENUMERATION_BEGIN", "source_commit_invoker_label": source,
            "plan_sha256": plan["target_plan_sha256"], "methods": plan["methods"], "runtime": plan["expected_runtime"]}
            or records[1] != {"event": "CROSS_ENUMERATION_END", **receipt}
            or intent["source_commit_invoker_label"] != source or intent["plan_sha256"] != plan["target_plan_sha256"]
            or intent["runtime"] != plan["expected_runtime"] or intent["planned_methods"] != plan["methods"]
            or intent["input_files"] != plan["target_inputs"]):
        raise ValueError("target intent/BEGIN/END binding differs")
    if (receipt["vector_file"] != {"bytes": len(vectors_raw), "sha256": sha256(vectors_raw).hexdigest()}
            or vectors["source_commit_invoker_label"] != source or vectors["plan_sha256"] != plan["target_plan_sha256"]
            or vectors["completed_counts"] != plan["expected_counts"] or vectors["all_538_required"] is not True
            or vectors["failure_vectors"] != [] or len(vectors["vector_groups"]) != 5):
        raise ValueError("complete vector archive differs")
    count = 0
    for index, group in enumerate(vectors["vector_groups"]):
        if group["test_id"] != expected_ids[index] or len(group["vectors"]) != plan["expected_counts"][index]:
            raise ValueError("vector/test identity or count differs")
        for vector in group["vectors"]:
            if vector["stage"] != "verified" or encoded(vector["expected"]) != encoded(vector["actual"]):
                raise ValueError("archived expected/actual values differ")
            if index < 4 and (set(vector["expected_metadata"]) != set(plan["metadata_fields"])
                    or encoded(vector["expected_metadata"]) != encoded(vector["actual_metadata"])):
                raise ValueError("archived expected/actual provenance differs")
            count += 1
    clean = (type(receipt["tests_run"]) is int and receipt["tests_run"] == 5
        and receipt["success_ids"] == expected_ids and receipt["completed_vectors_by_method"] == plan["expected_counts"]
        and type(receipt["completed_vectors"]) is int and receipt["completed_vectors"] == count == 538
        and all(type(receipt[k]) is int and receipt[k] == 0 for k in ("failures", "errors", "skipped"))
        and receipt["complete"] is True and receipt["passed"] is True and receipt["source_unchanged"] is True
        and receipt["runtime"] == plan["expected_runtime"] and receipt["forbidden_listed_events"] == []
        and receipt["Python_thread_count"] == 1 and receipt["loaded_UTA_modules"] == plan["loaded_modules"]
        and receipt["oracle_uses_reference_core"] is False and receipt["SQL_or_native_or_admission_executed"] is False)
    return receipt, clean, {"bytes": len(vectors_raw), "sha256": sha256(vectors_raw).hexdigest(), "verified_count": count}


def main():
    started = monotonic_ns(); deadline = started + 22_000_000_000
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--approved-plan-sha256", required=True)
    args = parser.parse_args()
    if not args.execute or sorted(os.sched_getaffinity(0)) != [1]:
        raise ValueError("explicit GO and inherited whole-host CPU1 required")
    plan_raw = read_regular(ROOT / PLAN)
    if sha256(plan_raw).hexdigest() != args.approved_plan_sha256:
        raise ValueError("approved capture plan SHA differs")
    plan = json.loads(plan_raw); before = pins(plan, args.source_commit, plan_raw)
    directory, target = Path(plan["capture_root"]), Path(plan["target_root"])
    if directory == target or any(p.resolve() != p or p.parent != Path("/workspace") or os.path.lexists(p) for p in (directory, target)):
        raise ValueError("two distinct new canonical workspace roots required")
    os.umask(0o077); directory.mkdir(mode=0o700)
    argv = [x.replace("<FINAL_SOURCE_HEAD>", args.source_commit) for x in plan["target_argv"]]
    fresh(directory, "capture-source.py", read_regular(ROOT / SELF))
    record(directory, "pins-before.json", before)
    record(directory, "intent.json", {"source_commit": args.source_commit, "exact_argv": argv,
        "literal_host_argv": list(sys.orig_argv), "host_affinity": sorted(os.sched_getaffinity(0)),
        "capture_plan_sha256": args.approved_plan_sha256, "target_plan_sha256": plan["target_plan_sha256"],
        "source_pin_semantics": "trusted physical/Git checks, not immutable execution attestation"})
    child = None; selector = selectors.DefaultSelector(); fds = {}
    actual_exit = None; reaped = eof = False; fault = None
    reserved = written = writes = 0; stream_bytes = {"stdout": 0, "stderr": 0}
    launch = monotonic_ns()
    try:
        if launch >= deadline:
            raise TimeoutError("host budget exhausted before target launch")
        child = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, close_fds=True)
        for label, stream in (("stdout", child.stdout), ("stderr", child.stderr)):
            os.set_blocking(stream.fileno(), False); selector.register(stream, selectors.EVENT_READ, label)
            fds[label] = os.open(directory / ("first." + label), os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        exited_at = None
        while selector.get_map():
            now = monotonic_ns()
            if child.poll() is not None and exited_at is None: exited_at = now
            if now >= deadline or exited_at is not None and now - exited_at > 2_000_000_000:
                fault = "DEADLINE_OR_INCOMPLETE_EOF_UNKNOWN"; break
            for key, unused in selector.select(min(.05, max(0, (deadline - now) / 1e9))):
                value = os.read(key.fileobj.fileno(), 4096)
                if not value: selector.unregister(key.fileobj); key.fileobj.close(); continue
                if reserved + len(value) > CAPTURE_RAW: fault = "RAW_CAP_UNKNOWN"; break
                reserved += len(value)
                count = os.write(fds[key.data], value); written += count; writes += 1; stream_bytes[key.data] += count
                if count != len(value): fault = "SHORT_RAW_WRITE_UNKNOWN"; break
            if fault: break
        eof = not selector.get_map()
    except BaseException as error:
        fault = type(error).__name__ + ":" + str(error)[:128]
    finally:
        for key in list(selector.get_map().values()): selector.unregister(key.fileobj); key.fileobj.close()
        if child is not None:
            try: actual_exit = child.wait(timeout=max(.001, (deadline - monotonic_ns()) / 1e9)); reaped = True
            except BaseException as error: fault = fault or "WAIT_" + type(error).__name__
        for fd in fds.values():
            try: os.fsync(fd)
            except BaseException as error: fault = fault or "FSYNC_" + type(error).__name__
            finally: os.close(fd)
        selector.close()
    wait_end = monotonic_ns(); after = receipt = vector_fact = None; target_clean = False
    try:
        after = pins(plan, args.source_commit, plan_raw); record(directory, "pins-after.json", after)
        if reaped and eof:
            receipt, target_clean, vector_fact = verify_target(target, read_regular(directory / "first.stdout", CAPTURE_RAW), plan, args.source_commit)
    except BaseException as error:
        fault = fault or "FINAL_" + type(error).__name__ + ":" + str(error)[:128]
    passed = (monotonic_ns() < deadline and fault is None and actual_exit == 0 and reaped and eof
              and before == after and target_clean and reserved == written)
    record(directory, "receipt.json", {"status": "FUNCTIONAL_PASS_PENDING_ACTUAL_HOST_EXIT_AND_INDEPENDENT_RAW" if passed else "FIRST_FAIL_OR_UNKNOWN_NO_RETRY",
        "source_commit": args.source_commit, "actual_host_exit": None, "actual_host_exit_requires_external_observation": True,
        "actual_prefix_exit": actual_exit, "reaped": reaped, "EOF_complete": eof, "fault": fault,
        "host_start_ns": started, "target_launch_ns": launch, "prefix_wait_raw_fsync_end_ns": wait_end,
        "host_before_receipt_ns": monotonic_ns(), "target_interval_ns": wait_end - launch,
        "live_raw_reserved_before_write": reserved, "live_raw_written": written, "write_calls": writes, "stream_bytes": stream_bytes,
        "source_before_after_equal": before == after, "target_receipt": receipt, "vector_file": vector_fact,
        "partial_target_files_preserved_without_repair": True, "unreaped_descendants_not_certified": True})
    summary = encoded({"status": "PENDING_EXTERNAL_EXIT" if passed else "FIRST_FAIL_OR_UNKNOWN_NO_RETRY",
        "prefix_exit": actual_exit, "reaped": reaped, "EOF": eof, "fault": fault})
    if len(summary) > 512 or reserved + 2 * len(summary) + 512 > TOTAL_RAW:
        raise ValueError("combined raw reserve exceeded")
    fresh(directory, "caller-summary.stdout", summary)
    if os.write(1, summary) != len(summary): raise OSError("short final summary")
    allowed_target = {"intent.json", "vectors.json", "first.execution.json"}
    target_files = list(target.iterdir()) if target.exists() else []
    if any(p.name not in allowed_target or not stat.S_ISREG(p.lstat().st_mode) or p.stat().st_size > FILE_LIMIT for p in target_files):
        raise ValueError("unexpected target resource")
    files = {p.name: {"bytes": p.stat().st_size, "sha256": sha256(read_regular(p, FILE_LIMIT)).hexdigest()} for p in directory.iterdir()}
    record(directory, "inventory.json", {"files": files, "excludes_this_inventory": True,
        "combined_final_logical_quota_only": True, "outer_summary_duplicate_bytes_charged": 2 * len(summary)})
    combined = sum(p.stat().st_size for p in directory.iterdir()) + sum(p.stat().st_size for p in target_files)
    if combined > 8 * 1024 * 1024: raise ValueError("combined final logical8MiB exceeded")
    return 0 if passed and monotonic_ns() < deadline else 1


def entry():
    try: return main()
    except Exception as error:
        trailer = encoded({"event": "ENUM_CAPTURE_FIRST_FAILURE", "type": type(error).__name__, "message": str(error)[:96], "complete": False})
        if len(trailer) <= 512: os.write(2, trailer)
        return 125


if __name__ == "__main__":
    raise SystemExit(entry())
