"""Independent source/AST/ancestry checks. Does not import diagnostic or testcase."""
import ast
from hashlib import sha256
import json
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[3]
BASE='5a2961134aedaef9914d4cdd0247bb8795fb9b90'
CANDIDATE='b58e587bf8eb17c1c8449e65c7368a8fc2ec4a31'
BAD='9ba043d83c1e584f85fe10e2b263e8f77214359b'
METHOD='test_expired_sigstopped_shared_gate_owner_is_killed_so_publication_can_recover'
def blob(commit,name):return subprocess.check_output(['git','show',commit+':'+name],cwd=ROOT)
paths=subprocess.check_output(['git','ls-tree','-r','--name-only',BASE,'--','tests/'],cwd=ROOT,text=True).splitlines()
assert len(paths)==172
changed=[p for p in paths if blob(BASE,p)!=blob(CANDIDATE,p)]
assert changed==['tests/test_durable_faults.py']
assert blob(BASE,'tests/test_failure_diagnostics.py')==blob(CANDIDATE,'tests/test_failure_diagnostics.py')
ancestry=subprocess.run(['git','merge-base','--is-ancestor',BAD,CANDIDATE],cwd=ROOT)
assert ancestry.returncode==1
before=ast.parse(blob(BASE,'tests/test_durable_faults.py'));after=ast.parse(blob(CANDIDATE,'tests/test_durable_faults.py'))
method=next(n for n in ast.walk(after) if isinstance(n,ast.FunctionDef) and n.name==METHOD)
hooks=[(block,i,item) for block in ast.walk(method) if isinstance(block,ast.Try) for i,item in enumerate(block.finalbody) if isinstance(item,ast.If) and any(isinstance(n,ast.ImportFrom) and n.module=='tests.expired_gate_failure_evidence' for n in ast.walk(item))]
assert len(hooks)==1
block,index,hook=hooks[0]
expected=ast.parse('''if primary_error is not None:
    try:
        from tests.expired_gate_failure_evidence import emit_expired_gate_failure
        emit_expired_gate_failure(observation, errors, primary_error, self.router, thread)
    except BaseException:
        pass
''').body[0]
assert ast.dump(hook,include_attributes=False)==ast.dump(expected,include_attributes=False)
del block.finalbody[index]
assert ast.dump(before,include_attributes=False)==ast.dump(after,include_attributes=False)
helper_raw=blob(CANDIDATE,'tests/expired_gate_failure_evidence.py');helper=ast.parse(helper_raw)
forbidden={'open','connect','status','kill','pidfd_send_signal','start','wait','sleep','join','getsource','read_text','read_bytes'}
called={n.func.id if isinstance(n.func,ast.Name) else n.func.attr for n in ast.walk(helper) if isinstance(n,ast.Call) and isinstance(n.func,(ast.Name,ast.Attribute))}
assert not called&forbidden
assert not any(isinstance(n,ast.Attribute) and n.attr in {'f_locals','tb_lasti','args','__notes__'} for n in ast.walk(helper))
assert not subprocess.check_output(['git','diff',BASE,CANDIDATE,'--','uta/'],cwd=ROOT)
print(json.dumps({'base':BASE,'candidate':CANDIDATE,'original_tests_inventory':172,'original_files_byte_identical':171,'sole_existing_change':changed,'old_failure_diagnostics_byte_restored':True,'bad_preparation_commit_is_not_ancestor':True,'whole_original_module_AST_preserved_after_exact_hook_removed':True,'helper_has_no_extra_SQL_status_proc_signal_wait_source_introspection':True,'helper_sha256':sha256(helper_raw).hexdigest(),'original_primary_assertions_cleanup_and_windows_unchanged':True,'production_runtime_unchanged':True,'recommendation':'MAY_INTEGRATE_DIAGNOSTIC_ONLY; fresh exact full QA/CI/package and synthetic observation gates still required','five_second_runtime_fixed':False,'native_or_SQL_run':False,'production_approved':False},indent=2))
