"""Synthetic JSON-only contract cases; no real task or database is accessed."""
import copy
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

TOOLS = Path(__file__).parents[1] / "tools"
sys.path.insert(0, str(TOOLS))
import bind_managed_terminal_evidence as binder


def synthetic_chain():
    job = {"job_id": "synthetic-terminal-contract-case", "planned_rounds": 5400,
           "configuration": {"duration": 21600.0, "rate": .25},
           "environment": {"commit": binder.SOURCE, "synthetic": True,
                           "python": "synthetic-python", "sqlite": "synthetic-sqlite",
                           "source_sha256": {"uta/example.py": "1" * 64},
                           "workload_spec_sha256": "2" * 64},
           "accounts": ["managed-soak-alice", "managed-soak-bob", "managed-soak-credit"],
           "bootstrap": {"synthetic_only": True, "initial_principal_satoshi": 10800},
           "file_identities": {"synthetic-file-identity": [1, 2]}}
    job["validation_evidence"] = {"code_commit":binder.SOURCE,"engineering_test_qualified":True,
        "production_approved":False,"python":"synthetic-python","sqlite":"synthetic-sqlite","tests_run":1801,
        "artifact_sha256":{name:"9"*64 for name in ("summary.json","worker-result.json","unittest.txt")}}
    baseline = {"job_id_sha256": binder.digest(job["job_id"]), "job_manifest_sha256": binder.digest(job),
                "frozen_commit": binder.SOURCE, "source_sha256": job["environment"]["source_sha256"],
                "workload_spec_sha256": job["environment"]["workload_spec_sha256"],
                "started_boottime_ns": binder.START, "deadline_boottime_ns": binder.DEADLINE,
                "boot_id": binder.BOOT, "duration_seconds": 21600.0, "planned_rounds": 5400,
                "file_identities_sha256": binder.digest(job["file_identities"]),
                "driver_pid": binder.DRIVER[0], "driver_birth": binder.DRIVER[1],
                "observer_code_sha256": binder.OBSERVER_CODE}
    contract = binder.digest(baseline)
    progress = {"status": "completed", "elapsed_seconds": 21600.1, "planned_rounds": 5400,
                "rounds": {"DONE": 5400}, "unresolved_steps": 0, "unresolved_faults": 0,
                "controller_sessions": 1, "verified_tls": True, "logs_verified": True,
                "final_audit": {"golden_passed": True}, "error": None, "fault_signals": dict(binder.FAULTS)}
    launch = {"driver_pid": binder.DRIVER[0], "driver_birth": binder.DRIVER[1],
              "launched_wall_ns": 1000, "launched_boottime_ns": 2000}
    wm = {"checkpoint": {"sequence": 123, "hash": "3" * 64}, "contract_sha256": contract,
          "financial": {"format": 2, "sha256": "4" * 64, "ledger_hash": "5" * 64,
                        "ledger_sequence": 27006, "business_event_sequence": 100000}}
    receipt = {"format": 1, "frozen_commit": binder.SOURCE, "producer_cold_audit_passed": True,
               "producer_audit_scope": binder.SCOPE,
               "producer_audit_runtime": {k:job["environment"][k] for k in ("python", "sqlite")},
               "private_clone_estimated_bytes":123456,"private_clone_max_bytes":1073741824,
               "audit_sha256": "6" * 64, "watermark_before": wm, "watermark_after": wm}
    def stopped(pid):
        return {"pid": pid, "birth": None, "state": "missing", "visibility": "absent",
                "identity_matches": False, "alive": False, "known_stopped": True}
    faults = [{"kind": kind, "round": r, "state": "DONE", "signal_sent": True,
               "old_generation": r, "new_generation": r + 1}
              for kind, step in (("worker",30),("parent",300)) for r in range(step,5401,step)]
    def snapshot(after):
        return {"frozen_commit": binder.SOURCE, "contract_sha256": contract,
                "original_start_boottime_ns": binder.START, "original_deadline_boottime_ns": binder.DEADLINE,
                "active_elapsed_seconds": 21600.1, "planned_rounds": 5400, "completed_rounds": 5400,
                "active_rounds": [], "logical_point": "stable_boundary", "unresolved_steps": 0,
                "unresolved_faults": 0, "driver": stopped(binder.DRIVER[0]), "listener": stopped(321),
                "worker": {"process": stopped(456), "lease_active": False}, "planned_faults": faults,
                "alerts": [], "finance": {"retry_alerts": [], "watermark": wm["financial"],
                    "golden": {"compared": True, "passed": True, "errors": []},
                    "counts": dict(binder.COUNTS), "residuals": {"live_orders": 0, "positions": []}},
                "final_evidence_eligible": after,
                "final_reconciliation": {"eligible": after, "errors": [] if after else ["producer_cold_audit_same_watermark_missing"],
                    "watermark": wm, "independent_reopen_same_watermark": True,
                    "independent_reopen_reconciliation_passed": True,
                    "producer_audit_sha256": receipt["audit_sha256"] if after else None,
                    "logs": {"verified": True, "events": 123, "last_hash": "3" * 64}}}
    def child(response, pid, birth, start, end, bootstart=10):
        return {"exit_code": 0, "identity": {"pid": pid,"birth":birth,"started_wall_ns":start,
                "started_boottime_ns":bootstart}, "ended_wall_ns":end, "stdout_complete":True,
                "stdout_sha256":"7"*64,"stderr_sha256":"8"*64,"stderr_present":False,"response":response}
    coverage = {"coverage_status":"COMPLETE_WITHIN_COVERAGE_BUDGET", "coverage_no_go_reasons":[],
                "measurement_status":"OBSERVED", "samples_observed":300,"last_sample_attempt_id":300,
                "actual_completed_active_seconds":21600.1,"preregistered_duration_seconds":21600,
                "preregistered_interval_seconds":61,"technical_read_unknown_budget":3,
                "consecutive_technical_read_unknown":0,"maximum_observed_consecutive_technical_read_unknown":0,
                "maximum_allowed_consecutive_technical_read_unknown":1,
                "counts":{"technical_read_unknown_samples":0},"logical_point_counts":{},
                "financial_golden_counts":{},"technical_error_types":{},"technical_error_digests":{},
                "alert_counts":{},"fatal_financial_code_counts":{},
                "blocks":[{"index":i,"start_active_seconds":i*1800,"end_active_seconds":(i+1)*1800,
                           "stable_golden_samples":1,"required_stable_golden_samples":1,"state":"SATISFIED"}
                          for i in range(12)]}
    summary = {"status":"COLLECTION_FINISHED", "financial_final_evidence_eligible":True,
               "overall_engineering_evidence_within_gates":True, "collection_errors":[],
               "historical_financial_alert_codes":[], "official_driver_drain_requested":False,
               "expected_fault_signals":dict(binder.FAULTS), "actual_fault_signals":dict(binder.FAULTS),
               "fault_schedule_complete":True, "no_automatic_resume_or_next_job":True,"live_coverage":coverage}
    return copy.deepcopy({"job":job,"progress":progress,"baseline":baseline,"launch":launch,
            "producer":child({k:v for k,v in progress.items() if k != "error"},binder.DRIVER[0],binder.DRIVER[1],1000,2000,2000),
            "before":child(snapshot(False),201,"2",3000,4000),"cold":child(receipt,202,"3",5000,6000),
            "receipt":receipt,"after":child(snapshot(True),203,"4",7000,8000),
            "coverage":coverage,"final":summary,"supervisor_failure_absent":True})


