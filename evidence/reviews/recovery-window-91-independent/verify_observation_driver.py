"""Compile/AST/hash inspection only; never execute the observation driver."""
import ast
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess

os.sched_setaffinity(0,{3})
ROOT=Path(__file__).resolve().parents[3]
CANDIDATE='5e26f0acd04b47cdafad942464e70b537c70d30b'
BASE='91e4ae40b5e9b884c54026406299df5000c9c100'
DRIVER='evidence/runs/recovery-horizon91/trace_original91.py'
EXPECTED='81b9a0c8ee7ed45f58f38174895ad2fa4e7d3043fd6ab7c03903016d69cae2ee'
def blob(commit,name):
 return subprocess.check_output(['git','show',commit+':'+name],cwd=ROOT)
raw=blob(CANDIDATE,DRIVER)
assert sha256(raw).hexdigest()==EXPECTED
compile(raw,DRIVER,'exec');tree=ast.parse(raw)
functions={n.name:n for n in tree.body if isinstance(n,ast.FunctionDef)}
worker=functions['worker'];inner={n.name:n for n in worker.body if isinstance(n,ast.FunctionDef)}
status=inner['status']
assert sum(isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='original_status' for n in ast.walk(status))==1
assert not any(isinstance(n,ast.Attribute) and n.attr in {'f_locals','connect','read_transaction','transaction'} for n in ast.walk(status))
assert not any(isinstance(n,ast.Attribute) and n.attr=='f_locals' for n in ast.walk(tree))
launch=functions['launch']
assert isinstance(launch.body[0],ast.Assign) and isinstance(launch.body[0].value,ast.Call) and launch.body[0].value.func.id=='monotonic'
reference=json.loads(blob(CANDIDATE,'evidence/runs/recovery-horizon91/original_source266.json'))
assert reference['source_commit']==BASE and len(reference['source_sha256'])==266
assert all(sha256(blob(CANDIDATE,name)).hexdigest()==digest for name,digest in reference['source_sha256'].items())
assert blob(CANDIDATE,'tests/test_durable_faults.py')==blob(BASE,'tests/test_durable_faults.py')
assert blob(CANDIDATE,'uta/durable_process.py')==blob(BASE,'uta/durable_process.py')
print(json.dumps({'candidate':CANDIDATE,'base_source':BASE,'driver_sha256':EXPECTED,'compiled_only':True,'executed_driver':False,'original_status_called_once_per_wrapper':True,'no_added_sql_in_status_wrapper':True,'no_frame_locals_serialization':True,'whole_timer_precedes_preflight':True,'reference_members_exact':266,'original_case_and_runtime_unchanged':True,'single_native_observation':'CONDITIONAL_GO_REQUIRES_PARENT_APPROVAL','required_outer_umask':'077','required_full_evidence':['whole<=30s','watchdogfalse','source266prepostexact','no_logger_or_sampling_unknown','observer_threads_end','no_forced_cleanup','spawn_start_return_balance','owned_PGID_SID_empty','PASS_is_NO_REPRO'],'five_second_recovery_approved':False,'production_approved':False},indent=2))
