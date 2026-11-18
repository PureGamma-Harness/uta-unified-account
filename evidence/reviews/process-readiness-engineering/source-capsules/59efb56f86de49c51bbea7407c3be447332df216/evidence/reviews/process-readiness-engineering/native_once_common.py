"""Preparation-only native-once support; importing this does not run a case."""
import hashlib
import json
import math
import os
from pathlib import Path
import select
import signal
import stat
from threading import Lock
from time import monotonic, monotonic_ns

PROTECTED_PIDS = frozenset({4471, 8784, 122905, 122907, 123007, 123009,
                           310035, 310039, 310266, 310269})
DATA_CAP = 64 * 1024 * 1024
LOG_CAP = 8 * 1024 * 1024
CASE_JOURNAL_CAP = 4 * 1024 * 1024
STDIO_CAP = 2 * 1024 * 1024
CONTROL_JOURNAL_CAP = 512 * 1024
SAFE_EXPORT_CAP = 512 * 1024
CASE_RESULT_CAP = 64 * 1024
SELECTOR = "test_process_readiness.ProcessReadinessTests.test_malformed_missing_and_oversize_persistent_quotes_fail_closed"
BIRTH_FIELDS = ("pid", "start_ticks", "boot_id", "uid", "session")


class ScopeUnknown(BaseException):
    """Stop this attempt without silently converting uncertainty to success."""


def require_unprotected_pid(pid):
    if type(pid) is not int or pid <= 0 or pid in PROTECTED_PIDS:
        raise ScopeUnknown("protected_or_invalid_pid")


