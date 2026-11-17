"""Bounded, failure-only test evidence. No source reads, SQL, signals or threads."""
import json
import math
import sys
import threading
import time

MAX_BYTES = 32768
PREFIX = 'UTA_EXPIRED_GATE_FAILURE_DIAGNOSTIC '
_FILES = {name: label for name, label in (
    ('tests/test_durable_faults.py', 'tests.test_durable_faults'),
    ('tests/expired_gate_failure_evidence.py', 'tests.expired_gate_failure_evidence'),
    ('uta/durable_process.py', 'uta.durable_process'), ('uta/writer_fence.py', 'uta.writer_fence'),
    ('uta/storage.py', 'uta.storage'), ('uta/sharding.py', 'uta.sharding'),
    ('multiprocessing/connection.py', 'stdlib.multiprocessing.connection'),
    ('multiprocessing/process.py', 'stdlib.multiprocessing.process'),
    ('threading.py', 'stdlib.threading'), ('contextlib.py', 'stdlib.contextlib'),
    ('unittest/case.py', 'stdlib.unittest.case'))}
_FUNCTIONS = frozenset(('publish', 'lease', '_supervise', '_spawn', '_record_process',
    '_load', 'status', 'read_transaction', 'transaction', '__enter__', '__exit__',
    '_verify_control_schema', '_verify_data_guards', '_verify_router', '_check',
    '_private_file', '_check_identity', '_connect', 'connect', 'execute', '_execute',
    'recv', '_recv', '_recv_bytes', 'poll', '_poll', 'read', 'write', 'wait',
    '_wait_for_tstate_lock', 'acquire', 'release', 'join', 'is_alive', '_lock',
    'publish_market', '_receipts', '_state', '_write_state', 'start', 'run',
    '_callTestMethod', '_callSetUp', '_callTearDown', 'testPartExecutor',
    'build_failure_diagnostic', 'emit_expired_gate_failure', '_threads', '_frames',
    'test_expired_sigstopped_shared_gate_owner_is_killed_so_publication_can_recover'))
_TYPES = frozenset(('AssertionError', 'OperationalError', 'DatabaseError', 'IntegrityError',
    'WriterFenceError', 'ServiceError', 'StorageError', 'RuntimeError', 'TimeoutError',
    'ValueError', 'TypeError', 'OSError', 'EOFError', 'ProcessLookupError',
    'FileNotFoundError', 'PermissionError', 'BrokenPipeError', 'KeyboardInterrupt'))
_CODES = frozenset(('router_busy', 'router_halted', 'lease_busy', 'lease_expired',
    'lease_lost', 'writer_fenced', 'clock_regressed', 'boot_changed', 'shard_unavailable',
    'shard_identity_conflict', 'ownership_recovery_pending', 'supervisor_busy',
    'managed_authority_conflict', 'orphan_recovery_pending'))
_TIMES = ('fixture_lease_seconds', 'capture_horizon_seconds', 'recovery_horizon_seconds',
    'api_phase_timeout_seconds', 'publication_lifecycle_watchdog_seconds', 'captured_at',
    'publication_started_at', 'publication_called_api_at', 'publication_finished_at',
    'publication_first_ex_entered_at', 'old_pidfd_exit_observed_at', 'new_generation_observed_at')
_LEASES = ('captured_lease', 'unexpired_control_lease', 'publication_entry_lease',
           'publication_thread_entry_lease', 'new_lease')
_LEASE_NUMBERS = ('owner_pid', 'generation', 'expires_ns', 'now_ns')


def _number(value, drops):
    if value is None or (type(value) is int and -(2**63) <= value < 2**63):
        return value
    if type(value) is float and math.isfinite(value) and abs(value) < 2**63:
        return value
    drops['values'] += 1
    return None


def _project(value, numbers, flags, drops, known=()):
    if type(value) is not dict:
        drops['values'] += 1
        return {}
    result = {key: _number(value[key], drops) for key in numbers if key in value}
    for key in flags:
        if key in value:
            result[key] = value[key] if type(value[key]) is bool else None
            drops['values'] += type(value[key]) is not bool
    drops['fields'] += len(value) - sum(key in value for key in (*numbers, *flags, *known))
    return result


def _frames(frame, drops, *, traceback=False, limit=20):
    result = []
    while frame is not None and len(result) < limit:
        actual = frame.tb_frame if traceback else frame
        code = actual.f_code
        label = next((label for suffix, label in _FILES.items()
                      if code.co_filename == suffix or code.co_filename.endswith('/' + suffix)), '<unlisted>')
        name = code.co_name if label != '<unlisted>' and code.co_name in _FUNCTIONS else '<unlisted>'
        result.append({'file': label, 'function': name,
                       'line': frame.tb_lineno if traceback else actual.f_lineno})
        frame = frame.tb_next if traceback else actual.f_back
    if frame is not None:
        drops['frames_at_least'] += 1
    return result


def _exception(error, drops):
    chain, seen = [], set()
    while isinstance(error, BaseException) and id(error) not in seen and len(chain) < 2:
        seen.add(id(error))
        name = type(error).__name__
        item = {'type': name if name in _TYPES else '<unlisted>',
                'frames': _frames(BaseException.__getattribute__(error, '__traceback__'), drops,
                                  traceback=True, limit=12)}
        attrs = BaseException.__getattribute__(error, '__dict__')
        for key in ('code', 'sqlite_errorcode'):
            if key in attrs:
                value = attrs[key]
                if type(value) is int and 0 <= value < 2**31:
                    item[key] = value
                elif key == 'code' and type(value) is str and value in _CODES:
                    item[key] = value
                else:
                    drops['values'] += 1
        chain.append(item)
        error = (BaseException.__getattribute__(error, '__cause__') or
                 (None if BaseException.__getattribute__(error, '__suppress_context__') else
                  BaseException.__getattribute__(error, '__context__')))
    if error is not None:
        drops['chain_links_at_least'] += 1
    return chain


