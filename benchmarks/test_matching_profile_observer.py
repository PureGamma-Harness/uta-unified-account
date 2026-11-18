"""Six CODE-only lifecycle models; no real UTA/SQLite/sys.monitoring import.

Only SqlObserver's AST is compiled in the future test command. All frame,
monitor, audit and connection objects below are synthetic; readiness/cProfile
coexistence still require separately authorized native evidence.
"""
import ast
from collections import Counter
import dis
import json
from pathlib import Path
import traceback
from types import SimpleNamespace
import unittest
import weakref


class ModelDatabase:
    def _connect(self, connection):
        connection.execute("synthetic code boundary, never executed")


def unknown_connect_model():
    pass


class ModelConnection:
    def __init__(self, name, log, attach_error=None):
        self.name, self.log, self.attach_error = name, log, attach_error
        self.ready, self.callback, self.attach_calls = False, None, 0

    def set_trace_callback(self, callback):
        self.attach_calls += 1
        if not self.ready:
            raise RuntimeError("synthetic connection is not initialized")
        if self.attach_error:
            raise RuntimeError(self.attach_error)
        self.callback = callback
        self.log.append((self.name, "attach"))

    def execute_model(self, statement):
        if self.callback is None:
            raise AssertionError("synthetic SQL reached before attach")
        self.log.append((self.name, statement.split()[0]))
        self.callback(statement)


class ModelMonitor:
    events = SimpleNamespace(LINE=1)

    def __init__(self, environment):
        self.environment = environment
        self.tools, self.callbacks, self.local = {}, {}, {}
        self.calls, self.fail_register = [], False

    def get_tool(self, tool):
        return self.tools.get(tool)

    def use_tool_id(self, tool, name):
        if tool in self.tools:
            raise ValueError("synthetic occupied slot")
        self.tools[tool] = name
        self.calls.append(("use", tool))

    def register_callback(self, tool, event, callback):
        if self.fail_register and callback is not None:
            raise RuntimeError("synthetic monitor registration failure")
        previous = self.callbacks.get((tool, event))
        self.callbacks[(tool, event)] = callback
        self.calls.append(("callback", tool, callback is not None))
        return previous

    def set_local_events(self, tool, code, mask):
        self.local[(tool, code)] = mask
        self.calls.append(("local", tool, mask))

    def free_tool_id(self, tool):
        del self.tools[tool]
        self.calls.append(("free", tool))

    def line(self, frame, line=None):
        self.environment.frame = frame
        callback = self.callbacks.get((3, self.events.LINE))
        if callback is not None and self.local.get((3, frame.f_code)) == self.events.LINE:
            callback(frame.f_code, frame.f_code.co_firstlineno if line is None else line)


class ModelEnvironment:
    def __init__(self):
        self.hooks, self.log = [], []
        self.frame = SimpleNamespace(f_code=ModelDatabase._connect.__code__)
        self.monitor = ModelMonitor(self)
        self.sys = SimpleNamespace(monitoring=self.monitor, addaudithook=self.hooks.append,
                                   _getframe=lambda depth: self.frame)

    def handle(self, connection, frame=None):
        self.frame = frame or SimpleNamespace(f_code=ModelDatabase._connect.__code__)
        self.log.append((connection.name, "audit"))
        for hook in tuple(self.hooks):
            hook("sqlite3.connect/handle", (connection,))
        return self.frame

    def returned(self, connection, frame):
        connection.ready = True
        self.log.append((connection.name, "returned"))
        self.monitor.line(frame)


def observer_class(environment):
    source = Path(__file__).with_name("matching_profile_case.py").read_text()
    tree = ast.parse(source)
    node = next(item for item in tree.body if isinstance(item, ast.ClassDef) and item.name == "SqlObserver")
    def require(value, message):
        if not value:
            raise AssertionError(message)
    namespace = {"Counter": Counter, "dis": dis, "traceback": traceback, "require": require, "sys": environment.sys,
                 "Database": ModelDatabase, "sqlite3": SimpleNamespace(Connection=ModelConnection),
                 "canonical": lambda value: json.dumps(value, sort_keys=True, separators=(",", ":")).encode("ascii")}
    exec(compile(ast.Module(body=[node], type_ignores=[]), "SqlObserver-lifecycle-model", "exec"), namespace)
    return namespace["SqlObserver"]


