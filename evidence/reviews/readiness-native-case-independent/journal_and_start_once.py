"""Pure behavioral negative controls for frozen native preparation source.

Only selected AST function definitions execute, with memory paths/writers and
an inert Process.start spy. No candidate module import, UTA, SQL, subprocess,
pidfd, /proc, network, signals, native run or actual filesystem adapter.
"""
import ast
from copy import deepcopy
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[3]
PREFIX = ROOT / "evidence/reviews/process-readiness-engineering"
PINS = {
    "native_safe_export.py": "690726615030d409c3c47bbb1ee3f188cb618d4d617a3e7a97b32e8fcf2aa4dc",
    "native_case_once.py": "5a009c63567433847f7c66a668650dc390668a3d98eca8f533023f7905c9be12",
}
SELECTOR = "test_process_readiness.ProcessReadinessTests.test_malformed_missing_and_oversize_persistent_quotes_fail_closed"
CONTROLS = [("market_invalid", False), ("market_missing", True), ("market_invalid", False)]


class ScopeUnknown(BaseException):
    pass


class MemoryPath:
    def __init__(self, files, path=""):
        self.files, self.path = files, path
    def __truediv__(self, suffix):
        return MemoryPath(self.files, self.path + "/" + suffix)
    def is_file(self):
        return self.path in self.files
    def read_bytes(self):
        return self.files[self.path]


def report(reason="ready"):
    return {"state_observed": True, "supervisor_alive": True, "workers_alive": True,
        "ready": reason == "ready", "financial_ready": reason == "ready", "managed": True,
        "decision_audit_required": False, "profile": "managed_development_legacy_gap", "reason": reason,
        "state": {"halted": False, "publishing": False, "epoch": 2, "market_version": 1,
                  "market_digest": "a" * 64, "watermarks": {"0": 2, "1": 2}, "error": None},
        "workers": [{"shard": shard, "pid": 9000 + shard, "owner_pid": 9000 + shard,
            "generation": 2, "alive": True, "lease_active": True, "owner_ready": True,
            "market_ready": reason == "ready", "funding_registry_ready": True, "reason": reason,
            "report": {"state": "ready", "shard": shard, "pid": 9000 + shard, "generation": 2}}
            for shard in (0, 1)]}


def fixture():
    rows = []
    def add(event, **fields):
        rows.append({"sequence": len(rows), "event": event, "monotonic_ns": len(rows) + 1, **fields})
    add("case_begin", selector=SELECTOR)
    add("activate_before", default_quote=True)
    first = report("publication_incomplete")
    first.update(ready=False, financial_ready=False)
    add("diagnostic_before", call=0)
    add("diagnostic_after", call=0, report=first)
    add("original_quote_created", quote={"version": 1, "observed_at": "2026-11-18T00:00:00+00:00", "payload_sha256": "b" * 64})
    add("diagnostic_before", call=1)
    add("diagnostic_after", call=1, report=report())
    add("activate_after")
    for call, (expected, missing) in enumerate(CONTROLS, 2):
        add("original_offline_fault_before", missing=missing, payload_bytes=0 if missing else 7)
        add("original_offline_fault_after", missing=missing)
        add("diagnostic_before", call=call)
        add("diagnostic_after", call=call, report=report(expected))
        add("original_subtest", expected=expected, missing=missing, passed=True)
    final = {"selector": SELECTOR, "tests_run": 1, "failures": 0, "errors": 0, "skipped": 0,
        "all_original_negative_controls_reached": True,
        "subtests": [{"expected": expected, "missing": missing, "passed": True} for expected, missing in CONTROLS],
        "test_result": "PASS", "technical_unknowns": [], "diagnostic_calls": 5,
        "candidate_local_diagnostic_only": True, "original_ci_two_failures_unresolved": True}
    add("case_end", **final)
    return rows, final


def reindex(rows):
    for sequence, record in enumerate(rows):
        record["sequence"] = sequence


def integrity_oracle(rows, final):
    """A complete session is more than an arbitrary paired-call prefix."""
    if not rows or [row.get("sequence") for row in rows] != list(range(len(rows))):
        return False
    if rows[0].get("event") != "case_begin" or rows[-1].get("event") != "case_end":
        return False
    if sum(row.get("event") == "case_begin" for row in rows) != 1 or sum(row.get("event") == "case_end" for row in rows) != 1:
        return False
    before, after, controls = [], [], []
    for row in rows:
        if row["event"] == "diagnostic_before":
            before.append(row["call"])
        if row["event"] in {"diagnostic_after", "diagnostic_raised"}:
            after.append(row["call"])
        if row["event"] == "original_subtest":
            controls.append((row["expected"], row["missing"], row["passed"]))
    return (before == after == list(range(final["diagnostic_calls"]))
            and controls == [(expected, missing, True) for expected, missing in CONTROLS]
            and rows[-1]["diagnostic_calls"] == final["diagnostic_calls"])


