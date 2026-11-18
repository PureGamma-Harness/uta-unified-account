"""CODE-only four fake contracts; no SQLite, UTA import or runtime readiness claim.

The future test command extracts only SqlObserver's AST. Synthetic connections
and events check diagnostics behavior; they never execute a SQL statement.
"""
import ast
from collections import Counter
import json
from pathlib import Path
import traceback
from types import SimpleNamespace
import unittest


def observer_class():
    source = Path(__file__).with_name("matching_profile_case.py").read_text()
    tree = ast.parse(source)
    node = next(item for item in tree.body if isinstance(item, ast.ClassDef) and item.name == "SqlObserver")
    hooks = []
    namespace = {"Counter": Counter, "traceback": traceback,
                 "sys": SimpleNamespace(addaudithook=hooks.append),
                 "canonical": lambda value: json.dumps(value, sort_keys=True, separators=(",", ":")).encode("ascii")}
    exec(compile(ast.Module(body=[node], type_ignores=[]), "SqlObserver-fake-contract", "exec"), namespace)
    return namespace["SqlObserver"], hooks


class ObserverContracts(unittest.TestCase):
    def test_attach_fault_bounded_and_snapshot_still_rejects(self):
        observer_type, hooks = observer_class()
        observer = observer_type()
        observer.phase = "setup32-scan"
        observer.install()
        class RejectedConnection:
            def set_trace_callback(self, callback):
                raise RuntimeError("synthetic attach failure " + "x" * 5000)
        hooks[0]("sqlite3.connect/handle", (RejectedConnection(),))
        fault = observer.failure
        self.assertEqual((fault["category"], fault["phase"], fault["event"]),
                         ("sqlite_trace_install_failed", "setup32-scan", "sqlite3.connect/handle"))
        self.assertEqual(fault["exception"]["type"]["text"], "builtins.RuntimeError")
        self.assertEqual(len(fault["exception"]["message"]["text"].encode()), 512)
        self.assertIs(fault["exception"]["message"]["truncated"], True)
        self.assertEqual((fault["total_trace_events"], fault["connections_in_phase"]), (0, 0))
        self.assertLessEqual(len(fault["exception"]["stack"]), 6)
        self.assertIs(fault["expanded_SQL_statement_copied"], False)
        with self.assertRaisesRegex(AssertionError, "first_fault=.*synthetic attach failure"):
            observer.snapshot()

    def test_callback_fault_is_first_and_cannot_be_overwritten(self):
        observer_type, hooks = observer_class()
        observer = observer_type()
        observer.install()
        class BadStatement:
            def __getitem__(self, key):
                raise ValueError("synthetic category failure")
        observer._trace(BadStatement())
        first = observer.failure
        class LaterConnection:
            def set_trace_callback(self, callback):
                raise RuntimeError("later must not replace original")
        hooks[0]("sqlite3.connect/handle", (LaterConnection(),))
        self.assertIs(observer.failure, first)
        self.assertEqual(first["category"], "sqlite_trace_callback_failed")
        self.assertEqual(first["exception"]["type"]["text"], "builtins.ValueError")
        self.assertEqual(first["exception"]["message"]["text"], "synthetic category failure")
        with self.assertRaises(AssertionError):
            observer.snapshot()

    def test_event_budget_fault_remains_fatal(self):
        observer_type, unused = observer_class()
        observer = observer_type()
        observer.total_events = 1000000
        observer._trace("SELECT synthetic_only")
        self.assertEqual(observer.failure["category"], "sqlite_trace_event_budget_exceeded")
        self.assertEqual(observer.failure["total_trace_events"], 1000001)
        self.assertIsNone(observer.failure["exception"])
        with self.assertRaises(AssertionError):
            observer.snapshot()

    def test_success_counts_and_snapshot_unchanged(self):
        observer_type, hooks = observer_class()
        observer = observer_type()
        observer.install()
        class AcceptedConnection:
            def set_trace_callback(self, callback):
                self.callback = callback
        connection = AcceptedConnection()
        hooks[0]("sqlite3.connect/handle", (connection,))
        for text in ("BEGIN IMMEDIATE", "SELECT synthetic_only", "COMMIT"):
            connection.callback(text)
        self.assertIsNone(observer.failure)
        self.assertEqual(observer.snapshot(), {"phase": "setup", "events": {"BEGIN": 1, "SELECT": 1, "COMMIT": 1},
            "connections": 1, "counts_are_trace_events_including_trigger_repeats": True})


if __name__ == "__main__":
    unittest.main()
