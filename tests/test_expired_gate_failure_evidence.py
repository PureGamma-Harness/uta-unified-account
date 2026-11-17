"""Pure failure-evidence/privacy checks. Never import the financial testcase."""
import ast
import hashlib
import io
import json
from pathlib import Path
import sys
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tests import expired_gate_failure_evidence as diagnostic

SECRET = 'SYNTHETIC_SECRET_NEVER_OUTPUT_741'
ROOT = Path(__file__).resolve().parents[1]
METHOD = 'test_expired_sigstopped_shared_gate_owner_is_killed_so_publication_can_recover'


def canonical(value):
    if isinstance(value, ast.AST):
        return [type(value).__name__, [[key, canonical(item)] for key, item in ast.iter_fields(value)
                if not (key == 'type_params' and item == [])]]
    if type(value) is list:
        return [canonical(item) for item in value]
    if type(value) is bytes:
        return ['bytes', value.hex()]
    if value is Ellipsis:
        return ['ellipsis']
    if type(value) is complex:
        return ['complex', repr(value)]
    return value


def ast_sha(value):
    return hashlib.sha256(json.dumps(canonical(value), separators=(',', ':'), ensure_ascii=True).encode()).hexdigest()


def router():
    return SimpleNamespace(_monitor=threading.current_thread(), _stop=threading.Event())


def packet(observation=None, errors=None, primary=None):
    stream = io.StringIO()
    emitted = diagnostic.emit_expired_gate_failure(observation or {}, errors or [], primary, router(), threading.current_thread(), stream=stream)
    text = stream.getvalue()
    if not emitted:
        raise AssertionError('pure in-memory writer did not accept record')
    return text, json.loads(text[len(diagnostic.PREFIX):])


def recursive_error():
    code = ('def ' + METHOD + '(n):\n'
            '    if n: return ' + METHOD + '(n-1)\n'
            '    raise ValueError("' + SECRET + '")\n' + METHOD + '(40)')
    try:
        exec(compile(code, '/' + SECRET + '/tests/test_durable_faults.py', 'exec'), {})
    except ValueError as error:
        return error


