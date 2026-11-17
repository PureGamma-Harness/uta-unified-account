"""One bounded synthetic package build; retain every first result externally."""
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import sys
import time

SOURCE = Path('/workspace/uta-deployment-sdist-fix')
OUTPUT = Path('/workspace/uta-deployment-package-e486-once-private')
COMMIT = 'e486d13d68cde98e1a1246b1274bf92bb3b1a29c'
OUTPUT.mkdir(mode=0o700, exist_ok=False)
DIST = OUTPUT / 'dist'
DIST.mkdir(mode=0o700)
started = time.monotonic()
records = []

def save(name, value):
    with (OUTPUT / name).open('x') as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())

def run(label, argv):
    before = time.monotonic()
    with (OUTPUT / (label + '.stdout')).open('xb') as out, (OUTPUT / (label + '.stderr')).open('xb') as err:
        try:
            result = subprocess.run(['taskset', '-c', '0', *argv], cwd=SOURCE,
                                    stdout=out, stderr=err,
                                    timeout=min(120, max(1, 180 - (before - started))))
            code, timed_out = result.returncode, False
        except subprocess.TimeoutExpired:
            code, timed_out = None, True
    record = dict(label=label, argv=argv, exit_code=code, timed_out=timed_out,
                  elapsed_seconds=time.monotonic()-before)
    records.append(record)
    save(label+'.execution.json', record)
    if code != 0:
        save('first-result.json', dict(passed=False, records=records, source_commit=COMMIT))
        raise SystemExit(1)

assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=SOURCE, text=True).strip() == COMMIT
assert not subprocess.check_output(['git', 'status', '--porcelain'], cwd=SOURCE)
paths = subprocess.check_output(['git', 'ls-tree', '-r', '--name-only', COMMIT], cwd=SOURCE, text=True).splitlines()
missing = [name for name in paths if not (SOURCE / name).is_file()]
save('admission.json', dict(source_commit=COMMIT, tracked_files=len(paths), missing=missing,
                            cpu_ids=[0], whole_budget_seconds=180, python=sys.version,
                            original_pr27_failed_runs=[44187794849, 44187905394],
                            source_change='one explicit sdist template include; runtime unchanged',
                            production_approved=False))
assert not missing
run('build', [sys.executable, '-B', '-c',
              'import setuptools.build_meta as b; print(b.build_wheel('+repr(str(DIST))+')); print(b.build_sdist('+repr(str(DIST))+'))'])
wheels, sdists = list(DIST.glob('*.whl')), list(DIST.glob('*.tar.gz'))
assert len(wheels) == len(sdists) == 1
run('verify', [sys.executable, '-B', str(SOURCE/'tools/verify_release_archives.py'),
               '--source', str(SOURCE), '--commit', COMMIT, '--wheel', str(wheels[0]),
               '--sdist', str(sdists[0]), '--output', str(OUTPUT/'artifact-manifest.json')])
report = json.loads((OUTPUT/'artifact-manifest.json').read_text())
save('first-result.json', dict(passed=report['passed'], checks=report['checks'],
                              source_commit=COMMIT, records=records,
                              elapsed_seconds=time.monotonic()-started,
                              original_failures_preserved=True,
                              production_approved=False))
print(json.dumps(dict(source_commit=COMMIT, passed=report['passed'], checks=report['checks'],
                      elapsed_seconds=time.monotonic()-started, production_approved=False)))
