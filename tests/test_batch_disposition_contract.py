"""Pure contract checks of the production disposition method, without DB imports.

Only the selected method/canonical JSON helper/terminal literal are evaluated.
This is not an integration test of SQLite, writer fencing, imports or recovery.
"""
import ast
from itertools import permutations
import json
from pathlib import Path
import unittest


def _load_production_disposition():
    root = Path(__file__).resolve().parents[1]
    batch = ast.parse((root / "uta/durable_batches.py").read_text())
    command = ast.parse((root / "uta/durable_commands.py").read_text())
    service = ast.parse((root / "uta/service.py").read_text())
    store = next(node for node in batch.body if isinstance(node, ast.ClassDef) and node.name == "BatchStore")
    verify = next(node for node in store.body if isinstance(node, ast.FunctionDef) and node.name == "_verify_outcome")
    canonical = next(node for node in service.body if isinstance(node, ast.FunctionDef) and node.name == "_json")
    terminal = next(node for node in command.body if isinstance(node, ast.Assign)
                    and any(isinstance(target, ast.Name) and target.id == "_TERMINAL" for target in node.targets))
    class RecoveryUnknown(Exception):
        pass
    namespace = {"json": json, "BatchRecoveryUnknown": RecoveryUnknown}
    selected_store = ast.ClassDef(name="BatchStore", bases=[], keywords=[], body=[verify], decorator_list=[])
    module = ast.fix_missing_locations(ast.Module(body=[canonical, terminal, selected_store], type_ignores=[]))
    exec(compile(module, "<production-disposition-contract>", "exec"), namespace)
    return namespace["BatchStore"](), RecoveryUnknown


class BatchDispositionContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.store, cls.unknown = _load_production_disposition()

    def verify(self, executed, recorded, actual=None, disposition="COMMITTED"):
        ids = ["cmd:A", "cmd:B", "cmd:C"]
        value = {"executed": executed, "commands": [
            {"command_id": cid, "state": state} for cid, state in zip(ids, recorded)]}
        row = {"disposition": disposition, "content": json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)}
        content = {"members": [{"command_id": cid} for cid in ids]}
        current = [{"command_id": cid, "state": state} for cid, state in zip(ids, actual or recorded)]
        return self.store._verify_outcome(row, content, current)

    def test_execution_is_a_subsequence_with_skips_not_a_required_prefix(self):
        # Explicit hand-derived language for visiting A, then B, then C once.
        allowed = {(), ("cmd:A",), ("cmd:B",), ("cmd:C",),
                   ("cmd:A", "cmd:B"), ("cmd:A", "cmd:C"), ("cmd:B", "cmd:C"),
                   ("cmd:A", "cmd:B", "cmd:C")}
        ids = ("cmd:A", "cmd:B", "cmd:C")
        for length in range(4):
            for sequence in permutations(ids, length):
                with self.subTest(executed=sequence):
                    if sequence in allowed:
                        self.assertEqual(self.verify(list(sequence), ["SUCCEEDED"] * 3)["executed"], list(sequence))
                    else:
                        with self.assertRaises(self.unknown):
                            self.verify(list(sequence), ["SUCCEEDED"] * 3)

    def test_quarantine_may_preexist_but_is_never_newly_executed(self):
        ids = ["cmd:A", "cmd:B", "cmd:C"]
        for index, cid in enumerate(ids):
            states = ["SUCCEEDED", "REJECTED", "SUCCEEDED"]
            states[index] = "QUARANTINED"
            with self.subTest(quarantined=cid, claimed=True), self.assertRaises(self.unknown):
                self.verify([cid], states)
            with self.subTest(quarantined=cid, claimed=False):
                executed = [other for other in ids if other != cid]
                self.assertEqual(self.verify(executed, states)["executed"], executed)

    def test_recovered_pending_snapshot_can_later_become_terminal(self):
        value = self.verify([], ["PENDING"] * 3,
                            ["SUCCEEDED", "QUARANTINED", "REJECTED"], "RECOVERED")
        self.assertEqual(value["executed"], [])
        self.assertEqual([row["state"] for row in value["commands"]], ["PENDING"] * 3)

    def test_recovery_disposition_never_claims_execution(self):
        with self.assertRaises(self.unknown):
            self.verify(["cmd:A"], ["SUCCEEDED"] * 3, disposition="RECOVERED")

    def test_duplicate_or_neighbor_CID_never_belongs_to_execution(self):
        for executed in (["cmd:A", "cmd:A"], ["cmd:neighbor"]):
            with self.subTest(executed=executed), self.assertRaises(self.unknown):
                self.verify(executed, ["SUCCEEDED"] * 3)


if __name__ == "__main__":
    unittest.main()