def exported(rows, final):
    raw = b"".join((json.dumps(row, sort_keys=True) + "\n").encode() for row in rows)
    assert len(raw) < 65536
    files = {"/raw/native.jsonl": raw, "/raw/case-result.json": (json.dumps(final) + "\n").encode()}
    root = MemoryPath(files)
    writes = {}
    def write(path, value, *, cap):
        assert len(json.dumps(value).encode()) <= cap
        writes[path.path] = deepcopy(value)
    namespace = dict(export_namespace, write_new_json=write)
    # Rebind only the write dependency: the actual six exporter functions run.
    for function in export_nodes:
        exec(compile(ast.Module(body=[function], type_ignores=[]), "frozen-export#memory", "exec"), namespace)
    state = namespace["export_safe"](root)
    return state, writes["/safe/diagnostics.json"]


class NativePreparationBehaviorTests(unittest.TestCase):
    def assert_incomplete(self, rows, final):
        self.assertFalse(integrity_oracle(rows, final))
        state, _ = exported(rows, final)
        self.assertIs(state["journal_complete"], False)

    def test_complete_manual_session_is_eligible_without_promoting_owner_witness(self):
        rows, final = fixture()
        self.assertTrue(integrity_oracle(rows, final))
        state, safe = exported(rows, final)
        self.assertIs(state["journal_complete"], True)
        self.assertEqual(len(safe["diagnostics"]), 5)
        self.assertFalse(safe["diagnostics"][0]["report"]["financial_ready"])

    def test_deleted_whole_diagnostic_pair_cannot_be_complete_against_case_count(self):
        rows, final = fixture()
        rows = [row for row in rows if not (row["event"] in {"diagnostic_before", "diagnostic_after"} and row.get("call") == 2)]
        reindex(rows)
        self.assert_incomplete(rows, final)

    def test_paired_prefix_with_separate_pass_result_is_incomplete(self):
        rows, final = fixture()
        self.assert_incomplete(rows[:4], final)

    def test_duplicate_sequence_and_missing_sequence_are_incomplete(self):
        rows, final = fixture()
        rows[4]["sequence"] = rows[2]["sequence"]
        self.assert_incomplete(rows, final)

    def test_missing_case_end_is_not_complete(self):
        rows, final = fixture()
        self.assert_incomplete(rows[:-1], final)

    def test_missing_original_subtest_evidence_is_incomplete_even_if_case_passes(self):
        rows, final = fixture()
        removed = False
        retained = []
        for row in rows:
            if row["event"] == "original_subtest" and not removed:
                removed = True
            else:
                retained.append(row)
        reindex(retained)
        self.assert_incomplete(retained, final)

    def test_third_live_worker_must_be_denied_before_start_spy(self):
        starts = []
        class Bound:
            birth = {"pid": 9001}
            def terminal(self): return False
        class Process:
            pid, name = 9003, "uta-shard-0"
        def start(process, *args, **kwargs):
            starts.append(process)
            return "started"
        namespace = {"original_start": start, "BoundChild": lambda *args, **kwargs: Bound(),
            "os": SimpleNamespace(getsid=lambda _: 8000, getpid=lambda: 8000),
            "bindings": {}, "bound_archive": [Bound(), Bound()],
            "journal": SimpleNamespace(append=lambda *args, **kwargs: None),
            "technical_unknowns": [], "ScopeUnknown": ScopeUnknown}
        exec(compile(ast.Module(body=[start_node], type_ignores=[]), "frozen-process-start#spy", "exec"), namespace)
        with self.assertRaises(ScopeUnknown):
            namespace["process_start"](Process())
        self.assertEqual(starts, [], "third original start must never be invoked")

    def test_top_level_observation_error_is_safely_preserved(self):
        native = report("diagnostic_timeout")
        native["observation_error"] = {"type": "service_error", "sqlite_errorcode": 5,
            "message": "private-input-must-not-be-exported"}
        safe = export_namespace["safe_report"](native)
        self.assertEqual(safe.get("observation_error"), {"type": "service_error", "sqlite_errorcode": 5})
        self.assertNotIn("private-input-must-not-be-exported", json.dumps(safe))


def guard(event, args):
    if event in {"sqlite3.connect", "subprocess.Popen", "os.fork", "os.kill", "os.posix_spawn",
                 "socket.__new__", "socket.connect", "os.mkdir", "os.link", "os.remove", "os.rename"}:
        raise AssertionError("pure negative control attempted native effect")
    if event == "open":
        _, mode, flags = args
        if (mode and any(char in mode for char in "wax+")) or flags & (os.O_WRONLY | os.O_RDWR):
            raise AssertionError("pure negative control attempted file mutation")


if __name__ == "__main__":
    parsed = {}
    for filename, expected in PINS.items():
        raw = (PREFIX / filename).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == expected
        parsed[filename] = ast.parse(raw)
    export_names = {"code", "number", "sha", "timestamp", "safe_report", "export_safe"}
    export_nodes = [node for node in parsed["native_safe_export.py"].body if isinstance(node, ast.FunctionDef) and node.name in export_names]
    assert len(export_nodes) == 6
    start_node = next(node for node in ast.walk(parsed["native_case_once.py"]) if isinstance(node, ast.FunctionDef) and node.name == "process_start")
    export_namespace = {"datetime": datetime, "json": json, "SAFE_EXPORT_CAP": 524288, "write_new_json": None}
    sys.dont_write_bytecode = True
    sys.addaudithook(guard)
    for function in export_nodes:
        exec(compile(ast.Module(body=[function], type_ignores=[]), "frozen-export#memory", "exec"), export_namespace)
    unittest.main()