class ObserverLifecycleContracts(unittest.TestCase):
    def test_return_attach_before_first_SQL_and_budget_stays_fatal(self):
        env = ModelEnvironment()
        observer = observer_class(env)()
        observer.install()
        for name in ("first", "second"):
            connection = ModelConnection(name, env.log)
            frame = env.handle(connection)
            self.assertEqual(connection.attach_calls, 0)
            env.returned(connection, frame)
            connection.execute_model("PRAGMA synthetic_only")
        snapshot = observer.snapshot()
        self.assertEqual((snapshot["handles_observed"], snapshot["attach_attempts"], snapshot["connections"]), (2, 2, 2))
        self.assertEqual(snapshot["events"], {"PRAGMA": 2})
        for name in ("first", "second"):
            self.assertEqual([event for owner, event in env.log if owner == name], ["audit", "returned", "attach", "PRAGMA"])
        # Original event ceiling remains a fatal, first-fault condition.
        observer.total_events = 1000000
        observer._trace("SELECT synthetic_only")
        self.assertEqual(observer.failure["category"], "sqlite_trace_event_budget_exceeded")
        with self.assertRaises(AssertionError):
            observer.snapshot()
        self.assertIs(observer.close()["tool_owned_after_close"], False)

    def test_unknown_callsite_remains_pending_and_close_drops_references(self):
        env = ModelEnvironment()
        observer = observer_class(env)()
        observer.install()
        connection = ModelConnection("unknown", env.log)
        reference = weakref.ref(connection)
        frame = env.handle(connection, SimpleNamespace(f_code=unknown_connect_model.__code__))
        connection.ready = True
        env.monitor.line(frame)
        self.assertEqual(connection.attach_calls, 0)
        self.assertEqual(observer.failure["category"], "sqlite_unknown_connect_callsite")
        self.assertEqual(len(observer.pending), 1)
        with self.assertRaises(AssertionError):
            observer.snapshot()
        state = observer.close()
        self.assertEqual((state["pending_references"], state["unattached_at_close"]), (0, 1))
        self.assertIs(state["active"], False)
        del connection
        self.assertIsNone(reference())

    def test_owned_handle_without_return_LINE_or_late_LINE_is_not_complete(self):
        env = ModelEnvironment()
        observer = observer_class(env)()
        observer.install()
        connection = ModelConnection("no-line", env.log)
        env.handle(connection)
        self.assertEqual(observer.connections["setup"], 0)
        with self.assertRaises(AssertionError):
            observer.snapshot()
        self.assertEqual(observer.failure["category"], "sqlite_unattached_pending_handle")
        state = observer.close()
        self.assertEqual(state["pending_references"], 0)
        self.assertIs(state["all_handles_attached"], False)
        # A delivered LINE after the first explicit SQL is also incomplete;
        # it must never be used as an opportunistic late attachment.
        late_env = ModelEnvironment()
        late = observer_class(late_env)()
        late.install()
        late_connection = ModelConnection("late", late_env.log)
        late_frame = late_env.handle(late_connection)
        late_connection.ready = True
        late_env.monitor.line(late_frame, late.first_sql_line + 1)
        self.assertEqual(late_connection.attach_calls, 0)
        with self.assertRaises(AssertionError):
            late.snapshot()
        self.assertEqual(late.failure["category"], "sqlite_trace_install_failed")
        late.close()

    def test_unsupported_occupied_and_registration_failure_do_not_steal(self):
        # Three explicitly bounded API/ownership variants, one contract method.
        for variant in ("unsupported", "occupied", "register-error"):
            env = ModelEnvironment()
            if variant == "unsupported":
                env.sys.monitoring = None
            elif variant == "occupied":
                env.monitor.tools[3] = "foreign-owner"
            else:
                env.monitor.fail_register = True
            observer = observer_class(env)()
            with self.assertRaises(AssertionError):
                observer.install()
            first = observer.failure
            self.assertEqual(first["category"], "sqlite_monitor_slot_occupied" if variant == "occupied" else "sqlite_monitor_install_failed")
            observer.close()
            self.assertIs(observer.failure, first)
            if variant == "occupied":
                self.assertEqual(env.monitor.tools[3], "foreign-owner")
                self.assertEqual(env.monitor.calls, [])
            else:
                self.assertIsNone(env.monitor.get_tool(3))

    def test_attach_error_is_bounded_first_fault_not_overwritten(self):
        env = ModelEnvironment()
        observer = observer_class(env)()
        observer.install()
        connection = ModelConnection("rejected", env.log, "synthetic attach failure " + "x" * 5000)
        frame = env.handle(connection)
        env.returned(connection, frame)
        first = observer.failure
        self.assertEqual(first["category"], "sqlite_trace_install_failed")
        self.assertEqual(first["event"], "post_connect_local_LINE")
        self.assertEqual(first["exception"]["type"]["text"], "builtins.RuntimeError")
        self.assertEqual(len(first["exception"]["message"]["text"].encode()), 512)
        self.assertIs(first["exception"]["message"]["truncated"], True)
        class BadStatement:
            def __getitem__(self, unused):
                raise ValueError("later category error")
        observer._trace(BadStatement())
        self.assertIs(observer.failure, first)
        with self.assertRaises(AssertionError):
            observer.snapshot()
        observer.close()

    def test_close_then_new_observer_leaves_old_hook_inert(self):
        env = ModelEnvironment()
        observer_type = observer_class(env)
        old = observer_type()
        old.install()
        first = ModelConnection("old", env.log)
        env.returned(first, env.handle(first))
        first.execute_model("PRAGMA synthetic_only")
        old_counts = (dict(old.handles), dict(old.connections), dict(old.events))
        self.assertIs(old.close()["owned_tool_released"], True)
        new = observer_type()
        new.install()
        old.close()  # Must never release the new observer's same-number tool.
        self.assertIs(env.monitor.callbacks[(3, 1)], new.line_callback)
        second = ModelConnection("new", env.log)
        env.returned(second, env.handle(second))
        second.execute_model("PRAGMA synthetic_only")
        second.execute_model("BEGIN synthetic_only")
        second.execute_model("COMMIT")
        first.execute_model("SELECT after-old-close")
        self.assertEqual((dict(old.handles), dict(old.connections), dict(old.events)), old_counts)
        self.assertEqual(new.snapshot()["events"], {"PRAGMA": 1, "BEGIN": 1, "COMMIT": 1})
        self.assertEqual((new.handles["setup"], new.connections["setup"]), (1, 1))
        self.assertIsNone(new.failure)
        state = new.close()
        self.assertEqual((state["active"], state["pending_references"], state["tool_owned_after_close"]), (False, 0, False))
        self.assertIsNone(env.monitor.get_tool(3))


if __name__ == "__main__":
    unittest.main()