class FailureDiagnosticTests(unittest.TestCase):
    def test_complete_original_ast_is_preserved_except_exact_failure_hook(self):
        tree = ast.parse((ROOT / 'tests/test_durable_faults.py').read_text())
        method = next(node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == METHOD)
        hooks = [(block, index, node) for block in ast.walk(method) if isinstance(block, ast.Try)
                 for index, node in enumerate(block.finalbody) if isinstance(node, ast.If)
                 and any(isinstance(part, ast.ImportFrom) and part.module == 'tests.expired_gate_failure_evidence' for part in ast.walk(node))]
        self.assertEqual(len(hooks), 1)
        block, index, actual = hooks[0]
        expected = ast.parse('''if primary_error is not None:
    try:
        from tests.expired_gate_failure_evidence import emit_expired_gate_failure
        emit_expired_gate_failure(observation, errors, primary_error, self.router, thread)
    except BaseException:
        pass
''').body[0]
        self.assertEqual(canonical(actual), canonical(expected))
        self.assertIsInstance(block.finalbody[index - 1], ast.Assign)
        del block.finalbody[index]
        reference = json.loads((ROOT / 'evidence/reviews/expired-gate-failure-5a/original-ast.json').read_text())
        self.assertEqual(ast_sha(tree), reference['canonical_module_ast_sha256'])

    def test_success_hook_does_not_import_collect_or_write(self):
        tree = ast.parse((ROOT / 'tests/test_durable_faults.py').read_text())
        method = next(node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == METHOD)
        hook = next(node for node in ast.walk(method) if isinstance(node, ast.If)
                    and any(isinstance(part, ast.ImportFrom) and part.module == 'tests.expired_gate_failure_evidence' for part in ast.walk(node)))
        code = compile(ast.fix_missing_locations(ast.Module(body=[hook], type_ignores=[])), '<actual-success-hook>', 'exec')
        # All other argument names deliberately absent: a success-path reference,
        # import or call would fail instead of silently passing a mirror fixture.
        with patch('builtins.__import__', side_effect=AssertionError(SECRET)):
            exec(code, {'primary_error': None})

    def test_secret_observation_fields_and_malformed_values_are_not_serialized(self):
        observation = {'owner_nonce': SECRET, 'message': SECRET, 'publication_started_at': SECRET,
            'selected_binding': {'pid': 11, 'start_ticks': 12, 'uid': 13, 'boot_id': SECRET},
            'captured_lease': {'owner_pid': 11, 'generation': 1, 'active': True, 'expires_ns': 15, 'owner_nonce': SECRET},
            'lease_reads': [{'observed': False, 'error_type': SECRET, 'message': SECRET}],
            'capture_attempts': [{'at': 1.25, 'candidate': [{'path': SECRET}],
                'retained_after_stop': [{'nonce': SECRET}], 'writer_availability_probe': {'available': False, 'native_errorcode': 15, 'message': SECRET}}]}
        text, data = packet(observation)
        self.assertNotIn(SECRET, text)
        self.assertEqual(data['observation']['captured_lease']['generation'], 1)
        self.assertEqual(data['observation']['last_capture']['writer_availability_probe']['native_errorcode'], 15)
        self.assertIsNone(data['observation']['publication_started_at'])
        self.assertGreater(data['drop_counts']['fields'], 0)

    def test_exception_messages_notes_locals_dynamic_names_and_codes_are_private(self):
        private_local = SECRET
        cls = type(SECRET, (Exception,), {})
        try:
            raise cls(private_local)
        except Exception as error:
            error.code = SECRET
            error.sqlite_errorcode = 5
            error.__notes__ = [SECRET]
            text, data = packet(errors=[error], primary=error)
        self.assertNotIn(SECRET, text)
        self.assertEqual(data['publisher_errors'][0][0]['type'], '<unlisted>')
        self.assertEqual(data['publisher_errors'][0][0]['sqlite_errorcode'], 5)
        self.assertNotIn('code', data['publisher_errors'][0][0])

    def test_source_paths_are_labels_and_frames_do_not_read_source(self):
        error = recursive_error()
        with patch('builtins.open', side_effect=AssertionError('forbidden source read')):
            text, data = packet(errors=[error], primary=error)
        self.assertNotIn(SECRET, text)
        self.assertIn('tests.test_durable_faults', text)
        self.assertTrue(data['publisher_errors'][0][0]['frames'])

    def test_only_three_named_thread_roles_and_monitor_flags_are_collected(self):
        text, data = packet()
        self.assertEqual(set(data['threads']), {'main', 'monitor', 'publisher', 'monitor_stop'})
        self.assertIs(data['threads']['monitor']['alive'], True)
        self.assertIs(data['threads']['monitor_stop'], False)
        self.assertIsInstance(data['monotonic_ns'], int)
        self.assertIsInstance(data['boottime_ns'], int)
        self.assertIsInstance(data['utc_ns'], int)

    def test_collections_frames_and_total_output_are_bounded_without_input_mutation(self):
        first, second = recursive_error(), recursive_error()
        second.__cause__ = first
        errors = [second] * 32
        reads = [{'observed': True, 'value': {'owner_pid': 11, 'generation': 1, 'active': True}}] * 5000
        observation = {'lease_reads': reads}
        text, data = packet(observation, errors, second)
        self.assertLessEqual(len(text.encode('utf-8')), diagnostic.MAX_BYTES)
        self.assertIs(data['truncated'], True)
        self.assertGreater(data['drop_counts']['items'], 0)
        self.assertEqual(len(errors), 32)
        self.assertEqual(len(reads), 5000)
        self.assertIs(second.__cause__, first)

    def test_logger_failure_preserves_original_exception_and_cleanup(self):
        class BrokenWriter:
            def write(self, value):
                raise KeyboardInterrupt(SECRET)
        primary = ValueError(SECRET)
        cleaned = []
        try:
            try:
                raise primary
            finally:
                self.assertIs(diagnostic.emit_expired_gate_failure({}, [], primary, None, None, stream=BrokenWriter()), False)
                cleaned.append(True)
        except ValueError as observed:
            self.assertIs(observed, primary)
        self.assertEqual(cleaned, [True])

    def test_collector_failure_is_bounded_literal_fallback_and_cleanup_continues(self):
        stream = io.StringIO()
        with patch.object(diagnostic, 'build_failure_diagnostic', side_effect=RuntimeError(SECRET)):
            self.assertIs(diagnostic.emit_expired_gate_failure({}, [], None, None, None, stream=stream), True)
        self.assertNotIn(SECRET, stream.getvalue())
        self.assertIs(json.loads(stream.getvalue()[len(diagnostic.PREFIX):])['collector_failed'], True)

    def test_partial_writer_is_not_reported_as_complete(self):
        class PartialWriter:
            def write(self, value):
                return 0
        self.assertIs(diagnostic.emit_expired_gate_failure({}, [], None, None, None, stream=PartialWriter()), False)

    def test_helper_has_no_source_SQL_status_signal_thread_start_or_wait_calls(self):
        tree = ast.parse((ROOT / 'tests/expired_gate_failure_evidence.py').read_text())
        forbidden = {'open', 'connect', 'status', 'kill', 'pidfd_send_signal', 'start', 'wait', 'sleep', 'join', 'getsource', 'read_text', 'read_bytes'}
        names = {node.func.id if isinstance(node.func, ast.Name) else node.func.attr
                 for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, (ast.Name, ast.Attribute))}
        self.assertEqual(names & forbidden, set())
