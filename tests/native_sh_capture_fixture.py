"""Fresh development fixture only: instrumented owner-held kernel SH capture.

No UTA function/class is replaced. Import performs no native operation. The
test-only target traces one exact unchanged worker callsite; this is explicit
fault instrumentation, never an uninstrumented-engine or performance claim.
"""
import ast
from hashlib import sha256
import json
import os
from pathlib import Path
import sys
import threading
from time import monotonic
from types import CodeType


RUNTIME_SHA256 = "46905e06af8e6ee12e16b71ad6ebce50847a7d77c03c1e7fb3e73fd165897219"
BINDING_KEYS = ("pid", "start_ticks", "boot_id", "uid", "generation")
PROFILE = "development_exact_worker_callsite_sh_v1"
CASE = "test_expired_sigstopped_shared_gate_owner_is_killed_so_publication_can_recover"


class CaptureFixtureError(AssertionError):
    pass


def binding(identity, generation):
    result = {key: identity[key] for key in BINDING_KEYS[:-1]}
    result["generation"] = generation
    if (any(type(result[key]) is not int or result[key] < 0
            for key in ("pid", "start_ticks", "uid", "generation"))
            or result["pid"] <= 1 or result["generation"] <= 0
            or type(result["boot_id"]) is not str or not 1 <= len(result["boot_id"]) <= 64):
        raise CaptureFixtureError("invalid fixture binding")
    return result


def packet(kind, owner, deadline):
    if kind not in {"ARM", "ENTERED", "RELEASE", "RELEASED", "ABORT"}:
        raise CaptureFixtureError("unknown fixture message")
    if (type(deadline) not in (int, float) or not 0 < deadline < 2**53
            or type(owner) is not dict or set(owner) != set(BINDING_KEYS)
            or binding(owner, owner["generation"]) != owner):
        raise CaptureFixtureError("invalid fixture message")
    return {"version": 1, "kind": kind, "binding": dict(owner), "deadline": deadline}


def send(connection, message):
    encoded = json.dumps(message, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("ascii")
    if len(encoded) > 2048:
        raise CaptureFixtureError("fixture message exceeded bound")
    connection.send_bytes(encoded)


def receive(connection, *, timeout):
    if not connection.poll(max(0, timeout)):
        raise CaptureFixtureError("fixture deadline expired")
    value = json.loads(connection.recv_bytes(2048).decode("ascii"))
    if type(value) is not dict or set(value) != {"version", "kind", "binding", "deadline"}:
        raise CaptureFixtureError("invalid fixture envelope")
    if type(value["version"]) is not int or value["version"] != 1:
        raise CaptureFixtureError("invalid fixture version")
    if packet(value["kind"], value["binding"], value["deadline"]) != value:
        raise CaptureFixtureError("invalid fixture fields")
    return value


class Protocol:
    """Finite protocol state only; kernel and lease facts stay external."""
    def __init__(self):
        self.state, self.owner, self.deadline = "NEW", None, None

    def arm(self, message):
        if self.state != "NEW" or message["kind"] != "ARM":
            raise CaptureFixtureError("fixture cannot be armed again")
        self.owner, self.deadline, self.state = dict(message["binding"]), message["deadline"], "ARMED"

    def entered(self, owner):
        if self.state != "ARMED" or owner != self.owner:
            raise CaptureFixtureError("fixture entered with another owner")
        self.state = "ENTERED"

    def release(self, message):
        if (self.state != "ENTERED" or message != packet("RELEASE", self.owner, self.deadline)):
            raise CaptureFixtureError("fixture release is out of order or changed")
        self.state = "RELEASED"

    def abort(self, message):
        if (self.state != "RELEASED" or message != packet("ABORT", self.owner, self.deadline)):
            raise CaptureFixtureError("fixture abort is out of order or changed")
        self.state = "CLOSED"


def exact_worker_boundary(worker, source):
    """Refuse changed installed source or loaded worker code; bypass nothing."""
    if sha256(source).hexdigest() != RUNTIME_SHA256:
        raise CaptureFixtureError("fixture source belongs to another runtime")
    compiled = compile(source, worker.__code__.co_filename, "exec", dont_inherit=True,
                       optimize=sys.flags.optimize)
    codes = [value for value in compiled.co_consts if isinstance(value, CodeType)
             and value.co_name == "_run_worker"]
    if len(codes) != 1 or codes[0] != worker.__code__:
        raise CaptureFixtureError("loaded worker differs from its exact source")
    tree = ast.parse(source)
    entry = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "_run_worker")
    calls = [node for node in ast.walk(entry) if isinstance(node, ast.Call)
             and isinstance(node.func, ast.Attribute) and node.func.attr == "process_one"
             and isinstance(node.func.value, ast.Name) and node.func.value.id == "view"]
    if len(calls) != 1:
        raise CaptureFixtureError("worker has no unique reviewed boundary")
    return calls[0].lineno


