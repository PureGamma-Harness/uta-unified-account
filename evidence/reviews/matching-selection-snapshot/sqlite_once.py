"""Unexecuted once-driver; a manifest or CLI flag is not execution approval."""
import os
from pathlib import Path
import sys
from time import monotonic

STARTED = monotonic()
DEADLINE = STARTED + 30
ROOT = Path(__file__).resolve().parents[3]
RAW_CAP = 524288
RAW_TRAILER_RESERVE = 512
RAW_RESERVED = 0
RAW_FAILED = False
DATA_CAP = 64 * 1024 * 1024
RUN_ROOT = None
LAST_SCAN = STARTED
MAX_OBSERVED_BYTES = 0
CHECKPOINTS = 0
TRACE_ROOTS = [str(ROOT)]


def raw_abort(reason):
    global RAW_FAILED
    RAW_FAILED = True
    trailer = ('{"event":"SQLITE_RAW_ABORT","reason":"' + reason + '","exit_status":125}\n').encode("ascii")
    try:
        os.write(2, trailer)
    except BaseException:
        pass
    os._exit(125)


class BoundedRaw:
    encoding = "utf-8"
    errors = "backslashreplace"

    def __init__(self, descriptor):
        self.descriptor = descriptor

    def write(self, value):
        global RAW_RESERVED
        if RAW_FAILED:
            os._exit(125)
        if type(value) is not str:
            raise TypeError("bounded raw writer requires plain text")
        data = value.encode(self.encoding, self.errors)
        if len(data) > RAW_CAP - RAW_TRAILER_RESERVE - RAW_RESERVED:
            raw_abort("combined_capacity")
        RAW_RESERVED += len(data)
        remaining = memoryview(data)
        try:
            while remaining:
                written = os.write(self.descriptor, remaining)
                if type(written) is not int or written <= 0 or written > len(remaining):
                    raw_abort("short_or_invalid_write")
                remaining = remaining[written:]
        except BaseException:
            raw_abort("fd_write_failure")
        return len(value)

    def flush(self):
        if RAW_FAILED:
            os._exit(125)

    def isatty(self):
        return False

    def fileno(self):
        return self.descriptor


sys.stdout = sys.__stdout__ = BoundedRaw(1)
sys.stderr = sys.__stderr__ = BoundedRaw(2)


def application_trace(frame, event, argument):
    if any(frame.f_code.co_filename.startswith(prefix) for prefix in TRACE_ROOTS):
        now = monotonic()
        if now >= DEADLINE:
            print('{"event":"SQLITE_SCOPE_DEADLINE","exit_status":124}', flush=True)
            os._exit(124)
        if RUN_ROOT is not None and now - LAST_SCAN >= .25:
            check_budget()
        return application_trace
    return None


sys.settrace(application_trace)
import argparse
import hashlib
import json
import runpy
import shutil
import stat
import traceback
from urllib.parse import unquote, urlsplit


def emit(event, **values):
    print(json.dumps({"event": event, **values}, sort_keys=True, allow_nan=False), flush=True)


def tree_bytes(root):
    total = 0
    for path in root.rglob("*"):
        details = path.lstat()
        if stat.S_ISREG(details.st_mode):
            total += details.st_size
        elif not stat.S_ISDIR(details.st_mode):
            raise ValueError("nonregular object in the new private run scope")
    return total


def check_budget():
    global LAST_SCAN, MAX_OBSERVED_BYTES
    now = monotonic()
    if now >= DEADLINE:
        emit("SQLITE_SCOPE_DEADLINE", exit_status=124)
        os._exit(124)
    LAST_SCAN = now
    observed = tree_bytes(RUN_ROOT) if RUN_ROOT is not None else 0
    MAX_OBSERVED_BYTES = max(MAX_OBSERVED_BYTES, observed)
    if observed > DATA_CAP:
        emit("SQLITE_LOGICAL_DATA_BUDGET_EXCEEDED", observed_bytes=observed, limit_bytes=DATA_CAP, exit_status=124)
        os._exit(124)
    return observed


def regular_bytes(path, expected_size=None):
    details = path.lstat()
    if (not stat.S_ISREG(details.st_mode) or path.resolve() != path
            or expected_size is not None and details.st_size != expected_size):
        raise ValueError("source is not the declared regular materialized file")
    return path.read_bytes()


def verify_sources(root, manifest):
    expected = set(manifest["inputs"])
    actual_uta = {str(path.relative_to(root)) for path in (root / "uta").glob("*.py")}
    if (len(actual_uta) != 61 or actual_uta != {name for name in expected if name.startswith("uta/")}
            or len(expected) != 63):
        raise ValueError("declared61 UTA plus2 runner inventory differs")
    observed = {}
    for name, pin in manifest["inputs"].items():
        data = regular_bytes(root / name, pin["bytes"])
        observed[name] = hashlib.sha256(data).hexdigest()
        if observed[name] != pin["sha256"]:
            raise ValueError("source digest differs: " + name)
    return observed


