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
    modules = ['tests.test_startup_write_contention', 'tests.test_owned_startup',
               'tests.test_owned_startup_reference', 'tests.test_worker_startup_lease',
               'tests.test_storage', 'tests.test_writer_fence']
    manifest = dict(commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip(),
        cwd=str(root), dirty_worktree=subprocess.check_output(['git', 'status', '--porcelain'], cwd=root, text=True),
        script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        runtime_sources={str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((root/'uta').glob('*.py'))},
        selected_tests={name: hashlib.sha256((root/(name.replace('.', '/')+'.py')).read_bytes()).hexdigest() for name in modules}, runs=[])
    interpreters = [('python310', '/tmp/uta-python310/cpython-3.10.22-linux-x86_64-gnu/bin/python3.10'),
                    ('python312', sys.executable), ('python313', '/usr/bin/python3')]
    for label, executable in interpreters:
        command = [executable, '-m', 'unittest', *modules, '-v']
        started = datetime.datetime.now(datetime.timezone.utc).isoformat()
        begin = time.monotonic_ns()
        result = subprocess.run(command, cwd=root, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=90)
        log = output/(label+'-targeted.txt')
        log.write_text(result.stdout)
        environment = subprocess.check_output([executable, '-c', 'import json,os,platform,sqlite3;print(json.dumps(dict(python=platform.python_version(),sqlite=sqlite3.sqlite_version,affinity=sorted(os.sched_getaffinity(0)))))'], text=True)
        row = dict(command=command, started_utc=started, elapsed_ns=time.monotonic_ns()-begin,
            exit_code=result.returncode, environment=json.loads(environment), log=str(log), sha256=hashlib.sha256(log.read_bytes()).hexdigest())
        manifest['runs'].append(row)
        (output/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
        print(json.dumps(row), flush=True)
        if result.returncode:
            print(result.stdout[-6000:], flush=True)
            break
    return any(row['exit_code'] for row in manifest['runs'])


if __name__ == '__main__':
    raise SystemExit(main())