def hold_at_boundary(view, connection, protocol, identity, *, clean_threads, clock=monotonic):
    """Never enter financial SQL after an arm; RELEASE parks outside SH."""
    if protocol.state != "NEW":
        raise CaptureFixtureError("armed fixture cannot reenter a worker call")
    if not connection.poll(0):
        return
    arm = receive(connection, timeout=0)
    protocol.arm(arm)
    current = binding(identity(), view.database.writer_token.generation)
    if (current != protocol.owner or view.shard != 0 or not clean_threads()
            or view.database.writer_token.process_id != current["pid"]):
        raise CaptureFixtureError("fixture requires exact owned shard and drained startup")
    with view._control._lock(timeout=max(0, protocol.deadline - clock())):
        protocol.entered(current)
        send(connection, packet("ENTERED", current, protocol.deadline))
        # This private wait owns SH, has no SQLite connection and no keeper.
        # The parent verifies the real kernel record before its one SIGSTOP.
        protocol.release(receive(connection, timeout=protocol.deadline - clock()))
    send(connection, packet("RELEASED", current, protocol.deadline))
    # The parent can observe stable absence of SH during cleanup. There is no
    # recapture and no continuation into original SQL after a failed capture.
    protocol.abort(receive(connection, timeout=protocol.deadline - clock()))
    raise CaptureFixtureError("one-shot fixture released; original SQL is forbidden")


def capture_worker(*arguments):
    """Only the initial synthetic shard-zero target is instrumented."""
    from uta import durable_process
    *worker_arguments, connection = arguments
    if worker_arguments[1] != 0 or worker_arguments[2]["financial_batch_size"] != 0:
        raise CaptureFixtureError("fixture target role is not the reviewed single-command shard")
    worker = durable_process._run_worker
    source = Path(worker.__code__.co_filename).read_bytes()
    line = exact_worker_boundary(worker, source)
    if sys.gettrace() is not None:
        raise CaptureFixtureError("fixture refuses another trace owner")
    protocol = Protocol()

    def trace(frame, event, arg):
        if frame.f_code is not worker.__code__:
            return None
        if event == "line" and frame.f_lineno == line:
            hold_at_boundary(frame.f_locals["view"], connection, protocol,
                lambda: durable_process._process_identity(os.getpid()),
                clean_threads=lambda: threading.enumerate() == [threading.main_thread()])
        return trace

    try:
        sys.settrace(trace)
        return worker(*worker_arguments)
    finally:
        sys.settrace(None)
        connection.close()


class CaptureContext:
    def __init__(self, real, child_connection):
        self.real, self.child_connection, self.used = real, child_connection, False

    def __getattr__(self, name):
        return getattr(self.real, name)

    def Process(self, *, target, args, name):
        if args[1] == 0 and not self.used:
            if target.__module__ != "uta.durable_process" or target.__name__ != "_run_worker":
                raise CaptureFixtureError("fixture cannot replace an unknown spawn target")
            self.used = True
            return self.real.Process(target=capture_worker, args=(*args, self.child_connection), name=name)
        return self.real.Process(target=target, args=args, name=name)


class NativeSHCapture:
    def __init__(self, router, *, fresh_synthetic=False):
        if (fresh_synthetic is not True or router._workers or router._supervisor_fd is not None
                or router.durable_batches is not False
                or router._settings["lease_seconds"] != 5 or router._settings["financial_batch_size"] != 0):
            raise CaptureFixtureError("fixture is restricted to a fresh five-second synthetic router")
        self.router, self.real_context = router, router._context
        self.parent, self.child = self.real_context.Pipe(duplex=True)
        self.context = CaptureContext(self.real_context, self.child)
        router._context = self.context
        self.owner, self.deadline, self.acknowledged, self.closed = None, None, False, False
        self.release_sent = False

    def arm(self, identity, generation, deadline):
        if self.owner is not None or self.closed:
            raise CaptureFixtureError("parent fixture cannot rearm")
        self.owner, self.deadline = binding(identity, generation), deadline
        send(self.parent, packet("ARM", self.owner, deadline))
        # This is instrumentation metadata, never a READY/lease/financial fact.
        print("UTA_SH_CAPTURE_PROFILE " + json.dumps({"profile": PROFILE,
            "profile_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
            "runtime_sha256": RUNTIME_SHA256, "binding": self.owner,
            "instrumented": True, "native_recovery_proven": False}, sort_keys=True), file=sys.stderr, flush=True)

    def entered(self, identity, generation):
        expected = binding(identity, generation)
        if self.owner != expected:
            raise CaptureFixtureError("parent fixture binding changed")
        if not self.acknowledged and self.parent.poll(0):
            observed = receive(self.parent, timeout=0)
            if observed != packet("ENTERED", expected, self.deadline):
                raise CaptureFixtureError("entered acknowledgement differs")
            self.acknowledged = True
        return self.acknowledged

    def release(self, identity, generation):
        if self.release_sent or not self.acknowledged or binding(identity, generation) != self.owner:
            raise CaptureFixtureError("cannot release another or unentered fixture")
        send(self.parent, packet("RELEASE", self.owner, self.deadline))
        self.release_sent = True

    def close(self):
        if self.closed:
            return
        self.closed = True
        if self.router._context is self.context:
            self.router._context = self.real_context
        try:
            if self.owner is not None:
                if not self.release_sent:
                    send(self.parent, packet("RELEASE", self.owner, self.deadline))
                    self.release_sent = True
                send(self.parent, packet("ABORT", self.owner, self.deadline))
        except (BrokenPipeError, EOFError, OSError):
            pass  # The exact target may already have been killed by supervision.
        finally:
            self.parent.close()
            self.child.close()
