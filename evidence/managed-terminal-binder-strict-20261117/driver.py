import contextlib,io,json,pathlib,sys,time
root=pathlib.Path.cwd();output=pathlib.Path(sys.argv[1])
p=root/"evidence/reviews/managed-terminal-binder-independent-20261117/first_independent_challenge.py"
namespace={"__file__":str(p),"__name__":"__main__"};captured=io.StringIO();exit_code=None
with contextlib.redirect_stdout(captured):
 try:
  exec(compile(p.read_bytes(),str(p),"exec"),namespace)
 except SystemExit as result:
  exit_code=result.code
raw=captured.getvalue();(output/"original17.stdout.json").write_text(raw)
original=json.loads(raw)
binder=namespace["binder"];fixture=namespace["fixture"]
r=fixture.synthetic_chain();r["before"]["identity"].update(pid=binder.DRIVER[0],birth=str(int(binder.DRIVER[1])+1))
legal=binder.bind_records(r,all_file_pins_verified=True)
okay=exit_code==0 and original["passed"] is True and len(original["cases"])==17 and legal["metadata_chain_bound"] is True
assert legal["candidate_for_independent_terminal_review"] is False and legal["production_approved"] is False
summary={"passed":okay,"original17_exit_code":exit_code,"original17_passed":original["passed"],"original17_cases":len(original["cases"]),"same_pid_new_birth_legal_case":legal,"planned_total_cases":18,"actual_source_is_in_outer_record":True,"original_challenge_candidate_commit_label_is_historical":True}
print(json.dumps(summary,sort_keys=True,indent=2))
raise SystemExit(0 if okay else 1)
