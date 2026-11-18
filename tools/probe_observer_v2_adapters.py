"""Prepared small synthetic filesystem/pipe probe. No run without explicit GO.

Default invocation prints a plan only. Execution requires a fresh allowlisted
output directory; never imports an observer/controller module or opens SQL.
"""
import argparse
import ast
import errno
from copy import deepcopy
from hashlib import sha256
import json
import os
from pathlib import Path
from queue import Empty, Queue
import stat
import subprocess
import sys
from threading import Event, Thread
import time
import traceback

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools import managed_observer_report as codec, managed_observer_transport as transport
from tools.managed_observer_coverage import Coverage
from tools.managed_output_budget import measured_output_bytes

ADAPTER_PARENT = Path('/workspace/uta-observer-v2-adapter-runs')
PLAN = {'observer': {'blocks': 1, 'independent_finance_golden_required_each_1800_second_block': 1,
    'technical_read_unknown_budget': 3, 'maximum_consecutive_technical_read_unknown': 2,
    'interval_seconds': 60}, 'producer': {'duration_seconds': 1800}}
BUDGET = {'scope': 'PREPARATION_ONLY_NOT_AUTHORIZED', 'frames': 4, 'commands_per_frame': 3,
    'max_pipe_bytes': 32768, 'max_dependency_bytes': 65536, 'max_output_bytes': 131072,
    'max_data_child_stderr_bytes': 49152,
    'max_new_threads': 2, 'max_new_child_processes': 1, 'proposed_CPU': 1,
    'proposed_outer_KILL_seconds': 10, 'data_only_emitter': 'ONE_FIXED_CHILD_ONLY',
    'actual_watch_SQL_business_native_workers_crypto_keys_network_CI': 'FORBIDDEN',
    'continuous_6h_stability_passed': False, 'production_approved': False}


def report(index):
    return {'format': 1, 'synthetic': True, 'sample_wall_ns': index, 'active_elapsed_seconds': index * 60.0,
        'logical_point': 'stable_boundary', 'active_rounds': [], 'completed_rounds': 3,
        'unresolved_steps': 0, 'unresolved_faults': 0, 'planned_faults': [], 'alerts': [],
        'final_evidence_eligible': False, 'finance': {'counts': {'uta_command_inbox': 3},
            'command_inbox': [{'sequence': n, 'command_id': 'synthetic-adapter:' + str(n),
                'state': 'SUCCEEDED', 'kind': 'SUBMIT_ORDER', 'control_lane': False,
                'attempts': 0, 'last_error_present': False, 'last_error_code': None} for n in (1, 2, 3)],
            'retry_alerts': [], 'watermark': {'format': 2, 'sha256': '0' * 64},
            'golden': {'compared': True, 'passed': True, 'errors': []}}}


def seal(path, value):
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, 'wb') as stream:
        stream.write(codec.canonical(value) + b'\n'); stream.flush(); os.fsync(stream.fileno())


def definitions(relative, names, namespace):
    tree = ast.parse((ROOT / relative).read_bytes())
    nodes = [node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.ClassDef)) and node.name in names]
    if len(nodes) != len(names): raise ValueError('explicit_source_definition_missing')
    exec(compile(ast.Module(body=nodes, type_ignores=[]), relative + '#adapter-selected', 'exec'), namespace)
    return namespace


