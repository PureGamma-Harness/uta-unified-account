"""Pure selected-function/fake-owned failure cases; no process/DB/product use."""
import argparse
import ast
import hashlib
import json
from pathlib import Path


class Namespace:
    def __init__(self, **values):
        self.__dict__.update(values)


class FakeTimeout(Exception):
    pass


class FakeChild:
    pid = 41

    def __init__(self, plan):
        self.plan, self.waits = list(plan), []

    def wait(self, *, timeout):
        self.waits.append(timeout)
        value = self.plan.pop(0)
        if isinstance(value, BaseException):
            raise value
        return value


class FakePath:
    def __truediv__(self, value):
        return value

    def __str__(self):
        return 'fake-outer-no-files'


def load_helpers(tree, *, fd_error=None, metadata_error=None, signal_error=None,
                 save_errors=()):
    calls, written, errors = [], [], list(save_errors)
    owned = {'pid': 41, 'ppid': 17, 'birth': 'fake-birth', 'uid': 23, 'boot': 'fake-boot'}

    def open_fd(pid):
        calls.append(('pidfd_open', pid))
        if fd_error:
            raise fd_error
        return 91

    def read_identity(pid):
        calls.append(('identity', pid))
        if metadata_error:
            raise metadata_error
        return dict(owned)

    def send(fd, value):
        calls.append(('pidfd_send_signal', fd, value))
        if signal_error:
            raise signal_error

    def write(path, data):
        calls.append(('save', path))
        if errors:
            error = errors.pop(0)
            if error is not None:
                raise error
        written.append((path, dict(data)))

    names = ('bind_direct_child', 'cleanup_direct_child', 'record_started', 'same')
    selected = ast.Module(body=[node for node in tree.body
                               if isinstance(node, ast.FunctionDef) and node.name in names], type_ignores=[])
    assert len(selected.body) == len(names)
    namespace = {'os': Namespace(pidfd_open=open_fd, getpid=lambda: 17),
                 'signal': Namespace(SIGKILL=9, pidfd_send_signal=send),
                 'subprocess': Namespace(TimeoutExpired=FakeTimeout),
                 'identity': read_identity, 'save': write}
    # Only these four function declarations execute, against the fakes above.
    # No supervisor imports/main/Popen/native pidfd call or file save executes.
    exec(compile(selected, '<selected-supervisor-functions-with-fakes>', 'exec'), namespace)
    return namespace, calls, written


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--supervisor', type=Path, required=True)
    parser.add_argument('--result', type=Path, required=True)
    args = parser.parse_args()
    tree = ast.parse(args.supervisor.read_bytes(), feature_version=(3, 10))
    scope = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'supervise')
    block = next(node for node in scope.body if isinstance(node, ast.With))
    assert isinstance(block.body[0], ast.Assign) and 'subprocess.Popen' in ast.unparse(block.body[0])
    assert isinstance(block.body[1], ast.Try)
    assert ast.unparse(block.body[1].body[0]).startswith('bind_direct_child(child, binding)')
    completed = []

    ns, calls, _ = load_helpers(tree)
    state = {'owned': None, 'pidfd': None}
    ns['bind_direct_child'](FakeChild([0]), state)
    assert calls[0] == ('pidfd_open', 41) and state['pidfd'] == 91 and state['owned']['pid'] == 41
    cleanup = ns['cleanup_direct_child'](FakeChild([0]), state['pidfd'])
    assert cleanup['wait_reaped'] and not cleanup['forced']
    completed.append('pidfd_bound_before_fallible_identity_no_poll_or_wait')

    ns, calls, _ = load_helpers(tree, metadata_error=PermissionError('fake'))
    state = {'owned': None, 'pidfd': None}
    try:
        ns['bind_direct_child'](FakeChild([]), state)
    except PermissionError as error:
        primary = type(error).__name__
    else:
        raise AssertionError('fake identity failure swallowed')
    cleanup = ns['cleanup_direct_child'](FakeChild([FakeTimeout(), -9]), state['pidfd'])
    assert primary == 'PermissionError' and state == {'owned': None, 'pidfd': 91}
    assert cleanup['forced'] and cleanup['wait_reaped'] and ('pidfd_send_signal', 91, 9) in calls
    completed.append('identity_failure_keeps_actual_direct_child_fd_and_primary_then_bounded_cleanup')

    ns, calls, _ = load_helpers(tree, fd_error=OSError('fake'))
    state = {'owned': None, 'pidfd': None}
    try:
        ns['bind_direct_child'](FakeChild([]), state)
    except OSError:
        pass
    cleanup = ns['cleanup_direct_child'](FakeChild([FakeTimeout()]), state['pidfd'])
    assert not cleanup['wait_reaped'] and not cleanup['forced']
    assert 'UNKNOWN' in cleanup['reason'] and not any(call[0] == 'pidfd_send_signal' for call in calls)
    completed.append('pidfd_failure_unknown_no_pid_group_or_metadata_fallback_no_finalraw')

    ns, _, _ = load_helpers(tree, signal_error=PermissionError('fake'))
    cleanup = ns['cleanup_direct_child'](FakeChild([FakeTimeout()]), 91)
    assert cleanup['cleanup_error'] == 'PermissionError' and not cleanup['wait_reaped']
    completed.append('cleanup_signal_failure_is_recorded_not_reaped')

    ns, _, _ = load_helpers(tree)
    cleanup = ns['cleanup_direct_child'](FakeChild([FakeTimeout(), FakeTimeout()]), 91)
    assert cleanup['forced'] and not cleanup['wait_reaped'] and cleanup['cleanup_error'] == 'FakeTimeout'
    completed.append('cleanup_wait_failure_keeps_unknown_and_nonfinalraw')

    base = {'kind': 'P2', 'supervisor_sha256': 'fake-source-hash'}
    ns, _, written = load_helpers(tree, metadata_error=PermissionError('fake'))
    outcome = ns['record_started'](FakePath(), FakeChild([]), dict(base))
    assert outcome['status'] == 'START_OCCURRED_RECORD_UNKNOWN' and outcome['Popen_returned']
    assert outcome['never_resubmit'] and written[0][1]['primary_error']['type'] == 'PermissionError'
    completed.append('starter_identity_failure_records_start_occurred_unknown_not_retry')

    ns, _, written = load_helpers(tree, save_errors=(OSError('fake-first'), None))
    outcome = ns['record_started'](FakePath(), FakeChild([]), dict(base))
    assert outcome['status'] == 'START_OCCURRED_RECORD_UNKNOWN' and outcome['actual_Popen_pid'] == 41
    assert written[0][0] == 'start-record-unknown.json' and written[0][1]['primary_error']['type'] == 'OSError'
    completed.append('starter_record_failure_preserves_first_error_in_exclusive_unknown_fallback')

    ns, _, written = load_helpers(tree, save_errors=(OSError('fake-first'), PermissionError('fake-second')))
    outcome = ns['record_started'](FakePath(), FakeChild([]), dict(base))
    assert outcome['status'] == 'START_OCCURRED_RECORD_UNKNOWN' and outcome['primary_error']['type'] == 'OSError'
    assert outcome['Popen_returned'] and outcome['never_resubmit'] and written == []
    completed.append('both_start_record_writes_fail_primary_kept_unknown_no_retry_without_poststart_record')
    result = {'status': 'PURE_FAKE_OWNED_CONTROL_FLOW_ONLY', 'completed_count': len(completed),
              'supervisor_sha256': hashlib.sha256(args.supervisor.read_bytes()).hexdigest(),
              'completed': completed, 'real_process_or_signal_or_SQL_or_DB_or_product_import': False,
              'P2_actual_status': 'NOT_RUN', 'P3_actual_status': 'NOT_RUN', 'production_approved': False}
    assert not args.result.exists()
    args.result.write_text(json.dumps(result, sort_keys=True, indent=2) + '\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