def write_new_json(path, value, cap=4 * 1024 * 1024):
    data = (json.dumps(value, sort_keys=True, ensure_ascii=True, indent=2, allow_nan=False) + "\n").encode()
    if len(data) > cap or check_budget() + len(data) > DATA_CAP:
        raise ValueError("new mandatory report would exceed the declared logical budget")
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        remaining = memoryview(data)
        while remaining:
            count = os.write(descriptor, remaining)
            if count <= 0:
                raise OSError("short mandatory report write")
            remaining = remaining[count:]
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    check_budget()


def within(path, directory):
    try:
        Path(path).resolve().relative_to(directory)
        return True
    except (ValueError, TypeError):
        return False


def install_scope_audit(business, reports):
    def audit(event, arguments):
        if event in {"subprocess.Popen", "os.fork", "os.forkpty", "os.posix_spawn", "os.kill", "os.killpg",
                     "os.pidfd_open", "signal.pidfd_send_signal", "socket.__new__", "socket.connect"}:
            raise AssertionError("forbidden child/PID/signal/network action: " + event)
        if event == "sqlite3.connect":
            target = arguments[0]
            if type(target) is not str:
                raise AssertionError("unexpected non-string SQLite target")
            if target.startswith("file:"):
                parsed = urlsplit(target)
                if parsed.netloc not in ("", "localhost"):
                    raise AssertionError("nonlocal SQLite target")
                target = unquote(parsed.path)
            if not within(target, business) or not Path(target).name.endswith(".sqlite3"):
                raise AssertionError("SQLite target outside the fresh synthetic business directory")
        if event in {"open", "os.listdir", "os.scandir", "os.readlink"}:
            target = arguments[0]
            if isinstance(target, (str, bytes)) and os.fsdecode(target).startswith("/proc"):
                raise AssertionError("proc inspection is outside this functional scope")
        if event == "open":
            target, mode, flags = arguments
            writing = (mode and any(character in mode for character in "wax+")) or flags & (os.O_WRONLY | os.O_RDWR)
            if writing and (isinstance(target, int) or not (within(target, business) or within(target, reports))):
                raise AssertionError("filesystem write outside the new private data/report scope")
        if event in {"os.mkdir", "os.remove", "os.rmdir", "os.rename", "os.link", "os.symlink", "os.truncate"}:
            paths = arguments[:2] if event in {"os.rename", "os.link", "os.symlink"} else arguments[:1]
            for target in paths:
                if not (within(target, business) or within(target, reports)):
                    raise AssertionError("filesystem mutation outside the new private data/report scope")
    sys.addaudithook(audit)


