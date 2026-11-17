"""P3 preparation: real AuthDB COMMIT-return, then owned worker self-exit73.

No SQL or process is started until guarded main is explicitly invoked. This is
after-COMMIT application reply loss, not a mid-COMMIT or power-loss simulation.
"""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import select
import signal
import subprocess
import sys
import time

spec = importlib.util.spec_from_file_location('independent_p2p3_support', Path(__file__).with_name('support.py'))
s = importlib.util.module_from_spec(spec)
spec.loader.exec_module(s)
CID = 'owned-replyloss-original'


def ready_line(stream, seconds, raw_sink):
    deadline, raw = time.monotonic() + seconds, b''
    while b'\n' not in raw:
        remaining = deadline - time.monotonic()
        if remaining <= 0 or not select.select([stream], [], [], max(0, remaining))[0]:
            raise s.TechnicalUnknown('owned readiness deadline')
        chunk = os.read(stream.fileno(), 4096 - len(raw))
        if not chunk:
            raise s.TechnicalUnknown('owned readiness EOF')
        raw_sink.write(chunk)
        raw_sink.flush()
        raw += chunk
        if len(raw) >= 4096:
            raise s.TechnicalUnknown('owned readiness exceeds bounded line')
    line, trailing = raw.split(b'\n', 1)
    if trailing:
        raise s.TechnicalUnknown('unexpected owned readiness trailing bytes')
    return json.loads(line)


def worker(args):
    # This signal affects only the newly started worker itself, never another PID.
    signal.signal(signal.SIGALRM, lambda *_: os._exit(92))
    signal.alarm(10)
    api = s.bind_source(args.source)
    descriptor = json.loads((args.private / 'fixture' / 'private-descriptor.json').read_bytes())
    issuer = api.Issuer(Path(descriptor['database']), Path(descriptor['profile']), **descriptor['scope'])
    wire = s.WireReference(Path(descriptor['profile']), args.private / 'fixture' / 'worker-private-requests')
    print(json.dumps({'event': 'READY', 'identity': s.identity(os.getpid()),
                      'source_commit': s.SOURCE_REF, 'runtime_commit': s.RUNTIME_REF}), flush=True)
    if not select.select([sys.stdin.buffer], [], [], 3)[0]:
        os._exit(92)
    # GO is exactly three bytes. EOF/partial input cannot accidentally authorize work.
    command = os.read(sys.stdin.fileno(), 4)
    if command != b'GO\n':
        os._exit(93)
    headers, request = wire.signed(CID)
    handle = issuer.capture(headers, **request)
    # Product capture documents that its normal return follows actual COMMIT.
    # This is an observation of that return, not an inferred physical commit epoch.
    observed = s.observe(issuer, handle)
    assert observed['receipt_kind'] == 'auth_first_observation'
    assert observed['found'] is True
    marker = args.private / 'private-after-commit-return.json'
    s.save(marker, {'observed_real_public_capture_return': True, 'marker_written_at': s.utc(),
                   'worker': s.identity(os.getpid()), 'source_commit': s.SOURCE_REF,
                   'runtime_commit': s.RUNTIME_REF, 'receipt_private': observed,
                   'physical_commit_time_inferred': False, 'next_action_self_exit': 73})
    directory = os.open(args.private, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)
    # Deliberately no application response / normal handle release after marker.
    os._exit(73)


def cleanup_owned(child, owned, pidfd):
    record = {'forced': False, 'signals': [], 'reaped': False, 'identity_verified': False}
    code = child.poll()
    if code is not None:
        record.update({'reaped': True, 'exit_code': child.wait(timeout=.1)})
        return record
    record['forced'] = True
    try:
        current = s.identity(child.pid)
        if pidfd is None or owned is None or not s.same_process(owned, current):
            record['reason'] = 'no_safe_owned_pidfd_binding_no_fallback'
            return record
        record['identity_verified'] = True
        for value, wait in ((signal.SIGTERM, 1), (signal.SIGKILL, 1)):
            try:
                signal.pidfd_send_signal(pidfd, value)
                record['signals'].append(value.name)
            except ProcessLookupError:
                pass
            try:
                record.update({'exit_code': child.wait(timeout=wait), 'reaped': True})
                return record
            except subprocess.TimeoutExpired:
                continue
        record['reason'] = 'own_child_reap_unknown'
    except BaseException as error:
        record['reason'] = type(error).__name__
    return record


