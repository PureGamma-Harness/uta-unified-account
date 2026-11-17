"""Failure-only evidence for the fixed synthetic CLI test; never runs a CLI.

The caller owns the original Popen/argv/timeout/signal protocol. Binary,
unbuffered PIPEs make the observed banner + communicate suffix exact bytes.
Raw data stays in a new private directory outside the source checkout.
"""
from __future__ import annotations

from hashlib import sha256
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time


PREFIX = "UTA_CLI_SIGTERM_FAILURE "
_ERRORS = {"TimeoutExpired", "AssertionError", "RuntimeError", "OSError",
           "PermissionError", "FileNotFoundError", "KeyboardInterrupt", "ValueError"}
_PHASES = {"popen_return", "startup_wait_before", "startup_wait_return", "banner_read",
           "health_before", "health_return", "sigterm_before", "sigterm_return",
           "exit_wait_before", "exit_wait_return", "post_exit_assertions_return",
           "primary_failure", "cleanup_enter", "cleanup_poll_return", "cleanup_kill_before",
           "cleanup_kill_return", "cleanup_communicate_before", "cleanup_communicate_return",
           "cleanup_failure", "cleanup_exit"}


class CleanupEvidenceError(RuntimeError):
    pass


def process_identity(pid):
    try:
        directory = Path("/proc") / str(pid)
        details = directory.stat()
        fields = (directory / "stat").read_text().rsplit(")", 1)[1].split()
        return {"observed": True, "pid": pid, "start_ticks": int(fields[19]),
                "boot_id": Path("/proc/sys/kernel/random/boot_id").read_text().strip(),
                "uid": details.st_uid, "parent": int(fields[1]), "state": fields[0]}
    except (OSError, ValueError, IndexError) as error:
        return {"observed": False, "pid": pid, "error_type": _error(error)["type"]}


def _error(error):
    name = type(error).__name__
    result = {"type": name if name in _ERRORS else "<unlisted>"}
    timeout = getattr(error, "timeout", None)
    if type(timeout) in (int, float) and math.isfinite(timeout) and 0 <= timeout <= 3600:
        result["timeout_seconds"] = timeout
    return result  # No message, args, notes, locals or credential values.


