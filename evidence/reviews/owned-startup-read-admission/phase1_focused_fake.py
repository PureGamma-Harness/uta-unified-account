"""Twelve methods /48 small pure traces of selected actual observation code.

No UTA import, SQLite connection, native worker, real lock/thread/process,
signal, network or sleep. Relative imports in selected methods are intercepted
by an in-memory module provider, not removed. Guard/schema/role enforcement and
COMMIT are explicitly fake boundaries; this is not native or financial proof.
"""
import ast
from contextlib import contextmanager
from copy import copy
from dataclasses import dataclass
from hashlib import sha256
from io import StringIO
from itertools import islice
import builtins
import json
import math
from pathlib import Path
import re
from types import MappingProxyType, ModuleType, SimpleNamespace
import unittest


ROOT = Path(__file__).resolve().parents[3]
TRACES = 0
INPUT_NAMES = ("uta/writer_fence.py", "uta/startup.py", "tools/run_validation.py")


def input_bytes(name):
    # The once driver passes only bytes whose materialized length/SHA it has
    # just verified. Selected AST must not reread a potentially different file.
    values = globals().get("_FROZEN_INPUT_BYTES")
    if type(values) is not MappingProxyType:
        raise RuntimeError("focused fixture requires the reviewed materialized-input driver")
    raw = values.get(name)
    if type(raw) is not bytes:
        raise RuntimeError("frozen source-byte input is absent")
    return raw


class Error(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


class SQLiteError(Exception):
    pass


@dataclass(frozen=True)
class Token:
    authority_id: str = "synthetic-authority"
    owner_nonce: str = "synthetic-binding-tag"
    generation: int = 1
    process_id: int = 17


class Lock:
    def __enter__(self):
        return self

    def __exit__(self, *unused):
        return False


class Clock:
    def __init__(self):
        self.calls = 0
        self.fault_at = None
        self.fault = None

    def monotonic_ns(self):
        self.calls += 1
        if self.calls == self.fault_at:
            raise self.fault
        return self.calls * 10

    def monotonic(self):
        return .001


class Cursor:
    def __init__(self, rows):
        self.rows = rows

    def __iter__(self):
        return iter(self.rows)

    def fetchall(self):
        return list(self.rows)

    def fetchone(self):
        return self.rows[0] if self.rows else None


class Connection:
    def __init__(self):
        self.trace = []
        self.expires, self.observed, self.generation = 1000, 0, 1
        self.in_transaction = True
        self.sql_error = None

    def execute(self, sql, parameters=()):
        self.trace.append((sql, parameters))
        if self.sql_error is not None:
            raise self.sql_error
        if sql.startswith("SELECT name,type FROM sqlite_master"):
            return Cursor([(name, "table") for name in (
                "writer_fence_authority", "writer_fence_lease", "writer_fence_events",
                "writer_fence_guard_config", "writer_fence_guard_tables")])
        if sql.startswith("SELECT singleton,format,authority_id,canonical_path"):
            return Cursor([(1, 1, "synthetic-authority", "fake-authority.sqlite3")])
        if sql.startswith("SELECT singleton,generation,owner_nonce"):
            return Cursor([(1, self.generation, "synthetic-binding-tag", 17, "synthetic-boot",
                            self.expires, self.observed)])
        if sql == "PRAGMA database_list":
            return Cursor([(0, "main", "fake-authority.sqlite3")])
        if sql.startswith("SELECT sequence,kind,authority_id"):
            return Cursor([])
        if sql == "SELECT singleton,format FROM writer_fence_guard_config":
            return Cursor([(1, 1)])
        if sql.startswith("SELECT 1 FROM writer_fence_events WHERE kind="):
            return Cursor([])
        if sql.startswith("UPDATE writer_fence_lease SET expires_ns="):
            self.expires, self.observed = parameters
            return Cursor([])
        raise AssertionError("unexpected fake SQL statement")

    def set_authorizer(self, callback):
        self.authorizer = callback


class Database:
    def __init__(self, connection=None):
        self.connection = connection or Connection()
        self.path = "fake-authority.sqlite3"
        self.writer_token = Token()
        self.timeout = 10.0
        self.now, self.boot = 100, "synthetic-boot"
        self.enter_error = self.commit_error = None
        self.begins = self.commits = self.commit_attempts = self.rollbacks = 0
        self.commit_unknown = False

    @contextmanager
    def _fence_transaction(self):
        self.begins += 1
        if self.enter_error is not None:
            raise self.enter_error
        try:
            yield self.connection
        except BaseException:
            self.rollbacks += 1
            raise
        else:
            self.commit_attempts += 1
            if self.commit_unknown:
                self.commits += 1
                raise self.commit_error
            if self.commit_error is not None:
                raise self.commit_error
            self.commits += 1

    @contextmanager
    def read_transaction(self):
        yield self.connection


def selected_class(tree, name, methods):
    source = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == name)
    return ast.ClassDef(name=name, bases=[], keywords=[],
                        body=[node for node in source.body if isinstance(node, ast.FunctionDef)
                              and node.name in methods], decorator_list=[])


