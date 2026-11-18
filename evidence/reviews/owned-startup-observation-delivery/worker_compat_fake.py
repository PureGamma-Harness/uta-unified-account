"""Six methods /32 bounded cases of the actual qualification QA prefix only.

No UTA/tools import, filesystem proof read, SQLite, native worker, thread,
process, signal, network or sleep. Proofs, paths, logs and CI records are memory
fakes. The package/installed/omission half of qualification is NOT executed.
Expected decisions/messages are independently hand-recorded policy examples.
"""
import ast
from copy import deepcopy
from hashlib import sha256
import json
import re
from types import MappingProxyType
import unittest


CASES = 0
CONSUMER = "tools/run_managed_variants.py"
REFERENCE = "evidence/reviews/owned-startup-observation-delivery/worker-compat-reference.json"
COMMIT = "c" * 40


def frozen(name):
    values = globals().get("_FROZEN_INPUT_BYTES")
    if type(values) is not MappingProxyType or type(values.get(name)) is not bytes:
        raise RuntimeError("reviewed materialized bytes required")
    return values[name]


class ListAlias(list):
    pass


class MemoryQA:
    def __init__(self, variant):
        self.values, self.logs, self.references, self.records = {}, {}, [], []
        self.source_hashes = {"uta/__init__.py": "a" * 64,
                              "tools/run_validation.py": "b" * 64,
                              "docs/ignored.md": "d" * 64}
        # Independent literal expected manifest; no target helper computes it.
        self.expected_hashes = {"uta/__init__.py": "a" * 64,
                                "tools/run_validation.py": "b" * 64}
        self.registration = {"source_commit": COMMIT,
            "qualification": {"expected_tests": 2, "local": [], "ci": [], "package": {}}}
        for version in ("3.10", "3.12", "3.13"):
            self.add_record("local", version, None, variant)
        for event in ("push", "pull_request"):
            for version in ("3.10", "3.11", "3.12", "3.13"):
                self.add_record("ci", version, event, variant)

    def reference(self, path, value):
        self.values[path] = value
        result = {"path": path, "sha256": "pending-memory-seal"}
        self.references.append(result)
        return result

    def add_record(self, kind, version, event, variant):
        label = (event or kind) + "-" + version
        prefix = "/synthetic/qa/" + label
        extension = variant == "new" or variant == "new_local" and kind == "local" or variant == "new_ci" and kind == "ci"
        worker = {"tests_run": 2, "failures": 0, "errors": 0, "skipped": 0,
                  "expected_failures": 0, "unexpected_successes": 0, "unittest_passed": True}
        if extension:
            worker.update(lease_observations=[], lease_observations_truncated=False)
        summary = {"tests_run": 2, "failures": 0, "errors": 0, "skipped": 0,
            "expected_failures": 0, "unexpected_successes": 0, "unittest_passed": True,
            "code_commit": COMMIT, "worker_exit_code": 0, "passed": True,
            "source_unchanged": True, "tracked_source_clean_before": True,
            "tracked_source_clean_after": True, "source_sha256": dict(self.expected_hashes),
            "source_sha256_after": dict(self.expected_hashes), "python": version + ".1",
            "command_argv": ["/synthetic/python", "/synthetic/tools/run_validation.py", "--output", "/synthetic/results"]}
        if extension:
            summary.update(lease_observations=[], lease_observations_truncated=False)
        logpath = prefix + ".txt"
        self.logs[logpath] = "Ran 2 tests in 0.1s\n\nOK\n"
        record = {"python": version, "summary": self.reference(prefix + ".summary.json", summary),
                  "worker": self.reference(prefix + ".worker.json", worker),
                  "log": {"path": logpath, "sha256": "pending-log-seal"}}
        if event:
            identity = 100 + len(self.records)
            record["run"] = self.reference(prefix + ".run.json", {"event": event,
                "head_sha": COMMIT, "id": identity, "status": "completed", "conclusion": "success",
                "html_url": "https://github.com/PureGamma-Harness/uta-unified-account/actions/runs/" + str(identity)})
            record["job"] = self.reference(prefix + ".job.json", {"run_id": identity,
                "status": "completed", "conclusion": "success", "name": "Validate (" + version + ")"})
        self.registration["qualification"][kind].append(record)
        self.records.append(record)

    def summary(self, record=None):
        return self.values[(record or self.records[0])["summary"]["path"]]

    def worker(self, record=None):
        return self.values[(record or self.records[0])["worker"]["path"]]

    def seal(self):
        for record in self.records:
            log_hash = sha256(self.logs[record["log"]["path"]].encode()).hexdigest()
            record["log"]["sha256"] = log_hash
            self.summary(record)["test_log_sha256"] = log_hash
        for reference in self.references:
            reference["sha256"] = sha256(json.dumps(self.values[reference["path"]], sort_keys=True).encode()).hexdigest()

    def proof(self, reference):
        # JSON/native-file parsing is explicitly a fake boundary. Returning
        # objects also permits adversarial native type-alias injections.
        return self.values[reference["path"]]

    def digest(self, path):
        return sha256(self.logs[str(path)].encode()).hexdigest()

    def path(self, value):
        owner = self
        class MemoryPath:
            def read_text(self):
                return owner.logs[value]
            def __str__(self):
                return value
        return MemoryPath()


