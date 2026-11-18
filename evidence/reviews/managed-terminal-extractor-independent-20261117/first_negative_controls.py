"""Independent fake-file review; never read real task paths or import UTA."""
import importlib.util,json,pathlib,tempfile,unittest
ROOT=pathlib.Path(__file__).resolve().parents[3]
spec=importlib.util.spec_from_file_location("candidate_terminal_metadata",ROOT/"tools/extract_managed_terminal_evidence.py")
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
def good():
    return {
      "job/progress.json":{"status":"completed","elapsed_seconds":21600.0,"planned_rounds":5400,"rounds":{"DONE":5400},"unresolved_steps":0,"unresolved_faults":0,"controller_sessions":1,"verified_tls":True,"logs_verified":True,"error":None,"final_audit":{"golden_passed":True},"fault_signals":{"worker":180,"parent":18},"validation_evidence":{"code_commit":m.SOURCE}},
      "control/final-summary.json":{"status":"COLLECTION_FINISHED","financial_final_evidence_eligible":True,"overall_engineering_evidence_within_gates":True},
      "control/producer-result.json":{},
      "control/strict-producer-cold-result.json":{},
      "control/live-coverage.json":{"coverage_status":"COMPLETE_WITHIN_COVERAGE_BUDGET"}}
def readfake(records):
    with tempfile.TemporaryDirectory(prefix="terminal-independent-fake-") as directory:
        root=pathlib.Path(directory)
        for relative,value in records.items():
            p=root/relative;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(value))
        return m.extract(root)
class IndependentTerminalReview(unittest.TestCase):
    def test_only_progress_and_summary_stays_incomplete(self):
        r=good();r={p:x for p,x in r.items() if p in {"job/progress.json","control/final-summary.json"}}
        result=readfake(r)
        self.assertFalse(result["candidate_for_independent_terminal_review"])
        self.assertFalse(result["financial_6h_passed"])
    def test_failed_producer_and_cold_receipts_cannot_qualify(self):
        r=good()
        r["control/producer-result.json"]={"exit_code":1,"stdout_complete":False}
        r["control/strict-producer-cold-result.json"]={"exit_code":1,"stdout_complete":False}
        self.assertFalse(readfake(r)["candidate_for_independent_terminal_review"])
    def test_empty_receipts_without_identity_final_snapshots_or_cold_receipt_cannot_qualify(self):
        self.assertFalse(readfake(good())["candidate_for_independent_terminal_review"])
    def test_inconsistent_watermarks_and_audit_hash_cannot_qualify(self):
        r=good()
        r["control/final-before-cold.json"]={"response":{"final_reconciliation":{"watermark":{"checkpoint":"before"}}}}
        r["control/final-after-cold.json"]={"response":{"final_reconciliation":{"watermark":{"checkpoint":"different"},"producer_audit_sha256":"a"*64}}}
        r["observer/producer-cold-audit-receipt.json"]={"format":1,"frozen_commit":m.SOURCE,"producer_cold_audit_passed":False,"audit_sha256":"b"*64,"watermark_before":{"checkpoint":"before"},"watermark_after":{"checkpoint":"different"}}
        self.assertFalse(readfake(r)["candidate_for_independent_terminal_review"])
    def test_summary_fault_facts_disagreeing_with_progress_cannot_qualify(self):
        r=good();r["control/final-summary.json"].update({"actual_fault_signals":{"worker":179,"parent":18},"fault_schedule_complete":False})
        self.assertFalse(readfake(r)["candidate_for_independent_terminal_review"])
    def test_wrong_original_contract_duration_cannot_qualify(self):
        r=good();r["job/job.json"]={"contract":{"started_boottime_ns":1000000000,"deadline_boottime_ns":2000000000,"duration_seconds":1,"planned_rounds":5400}}
        self.assertFalse(readfake(r)["candidate_for_independent_terminal_review"])
if __name__=="__main__": unittest.main(verbosity=2)
