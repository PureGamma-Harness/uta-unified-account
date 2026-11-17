"""Pure mocked dispatch vectors: no database, signals, /proc, or child process."""
import json
import signal
from unittest.mock import patch
from tests.test_durable_faults import undo_owned_test_stop

IDENTITY = {'pid': 991, 'start_ticks': 71, 'boot_id': 'synthetic', 'uid': 1000}
BASE_LEASE = {'active': True, 'owner_pid': 991, 'generation': 4}

class Poll:
    def __init__(self, exited): self.exited = exited
    def register(self, *args): pass
    def poll(self, timeout): return [(321, 1)] if self.exited else []

def vector(name, *, known=BASE_LEASE, cleanup=False, current=None, exited=False,
           expect=None, action=None, signal_error=None):
    observation = {}
    expected_identity = dict(IDENTITY)
    current_identity = dict(IDENTITY if current is None else current)
    with patch('select.poll', return_value=Poll(exited)), \
         patch('uta.durable_process._process_identity', return_value=current_identity) as identity_read, \
         patch('signal.pidfd_send_signal', side_effect=signal_error) as send, \
         patch('uta.writer_fence.WriterFence.status', side_effect=AssertionError('native lease read forbidden')) as status:
        try:
            result = undo_owned_test_stop(991, 321, expected_identity, observation,
                       reason='independent_pure_vector', known_lease=known,
                       expected_generation=4, cleanup=cleanup)
        except AssertionError:
            assert expect == 'AssertionError', name
            result = 'AssertionError'
        else:
            assert result is expect, (name, result, expect)
        status.assert_not_called()
        if action is None:
            send.assert_not_called()
        else:
            send.assert_called_once_with(321, action)
        assert observation['injection_undos'][0]['lease_observed'] is False
        assert observation['injection_undos'][0]['financial_authority_granted'] is False
        if action == signal.SIGKILL:
            assert observation['cleanup_forced_kill'] is True
        if exited:
            identity_read.assert_not_called()
    return {'name': name, 'passed': True, 'result': result,
            'signal_mock_only': None if action is None else int(action)}

rows = [
 vector('cached_same_owner_active', expect=True, action=signal.SIGCONT),
 vector('unknown_undo_grants_no_authority', known=None, expect=True, action=signal.SIGCONT),
 vector('known_inactive_no_resume', known={**BASE_LEASE, 'active': False}, expect='AssertionError'),
 vector('known_inactive_cleanup_records_forced_kill', known={**BASE_LEASE, 'active': False}, cleanup=True,
        expect=False, action=signal.SIGKILL),
 vector('known_other_owner_no_resume', known={**BASE_LEASE, 'owner_pid': 992}, expect='AssertionError'),
 vector('known_other_generation_no_resume', known={**BASE_LEASE, 'generation': 5}, expect='AssertionError'),
 vector('different_birth_no_signal', current={**IDENTITY, 'start_ticks': 72}, expect='AssertionError'),
 vector('different_boot_no_signal', current={**IDENTITY, 'boot_id': 'other'}, expect='AssertionError'),
 vector('different_uid_no_signal', current={**IDENTITY, 'uid': 1001}, expect='AssertionError'),
 vector('already_exited_no_signal', exited=True, expect=False),
 vector('process_exits_during_undo', expect=False, action=signal.SIGCONT, signal_error=ProcessLookupError()),
]
print(json.dumps({'scope': 'independent pure mocked control only', 'rows': rows,
                  'passed': len(rows) == 11 and all(row['passed'] for row in rows),
                  'native_sql_executed': False, 'native_signal_executed': False,
                  'production_approved': False}, indent=2))