def _observation(value, drops):
    result = _project(value, _TIMES, ('cleanup_forced_kill',), drops,
                      (*_LEASES, 'selected_binding', 'lease_reads', 'capture_attempts', 'injection_undos', 'cleanup_errors'))
    if type(value) is not dict:
        return result
    for key in _LEASES:
        if key in value:
            result[key] = _project(value[key], _LEASE_NUMBERS, ('active',), drops)
    if 'selected_binding' in value:
        result['selected_binding'] = _project(value['selected_binding'], ('pid', 'start_ticks', 'uid'), (), drops)
    reads = value.get('lease_reads')
    if type(reads) is list:
        result['lease_reads_count'] = len(reads)
        result['lease_reads_tail'] = []
        drops['items'] += max(0, len(reads) - 8)
        for row in reads[-8:]:
            safe = _project(row, (), ('observed',), drops, ('value', 'error_type'))
            if type(row) is dict and 'value' in row:
                safe['value'] = _project(row['value'], _LEASE_NUMBERS, ('active',), drops)
            if type(row) is dict and 'error_type' in row:
                safe['error_type'] = row['error_type'] if type(row['error_type']) is str and row['error_type'] in _TYPES else '<unlisted>'
            result['lease_reads_tail'].append(safe)
    for key in ('capture_attempts', 'injection_undos', 'cleanup_errors'):
        if type(value.get(key)) is list:
            result[key + '_count'] = len(value[key])
    attempts = value.get('capture_attempts')
    if type(attempts) is list and attempts and type(attempts[-1]) is dict:
        last = attempts[-1]
        safe = _project(last, ('at', 'stop_sent_at'), (), drops,
                        ('candidate', 'retained_after_stop', 'writer_availability_probe'))
        for key in ('candidate', 'retained_after_stop'):
            if type(last.get(key)) is list:
                safe[key + '_count'] = len(last[key])
        if 'writer_availability_probe' in last:
            safe['writer_availability_probe'] = _project(last['writer_availability_probe'], ('native_errorcode',), ('available',), drops)
        result['last_capture'] = safe
    return result


def _threads(router, publisher, drops):
    fields = object.__getattribute__(router, '__dict__') if router is not None else {}
    monitor, stop = fields.get('_monitor'), fields.get('_stop')
    frames = sys._current_frames()
    result = {}
    for role, thread in (('main', threading.main_thread()), ('monitor', monitor), ('publisher', publisher)):
        if not isinstance(thread, threading.Thread):
            result[role] = {'alive': None, 'frames': []}
            continue
        alive = threading.Thread.is_alive(thread)
        if type(alive) is not bool:
            alive = None
            drops['values'] += 1
        result[role] = {'alive': alive, 'frames': _frames(frames.get(thread.ident), drops)}
    stopped = stop.is_set() if type(stop) is threading.Event else None
    if stopped is not None and type(stopped) is not bool:
        stopped = None
        drops['values'] += 1
    result['monitor_stop'] = stopped
    return result


def build_failure_diagnostic(observation, publisher_errors, primary_error, router, publisher):
    drops = {key: 0 for key in ('fields', 'values', 'items', 'frames_at_least', 'chain_links_at_least', 'payload_items')}
    errors = publisher_errors if type(publisher_errors) is list else []
    drops['items'] += max(0, len(errors) - 8)
    clocks = {'monotonic_ns': time.monotonic_ns(),
              'boottime_ns': time.clock_gettime_ns(time.CLOCK_BOOTTIME), 'utc_ns': time.time_ns()}
    for key, value in clocks.items():
        if type(value) is not int or not 0 <= value < 2**63:
            clocks[key] = None
            drops['values'] += 1
    return {'event': 'uta.expired_gate_failure.v1', 'phase': 'before_original_cleanup',
            **clocks, 'observation': _observation(observation, drops),
            'primary': _exception(primary_error, drops),
            'publisher_errors': [_exception(error, drops) for error in errors[:8]],
            'threads': _threads(router, publisher, drops), 'drop_counts': drops,
            'truncated': False, 'max_bytes': MAX_BYTES}


def _render(payload):
    while True:
        text = PREFIX + json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False) + '\n'
        if len(text.encode('ascii')) <= MAX_BYTES:
            return text
        payload['truncated'] = True
        payload['drop_counts']['payload_items'] += 1
        if payload['publisher_errors']:
            payload['publisher_errors'].pop()
        elif any(row['frames'] for key, row in payload['threads'].items() if type(row) is dict):
            max((row['frames'] for row in payload['threads'].values() if type(row) is dict), key=len).pop()
        elif payload['observation'].get('lease_reads_tail'):
            payload['observation']['lease_reads_tail'].pop(0)
        elif payload['primary']:
            payload['primary'].pop()
        else:
            return PREFIX + '{"event":"uta.expired_gate_failure.v1","truncated":true,"collector_failed":true}\n'


def emit_expired_gate_failure(observation, publisher_errors, primary_error, router, publisher, *, stream=None):
    """One bounded best-effort write. Its errors never replace the test failure."""
    try:
        payload = build_failure_diagnostic(observation, publisher_errors, primary_error, router, publisher)
        payload['truncated'] = any(payload['drop_counts'].values())
        text = _render(payload)
    except BaseException:
        text = PREFIX + '{"event":"uta.expired_gate_failure.v1","collector_failed":true,"truncated":true}\n'
    try:
        written = (sys.stderr if stream is None else stream).write(text)
        return type(written) is int and written == len(text)
    except BaseException:
        return False
