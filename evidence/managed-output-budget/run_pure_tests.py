"""Sequential <=30-second JSON/metadata batch; no PIPE/dummy/SQL test selected."""
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import time

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT/'evidence/managed-output-budget'
RUNTIMES = {
    'python310': '/tmp/uta-python310/cpython-3.10.22-linux-x86_64-gnu/bin/python3.10',
    'python312': '/opt/codex/runtimes/codex-primary-runtime/dependencies/python/bin/python',
    'python313': '/usr/bin/python3.13',
}
SELECTED = ['tests.test_managed_output_budget', 'tests.test_managed_stability_prepare'] + [
    'tests.test_managed_long.LongPreparationTests.' + name for name in (
        'test_full_log_disk_cannot_suppress_known_financial_drain_or_history',
        'test_original_plan_hash_and_supported_amended_cadence',
        'test_producer_is_original_run_with_exact_report_and_no_resume',
        'test_observer_uses_supported_cli_with_fresh_devices_and_exec_identity',
        'test_timeline_keeps_partial_line_and_never_double_counts',
        'test_stop_refuses_protected_identity_without_reading_or_signalling_it')]


def main():
    start = time.monotonic()
    evidence = dict(started_utc=datetime.now(timezone.utc).isoformat(), cpu=2,
        scope='pure JSON and owned temporary output metadata; mocked control children',
        sqlite_connections=0, services_started=0, dummy_children_started=0,
        original_jobs_changed=False, qualification_passed=False, runtimes={})
    for name, python in RUNTIMES.items():
        command = ['taskset', '-c', '2', python, '-B', '-W', 'error::ResourceWarning', '-m', 'unittest', '-v', *SELECTED]
        log = OUT/f'final-{name}.txt'
        runtime_start = time.monotonic()
        with log.open('wb') as stream:
            result = subprocess.run(command, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL, close_fds=True, timeout=max(.1, 30-(time.monotonic()-start)))
        evidence['runtimes'][name] = dict(command_argv=command, exit_code=result.returncode,
            wall_seconds=time.monotonic()-runtime_start, log_sha256=sha256(log.read_bytes()).hexdigest())
        if result.returncode:
            break
    evidence['wall_seconds'] = time.monotonic()-start
    evidence['finished_utc'] = datetime.now(timezone.utc).isoformat()
    (OUT/'pure-tests.json').write_text(json.dumps(evidence, sort_keys=True, indent=2)+'\n')
    assert len(evidence['runtimes']) == 3 and all(item['exit_code'] == 0 for item in evidence['runtimes'].values())
    print(json.dumps(evidence))


if __name__ == '__main__':
    main()
