"""Execute exact original pure controls only; never invoke old dummy main."""
import ast
from hashlib import sha256
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
from tempfile import TemporaryDirectory
import time

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from tools import run_managed_variants as runner
from tests.runner_package_fixtures import create_package_evidence, save
from tests.test_managed_variant_runner import COMMIT, raw_fixture


def main():
    signal.signal(signal.SIGALRM, lambda *_: (_ for _ in ()).throw(TimeoutError('pure closing bound')))
    signal.setitimer(signal.ITIMER_REAL, 4.5)
    started = time.monotonic()
    runs = []
    for name in ('additional-data-controls.py', 'pure-vectors/review_red_vectors.py'):
        result = subprocess.run([sys.executable, '-B', str(OUT/name)], cwd=ROOT,
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=1.5)
        label = Path(name).stem
        (OUT/(label+'.stdout')).write_bytes(result.stdout)
        (OUT/(label+'.stderr')).write_bytes(result.stderr)
        runs.append({'script':name,'sha256':sha256((OUT/name).read_bytes()).hexdigest(),
            'returncode':result.returncode})
        assert result.returncode == 0
    old = OUT/'original-run-review-not-invoked.py'
    tree = ast.parse(old.read_text())
    original_main = next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='main')
    selected = [n for n in original_main.body if isinstance(n,ast.With)
        and any(isinstance(item.context_expr,ast.Call)
            and isinstance(item.context_expr.func,ast.Name)
            and item.context_expr.func.id=='TemporaryDirectory'
            and any(k.arg=='prefix' and isinstance(k.value,ast.Constant)
                and k.value.value=='uta-independent-runner-report-' for k in item.context_expr.keywords)
            for item in n.items)]
    assert len(selected)==1
    records={}
    module=ast.fix_missing_locations(ast.Module(body=selected,type_ignores=[]))
    exec(compile(module,str(old),'exec'),dict(TemporaryDirectory=TemporaryDirectory,Path=Path,
        create_package_evidence=create_package_evidence,COMMIT=COMMIT,runner=runner,save=save,records=records))
    assert records['report_output_path_control']['outcome']['accepted'] is False
    assert records['report_output_path_control']['outcome']['error_type']=='GateError'
    # Confirm lawful business rejection remains in the same 180/20 mix.
    with TemporaryDirectory(prefix='uta-independent-valid-raw-') as temporary:
        root=Path(temporary)
        hashes=raw_fixture(root)
        legal=runner.recompute(root,runner.schedule()[0],hashes,COMMIT)
        assert legal['counts']=={'financial_succeeded':180,'business_rejected':20}
        assert legal['technical_and_deadline_passed'] is True
    additional=json.loads((OUT/'additional-data-controls.json').read_text())
    assert all(not row['outcome']['accepted'] and row['outcome']['error_type']=='GateError'
               for row in additional['controls'])
    report={'actual_source_commit':'8a39b0ff039ef825d325257870b9f83a614c1ec3',
        'source_runner_sha256':sha256((ROOT/'tools/run_managed_variants.py').read_bytes()).hexdigest(),
        'original_script_source_labels_preserved':'673d319 labels in copied historical scripts were not rewritten',
        'original_pure_runs':runs,'original_main_or_dummy_invoked':False,
        'R5_original_pure_AST_block':{'lines':[selected[0].lineno,selected[0].end_lineno],
            'ast_sha256':sha256(ast.dump(selected[0],include_attributes=False).encode()).hexdigest(),
            'result':records['report_output_path_control']},
        'legal_raw_mix':legal['counts'],'legal_raw_gate':legal['technical_and_deadline_passed'],
        'elapsed_seconds':time.monotonic()-started,'actual_cpu_ids':sorted(os.sched_getaffinity(0)),
        'SQL_service_collector_verifier_build_install_benchmark_or_real_dummy_executed':False,
        'execution_approved':False,'production_approved':False}
    (OUT/'execution.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
    signal.setitimer(signal.ITIMER_REAL,0)
    print(json.dumps({'elapsed_seconds':report['elapsed_seconds'],'old_four_pure_cases':'PASS',
        'four_new_red_controls':'all GateError refused','R5_output_mismatch':'GateError refused',
        'legal_raw_mix':legal['counts']},sort_keys=True))


if __name__=='__main__':
    main()
