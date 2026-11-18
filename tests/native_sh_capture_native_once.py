"""Prepared single native baseline controller. Explicit new root GO required.

Only a newly launched private subtree is owned. No global /proc walk, existing
PID adoption, group signal, financial function replacement or old authority is
supported. This file is CODE-only until separately reviewed and authorized.
"""
import argparse
import ast
import builtins
import ctypes
import fcntl
from hashlib import sha256
import importlib.util
import json
import os
from pathlib import Path
import resource
import select
import selectors
import signal
import socket
import stat
import subprocess
import sys
import tempfile
import threading
import time
import types
import unittest


ROOT = Path(__file__).resolve().parents[1]
DRIVER = "tests/native_sh_capture_native_once.py"
PLAN = "evidence/reviews/native-sh-capture-handshake/native-executor-plan-v2.json"
CASE = "test_expired_sigstopped_shared_gate_owner_is_killed_so_publication_can_recover"
PROTECTED = frozenset((4471, 8784, 122905, 122907, 123007, 123009, 310035, 310039, 310266, 310269))
RAW_CAP, RAW_TRAILER = 262144, 512
EVENT_CAP, EVENT_BYTES, EVENT_RESERVE = 512, 2097152, 65536
DATA_CAP, DATA_HEADROOM, EVIDENCE_CAP = 33554432, 4194304, 8388608
FINAL_EVIDENCE_RESERVE = 262144
MAX_FRAME, SAMPLE_SECONDS = 65536, .05
ROLE_LIMITS = {"financial": 8, "tracker": 2, "case_parent": 1}
EXIT_CONTEXT = {}
REAL_EXIT = os._exit


class ScopeUnknown(RuntimeError):
    pass