class ActualQAPrefix:
    def __init__(self):
        source = ast.parse(frozen(CONSUMER))
        target = deepcopy(next(node for node in source.body
                               if isinstance(node, ast.FunctionDef) and node.name == "qualification"))
        boundary = next(index for index, node in enumerate(target.body)
                        if isinstance(node, ast.Assign) and any(isinstance(name, ast.Name)
                        and name.id == "package" for name in node.targets))
        # This exact original prefix includes all eleven local/CI QA records.
        # The package gate and every later process/resource path are absent.
        target.body = target.body[:boundary]
        selected = [node for node in source.body
                    if isinstance(node, ast.ClassDef) and node.name == "GateError"
                    or isinstance(node, ast.FunctionDef) and node.name == "require"]
        selected.append(target)
        self.code = compile(ast.fix_missing_locations(ast.Module(body=selected, type_ignores=[])),
                            "<actual-qualification-QA-prefix>", "exec")

    def run(self, memory):
        namespace = {"re": re, "proof": memory.proof, "digest": memory.digest, "Path": memory.path}
        exec(self.code, namespace)
        try:
            namespace["qualification"](memory.source_hashes, memory.registration)
        except namespace["GateError"] as error:
            return False, str(error)
        return True, None


def apply_case(memory, label):
    worker, summary = memory.worker(), memory.summary()
    if label == "legacy_unknown_key":
        worker["unknown"] = 0
    elif label == "new_unknown_key":
        worker["unknown"] = 0
    elif label == "half_list":
        del worker["lease_observations_truncated"]
    elif label == "half_flag":
        del worker["lease_observations"]
    elif label == "tuple_list":
        worker["lease_observations"] = ()
    elif label == "summary_missing_diagnostic":
        del summary["lease_observations_truncated"]
    elif label == "nonempty_list":
        worker["lease_observations"] = [{"test": "synthetic.Case.test_probe", "lease": {"version": 1}}]
    elif label == "truncated_true":
        worker["lease_observations_truncated"] = True
    elif label == "list_alias":
        worker["lease_observations"] = ListAlias()
    elif label == "false_zero":
        worker["lease_observations_truncated"] = 0
    elif label == "false_none":
        worker["lease_observations_truncated"] = None
    elif label == "count_bool_alias":
        summary["errors"] = worker["errors"] = False
    elif label.startswith("count_"):
        field = label[len("count_"):]
        summary[field] = worker[field] = 1
    elif label == "summary_failed":
        summary["passed"] = False
    elif label == "worker_count_mismatch":
        worker["tests_run"] = 3
    elif label == "source_hash_mismatch":
        summary["source_sha256_after"]["uta/__init__.py"] = "e" * 64
    elif label == "runtime_mismatch":
        summary["python"] = "3.11.1"
    elif label == "old_local_source":
        summary["code_commit"] = "f" * 40
    elif label in ("ci_pending", "old_ci_head", "old_ci_summary"):
        record = memory.registration["qualification"]["ci"][0]
        run = memory.values[record["run"]["path"]]
        if label == "ci_pending":
            run["status"] = "in_progress"
        elif label == "old_ci_head":
            run["head_sha"] = "f" * 40
        else:
            memory.summary(record)["code_commit"] = "f" * 40
    elif label == "raw_warning":
        memory.logs[memory.records[0]["log"]["path"]] += "ResourceWarning: synthetic\n"
    elif label == "raw_not_OK":
        memory.logs[memory.records[0]["log"]["path"]] = "Ran 2 tests in 0.1s\n\nFAILED\n"
    elif label not in ("legacy_all", "new_all", "mixed_local7_ci9", "mixed_local9_ci7"):
        raise ValueError("unregistered synthetic case")


class WorkerCompatibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.path = ActualQAPrefix()
        cls.reference = json.loads(frozen(REFERENCE))

    def examples(self, labels):
        global CASES
        for label in labels:
            with self.subTest(case=label):
                CASES += 1
                expected = self.reference["cases"][label]
                memory = MemoryQA(expected["variant"])
                apply_case(memory, label)
                memory.seal()
                original_records = deepcopy((memory.values, memory.registration, memory.logs))
                actual = self.path.run(memory)
                self.assertEqual(actual, (expected["accept_QA_prefix"], expected["error_message"]))
                self.assertEqual((memory.values, memory.registration, memory.logs), original_records)

    def test_01_exact_legacy_new_and_mixed_positive_records(self):
        self.examples(("legacy_all", "new_all", "mixed_local7_ci9", "mixed_local9_ci7"))

    def test_02_unknown_half_fields_and_wrong_collection_rejected(self):
        self.examples(("legacy_unknown_key", "new_unknown_key", "half_list", "half_flag", "tuple_list", "summary_missing_diagnostic"))

    def test_03_nonempty_truncated_and_type_aliases_rejected(self):
        self.examples(("nonempty_list", "truncated_true", "list_alias", "false_zero", "false_none"))

    def test_04_original_nonzero_counts_and_boolean_alias_rejected(self):
        self.examples(("count_failures", "count_errors", "count_skipped", "count_expected_failures",
                       "count_unexpected_successes", "count_worker_exit_code", "count_bool_alias"))

    def test_05_original_summary_source_and_runtime_binding_rejected(self):
        self.examples(("summary_failed", "worker_count_mismatch", "source_hash_mismatch", "runtime_mismatch", "old_local_source"))

    def test_06_original_CI_source_and_raw_log_gates_rejected(self):
        self.examples(("ci_pending", "old_ci_head", "old_ci_summary", "raw_warning", "raw_not_OK"))


if __name__ == "__main__":
    result = unittest.TextTestRunner(verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(WorkerCompatibilityTests))
    complete = result.testsRun == 6 and CASES == 32
    passed = result.wasSuccessful() and complete
    print(json.dumps({"scope": "ACTUAL_QUALIFICATION_QA_PREFIX_WITH_MEMORY_PROOFS_ONLY",
        "methods": result.testsRun, "bounded_cases": CASES, "failures": len(result.failures),
        "errors": len(result.errors), "passed": passed, "expected_counts_complete": complete,
        "full_package_qualification_executed": False, "SQL_or_UTA_or_tool_module_import": False,
        "native_thread_process_signal_network_or_real_sleep": False,
        "phase2_authorized": False, "native_financial_CI_performance_production_approved": False}, sort_keys=True))
    raise SystemExit(0 if passed else 1)
