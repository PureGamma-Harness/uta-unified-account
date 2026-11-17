"""One bounded diagnostic of the original observer; never a qualification gate.

Default: private, newly created synthetic WAL fixtures, no producer or service.
The optional live command calls Observer.sample once on an existing synthetic
job. Every read runs in a kernel read-only namespace with one fresh output bind.
No exception messages, SQL, command IDs, nonce, keys or absolute paths are saved.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import resource
import shutil
import signal
import sqlite3
import subprocess
import sys
import tempfile
import time

sys.dont_write_bytecode = True
try:
    from tools import managed_soak_observer as ro
except ModuleNotFoundError:
    import managed_soak_observer as ro

FROZEN_OBSERVER = "ce3045f66456c1592858d0297f90a9552c7500dd"
FLAGS = {"diagnostic_only": True, "eligibility_evidence": False,
         "modifies_existing_coverage": False, **ro.FLAGS}
_MODULES = {"managed_soak_observer.py", "managed_observer_finance.py", "diagnose_observer_read.py"}


class DiagnosticDeadline(Exception):
    pass


def sidecars(path):
    """Metadata only: never raw-open a database or its auxiliary inodes."""
    result = {}
    for name, suffix in (("wal_exists", "-wal"), ("shm_exists", "-shm")):
        try:
            Path(str(path) + suffix).stat()
            result[name] = True
        except FileNotFoundError:
            result[name] = False
        except OSError:
            result[name] = None
    return result


def safe_error(error):
    """Only typed metadata plus a one-way fingerprint of the existing message."""
    code, name = getattr(error, "sqlite_errorcode", None), getattr(error, "sqlite_errorname", None)
    frames = []
    cursor = error.__traceback__
    while cursor is not None:
        module = Path(cursor.tb_frame.f_code.co_filename).name
        function = cursor.tb_frame.f_code.co_name
        if module in _MODULES and re.fullmatch(r"[A-Za-z_][A-Za-z_0-9]*", function):
            frames.append({"module": module, "function": function, "line": cursor.tb_lineno})
        cursor = cursor.tb_next
    return {"error_type": type(error).__name__,
            "error_digest": sha256(str(error).encode()).hexdigest(),
            "sqlite_errorcode": code if type(code) is int else None,
            "sqlite_errorname": name if isinstance(name, str) and re.fullmatch(r"SQLITE_[A-Z_]+", name) else None,
            "frames": frames[-12:]}


def require_namespace(output, *read_paths):
    if not ro.safe_standard_descriptors():
        raise ValueError("pipe_standard_descriptors_required")
    if any(not (os.statvfs(path).f_flag & os.ST_RDONLY) for path in read_paths):
        raise ValueError("kernel_readonly_namespace_required")
    if os.statvfs(output).f_flag & os.ST_RDONLY:
        raise ValueError("private_output_must_be_writable")


def original_read(role, path, events, callback):
    event = {"role": role, "phase": "original_readonly", "before": sidecars(path)}
    events.append(event)
    started = time.monotonic()
    try:
        with ro.readonly(path, cold=False) as connection:
            callback(connection)
        event["outcome"] = "read_completed"
    except Exception as error:
        event.update(outcome="read_failed", **safe_error(error))
    finally:
        event.update(after=sidecars(path), elapsed_seconds=time.monotonic() - started)


def synthetic_sample(fixtures):
    events = []
    original_read("synthetic_live_wal", fixtures / "live.sqlite3", events,
                  lambda connection: connection.execute("SELECT value FROM facts").fetchone())
    original_read("synthetic_cold_wal", fixtures / "cold.sqlite3", events,
                  lambda connection: connection.execute("SELECT value FROM facts").fetchone())
    # Normal SQLite behavior on our closed, disposable fixture only. This is
    # intentionally not used for any live job or as an observer fallback.
    target = fixtures / "cold.sqlite3"
    event = {"role": "synthetic_cold_wal", "phase": "plain_sqlite_mode_ro",
             "before": sidecars(target)}
    events.append(event)
    connection = None
    started = time.monotonic()
    try:
        connection = sqlite3.connect(target.as_uri() + "?mode=ro", uri=True, timeout=1)
        connection.execute("SELECT value FROM facts").fetchone()
        event["outcome"] = "read_completed"
    except sqlite3.Error as error:
        event.update(outcome="read_failed", **safe_error(error))
    finally:
        if connection is not None:
            connection.close()
        event.update(after=sidecars(target), elapsed_seconds=time.monotonic() - started)
    return {"mode": "private_synthetic_fixtures", "events": events}


def live_sample(args):
    """Call the exact original sample; wrap only its read context for metadata."""
    if not ro.process_identity(args.driver_pid, args.driver_birth)["alive"]:
        raise ValueError("original_live_driver_identity_required")
    if ro.load_json(args.job / "progress.json")["status"] == "completed":
        raise ValueError("live_job_required_no_cold_shortcut")
    original = ro.readonly
    paths = {args.job / "checkpoint.sqlite3": "checkpoint",
             args.job / "managed/router.sqlite3": "router",
             args.job / "managed/shard-0000.sqlite3": "shard"}
    events = []

    @contextmanager
    def observed_readonly(path, *, cold=False):
        if cold:
            raise ValueError("live_diagnostic_disallows_cold_immutable")
        target = Path(path)
        role = paths.get(target)
        if role is None:
            raise ValueError("unexpected_database_role")
        event = {"role": role, "phase": "original_readonly", "before": sidecars(target)}
        events.append(event)
        started = time.monotonic()
        try:
            with original(target, cold=False) as connection:
                yield connection
            event["outcome"] = "read_completed"
        except Exception as error:
            event.update(outcome="read_failed", **safe_error(error))
            raise
        finally:
            event.update(after=sidecars(target), elapsed_seconds=time.monotonic() - started)

    ro.readonly = observed_readonly
    try:
        observer = ro.Observer(args.job, args.output, args.source, args.frozen_commit,
                               args.driver_pid, args.driver_birth)
        sample = observer.sample()
        # Financial payloads and original command IDs are deliberately dropped.
        return {"mode": "one_live_original_observer_sample", "outcome": "sample_returned",
                "logical_point": sample["logical_point"], "events": events}
    except Exception as error:
        return {"mode": "one_live_original_observer_sample", "outcome": "sample_failed",
                "events": events, **safe_error(error)}
    finally:
        ro.readonly = original


def child(args):
    require_namespace(args.output, *(p for p in (args.fixtures, args.job, args.source) if p))
    resource.setrlimit(resource.RLIMIT_AS, (512 * 1024**2, 512 * 1024**2))
    resource.setrlimit(resource.RLIMIT_CPU, (8, 8))
    signal.signal(signal.SIGALRM, lambda *_: (_ for _ in ()).throw(DiagnosticDeadline()))
    signal.setitimer(signal.ITIMER_REAL, 8)
    started = time.monotonic()
    try:
        result = synthetic_sample(args.fixtures) if args.mode == "synthetic" else live_sample(args)
    except Exception as error:
        result = {"outcome": "diagnostic_failed", **safe_error(error)}
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
    result.update(format=1, synthetic=True, redacted=True,
                  observer_commit=FROZEN_OBSERVER, elapsed_seconds=time.monotonic() - started,
                  wall_ns=time.time_ns(), kernel_readonly_enforced=True,
                  observer_code_sha256={path.name: sha256(path.read_bytes()).hexdigest() for path in
                      (Path(ro.__file__), Path(ro.__file__).with_name("managed_observer_finance.py"))}, **FLAGS)
    print(ro.canonical(result), flush=True)
    return 0


def launch(args):
    output = args.output.resolve()
    if args.mode == "live":
        if any(value is None for value in (args.job, args.source, args.frozen_commit, args.driver_pid, args.driver_birth)):
            raise ValueError("explicit_live_job_source_commit_and_driver_required")
        job, source = args.job.resolve(), args.source.resolve()
        if output == job or output.is_relative_to(job) or job.is_relative_to(output) or output.is_relative_to(source):
            raise ValueError("fresh_external_output_required")
    # Never reuse the existing job/observer output, even if it is private.
    output.mkdir(mode=0o700, parents=False, exist_ok=False)
    fixture_context, writer = None, None
    try:
        forwarded = ["--mode", args.mode, "--output", str(output), "--child"]
        if args.mode == "synthetic":
            fixture_context = tempfile.TemporaryDirectory(prefix="uta-private-read-fixture-", dir=output.parent)
            fixtures = Path(fixture_context.name)
            for name in ("cold", "live"):
                connection = sqlite3.connect(fixtures / (name + ".sqlite3"))
                connection.execute("PRAGMA journal_mode=WAL")
                connection.execute("CREATE TABLE facts(value INTEGER)")
                connection.execute("INSERT INTO facts VALUES(1)")
                connection.commit()
                if name == "live":
                    writer = connection
                else:
                    connection.close()
            forwarded.extend(["--fixtures", str(fixtures)])
        else:
            forwarded.extend(["--job", str(job), "--source", str(source), "--frozen-commit", args.frozen_commit,
                              "--driver-pid", str(args.driver_pid), "--driver-birth", args.driver_birth])
        executable = shutil.which("bwrap")
        if not executable:
            raise ValueError("bwrap_required_no_fallback")
        command = [executable, "--die-with-parent", "--ro-bind", "/", "/", "--dev", "/dev",
                   "--bind", str(output), str(output), "--", sys.executable, "-B",
                   str(Path(__file__).resolve()), *forwarded]
        started = time.monotonic()
        try:
            run = subprocess.run(command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                 close_fds=True, timeout=9.5)
            result = json.loads(run.stdout) if run.returncode == 0 else {
                "outcome": "diagnostic_child_failed", "exit_code": run.returncode}
            result.update(child_stderr_sha256=sha256(run.stderr).hexdigest(), child_stderr_bytes=len(run.stderr))
        except subprocess.TimeoutExpired:
            result = {"outcome": "diagnostic_timeout", "redacted": True, "synthetic": True, **FLAGS}
        result["bounded_wall_seconds"] = time.monotonic() - started
        ro.private_write(output / "diagnostic.json", (ro.canonical(result) + "\n").encode())
        print(ro.canonical(result))
        return 0 if result.get("kernel_readonly_enforced") else 1
    finally:
        if writer is not None:
            writer.close()
        if fixture_context is not None:
            fixture_context.cleanup()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("synthetic", "live"), default="synthetic")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--job", type=Path)
    parser.add_argument("--source", type=Path)
    parser.add_argument("--frozen-commit")
    parser.add_argument("--driver-pid", type=int)
    parser.add_argument("--driver-birth")
    parser.add_argument("--fixtures", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--child", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    return child(args) if args.child else launch(args)


if __name__ == "__main__":
    raise SystemExit(main())