def encode(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode("ascii")


def deny_pid(pid):
    if type(pid) is not int or pid <= 1 or pid in PROTECTED:
        raise ScopeUnknown("PID denied before any lookup, pidfd or signal")


def ready(fd):
    poller = select.poll()
    poller.register(fd, select.POLLIN)
    return bool(poller.poll(0))


def dispatch_owned(record, sig, deadline, *, fd=None, siginfo=None, flags=0):
    """Last check after all logging/IPC, immediately before the real syscall."""
    deny_pid(record["identity"]["pid"])
    checked = time.monotonic()
    if checked >= deadline:
        return False
    signal.pidfd_send_signal(record["pidfd"] if fd is None else fd, sig, siginfo, flags)
    return True


def identity(pid, procfd=None):
    deny_pid(pid)
    # This function is called only after a new creation/owned-children receipt.
    own_fd = procfd is None
    if own_fd:
        procfd = os.open(f"/proc/{pid}", os.O_PATH | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        info = os.fstat(procfd)
        fd = os.open("stat", os.O_RDONLY | os.O_CLOEXEC, dir_fd=procfd)
        try:
            raw = os.read(fd, 8192)
        finally:
            os.close(fd)
    finally:
        if own_fd:
            os.close(procfd)
    fields = raw.decode().rsplit(")", 1)[1].split()
    return {"pid": pid, "start_ticks": int(fields[19]), "uid": info.st_uid,
        "boot_id": Path("/proc/sys/kernel/random/boot_id").read_text().strip(),
        "ppid": int(fields[1]), "group": int(fields[2]), "session": int(fields[3]), "state": fields[0]}


def birth_equal(first, second):
    return all(first[key] == second[key] for key in ("pid", "start_ticks", "uid", "boot_id"))


def bind_new(pid, *, parents, receipt):
    deny_pid(pid)
    if not receipt:
        raise ScopeUnknown("no positive creation receipt")
    procfd = os.open(f"/proc/{pid}", os.O_PATH | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        first = identity(pid, procfd)
        if first["ppid"] not in parents or first["uid"] != os.geteuid():
            raise ScopeUnknown("new child parent/UID differs")
    except BaseException:
        os.close(procfd)
        raise
    try:
        fd = os.pidfd_open(pid)
    except BaseException:
        os.close(procfd)
        raise
    try:
        second = identity(pid, procfd)
        if not birth_equal(first, second):
            raise ScopeUnknown("birth changed around held pidfd")
    except BaseException:
        os.close(fd)
        os.close(procfd)
        raise
    return {"identity": first, "pidfd": fd, "procfd": procfd, "receipt": receipt, "reaped": False, "exit": None}


def send(channel, value, *, blocking=False):
    data = encode(value)
    if len(data) > MAX_FRAME:
        raise ScopeUnknown("control frame exceeds fixed bound")
    count = channel.send(data, 0 if blocking else socket.MSG_DONTWAIT)
    if count != len(data):
        raise ScopeUnknown("control frame short write")


def receive(channel):
    raw = channel.recv(MAX_FRAME + 1)
    if not raw:
        return None
    if len(raw) > MAX_FRAME:
        raise ScopeUnknown("control frame exceeds fixed bound")
    value = json.loads(raw)
    if type(value) is not dict or type(value.get("kind")) is not str:
        raise ScopeUnknown("invalid control frame")
    return value


def load_envelope(root, expected):
    path = root / "tests/native_sh_capture_pure_once.py"
    raw = path.read_bytes()
    if sha256(raw).hexdigest() != expected:
        raise ScopeUnknown("reviewed raw/source envelope helper differs")
    module = types.ModuleType("nshc_reviewed_envelope")
    module.__file__ = str(path)
    exec(compile(raw, str(path), "exec", dont_inherit=True), module.__dict__)
    return module


def validate_loaded(function, pins):
    path = Path(function.__globals__["__file__"]).resolve()
    raw = path.read_bytes()
    if {"bytes": len(raw), "sha256": sha256(raw).hexdigest()} != pins.get(str(path)):
        raise ScopeUnknown("loaded stdlib source pin differs")
    compiled = compile(raw, function.__code__.co_filename, "exec", dont_inherit=True, optimize=sys.flags.optimize)
    pending, matches = [compiled], []
    while pending:
        code = pending.pop()
        for item in code.co_consts:
            if isinstance(item, types.CodeType):
                pending.append(item)
                if item.co_name == function.__code__.co_name:
                    matches.append(item)
    if len(matches) != 1 or matches[0] != function.__code__:
        raise ScopeUnknown("loaded stdlib implementation differs from frozen source")


class EventFile:
    def __init__(self, fd):
        self.fd, self.count, self.used, self.failed = fd, 0, 0, False

    def write(self, value, *, cleanup=False):
        raw = encode({"outer_received_monotonic_ns": time.monotonic_ns(), **value})
        count_limit = EVENT_CAP if cleanup else EVENT_CAP - 32
        byte_limit = EVENT_BYTES if cleanup else EVENT_BYTES - EVENT_RESERVE
        if self.count + 1 > count_limit or self.used + len(raw) > byte_limit:
            self.failed = True
            raise ScopeUnknown("event quota exhausted")
        self.count += 1
        self.used += len(raw)  # No refund after a short/uncertain write.
        if os.write(self.fd, raw) != len(raw):
            self.failed = True
            raise ScopeUnknown("event capture short write")


class ParentLedger:
    """Only the new case parent: actual stdlib birth/wait receipts, held fds."""
    def __init__(self, channel, deadline):
        self.channel, self.lock = channel, threading.RLock()
        self.deadline = deadline
        self.records, self.by_pid, self.test_fds = [], {}, {}
        self.counts = {"financial": 0, "tracker": 0}
        self.pending_shard, self.unknown, self.stopped = None, [], set()
        self.case, self.pre_sh = None, {}
        self.real_waitpid, self.real_spawn = os.waitpid, None

    def event(self, kind, **values):
        with self.lock:
            send(self.channel, {"kind": kind, "monotonic_ns": time.monotonic_ns(),
                "boottime_ns": time.clock_gettime_ns(time.CLOCK_BOOTTIME), **values})

    def fail(self, reason):
        self.unknown.append(reason)
        try:
            self.event("UNKNOWN", reason=reason)
        finally:
            raise ScopeUnknown(reason)

    def record_for(self, pid):
        deny_pid(pid)
        record = self.by_pid.get(pid)
        if record is None:
            self.fail("PID has no new-child birth receipt")
        return record

    def case_identity(self, pid):
        record = self.record_for(pid)
        if ready(record["pidfd"]):
            raise FileNotFoundError("held new child has exited")
        current = identity(pid, record["procfd"])
        if not birth_equal(current, record["identity"]):
            self.fail("held-procdir child identity differs")
        return {key: current[key] for key in ("pid", "start_ticks", "boot_id", "uid", "state")}

    def classify_spawn(self, path, argv):
        if str(Path(os.fsdecode(path)).resolve()) != str(Path(sys.executable).resolve()):
            self.fail("unknown child executable")
        arguments = [os.fsdecode(value) for value in argv]
        if arguments.count("-c") != 1:
            self.fail("unknown multiprocessing launch form")
        position = arguments.index("-c")
        tree = ast.parse(arguments[position + 1])
        if len(tree.body) != 2 or not isinstance(tree.body[0], ast.ImportFrom) or not isinstance(tree.body[1], ast.Expr):
            self.fail("unknown child launch program")
        imported, call = tree.body[0], tree.body[1].value
        if not isinstance(call, ast.Call) or not isinstance(call.func, ast.Name):
            self.fail("unknown child entry")
        if (imported.module == "multiprocessing.resource_tracker" and len(imported.names) == 1
                and imported.names[0].name == call.func.id == "main" and len(call.args) == 1
                and isinstance(call.args[0], ast.Constant) and type(call.args[0].value) is int and not call.keywords):
            return "tracker", None
        if (imported.module == "multiprocessing.spawn" and len(imported.names) == 1
                and imported.names[0].name == call.func.id == "spawn_main" and not call.args
                and all(item.arg in {"tracker_fd", "pipe_handle", "parent_pid"}
                        and isinstance(item.value, ast.Constant) and type(item.value.value) is int for item in call.keywords)
                and arguments[position + 2:] == ["--multiprocessing-fork"] and self.pending_shard in (0, 1)):
            return "financial", self.pending_shard
        self.fail("unregistered child role")

    def spawn(self, path, argv, passfds):
        with self.lock:
            role, shard = self.classify_spawn(path, argv)
            if self.counts[role] >= ROLE_LIMITS[role]:
                self.fail("cumulative " + role + " birth budget")
            if role == "financial" and sum(row["role"] == role and not ready(row["pidfd"]) for row in self.records) >= 2:
                self.fail("two-live-financial-worker budget")
            self.counts[role] += 1  # A failed/uncertain spawn stops scope; never retries a reservation.
            self.event("SPAWN_INTENT", role=role, shard=shard, sequence=len(self.records) + 1)
            pid = self.real_spawn(path, argv, passfds)
            deny_pid(pid)  # Positive spawnv return precedes all PID lookup/operations.
            record = bind_new(pid, parents={os.getpid()}, receipt="actual_stdlib_spawnv_passfds_return")
            record.update(role=role, shard=shard, sequence=len(self.records) + 1)
            record["birth"] = sha256(encode({"identity": record["identity"], "sequence": record["sequence"]})).hexdigest()
            self.records.append(record)
            self.by_pid[pid] = record
            self.event("BIRTH", birth=record["birth"], role=role, shard=shard, identity=record["identity"],
                creation_receipt=record["receipt"])
            self.channel.settimeout(.5)
            try:
                acknowledged = receive(self.channel)
            finally:
                self.channel.settimeout(None)
            if acknowledged != {"kind": "ACK_BIRTH", "birth": record["birth"]}:
                self.fail("outer did not bind new birth before release to original spawn")
            return pid

    def waitpid(self, pid, options):
        record = self.record_for(pid)
        result = self.real_waitpid(pid, options)
        if result[0]:
            record["reaped"], record["exit"] = True, os.waitstatus_to_exitcode(result[1])
            self.event("WAIT", birth=record["birth"], pid=pid, raw_status=result[1], exit=record["exit"],
                pidfd_exit=ready(record["pidfd"]), actual_wait_return=True)
        return result

    def signal_record(self, record, sig, reason):
        deny_pid(record["identity"]["pid"])
        if ready(record["pidfd"]):
            return
        self.event("OWN_SIGNAL_ENTRY", birth=record["birth"], signal=int(sig), reason=reason)
        if not dispatch_owned(record, sig, self.deadline):
            self.fail("absolute51 deadline refused parent signal")
        self.event("OWN_SIGNAL_RETURN", birth=record["birth"], signal=int(sig), reason=reason)

    def finish(self, tracker):
        # Source TestCase cleanups already ran. Inspect only retained new handles.
        for record in self.records:
            if record["role"] == "financial" and (not record["reaped"] or not ready(record["pidfd"])):
                self.fail("financial child terminal state not confirmed after original cleanup")
        support = tracker._resource_tracker
        if support._pid is not None:
            self.record_for(support._pid)
            with support._lock:
                # Explicit wait callback preserves the actual status that the
                # stdlib's definition-time default otherwise discards.
                support._stop_locked(waitpid=self.waitpid)
        for record in self.records:
            if not record["reaped"] or not ready(record["pidfd"]):
                self.fail("new child lacks confirmed exit and actual reap")
        self.event("ALL_CHILDREN_TERMINAL", births=[{"birth": row["birth"], "role": row["role"],
            "exit": row["exit"], "reaped": row["reaped"]} for row in self.records])


class TrackedProcess:
    def __init__(self, raw, shard, ledger):
        self.raw, self.shard, self.ledger = raw, shard, ledger

    def __getattr__(self, name):
        return getattr(self.raw, name)

    def start(self):
        self.ledger.pending_shard = self.shard
        try:
            return self.raw.start()
        finally:
            self.ledger.pending_shard = None

    def kill(self):
        self.ledger.signal_record(self.ledger.record_for(self.raw.pid), signal.SIGKILL, "original_process_handle_kill")


class LedgerContext:
    def __init__(self, actual, ledger):
        self.actual, self.ledger = actual, ledger

    def __getattr__(self, name):
        return getattr(self.actual, name)

    def Process(self, *, target, args, name):
        return TrackedProcess(self.actual.Process(target=target, args=args, name=name), args[1], self.ledger)


class TestOS:
    """Only the test module's binding; financial modules keep real os."""
    def __init__(self, ledger):
        self.ledger = ledger

    def __getattr__(self, name):
        return getattr(os, name)

    def pidfd_open(self, pid, flags=0):
        record = self.ledger.record_for(pid)
        if ready(record["pidfd"]):
            self.ledger.fail("test tried to bind an exited child")
        if flags != 0:
            self.ledger.fail("unexpected test pidfd flags")
        # Duplicate the creator-held real pidfd, avoiding a new integer-PID
        # lookup after a concurrent source supervisor reap. It is the same
        # kernel process reference, never a fake descriptor or success result.
        fd = fcntl.fcntl(record["pidfd"], fcntl.F_DUPFD_CLOEXEC, 0)
        try:
            if not birth_equal(identity(pid, record["procfd"]), record["identity"]):
                self.ledger.fail("test pidfd birth differs")
        except BaseException:
            os.close(fd)
            raise
        self.ledger.test_fds[fd] = record
        self.ledger.event("TEST_PIDFD", birth=record["birth"], fd=fd, actual_kernel_reference="duplicate_of_creation_pidfd")
        return fd

    def close(self, fd):
        self.ledger.test_fds.pop(fd, None)
        return os.close(fd)


class TestSignal:
    def __init__(self, ledger):
        self.ledger = ledger

    def __getattr__(self, name):
        return getattr(signal, name)

    def pidfd_send_signal(self, fd, sig, siginfo=None, flags=0):
        record = self.ledger.test_fds.get(fd)
        if record is None or sig not in (signal.SIGSTOP, signal.SIGCONT, signal.SIGKILL):
            self.ledger.fail("test signal lacks a new owned pidfd/allowed role")
        pid = record["identity"]["pid"]
        deny_pid(pid)
        if sig == signal.SIGSTOP:
            case = self.ledger.case
            profile = case._native_sh_capture
            observation = case._expired_gate_observation
            reads = observation["lease_reads"]
            lease = reads[-1]["value"] if reads and reads[-1].get("observed") else {}
            if (record["birth"] in self.ledger.stopped or not profile.acknowledged
                    or profile.owner["pid"] != pid or not self.ledger.pre_sh.get(pid)
                    or lease.get("owner_pid") != pid or lease.get("active") is not True
                    or lease.get("generation") != profile.owner["generation"]
                    or time.monotonic() >= profile.deadline
                    or time.clock_gettime_ns(time.CLOCK_BOOTTIME) >= lease.get("expires_ns", 0)):
                self.ledger.fail("SIGSTOP preconditions are not complete and live")
            self.ledger.stopped.add(record["birth"])
        elif record["birth"] not in self.ledger.stopped:
            self.ledger.fail("undo/cleanup signal is not this fixture's own stop")
        self.ledger.event("TEST_SIGNAL_ENTRY", birth=record["birth"], signal=int(sig), fd=fd)
        if not dispatch_owned(record, sig, self.ledger.deadline, fd=fd, siginfo=siginfo, flags=flags):
            self.ledger.fail("absolute51 deadline refused test signal")
        self.ledger.event("TEST_SIGNAL_RETURN", birth=record["birth"], signal=int(sig), fd=fd)


def parent_case(config, channel):
    root = Path(config["source_copy"])
    sys.path[:0] = [str(root / "tests"), str(root)]
    import sqlite3
    import multiprocessing.resource_tracker as tracker
    import multiprocessing.util as mp_util
    if sqlite3.sqlite_version != config["expected_sqlite"] or str(Path(sys.executable).resolve()) != config["python"]:
        raise ScopeUnknown("native runtime differs before authority creation")
    os.sched_setaffinity(0, {1})
    resource.setrlimit(resource.RLIMIT_NOFILE, (256, 256))
    if tracker._resource_tracker._pid is not None:
        raise ScopeUnknown("unregistered support process before new scope")
    validate_loaded(mp_util.spawnv_passfds, config["stdlib_files"])
    validate_loaded(type(tracker._resource_tracker).ensure_running, config["stdlib_files"])
    validate_loaded(type(tracker._resource_tracker)._stop_locked, config["stdlib_files"])
    ledger = ParentLedger(channel, config["absolute_deadline_monotonic"])
    ledger.real_spawn = mp_util.spawnv_passfds
    spec = importlib.util.spec_from_file_location("test_durable_faults", root / "tests/test_durable_faults.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    original_temp = module.TemporaryDirectory
    authority_tmp = Path(config["output"]) / "authority-tmp"

    class KeptTemporaryDirectory(original_temp):
        def __init__(self, *args, **kwargs):
            if args or "dir" in kwargs:
                raise ScopeUnknown("unexpected temporary-directory call")
            super().__init__(dir=authority_tmp, **kwargs)
            self._finalizer.detach()
            ledger.event("NEW_AUTHORITY_DIRECTORY", path=self.name)

        def cleanup(self):
            ledger.event("AUTHORITY_RETAINED", path=self.name)

    def kernel_records(pid, owner, path, file_identity):
        record = ledger.record_for(pid)
        if not birth_equal(owner, record["identity"]):
            ledger.fail("kernel observer binding differs from new child")
        # Same kernel predicates as the original helper, reached exclusively
        # through creator-held procdir anchors. A reused integer cannot redirect
        # fd/fdinfo reads. Missing/exited identity is an error, never fake SH.
        ledger.case_identity(pid)
        current = path.stat(follow_symlinks=False)
        if (current.st_dev, current.st_ino) != file_identity:
            raise AssertionError("router lock file identity changed")
        value = []
        infofd = os.open("fdinfo", os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC, dir_fd=record["procfd"])
        try:
            for name in os.listdir(infofd):
                if not name.isdigit():
                    ledger.fail("unexpected kernel descriptor name")
                try:
                    if os.readlink("fd/" + name, dir_fd=record["procfd"]) != str(path):
                        continue
                    details = os.stat("fd/" + name, dir_fd=record["procfd"])
                    if (details.st_dev, details.st_ino) != file_identity:
                        raise AssertionError("worker lock descriptor targets a different inode")
                    fd = os.open(name, os.O_RDONLY | os.O_CLOEXEC, dir_fd=infofd)
                    try:
                        chunks, size = [], 0
                        while size <= 65536:
                            chunk = os.read(fd, min(8192, 65537 - size))
                            if not chunk:
                                break
                            chunks.append(chunk)
                            size += len(chunk)
                        content = b"".join(chunks).decode()
                    finally:
                        os.close(fd)
                    if size > 65536:
                        ledger.fail("kernel fdinfo exceeds bounded observation")
                except FileNotFoundError:
                    continue
                for line in content.splitlines():
                    fields = line.split()
                    if (len(fields) == 9 and fields[0] == "lock:"
                            and fields[2:5] == ["FLOCK", "ADVISORY", "READ"]
                            and fields[5] == str(pid) and fields[7:] == ["0", "EOF"]):
                        device = fields[6].split(":")
                        if (len(device) != 3 or int(device[0], 16) != os.major(current.st_dev)
                                or int(device[1], 16) != os.minor(current.st_dev)
                                or int(device[2]) != current.st_ino):
                            raise AssertionError("kernel lock record differs from router lock identity")
                        value.append({"fd": int(name), "kernel_record": line,
                                      "device": current.st_dev, "inode": current.st_ino})
        finally:
            os.close(infofd)
        ledger.case_identity(pid)
        ledger.pre_sh[pid] = value
        ledger.event("ACTUAL_KERNEL_SH", birth=record["birth"], records=value)
        return value

    case = module.ManagedProcessFaultTests(CASE)
    ledger.case = case
    original_setup, original_body = case.setUp, getattr(case, CASE)

    def setup():
        original_setup()
        if authority_tmp not in case.path.parents or case.router.layout["shard_count"] != 2:
            ledger.fail("original two-shard authority is not in the new private root")
        old_context = case.router._context
        wrapped = LedgerContext(old_context, ledger)
        case.router._context = wrapped
        def detach():
            if case.router._context is wrapped:
                case.router._context = old_context
        case.addCleanup(detach)
        ledger.event("ORIGINAL_SETUP", shards=2, settings=case.router._settings,
            authority_root=str(case.path), source_commit=config["revision"])

    def body():
        passed = False
        try:
            original_body()  # Exactly once: every original assertion/finally.
            passed = True
            expected = case._expired_gate_observation["new_lease"]
            with case.router._mutex:
                process, _, connection = case.router._workers[0]
                report = case.router._reports.get(0)
                if not (type(report) is dict and report.get("state") == "ready"
                        and report.get("pid") == process.pid and report.get("generation") == expected["generation"]):
                    report = None
                    # One nonblocking observation only, never a wait-until-green.
                    for _ in range(4):
                        if not connection.poll(0):
                            break
                        actual = connection.recv()
                        if (type(actual) is dict and actual.get("state") == "ready"
                                and actual.get("pid") == process.pid and actual.get("generation") == expected["generation"]):
                            report = actual
                if report is None:
                    ledger.fail("real replacement READY not observed")
                replacement = ledger.record_for(process.pid)
                ledger.event("ACTUAL_REPLACEMENT_READY", birth=replacement["birth"], report=report)
        finally:
            ledger.event("ORIGINAL_BODY_RESULT", original_assertions_completed=passed,
                observation=getattr(case, "_expired_gate_observation", None))

    case.setUp = setup
    setattr(case, CASE, body)
    saved_import = builtins.__import__

    def case_import(name, globals=None, locals=None, fromlist=(), level=0):
        imported = saved_import(name, globals, locals, fromlist, level)
        # Only original test/undo helper local imports are adapted. Native
        # financial modules and worker code receive the real module unchanged.
        if (globals is module.__dict__ and name == "uta.durable_process"
                and tuple(fromlist) == ("_process_identity",) and level == 0):
            return types.SimpleNamespace(_process_identity=ledger.case_identity)
        return imported
    try:
        module.TemporaryDirectory = KeptTemporaryDirectory
        module.bound_router_shared_flocks = kernel_records
        module.os, module.signal = TestOS(ledger), TestSignal(ledger)
        os.waitpid, mp_util.spawnv_passfds = ledger.waitpid, ledger.spawn
        builtins.__import__ = case_import
        def cancelled(signum, frame):
            ledger.fail("outer cancelled this new case scope")
        signal.signal(signal.SIGTERM, cancelled)
        result = unittest.TextTestRunner(stream=sys.stdout, verbosity=2).run(case)
        ledger.finish(tracker)
        ledger.event("CASE_END", tests_run=result.testsRun, failures=len(result.failures), errors=len(result.errors),
            skipped=len(result.skipped), expected_failures=len(result.expectedFailures),
            unexpected_successes=len(result.unexpectedSuccesses), case_passed=result.wasSuccessful(),
            unknowns=ledger.unknown, actual_affinity=sorted(os.sched_getaffinity(0)))
        return 0 if result.wasSuccessful() and not ledger.unknown else 1
    finally:
        # This interpreter has exactly one case and ends through REAL_EXIT.
        # Keep registration/wait/identity gates and held fds live until then:
        # a residual monitor cannot spawn/wait through restored raw callbacks
        # or observe a closed/reused ledger fd during final status persistence.
        # Normal original TestCase teardown already ran, unchanged.
        EXIT_CONTEXT["parent_ledger_retained_until_real_exit"] = True


def private_totals(output):
    data, evidence, files = 0, 0, 0
    for directory, names, entries in os.walk(output, followlinks=False):
        for name in [*names, *entries]:
            path = Path(directory) / name
            info = path.stat(follow_symlinks=False)
            if stat.S_ISLNK(info.st_mode):
                raise ScopeUnknown("unexpected private symlink")
            if stat.S_ISREG(info.st_mode):
                files += 1
                if files > 512:
                    raise ScopeUnknown("private file-count limit")
                if "authority-tmp" in path.relative_to(output).parts[:1]:
                    data += info.st_size
                else:
                    evidence += info.st_size
    return {"authority_logical_bytes": data, "evidence_logical_bytes": evidence, "regular_files": files}


def new_children(record):
    """Read only a held-live new process's own task/children subtree."""
    pid = record["identity"]["pid"]
    deny_pid(pid)
    if ready(record["pidfd"]):
        return []  # Never look up a possibly reused integer after recorded exit.
    found = []
    try:
        taskfd = os.open("task", os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC, dir_fd=record["procfd"])
    except FileNotFoundError:
        return []
    try:
        for name in os.listdir(taskfd):
            if not name.isdigit():
                continue
            deny_pid(int(name))
            try:
                fd = os.open(name + "/children", os.O_RDONLY | os.O_CLOEXEC, dir_fd=taskfd)
            except FileNotFoundError:
                continue
            try:
                values = os.read(fd, 8192).decode().split()
            finally:
                os.close(fd)
            for value in values:
                child = int(value)
                deny_pid(child)
                found.append(child)
    finally:
        os.close(taskfd)
    return found


def outer(args):
    if not args.execute:
        raise ScopeUnknown("native execution requires a new explicit root GO")
    deny_pid(os.getpid())  # New self only; no existing PID lookup.
    os.sched_setaffinity(0, {1})
    env = load_envelope(ROOT, args.envelope_sha256)
    plan_raw, _ = env.regular_bytes(ROOT / PLAN)
    if sha256(plan_raw).hexdigest() != args.plan_sha256:
        raise ScopeUnknown("native plan differs")
    plan = json.loads(plan_raw)
    if (plan.get("schema") != 1 or plan.get("cpu") != [1]
            or plan.get("financial_birth_limit") != 8 or plan.get("tracker_birth_limit") != 2
            or plan.get("financial_live_limit") != 2 or plan.get("case_wall_seconds") != 45
            or plan.get("native_envelope_seconds") != 51
            or plan.get("raw_bytes") != RAW_CAP or plan.get("raw_trailer_bytes") != RAW_TRAILER
            or plan.get("event_entries") != EVENT_CAP or plan.get("event_bytes") != EVENT_BYTES
            or plan.get("authority_logical_bytes") != DATA_CAP or plan.get("cleanup_headroom_bytes") != DATA_HEADROOM
            or plan.get("evidence_bytes") != EVIDENCE_CAP or plan.get("case") != CASE):
        raise ScopeUnknown("native scope/limits differ from reviewed single case")
    if str(Path(sys.executable).resolve()) != plan["python_executable"] or not args.sqlite_version:
        raise ScopeUnknown("exact interpreter and explicit SQLite identity are required")
    frozen, before = env.snapshot(plan, args.source_commit)
    if before[DRIVER]["sha256"] != args.driver_sha256 or env.git("show", args.source_commit + ":" + PLAN) != plan_raw:
        raise ScopeUnknown("native driver/plan Git binding differs")
    output = Path(args.output)
    if not output.is_absolute() or output.parent.resolve() != output.parent or ROOT in output.parents:
        raise ScopeUnknown("new private root must be physical and outside source")
    os.mkdir(output, 0o700)
    for name in ("source", "authority-tmp"):
        os.mkdir(output / name, 0o700)
    source_copy = output / "source"
    copy_before = {}
    for name, raw in frozen.items():
        destination = source_copy / name
        destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        env.private_file(destination, raw)
        os.chmod(destination, 0o444)
        copy_before[name] = env.regular_bytes(destination)[1]
    stdlib_before = {}
    for name, pin in plan["stdlib_files"].items():
        raw, fact = env.regular_bytes(Path(name))
        if {key: fact[key] for key in ("bytes", "sha256")} != pin:
            raise ScopeUnknown("declared stdlib spawn/wait source differs")
        stdlib_before[name] = fact
    started = time.monotonic()
    deadline = started + 51
    EXIT_CONTEXT.update(output=output, deadline=deadline, actor="outer")
    config = {"revision": args.source_commit, "output": str(output), "source_copy": str(source_copy),
        "python": plan["python_executable"], "expected_sqlite": args.sqlite_version,
        "files": plan["input_files"], "stdlib_files": plan["stdlib_files"],
        "absolute_deadline_monotonic": deadline}
    config_raw = encode(config)
    env.private_file(output / "inner-config.json", config_raw)
    events_fd = env.private_file(output / "events.jsonl")
    out_fd, err_fd = env.private_file(output / "first.stdout.txt"), env.private_file(output / "first.stderr.txt")
    events, raw = EventFile(events_fd), env.SharedRaw(out_fd, err_fd)
    parent_socket, child_socket = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET)
    parent_socket.setblocking(False)
    library = ctypes.CDLL(None, use_errno=True)
    if library.prctl(36, 1, 0, 0, 0) != 0:  # New outer self only: child subreaper.
        raise ScopeUnknown("new-scope subreaper unavailable")
    command = [plan["python_executable"], "-I", "-S", "-B", str(source_copy / DRIVER), "--inner",
        "--config", str(output / "inner-config.json"), "--config-sha256", sha256(config_raw).hexdigest(),
        "--event-fd", str(child_socket.fileno())]
    env.private_file(output / "intent.json", encode({"argv": command, "source_commit": args.source_commit,
        "plan_sha256": args.plan_sha256, "driver_sha256": args.driver_sha256, "before": before,
        "proposed_wall_seconds": 45, "cleanup_seconds": 6, "cpu": [1], "protected_deny": sorted(PROTECTED),
        "prior_scope_reused": False, "future_exit_not_attested": True}))
    launch_started_ns = time.monotonic_ns()
    process, leader, self_record, selector = None, None, None, None
    records, by_pid, counts = {}, {}, {"financial": 0, "tracker": 0}
    unknowns, case_end, all_terminal, authority_totals = [], None, None, []
    watchdog, cleanup_started, killed = False, None, False
    exit_status, started_case = 126, False
    def note_unknown(reason):
        if reason not in unknowns:
            unknowns.append(reason)

    def own_signal(record, sig):
        deny_pid(record["identity"]["pid"])
        if not ready(record["pidfd"]):
            try:
                events.write({"kind": "OUTER_OWN_SIGNAL", "birth": record["birth"], "signal": int(sig),
                              "at": time.monotonic()}, cleanup=True)
            except BaseException:
                note_unknown("cleanup_event_capture_failed")
            if not dispatch_owned(record, sig, deadline):
                note_unknown("absolute51_deadline_refused_outer_signal")
                return False
            return True

    def register(message, receipt, *, expected_parent):
        nonlocal records
        pid = message["identity"]["pid"]
        deny_pid(pid)
        role = message["role"]
        birth = message.get("birth")
        if role not in ("financial", "tracker", "unknown_descendant", "pending_birth"):
            raise ScopeUnknown("new child role is not declared")
        if type(birth) is not str or not 1 <= len(birth) <= 96 or birth in records:
            raise ScopeUnknown("new child birth frame is invalid or duplicated")
        existing = records.get(by_pid.get(pid))
        reuse_pending = (existing is not None and existing["role"] == "pending_birth"
            and birth_equal(existing["identity"], message["identity"]))
        if reuse_pending:
            record = existing
        else:
            record = bind_new(pid, parents={expected_parent, os.getpid()}, receipt=receipt)
        try:
            if not birth_equal(record["identity"], message["identity"]):
                raise ScopeUnknown("parent/outer held birth differs")
        except BaseException:
            if not reuse_pending:
                os.close(record["pidfd"])
                os.close(record["procfd"])
            raise
        if reuse_pending:
            records.pop(record["birth"])
        record.update(role=role, shard=message.get("shard"), birth=birth)
        records[record["birth"]], by_pid[pid] = record, record["birth"]
        if role in counts:
            counts[role] += 1
            if counts[role] > ROLE_LIMITS[role]:
                note_unknown("birth_budget_" + role)
        if role == "financial" and sum(row["role"] == role and not ready(row["pidfd"]) for row in records.values()) > 2:
            note_unknown("live_financial_budget")
        return record

    def reap_owned():
        while True:
            try:
                waiting = os.waitid(os.P_ALL, 0, os.WEXITED | os.WNOHANG | os.WNOWAIT)
            except ChildProcessError:
                waiting = None
            if waiting is None:
                return
            pid = waiting.si_pid
            if pid == process.pid:
                leader["exit"] = process.wait(timeout=0)
                leader["reaped"] = True
                exit_value = leader["exit"]
            elif pid in PROTECTED:
                # Kernel waitid returned this fresh subreaper's actual child.
                # Do not inspect/open/signal the denied number. Reap only that
                # already-exited own child and reject the entire qualification.
                waited, status = os.waitpid(pid, 0)
                note_unknown("protected_numeric_collision_in_new_child_exit")
                exit_value = os.waitstatus_to_exitcode(status)
            else:
                deny_pid(pid)
                birth = by_pid.get(pid)
                if birth is None:
                    found = identity(pid)
                    birth = "adopted-" + sha256(encode(found)).hexdigest()
                    register({"identity": found, "role": "unknown_descendant", "birth": birth},
                        "new_subreaper_waitid_child_receipt", expected_parent=os.getpid())
                    note_unknown("unregistered_adopted_child")
                waited, status = os.waitpid(pid, 0)
                records[birth]["exit"], records[birth]["reaped"] = os.waitstatus_to_exitcode(status), waited == pid
                exit_value = records[birth]["exit"]
            try:
                events.write({"kind": "OUTER_ACTUAL_REAP", "pid": pid, "exit": exit_value}, cleanup=True)
            except BaseException:
                note_unknown("reap_event_capture_failed")

    try:
        process = subprocess.Popen(command, cwd=source_copy, start_new_session=True, stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, pass_fds=(child_socket.fileno(),), close_fds=True,
            env={**os.environ, "TMPDIR": str(output / "authority-tmp"), "PYTHONDONTWRITEBYTECODE": "1"})
        child_socket.close()
        # Owning finally already covers every statement after actual Popen.
        leader = bind_new(process.pid, parents={os.getpid()}, receipt="actual_new_Popen_return")
        leader.update(role="case_parent", birth="case_parent")
        records["case_parent"], by_pid[process.pid] = leader, "case_parent"
        if leader["identity"]["group"] != process.pid or leader["identity"]["session"] != process.pid:
            raise ScopeUnknown("new leader did not own a new private session")
        env.private_file(output / "ACTUAL_LAUNCH.json", encode({"started_monotonic_ns": launch_started_ns,
            "bound_monotonic_ns": time.monotonic_ns(), "argv": command,
            "actual_new_leader_identity": leader["identity"], "future_exit_not_attested": True}))
        self_record = bind_new(os.getpid(), parents={os.getppid()}, receipt="new_outer_self")
        selector = selectors.DefaultSelector()
        selector.register(parent_socket, selectors.EVENT_READ, "control")
        for label, stream in (("stdout", process.stdout), ("stderr", process.stderr)):
            os.set_blocking(stream.fileno(), False)
            selector.register(stream, selectors.EVENT_READ, label)
        events.write({"kind": "OWNED_LEADER", "identity": leader["identity"], "creation_receipt": leader["receipt"]})
        last_sample = 0.0
        if time.monotonic() >= deadline:
            raise ScopeUnknown("absolute51 expired before START_CASE")
        send(parent_socket, {"kind": "START_CASE", "source_commit": args.source_commit})
        started_case = True
        while time.monotonic() < deadline:
            now = time.monotonic()
            for key, _ in selector.select(.01):
                if key.data in ("stdout", "stderr"):
                    block = os.read(key.fileobj.fileno(), 8192)
                    if block:
                        raw.write(key.data, block)
                    else:
                        selector.unregister(key.fileobj)
                        key.fileobj.close()
                else:
                    message = receive(parent_socket)
                    if message is None:
                        selector.unregister(parent_socket)
                        continue
                    events.write(message, cleanup=cleanup_started is not None)
                    if message["kind"] == "BIRTH":
                        register(message, "new_parent_spawnv_return_and_private_birth_frame", expected_parent=process.pid)
                        send(parent_socket, {"kind": "ACK_BIRTH", "birth": message["birth"]})
                    elif message["kind"] == "WAIT":
                        record = records.get(message["birth"])
                        if (record is None or not message.get("actual_wait_return") or not ready(record["pidfd"])
                                or message.get("pid") != record["identity"]["pid"]
                                or type(message.get("raw_status")) is not int
                                or os.waitstatus_to_exitcode(message["raw_status"]) != message.get("exit")):
                            note_unknown("invalid_or_unconfirmed_parent_wait")
                        else:
                            record["reaped"], record["exit"] = True, message["exit"]
                    elif message["kind"] == "UNKNOWN":
                        note_unknown(message.get("reason", "parent_unknown"))
                    elif message["kind"] == "CASE_END":
                        case_end = message
                    elif message["kind"] == "ALL_CHILDREN_TERMINAL":
                        all_terminal = message
            if now - last_sample >= SAMPLE_SECONDS:
                last_sample = now
                totals = private_totals(output)
                authority_totals.append(totals["authority_logical_bytes"])
                if totals["authority_logical_bytes"] > DATA_CAP - DATA_HEADROOM:
                    note_unknown("authority_cleanup_headroom_threshold")
                if totals["evidence_logical_bytes"] > EVIDENCE_CAP - FINAL_EVIDENCE_RESERVE:
                    note_unknown("evidence_limit")
                # New self and held-live known subtree only; no global /proc walk.
                for parent in [self_record, *list(records.values())]:
                    for child in new_children(parent):
                        if child == process.pid or child in by_pid:
                            continue
                        found = identity(child)  # Positive owned-children receipt already obtained.
                        birth = "pending-" + sha256(encode(found)).hexdigest()
                        pending = register({"identity": found, "role": "pending_birth", "birth": birth},
                            "registered_new_subtree_children_receipt", expected_parent=parent["identity"]["pid"])
                        pending["pending_since"] = now
                for record in records.values():
                    if record["role"] == "pending_birth" and now - record["pending_since"] > .75:
                        note_unknown("unregistered_descendant_after_birth_handshake_window")
            if raw.failed or events.failed:
                note_unknown("capture_quota_or_short_write")
            if now - started >= 45 and not ready(leader["pidfd"]):
                watchdog = True
                note_unknown("case_wall_45_seconds")
            if unknowns and cleanup_started is None:
                cleanup_started = now
                own_signal(leader, signal.SIGTERM)
            if cleanup_started is not None and now - cleanup_started >= 1 and not killed:
                killed = True
                for record in list(records.values()):
                    own_signal(record, signal.SIGKILL)
            reap_owned()
            all_exited = all(ready(row["pidfd"]) and row["reaped"] for row in records.values())
            pipes_done = not selector.get_map()
            if leader["reaped"] and all_exited and pipes_done:
                break
        final_totals = private_totals(output)
        if final_totals["authority_logical_bytes"] > DATA_CAP or final_totals["evidence_logical_bytes"] > EVIDENCE_CAP:
            note_unknown("final_data_or_evidence_limit")
        env.private_file(output / "actual-host-exit.txt", ("UNKNOWN" if leader["exit"] is None else str(leader["exit"])).encode() + b"\n")
        _, after = env.snapshot(plan, args.source_commit)
        if after != before:
            note_unknown("source_changed")
        copy_after = {name: env.regular_bytes(source_copy / name)[1] for name in copy_before}
        if copy_after != copy_before:
            note_unknown("private_source_copy_changed")
        stdlib_after = {name: env.regular_bytes(Path(name))[1] for name in stdlib_before}
        if stdlib_after != stdlib_before:
            note_unknown("stdlib_source_changed")
        if env.regular_bytes(ROOT / PLAN)[0] != plan_raw:
            note_unknown("native_plan_changed")
        env.private_file(output / "SOURCE_AFTER.json", encode({"original": after, "private_copy": copy_after,
            "stdlib": stdlib_after, "original_unchanged": after == before,
            "private_copy_unchanged": copy_after == copy_before, "stdlib_unchanged": stdlib_after == stdlib_before}))
        if any(row["role"] == "pending_birth" for row in records.values()):
            note_unknown("birth_handshake_missing")
        all_exited = all(ready(row["pidfd"]) and row["reaped"] for row in records.values())
        if not all_exited or not all_terminal or not leader["reaped"] or selector.get_map():
            note_unknown("terminal_or_END_evidence_missing")
        passed = (not unknowns and not watchdog and not raw.failed and case_end is not None
            and case_end.get("tests_run") == 1 and case_end.get("case_passed") is True
            and not any(case_end.get(key) for key in ("failures", "errors", "skipped", "expected_failures", "unexpected_successes"))
            and leader["exit"] == 0)
        if time.monotonic() >= deadline:
            note_unknown("actual_native_envelope_exceeded_51_seconds")
            passed = False
        qualification = "NATIVE_SINGLE_CASE_PASS" if passed else "UNKNOWN" if unknowns else "NATIVE_SINGLE_CASE_FAIL"
        exit_status = 0 if passed else 125 if raw.failed else 126 if unknowns else 1
        raw.trailer({"event": "NSHC_NATIVE_END", "qualification": "PENDING_FINAL_RETURN",
            "observed_candidate": qualification, "future_exit_not_attested": True,
            "host_exit": leader["exit"], "leader_reaped": leader["reaped"], "all_new_children_terminal": all_exited,
            "envelope_exit": exit_status})
        if raw.failed:
            note_unknown("raw_capture_or_trailer_failed")
            qualification, exit_status = "UNKNOWN", 125
        for fd in (events_fd, out_fd, err_fd):
            os.fsync(fd)
        raw_facts = {name: env.regular_bytes(output / name, RAW_CAP)[1]
                     for name in ("first.stdout.txt", "first.stderr.txt")}
        if sum(value["bytes"] for value in raw_facts.values()) > RAW_CAP:
            note_unknown("actual_raw_limit")
            qualification, exit_status = "UNKNOWN", 125
        end = {"qualification": "PENDING_FINAL_RETURN", "observed_candidate": qualification,
            "proposed_envelope_exit": exit_status, "future_exit_not_attested": True,
            "source_commit": args.source_commit, "actual_host_exit": leader["exit"], "actual_host_reaped": leader["reaped"],
            "actual_elapsed_seconds": time.monotonic() - started,
            "case_end": case_end, "unknowns": unknowns, "watchdog": watchdog, "data_sample_seconds": SAMPLE_SECONDS,
            "data_peak_observed": max(authority_totals, default=0), "final_totals": final_totals,
            "data_limit_is_not_hard_quota": True, "sampling_overshoot_possible": True,
            "children": [{"birth": row["birth"], "role": row["role"], "identity": row["identity"],
                "actual_exit": row["exit"], "actual_reaped": row["reaped"], "pidfd_exit": ready(row["pidfd"])} for row in records.values()],
            "raw_capture_failed": raw.failed, "raw_files": raw_facts,
            "event_count": events.count, "event_bytes": events.used,
            "production_approved": False}
        if len(encode(end)) > FINAL_EVIDENCE_RESERVE // 2:
            raise ScopeUnknown("final metadata reservation exceeded")
        env.private_file(output / "END.json", encode(end))
    finally:
        # Covers Popen, all pre-START setup and every subsequent exception.
        # A not-yet-bound actor receives channel EOF; only creation-held
        # positive handles may dispatch signals, always before absolute51.
        try:
            parent_socket.close()
        except BaseException:
            note_unknown("control_close_failed")
        try:
            child_socket.close()
        except BaseException:
            note_unknown("child_channel_close_failed")
        for record in list(records.values()):
            try:
                if not ready(record["pidfd"]):
                    own_signal(record, signal.SIGKILL)
            except BaseException:
                note_unknown("exception_cleanup_signal_unknown")
        if process is not None and leader is None:
            # START was never released. Direct Popen wait is a creator receipt,
            # not a lookup/adoption of this integer and never dispatches a signal.
            note_unknown("new_leader_binding_incomplete")
            try:
                process.wait(timeout=max(0, deadline - time.monotonic()))
            except BaseException:
                note_unknown("unbound_new_leader_reap_unknown")
        while time.monotonic() < deadline and any(not row["reaped"] for row in records.values()):
            try:
                reap_owned()
            except BaseException:
                note_unknown("exception_cleanup_reap_unknown")
            if process is not None:
                for stream, label in ((process.stdout, "stdout"), (process.stderr, "stderr")):
                    if not stream.closed:
                        try:
                            os.set_blocking(stream.fileno(), False)
                            block = os.read(stream.fileno(), 8192)
                            if block:
                                raw.write(label, block)
                        except BlockingIOError:
                            pass
                        except BaseException:
                            note_unknown("exception_cleanup_pipe_unknown")
            time.sleep(min(.01, max(0, deadline - time.monotonic())))
        terminal = bool(leader is not None and leader["reaped"]
            and all(row["reaped"] and ready(row["pidfd"]) for row in records.values()))
        if not terminal:
            note_unknown("final_registered_terminal_evidence_incomplete")
        if time.monotonic() >= deadline:
            note_unknown("absolute51_before_final_ownership")
        try:
            env.private_file(output / "FINAL_OWNERSHIP.json", encode({
                "leader_exit": None if leader is None else leader["exit"],
                "leader_reaped": False if leader is None else leader["reaped"],
                "unbound_creator_handle_exit": None if process is None else process.returncode,
                "START_CASE_sent": started_case, "all_registered_new_children_terminal": terminal,
                "unknowns": unknowns, "elapsed_seconds": time.monotonic() - started,
                "future_exit_not_attested": True, "production_approved": False}))
        except BaseException:
            note_unknown("final_ownership_write_failed")
        for record in ([self_record] if self_record is not None else []) + list(records.values()):
            for name in ("pidfd", "procfd"):
                try:
                    os.close(record[name])
                except BaseException:
                    note_unknown("held_handle_close_failed")
        if process is not None:
            for stream in (process.stdout, process.stderr):
                try:
                    if not stream.closed:
                        stream.close()
                except BaseException:
                    note_unknown("pipe_close_failed")
        if selector is not None:
            try:
                selector.close()
            except BaseException:
                note_unknown("selector_close_failed")
        for fd in (events_fd, out_fd, err_fd):
            try:
                os.fsync(fd)
            except BaseException:
                note_unknown("final_raw_fsync_failed")
            finally:
                try:
                    os.close(fd)
                except BaseException:
                    note_unknown("raw_descriptor_close_failed")
    # No in-try return can retain a pre-fsync PASS. CLI hard-exit repeats the
    # check after its own durable status/flush; external actual exit is required.
    if time.monotonic() >= deadline:
        note_unknown("absolute51_after_durable_finalization")
    if unknowns:
        exit_status = 125 if raw.failed else 126
    return exit_status


def inner(args):
    deny_pid(os.getpid())
    expected_config = ROOT.parent / "inner-config.json"
    if ROOT.name != "source" or Path(args.config) != expected_config:
        raise ScopeUnknown("inner configuration is not the new private sibling of deployed source")
    fd = os.open(expected_config, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode) or before.st_size > 262144:
            raise ScopeUnknown("private config is not a bounded regular file")
        raw = os.read(fd, 262145)
        after = os.fstat(fd)
    finally:
        os.close(fd)
    if (len(raw) != before.st_size or (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns)
            != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns)):
        raise ScopeUnknown("private config changed during bound read")
    if sha256(raw).hexdigest() != args.config_sha256:
        raise ScopeUnknown("private native config differs")
    config = json.loads(raw)
    if config["source_copy"] != str(ROOT) or config["output"] != str(ROOT.parent):
        raise ScopeUnknown("inner output/source root differs")
    deadline = config["absolute_deadline_monotonic"]
    if type(deadline) not in (int, float) or not 0 < deadline < 2**53:
        raise ScopeUnknown("inner absolute deadline is invalid")
    EXIT_CONTEXT.update(output=ROOT.parent, deadline=deadline, actor="inner")
    for name, pin in config["files"].items():
        path = Path(config["source_copy"]) / name
        data = path.read_bytes()
        if path.is_symlink() or {"bytes": len(data), "sha256": sha256(data).hexdigest()} != pin:
            raise ScopeUnknown("new private code copy differs")
    channel = socket.socket(fileno=args.event_fd)
    os.set_inheritable(args.event_fd, False)
    try:
        if receive(channel) != {"kind": "START_CASE", "source_commit": config["revision"]}:
            raise ScopeUnknown("outer did not release the newly bound case actor")
        return parent_case(config, channel)
    finally:
        channel.close()


def finish_process(status):
    """Never enter multiprocessing atexit, including failed log/flush paths.

    This durable observation proposes an exit; only the separate launcher can
    attest actual exit/reap and the final elapsed bound.
    """
    status = status if type(status) is int and 0 <= status <= 255 else 126
    try:
        if EXIT_CONTEXT:
            deadline = EXIT_CONTEXT["deadline"]
            if time.monotonic() >= deadline:
                status = 126
            data = encode({"event": "NSHC_NATIVE_PRE_EXIT_OBSERVATION",
                "actor": EXIT_CONTEXT["actor"], "proposed_exit": status,
                "before_absolute51": time.monotonic() < deadline,
                "observed_monotonic_ns": time.monotonic_ns(),
                "future_exit_not_attested": True, "production_approved": False})
            path = EXIT_CONTEXT["output"] / (EXIT_CONTEXT["actor"].upper() + "_PRE_EXIT.json")
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
            try:
                if os.write(fd, data) != len(data):
                    raise ScopeUnknown("pre-exit observation short write")
                os.fsync(fd)
            finally:
                os.close(fd)
    except BaseException:
        status = 126
    finally:
        try:
            sys.stdout.flush()
            sys.stderr.flush()
        except BaseException:
            status = 126
        finally:
            # Recheck after every write/fsync/flush. No durable earlier claim
            # can turn a late actual return into success. No atexit callbacks.
            try:
                if EXIT_CONTEXT and time.monotonic() >= EXIT_CONTEXT["deadline"]:
                    status = 126
            except BaseException:
                status = 126
            finally:
                REAL_EXIT(status)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--inner", action="store_true")
    parser.add_argument("--output")
    parser.add_argument("--source-commit")
    parser.add_argument("--plan-sha256")
    parser.add_argument("--driver-sha256")
    parser.add_argument("--envelope-sha256")
    parser.add_argument("--sqlite-version")
    parser.add_argument("--config")
    parser.add_argument("--config-sha256")
    parser.add_argument("--event-fd", type=int)
    args = parser.parse_args()
    status = 126
    try:
        try:
            status = inner(args) if args.inner else outer(args)
        except BaseException as error:
            status = 126
            print(encode({"event": "NSHC_NATIVE_CONTROLLER_UNKNOWN", "error_type": type(error).__name__,
                          "qualification": "UNKNOWN", "production_approved": False}).decode(), file=sys.stderr, end="", flush=True)
    finally:
        finish_process(status)
