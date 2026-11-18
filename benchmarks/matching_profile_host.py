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
            ("process_completion_observed" if child else "function_completion_observed"): type(status) is int,
            "reaped": child and type(status) is int}


def remaining_budget(scope_start, phases):
    now = monotonic_ns()
    used = sum(value["elapsed_ns"] for value in phases.values())
    require(now - scope_start <= 120000000000 and 0 <= now - scope_start - used <= 5000000000,
            "host/total budget exhausted before next phase; no new target started")


PROTECTED_PIDS = frozenset({4471,8784,122905,122907,123007,123009,310035,310039,310266,310269})


def child_phase(name, argv, root, host, control, manifest, limit, raw_cap, scope_start, completed_phases):
    require(callable(getattr(os, "pidfd_open", None)) and callable(getattr(signal, "pidfd_send_signal", None)),
            "required held-child handle APIs unavailable; no target started")
    remaining_budget(scope_start, completed_phases)
    outputs = [host / (name + ".stdout"), host / (name + ".stderr")]
    fds, gate_read, gate_write = [], None, None
    process, pidfd, status, timeout = None, None, None, False
    gate_released, handle_ready = False, False
    errors = {key: None for key in ("start_error", "owner_record_error", "held_handle_error", "signal_error", "gate_error", "cleanup_error")}
    start = monotonic_ns()
    try:
        fds = [os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600) for path in outputs]
        gate_read, gate_write = os.pipe2(os.O_CLOEXEC)
        remaining_budget(scope_start, completed_phases)
        try:
            process = subprocess.Popen(argv, stdin=gate_read, stdout=fds[0], stderr=fds[1], close_fds=True)
        except Exception as error:
            errors["start_error"] = type(error).__name__
        os.close(gate_read)
        gate_read = None
        if process is not None:
            try:
                write_new(host / (name + "-owned-child.json"), {"kind": "NEW_OWNED_GATED_CHILD_FACT",
                    "source_commit": control, "profile_set": name, "argv": argv, "owned_child_pid": process.pid,
                    "gate": "stdin_fd0_pipe_closed_until_release", "gate_released": False,
                    "monotonic_start_ns": start, "actual_exit_status": None})
            except Exception as error:
                errors["owner_record_error"] = type(error).__name__
            if process.pid in PROTECTED_PIDS:
                errors["held_handle_error"] = "PROTECTED_PID_COLLISION_NO_HANDLE_OR_SIGNAL"
            elif errors["owner_record_error"] is None:
                try:
                    pidfd = os.pidfd_open(process.pid, 0)
                    handle_ready = True
                    write_new(host / (name + "-held-handle.json"), {"kind": "OWNED_CHILD_HELD_PIDFD_FACT",
                        "source_commit": control, "profile_set": name, "owned_child_pid": process.pid,
                        "held_pidfd": pidfd, "gate_released": False})
                except Exception as error:
                    errors["held_handle_error"] = type(error).__name__
            if handle_ready and all(value is None for value in errors.values()):
                try:
                    before_release = monotonic_ns()
                    require(before_release - start <= limit * 1000000000
                            and before_release - scope_start <= 120000000000,
                            "known phase/total deadline exhausted before business gate release")
                    require(os.write(gate_write, b"G") == 1, "incomplete one-byte startgate release")
                    gate_released = True
                except Exception as error:
                    errors["gate_error"] = type(error).__name__
        # Any pre-release failure closes the gate: EOF makes the script exit
        # before UTA/business/SQL. Numeric collision never opens a pidfd.
        os.close(gate_write)
        gate_write = None
        if process is not None:
            try:
                status = process.wait(timeout=max(0, limit - (monotonic_ns() - start) / 1000000000))
            except subprocess.TimeoutExpired:
                timeout = True
                if gate_released and pidfd is not None and process.pid not in PROTECTED_PIDS:
                    try:
                        signal.pidfd_send_signal(pidfd, signal.SIGKILL)
                    except Exception as error:
                        errors["signal_error"] = type(error).__name__
    except Exception as error:
        errors["cleanup_error"] = type(error).__name__
    finally:
        for descriptor in (gate_read, gate_write):
            if descriptor is not None:
                try:
                    os.close(descriptor)
                except Exception as error:
                    errors["cleanup_error"] = type(error).__name__
        # Always try to reap the child we created, even after handle/signal/raw
        # failures. Never substitute a naked-PID signal or query an old process.
        if process is not None and status is None:
            try:
                status = process.wait(timeout=1)
            except Exception as error:
                errors["cleanup_error"] = type(error).__name__
        end = monotonic_ns()
        if pidfd is not None:
            try:
                os.close(pidfd)
            except Exception as error:
                errors["cleanup_error"] = type(error).__name__
        for descriptor in fds:
            try:
                os.fsync(descriptor)
            except Exception as error:
                errors["cleanup_error"] = type(error).__name__
            finally:
                os.close(descriptor)
    receipt = {"kind": "ROOT_HOST_COMPLETION_RECEIPT", "source_commit": control, "profile_set": name,
        "argv": argv, "manifest_sha256": manifest, **timed(start, end, status, limit, True), **errors,
        "timeout_observed": timeout, "owned_child_pid": process.pid if process is not None else None,
        "gate_released_once": gate_released, "held_pidfd_ready_before_gate": handle_ready,
        "raw_capture_complete": type(status) is int,
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
        require(self.shared[0] + len(raw) <= 15 * 1024, "aggregate raw cap exceeded")
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
            "--host-start-gate-stdin", "--profile-set", name, "--run-root", str(roots[name]), "--source-commit", control,
            "--approved-manifest-sha256", plan["manifests"][name]["sha256"]]
        require(argv == expected, "host target argv differs from fixed invocation")
        phases[name] = child_phase(name, argv, roots[name], host, control, plan["manifests"][name]["sha256"],
                                   limit, raw_cap, scope_start, phases)
        require(phases[name]["actual_exit_status"] == 0 and phases[name]["reaped"] is True
                and phases[name]["late"] is False and phases[name]["timeout_observed"] is False
                and phases[name]["gate_released_once"] is True and phases[name]["held_pidfd_ready_before_gate"] is True
                and all(phases[name][key] is None for key in ("start_error", "owner_record_error", "held_handle_error",
                                                             "signal_error", "gate_error", "cleanup_error")),
                "first target failure/late/unknown: stop, retain all raw, no retry")
    remaining_budget(scope_start, phases)
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


