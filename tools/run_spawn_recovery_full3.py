"""Prepare by default; --execute needs root GO for one detached full-QA matrix.

The frozen source's standard run_validation.py remains the test runner. This
external supervisor changes neither tests nor financial code nor their limits.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha1, sha256
import json
import os
from pathlib import Path
import select
import shutil
import signal
import subprocess
import sys
import time

SOURCE = Path("/workspace/uta-stopped-owner-gate")
COMMIT = "6b7d473c0fbf92b17c146140c88eb2c25d38dce1"
OUTPUT = Path("/workspace/uta-spawn-full3-validation/6b7d473-first")
FLOOR = 17_448_304_640
RESERVE = 256 * 1024**2
RUNTIME_SECONDS = 900
MATRIX_SECONDS = 2730
CPU = 4
EXPECTED_TESTS = 1813
PROTECTED = {4471, 8784, 310035, 310039, 310266, 310269}
RUNTIMES = (
    ("python310", "/tmp/uta-python310/cpython-3.10.22-linux-x86_64-gnu/bin/python3.10", "473dd9c9a03e0b41ba35f986afd9bb13162d7ac7aa5d44d4dfdf75a2e19c9989"),
    ("python312", "/opt/codex/runtimes/codex-primary-runtime/dependencies/python/bin/python", "fa67443527ed9647f760d807e2a38f26340757123e643c4639cf273ed15d5ea7"),
    ("python313-sqlite346", "/usr/bin/python3.13", "889c603f0d17cb54060951bcf4c4f9b8c9ebd9e52b392c70209bbb9755d797d9"),
)
DIRECTORIES = ("uta", "tests", "formal", "tools", "benchmarks", "scripts")


def git(*arguments):
    return subprocess.check_output(["git", *arguments], cwd=SOURCE, text=True).strip()


def digest(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    with Path(path).open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())


def identity(pid):
    tail = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
    return {"pid": pid, "birth_ticks": int(tail[19]), "state": tail[0],
            "parent": int(tail[1]), "group": int(tail[2]), "session": int(tail[3]),
            "boot_id": Path("/proc/sys/kernel/random/boot_id").read_text().strip()}


def same_birth(left, right):
    return all(left[key] == right[key] for key in ("pid", "birth_ticks", "boot_id"))


def binary_pins():
    rows = []
    for label, executable, expected in RUNTIMES:
        actual = digest(Path(executable).resolve())
        if actual != expected:
            raise RuntimeError("runtime binary pin moved")
        rows.append({"label": label, "executable": executable,
                     "resolved": str(Path(executable).resolve()), "sha256": actual})
    return rows


def source_pin():
    if git("rev-parse", "HEAD") != COMMIT or git("status", "--porcelain", "--untracked-files=all"):
        raise RuntimeError("frozen QA checkout moved or became dirty")
    full, selected = {}, {}
    for line in git("ls-tree", "-r", COMMIT, "--", *DIRECTORIES, "pyproject.toml", "MANIFEST.in", "LICENSE").splitlines():
        header, name = line.split("\t", 1)
        path = SOURCE / name
        if not path.is_file() or path.is_symlink():
            raise RuntimeError("tracked QA input is not fully materialized")
        data = path.read_bytes()
        if sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest() != header.split()[2]:
            raise RuntimeError("tracked QA input differs from source Git blob")
        full[name] = sha256(data).hexdigest()
        if name.endswith(".py") or name.startswith("tests/fixtures/") or \
                name in {"pyproject.toml", "MANIFEST.in", "LICENSE"}:
            selected[name] = full[name]
    # Match the standard runner's selected-file inventory, including unexpected
    # selected files instead of silently ignoring a changed sparse checkout.
    actual = {p.relative_to(SOURCE).as_posix() for folder in DIRECTORIES
              for p in (SOURCE / folder).rglob("*.py")}
    actual.update(p.relative_to(SOURCE).as_posix() for p in (SOURCE / "tests/fixtures").rglob("*") if p.is_file())
    actual.update(name for name in ("pyproject.toml", "MANIFEST.in", "LICENSE") if (SOURCE / name).exists())
    if actual != set(selected):
        raise RuntimeError("standard QA selected input inventory differs from frozen Git")
    return {"commit": COMMIT, "tree": git("rev-parse", COMMIT + "^{tree}"),
            "all_tracked_QA_input_sha256": full, "standard_runner_source_sha256": selected,
            "run_validation_sha256": full["tools/run_validation.py"],
            "owned_cleanup_helper_sha256": full["tools/run_managed_variants.py"],
            "orphan_reaper_source_sha256": full["tests/test_durable_process.py"]}


def commands():
    return [[executable, "-B", str(SOURCE / "tools/run_validation.py"),
             "--output", str(OUTPUT / label)] for label, executable, _ in RUNTIMES]


def plan():
    if OUTPUT.exists():
        raise RuntimeError("once-only output already exists")
    variables = sorted(key for key in os.environ if key.startswith("UTA_"))
    if variables:
        raise RuntimeError("inherited UTA test overrides must be absent")
    free = shutil.disk_usage("/workspace").free
    if free < FLOOR + RESERVE:
        raise RuntimeError("resource admission denied")
    if CPU not in os.sched_getaffinity(0):
        raise RuntimeError("QA CPU unavailable")
    return {"source": source_pin(), "runtimes": binary_pins(), "commands": commands(),
            "cpu": CPU, "per_runtime_seconds": RUNTIME_SECONDS, "matrix_seconds": MATRIX_SECONDS,
            "free_bytes": free, "floor_bytes": FLOOR, "reserve_bytes": RESERVE,
            "expected_tests_per_runtime": EXPECTED_TESTS,
            "environment": {"PYTHONDONTWRITEBYTECODE": "1", "PYTHONPATH": "removed", "UTA_overrides": "must be absent"},
            "supervisor_sha256": digest(__file__), "execution_permitted_by_prepare": False,
            "production_approved": False, "original_ci_cause_proven": False}


def group_signal(process, original, pidfd, sig, helpers):
    current = identity(process.pid)
    if not same_birth(current, original) or current["group"] != current["session"] or current["group"] != process.pid:
        raise RuntimeError("lost exact unreaped QA session identity")
    if any(helpers._same_group(pid, process.pid) for pid in PROTECTED | helpers.PROTECTED):
        raise RuntimeError("protected process observed in QA group")
    # The pidfd and unreaped leader remain open across the group signal.
    os.killpg(process.pid, sig)


def validate_report(report, worker, pin, code):
    counters = ("tests_run", "failures", "errors", "skipped", "expected_failures", "unexpected_successes")
    typed = (type(code) is int and type(report.get("worker_exit_code")) is int
             and all(type(row.get(key)) is int for row in (report, worker) for key in counters))
    return (typed and code == 0 and report.get("passed") is True and report.get("code_commit") == COMMIT
            and report.get("tests_run") == EXPECTED_TESTS
            and all(report.get(key) == 0 for key in ("failures", "errors", "skipped", "expected_failures", "unexpected_successes"))
            and all(report.get(key) is True for key in ("source_unchanged", "tracked_source_clean_before", "tracked_source_clean_after"))
            and report.get("source_sha256") == report.get("source_sha256_after") == pin["standard_runner_source_sha256"]
            and report.get("worker_exit_code") == 0 and report.get("unittest_passed") is True
            and worker.get("unittest_passed") is True and worker.get("tests_run") == EXPECTED_TESTS
            and all(worker.get(key) == report.get(key) for key in ("failures", "errors", "skipped", "expected_failures", "unexpected_successes")))


def finalize_child(process, original, pidfd, helpers):
    """Always attempt direct-child reap and FD close after a group error."""
    errors = []
    try:
        if process.returncode is None:
            try:
                if original is not None and pidfd is not None:
                    group_signal(process, original, pidfd, signal.SIGKILL, helpers)
                else:
                    process.kill()  # Our own never-reaped direct child only.
            except BaseException as error:
                errors.append(type(error).__name__)
            try:
                process.wait(timeout=2)
            except BaseException as error:
                errors.append(type(error).__name__)
                try:
                    process.kill()
                    process.wait(timeout=2)
                except BaseException as second:
                    errors.append(type(second).__name__)
    finally:
        if pidfd is not None:
            try:
                os.close(pidfd)
            except BaseException as error:
                errors.append(type(error).__name__)
    return {"leader_reaped": process.returncode is not None, "cleanup_error_types": errors}


def run_one(index, admission, matrix_deadline, helpers, orphan_reaper):
    label, executable, _ = RUNTIMES[index]
    command = admission["commands"][index]
    original_pin = admission["source"]
    if source_pin() != original_pin or binary_pins() != admission["runtimes"]:
        raise RuntimeError("inputs moved before runtime")
    if shutil.disk_usage("/workspace").free < FLOOR + RESERVE:
        raise RuntimeError("resource admission lost before runtime")
    if matrix_deadline - time.monotonic() < RUNTIME_SECONDS + 10:
        raise RuntimeError("insufficient unchanged runtime budget")
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    env.pop("PYTHONPATH", None)
    started = time.monotonic()
    reason, code, original, process, pidfd = None, None, None, None, None
    raw_path = OUTPUT / (label + "-launcher.txt")
    with orphan_reaper(), raw_path.open("x", encoding="utf-8") as raw:
        process = subprocess.Popen(command, cwd=SOURCE, env=env, stdin=subprocess.DEVNULL,
                                   stdout=raw, stderr=subprocess.STDOUT, start_new_session=True)
        try:
            original = identity(process.pid)
            pidfd = os.pidfd_open(process.pid)
            if (not same_birth(original, identity(process.pid)) or original["pid"] in PROTECTED
                    or original["group"] != original["session"] or original["group"] != process.pid
                    or os.sched_getaffinity(process.pid) != {CPU}):
                raise RuntimeError("QA child identity or CPU ACK unavailable")
            save(OUTPUT / (label + "-actual-Popen.json"), {"identity": original, "command": command,
                 "pidfd_used": True, "cpu_ids": [CPU], "affinity_observed": True})
            while not helpers._pidfd_ready(pidfd):
                if time.monotonic() - started >= RUNTIME_SECONDS:
                    reason = "RUNTIME_TIMEOUT_UNKNOWN"
                elif time.monotonic() >= matrix_deadline - 10:
                    reason = "MATRIX_TIMEOUT_UNKNOWN"
                elif shutil.disk_usage("/workspace").free < FLOOR:
                    reason = "RESOURCE_FLOOR_LOST_UNKNOWN"
                elif sum(p.stat().st_size for p in OUTPUT.rglob("*") if p.is_file()) > 64 * 1024**2:
                    reason = "OUTPUT_CAP_UNKNOWN"
                if reason:
                    break
                select.poll().poll(100)
            if helpers._group_members(process.pid, exclude=process.pid) and reason is None:
                reason = "LIVE_DESCENDANTS_AFTER_LEADER_EXIT_UNKNOWN"
            if reason is not None:
                group_signal(process, original, pidfd, signal.SIGTERM, helpers)
                deadline = time.monotonic() + 2
                while time.monotonic() < deadline and (not helpers._pidfd_ready(pidfd) or helpers._group_members(process.pid, exclude=process.pid)):
                    select.poll().poll(20)
                if not helpers._pidfd_ready(pidfd) or helpers._group_members(process.pid, exclude=process.pid):
                    group_signal(process, original, pidfd, signal.SIGKILL, helpers)
            deadline = time.monotonic() + 2
            while not helpers._pidfd_ready(pidfd) and time.monotonic() < deadline:
                select.poll().poll(10)
            if not helpers._pidfd_ready(pidfd):
                raise RuntimeError("owned QA leader did not exit")
            if helpers._group_members(process.pid, exclude=process.pid):
                raise RuntimeError("owned QA group still has live descendants")
            code = process.wait(timeout=2)
            raw.flush()
            os.fsync(raw.fileno())
        finally:
            cleanup = finalize_child(process, original, pidfd, helpers)
        if not cleanup["leader_reaped"] or cleanup["cleanup_error_types"]:
            raise RuntimeError("QA child cleanup was incomplete or required an error fallback")
    report_path, worker_path = OUTPUT / label / "summary.json", OUTPUT / label / "worker-result.json"
    report = json.loads(report_path.read_text()) if report_path.exists() else {}
    worker = json.loads(worker_path.read_text()) if worker_path.exists() else {}
    files = [p for p in (report_path, worker_path, OUTPUT / label / "unittest.txt", raw_path) if p.exists()]
    stable = source_pin() == original_pin and binary_pins() == admission["runtimes"]
    passed = reason is None and stable and validate_report(report, worker, original_pin, code)
    if report and digest(OUTPUT / label / "unittest.txt") != report.get("test_log_sha256"):
        passed = False
    outcome = {"label": label, "command": command, "identity": original,
               "exit_code": code, "watchdog_reason": reason, "leader_reaped": True,
               "pidfd_used": True, "source_and_binary_unchanged": stable,
               "elapsed_seconds": time.monotonic() - started,
               "passed": passed, "outcome": "PASS" if passed else "UNKNOWN" if reason or not report else "FAIL",
               "originals": {str(p.relative_to(OUTPUT)): {"bytes": p.stat().st_size, "sha256": digest(p)} for p in files},
               "production_approved": False, "original_ci_cause_proven": False}
    save(OUTPUT / (label + "-first-outcome.json"), outcome)
    return outcome


def supervise(go_fd):
    started = time.monotonic()
    os.sched_setaffinity(0, {CPU})
    pid = os.getpid()
    # A visible partially written/fsync-failed ACK is never an execution GO.
    # The parent sends this one-byte gate only after every launch record and
    # parent stream close has returned success; EOF/dead parent means no QA.
    try:
        gate = select.poll()
        gate.register(go_fd, select.POLLIN | select.POLLHUP)
        if not gate.poll(2000) or os.read(go_fd, 1) != b"G":
            raise RuntimeError("no confirmed detached-launch GO")
    finally:
        os.close(go_fd)
    ack_path = OUTPUT / "supervisor-launch.json"
    ack = json.loads(ack_path.read_text())
    if not same_birth(ack["identity"], identity(pid)) or identity(pid)["group"] != pid or identity(pid)["session"] != pid:
        raise RuntimeError("detached supervision launch proof failed")
    admission = json.loads((OUTPUT / "admission.json").read_text())
    if source_pin() != admission["source"] or digest(__file__) != admission["supervisor_sha256"]:
        raise RuntimeError("supervisor inputs changed after admission")
    sys.path.insert(0, str(SOURCE))
    from tools import run_managed_variants as helpers
    from tests.test_durable_process import _orphan_reaper
    save(OUTPUT / "supervisor-ready.json", {"identity": identity(pid), "cpu_ids": sorted(os.sched_getaffinity(0)),
         "detached": True, "input_pin_verified": True})
    records, error = [], None
    try:
        for index in range(3):
            try:
                record = run_one(index, admission, started + MATRIX_SECONDS, helpers, _orphan_reaper)
            except BaseException as failure:
                label = RUNTIMES[index][0]
                record = {"label": label, "passed": False, "outcome": "UNKNOWN",
                          "error_type": type(failure).__name__, "cleanup_confirmed": False,
                          "production_approved": False, "original_ci_cause_proven": False}
                if not (OUTPUT / (label + "-first-outcome.json")).exists():
                    save(OUTPUT / (label + "-first-outcome.json"), record)
            records.append(record)
            if not record["passed"]:
                break
    except BaseException as failure:
        error = type(failure).__name__
    elapsed = time.monotonic() - started
    complete = len(records) == 3 and all(row["passed"] for row in records) and elapsed <= MATRIX_SECONDS
    save(OUTPUT / "matrix-summary.json", {"source_commit": COMMIT, "records": records,
         "all_three_first_full_runs_passed": complete, "error_type": error,
         "elapsed_seconds": elapsed, "matrix_budget_seconds": MATRIX_SECONDS,
         "production_approved": False, "original_ci_cause_proven": False})
    return 0 if complete else 1


def launch_detached(admission):
    read_fd, write_fd = os.pipe()
    process = original = pidfd = None
    out = err = None
    released = False
    try:
        out = (OUTPUT / "supervisor.stdout").open("xb")
        err = (OUTPUT / "supervisor.stderr").open("xb")
        process = subprocess.Popen([sys.executable, "-B", str(Path(__file__).resolve()),
                  "--supervise", "--go-fd", str(read_fd)], pass_fds=(read_fd,),
                  stdin=subprocess.DEVNULL, stdout=out, stderr=err, start_new_session=True,
                  env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
        pidfd = os.pidfd_open(process.pid)
        original = identity(process.pid)
        if not same_birth(original, identity(process.pid)) or original["group"] != original["session"] or original["session"] != process.pid:
            raise RuntimeError("detached supervisor identity unavailable")
        # Close parent handles and durably record identity BEFORE releasing GO.
        out.close()
        out = None
        err.close()
        err = None
        save(OUTPUT / "supervisor-launch.json", {"identity": original, "argv": process.args,
             "detached": True, "expected_cpu_ids": [CPU], "go_requires_pipe_byte": True})
        if os.write(write_fd, b"G") != 1:
            raise RuntimeError("detached supervisor GO was not written")
        released = True
        # No record/print/stream operation after release is allowed to revoke
        # the authorized persistent supervisor. Query its saved launch ID.
        return original
    except BaseException as error:
        cleanup = {"leader_reaped": False, "cleanup_error_types": []}
        if process is not None and not released:
            try:
                if pidfd is not None:
                    signal.pidfd_send_signal(pidfd, signal.SIGKILL)
                else:
                    process.kill()
            except BaseException as failure:
                cleanup["cleanup_error_types"].append(type(failure).__name__)
            try:
                process.wait(timeout=2)
                cleanup["leader_reaped"] = True
            except BaseException as failure:
                cleanup["cleanup_error_types"].append(type(failure).__name__)
        try:
            save(OUTPUT / "launch-unknown.json", {"outcome": "UNKNOWN", "go_released": released,
                 "error_type": type(error).__name__, "identity": original, "cleanup": cleanup})
        except BaseException:
            pass  # A storage failure cannot release the still-closed GO gate.
        raise
    finally:
        for stream in (out, err):
            if stream is not None:
                try:
                    stream.close()
                except BaseException:
                    pass
        for descriptor in (read_fd, write_fd, pidfd):
            if descriptor is not None:
                try:
                    os.close(descriptor)
                except OSError:
                    pass


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--supervise", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--go-fd", type=int, help=argparse.SUPPRESS)
    parser.add_argument("--prepare-output", type=Path)
    args = parser.parse_args()
    if args.supervise:
        try:
            return supervise(args.go_fd)
        except BaseException as failure:
            save(OUTPUT / "supervisor-error.json", {"error_type": type(failure).__name__, "outcome": "UNKNOWN"})
            if not (OUTPUT / "matrix-summary.json").exists():
                save(OUTPUT / "matrix-summary.json", {"source_commit": COMMIT,
                     "all_three_first_full_runs_passed": False, "outcome": "UNKNOWN",
                     "error_type": type(failure).__name__, "production_approved": False})
            return 1
    admission = plan()
    if not args.execute:
        if args.prepare_output:
            save(args.prepare_output, admission)
        print(json.dumps({"prepare_only": True, "selected_input_count": len(admission["source"]["standard_runner_source_sha256"]),
                          "all_QA_input_count": len(admission["source"]["all_tracked_QA_input_sha256"]),
                          "supervisor_sha256": admission["supervisor_sha256"], "commands": admission["commands"]}, indent=2))
        return 0
    os.umask(0o077)
    OUTPUT.mkdir(parents=True, mode=0o700, exist_ok=False)
    save(OUTPUT / "admission.json", admission)
    launch_detached(admission)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