def require_before(deadline, code):
    if (type(deadline) not in (int, float) or not math.isfinite(deadline)
            or monotonic() >= deadline):
        raise ScopeUnknown(code)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def encode(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def _write_all(fd, data):
    while data:
        written = os.write(fd, data)
        if written <= 0:
            raise ScopeUnknown("short_write")
        data = data[written:]


def write_new_json(path, value, *, cap=CASE_RESULT_CAP):
    data = encode(value)
    if len(data) > cap:
        raise ScopeUnknown("result_output_cap")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        _write_all(fd, data)
        os.fsync(fd)
    finally:
        os.close(fd)
    directory = os.open(Path(path).parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


class Journal:
    def __init__(self, path, cap, *, context=None):
        self.context = dict(context or {})
        if set(self.context) & {"sequence", "event", "monotonic_ns"}:
            raise ScopeUnknown("journal_context_overrides_reserved_field")
        self.fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_APPEND | os.O_NOFOLLOW, 0o600)
        self.cap, self.size, self.sequence = cap, 0, 0
        self.failed = False
        self.lock = Lock()

    def append(self, event, **values):
        with self.lock:
            if self.failed:
                raise ScopeUnknown("journal_writer_failed_latched")
            if (set(values) & {"sequence", "event", "monotonic_ns"}
                    or any(key in values and values[key] != value for key, value in self.context.items())):
                self.failed = True
                raise ScopeUnknown("journal_record_overrides_identity_or_sequence")
            record = {**self.context, **values, "sequence": self.sequence, "event": event,
                      "monotonic_ns": monotonic_ns()}
            data = encode(record)
            if self.size + len(data) > self.cap:
                self.failed = True
                raise ScopeUnknown("journal_output_cap")
            # Reserve before any I/O. Partial writes or failed fsync never erase
            # written bytes or permit another append through this writer.
            self.size += len(data)
            try:
                _write_all(self.fd, data)
                os.fsync(self.fd)
            except BaseException:
                self.failed = True
                raise
            self.sequence += 1

    def close(self):
        os.close(self.fd)


def identity(pid):
    # Reject the union of all ten protected PIDs before any proc access.
    require_unprotected_pid(pid)
    fields = (Path("/proc") / str(pid) / "stat").read_text().rsplit(")", 1)[1].split()
    status = (Path("/proc") / str(pid) / "status").read_text().splitlines()
    uid = int(next(line for line in status if line.startswith("Uid:")).split()[2])
    return {"pid": pid, "state": fields[0], "ppid": int(fields[1]),
            "pgrp": int(fields[2]), "session": int(fields[3]), "start_ticks": int(fields[19]),
            "uid": uid, "boot_id": Path("/proc/sys/kernel/random/boot_id").read_text().strip()}


def same_birth(left, right):
    return all(left[key] == right[key] for key in BIRTH_FIELDS)


def children_of(pid):
    # Callers supply only this controller, the new leader, or already-bound children.
    require_unprotected_pid(pid)
    children = set()
    # Linux records children per spawning thread; monitor-spawned replacements
    # must be included without scanning any unrelated process.
    for task in (Path("/proc") / str(pid) / "task").iterdir():
        require_unprotected_pid(int(task.name))
        try:
            children.update(int(value) for value in (task / "children").read_text().split())
        except FileNotFoundError:
            continue
    return sorted(children)


class BoundChild:
    def __init__(self, pid, *, session, signal_deadline, parent=None):
        require_unprotected_pid(pid)
        require_before(signal_deadline, "child_binding_after_signal_deadline")
        self.signal_deadline = signal_deadline
        before = identity(pid)
        if before["session"] != session or before["uid"] != os.geteuid():
            raise ScopeUnknown("unowned_session_or_uid")
        if parent is not None and before["ppid"] != parent:
            raise ScopeUnknown("unowned_parent")
        require_unprotected_pid(pid)
        require_before(signal_deadline, "pidfd_binding_after_signal_deadline")
        self.fd = os.pidfd_open(pid)
        try:
            after = identity(pid)
            if not same_birth(before, after):
                raise ScopeUnknown("pid_changed_while_binding")
        except BaseException:
            os.close(self.fd)
            raise
        self.birth, self.sent = before, set()

    def terminal(self):
        require_unprotected_pid(self.birth["pid"])
        poller = select.poll()
        poller.register(self.fd, select.POLLIN)
        return bool(poller.poll(0))

    def verify(self):
        if self.terminal():
            return False
        current = identity(self.birth["pid"])
        if not same_birth(current, self.birth):
            raise ScopeUnknown("owned_pid_birth_changed")
        return True

    def send(self, signum, journal, *, reason):
        require_unprotected_pid(self.birth["pid"])
        if signum in self.sent:
            raise ScopeUnknown("duplicate_signal_for_bound_child")
        self.sent.add(signum)  # An uncertain attempt is never silently repeated.
        require_before(self.signal_deadline, "signal_absolute_deadline_expired")
        if not self.verify():
            journal.append("signal_unneeded_terminal", birth=self.birth, signal=int(signum), reason=reason)
            return
        journal.append("signal_before", birth=self.birth, signal=int(signum), reason=reason)
        # verify/proc reads and especially the journal's fsync may return late.
        require_unprotected_pid(self.birth["pid"])
        require_before(self.signal_deadline, "signal_absolute_deadline_expired_after_journal")
        try:
            signal.pidfd_send_signal(self.fd, signum)
        except ProcessLookupError:
            if not self.terminal():
                raise ScopeUnknown("signal_target_exit_unproven")
        journal.append("signal_after", birth=self.birth, signal=int(signum), reason=reason)

    def close(self):
        os.close(self.fd)


def tree_bytes(path):
    total = 0
    try:
        entries = os.scandir(path)
    except FileNotFoundError:
        return 0  # Original fixture cleanup may remove a private directory.
    with entries:
        for entry in entries:
            try:
                details = entry.stat(follow_symlinks=False)
            except FileNotFoundError:
                continue
            if stat.S_ISDIR(details.st_mode):
                total += tree_bytes(entry.path)
            elif stat.S_ISREG(details.st_mode):
                total += details.st_size
            else:
                raise ScopeUnknown("nonregular_owned_tree_entry")
    return total


def verify_sources(root, manifest):
    base, observed = Path(root).resolve(), {}
    lengths = manifest.get("sources_bytes")
    if not isinstance(lengths, dict) or set(lengths) != set(manifest["sources_sha256"]):
        raise ScopeUnknown("source_length_manifest_incomplete")
    for relative in manifest["sources_sha256"]:
        part = Path(relative)
        if part.is_absolute() or ".." in part.parts or str(part) != relative:
            raise ScopeUnknown("source_input_path_outside_declared_tree")
        path = base / part
        try:
            details = path.stat(follow_symlinks=False)
            if (not stat.S_ISREG(details.st_mode) or path.resolve() != path
                    or type(lengths[relative]) is not int or details.st_size != lengths[relative]):
                raise ScopeUnknown("source_input_type_or_length_mismatch")
            observed[relative] = digest(path)
        except OSError as error:
            raise ScopeUnknown("source_input_unmaterialized_or_unreadable") from error
    if observed != manifest["sources_sha256"]:
        raise ScopeUnknown("source_hash_mismatch")
    return observed


def binary_info():
    # Version constants and this process's own loaded-library map; no connection
    # is opened and no SQL is executed by this metadata function.
    import sqlite3
    import _sqlite3
    import sys
    import sysconfig
    sql_libraries = {}
    for line in Path("/proc/self/maps").read_text().splitlines():
        fields = line.split(maxsplit=5)
        if len(fields) == 6 and fields[5].startswith("/") and "libsqlite3" in Path(fields[5]).name:
            library = Path(fields[5]).resolve()
            sql_libraries[str(library)] = digest(library)
    executable = Path(sys.executable).resolve()
    multiprocessing_source = Path(sysconfig.get_path("stdlib")) / "multiprocessing"
    multiprocessing_hashes = {name: digest(multiprocessing_source / name) for name in (
        "context.py", "process.py", "popen_spawn_posix.py", "popen_fork.py", "spawn.py",
        "util.py", "resource_tracker.py", "synchronize.py", "connection.py", "forkserver.py")}
    return {"python_version": sys.version, "executable": str(executable),
            "executable_sha256": digest(executable), "sqlite_version": sqlite3.sqlite_version,
            "sqlite_module": str(Path(_sqlite3.__file__).resolve()),
            "sqlite_module_sha256": digest(_sqlite3.__file__),
            "loaded_libsqlite_sha256": sql_libraries,
            "multiprocessing_source_directory": str(multiprocessing_source),
            "multiprocessing_sources_sha256": multiprocessing_hashes}