class Environment:
    def __init__(self):
        self.clock = Clock()
        self.clock_calls = 0
        self.optional_import_error = None
        self.events = []
        self.writer_raw = input_bytes("uta/writer_fence.py")
        self.startup_raw = input_bytes("uta/startup.py")
        self.tool_raw = input_bytes("tools/run_validation.py")
        self.namespace = {"__name__": "_selected_phase1", "__package__": "_selected_phase1",
            "MappingProxyType": MappingProxyType, "ModuleType": ModuleType, "math": math,
            "contextmanager": contextmanager, "Database": Database, "WriterToken": Token,
            "WriterFenceError": Error, "time": self.clock, "re": re,
            "RLock": Lock, "get_ident": lambda: 1, "os": SimpleNamespace(getpid=lambda: 17),
            "sqlite3": SimpleNamespace(Connection=Connection, Error=SQLiteError), "copy": copy,
            "monotonic": self.clock.monotonic,
            "_verify_control_schema": lambda *unused: None,
            "_verify_data_guards": lambda *unused, **ignored: (),
            "_assert_joinable": lambda *unused: None}
        def clock(database):
            self.clock_calls += 1
            return database.now, database.boot
        self.namespace["_clock"] = clock
        original_import = builtins.__import__
        def virtual_import(name, globals=None, locals=None, fromlist=(), level=0):
            if level == 1 and name == "writer_fence":
                if (tuple(fromlist) == ("_lease_note_time", "_lease_observation")
                        and self.optional_import_error is not None):
                    raise self.optional_import_error
                return SimpleNamespace(**self.namespace)
            raise AssertionError("selected methods attempted a nonvirtual import")
        injected = dict(vars(builtins))
        injected["__import__"] = virtual_import
        self.namespace["__builtins__"] = injected
        tree = ast.parse(self.writer_raw)
        names = {"_BASE_NAMES", "_GUARD_NAMES", "_STANDARD_NAMES", "_BATCH_NAMES",
                 "_CREDIT_NAMES", "_CREDIT_V2_NAMES", "_NAMES", "_INVENTORIES", "_NAME",
                 "_MAX_INTEGER", "_REGISTRY", "_REGISTRY_LOCK", "_LEASE_OBSERVATION_TAG",
                 "_LEASE_OBSERVATION_ATTRIBUTE", "_LEASE_OBSERVATION_INTS",
                 "_LEASE_OBSERVATION_BOOLS", "_LEASE_OBSERVATION_ENUMS"}
        body = [node for node in tree.body if isinstance(node, ast.Assign)
                and any(isinstance(target, ast.Name) and target.id in names for target in node.targets)]
        functions = {"_lease_observation", "_lease_note_time", "_lease_set", "_lease_annotation",
                     "_observed_load", "_read_guard_observation", "_lease_load_note",
                     "_load", "_observed", "_assert_token", "_require_guard_format", "_ttl"}
        body += [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in functions]
        body += [selected_class(tree, "WriterFence", {"__init__", "renew", "assert_writer"}),
                 selected_class(tree, "_TransactionGuard", {"__init__"})]
        exec(compile(ast.fix_missing_locations(ast.Module(body=body, type_ignores=[])),
                     "<actual-selected-fence-code>", "exec"), self.namespace)
        self.fence_class = self.namespace["WriterFence"]
        self.fence_class._event = lambda owner, connection, kind, state, now: self.events.append((kind, now))
        self.namespace["_TransactionGuard"]._authorize = lambda *unused: 0
        startup = ast.parse(self.startup_raw)
        own = selected_class(startup, "_OwnedStartup", {
            "_renew_diagnostic", "_annotate_lease_failure", "_renew", "verify_ledger", "verify_credit"})
        exec(compile(ast.fix_missing_locations(ast.Module(body=[own], type_ignores=[])),
                     "<actual-selected-startup-code>", "exec"), self.namespace)
        self.original_import = original_import  # Not called by selected code.

    def state(self, **changes):
        return {"authority_id": "synthetic-authority", "owner_nonce": "synthetic-binding-tag",
                "generation": 1, "owner_pid": 17, "boot_id": "synthetic-boot",
                "expires_ns": 1000, "observed_ns": 0, "guard_format": 1, **changes}

    def owned(self, database=None):
        scope = self.namespace["_OwnedStartup"]()
        scope.database = database or Database()
        scope.token = scope.database.writer_token
        scope.lease_seconds = .4
        scope._lease_diagnostic_state = (None, None)
        scope._lock = Lock()
        scope.check = lambda: None
        scope._check_identity = lambda database: None
        scope.require_database = lambda database: None
        scope.require_ledger = lambda exchange: None
        scope._schema = lambda connection: (("unchanged",),)
        scope._exchange = scope._credit = None
        scope._ledger_verified = False
        scope.last_renew_started = None
        return scope

    def annotation(self, error):
        data = BaseException.__dict__["__dict__"].__get__(error, BaseException)
        value = data.get("_uta_lease_observation_v1")
        if (type(value) is tuple and len(value) == 2
                and value[0] is self.namespace["_LEASE_OBSERVATION_TAG"]):
            return dict(value[1])
        return None

    def collector(self):
        module = ModuleType("uta.writer_fence")
        vars(module)["_LEASE_OBSERVATION_TAG"] = self.namespace["_LEASE_OBSERVATION_TAG"]
        namespace = {"sys": SimpleNamespace(modules={"uta.writer_fence": module}),
                     "MappingProxyType": MappingProxyType, "ModuleType": ModuleType,
                     "unittest": unittest, "re": re, "json": json, "islice": islice}
        tree = ast.parse(self.tool_raw)
        selected = [node for node in tree.body if (
            isinstance(node, ast.Assign) and any(isinstance(target, ast.Name)
            and target.id.startswith("_LEASE_CAPTURE_") for target in node.targets))
            or isinstance(node, ast.FunctionDef) and node.name.startswith("_lease_")
            or isinstance(node, ast.ClassDef) and node.name == "_LeaseObservedResult"]
        exec(compile(ast.fix_missing_locations(ast.Module(body=selected, type_ignores=[])),
                     "<actual-selected-collector-code>", "exec"), namespace)
        return namespace


