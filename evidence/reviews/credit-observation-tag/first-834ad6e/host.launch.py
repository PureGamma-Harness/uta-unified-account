from pathlib import Path
import hashlib,json,os,subprocess,time
ROOT=Path(__file__).resolve().parent
ARGV=["/opt/codex/runtimes/codex-primary-runtime/dependencies/python/bin/python3.12","-I","-S","-B","/workspace/uta-credit-artifact-diag-compat/tools/run_credit_observation_tag_outer_once.py","--execute","--source-commit","834ad6e4da8a97c2246b0a49d82085183f73519c","--plan-sha256","8f12dd7a2ad9faabf4981499dee4bf011111273a48bf797678053dbc684ee726","--output","/workspace/uta-credit-observation-tag-834ad6e-once01"]
def new(name,value):
 fd=os.open(ROOT/name,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
 with os.fdopen(fd,"wb") as handle:
  handle.write((json.dumps(value,sort_keys=True,indent=2)+"\n").encode());handle.flush();os.fsync(handle.fileno())
start=time.monotonic_ns()
new("intent.json",{"argv":ARGV,"shell":False,"attempt":1,"monotonic_intent_ns":start,"source_commit":"834ad6e4da8a97c2246b0a49d82085183f73519c","plan_sha256":"8f12dd7a2ad9faabf4981499dee4bf011111273a48bf797678053dbc684ee726","no_retry_authorized":True})
fds=[os.open(ROOT/name,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600) for name in ("launcher.stdout.txt","launcher.stderr.txt")]
process=None;status=None;reaped=False;error=None;launch=time.monotonic_ns()
try:
 process=subprocess.Popen(ARGV,stdin=subprocess.DEVNULL,stdout=fds[0],stderr=fds[1],cwd="/workspace/uta-credit-artifact-diag-compat",shell=False,close_fds=True)
 status=process.wait();reaped=True
except BaseException as failure:
 error=type(failure).__name__
finally:
 end=time.monotonic_ns()
 for fd in fds:os.fsync(fd);os.close(fd)
 raw={}
 for name in ("launcher.stdout.txt","launcher.stderr.txt"):
  value=(ROOT/name).read_bytes();raw[name]={"bytes":len(value),"sha256":hashlib.sha256(value).hexdigest()}
 new("execution.json",{"argv":ARGV,"shell":False,"attempt":1,"actual_outer_exit":status,"actual_outer_reaped":reaped,"error_type":error,"monotonic_intent_ns":start,"monotonic_launch_ns":launch,"monotonic_end_ns":end,"outer_elapsed_ns":end-launch,"intent_through_completion_ns":end-start,"launcher_raw":raw,"caller_not_inner_self_attestation":True,"production_approved":False})
print(json.dumps({"actual_outer_exit":status,"actual_outer_reaped":reaped,"elapsed_ns":end-launch,"launcher_raw":raw,"error_type":error}),flush=True)
raise SystemExit(status if type(status)is int and 0<=status<=255 else 126)