class CliFailureEvidence:
    def __init__(self, process, *, artifact_root=None, clock=time.monotonic_ns,
                 identity_reader=process_identity, notice_stream=None):
        self.process, self._clock, self._identity = process, clock, identity_reader
        self._root = artifact_root
        self._notice = sys.stderr if notice_stream is None else notice_stream
        self.directory = None
        self._prefix = bytearray()
        self._stdout = self._stderr = b""
        self._primary = None
        self._cleaned = self._communicated = self._reaped = False
        self._cleanup = "NOT_OBSERVED"
        self._cleanup_errors = []
        self._archive_errors = []
        self._events = []
        self._binding = self._observe(process.pid)
        args = process.args
        self._argv = (json.dumps(args, ensure_ascii=True).encode() + b"\n"
                      if type(args) is list and all(type(value) is str for value in args) else b"null\n")
        self.event("popen_return")

    def event(self, phase):
        child = self._observe(self.process.pid)
        same = (self._binding.get("observed") is True and child.get("observed") is True
                and all(child.get(key) == self._binding.get(key)
                        for key in ("pid", "start_ticks", "boot_id", "uid")))
        try:
            tick = self._clock()
            tick = tick if type(tick) is int and tick >= 0 else None
        except BaseException:
            tick = None
        self._events.append({"phase": phase if phase in _PHASES else "<unlisted>",
            "monotonic_ns": tick, "parent": self._observe(os.getpid()),
            "child": child, "same_child_birth": same})

    def _observe(self, pid):
        try:
            return self._identity(pid)
        except BaseException as error:
            return {"observed": False, "pid": pid, "error_type": _error(error)["type"]}

    def banner(self, data):
        if type(data) is not bytes:
            raise TypeError("CLI evidence requires binary unbuffered stdout")
        self._prefix.extend(data)
        self.event("banner_read")

    def primary_failure(self, error):
        self._primary = _error(error)
        self.event("primary_failure")
        # Preserve the pre-cleanup identity/state even if later cleanup cannot
        # finish. The original exception is never replaced by archive errors.
        try:
            self._ensure_directory()
            self._write("before-cleanup.json", self._json(self.packet()))
            self._write("stdout-prefix.bin", bytes(self._prefix))
        except BaseException as failure:
            self._archive_errors.append(_error(failure))

    def _ensure_directory(self):
        if self.directory is not None:
            return
        root = None if self._root is None else Path(self._root).absolute()
        source = Path(__file__).resolve().parents[1]
        if root is not None:
            if root == source or source in root.parents or root.is_symlink():
                raise ValueError("raw CLI evidence must remain outside source")
            info = root.stat()
            if info.st_uid != os.geteuid() or info.st_mode & 0o077:
                raise PermissionError("raw CLI evidence parent must be private")
        self.directory = Path(tempfile.mkdtemp(prefix="uta-cli-sigterm-failure-", dir=root))
        if self.directory.stat().st_mode & 0o077:
            raise PermissionError("raw CLI evidence directory is not private")

    @staticmethod
    def _json(value):
        return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()

    def _write(self, name, data):
        descriptor = os.open(self.directory / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())

    def packet(self):
        streams = {"stdout": bytes(self._prefix) + self._stdout, "stderr": self._stderr}
        return {"event": "uta.cli_sigterm_failure.v1", "primary": self._primary,
            "child_binding": self._binding, "phases": list(self._events),
            "cleanup": self._cleanup, "communicate_returned": self._communicated,
            "child_exit_and_reap_confirmed": self._reaped,
            "returncode": self.process.returncode if type(self.process.returncode) is int else None,
            "cleanup_kill_requested": any(row["phase"] == "cleanup_kill_before" for row in self._events),
            "streams_complete": self._communicated and self._reaped,
            "streams": {name: {"bytes": len(data), "sha256": sha256(data).hexdigest()}
                        for name, data in streams.items()},
            "argv": {"bytes": len(self._argv), "sha256": sha256(self._argv).hexdigest()},
            "cleanup_errors": list(self._cleanup_errors), "archive_errors": list(self._archive_errors)}

    def _persist(self):
        self._ensure_directory()
        self._write("stdout.bin", bytes(self._prefix) + self._stdout)
        self._write("stderr.bin", self._stderr)
        self._write("argv.private.json", self._argv)
        self._write("evidence.json", self._json(self.packet()))

    def cleanup(self):
        if self._cleaned:
            return
        self._cleaned = True
        self.event("cleanup_enter")
        try:
            running = self.process.poll() is None
            self.event("cleanup_poll_return")
            if running:
                self.event("cleanup_kill_before")
                self.process.kill()  # Original test's own Popen cleanup, no new signal.
                self.event("cleanup_kill_return")
            self.event("cleanup_communicate_before")
            stdout, stderr = self.process.communicate(timeout=5)  # Original limit.
            if type(stdout) is not bytes or type(stderr) is not bytes:
                raise TypeError("binary communicate outputs were not confirmed")
            self._stdout, self._stderr = stdout, stderr
            self._communicated = True
            self._reaped = type(self.process.returncode) is int
            self._cleanup = "CONFIRMED" if self._reaped else "UNKNOWN"
            self.event("cleanup_communicate_return")
        except BaseException as error:
            self._cleanup = "UNKNOWN"
            self._cleanup_errors.append(_error(error))
            if isinstance(error, subprocess.TimeoutExpired):
                self._stdout = error.output if type(error.output) is bytes else b""
                self._stderr = error.stderr if type(error.stderr) is bytes else b""
            self.event("cleanup_failure")
        self.event("cleanup_exit")
        failed = self._primary is not None or self._cleanup != "CONFIRMED"
        if failed:
            retained = False
            try:
                self._persist()
                retained = True
            except BaseException as error:
                self._archive_errors.append(_error(error))
            try:
                # Only stage/identity/completeness/hash metadata is emitted.
                # No raw stream, argv, file path, message, nonce or auth header.
                self._notice.write(PREFIX + json.dumps({**self.packet(), "archive_retained": retained},
                                                       sort_keys=True, allow_nan=False) + "\n")
                self._notice.flush()
            except BaseException:
                pass
        if self._primary is None and self._cleanup != "CONFIRMED":
            raise CleanupEvidenceError("CLI cleanup outcome is unknown; inspect private evidence")
