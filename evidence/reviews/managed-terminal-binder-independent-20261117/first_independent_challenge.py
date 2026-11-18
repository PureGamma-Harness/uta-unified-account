"""One independent pure challenge; the imported author module only builds schema fixtures."""
import copy,hashlib,importlib.util,json,pathlib,sys,tempfile
ROOT=pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/"tools"))
import bind_managed_terminal_evidence as binder
spec=importlib.util.spec_from_file_location("schema_fixture_only",ROOT/"tests/test_managed_terminal_binding.py")
fixture=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixture)
RESULTS=[]
def record(name,expected,run):
    try:
        result=run()
        actual=result["metadata_chain_bound"]
        okay=actual is expected
        detail={"actual_metadata_chain_bound":actual,"expected_metadata_chain_bound":expected,"candidate":result.get("candidate_for_independent_terminal_review"),"codes":result.get("missing_or_mismatched_evidence_codes")}
        assert result.get("production_approved") is False
        assert result.get("financial_6h_passed") is False
    except Exception as e:
        okay=False;detail={"exception_type":type(e).__name__,"expected_structured_fail_closed":True}
    RESULTS.append({"case":name,"passed":okay,**detail})
def changed(mutator):
    r=fixture.synthetic_chain();mutator(r)
    return binder.bind_records(r,all_file_pins_verified=True)
record("schema_baseline_remains_bound_unapproved",True,lambda:changed(lambda r:None))
record("original_failed_receipt_is_now_rejected",False,lambda:changed(lambda r:r["cold"].update(exit_code=1,stdout_complete=False)))
record("original_watermark_mismatch_is_now_rejected",False,lambda:changed(lambda r:r["after"]["response"]["final_reconciliation"].update(watermark={})))
record("original_fault_count_contradiction_is_now_rejected",False,lambda:changed(lambda r:r["final"].update(actual_fault_signals={"worker":179,"parent":18})))
def bool_zero(r):
    for key in ("before","after"):
        r[key]["response"].update(unresolved_steps=False,unresolved_faults=False)
record("boolean_zero_snapshot_counts_must_not_bind",False,lambda:changed(bool_zero))
def float_counts(r):
    for key in ("before","after"):
        r[key]["response"].update(planned_rounds=5400.0,completed_rounds=5400.0)
record("floating_snapshot_counts_must_not_bind",False,lambda:changed(float_counts))
def float_progress(r):
    r["progress"]["planned_rounds"]=5400.0;r["producer"]["response"]["planned_rounds"]=5400.0
record("floating_progress_count_must_not_bind",False,lambda:changed(float_progress))
record("floating_summary_fault_counts_must_not_bind",False,lambda:changed(lambda r:r["final"].update(expected_fault_signals={"worker":180.0,"parent":18.0},actual_fault_signals={"worker":180.0,"parent":18.0})))
def duplicate_identity(r):
    r["before"]["identity"].update(pid=binder.DRIVER[0],birth=binder.DRIVER[1])
record("producer_identity_reused_for_new_final_child_must_not_bind",False,lambda:changed(duplicate_identity))
def giant(r):
    r["progress"]["elapsed_seconds"]=10**1000
    r["producer"]["response"]["elapsed_seconds"]=10**1000
record("bounded_json_huge_integer_must_fail_closed_without_exception",False,lambda:changed(giant))
record("boolean_fault_generation_is_rejected",False,lambda:changed(lambda r:r["after"]["response"]["planned_faults"][0].update(old_generation=True)))
def bundle(mode):
    r=fixture.synthetic_chain()
    with tempfile.TemporaryDirectory(prefix="independent-binder-fake-") as directory:
        root=pathlib.Path(directory);pins={}
        for label,(relative,_) in binder.FILES.items():
            p=root/relative;p.parent.mkdir(parents=True,exist_ok=True)
            raw=json.dumps(r[label],sort_keys=True).encode();p.write_bytes(raw);pins[relative]=hashlib.sha256(raw).hexdigest()
        manifest={"schema":"uta-terminal-json-pins-v1","source_commit":binder.SOURCE,"files":pins}
        mp=root/"reviewed.json"
        if mode=="unknown_manifest_path":manifest["files"]["unrelated-resource.txt"]="0"*64
        raw=json.dumps(manifest,sort_keys=True).encode()
        if mode=="duplicate_key":raw=raw[:-1]+b',"source_commit":'+json.dumps(binder.SOURCE).encode()+b"}"
        mp.write_bytes(raw);checksum=hashlib.sha256(raw).hexdigest()
        if mode=="missing_file":(root/"control/producer-result.json").unlink()
        if mode=="wrong_file_hash":(root/"control/producer-result.json").write_bytes(b"{}")
        if mode=="bad_manifest_hash":checksum="0"*64
        if mode=="extra_unknown_resource":
            (root/"unrelated-resource.txt").write_text("SYNTHETIC-PRIVATE-SENTINEL")
        result=binder.verify_bundle(root,mp,checksum)
        assert "SYNTHETIC-PRIVATE-SENTINEL" not in json.dumps(result)
        return result
for mode in ("missing_file","wrong_file_hash","bad_manifest_hash","duplicate_key","unknown_manifest_path"):
    record(mode,False,lambda mode=mode:bundle(mode))
record("unknown_noncontract_resource_is_never_read_or_echoed",True,lambda:bundle("extra_unknown_resource"))
summary={"candidate_commit":"8a0aa6893d7ad301e1b67379a893e31554ca52c2","fixture_scope":"author synthetic schema builder imported without running its 12 test cases; independent mutations and expectations","cases":RESULTS,"passed":all(x["passed"] for x in RESULTS),"production_approved":False,"live_task_access":False,"sql_execution":False}
print(json.dumps(summary,sort_keys=True,indent=2))
sys.exit(0 if summary["passed"] else 1)
