"""Run one unchanged test under a real self-owned process pause, not a fake clock."""
from contextlib import contextmanager
from pathlib import Path
import hashlib
import json
import os
import signal
import subprocess
import sys
import time
import unittest
from unittest.mock import patch


def main():
    root, output = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve()
    output.mkdir(exist_ok=True)
    os.chdir(root)
    sys.path.insert(0, str(root))
    os.sched_setaffinity(0, {min(os.sched_getaffinity(0))})
    from tests import test_owned_startup as fixture
    from tests.test_startup_write_contention import StartupWriteContentionTests, describe_error
    from uta.startup import _OwnedStartup
    from uta.storage import Database
    from uta.writer_fence import WriterFence
    phases = dict(construct_entered=False, construct_returned=False, producer_entered=False,
                  pause_seconds=.55, initial_acquire_ttl=None, keeper_failures=[])
    originals = fixture.OwnedStartupTests.construct, Database.inbox_transaction, WriterFence.acquire, _OwnedStartup._fail
    helper_code = ("import os,signal,sys,time; target=os.getppid(); print('ready',flush=True); "
                   "sys.stdin.readline(); time.sleep(.55); "
                   "os.kill(target,signal.SIGCONT) if os.getppid()==target else None")
    def construct(case, scope):
        phases['construct_entered'] = True
        helper = subprocess.Popen([sys.executable, '-u', '-c', helper_code],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            if helper.stdout.readline().strip() != 'ready':
                raise RuntimeError('pause helper did not become ready')
            helper.stdin.write('pause\n')
            helper.stdin.flush()
            begin = time.monotonic_ns()
            os.kill(os.getpid(), signal.SIGSTOP)
            phases['observed_pause_ns'] = time.monotonic_ns() - begin
            helper.communicate(timeout=2)
            if helper.returncode:
                raise RuntimeError('pause helper failed')
        finally:
            if helper.poll() is None:
                helper.kill()
                helper.communicate(timeout=2)
        result = originals[0](case, scope)
        phases['construct_returned'] = True
        return result
    @contextmanager
    def inbox(database):
        with originals[1](database) as connection:
            phases['producer_entered'] = connection.in_transaction
            yield connection
    def acquire(fence, nonce, ttl):
        result = originals[2](fence, nonce, ttl)
        phases['initial_acquire_ttl'] = ttl
        return result
    def failure(scope, error):
        originals[3](scope, error)
        phases['keeper_failures'].append(describe_error(error))
    code_sha = {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in sorted((root/'uta').glob('*.py'))}
    name = 'test_uncoordinated_producer_writer_busy_is_still_technical_poison'
    log = output/'unittest.txt'
    with log.open('w') as stream, patch.object(fixture.OwnedStartupTests, 'construct', construct), \
         patch.object(Database, 'inbox_transaction', inbox), patch.object(WriterFence, 'acquire', acquire), \
         patch.object(_OwnedStartup, '_fail', failure):
        result = unittest.TextTestRunner(stream=stream, verbosity=2).run(unittest.TestSuite([StartupWriteContentionTests(name)]))
    record = dict(commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        runtime_sha256=code_sha, selected_test_sha256={str(p):hashlib.sha256(p.read_bytes()).hexdigest()
            for p in (Path('tests/test_owned_startup.py'),Path('tests/test_startup_write_contention.py'))},
        phases=phases, tests=result.testsRun, errors=len(result.errors), failures=len(result.failures),
        passed=result.wasSuccessful(), source_pause='real SIGSTOP/SIGCONT of this driver only',
        python=sys.version, script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        log_sha256=hashlib.sha256(log.read_bytes()).hexdigest())
    (output/'result.json').write_text(json.dumps(record, indent=2)+'\n')
    print(json.dumps(dict(passed=record['passed'],errors=record['errors'],failures=record['failures'],phases=phases)))
    return not result.wasSuccessful()


if __name__ == '__main__':
    raise SystemExit(main())
