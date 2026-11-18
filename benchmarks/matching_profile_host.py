"""CODE-only two-child continuous host producer; root-specific GO required.

No UTA/SQLite import, network, worker, /proc or old-process inspection. Only
new Popen children owned here may be reaped or signalled, through held pidfds.
C I/O may block; a late/unknown completion never qualifies as a successful run.
"""
import argparse
from contextlib import redirect_stdout, redirect_stderr
from hashlib import sha256
import json
import os
from pathlib import Path
import runpy
import signal
import stat
import subprocess
import sys
from time import monotonic_ns


def require(value, message):
    if not value:
        raise ValueError(message)


def canonical(value):
    return json.dumps(value, sort_keys=True, indent=2, ensure_ascii=True, allow_nan=False).encode() + b"\n"


def read_regular(path, cap=4 * 1024 * 1024):
    require(path.is_absolute() and path.resolve() == path, "noncanonical host input")
    before = path.lstat()
    require(stat.S_ISREG(before.st_mode) and before.st_size <= cap, "host input not bounded regular data")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        opened = os.fstat(fd)
        require((opened.st_dev, opened.st_ino, opened.st_size, opened.st_mtime_ns, opened.st_ctime_ns)
                == (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns), "host input changed")
        data = bytearray()
        while True:
            part = os.read(fd, 65536)
            if not part:
                break
            data.extend(part)
            require(len(data) <= cap, "host input grew beyond cap")
        after = os.fstat(fd)
        require((after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns)
                == (opened.st_dev, opened.st_ino, opened.st_size, opened.st_mtime_ns, opened.st_ctime_ns)
                and len(data) == after.st_size, "host input changed during read")
        return bytes(data)
    finally:
        os.close(fd)


def pin(path, cap=4 * 1024 * 1024):
    raw = read_regular(path, cap)
    return {"path": str(path), "bytes": len(raw), "sha256": sha256(raw).hexdigest()}


def write_new(path, value):
    raw = canonical(value)
    require(len(raw) <= 1024 * 1024, "host receipt exceeds bound")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        rest = memoryview(raw)
        while rest:
            count = os.write(fd, rest)
            require(type(count) is int and 0 < count <= len(rest), "incomplete host receipt")
            rest = rest[count:]
        os.fsync(fd)
    finally:
        os.close(fd)


def timed(start, end, status, limit, child):
    return {"monotonic_start_ns": start, "monotonic_end_ns": end, "elapsed_ns": end - start,
            ("actual_exit_status" if child else "actual_return_status"): status, "late": end - start > limit * 1000000000,
            "process_completion_observed": type(status) is int, "reaped": child and type(status) is int}


def child_phase(name, argv, root, host, control, manifest, limit, raw_cap):
    outputs = [host / (name + ".stdout"), host / (name + ".stderr")]
    fds = [os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600) for path in outputs]
    start = monotonic_ns()
    process, pidfd, status, timeout = None, None, None, False
    require(callable(getattr(os, "pidfd_open", None)) and callable(getattr(signal, "pidfd_send_signal", None)),
            "required held-child handle APIs unavailable; no target started")
    try:
        process = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=fds[0], stderr=fds[1], close_fds=True)
        # The owned unreaped child PID cannot be recycled before this handle is
        # obtained. No raw-PID signal or lookup is used, including on timeout.
        handle_error = None
        try:
            pidfd = os.pidfd_open(process.pid, 0)
        except OSError as error:
            handle_error = type(error).__name__
        try:
            status = process.wait(timeout=max(0, limit - (monotonic_ns() - start) / 1000000000))
        except subprocess.TimeoutExpired:
            timeout = True
            if pidfd is not None:
                signal.pidfd_send_signal(pidfd, signal.SIGKILL)
            try:
                status = process.wait(timeout=1)
            except subprocess.TimeoutExpired:
                status = None
    finally:
        end = monotonic_ns()
        if pidfd is not None:
            os.close(pidfd)
        for fd in fds:
            os.fsync(fd)
            os.close(fd)
    receipt = {"kind": "ROOT_HOST_COMPLETION_RECEIPT", "source_commit": control, "profile_set": name,
               "argv": argv, "manifest_sha256": manifest, **timed(start, end, status, limit, True),
               "timeout_observed": timeout, "held_handle_error": handle_error, "raw_capture_complete": type(status) is int,
               "stdout": pin(outputs[0], raw_cap), "stderr": pin(outputs[1], raw_cap)}
    require(receipt["stdout"]["bytes"] + receipt["stderr"]["bytes"] <= raw_cap, "target raw cap exceeded")
    result = root / "reports/result.json"
    receipt["result"] = {key: value for key, value in pin(result).items() if key != "path"} if result.is_file() else None
    write_new(host / ("current-host.json" if name == "current" else "original-host.json"), receipt)
    return receipt


