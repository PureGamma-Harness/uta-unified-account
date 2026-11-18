"""One isolated, source-pinned reference batch; no native UTA execution."""
import os
import sys
from time import monotonic

_started = monotonic()
_deadline = _started + 10


def _budget_guard(frame, event, arg):
    if monotonic() >= _deadline:
        print('{"event":"pure_budget_exhausted","wall_limit_seconds":10}', flush=True)
        os._exit(124)  # Exit this interpreter; never signal another process.
    return _budget_guard


sys.settrace(_budget_guard)
import hashlib
import json
from pathlib import Path
import unittest


class _NoRuntimeImports:
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split(".", 1)[0] in {"uta", "sqlite3", "_sqlite3"}:
            raise ImportError("native UTA/SQLite is outside this pure batch")
        return None


def _emit(event, **values):
    print(json.dumps({"event": event, **values}, sort_keys=True), flush=True)


def main():
    if len(sys.argv) != 2 or len(sys.argv[1]) != 40 or any(c not in "0123456789abcdef" for c in sys.argv[1]):
        raise ValueError("supply the frozen source commit")
    root = Path(__file__).resolve().parents[3]
    manifest_path = root / "evidence/reviews/process-readiness-engineering/source-plan-v2.json"
    manifest = json.loads(manifest_path.read_text())
    affinity = os.sched_getaffinity(0)
    os.sched_setaffinity(0, {min(affinity)})
    _emit("BEGIN", source_commit=sys.argv[1], runtime=sys.version,
          cpu_affinity=sorted(os.sched_getaffinity(0)), wall_limit_seconds=10,
          selector="test_readiness_before_quote_reference.BeforeQuoteReferenceTests",
          manifest_sha256=hashlib.sha256(manifest_path.read_bytes()).hexdigest())
    observed = {}
    for relative, expected in {**manifest["candidate_files_sha256"],
                               **manifest["unchanged_runtime_sha256"]}.items():
        observed[relative] = hashlib.sha256((root / relative).read_bytes()).hexdigest()
        if observed[relative] != expected:
            _emit("SOURCE_MISMATCH", path=relative, expected=expected, actual=observed[relative])
            return 2
    _emit("SOURCE_PINS", sha256=observed)
    sys.meta_path.insert(0, _NoRuntimeImports())
    sys.path.insert(0, str(root / "tests"))
    suite = unittest.defaultTestLoader.loadTestsFromName(
        "test_readiness_before_quote_reference.BeforeQuoteReferenceTests")
    if suite.countTestCases() != 7:
        _emit("SELECTOR_MISMATCH", expected_methods=7, selected_methods=suite.countTestCases())
        return 2
    result = unittest.TextTestRunner(stream=sys.stdout, verbosity=2).run(suite)
    forbidden = sorted(name for name in sys.modules
                       if name.split(".", 1)[0] in {"uta", "sqlite3", "_sqlite3"})
    status = 0 if result.wasSuccessful() and not forbidden else 1
    _emit("END", tests_run=result.testsRun, failures=len(result.failures),
          errors=len(result.errors), skipped=len(result.skipped),
          forbidden_runtime_imports=forbidden, elapsed_seconds=monotonic() - _started,
          exit_status=status)
    return status


try:
    _status = main()
finally:
    sys.settrace(None)
raise SystemExit(_status)