def open_readonly_stdin():
    """Pin Linux's real null device before the write audit; no writable FD."""
    before = os.lstat('/dev/null')
    if not stat.S_ISCHR(before.st_mode) or before.st_rdev != os.makedev(1, 3):
        raise ValueError('real_linux_null_character_device_required')
    descriptor = os.open('/dev/null', os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
    try:
        after = os.fstat(descriptor)
        if (not stat.S_ISCHR(after.st_mode) or after.st_rdev != os.makedev(1, 3)
                or (after.st_dev, after.st_ino) != (before.st_dev, before.st_ino)
                or os.get_inheritable(descriptor)):
            raise ValueError('readonly_stdin_device_identity_changed')
        return descriptor
    except BaseException:
        os.close(descriptor)
        raise


def cleanup_owned_adapter(pipe, lifecycle, release, control):
    """Bounded cooperative cleanup, including an incomplete Pipes constructor.

    No process signal is permitted. A construction failure is never a scope
    pass, even when the registered Popen can be reaped successfully.
    """
    child = lifecycle['child']
    if child is not None and not release.exists():
        seal(release, {'synthetic': True, 'cleanup_release_after_failure': True})
    until, fallback = time.monotonic() + 2, {}
    try:
        while child is not None:
            threads = getattr(pipe, 'threads', ()) if pipe is not None else ()
            alive_threads = any(thread.is_alive() for thread in threads)
            child_exited = child.poll() is not None
            results = getattr(pipe, 'results', {}) if pipe is not None else {}
            fallback_complete = all(label in results or fallback.get(label, {}).get('EOF', False)
                for label in ('stdout', 'stderr'))
            if child_exited and not alive_threads and (lifecycle['constructor_complete'] or fallback_complete):
                break
            if time.monotonic() >= until:
                break
            queue = getattr(pipe, 'samples', None) if pipe is not None else None
            if queue is not None:
                for _ in range(2):
                    try: queue.get_nowait()
                    except Empty: break
            if not lifecycle['constructor_complete'] and not alive_threads:
                # No drain thread exists to unblock the child after a birth
                # binding failure. Read only its owned pipes nonblocking;
                # preserve every captured synthetic byte under the same quota.
                for label in ('stdout', 'stderr'):
                    if label in results:
                        continue  # Its actual drain thread already closed it.
                    if label not in fallback:
                        original = getattr(child, label)
                        stream = getattr(original, 'stream', original)
                        os.set_blocking(stream.fileno(), False)
                        descriptor = os.open(control / ('cleanup-fallback-' + label + '.bin'),
                            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
                        fallback[label] = {'original': original, 'stream': stream,
                            'descriptor': descriptor, 'bytes': 0, 'EOF': False}
                    channel = fallback[label]
                    if channel['EOF']:
                        continue
                    try: raw = os.read(channel['stream'].fileno(), 65536)
                    except BlockingIOError: continue
                    if not raw:
                        channel['EOF'] = True
                        continue
                    limit = BUDGET['max_pipe_bytes'] if label == 'stdout' else BUDGET['max_data_child_stderr_bytes']
                    if channel['bytes'] + len(raw) > limit:
                        raise RuntimeError('constructor_cleanup_pipe_budget_exceeded')
                    position = 0
                    while position < len(raw):
                        position += os.write(channel['descriptor'], raw[position:])
                    channel['bytes'] += len(raw)
            time.sleep(.001)
    finally:
        for channel in fallback.values():
            try: os.fsync(channel['descriptor'])
            finally:
                os.close(channel['descriptor'])
                channel['original'].close()
    threads = getattr(pipe, 'threads', ()) if pipe is not None else ()
    for thread in threads:
        if thread.ident is not None: thread.join(timeout=.1)
    cleanup = {'synthetic': True,
        'owned_child': None if child is None else {'pid': child.pid, 'birth': lifecycle['birth']},
        'child_was_registered': child is not None,
        'birth_identity_established': lifecycle['birth'] is not None,
        'Pipes_identity_binding_matches': lifecycle['identity_binding_matches'],
        'Pipes_constructor_completed': lifecycle['constructor_complete'],
        'child_exit': None if child is None else child.poll(),
        'owned_threads_alive': any(thread.is_alive() for thread in threads),
        'threads_created': len(threads),
        'constructor_fallback': {label: {'bytes': item['bytes'], 'EOF': item['EOF']}
            for label, item in fallback.items()},
        'no_process_signal_used': True, **codec.FLAGS}
    seal(control / 'cleanup.json', cleanup)
    if lifecycle['constructor_complete'] and (cleanup['child_exit'] != 0
            or cleanup['owned_threads_alive'] or cleanup['threads_created'] != 2
            or not cleanup['birth_identity_established'] or not cleanup['Pipes_identity_binding_matches']):
        raise RuntimeError('synthetic_child_or_threads_cleanup_unknown')
    if measured_output_bytes(control, control.parent / 'observer') > BUDGET['max_output_bytes']:
        raise RuntimeError('cleanup_exceeded_small_actual_output_budget')
    return cleanup


def execute(output):
    if (not output.is_absolute() or output.parent != ADAPTER_PARENT or output.name in ('', '.', '..')
            or output.exists() or ADAPTER_PARENT.is_symlink()):
        raise ValueError('fresh_direct_allowlisted_output_required')
    parent = ADAPTER_PARENT.lstat()
    if not stat.S_ISDIR(parent.st_mode) or parent.st_uid != os.geteuid() or stat.S_IMODE(parent.st_mode) != 0o700:
        raise ValueError('existing_private_owned_adapter_parent_required')
    output.mkdir(mode=0o700, exist_ok=False)
    control, observer = output / 'control', output / 'observer'
    control.mkdir(mode=0o700); observer.mkdir(mode=0o700)
    seal(control / 'intent.json', {**BUDGET, 'scope': 'EXPLICIT_SYNTHETIC_ADAPTER_EXECUTION',
        'started_wall_ns': time.time_ns(), 'source_file_sha256': sha256(Path(__file__).read_bytes()).hexdigest()})
    stdin_fd = open_readonly_stdin()
    try:
        return execute_with_stdin(output, control, observer, stdin_fd)
    finally:
        primary_error = sys.exc_info()[1]
        try:
            os.close(stdin_fd)
        except BaseException as close_error:
            if primary_error is None: raise
            try:
                seal(control / 'stdin-close-error.json', {'synthetic': True,
                    'primary_error_preserved': True, 'stdin_close_status': 'UNKNOWN',
                    'error_type': type(close_error).__name__, 'production_approved': False})
            except BaseException:
                pass


def execute_with_stdin(output, control, observer, stdin_fd):
    release = control / 'release.json'
    command = [sys.executable, '-B', str(ROOT / 'tools/emit_observer_v2_fixture.py'), '--release-marker', str(release)]
    lifecycle = {'launching': False, 'spawned': 0, 'child': None, 'birth': None,
        'constructor_complete': False, 'identity_binding_matches': False}
    def audit(event, args):
        if event == 'subprocess.Popen':
            if not lifecycle['launching'] or list(args[1]) != command:
                raise RuntimeError('only_one_exact_synthetic_emitter_allowed')
            return
        if event in {'os.fork', 'os.posix_spawn'} and lifecycle['launching']:
            return
        if event in {'sqlite3.connect', 'os.fork', 'os.posix_spawn', 'os.kill', 'os.killpg',
                     'socket.connect', 'socket.bind', 'ctypes.dlopen'}:
            raise RuntimeError('adapter_forbidden_effect:' + event)
        if event == 'open':
            path, mode, flags = args
            if isinstance(path, (str, bytes, os.PathLike)) and ((mode and any(c in mode for c in 'wax+')) or flags & (os.O_WRONLY | os.O_RDWR)):
                if not Path(path).absolute().is_relative_to(output):
                    raise RuntimeError('adapter_write_outside_new_output')
    sys.addaudithook(audit)
    class StderrEvidence:
        def __init__(self, stream, descriptor):
            self.stream, self.descriptor, self.saved = stream, descriptor, 0
        def read(self, size):
            raw = self.stream.read(size)
            permitted = min(len(raw), BUDGET['max_data_child_stderr_bytes'] - self.saved)
            position = 0
            while position < permitted:
                position += os.write(self.descriptor, raw[position:permitted])
            self.saved += permitted
            if permitted != len(raw): raise RuntimeError('data_child_stderr_budget_exceeded')
            return raw
        def close(self):
            try:
                os.fsync(self.descriptor)
            finally:
                os.close(self.descriptor); self.stream.close()
    class ChildAPI:
        PIPE, DEVNULL = subprocess.PIPE, subprocess.DEVNULL
        @staticmethod
        def Popen(argv, **kwargs):
            if list(argv) != command or lifecycle['spawned'] != 0:
                raise RuntimeError('synthetic_child_allowlist_or_count')
            if type(kwargs.get('stdin')) is not int or kwargs['stdin'] != subprocess.DEVNULL:
                raise RuntimeError('only_validated_readonly_stdin_substitution_allowed')
            lifecycle['spawned'] += 1; lifecycle['launching'] = True
            kwargs['stdin'] = stdin_fd
            kwargs['env'] = {'PATH': os.defpath, 'PYTHONDONTWRITEBYTECODE': '1', 'LC_ALL': 'C.UTF-8'}
            descriptor = None
            try:
                descriptor = os.open(control / 'emitter-stderr.txt', os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
                child = subprocess.Popen(argv, **kwargs)
                lifecycle['child'] = child  # Register immediately after actual creation.
                lifecycle['birth'] = namespace['process_identity'](child.pid)['birth']
                if lifecycle['birth'] is None:
                    raise ValueError('new_owned_child_birth_unavailable')
                child.stderr = StderrEvidence(child.stderr, descriptor)
                descriptor = None  # The bounded original-stderr wrapper now owns it.
                return child
            finally:
                lifecycle['launching'] = False
                if descriptor is not None: os.close(descriptor)
    namespace = {'os': os, 'json': json, 'Path': Path, 'sha256': sha256,
        'canonical': lambda value: codec.canonical(value).decode(), 'time': time,
        'tempfile': __import__('tempfile'), 'transport': transport, 'Empty': Empty,
        'Queue': Queue, 'Thread': Thread, 'subprocess': ChildAPI, 'errno': errno,
        'compact_reports': codec,
        'ro': type('ReadOnlyJSON', (), {'parse': staticmethod(codec.strict_json),
            'canonical': staticmethod(lambda value: codec.canonical(value).decode()), 'FLAGS': codec.FLAGS})}
    definitions('tools/managed_soak_observer.py', {'atomic_json', 'integer', 'process_identity'}, namespace)
    namespace['ro'].process_identity = staticmethod(namespace['process_identity'])
    definitions('tools/run_managed_long.py', {'append', 'Pipes', 'Timeline'}, namespace)
    store, receipts = codec.DirectoryStore(observer, max_bytes=BUDGET['max_dependency_bytes']), transport.DirectoryReceipts(observer)
    snapshots = [report(index) for index in range(1, 5)]
    frames = [transport.input_frame(value, index) for index, value in enumerate(snapshots, 1)]
    if sum(map(len, frames)) > BUDGET['max_pipe_bytes']: raise ValueError('synthetic_pipe_budget_exceeded')
    pipe = None
    coverage, compacts, batches = Coverage(PLAN), [], []
    deadline = time.monotonic() + 5
    first_live, queue_full = False, False
    try:
        # Retain the actual instance before __init__, so a partially completed
        # constructor and any registered Popen remain in the cleanup scope.
        pipe = object.__new__(namespace['Pipes'])
        namespace['Pipes'].__init__(pipe, command, ROOT, stream_samples=True, wire_input=True)
        lifecycle['constructor_complete'] = True
        lifecycle['identity_binding_matches'] = pipe.process is lifecycle['child'] and pipe.birth == lifecycle['birth']
        if not lifecycle['identity_binding_matches']:
            raise ValueError('Pipes_owned_child_identity_binding_mismatch')
        first_deadline = time.monotonic() + 1
        while pipe.samples.qsize() == 0:
            if pipe.process.poll() is not None or time.monotonic() >= first_deadline:
                raise RuntimeError('small_first_frame_not_delivered_while_child_alive')
            time.sleep(.001)
        while len(compacts) < 4:
            if time.monotonic() >= deadline: raise RuntimeError('synthetic_pipe_deadline_exceeded')
            values = list(pipe.read_samples())
            batches.append(len(values))
            if len(values) > 2: raise RuntimeError('read_batch_exceeded_two')
            for value in values:
                attempt = len(compacts) + 1
                def consume(report, **timing):
                    nonlocal first_live
                    receipt = coverage.observe(report, **timing)
                    if attempt == 1:
                        identity = namespace['process_identity'](pipe.process.pid, pipe.birth)
                        if pipe.process.poll() is not None or not identity['alive'] or 'stdout' in pipe.results or release.exists():
                            raise RuntimeError('first_classification_depended_on_EOF_or_release')
                        first_live = True
                        seal(control / 'first-frame-live.json', {'synthetic': True, 'identity': identity,
                            'classified_while_child_alive': True, 'stdout_EOF_observed': False,
                            'classified_monotonic_ns': time.monotonic_ns(),
                            'actual_stdout_reader_type': type(pipe.process.stdout).__name__,
                            'complete_first_frame_bytes': len(frames[0]), 'under_64KiB': len(frames[0]) < 65536})
                        seal(release, {'synthetic': True, 'released_after_first_classification': True})
                    return receipt
                compact = codec.consume_and_format(value, consume,
                    job_elapsed_seconds=value['active_elapsed_seconds'], sample_attempt_id=attempt,
                    report_format='compact-v2', store=store)
                transport.commit_publication(compact, attempt, receipts,
                    lambda item: namespace['append'](observer / 'timeline.jsonl', item),
                    lambda item: namespace['atomic_json'](observer / 'latest.json', item))
                compacts.append(compact)
            if len(compacts) == 1 and not queue_full:
                until = min(deadline, time.monotonic() + 1)
                while pipe.samples.qsize() != 2 and time.monotonic() < until: time.sleep(.001)
                if pipe.samples.qsize() != 2: raise RuntimeError('real_two_frame_backpressure_not_observed')
                queue_full = True
                seal(control / 'backpressure.json', {'synthetic': True, 'pipe_state': pipe.input_state(),
                    'child_exit': pipe.process.poll(), 'observed_monotonic_ns': time.monotonic_ns()})
            if measured_output_bytes(control, observer) > BUDGET['max_output_bytes']:
                raise RuntimeError('small_actual_output_budget_exceeded')
            if not values: time.sleep(.001)
        pipe.process.wait(timeout=1)
        for thread in pipe.threads: thread.join(timeout=.5)
        if (any(thread.is_alive() for thread in pipe.threads) or pipe.process.returncode != 0
                or set(pipe.results) != {'stdout', 'stderr'} or pipe.results['stderr']['bytes'] != 0):
            raise RuntimeError('owned_adapter_threads_not_clean')
        if not pipe.input_state()['frames_complete']: raise RuntimeError('framed_stream_incomplete')
        if pipe.results['stdout']['sha256'] != sha256(b''.join(frames)).hexdigest():
            raise RuntimeError('kernel_pipe_hash_changed')
        reopened = transport.DirectoryReader(observer)
        for compact, expected in zip(compacts, snapshots):
            if codec.canonical(codec.restore(compact, reopened)) != codec.canonical(expected):
                raise RuntimeError('real_dependency_reopen_changed_full_input')
        namespace['LINE_CAP'] = transport.LINE_CAP
        replay = namespace['Timeline'](observer / 'timeline.jsonl', reference_store=reopened).read()
        if codec.canonical(replay) != codec.canonical(snapshots): raise RuntimeError('real_timeline_replay_changed')
        before = measured_output_bytes(control, observer)
        reopened_writer = codec.DirectoryStore(observer, max_bytes=BUDGET['max_dependency_bytes'])
        root_identity = compacts[0]['full_reference']['root']
        reopened_writer.put(root_identity, reopened.get(root_identity))
        if measured_output_bytes(control, observer) != before:
            raise RuntimeError('reopened_idempotent_node_put_changed_output')
        duplicate = transport.commit_publication(compacts[0], 1, receipts,
            lambda _: (_ for _ in ()).throw(RuntimeError('duplicate_append')), lambda _: None)
        if not duplicate['already_existed'] or measured_output_bytes(control, observer) != before:
            raise RuntimeError('idempotent_receipt_query_changed_output')
        if len(replay) != 4 or coverage.report(240)['samples_observed'] != 4:
            raise RuntimeError('synthetic_sample_count_changed')
        negative_root = control / 'negative-observer'
        negative_root.mkdir(mode=0o700)
        limited, negative_coverage, retained = codec.DirectoryStore(negative_root, max_bytes=0), Coverage(PLAN), []
        def classified_before_quota(value, **timing):
            receipt = negative_coverage.observe(value, **timing)
            retained.append(receipt)
            return receipt
        try:
            codec.consume_and_format(snapshots[0], classified_before_quota,
                job_elapsed_seconds=60, sample_attempt_id=1, report_format='compact-v2', store=limited)
        except ValueError as error:
            if str(error) != 'dependency_store_budget_exceeded': raise
        else:
            raise RuntimeError('real_node_store_quota_not_enforced')
        if len(retained) != 1 or negative_coverage.report(60)['samples_observed'] != 1:
            raise RuntimeError('quota_failure_reclassified_or_lost_prior_receipt')
        seal(control / 'result.json', {'synthetic': True, 'checks_before_cleanup_passed': True,
            'final_adapter_pass_requires_outer_exit_zero_and_cleanup': True,
            'frames': 4, 'commands_per_frame': 3, 'batch_sizes': batches,
            'measured_control_and_observer_bytes_before_result': before,
            'pipe_state': pipe.input_state(), 'owned_threads_alive': False,
            'data_only_child': pipe.identity(), 'first_small_frame_classified_before_EOF': first_live,
            'actual_two_frame_backpressure_observed': queue_full, 'child_exit': pipe.process.returncode,
            'expected_zero_quota_rejection': True, 'negative_report_consumed_once': True,
            'watch_process_or_SQL_or_real_financial_execution': False, **codec.FLAGS})
        if measured_output_bytes(control, observer) > BUDGET['max_output_bytes']:
            raise RuntimeError('final_small_output_budget_exceeded')
        return {'synthetic': True, 'adapter_scope_passed': True, 'frames': 4, **codec.FLAGS}
    finally:
        primary_error = sys.exc_info()[1]
        try:
            cleanup_owned_adapter(pipe, lifecycle, release, control)
        except BaseException as cleanup_error:
            if primary_error is None: raise
            try:
                seal(control / 'cleanup-error.json', {'synthetic': True,
                    'primary_error_preserved': True, 'cleanup_error_type': type(cleanup_error).__name__,
                    'cleanup_status': 'UNKNOWN', **codec.FLAGS})
            except BaseException:
                pass  # Keep the original failure; never turn missing evidence into success.
        # Preserve every newly created synthetic file for first-result review.
        # No recursive delete, old-job access, process signal or automatic retry.


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute-synthetic-adapters', action='store_true')
    parser.add_argument('--new-output', type=Path)
    args = parser.parse_args()
    if not args.execute_synthetic_adapters:
        print(json.dumps(BUDGET, sort_keys=True)); return 0
    if args.new_output is None: parser.error('explicit fresh --new-output required')
    try:
        print(json.dumps(execute(args.new_output), sort_keys=True)); return 0
    except BaseException as error:
        traceback.print_exc(file=sys.stderr)
        print(json.dumps({'synthetic': True, 'adapter_scope_passed': False,
            'error_type': type(error).__name__, 'no_retry': True, **codec.FLAGS}, sort_keys=True))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