def main():
    global RUN_ROOT, CHECKPOINTS
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--approved-manifest-sha256", required=True)
    args = parser.parse_args()
    if (len(args.source_commit) != 40 or any(value not in "0123456789abcdef" for value in args.source_commit)
            or len(args.approved_manifest_sha256) != 64
            or any(value not in "0123456789abcdef" for value in args.approved_manifest_sha256)):
        raise ValueError("supply exact reviewed source and manifest labels")
    os.umask(0o077)
    os.sched_setaffinity(0, {min(os.sched_getaffinity(0))})
    root = Path(args.run_root)
    if not root.is_absolute() or root.exists() or root.parent != Path("/workspace"):
        raise ValueError("scope requires a new absolute direct child of /workspace")
    if shutil.disk_usage(root.parent).free < 128 * 1024 * 1024:
        raise ValueError("free disk below128MiB preparation floor")
    manifest_name = "evidence/reviews/matching-selection-snapshot/sqlite-source-manifest.json"
    manifest_data = regular_bytes(ROOT / manifest_name)
    if hashlib.sha256(manifest_data).hexdigest() != args.approved_manifest_sha256:
        raise ValueError("manifest differs from explicitly reviewed exact bytes")
    manifest = json.loads(manifest_data)
    if manifest["source_commit"] != args.source_commit:
        raise ValueError("manifest source label differs")
    pins = verify_sources(ROOT, manifest)
    if sum(value["bytes"] for value in manifest["inputs"].values()) > 2 * 1024 * 1024:
        raise ValueError("source mini-snapshot exceeds2MiB")
    root.mkdir(mode=0o700)
    RUN_ROOT = root
    source, business, reports = (root / name for name in ("source", "business", "reports"))
    for path in (source, business, reports):
        path.mkdir(mode=0o700)
    for name in [*manifest["inputs"], manifest_name]:
        target = source / name
        target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        data = regular_bytes(ROOT / name)
        descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o400)
        try:
            remaining = memoryview(data)
            while remaining:
                written = os.write(descriptor, remaining)
                if written <= 0:
                    raise OSError("short source snapshot write")
                remaining = remaining[written:]
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    for directory in sorted((path for path in source.rglob("*") if path.is_dir()), reverse=True):
        directory.chmod(0o500)
    source.chmod(0o500)
    TRACE_ROOTS.append(str(source))
    require_snapshot = verify_sources(source, manifest)
    if require_snapshot != pins or not sys.dont_write_bytecode:
        raise ValueError("source snapshot differs or bytecode writes are enabled")
    write_new_json(reports / "intent.json", {"source_commit": args.source_commit, "manifest_sha256": args.approved_manifest_sha256,
                   "runtime": sys.version, "actual_affinity": sorted(os.sched_getaffinity(0)), "source_pins": pins,
                   "case_count": 4, "authority_count": 8, "wall_seconds": 30, "raw_cap_bytes": RAW_CAP,
                   "logical_data_cap_bytes": DATA_CAP, "kernel_directory_quota_proven": False,
                   "execution_approval_source": "separate root scope; manifest/CLI alone do not authorize execution"})
    install_scope_audit(business, reports)
    sys.path.insert(0, str(source))
    emit("BEGIN_SQLITE_ONCE", source_commit=args.source_commit, actual_affinity=sorted(os.sched_getaffinity(0)),
         manifest_sha256=args.approved_manifest_sha256, source_files=len(pins), child_processes=0,
         raw_cap_bytes=RAW_CAP, logical_data_cap_bytes=DATA_CAP, kernel_directory_quota_proven=False)

    def checkpoint(case, mode, label, phase):
        global CHECKPOINTS
        observed = check_budget()
        CHECKPOINTS += 1
        emit("SQLITE_CHECKPOINT", case=case, mode=mode, label=label, phase=phase, observed_logical_bytes=observed)

    def save_report(name, value):
        if "/" in name or not name.endswith(".json"):
            raise ValueError("unexpected report name")
        write_new_json(reports / name, value)

    case_path = source / "evidence/reviews/matching-selection-snapshot/sqlite_case_once.py"
    values = runpy.run_path(str(case_path), run_name="matching_sqlite_functional_once")
    result = values["run_cases"](business, checkpoint, save_report)
    import sqlite3
    import _sqlite3
    import threading
    if threading.active_count() != 1:
        raise AssertionError("unexpected additional live thread")
    forbidden = sorted(name for name in sys.modules if name.split(".", 1)[0] in {"multiprocessing", "subprocess"}
                       or name in {"uta.request_signing", "uta.durable_process", "uta.durable_gateway", "uta.gateway"})
    if forbidden:
        raise AssertionError("unexpected worker/auth/network module imported")
    origins = {}
    for name, module in tuple(sys.modules.items()):
        if name == "uta" or name.startswith("uta."):
            path = Path(module.__file__).resolve()
            relative = str(path.relative_to(source))
            if relative not in pins or hashlib.sha256(regular_bytes(path)).hexdigest() != pins[relative]:
                raise AssertionError("loaded UTA module origin differs from frozen mini-source")
            origins[name] = relative
    after = verify_sources(source, manifest)
    original_after = verify_sources(ROOT, manifest)
    if after != pins or original_after != pins:
        raise AssertionError("source changed during the actual once scope")
    result.update({"source_commit": args.source_commit, "source_unchanged": True, "loaded_uta_origins": origins,
                   "source_before_sha256": pins, "snapshot_after_sha256": after, "original_after_sha256": original_after,
                   "sqlite_version": sqlite3.sqlite_version, "sqlite_extension_sha256": hashlib.sha256(Path(_sqlite3.__file__).read_bytes()).hexdigest(),
                   "python_version": sys.version, "actual_affinity": sorted(os.sched_getaffinity(0)),
                   "driver_elapsed_seconds": monotonic() - STARTED, "checkpoints": CHECKPOINTS,
                   "max_observed_logical_bytes": MAX_OBSERVED_BYTES, "kernel_directory_quota_proven": False,
                   "data_cap_limitation": "Python report writes reserve before write; SQLite C files checked between application lines/steps. No kernel quota or blocked-I/O hard realtime guarantee.",
                   "forbidden_imports": forbidden, "active_threads_at_end": 1,
                   "thread_observation_limit": "No thread start in reviewed scope; threading.active_count is a Python end-state observation, not kernel thread enumeration.",
                   "status": "LOCAL_SQLITE_FUNCTIONAL_PASS_PENDING_INDEPENDENT_REVIEW"})
    write_new_json(reports / "result.json", result)
    inventory = {}
    # All native transactions/connections have ended before reading DB bytes.
    for path in sorted(root.rglob("*")):
        if path.is_file():
            data = regular_bytes(path)
            inventory[str(path.relative_to(root))] = {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
    write_new_json(reports / "inventory.json", {"files": inventory, "excludes_this_inventory": True,
                   "sum_file_bytes": sum(value["bytes"] for value in inventory.values()), "source_unchanged": True})
    check_budget()
    emit("END_SQLITE_ONCE", status=result["status"], authorities=8, cases=4, driver_elapsed_seconds=monotonic() - STARTED,
         max_observed_logical_bytes=MAX_OBSERVED_BYTES, source_unchanged=True,
         all_financial_production_and_performance_approvals=False, exit_status=0)
    return 0


try:
    STATUS = main()
except BaseException:
    traceback.print_exc()
    STATUS = 1
finally:
    sys.settrace(None)
raise SystemExit(STATUS)