class BoundedText:
    def __init__(self, handle, shared):
        self.handle, self.shared = handle, shared

    def write(self, text):
        raw = text.encode("utf-8", "backslashreplace")
        require(self.shared[0] + len(raw) <= 16 * 1024, "aggregate raw cap exceeded")
        self.shared[0] += len(raw)
        return self.handle.write(text)

    def flush(self):
        self.handle.flush()


def main():
    # The measurement includes argv/plan reads, namespace creation and receipts;
    # interpreter startup before this module is not claimed to be timed.
    scope_start = monotonic_ns()
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--approved-plan-sha256", required=True)
    args = parser.parse_args()
    os.umask(0o077)
    raw = read_regular(args.plan)
    require(sha256(raw).hexdigest() == args.approved_plan_sha256, "unapproved host plan bytes")
    plan = json.loads(raw)
    control = plan["control_source_commit"]
    host = Path(plan["fresh_namespaces"]["host"])
    roots = {name: Path(plan["fresh_namespaces"][name]) for name in ("current", "original-scan", "aggregate")}
    require(len(set(roots.values()) | {host}) == 4 and all(path.is_absolute() and path.parent == Path("/workspace")
            and path.resolve() == path and not path.exists() for path in (*roots.values(), host)), "host namespaces must be fresh/distinct")
    os.sched_setaffinity(0, {min(os.sched_getaffinity(0))})
    host.mkdir(mode=0o700)
    phases = {}
    for name, limit, raw_cap in (("current", 60, 320 * 1024), ("original-scan", 45, 176 * 1024)):
        argv = plan["commands"][name]
        expected = [sys.executable, "-I", "-S", "-B", str(Path(__file__).resolve().with_name("matching_profile_once.py")),
            "--profile-set", name, "--run-root", str(roots[name]), "--source-commit", control,
            "--approved-manifest-sha256", plan["manifests"][name]["sha256"]]
        require(argv == expected, "host target argv differs from fixed invocation")
        phases[name] = child_phase(name, argv, roots[name], host, control, plan["manifests"][name]["sha256"], limit, raw_cap)
        require(phases[name]["actual_exit_status"] == 0 and phases[name]["reaped"] is True
                and phases[name]["late"] is False and phases[name]["timeout_observed"] is False
                and phases[name]["held_handle_error"] is None,
                "first target failure/late/unknown: stop, retain all raw, no retry")
    aggregate_start = monotonic_ns()
    context = {"kind": "ROOT_HOST_SEQUENCE_AGGREGATE_CONTEXT", "source_commit": control,
               "monotonic_start_ns": scope_start, "aggregate_start_ns": aggregate_start, "phases": phases}
    context_path = host / "aggregate-context.json"
    write_new(context_path, context)
    aggregate_argv = plan["commands"]["aggregate"]
    require(aggregate_argv[:4] == [sys.executable, "-I", "-S", "-B"]
            and aggregate_argv[4] == str(Path(__file__).resolve().with_name("matching_profile_aggregate.py"))
            and aggregate_argv[-2:] == ["--host-sequence-context", str(context_path)], "host aggregate argv differs")
    # Read-only aggregate executes in this host process: exactly two child
    # targets, no third subprocess and no module replacement inside a target.
    aggregate = runpy.run_path(aggregate_argv[4], run_name="matching_profile_host_readonly_aggregate")
    shared = [0]
    with open(host / "aggregate.stdout", "x", encoding="utf-8") as stdout, open(host / "aggregate.stderr", "x", encoding="utf-8") as stderr:
        with redirect_stdout(BoundedText(stdout, shared)), redirect_stderr(BoundedText(stderr, shared)):
            status = aggregate["main"](aggregate_argv[5:])
        stdout.flush()
        stderr.flush()
        os.fsync(stdout.fileno())
        os.fsync(stderr.fileno())
    aggregate_end = monotonic_ns()
    require(sum(value[channel]["bytes"] for value in phases.values() for channel in ("stdout", "stderr"))
            + shared[0] + 1024 <= 512 * 1024, "joint raw cap lacks reserved host completion output")
    phases["aggregate"] = {"argv": aggregate_argv, **timed(aggregate_start, aggregate_end, status, 10, False)}
    logical = {}
    for name, root, cap in (("current", roots["current"], 78 * 1024 * 1024),
                            ("original-scan", roots["original-scan"], 40 * 1024 * 1024),
                            ("aggregate", roots["aggregate"], 8 * 1024 * 1024), ("host", host, 2 * 1024 * 1024)):
        total = 0
        for path in root.rglob("*"):
            details = path.lstat()
            require(stat.S_ISREG(details.st_mode) or stat.S_ISDIR(details.st_mode), "nonregular host scope object")
            if stat.S_ISREG(details.st_mode):
                total += details.st_size
        require(total <= cap, "host final logical namespace cap exceeded")
        logical[name] = total
    require(logical["host"] + 1024 * 1024 <= 2 * 1024 * 1024
            and sum(logical.values()) + 1024 * 1024 <= 128 * 1024 * 1024,
            "joint logical cap lacks reserved final receipt capacity")
    end = monotonic_ns()
    sequence_timing = timed(scope_start, end, status, 120, False)
    sequence_timing["controller_return_status"] = sequence_timing.pop("actual_return_status")
    receipt = {"kind": "ROOT_HOST_SEQUENCE_COMPLETION_RECEIPT", "source_commit": control,
               **sequence_timing, "actual_outer_exit_status": None, "outer_exit_requires_caller_observation": True,
               "complete": status == 0, "phases": phases,
               "host_control_elapsed_ns": end - scope_start - sum(value["elapsed_ns"] for value in phases.values()),
               "logical_bytes_before_final_receipt": logical, "final_receipt_reserved_bytes": 1024 * 1024,
               "kernel_directory_quota_proven": False, "aggregate_raw_bytes": shared[0], "actual_affinity": sorted(os.sched_getaffinity(0)),
               "comparison": pin(roots["aggregate"] / "comparison.json"), "production_approved": False,
               "measurement_boundary": "main entry through all business/aggregate outputs durable; final receipt publication follows"}
    aggregate["validate_host_sequence"](receipt, control)
    final_path = host / "sequence-completion.json"
    write_new(final_path, receipt)
    # Include final receipt fsync in the exit-time guard. This trailing guard is
    # not silently added to the earlier timestamp; a late return exits nonzero.
    aggregate["validate_host_sequence"](json.loads(read_regular(final_path)), control)
    final_pin = pin(final_path)
    tail_end = monotonic_ns()
    require(tail_end - scope_start <= 120000000000
            and tail_end - scope_start - sum(value["elapsed_ns"] for value in phases.values()) <= 5000000000,
            "final host receipt publication exceeded total/control budget")
    print(json.dumps({"event": "END_MATCHING_PROFILE_HOST", "controller_return_status": 0,
                     "receipt": final_pin, "elapsed_ns_through_final_receipt_guard": tail_end - scope_start,
                     "requires_observed_outer_process_exit_zero": True}), flush=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(json.dumps({"event": "MATCHING_PROFILE_HOST_FAILED_OR_UNKNOWN", "error_type": type(error).__name__,
                          "message": str(error)[:400], "production_approved": False}), flush=True)
        raise SystemExit(1)