def run(args, api):
    start, begin = s.utc(), time.monotonic_ns()
    child = None
    owned = None
    pidfd = None
    cleanup = None
    status, steps, detail = 'PASS', [], {}
    raw_out = (args.private / 'private-worker-stdout.txt').open('xb')
    try:
        if not hasattr(os, 'pidfd_open') or not hasattr(signal, 'pidfd_send_signal'):
            raise s.NotCompleted('required pidfd API unavailable; no process spawned')
        preflight = os.pidfd_open(os.getpid())
        os.close(preflight)
        fixture = s.Fixture(api, args.private / 'fixture')
        assert s.snapshot(fixture.path)['auth_credit_acceptances'] == []
        command = [sys.executable, '-I', '-B', str(Path(__file__).resolve()), '--worker',
                   '--source', str(args.source), '--private', str(args.private), '--result', str(args.result)]
        with (args.private / 'private-worker-stderr.txt').open('xb') as err:
            child = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                     stderr=err, start_new_session=True, close_fds=True,
                                     cwd=Path(__file__).resolve().parent)
            try:
                owned = s.identity(child.pid)
                pidfd = os.pidfd_open(child.pid)
                assert owned['ppid'] == os.getpid() and owned['uid'] == os.geteuid()
                s.save(args.private / 'private-worker-actual-Popen.json',
                       {'identity': owned, 'parent_identity': s.identity(os.getpid()),
                        'pidfd_bound': True, 'command': command, 'affinity_inherited': [4]})
                ready = ready_line(child.stdout, 3, raw_out)
                assert ready['event'] == 'READY' and ready['source_commit'] == s.SOURCE_REF
                assert ready['runtime_commit'] == s.RUNTIME_REF
                assert s.same_process(owned, ready['identity'])
                assert s.same_process(owned, s.identity(child.pid))
                steps.append('actual_owned_worker_ready_pidfd_bound_before_GO')
                child.stdin.write(b'GO\n')
                child.stdin.flush()
                child.stdin.close()
                code = child.wait(timeout=5)
                detail['worker_actual_exit_code'] = code
                detail['worker_wait_reaped'] = True
                if code != 73:
                    raise s.TechnicalUnknown('worker did not complete designated exit73')
                # Child has exited and was reaped: remaining pipe cannot block.
                raw_out.write(child.stdout.read(4096))
                child.stdout.close()
                marker_path = args.private / 'private-after-commit-return.json'
                if not marker_path.exists():
                    raise s.TechnicalUnknown('exit73 lacks fsynced return observation marker')
                marker = json.loads(marker_path.read_bytes())
                assert marker['observed_real_public_capture_return'] is True
                assert s.same_process(owned, marker['worker'])
                first = marker['receipt_private']
                assert all(first[name] is False for name in s.FLAGS)
                assert first['command_id'] == CID and first['receipt_kind'] == 'auth_first_observation'
                data = s.snapshot(fixture.path)
                assert len(data['auth_credit_acceptances']) == 1
                row = data['auth_credit_acceptances'][0]
                assert row['command_id'] == CID and row['payload'] == first['first_acceptance_payload_or_null']
                assert row['acceptance_id'] == first['first_acceptance_id']
                steps.append('real_commit_return_marker_fsynced_then_self_exit73_without_application_response')
            finally:
                cleanup = cleanup_owned(child, owned, pidfd)
                if child.stdin and not child.stdin.closed:
                    child.stdin.close()
                if cleanup['forced'] or not cleanup['reaped']:
                    status = 'UNKNOWN'
                err.flush()
                os.fsync(err.fileno())
        if status != 'PASS':
            raise s.TechnicalUnknown('forced cleanup cannot become PASS')
        # New public issuer to same own authority, no inherited handles or context.
        current = api.Issuer(fixture.path, fixture.profile, **fixture.scope)
        headers, request = fixture.wire.signed(CID, lookup=True, key='reader')
        observed = s.observe(current, current.lookup(headers, **request), release=True)
        assert observed['receipt_kind'] == 'auth_query_only' and observed['found'] is True
        assert observed['first_acceptance_payload_or_null'] == first['first_acceptance_payload_or_null']
        headers, request = fixture.wire.signed(CID)
        retried = s.observe(current, current.capture(headers, **request), release=True)
        assert retried['receipt_kind'] == 'auth_query_only' and retried['found'] is True
        assert retried['first_acceptance_payload_or_null'] == first['first_acceptance_payload_or_null']
        final = s.snapshot(fixture.path)
        assert final['auth_credit_acceptances'] == data['auth_credit_acceptances']
        assert len(final['auth_nonces']) == 3
        assert sum(item['outcome'] == 'FIRST_ACCEPTED' for item in final['auth_audit']) == 1
        assert sum(item['outcome'] == 'QUERY_ORIGINAL' for item in final['auth_audit']) == 2
        steps.append('new_issuer_current_read_and_sameCID_retry_query_original_without_second_acceptance')
        detail.update({'first_acceptance_count': 1, 'actual_request_count': 3,
                       'original_first_identity_unchanged': True})
    except s.NotCompleted:
        status = 'NOT_COMPLETED'
    except (s.TechnicalUnknown, subprocess.TimeoutExpired):
        status = 'UNKNOWN'
    except BaseException as error:
        known_failure = isinstance(error, AssertionError) or (
            isinstance(error, api.SigningError) and error.status != 503)
        status = 'FAIL' if known_failure else 'UNKNOWN'
        detail['first_exception_type'] = type(error).__name__
    finally:
        if child is not None and cleanup is None:
            cleanup = cleanup_owned(child, owned, pidfd)
        if cleanup is not None and (cleanup['forced'] or not cleanup['reaped']):
            status = 'UNKNOWN'
        if pidfd is not None:
            os.close(pidfd)
        if child is not None and child.stdout and not child.stdout.closed:
            # Preserve available partial readiness on UNKNOWN; never a blocking
            # read from a still-live/unreaped process, and never claim full raw.
            for _ in range(2):
                if not select.select([child.stdout], [], [], 0)[0]:
                    break
                chunk = os.read(child.stdout.fileno(), 4096)
                if not chunk:
                    break
                raw_out.write(chunk)
            child.stdout.close()
        raw_out.flush()
        os.fsync(raw_out.fileno())
        raw_out.close()
    report = s.report_base(args.source, api, start, begin)
    report.update({'probe': 'P3', 'status': status, 'completed_steps': steps,
                   'completed_step_count': len(steps), 'planned_step_count': 3,
                   'detail': detail, 'owned_worker_cleanup': cleanup,
                   'worker_raw_final_only_if_reaped': cleanup is not None and cleanup['reaped'],
                   'all_observed_authorization_flags_false': True if status == 'PASS' else None,
                   'scope': 'after-AuthDB-COMMIT-return application reply loss; auth-only originalCID query',
                   'mid_COMMIT_or_powerloss_or_financial_recovery_tested': False})
    s.save(args.result, report)
    print(json.dumps({key: value for key, value in report.items() if key != 'runtime_hashes_before'}), flush=True)
    return 0 if status == 'PASS' and len(steps) == 3 and report['source_unchanged'] else 2


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser()
    parser.add_argument('--worker', action='store_true')
    for name in ('source', 'private', 'result'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    assert all(path.is_absolute() for path in (args.source, args.private, args.result))
    if args.worker:
        return worker(args)
    assert not args.private.exists() and not args.result.exists()
    args.private.mkdir(mode=0o700)
    api = s.bind_source(args.source)
    return run(args, api)


if __name__ == '__main__':
    raise SystemExit(main())
