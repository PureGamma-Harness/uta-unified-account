from pathlib import Path
import datetime
import hashlib
import json
import os
import subprocess
import sys
import time


def main():
    root, output = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve()
    output.mkdir(exist_ok=True)
    os.sched_setaffinity(0, {min(os.sched_getaffinity(0))})
    base = '74e03a8fc7e3265cb03a3ffa0ffcaeac88fc35fd'
    runtime = {str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
               for path in sorted((root/'uta').glob('*.py'))}
    for path, digest in runtime.items():
        assert hashlib.sha256(subprocess.check_output(['git','show',base+':'+path],cwd=root)).hexdigest() == digest
    manifest = dict(runtime_base=base, runtime_sha256=runtime,
        tested_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),
        dirty_worktree=subprocess.check_output(['git','status','--porcelain'],cwd=root,text=True),
        test_sha256=hashlib.sha256((root/'tests/test_batch_cache_integration.py').read_bytes()).hexdigest(),
        driver_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), runs=[])
    deadline = time.monotonic()+42
    for label, executable in [('python310','/tmp/uta-python310/cpython-3.10.22-linux-x86_64-gnu/bin/python3.10'),
                              ('python312',sys.executable),('python313','/usr/bin/python3')]:
        facts = output/label
        facts.mkdir()
        environment = dict(os.environ, UTA_BATCH_CACHE_TEST_EVIDENCE=str(facts))
        command = [executable,'-m','unittest','tests.test_batch_cache_integration','-v']
        started = datetime.datetime.now(datetime.timezone.utc).isoformat()
        begin = time.monotonic_ns()
        run = subprocess.run(command,cwd=root,env=environment,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,
                             text=True,timeout=min(15,max(1,deadline-time.monotonic())))
        log = output/(label+'-unittest.txt')
        log.write_text(run.stdout)
        actual_environment = json.loads(subprocess.check_output([executable,'-c',
            'import json,os,platform,sqlite3;print(json.dumps(dict(python=platform.python_version(),sqlite=sqlite3.sqlite_version,affinity=sorted(os.sched_getaffinity(0)))))'],text=True))
        record = dict(command=command,started_utc=started,elapsed_ns=time.monotonic_ns()-begin,
            exit_code=run.returncode,environment=actual_environment,log=log.name,
            log_sha256=hashlib.sha256(log.read_bytes()).hexdigest(),
            actual_fact_files={str(p.relative_to(output)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(facts.glob('*.json'))})
        manifest['runs'].append(record)
        (output/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
        print(json.dumps(record),flush=True)
        if run.returncode:
            print(run.stdout[-6000:],flush=True)
            break
    return any(row['exit_code'] for row in manifest['runs'])


if __name__ == '__main__':
    raise SystemExit(main())
