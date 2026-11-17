"""Checks of the design model, never of the current UTA runtime."""
import ast
import hashlib
import importlib.util
import json
from pathlib import Path
import unittest


SOURCE = Path(__file__).resolve().parents[1] / "formal" / "explore_market_epochs.py"
SPEC = importlib.util.spec_from_file_location("market_epoch_spec", SOURCE)
MODEL = importlib.util.module_from_spec(SPEC)
# dataclasses resolves the defining module through sys.modules.
import sys
sys.modules[SPEC.name] = MODEL
SPEC.loader.exec_module(MODEL)


class MarketEpochModelTests(unittest.TestCase):
    def test_complete_graphs_and_nonempty_coverage(self):
        result = MODEL.run()
        self.assertTrue(result["passed"])
        for graph in result["models"].values():
            self.assertTrue(graph["complete"])
            self.assertEqual(graph["violations"], [])
        coverage = result["models"]["delivery"]["coverage"]
        for name in ("divergent_shards", "committed_ack_unknown", "recovered_with_durable_history"):
            self.assertGreater(coverage[name], 0, name)
        self.assertGreater(result["models"]["checkpoint"]["coverage"]["accepted_old_local_quote"], 0)
        self.assertGreater(result["models"]["hard_barrier"]["coverage"]["current_parent_child_authorized"], 0)
        self.assertFalse(result["physical_commit_age_proven"])
        self.assertFalse(result["runtime_refinement_proven"])
        self.assertFalse(result["production_approved"])

    def test_every_mutation_has_replayable_specific_counterexample(self):
        result = MODEL.run()
        self.assertEqual(len(result["negative_controls"]), 9)
        for name, (factory, edges, invariants, mutations) in MODEL.MODELS.items():
            for mutation, target in mutations.items():
                broken = result["negative_controls"][mutation]
                self.assertIn(target, broken["violations"])
                broken = json.loads(json.dumps(broken))
                self.assertTrue(MODEL.replay(factory(), edges, invariants, mutation,
                                             broken["counterexample"]), (name, mutation))
                self.assertFalse(broken["complete"])
                state, differs = factory(), False
                for item in broken["counterexample"][1:]:
                    differs |= not any(action == item["action"] and MODEL.plain(successor) == item["state"]
                                       for action, successor in edges(state))
                    state = next(successor for action, successor in edges(state, mutation)
                                 if action == item["action"] and MODEL.plain(successor) == item["state"])
                self.assertTrue(differs, mutation)

    def test_unknown_ack_recovery_and_delayed_old_tick(self):
        state = MODEL.Delivery()
        actions = ["authorize_child_1", "install_1_on_0_ack_unknown", "worker_0_dies",
                   "worker_0_recovers_with_new_generation", "observe_success_1_on_0",
                   "authorize_child_2", "install_2_on_0_ack_unknown", "replay_1_on_0"]
        for desired in actions:
            choices = [s for a, s in MODEL.delivery_edges(state) if a == desired]
            self.assertEqual(len(choices), 1, desired)
            state = choices[0]
            self.assertEqual(MODEL.delivery_invariants(state), ())
        self.assertEqual(state.replicas[0].pointer, 2)
        self.assertEqual(state.replicas[0].archive, 7)
        self.assertEqual(state.replicas[0].receipts, 7)

    def test_old_local_quote_is_an_intentional_changed_policy(self):
        # Global child 1 is authorized; shard 0 may still decide at local 0.
        state = MODEL.Checkpoint()
        state = next(s for a, s in MODEL.checkpoint_edges(state)
                     if a == "authorize_child_1_without_freeze")
        state = next(s for a, s in MODEL.checkpoint_edges(state)
                     if a == "begin_decision_pin_local_snapshot_and_shared_gate")
        state = next(s for a, s in MODEL.checkpoint_edges(state)
                     if a == "final_checkpoint_and_abstract_commit")
        self.assertEqual(state.accepted, (0, 0, 0, True, 1))
        self.assertEqual(MODEL.checkpoint_invariants(state), ())

    def test_incomplete_exploration_cannot_pass(self):
        with self.assertRaisesRegex(RuntimeError, "incomplete exploration"):
            MODEL.explore(MODEL.Delivery(), MODEL.delivery_edges,
                          MODEL.delivery_invariants, limit=1)
        with self.assertRaisesRegex(ValueError, "unknown model or mutation"):
            MODEL.explore(MODEL.Delivery(), MODEL.delivery_edges,
                          MODEL.delivery_invariants, mutation="typo")

    def test_imports_are_independent_standard_library_only(self):
        modules = []
        for node in ast.walk(ast.parse(SOURCE.read_text())):
            if isinstance(node, ast.Import):
                modules.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                modules.append(node.module)
        self.assertEqual(set(modules), {"collections", "dataclasses", "json"})

    def test_physical_pause_limitation_is_explicit(self):
        broken = MODEL.explore(MODEL.PhysicalGap(), MODEL.physical_gap_edges,
                               MODEL.physical_gap_invariants)
        self.assertIn("physical_commit_age_unbounded", broken["violations"])
        self.assertTrue(MODEL.replay(MODEL.PhysicalGap(), MODEL.physical_gap_edges,
                                    MODEL.physical_gap_invariants, "", broken["counterexample"]))

    def test_retained_artifact_matches_source_and_has_full_graph_counts(self):
        result = json.loads((SOURCE.parent / "results" / "market-epochs-design-20261117.json").read_text())
        self.assertEqual(result["source_sha256"], hashlib.sha256(SOURCE.read_bytes()).hexdigest())
        fresh = MODEL.run()
        self.assertEqual(result["models"], fresh["models"])
        self.assertEqual(result["negative_controls"], fresh["negative_controls"])


if __name__ == "__main__":
    unittest.main()
