"""Failure-only parent memory projection; no SQL, process probe or new thread."""
import json
import os
import stat
import sys
import threading
from types import FunctionType, ModuleType


MAX_BYTES = 32768
MAX_FRAMES = 8
PREFIX = b"UTA_MONITOR_REGISTRY_FAILURE "
_FILES = {path: module for path, module in (
    ("tests/test_durable_process.py", "tests.test_durable_process"),
    ("tests/monitor_registry_failure_evidence.py", "tests.monitor_registry_failure_evidence"),
    ("uta/durable_process.py", "uta.durable_process"),
    ("uta/storage.py", "uta.storage"), ("uta/sharding.py", "uta.sharding"),
    ("uta/writer_fence.py", "uta.writer_fence"),
    ("threading.py", "stdlib.threading"), ("contextlib.py", "stdlib.contextlib"),
    ("unittest/case.py", "stdlib.unittest.case"),
    ("multiprocessing/process.py", "stdlib.multiprocessing.process"),
    ("multiprocessing/connection.py", "stdlib.multiprocessing.connection"))}
_FUNCTIONS = frozenset(("_supervise", "_spawn", "_record_process", "_connect",
    "transaction", "read_transaction", "_lock", "publish_market", "_receipts",
    "_state", "_write_state", "status", "_load", "_observed", "_clock",
    "_wait_for_tstate_lock", "wait", "join", "is_alive", "__enter__", "__exit__",
    "run", "_bootstrap", "_bootstrap_inner", "_callTestMethod", "testPartExecutor",
    "_recv", "recv", "_recv_bytes", "poll", "_poll", "build_packet", "emit_once",
    "_primary", "_thread_packets", "_walk",
    "test_expired_stopped_owner_holding_shared_gate_is_killed_and_publication_recovers"))
_MODULES = frozenset((*_FILES.values(), "test_durable_process", "contextlib", "threading"))
_TYPES = frozenset(("builtins.AssertionError", "builtins.RuntimeError", "builtins.OSError",
    "builtins.BlockingIOError", "builtins.TimeoutError", "sqlite3.OperationalError",
    "sqlite3.DatabaseError", "sqlite3.IntegrityError", "uta.service.ServiceError",
    "uta.storage.StorageError", "uta.writer_fence.WriterFenceError"))
_CODES = frozenset(("router_busy", "router_halted", "lease_busy", "lease_expired",
                   "writer_fenced", "shard_unavailable", "worker_registration_failed"))
_FALLBACK = PREFIX + b'{"event":"uta.monitor_registry_failure.v1","collector_failed":true}\n'
_QUOTA = PREFIX + b'{"event":"uta.monitor_registry_failure.v1","quota_denied":true}\n'


def _line(value):
    return value if type(value) is int and 0 <= value < 2**31 else None


def _walk(frame):
    result = []
    while frame is not None and len(result) < MAX_FRAMES:
        code = frame.f_code
        label = next((module for path, module in _FILES.items()
                      if code.co_filename == path or code.co_filename.endswith("/" + path)), "<unlisted>")
        result.append({"module": label,
            "function": code.co_name if label != "<unlisted>" and code.co_name in _FUNCTIONS else "<unlisted>",
            "line": _line(frame.f_lineno)})
        frame = frame.f_back
    return {"frames": result, "frames_truncated": frame is not None}


def _thread_packets(router):
    # Read two selected IDs only; never enumerate or inspect other thread frames.
    frames = sys._current_frames()
    try:
        current = threading.get_ident()
        parent = {"role": "case_parent", "ownership": "current_caller", **_walk(frames.get(current))}
        monitor = {"role": "supervisor", "ownership": "unverified", "frames": [], "frames_truncated": False}
        fields = object.__getattribute__(router, "__dict__")
        thread = dict.get(fields, "_monitor") if type(fields) is dict else None
        if type(thread) is threading.Thread:
            values = object.__getattribute__(thread, "__dict__")
            ident, name = dict.get(values, "_ident"), dict.get(values, "_name")
            active = getattr(threading, "_active", None)
            if (type(ident) is int and ident != current and name == "uta-process-supervisor"
                    and type(active) is dict and dict.get(active, ident) is thread):
                selected = _walk(frames.get(ident))
                if (dict.get(fields, "_monitor") is thread and dict.get(active, ident) is thread):
                    monitor.update(ownership="matched_unlocked_samples", **selected)
                else:
                    monitor["ownership"] = "racy_discarded"
        return [parent, monitor]
    finally:
        frames.clear()  # Release snapshot references, including uninspected threads.


def _primary(error):
    # Existing unchanged financial helper, bounded8 causes x8 traceback frames.
    # This test projection retains at most2 causes x8 frames, without messages.
    module = sys.modules.get("uta.failure_diagnostics")
    if type(module) is not ModuleType:
        raise RuntimeError("existing failure metadata helper is not loaded")
    capture_failure = vars(module).get("capture_failure")
    if type(capture_failure) is not FunctionType:
        raise RuntimeError("existing failure metadata helper is unavailable")
    raw = capture_failure(error)
    chain = []
    for item in raw["chain"][:2]:
        native = item["sqlite_errorcode"]
        chain.append({"type": item["type"] if item["type"] in _TYPES else "<unlisted>",
            "relation": item["relation"] if item["relation"] in {"root", "cause", "context"} else "<unlisted>",
            "public_code": item["public_code"] if item["public_code"] in _CODES else None,
            "sqlite_errorcode": native if type(native) is int and 0 <= native < 2**31 else None,
            "frames": [{"module": row["module"] if row["module"] in _MODULES else "<unlisted>",
                        "function": row["function"] if row["function"] in _FUNCTIONS else "<unlisted>",
                        "line": _line(row["lineno"])} for row in item["frames"][:8]],
            "frames_truncated": item["frames_truncated"]})
    return {"chain": chain, "chain_truncated": raw["chain_truncated"] or len(raw["chain"]) > 2,
            "chain_cycle": raw["chain_cycle"]}


def build_packet(router, primary_error):
    return {"event": "uta.monitor_registry_failure.v1", "phase": "before_original_cleanup",
            "profile": "pr49_parent_memory_only", "cause_proven": False,
            "threads": _thread_packets(router), "primary": _primary(primary_error),
            "limits": {"threads": 2, "frames_per_thread": 8, "packet_bytes": MAX_BYTES},
            "router_mutex": "not_acquired", "worker_cache": "not_read"}


def render(payload):
    data = PREFIX + json.dumps(payload, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode("ascii") + b"\n"
    return data if len(data) <= MAX_BYTES else _QUOTA


def write_packet(data, fd=2):
    # CI already redirects this FD to regular unittest.txt. No Python stream
    # lock or FD flag change. Refuse blocking pipes/TTYs; do not retry short IO.
    if len(data) > MAX_BYTES:
        return "quota_denied"
    if not stat.S_ISREG(os.fstat(fd).st_mode) and os.get_blocking(fd):
        return "blocking_sink_declined"
    count = os.write(fd, data)
    return "written" if type(count) is int and count == len(data) else "short_write"


def emit_once(router, primary_error):
    try:
        data = render(build_packet(router, primary_error))
    except BaseException:
        data = _FALLBACK
    try:
        return write_packet(data)
    except BaseException:
        return "collector_failed"
