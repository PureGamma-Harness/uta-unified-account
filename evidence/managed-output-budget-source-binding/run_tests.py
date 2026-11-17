"""Pure JSON/metadata batch, at most ten seconds shared by all runtimes."""
from datetime import datetime, timezone
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import subprocess
import time

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location('budget_previous_commands',
    ROOT/'evidence/managed-output-budget/run_pure_tests.py')
PREVIOUS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PREVIOUS)


def main():
    started = time.monotonic()
    evidence = dict(started_utc=datetime.now(timezone.utc).isoformat(), cpu=2,
        sqlite_connections=0, services_started=0, dummy_children_started=0,
        original_jobs_changed=False, qualification_passed=False, runtimes={})
    for name, python in PREVIOUS.RUNTIMES.items():
        command = ['taskset', '-c', '2', python, '-B', '-W', 'error::ResourceWarning',
                   '-m', 'unittest', '-v', *PREVIOUS.SELECTED]
        log = OUT/f'final-{name}.txt'
        with log.open('wb') as stream:
            result = subprocess.run(command, cwd=ROOT, stdin=subprocess.DEVNULL, stdout=stream,
                stderr=subprocess.STDOUT, close_fds=True, timeout=max(.1,10-(time.monotonic()-started)))
        evidence['runtimes'][name] = dict(command_argv=command, exit_code=result.returncode,
            log_sha256=sha256(log.read_bytes()).hexdigest())
        if result.returncode:
            break
    evidence['wall_seconds'] = time.monotonic()-started
    evidence['finished_utc'] = datetime.now(timezone.utc).isoformat()
    (OUT/'results.json').write_text(json.dumps(evidence,sort_keys=True,indent=2)+'\n')
    assert len(evidence['runtimes']) == 3 and all(value['exit_code'] == 0 for value in evidence['runtimes'].values())
    print(json.dumps(evidence))


if __name__ == '__main__':
    main()
