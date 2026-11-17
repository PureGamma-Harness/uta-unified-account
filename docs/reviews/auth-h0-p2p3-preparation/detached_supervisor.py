"""One-shot P2/P3 launcher preparation. Starting requires separate root GO.

The long-lived supervisor has no exec-server stdin/stdout/stderr pipe. Only its
own new Popen child and a fully bound P3 grandchild may be signalled by pidfd.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import stat
import subprocess
import sys
import time

SOURCE_REF = '912f2a4e5ed74f7a3fbf892ff0172e4eacc9c45a'
RUNTIME_REF = '5750e12d60dbf7f8414b4e837e076a60c93a23bc'
FLOOR = 17448304640
BUNDLE = {
    'tests/auth_h0_p2p3_independent/support.py': '5498be6b04d32250128c2f1edebae339180dc99b061b84eff99c3fb01e497152',
    'tests/auth_h0_p2p3_independent/default_handles_probe.py': 'f2ecd948ab3b5b261282dfa1650beac60c1c610da6783c65669cd79ef133b1e1',
    'tests/auth_h0_p2p3_independent/reply_loss_probe.py': '7fd73d8a77173528f21dd94604e50437f4e91dfce4a4ab744b617cf4bf9a668d',
}
SUBJECTS = {'P2': ('default_handles_probe.py', 7, 32 * 1024**2),
            'P3': ('reply_loss_probe.py', 3, 16 * 1024**2)}


def utc():
    return datetime.now(timezone.utc).isoformat()


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())


def identity(pid):
    proc = Path('/proc') / str(pid)
    raw = (proc / 'stat').read_text()
    fields = raw[raw.rfind(')') + 2:].split()
    return {'pid': pid, 'birth': fields[19], 'state': fields[0], 'ppid': int(fields[1]),
            'uid': proc.stat().st_uid, 'boot': Path('/proc/sys/kernel/random/boot_id').read_text().strip()}


def same(expected, actual):
    return all(expected[key] == actual[key] for key in ('pid', 'birth', 'uid', 'boot'))


def validate(args):
    assert all(path.is_absolute() for path in (args.source, args.bundle_root, args.outer))
    for name, digest in BUNDLE.items():
        assert sha(args.bundle_root / name) == digest
    assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=args.source, text=True).strip() == SOURCE_REF
    assert subprocess.check_output(['git', 'status', '--porcelain'], cwd=args.source, text=True) == ''
    names = subprocess.check_output(['git', 'ls-tree', '-r', '--name-only', RUNTIME_REF,
                                     '--', 'uta'], cwd=args.source, text=True).splitlines()
    assert len(names) == 64
    hashes = {}
    for name in names:
        raw = (args.source / name).read_bytes()
        assert raw == subprocess.check_output(['git', 'show', RUNTIME_REF + ':' + name], cwd=args.source)
        hashes[name] = hashlib.sha256(raw).hexdigest()
    return hashes


def start(args):
    os.sched_setaffinity(0, {4})
    validate(args)
    # pidfd is required for actual execution; never degrade to PID/group search.
    assert hasattr(os, 'pidfd_open') and hasattr(signal, 'pidfd_send_signal')
    fd = os.pidfd_open(os.getpid())
    os.close(fd)
    assert not args.outer.exists() and not args.outer.is_symlink()
    parent = args.outer.parent.stat()
    assert parent.st_uid == os.geteuid() and not stat.S_IMODE(parent.st_mode) & 0o077
    free = shutil.disk_usage('/workspace').free
    assert free >= FLOOR + SUBJECTS[args.kind][2]
    args.outer.mkdir(mode=0o700)
    command = [sys.executable, '-I', '-B', str(Path(__file__).resolve()), 'supervise',
               '--kind', args.kind, '--source', str(args.source), '--bundle-root', str(args.bundle_root),
               '--outer', str(args.outer)]
    record = {'kind': args.kind, 'launch_prepared_at': utc(),
              'command': command, 'source_commit': SOURCE_REF, 'runtime_commit': RUNTIME_REF,
              'bundle_sha256': BUNDLE, 'supervisor_sha256': sha(Path(__file__)),
              'free_bytes_before_start': free, 'floor_plus_private_budget_required': FLOOR + SUBJECTS[args.kind][2],
              'streams': 'exclusive private files; stdin DEVNULL; no exec-server pipe',
              'start_new_session': True, 'production_approved': False}
    # Persist the exclusive one-shot attempt before launch. If a later record
    # fails, this directory/intent remains an UNKNOWN attempt, never retry GO.
    save(args.outer / 'launch-intent.json', {'status': 'INTENT_NOT_START_OUTCOME',
         'kind': args.kind, 'command': command, 'created_at': record['launch_prepared_at'],
         'supervisor_sha256': record['supervisor_sha256'], 'never_resubmit_this_outer': True})
    with (args.outer / 'private-supervisor-stdout.txt').open('xb') as out, \
         (args.outer / 'private-supervisor-stderr.txt').open('xb') as err:
        child = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=out, stderr=err,
                                 cwd=Path(__file__).resolve().parent, start_new_session=True, close_fds=True)
        outcome = record_started(args.outer, child, record)
    print(json.dumps(outcome), flush=True)
    return 2 if outcome['primary_error'] else 0


def record_started(outer, child, record):
    """Popen already returned: metadata/record failure must not mean no start."""
    owned, primary = None, None
    try:
        owned = identity(child.pid)
    except BaseException as error:
        primary = {'phase': 'post_Popen_identity', 'type': type(error).__name__}
    record.update({'actual_Popen_supervisor': owned, 'actual_Popen_pid': child.pid,
                   'Popen_returned': True, 'primary_error': primary})
    try:
        save(outer / 'start-record.json', record)
    except BaseException as error:
        record['record_save_error'] = {'phase': 'post_Popen_start_record', 'type': type(error).__name__}
        primary = primary or record['record_save_error']
        record['primary_error'] = primary
        try:
            save(outer / 'start-record-unknown.json', record)
        except BaseException:
            # The pre-launch exclusive intent and private streams still exist;
            # supervisor-owner may independently prove the actual start.
            pass
    return {'status': 'START_OCCURRED_RECORD_UNKNOWN' if primary else 'STARTED_ONCE',
            'kind': record['kind'], 'supervisor': owned, 'actual_Popen_pid': child.pid,
            'Popen_returned': True, 'primary_error': primary, 'never_resubmit': True,
            'outer': str(outer), 'supervisor_sha256': record['supervisor_sha256']}


def bind_direct_child(child, state):
    # No wait/poll has occurred since this direct Popen child was returned.
    # Its PID cannot be reused until this sole parent reaps it. Bind first,
    # before fallible /proc metadata or recording, and retain the fd in state
    # even if a later step raises. Never use this rule for arbitrary old PIDs.
    state['pidfd'] = os.pidfd_open(child.pid)
    state['owned'] = identity(child.pid)
    assert same(state['owned'], identity(child.pid)) and state['owned']['ppid'] == os.getpid()


def cleanup_direct_child(child, pidfd):
    result = {'forced': False, 'wait_reaped': False, 'pidfd_bound': pidfd is not None}
    try:
        try:
            result['exit_code'] = child.wait(timeout=0)
            result['wait_reaped'] = True
            return result
        except subprocess.TimeoutExpired:
            pass
        if pidfd is None:
            result['reason'] = 'UNKNOWN_NO_PIDFD_NO_PID_OR_GROUP_FALLBACK'
            return result
        result['forced'] = True
        try:
            signal.pidfd_send_signal(pidfd, signal.SIGKILL)
        except ProcessLookupError:
            pass
        result['exit_code'] = child.wait(timeout=.75)
        result['wait_reaped'] = True
    except BaseException as error:
        result['cleanup_error'] = type(error).__name__
    return result


def stop_bound_grandchild(args, subject):
    """Best bounded cleanup only for P3's recorded actual own worker.

    This supervisor is not the worker's parent and makes no worker-reap claim.
    If binding is unavailable, do not inspect or signal unrelated processes.
    """
    result = {'attempted': False, 'worker_reaped_by_supervisor': False}
    record = args.outer / 'cases' / 'private-worker-actual-Popen.json'
    if args.kind != 'P3' or not record.exists():
        result['reason'] = 'no_recorded_P3_worker_binding'
        return result
    pidfd = None
    try:
        recorded = json.loads(record.read_bytes())
        if not same(subject, recorded['parent_identity']):
            raise ValueError('worker parent differs from actual Popen subject')
        worker = recorded['identity']
        current = identity(worker['pid'])
        if not same(worker, current) or current['ppid'] != subject['pid']:
            raise ValueError('worker is no longer the recorded direct subject child')
        pidfd = os.pidfd_open(worker['pid'])
        if not same(worker, identity(worker['pid'])):
            raise ValueError('worker identity changed before pidfd binding')
        signal.pidfd_send_signal(pidfd, signal.SIGKILL)
        result.update({'attempted': True, 'signal': 'SIGKILL', 'exact_owned_binding': worker,
                       'outcome': 'UNKNOWN_FORCED_CLEANUP', 'reap_obligation': 'subject parent only'})
    except FileNotFoundError:
        result['reason'] = 'recorded_worker_already_absent_no_signal'
    except BaseException as error:
        result['reason'] = type(error).__name__
    finally:
        if pidfd is not None:
            os.close(pidfd)
    return result


def supervise(args):
    os.sched_setaffinity(0, {4})
    begin, started = time.monotonic_ns(), utc()
    self_hash, runtime = sha(Path(__file__)), validate(args)
    owner = identity(os.getpid())
    save(args.outer / 'supervisor-owner.json', owner)
    harness = args.bundle_root / 'tests' / 'auth_h0_p2p3_independent' / SUBJECTS[args.kind][0]
    command = [sys.executable, '-I', '-B', str(harness), '--source', str(args.source),
               '--private', str(args.outer / 'cases'), '--result', str(args.outer / 'probe-result.json')]
    reason, reaped, code, grandchild, primary, cleanup = None, False, None, None, None, None
    unknown_record_error = None
    binding = {'owned': None, 'pidfd': None}
    with (args.outer / 'private-probe-stdout.txt').open('xb') as out, \
         (args.outer / 'private-probe-stderr.txt').open('xb') as err:
        child = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=out, stderr=err,
                                 start_new_session=True, close_fds=True, cwd=args.bundle_root)
        try:
            bind_direct_child(child, binding)
            save(args.outer / 'probe-actual-Popen.json', {'identity': binding['owned'], 'command': command,
                 'pidfd_bound': True, 'affinity_inherited_from_supervisor': [4]})
            try:
                # Reserve2.5s for own-child cleanup, stream fsync, hashes and result.
                code = child.wait(timeout=max(.001, 27.5 - (time.monotonic_ns() - begin) / 1e9))
                reaped = True
            except subprocess.TimeoutExpired:
                reason = 'WATCHDOG_27_5_SECONDS_WITHIN_HARD30_BUDGET'
                grandchild = stop_bound_grandchild(args, binding['owned'])
                cleanup = cleanup_direct_child(child, binding['pidfd'])
                code, reaped = cleanup.get('exit_code'), cleanup['wait_reaped']
        except BaseException as error:
            primary = {'phase': 'post_Popen_bind_record_or_control', 'type': type(error).__name__}
            reason = 'SUPERVISOR_BIND_OR_CONTROL_' + type(error).__name__
            if binding['owned'] is not None:
                grandchild = stop_bound_grandchild(args, binding['owned'])
            cleanup = cleanup_direct_child(child, binding['pidfd'])
            code, reaped = cleanup.get('exit_code'), cleanup['wait_reaped']
            try:
                save(args.outer / 'probe-control-unknown.json', {'status': 'UNKNOWN',
                     'actual_Popen_pid': child.pid, 'metadata': binding['owned'],
                     'pidfd_bound': binding['pidfd'] is not None, 'primary_error': primary,
                     'cleanup': cleanup, 'raw_final_only_if_wait_reaped': reaped})
            except BaseException as record_error:
                unknown_record_error = type(record_error).__name__
        finally:
            if binding['pidfd'] is not None:
                os.close(binding['pidfd'])
        out.flush()
        os.fsync(out.fileno())
        err.flush()
        os.fsync(err.fileno())
    streams = {name: {'bytes': (args.outer / name).stat().st_size, 'sha256': sha(args.outer / name)}
               for name in ('private-probe-stdout.txt', 'private-probe-stderr.txt')}
    report = args.outer / 'probe-result.json'
    probe = json.loads(report.read_bytes()) if report.exists() else None
    same_inputs = all(sha(args.source / name) == digest for name, digest in runtime.items()) \
        and all(sha(args.bundle_root / name) == digest for name, digest in BUNDLE.items()) \
        and sha(Path(__file__)) == self_hash
    passed = reason is None and reaped and code == 0 and same_inputs and probe is not None \
        and probe.get('status') == 'PASS' and probe.get('source_unchanged') is True \
        and probe.get('completed_step_count') == SUBJECTS[args.kind][1]
    result = {'kind': args.kind, 'started_at': started, 'raw_closed_fsynced_hashed_at': utc(),
              'source_commit': SOURCE_REF, 'runtime_commit': RUNTIME_REF, 'source_validation_scope': '64 runtime only',
              'bundle_sha256': BUNDLE, 'supervisor_sha256': self_hash, 'supervisor_identity': owner,
              'subject_actual_Popen': binding['owned'], 'subject_actual_Popen_pid': child.pid,
              'subject_pidfd_bound': binding['pidfd'] is not None,
              'primary_control_error': primary, 'owned_subject_cleanup': cleanup,
              'control_unknown_record_error': unknown_record_error,
              'subject_exit_code': code, 'subject_wait_reaped': reaped,
              'watchdog_or_control_reason': reason, 'grandchild_forced_cleanup': grandchild,
              'private_raw_streams': streams, 'source_and_harness_unchanged': same_inputs,
              'raw_hashes_final_only_if_subject_reaped': reaped,
              'probe_result_sha256': sha(report) if report.exists() else None,
              'probe_status': probe.get('status') if probe else None,
              'probe_completed_steps': probe.get('completed_step_count') if probe else None,
              'subject_passed_before_final_result_serialization': passed, 'production_approved': False}
    save(args.outer / 'supervisor-result.json', result)
    elapsed = time.monotonic_ns() - begin
    completion = {'completed_at': utc(), 'elapsed_ns_after_result_fsync': elapsed,
                  'raw_close_fsync_hash_and_result_fsync_precede_clock': True,
                  'completion_record_serialization_follows_clock': True,
                  'within30seconds_at_recorded_clock': elapsed <= 30 * 10**9,
                  'supervisor_result_sha256': sha(args.outer / 'supervisor-result.json'),
                  'accepted_scoped_probe': passed and elapsed <= 30 * 10**9,
                  'supervisor_not_reaped_by_short_starter': True, 'production_approved': False}
    save(args.outer / 'completion.json', completion)
    return 0 if completion['accepted_scoped_probe'] else 2


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser()
    parser.add_argument('operation', choices=('start', 'supervise', 'status'))
    parser.add_argument('--kind', choices=tuple(SUBJECTS), required=True)
    for name in ('source', 'bundle-root', 'outer'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    if args.operation == 'start':
        return start(args)
    if args.operation == 'supervise':
        return supervise(args)
    # Safe metadata only; never dump private AuthDB/credentials/requests/raw.
    value = {}
    for name in ('launch-intent.json', 'start-record.json', 'start-record-unknown.json',
                 'supervisor-owner.json', 'probe-actual-Popen.json',
                 'probe-control-unknown.json',
                 'supervisor-result.json', 'completion.json'):
        path = args.outer / name
        value[name] = json.loads(path.read_bytes()) if path.exists() else None
    print(json.dumps(value, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
