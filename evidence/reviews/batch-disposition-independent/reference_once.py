"""Independent bounded history oracle; selected target AST only, no UTA import.

The oracle describes visit events and hand-enumerates their observable execution
language. It does not reuse the production outcome validator or its algorithm.
The actual method AST is evaluated solely as the differential-test target.
"""
import ast
from hashlib import sha256
from itertools import permutations, product
import json
from pathlib import Path
import sys
import unittest


IDS = ("member:alpha", "member:bravo", "member:charlie", "member:delta")
STATES = ("PENDING", "SUCCEEDED", "REJECTED", "QUARANTINED")
TERMINAL = ("SUCCEEDED", "REJECTED", "QUARANTINED")
# Independently hand-listed language for visiting alpha, bravo, charlie, delta.
LEGAL_WORDS = {
    (), (IDS[0],), (IDS[1],), (IDS[2],), (IDS[3],),
    (IDS[0], IDS[1]), (IDS[0], IDS[2]), (IDS[0], IDS[3]),
    (IDS[1], IDS[2]), (IDS[1], IDS[3]), (IDS[2], IDS[3]),
    (IDS[0], IDS[1], IDS[2]), (IDS[0], IDS[1], IDS[3]),
    (IDS[0], IDS[2], IDS[3]), (IDS[1], IDS[2], IDS[3]), IDS,
}
CHECKS = 0


def canonical(value):
    # Independent wire-format implementation, not the production helper AST.
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


class TargetUnknown(Exception):
    pass


def target():
    root = Path(__file__).resolve().parents[3]
    path = root / "uta/durable_batches.py"
    raw = path.read_bytes()
    module = ast.parse(raw)
    store = next(node for node in module.body
                 if isinstance(node, ast.ClassDef) and node.name == "BatchStore")
    method = next(node for node in store.body
                  if isinstance(node, ast.FunctionDef) and node.name == "_verify_outcome")
    namespace = {"json": json, "_json": canonical, "_TERMINAL": TERMINAL,
                 "BatchRecoveryUnknown": TargetUnknown}
    code = ast.fix_missing_locations(ast.Module(body=[method], type_ignores=[]))
    exec(compile(code, "<independent-selected-target-only>", "exec"), namespace)
    return namespace["_verify_outcome"], sha256(raw).hexdigest()


def visit_history(choices):
    """Four append-only visit events, specified independently of validation.

    Codes 0..3 observe existing P/S/R/Q without running an action. Codes 4/5
    complete one new business action successfully/rejected. A history cannot
    append an execution for a technical-quarantine observation.
    """
    events = [(IDS[index], choice) for index, choice in enumerate(choices)]
    transcript, final_states = [], []
    for identity, event in events:
        if event < 4:
            final_states.append(STATES[event])
        else:
            transcript.append(identity)
            final_states.append("SUCCEEDED" if event == 4 else "REJECTED")
    return transcript, final_states


class IndependentDispositionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        method, digest = target()
        cls.method = staticmethod(method)
        cls.target_sha256 = digest

    def check(self, executed, recorded, expected, *, actual=None,
              disposition="COMMITTED", mutate=None, noncanonical=False):
        global CHECKS
        CHECKS += 1
        value = {"executed": executed, "commands": [
            {"command_id": identity, "state": state}
            for identity, state in zip(IDS, recorded)]}
        if mutate is not None:
            mutate(value)
        content = canonical(value)
        if noncanonical:
            content += "\n"
        row = {"disposition": disposition, "content": content}
        membership = {"members": [{"command_id": identity} for identity in IDS]}
        current = [{"command_id": identity, "state": state}
                   for identity, state in zip(IDS, recorded if actual is None else actual)]
        try:
            observed = self.method(None, row, membership, current)
        except TargetUnknown:
            accepted = False
        else:
            accepted = True
            self.assertEqual(canonical(observed), canonical(value))
        self.assertIs(accepted, expected, (executed, recorded, actual, disposition))

    def test_bounded_four_visit_business_histories(self):
        for choices in product(range(6), repeat=4):
            executed, recorded = visit_history(choices)
            with self.subTest(history=choices):
                self.check(executed, recorded, True)

    def test_all_four_member_permutations_against_handwritten_language(self):
        self.assertEqual(len(LEGAL_WORDS), 16)
        for length in range(5):
            for word in permutations(IDS, length):
                with self.subTest(word=word):
                    self.check(list(word), ["SUCCEEDED"] * 4, word in LEGAL_WORDS)

    def test_preexisting_quarantine_is_skipped_and_never_newly_executed(self):
        for index, identity in enumerate(IDS):
            recorded = ["SUCCEEDED"] * 4
            recorded[index] = "QUARANTINED"
            self.check([item for item in IDS if item != identity], recorded, True)
            self.check([identity], recorded, False)

    def test_new_execution_only_has_business_terminals(self):
        for index, identity in enumerate(IDS):
            for state in STATES:
                recorded = ["PENDING"] * 4
                recorded[index] = state
                self.check([identity], recorded, state in ("SUCCEEDED", "REJECTED"))

    def test_recovered_pending_snapshot_all_later_states_and_no_execution(self):
        for actual in product(STATES, repeat=4):
            self.check([], ["PENDING"] * 4, True, actual=actual,
                       disposition="RECOVERED")
        for identity in IDS:
            self.check([identity], ["SUCCEEDED"] * 4, False,
                       disposition="RECOVERED")

    def test_recorded_terminal_cannot_change_after_disposition(self):
        for index in range(4):
            for recorded_terminal in TERMINAL:
                for later in STATES:
                    if later == recorded_terminal:
                        continue
                    recorded = ["PENDING"] * 4
                    actual = list(recorded)
                    recorded[index] = recorded_terminal
                    actual[index] = later
                    self.check([], recorded, False, actual=actual)

    def test_existing_duplicate_membership_and_wire_rejections_remain(self):
        complete = ["SUCCEEDED"] * 4
        self.check([IDS[0], IDS[0]], complete, False)
        self.check(["neighbor:foreign"], complete, False)
        self.check(True, complete, False)
        self.check([IDS[0], 1], complete, False)
        self.check([], complete, False, disposition="FAILED")
        self.check([], complete, False, mutate=lambda value: value.update(extra=True))
        self.check([], complete, False, mutate=lambda value: value["commands"][0].update(extra=True))
        self.check([], ["INVALID"] * 4, False)
        self.check([], complete, False, noncanonical=True)

    def test_manual_nonprefix_and_original_counterexample_controls(self):
        self.check([IDS[1], IDS[3]], ["QUARANTINED", "REJECTED", "PENDING", "SUCCEEDED"], True)
        self.check([IDS[3], IDS[1]], ["QUARANTINED", "REJECTED", "PENDING", "SUCCEEDED"], False)
        self.check([], ["PENDING"] * 4, True)
        self.check([IDS[0]], ["QUARANTINED", "PENDING", "PENDING", "PENDING"], False)


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(IndependentDispositionTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    print(canonical({"scope": "INDEPENDENT_FOUR_MEMBER_PURE_HISTORY_MODEL",
                     "target_sha256": IndependentDispositionTests.target_sha256,
                     "test_methods": result.testsRun, "checks": CHECKS,
                     "failures": len(result.failures), "errors": len(result.errors),
                     "passed": result.wasSuccessful(), "full_module_imports": 0,
                     "actual_SQL_or_worker_or_network": False,
                     "production_approved": False}))
    sys.exit(0 if result.wasSuccessful() else 1)
