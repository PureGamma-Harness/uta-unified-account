"""Pure source/result inspection; imports no financial runtime and opens no SQL."""
import ast
from hashlib import sha256
import json
from pathlib import Path
import subprocess

SOURCE = '91e4ae40b5e9b884c54026406299df5000c9c100'
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]

def code(path):
    raw = subprocess.check_output(['git', 'show', SOURCE + ':' + path], cwd=ROOT)
    assert (ROOT/path).read_bytes() == raw
    return raw, ast.parse(raw)

facts = {}
raw, tree = code('uta/durable_process.py')
cls = next(x for x in tree.body if isinstance(x, ast.ClassDef) and x.name == 'DurableProcessRouter')
methods = {x.name: x for x in cls.body if isinstance(x, ast.FunctionDef)}
supervisor = methods['_supervise']
facts['supervision_loop_is_independent_of_publication'] = not any(isinstance(x, ast.Attribute) and x.attr == 'publish_market' for x in ast.walk(supervisor))
facts['supervision_status_failure_becomes_none'] = any(isinstance(x, ast.Assign) and isinstance(x.value, ast.Constant) and x.value.value is None and any(isinstance(t, ast.Name) and t.id == 'lease' for t in x.targets) for x in ast.walk(supervisor))
facts['supervision_pipe_poll_and_recv_are_separate_calls'] = {x.attr for x in ast.walk(supervisor) if isinstance(x, ast.Attribute)} >= {'poll', 'recv'}
facts['supervision_mutex_covers_status_and_spawn'] = isinstance(supervisor.body[0], ast.While) and isinstance(supervisor.body[0].body[0], ast.With) and any(isinstance(x, ast.Attribute) and x.attr == '_spawn' for x in ast.walk(supervisor.body[0].body[0]))
facts['spawn_does_not_poll_or_recv_ready'] = not any(isinstance(x, ast.Attribute) and x.attr in {'poll', 'recv', 'wait'} for x in ast.walk(methods['_spawn']))
record = next(x for x in tree.body if isinstance(x, ast.FunctionDef) and x.name == '_record_process')
facts['record_process_has_no_router_flock_call'] = not any(isinstance(x, ast.Attribute) and x.attr == '_lock' for x in ast.walk(record))
raw_test, tests = code('tests/test_durable_faults.py')
cls_test = next(x for x in tests.body if isinstance(x, ast.ClassDef) and x.name == 'ManagedProcessFaultTests')
case = next(x for x in cls_test.body if isinstance(x, ast.FunctionDef) and x.name == 'test_expired_sigstopped_shared_gate_owner_is_killed_so_publication_can_recover')
publish = next(x for x in case.body if isinstance(x, ast.Try) for x in x.body if isinstance(x, ast.FunctionDef) and x.name == 'publish')
facts['publisher_records_error_in_local_list'] = any(isinstance(x, ast.Call) and isinstance(x.func, ast.Attribute) and isinstance(x.func.value, ast.Name) and x.func.value.id == 'errors' and x.func.attr == 'append' for x in ast.walk(publish))
facts['publisher_has_fresh_lease_assert_before_api'] = any(isinstance(x, ast.Call) and isinstance(x.func, ast.Attribute) and x.func.attr == 'assertTrue' for x in ast.walk(publish))
assert all(facts.values()), facts
hashes = {p: sha256(subprocess.check_output(['git','show',SOURCE+':'+p],cwd=ROOT)).hexdigest() for p in ['uta/durable_process.py','uta/writer_fence.py','uta/storage.py','tests/test_durable_faults.py']}
print(json.dumps({'source_commit':SOURCE,'facts':facts,'source_sha256':hashes,'sql_or_native_run':False,'historical_cause':'UNPROVEN','five_second_recovery_approved':False,'production_approved':False},indent=2))