class MarkerCase(unittest.TestCase):
    def test_marker(self):
        pass


class Phase1FocusedFakeTests(unittest.TestCase):
    def mark(self):
        global TRACES
        TRACES += 1

    def test_01_strict_primitive_filter_and_no_nonce(self):
        examples = [({"version": 1, "assert_now_ns": 7}, {"version": 1, "assert_now_ns": 7}),
                    ({"version": True, "owner_nonce": "never-export", "assert_now_ns": float("nan")}, {}),
                    ({"snapshot_time_known": True, "phase": "unreviewed", "assert_generation": -1}, {}),
                    ({"renew_attempt_state": "failed_or_unknown", "elapsed_clock": "monotonic_ns"},
                     {"renew_attempt_state": "failed_or_unknown", "elapsed_clock": "monotonic_ns"})]
        for values, expected in examples:
            self.mark()
            env = Environment()
            filtered = env.namespace["_lease_observation"](values)
            self.assertEqual(dict(filtered), expected)

    def test_02_primary_annotation_identity_chain_and_unknown_attribute(self):
        for mode in ("normal", "unknown_existing", "helper_raises", "metadata_getter_raises"):
            self.mark()
            env = Environment()
            error = Error("lease_expired", "original-primary")
            cause, context = ValueError("cause"), LookupError("context")
            error.__cause__, error.__context__ = cause, context
            if mode == "unknown_existing":
                error._uta_lease_observation_v1 = "unknown-owner"
            if mode == "helper_raises":
                env.namespace["_lease_observation"] = lambda values: (_ for _ in ()).throw(KeyboardInterrupt())
            if mode == "metadata_getter_raises":
                callbacks = []
                class Values(dict):
                    def items(self):
                        callbacks.append("items")
                        raise SystemExit(99)
                values = Values(version=1)
            else:
                values = {"version": 1}
            env.namespace["_lease_annotation"](error, values)
            self.assertEqual(error.args, ("original-primary",))
            self.assertEqual(error.code, "lease_expired")
            self.assertIs(error.__cause__, cause)
            self.assertIs(error.__context__, context)
            if mode == "unknown_existing":
                self.assertEqual(error._uta_lease_observation_v1, "unknown-owner")
            if mode == "metadata_getter_raises":
                self.assertEqual(callbacks, [])

    def test_03_one_load_sql_trace_row_fetch_and_primary(self):
        for mode in ("trace", "timing", "clock_exception", "sql_primary"):
            self.mark()
            env = Environment()
            observed = Connection()
            reference = json.loads(input_bytes(
                "evidence/reviews/owned-startup-read-admission/phase1-original-reference.json"))["normal_fake_load"]
            expected_trace = [(item["sql"], tuple(item["parameters"])) for item in reference["ordered_SQL_and_parameters"]]
            if mode == "clock_exception":
                env.clock.fault_at, env.clock.fault = 1, ValueError("optional clock")
            if mode == "sql_primary":
                failure = OSError("original SQL primary")
                observed.sql_error = failure
                with self.assertRaises(OSError) as caught:
                    env.namespace["_observed_load"](observed, "guard")
                self.assertIs(caught.exception, failure)
                self.assertEqual(observed.trace, expected_trace[:1])
                continue
            actual, fields = env.namespace["_observed_load"](observed, "guard")
            self.assertEqual(actual, reference["returned_state"])
            self.assertEqual(observed.trace, expected_trace)
            self.assertIs(fields["snapshot_time_known"], False)
            if mode == "timing":
                self.assertLess(fields["guard_lease_fetch_started_ns"], fields["guard_lease_fetch_finished_ns"])
                self.assertLess(fields["guard_lease_fetch_finished_ns"], fields["guard_load_finished_ns"])

    def test_04_cancellation_before_sql_and_guard_registration(self):
        for mode in ("keyboard", "system_exit", "ordinary", "guard_final_clock"):
            self.mark()
            env, connection = Environment(), Connection()
            env.clock.fault_at = 5 if mode == "guard_final_clock" else 1
            env.clock.fault = ValueError("optional") if mode == "ordinary" else (
                SystemExit(7) if mode == "system_exit" else KeyboardInterrupt())
            if mode == "ordinary":
                env.namespace["_observed_load"](connection, "guard")
                self.assertGreater(len(connection.trace), 0)
            elif mode == "guard_final_clock":
                with self.assertRaises(KeyboardInterrupt):
                    env.namespace["_TransactionGuard"](Database(connection), connection, "read")
                self.assertEqual(env.namespace["_REGISTRY"], {})
            else:
                with self.assertRaises(type(env.clock.fault)):
                    env.namespace["_observed_load"](connection, "guard")
                self.assertEqual(connection.trace, [])

    def test_05_original_clock_once_expiry_and_created_primary_fault(self):
        for mode in ("live", "expired", "wrong_generation", "created_primary_metadata_fault"):
            self.mark()
            env, database = Environment(), Database()
            created = []
            class RecordingError(Error):
                def __init__(self, code, message):
                    super().__init__(code, message)
                    created.append(self)
            env.namespace["WriterFenceError"] = RecordingError
            state = env.state()
            if mode in ("expired", "created_primary_metadata_fault"):
                state["expires_ns"] = database.now
            if mode == "wrong_generation":
                state["generation"] = 2
            if mode == "created_primary_metadata_fault":
                class FaultState(dict):
                    generation_reads = 0
                    def __getitem__(self, key):
                        if key == "generation":
                            self.generation_reads += 1
                            if self.generation_reads == 2:
                                raise KeyboardInterrupt()
                        return super().__getitem__(key)
                state = FaultState(state)
            if mode == "live":
                env.namespace["_assert_token"](database, state, database.writer_token)
            else:
                with self.assertRaises(Error) as caught:
                    env.namespace["_assert_token"](database, state, database.writer_token)
                self.assertEqual(caught.exception.code,
                                 "writer_fenced" if mode == "wrong_generation" else "lease_expired")
                self.assertIs(caught.exception, created[-1])
                self.assertEqual(caught.exception.args,
                    ("transaction does not own the current authority generation in this process",)
                    if mode == "wrong_generation" else ("writer lease expired; renew cannot revive it",))
            self.assertEqual(env.clock_calls, 1)

    def test_06_guard_assert_plumbing_and_optional_annotation_call_failure(self):
        for mode in ("plumbing", "annotation_call_fault", "metadata_clock_fault", "nonread"):
            self.mark()
            env, database = Environment(), Database()
            originals = []
            original_cause, original_context = LookupError("cause"), OSError("context")
            class RecordingError(Error):
                def __init__(self, code, message):
                    super().__init__(code, message)
                    self.__cause__, self.__context__ = original_cause, original_context
                    originals.append(self)
            env.namespace["WriterFenceError"] = RecordingError
            if mode == "nonread":
                env.namespace["_REGISTRY"][id(database.connection)] = SimpleNamespace(
                    connection=database.connection, role="financial")
            else:
                env.namespace["_TransactionGuard"](database, database.connection, "read")
            if mode == "metadata_clock_fault":
                env.clock.fault_at, env.clock.fault = env.clock.calls + 1, RuntimeError("clock")
            if mode == "annotation_call_fault":
                env.namespace["_lease_annotation"] = lambda *args: (_ for _ in ()).throw(SystemExit(13))
            database.now = database.connection.expires
            with self.assertRaises(Error) as caught:
                env.fence_class(database).assert_writer(database.connection)
            self.assertIs(caught.exception, originals[-1])
            self.assertEqual(caught.exception.code, "lease_expired")
            self.assertEqual(caught.exception.args, ("writer lease expired; renew cannot revive it",))
            self.assertIs(caught.exception.__cause__, original_cause)
            self.assertIs(caught.exception.__context__, original_context)
            if mode == "plumbing":
                fields = env.annotation(caught.exception)
                self.assertIn("guard_validation_finished_ns", fields)
                self.assertIn("assert_lease_fetch_finished_ns", fields)
                self.assertIs(fields["snapshot_time_known"], False)

    def test_07_known_commit_and_transaction_unknown_never_invent_receipt(self):
        for mode in ("success", "begin_error", "commit_unknown", "event_error"):
            self.mark()
            env, database = Environment(), Database()
            fence = env.fence_class(database)
            failure = OSError("original transaction primary")
            if mode == "begin_error":
                database.enter_error = failure
            elif mode == "commit_unknown":
                database.commit_unknown, database.commit_error = True, failure
            elif mode == "event_error":
                env.fence_class._event = lambda *args: (_ for _ in ()).throw(failure)
            if mode == "success":
                self.assertIs(fence.renew(database.writer_token, .4), database.writer_token)
                self.assertIs(fence._last_renewal_token, database.writer_token)
                self.assertIs(fence._last_renewal_observation["renew_known_commit"], True)
                self.assertEqual(fence._last_renewal_observation["renew_expires_ns"], 400_000_100)
                self.assertEqual(database.commits, 1)
                self.assertEqual(len(env.events), 1)
                self.assertEqual(sum(sql.startswith("UPDATE writer_fence_lease") for sql, _ in database.connection.trace), 1)
            else:
                with self.assertRaises(OSError) as caught:
                    fence.renew(database.writer_token, .4)
                self.assertIs(caught.exception, failure)
                self.assertIsNone(fence._last_renewal_observation)
                self.assertIsNone(fence._last_renewal_token)

    def test_08_owned_same_token_last_known_and_postcommit_wrapper_unknown(self):
        for mode in ("known", "wrapper_unknown", "wrong_receipt_token", "optional_import_error"):
            self.mark()
            env, scope = Environment(), None
            scope = env.owned()
            keeper_databases = []
            original_copy = env.namespace["copy"]
            def observe_copy(database):
                keeper_database = original_copy(database)
                keeper_databases.append(keeper_database)
                return keeper_database
            env.namespace["copy"] = observe_copy
            old = MappingProxyType({"version": 1, "last_known_renew_attempt": 1,
                                    "last_known_renew_expires_ns": 410, "last_known_renew_same_token": True})
            scope._lease_diagnostic_state = (MappingProxyType({"renew_attempt": 1,
                                                              "renew_attempt_state": "known_commit"}), old)
            original = env.fence_class.renew
            failure = OSError("lost response after original COMMIT")
            if mode == "wrapper_unknown":
                def wrapped(fence, token, ttl):
                    original(fence, token, ttl)
                    raise failure
                env.fence_class.renew = wrapped
            elif mode == "wrong_receipt_token":
                def wrong(fence, token, ttl):
                    result = original(fence, token, ttl)
                    fence._last_renewal_token = Token()
                    return result
                env.fence_class.renew = wrong
            elif mode == "optional_import_error":
                env.optional_import_error = ImportError("optional helper unavailable")
            if mode == "wrapper_unknown":
                with self.assertRaises(OSError) as caught:
                    scope._renew()
                self.assertIs(caught.exception, failure)
                self.assertEqual(scope._lease_diagnostic_state[1], old)
                self.assertEqual(scope._lease_diagnostic_state[0]["renew_attempt_state"], "failed_or_unknown")
            else:
                scope._renew()
                if mode == "known":
                    self.assertEqual(scope._lease_diagnostic_state[1]["last_known_renew_attempt"], 2)
                else:
                    self.assertEqual(scope._lease_diagnostic_state[1], old)
            self.assertEqual(len(keeper_databases), 1)
            keeper_database = keeper_databases[0]
            self.assertIsNot(keeper_database, scope.database)
            self.assertIs(keeper_database.connection, scope.database.connection)
            self.assertEqual(keeper_database.commits, 1)
            self.assertEqual(scope.database.commits, 0)

    def test_09_owned_read_primary_retained_before_any_verifier(self):
        for mode in ("ledger", "credit", "helper_raises", "existing_unknown_attribute"):
            self.mark()
            env, scope = Environment(), None
            scope = env.owned()
            primary = Error("lease_expired", "original read-entry primary")
            if mode == "existing_unknown_attribute":
                primary._uta_lease_observation_v1 = "other-owner"
            class RejectingFence:
                def __init__(self, database):
                    pass
                def assert_writer(self, *args):
                    raise primary
            env.namespace["WriterFence"] = RejectingFence
            if mode == "helper_raises":
                scope._annotate_lease_failure = lambda *args: (_ for _ in ()).throw(KeyboardInterrupt())
            verifies = []
            exchange = SimpleNamespace(database=scope.database,
                ledger=SimpleNamespace(verify=lambda **kwargs: verifies.append("ledger")))
            credit = SimpleNamespace(exchange=exchange, _verify=lambda connection: verifies.append("credit"))
            with self.assertRaises(Error) as caught:
                scope.verify_credit(credit) if mode == "credit" else scope.verify_ledger(exchange)
            self.assertIs(caught.exception, primary)
            self.assertEqual(primary.args, ("original read-entry primary",))
            self.assertEqual(verifies, [])
            if mode == "existing_unknown_attribute":
                self.assertEqual(primary._uta_lease_observation_v1, "other-owner")

    def test_10_collector_bookkeeping_first_no_import_and_no_nonce(self):
        for mode in ("valid", "missing_module", "unknown_attribute", "collector_raises"):
            self.mark()
            env = Environment()
            namespace = env.collector()
            primary = Error("lease_expired", "original primary")
            env.namespace["_lease_annotation"](primary, {"version": 1, "assert_now_ns": 3,
                                                        "owner_nonce": "never-export"})
            if mode == "missing_module":
                namespace["sys"].modules.clear()
            elif mode == "unknown_attribute":
                primary._uta_lease_observation_v1 = "unknown-owner"
            elif mode == "collector_raises":
                namespace["_lease_error_fields"] = lambda error: (_ for _ in ()).throw(SystemExit(19))
            result = namespace["_LeaseObservedResult"](StringIO(), True, 0)
            result.addError(MarkerCase("test_marker"), (type(primary), primary, None))
            self.assertEqual(len(result.errors), 1)
            self.assertFalse(result.wasSuccessful())
            self.assertEqual(len(result.lease_observations), 1 if mode == "valid" else 0)
            self.assertNotIn("never-export", json.dumps(result.lease_observations))

    def test_11_worker_projection_revalidates_mutable_state_and_caps(self):
        for mode in ("valid", "bad_values", "capsules", "bad_test"):
            self.mark()
            env, namespace = Environment(), None
            namespace = env.collector()
            result = namespace["_LeaseObservedResult"](StringIO(), True, 0)
            capsule = {"test": "synthetic.Case.test_marker", "lease": {"version": 1, "assert_now_ns": 7}}
            if mode == "bad_values":
                capsule["lease"].update(version=True, owner_nonce="never-export", assert_now_ns=float("inf"))
            if mode == "bad_test":
                capsule["test"] = "header=value [private]"
            result.lease_observations = [copy(capsule) for _ in range(17 if mode == "capsules" else 1)]
            output = namespace["_lease_result_projection"](result)
            self.assertLessEqual(len(output["lease_observations"]), 16)
            self.assertNotIn("never-export", json.dumps(output))
            if mode in ("bad_values", "bad_test"):
                self.assertEqual(output["lease_observations"], [])
            if mode == "capsules":
                self.assertIs(output["lease_observations_truncated"], True)

    def test_12_static_sql_and_original_lifecycle_reference(self):
        reference = json.loads(input_bytes("evidence/reviews/owned-startup-read-admission/phase1-original-reference.json"))
        for mode in ("sql", "lifecycle", "original_tests", "publication_filter"):
            self.mark()
            env = Environment()
            if mode == "sql":
                for name in INPUT_NAMES:
                    tree = ast.parse(input_bytes(name))
                    observed = sorted(ast.dump(node.args[0], include_attributes=False)
                        for node in ast.walk(tree) if isinstance(node, ast.Call)
                        and isinstance(node.func, ast.Attribute) and node.func.attr in ("execute", "executemany")
                        and node.args)
                    self.assertEqual(observed, reference["SQL_call_argument_AST"][name])
            elif mode == "lifecycle":
                tree = ast.parse(env.startup_raw)
                cls = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "_OwnedStartup")
                for name, expected in reference["lifecycle_AST"].items():
                    method = next(node for node in cls.body if isinstance(node, ast.FunctionDef) and node.name == name)
                    self.assertEqual(ast.dump(method, include_attributes=False), expected)
            elif mode == "original_tests":
                for name, expected in reference["unchanged_test_SHA256"].items():
                    self.assertEqual(sha256(input_bytes(name)).hexdigest(), expected)
            else:
                namespace = env.collector()
                self.assertEqual(env.namespace["_LEASE_OBSERVATION_INTS"], namespace["_LEASE_CAPTURE_INTS"])
                self.assertEqual(env.namespace["_LEASE_OBSERVATION_BOOLS"], namespace["_LEASE_CAPTURE_BOOLS"])
                self.assertEqual(env.namespace["_LEASE_OBSERVATION_ENUMS"], namespace["_LEASE_CAPTURE_ENUMS"])
                # Independent size bound for16 capsules with the maximum typed
                # field values and longest permitted256-byte test identifier.
                worst = {key: 2**63 - 1 for key in namespace["_LEASE_CAPTURE_INTS"]}
                worst.update({key: key != "snapshot_time_known" for key in namespace["_LEASE_CAPTURE_BOOLS"]})
                worst.update({key: max(values, key=len) for key, values in namespace["_LEASE_CAPTURE_ENUMS"].items()})
                capsule = {"test": "x" * 256, "lease": worst}
                self.assertLessEqual(16 * len(json.dumps(capsule, separators=(",", ":"))), 65536)


if __name__ == "__main__":
    result = unittest.TextTestRunner(verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(Phase1FocusedFakeTests))
    print(json.dumps({"scope": "SELECTED_ACTUAL_OBSERVATION_CODE_WITH_MEMORY_FAKES_ONLY",
        "methods": result.testsRun, "small_traces": TRACES,
        "failures": len(result.failures), "errors": len(result.errors),
        "passed": result.wasSuccessful(), "SQL_or_UTA_module_import": False,
        "native_thread_process_signal_network_or_real_sleep": False,
        "phase2_authorized": False, "native_or_financial_approved": False,
        "production_approved": False}, sort_keys=True))
    raise SystemExit(0 if result.wasSuccessful() else 1)
