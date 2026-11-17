"""Pure plan/AST counterexample; no producer import, SQL or process call."""
import ast
from hashlib import sha256
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from time import monotonic
from unittest.mock import patch
import sys

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from tools import run_managed_long as runner
GIB=1024**3
os.sched_setaffinity(0,{3})
started=monotonic()
plan=json.loads((ROOT/'benchmarks/plans/20261117-managed-d421df3-six-hours.json').read_text())
plan['observer']['output_budget_bytes']=2*GIB
plan['producer']['source_budget_bytes']=GIB
amendment=json.loads((ROOT/'benchmarks/plans/20261117-managed-d421df3-six-hours-observer-amendment.json').read_text())
module=ast.parse((ROOT/'benchmarks/run_managed_soak.py').read_text())
configuration=next(n for n in module.body if isinstance(n,ast.ClassDef) and n.name=='Configuration')
field=next(n for n in configuration.body if isinstance(n,ast.AnnAssign) and n.target.id=='max_directory_bytes')
actual_default=eval(compile(ast.Expression(field.value),'exact-source-default','eval'),{'__builtins__':{}},{})
with TemporaryDirectory() as directory:
 path=Path(directory)/'plan.json';raw=json.dumps(plan).encode();path.write_bytes(raw)
 amendment['original_plan_sha256']=sha256(raw).hexdigest();change=Path(directory)/'change.json';change.write_text(json.dumps(amendment))
 with patch.object(runner.subprocess,'Popen',side_effect=AssertionError('no process permitted')):
  parsed,_,_=runner.read_plan(path,change)
  argv=runner.producer_command(parsed,Path(directory)/'never-created-job')
 declared=parsed['producer']['source_budget_bytes']
 assert actual_default==6*GIB and declared==GIB
 assert not (Path(directory)/'never-created-job').exists()
result={'reviewed_source':'c27ced8306009106f9da720179fa53b1080f2c91','explicit_output_budget':2*GIB,
 'accepted_declared_source_budget':declared,'actual_configuration_max_directory_bytes_AST':actual_default,
 'producer_argv':argv,'producer_cli_has_source_budget_override':False,
 'accepted_source_reservation_understatement_bytes':actual_default-declared,
 'actual_plan_validation_refused':False,'native_producer_SQL_service_process_started':False,
 'expected_new_explicit_policy':'reject a mismatched producer declaration before preflight subprocess or start',
 'wall_seconds':monotonic()-started}
Path(__file__).with_name('source-budget-red.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
raise SystemExit(1)  # Deliberate historical red: explicit wrong budget accepted.
