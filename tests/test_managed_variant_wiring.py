"""Tiny real wiring checks and side-effect-free invalid configurations.

At most eight synthetic arrivals per real case; not performance evidence.
"""
from dataclasses import replace
import io
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from benchmarks.run_managed_benchmark import Configuration, main, run


class ManagedVariantWiringTests(unittest.TestCase):
    def test_defaults_preserve_uncapped_single_dispatch(self):
        configuration = Configuration()
        self.assertEqual((configuration.normal_cache_size, configuration.financial_batch_size,
                          configuration.durable_batches), (0, 0, False))
        configuration.validate()
        replace(configuration, durable_batches=True).validate()

    def test_preregistered_comparisons_keep_capability_and_single_factor_fixed(self):
        path = Path(__file__).resolve().parents[1] / "benchmarks/plans/20261117-managed-variants.json"
        plan = json.loads(path.read_text())
        self.assertEqual(plan["status"], "PLANNED_NOT_RUN")
        self.assertFalse(plan["execution_authorized"])
        self.assertIsNone(plan["frozen_commit"])
        baseline = plan["baseline"]
        self.assertEqual((baseline["durable_batches"], baseline["financial_batch_size"],
                          baseline["normal_cache_size"]), (True, 0, 0))
        for variant in plan["variants"]:
            self.assertIs(variant["durable_batches"], True)
            replace(Configuration(), **{name: variant[name] for name in
                ("durable_batches", "financial_batch_size", "normal_cache_size")}).validate()
            self.assertEqual(sum(variant[name] != baseline[name] for name in
                ("financial_batch_size", "normal_cache_size")), 1)
            self.assertIn("--durable-batches", variant["command_template"])
        self.assertEqual(plan["soft_budget"]["default_seconds"], .005)
        self.assertFalse(plan["soft_budget"]["hard_transaction_or_commit_deadline"])

    def test_invalid_or_incompatible_api_options_have_no_directory_database_or_worker_side_effect(self):
        invalid = [{"normal_cache_size": value} for value in (-1, True, 1.0, 65537)]
        invalid += [{"financial_batch_size": value, "durable_batches": True} for value in (-1, True, 1, 2, 9, 3.0)]
        invalid += [{"durable_batches": value} for value in (0, 1, "true")]
        invalid += [{"financial_batch_size": 3}, {"financial_batch_size": 8, "durable_batches": False}]
        with TemporaryDirectory() as temporary:
            for index, values in enumerate(invalid):
                with self.subTest(values=values):
                    directory = Path(temporary) / ("must-not-exist-" + str(index))
                    with patch("benchmarks.run_managed_benchmark._environment") as environment, \
                            patch("benchmarks.run_managed_benchmark.DurableProcessRouter.initialize") as initialize, \
                            patch("benchmarks.run_managed_benchmark.process_module._run_worker") as worker:
                        with self.assertRaises(ValueError):
                            run(replace(Configuration(), **values), directory)
                        environment.assert_not_called()
                        initialize.assert_not_called()
                        worker.assert_not_called()
                    self.assertFalse(directory.exists())

    def test_invalid_cli_options_reject_before_affinity_or_run(self):
        for arguments in (("--financial-batch-size", "3"), ("--normal-cache-size", "65537"),
                          ("--durable-batches", "--financial-batch-size", "2"), ("--cpu-limit", "0")):
            with self.subTest(arguments=arguments), \
                    patch("benchmarks.run_managed_benchmark.os.sched_setaffinity") as affinity, \
                    patch("benchmarks.run_managed_benchmark.run") as execute, \
                    patch("sys.stderr", new_callable=io.StringIO):
                with self.assertRaises(SystemExit) as caught:
                    main(["--output", "/must-not-be-created", *arguments])
                self.assertEqual(caught.exception.code, 2)
                affinity.assert_not_called()
                execute.assert_not_called()

    def test_valid_cli_explicitly_passes_each_runtime_option(self):
        with patch("benchmarks.run_managed_benchmark.os.sched_setaffinity"), \
                patch("benchmarks.run_managed_benchmark.run", return_value={"probe_qualification": {"passed": True}}) as execute, \
                patch("sys.stdout", new_callable=io.StringIO):
            self.assertEqual(main(["--output", "/unused-test-output", "--normal-cache-size", "100",
                "--financial-batch-size", "8", "--durable-batches", "--cpu-limit", "1"]), 0)
        configuration = execute.call_args.args[0]
        self.assertEqual((configuration.normal_cache_size, configuration.financial_batch_size,
                          configuration.durable_batches), (100, 8, True))

    def test_tiny_real_variants_reach_spawned_workers_and_reopen_correct_capability(self):
        variants = (("default", False, 0, 0), ("samecap-baseline", True, 0, 0),
                    ("batch3-cache8", True, 3, 8), ("batch8-cache100", True, 8, 100))
        with TemporaryDirectory() as temporary:
            output = Path(os.environ.get("UTA_MANAGED_VARIANT_EVIDENCE", temporary))
            output.mkdir(parents=True, exist_ok=True)
            for label, capability, batch, cache in variants:
                with self.subTest(label=label):
                    directory = output / label
                    configuration = Configuration(duration=.05, rate=160, accounts=3, shards=1,
                        outstanding=16, inbox_capacity=16, reject_every=0, drain_seconds=5,
                        durable_batches=capability, financial_batch_size=batch, normal_cache_size=cache)
                    # A stale inherited profiling directory must not enable a profiler.
                    with patch.dict(os.environ, {"UTA_MANAGED_PROFILE_DIRECTORY": "/not-a-requested-profile"}):
                        summary = run(configuration, directory)
                    self.assertEqual(summary["offered"], 8)
                    self.assertIn("not performance evidence", summary["evidence_kind"])
                    self.assertEqual(summary["counts"]["financial_succeeded"], 8)
                    self.assertTrue(summary["probe_qualification"]["passed"])
                    actual = summary["actual_runtime"]
                    self.assertEqual((actual["router_settings"]["financial_batch_size"],
                        actual["router_settings"]["normal_cache_size"], actual["durable_batches_capability"]),
                        (batch, cache, capability))
                    self.assertEqual(actual["financial_batch_soft_budget_seconds"], .005)
                    self.assertFalse(actual["physical_commit_counts_measured"])
                    self.assertEqual(len(summary["actual_spawned_worker_inputs"]), 1)
                    worker = summary["actual_spawned_worker_inputs"][0]
                    self.assertEqual(worker["received_settings"], actual["router_settings"])
                    self.assertNotEqual(worker["pid"], os.getpid())
                    self.assertEqual(worker["pid"], summary["initial_real_pid_and_fence"]["workers"][0]["pid"])
                    self.assertEqual(summary["readonly_reconciliation"]["persistent_successes"], 8)
                    for shard in summary["readonly_reconciliation"]["shards"]:
                        self.assertIs(shard["durable_batches_capability"], capability)
                        self.assertEqual(shard["confirmed_matches"], 0)
                    phases = summary["execution_classification"]
                    self.assertEqual(phases["durable_metadata_enqueue_acknowledgements"], 8)
                    self.assertEqual(phases["observed_financial_admission_committed_receipts"], 8)
                    self.assertEqual(phases["internal_command_execution_attempts"], 0)
                    self.assertEqual(sum(phases["batch_failure_events_by_phase"].values()), 0)
                    if not batch:
                        self.assertEqual(summary["batch_dispatch_diagnostics"]["prepared_batches"], 0)
                    self.assertEqual(list((directory / "profiles").glob("*.prof")), [])
                    manifest = json.loads((directory / "manifest.json").read_text())
                    self.assertIn("workers/worker-" + str(worker["pid"]) + ".json", manifest["files"])


if __name__ == "__main__":
    unittest.main()
