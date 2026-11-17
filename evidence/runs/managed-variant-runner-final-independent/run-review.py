"""One independent original-vector/dummy/pure-artifact check; no benchmark."""
from contextlib import redirect_stderr, redirect_stdout
from hashlib import sha256
import io
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
from tempfile import TemporaryDirectory
import time
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from tools import run_managed_variants as runner
from tests.runner_package_fixtures import create_package_evidence, save
from tests.test_managed_variant_runner import COMMIT


def main():
    signal.signal(signal.SIGALRM, lambda *_: (_ for _ in ()).throw(TimeoutError('independent total bound')))
    signal.setitimer(signal.ITIMER_REAL, 4.5)
    started = time.monotonic()
    original = OUT / 'pure-vectors/review_red_vectors.py'
    run = subprocess.run([sys.executable, '-B', str(original)], cwd=ROOT,
        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=1.5)
    (OUT / 'original-vectors.stdout').write_bytes(run.stdout)
    (OUT / 'original-vectors.stderr').write_bytes(run.stderr)
    records = {'original_vectors': {'returncode': run.returncode,
        'script_sha256': sha256(original.read_bytes()).hexdigest()}}
    old_affinity = os.sched_getaffinity(0)
    try:
        os.sched_setaffinity(0, {3, 4})
        get_affinity = os.sched_getaffinity
        reads = []
        def observe(pid):
            cpus = get_affinity(pid)
            reads.append({'pid': pid, 'actual_cpu_ids': sorted(cpus)})
            return cpus
        with TemporaryDirectory(prefix='uta-independent-runner-dummy-') as temporary:
            root = Path(temporary)
            with patch.object(runner.os, 'sched_getaffinity', side_effect=observe):
                result = runner.owned_run([sys.executable, '-c',
                    "import json,os;print(json.dumps({'actual_child_cpu_ids':sorted(os.sched_getaffinity(0))}))"],
                    root, root / 'dummy', cpu_ids=[3], wall_seconds=1,
                    grace_seconds=.05, kill_wait_seconds=.5, output_cap=4096,
                    protected={4471, 8784, os.getpid()})
            records['affinity_dummy'] = {'result': result, 'real_callthrough_affinity_reads': reads,
                'stdout': (root / 'dummy.stdout').read_text(),
                'parent_actual_cpu_ids': sorted(get_affinity(0))}
            assert result['returncode'] == 0 and result['launcher_affinity_acknowledged'] is True
            assert result['observed_child_cpu_ids'] == [3]
    finally:
        os.sched_setaffinity(0, old_affinity)
    with TemporaryDirectory(prefix='uta-independent-runner-report-') as temporary:
        root = Path(temporary)
        hashes, package = create_package_evidence(root, COMMIT)
        archives = runner.proof(package['archives'])
        runner.omission_binding(package, archives, hashes, COMMIT)
        controls = runner.proof(package['runtime_controls'])
        pinned = package['runtime_reports']['wheel']['path']
        controls['cases'][0]['argv'][11] = str(root / 'different-verifier-output.json')
        package['runtime_controls'] = save(root / 'controls-wrong-output-path.json', controls)
        try:
            runner.omission_binding(package, archives, hashes, COMMIT)
        except runner.GateError as error:
            outcome = {'accepted': False, 'error_type': type(error).__name__, 'message': str(error)}
        else:
            outcome = {'accepted': True}
        records['report_output_path_control'] = {'expected_pinned_report_path': pinned,
            'actual_argv_output_path': controls['cases'][0]['argv'][11], 'outcome': outcome,
            'collector_build_install_verifier_SQL_executed': False}
    records.update(elapsed_seconds=time.monotonic()-started,
        source_commit='673d3195b65cdb9e3fed2fd1b18dbad789d99b46',
        runtime_tests_or_benchmark_executed=False, original_jobs_accessed=False,
        protected_existing_processes_signalled=False, production_approved=False)
    (OUT / 'execution.json').write_text(json.dumps(records, indent=2, sort_keys=True)+'\n')
    signal.setitimer(signal.ITIMER_REAL, 0)
    print(json.dumps({'elapsed_seconds':records['elapsed_seconds'],
        'original_vectors_exit_code':run.returncode,
        'report_output_path_control':records['report_output_path_control']['outcome']},sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