class TerminalBindingTests(unittest.TestCase):
    def bind(self, records):
        return binder.bind_records(records, all_file_pins_verified=True)

    def test_complete_schema_shaped_synthetic_chain_binds_but_remains_unapproved(self):
        result = self.bind(synthetic_chain())
        self.assertEqual(result["missing_or_mismatched_evidence_codes"], [])
        self.assertTrue(result["metadata_chain_bound"])
        self.assertFalse(result["candidate_for_independent_terminal_review"])
        for flag in ("financial_6h_passed","continuous_6h_stability_passed","continuous_24h_stability_passed",
                     "capacity_10000_per_s_passed","production_approved","full_risk_engine_reexecution_passed"):
            self.assertIs(result[flag],False)

    def test_every_missing_record_blocks_binding(self):
        for label in binder.FILES:
            with self.subTest(label=label):
                records=synthetic_chain();del records[label]
                self.assertFalse(self.bind(records)["metadata_chain_bound"])

    def test_each_child_failure_or_incomplete_or_missing_identity_blocks(self):
        for label in ("producer","before","cold","after"):
            for key,value in (("exit_code",1),("stdout_complete",False),("identity",{})):
                with self.subTest(label=label,key=key):
                    records=synthetic_chain();records[label][key]=value
                    self.assertFalse(self.bind(records)["metadata_chain_bound"])

    def test_wrong_boot_clock_source_original_job_or_contract_blocks(self):
        for label,key,value in (("baseline","boot_id","wrong"),("baseline","deadline_boottime_ns",binder.START+1000000000),
                                ("baseline","frozen_commit","a"*40),("job","job_id","other"),
                                ("baseline","observer_code_sha256",{})):
            records=synthetic_chain();records[label][key]=value
            self.assertFalse(self.bind(records)["metadata_chain_bound"])

    def test_no_duration_epsilon_or_observer_wait_credit(self):
        for elapsed in (21599.999999,True):
            records=synthetic_chain();records["progress"]["elapsed_seconds"]=elapsed
            self.assertFalse(self.bind(records)["metadata_chain_bound"])

    def test_watermark_audit_runtime_scope_and_hash_disagreement_blocks(self):
        for key,value in (("audit_sha256","f"*64),("producer_audit_runtime",{}),("producer_audit_scope","other"),
                          ("watermark_after",{}),("producer_cold_audit_passed",False)):
            records=synthetic_chain();records["receipt"][key]=value
            self.assertFalse(self.bind(records)["metadata_chain_bound"])
        records=synthetic_chain();records["after"]["response"]["final_reconciliation"]["watermark"]={}
        self.assertFalse(self.bind(records)["metadata_chain_bound"])

    def test_before_legitimately_lacks_cold_receipt_after_cannot(self):
        records=synthetic_chain()
        self.assertTrue(self.bind(records)["metadata_chain_bound"])
        records["after"]["response"]["final_reconciliation"]["errors"]=["producer_cold_audit_same_watermark_missing"]
        self.assertFalse(self.bind(records)["metadata_chain_bound"])

    def test_fault_mismatch_duplicate_or_malformed_kind_blocks(self):
        for value in (("final","actual_fault_signals",{"worker":179,"parent":18}),
                      ("progress","fault_signals",{"worker":179,"parent":18})):
            records=synthetic_chain();records[value[0]][value[1]]=value[2]
            self.assertFalse(self.bind(records)["metadata_chain_bound"])
        for malformed in ([],{"unexpected":"object"}):
            records=synthetic_chain();records["after"]["response"]["planned_faults"][0]["kind"]=malformed
            self.assertFalse(self.bind(records)["metadata_chain_bound"])
        records=synthetic_chain();f=records["after"]["response"]["planned_faults"];f[-1]=copy.deepcopy(f[0])
        self.assertFalse(self.bind(records)["metadata_chain_bound"])

    def test_running_worker_unknown_exit_or_lease_active_blocks(self):
        for update in ({"alive":True},{"known_stopped":False},{"visibility":"unknown"}):
            records=synthetic_chain();records["after"]["response"]["worker"]["process"].update(update)
            self.assertFalse(self.bind(records)["metadata_chain_bound"])
        records=synthetic_chain();records["after"]["response"]["worker"]["lease_active"]=True
        self.assertFalse(self.bind(records)["metadata_chain_bound"])

    def test_collection_errors_drain_failed_coverage_and_missing_external_pin_block(self):
        for key,value in (("collection_errors",["some_error"]),("official_driver_drain_requested",True),
                          ("fault_schedule_complete",False)):
            records=synthetic_chain();records["final"][key]=value
            self.assertFalse(self.bind(records)["metadata_chain_bound"])
        records=synthetic_chain();records["coverage"]["coverage_status"]="NO_GO"
        self.assertFalse(self.bind(records)["metadata_chain_bound"])
        self.assertFalse(binder.bind_records(synthetic_chain())["metadata_chain_bound"])

    def test_post_shutdown_informational_alert_is_not_a_new_financial_gate(self):
        records=synthetic_chain()
        records["after"]["response"]["alerts"]=["market_stale","progress_future_or_stale"]
        self.assertTrue(self.bind(records)["metadata_chain_bound"])

    def test_bundle_file_hashes_external_manifest_and_absence_are_checked(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);records=synthetic_chain();pins={}
            for label,(relative,_) in binder.FILES.items():
                p=root/relative;p.parent.mkdir(parents=True,exist_ok=True)
                raw=json.dumps(records[label],sort_keys=True).encode();p.write_bytes(raw)
                pins[relative]=binder.hashlib.sha256(raw).hexdigest()
            manifest={"schema":"uta-terminal-json-pins-v1","source_commit":binder.SOURCE,"files":pins}
            mp=root/'reviewed.json';raw=json.dumps(manifest,sort_keys=True).encode();mp.write_bytes(raw)
            checksum=binder.hashlib.sha256(raw).hexdigest()
            self.assertTrue(binder.verify_bundle(root,mp,checksum)["metadata_chain_bound"])
            (root/'control/strict-producer-cold-result.json').write_text('{}')
            self.assertFalse(binder.verify_bundle(root,mp,checksum)["metadata_chain_bound"])
            self.assertFalse(binder.verify_bundle(root,mp,'0'*64)["metadata_chain_bound"])


if __name__ == "__main__":
    unittest.main()