HOST_RAW_RESERVED = 0
HOST_RAW_FAILED = False


class HostRaw:
    encoding, errors = "utf-8", "backslashreplace"

    def __init__(self, descriptor):
        self.descriptor = descriptor

    def write(self, value):
        global HOST_RAW_RESERVED, HOST_RAW_FAILED
        raw = value.encode(self.encoding, self.errors)
        if HOST_RAW_FAILED or HOST_RAW_RESERVED + len(raw) > 1024:
            HOST_RAW_FAILED = True
            raise RuntimeError("host raw budget exhausted; unwind owned-child cleanup")
        HOST_RAW_RESERVED += len(raw)
        remaining = memoryview(raw)
        while remaining:
            try:
                count = os.write(self.descriptor, remaining)
            except BaseException as error:
                HOST_RAW_FAILED = True
                raise RuntimeError("host raw write failed; unwind owned-child cleanup") from error
            if type(count) is not int or not 0 < count <= len(remaining):
                HOST_RAW_FAILED = True
                raise RuntimeError("host raw write failed; unwind owned-child cleanup")
            remaining = remaining[count:]
        return len(value)

    def flush(self):
        pass


if __name__ == "__main__":
    sys.stdout = sys.__stdout__ = HostRaw(1)
    sys.stderr = sys.__stderr__ = HostRaw(2)
    try:
        raise SystemExit(main())
    except BaseException as error:
        if isinstance(error, SystemExit) and error.code == 0:
            raise
        try:
            print(json.dumps({"event": "MATCHING_PROFILE_HOST_FAILED_OR_UNKNOWN", "error_type": type(error).__name__,
                              "message": str(error)[:200], "production_approved": False}), flush=True)
        except BaseException:
            pass
        raise SystemExit(125 if HOST_RAW_FAILED else 1)
