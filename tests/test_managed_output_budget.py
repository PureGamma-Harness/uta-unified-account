"""Pure JSON and owned temporary output fixtures; no SQL or child processes."""
from copy import deepcopy
from contextlib import nullcontext
from hashlib import sha256
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from tools import managed_output_budget as policy
from tools import prepare_managed_stability as prepare
from tools import run_managed_long as runner
from tools.managed_output_budget import GIB, explicit_output_budget, measured_output_bytes, output_budget_bytes


def long_plan(explicit=True):
    observer = dict(blocks=12, independent_finance_golden_required_each_1800_second_block=1,
        technical_read_unknown_budget=3, maximum_consecutive_technical_read_unknown=1,
        interval_seconds=61, max_private_clone_bytes=GIB, clone_headroom_bytes=GIB,
        max_address_space_bytes=2 * GIB)
    if explicit:
        observer['output_budget_bytes'] = 2 * GIB
    return dict(source_root='/synthetic/source', source_commit='a' * 40,
        python='/synthetic/python', validation_report='/synthetic/report.json', known_failed_gate='capacity',
        producer=dict(duration_seconds=21600, rate_rounds_per_second=.25, planned_rounds=5400,
            worker_fault_every_rounds=30, parent_fault_every_rounds=300, source_budget_bytes=6 * GIB),
        observer=observer)


class OutputBudgetPolicyTests(unittest.TestCase):
    def test_missing_field_preserves_six_gib_and_does_not_mutate_plan(self):
        plan = {'observer': {'blocks': 12}}
        before = deepcopy(plan)
        self.assertEqual(output_budget_bytes(plan), 6 * GIB)
        self.assertFalse(explicit_output_budget(plan))
        self.assertEqual(plan, before)

    def test_explicit_integer_byte_boundaries_and_future_two_gib(self):
        for value in (GIB, GIB + 1, 2 * GIB, 6 * GIB):
            with self.subTest(value=value):
                plan = {'producer': {'source_budget_bytes': 6 * GIB}, 'observer': {'output_budget_bytes': value}}
                self.assertEqual(output_budget_bytes(plan), value)
                self.assertTrue(explicit_output_budget(plan))

    def test_rejects_out_of_range_values(self):
        for value in (-1, 0, 1, GIB - 1, 6 * GIB + 1):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, 'budget_bytes_invalid'):
                output_budget_bytes({'observer': {'output_budget_bytes': value}})

    def test_rejects_bool_float_string_null_and_containers(self):
        for value in (True, False, float(GIB), str(GIB), None, [], {}):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, 'budget_bytes_invalid'):
                output_budget_bytes({'observer': {'output_budget_bytes': value}})

    def test_rejects_missing_or_invalid_observer_metadata(self):
        for plan in (None, [], {}, {'observer': None}, {'observer': []}):
            with self.subTest(plan=plan), self.assertRaisesRegex(ValueError, 'budget_plan_invalid'):
                output_budget_bytes(plan)

    def test_future_reservation_arithmetic_is_not_a_qualification(self):
        new = 6 * GIB + output_budget_bytes(long_plan()) + GIB + GIB
        self.assertEqual(new, 10_737_418_240)
        self.assertEqual(new + 6 * GIB + 256 * 1024**2, 17_448_304_640)


class OutputMeasurementTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.control, self.observer = self.root / 'control', self.root / 'observer'
        self.control.mkdir()
        self.observer.mkdir()

    def test_counts_control_unknown_nested_receipts_and_atomic_temporary_files(self):
        (self.control / 'classifications.jsonl').write_bytes(b'123')
        nested = self.observer / 'unknown'
        nested.mkdir()
        (nested / 'receipt.json').write_bytes(b'12345')
        (self.control / '.atomic-temporary').write_bytes(b'12')
        self.assertEqual(measured_output_bytes(self.control, self.observer), 10)

    def test_only_actual_direct_private_clone_subtrees_are_excluded(self):
        private = self.observer / 'private-audit'
        private.mkdir(mode=0o700)
        clone = private / 'private-full-clone-a1b2c3d4'
        clone.mkdir(mode=0o700)
        (clone / 'complete-authority.bin').write_bytes(b'x' * 37)
        (private / 'unknown.log').write_bytes(b'123')
        invalid = private / 'private-full-clone-unknown-sibling'
        invalid.mkdir()
        (invalid / 'not-an-actual-clone.bin').write_bytes(b'12')
        unknown = self.control / 'private-full-clone-not-an-exception'
        unknown.mkdir()
        (unknown / 'other.bin').write_bytes(b'12345')
        self.assertEqual(measured_output_bytes(self.control, self.observer), 10)

    def test_symlinks_in_counted_and_excluded_trees_are_rejected(self):
        for name in ('normal', 'clone'):
            with self.subTest(name=name):
                if name == 'normal':
                    parent = self.control
                else:
                    private = self.observer / 'private-audit'
                    private.mkdir(mode=0o700)
                    parent = private / 'private-full-clone-a1b2c3d4'
                    parent.mkdir(mode=0o700)
                link = parent / 'link'
                link.symlink_to(self.root / 'missing')
                with self.assertRaisesRegex(ValueError, 'symlink_or_special'):
                    measured_output_bytes(self.control, self.observer)
                link.unlink()

    def test_root_or_clone_directory_symlink_is_rejected(self):
        external = self.root / 'external'
        external.mkdir()
        private = self.observer / 'private-audit'
        private.mkdir(mode=0o700)
        (private / 'private-full-clone-link').symlink_to(external, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'symlink_or_special'):
            measured_output_bytes(self.control, self.observer)
        with self.assertRaises(OSError):
            measured_output_bytes(private / 'private-full-clone-link', self.observer)

    def test_special_file_rejected_without_opening_it(self):
        os.mkfifo(self.control / 'pipe')
        with self.assertRaisesRegex(ValueError, 'symlink_or_special'):
            measured_output_bytes(self.control, self.observer)

    def test_unreadable_or_disappeared_metadata_is_unknown_not_zero(self):
        (self.control / 'entry').write_bytes(b'x')
        for error in (PermissionError('synthetic denied'), OSError('synthetic IO'), FileNotFoundError('synthetic race')):
            with self.subTest(error=type(error).__name__), patch.object(policy.os, 'stat', side_effect=error):
                with self.assertRaises(type(error)):
                    measured_output_bytes(self.control, self.observer)

    def test_missing_required_output_tree_is_unknown(self):
        with self.assertRaises(FileNotFoundError):
            measured_output_bytes(self.root / 'missing', self.observer)

    def test_clone_identity_permissions_must_be_private_before_exclusion(self):
        private = self.observer / 'private-audit'
        private.mkdir(mode=0o700)
        clone = private / 'private-full-clone-a1b2c3d4'
        clone.mkdir(mode=0o755)
        clone.chmod(0o755)  # Do not let the caller's private umask alter the fixture.
        with self.assertRaisesRegex(ValueError, 'private_clone_identity_invalid'):
            measured_output_bytes(self.control, self.observer)


class SourceBudgetBindingTests(unittest.TestCase):
    def fixture(self, root, source=6 * GIB, *, missing=False, explicit=True):
        plan = long_plan(explicit)
        if missing:
            del plan['producer']['source_budget_bytes']
        else:
            plan['producer']['source_budget_bytes'] = source
        path, amendment = root/'plan.json', root/'amendment.json'
        raw = json.dumps(plan).encode()
        path.write_bytes(raw)
        amendment.write_text(json.dumps(dict(original_plan_sha256=sha256(raw).hexdigest(),
            observer_interval_seconds_effective=61)))
        profile = {key: plan[key] for key in ('source_root', 'source_commit', 'python', 'validation_report')}
        profile.update(plan=str(path), amendment=str(amendment), plan_sha256=sha256(raw).hexdigest(),
            amendment_sha256=sha256(amendment.read_bytes()).hexdigest(), qualification={},
            smoke_scratch=str(root/'smoke'), long_scratch=str(root/'long'))
        profile_path = root/'profile.json'
        profile_path.write_text(json.dumps(profile))
        control = root/'control'
        control.mkdir(exist_ok=True)
        (control/'preflight.json').write_text('{}')
        return plan, path, amendment, profile_path

    def test_real_hashed_plan_counterexample_refused_without_mutating_counters_or_bytes(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            plan, path, amendment, _ = self.fixture(root, GIB)
            raw, counters = path.read_bytes(), deepcopy(plan['producer'])
            with patch.object(runner.subprocess, 'Popen') as child:
                with self.assertRaisesRegex(ValueError, 'actual_six_gib_source_budget'):
                    runner.read_plan(path, amendment)
                child.assert_not_called()
            self.assertEqual(path.read_bytes(), raw)
            self.assertEqual(plan['producer'], counters)

    def test_all_entrypoints_refuse_wrong_missing_or_noninteger_source_before_external_effects(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            for source in (True, False, float(6 * GIB), GIB, 7 * GIB, None, str(6 * GIB)):
                for missing in (False, True) if source is None else (False,):
                    _, path, amendment, profile_path = self.fixture(root, source, missing=missing)
                    args = SimpleNamespace(plan=path, amendment=amendment, scratch=root)
                    entrypoints = {
                        'resolver': lambda: output_budget_bytes(json.loads(path.read_text())),
                        'read_plan': lambda: runner.read_plan(path, amendment),
                        'preflight': lambda: runner.preflight(args),
                        'supervise': lambda: runner.supervise(args),
                        'profile': lambda: prepare.profile(profile_path),
                        'prepare': lambda: prepare.prepare(profile_path),
                        'invoke': lambda: prepare.invoke(profile_path, 'long-start', 'no-go'),
                    }
                    for name, entry in entrypoints.items():
                        with self.subTest(source=source, missing=missing, entry=name), \
                                patch.object(runner.subprocess, 'Popen') as child, \
                                patch.object(runner.subprocess, 'run') as command, \
                                patch.object(runner, 'git') as git, \
                                patch.object(prepare.subprocess, 'check_output') as process, \
                                patch.object(prepare.importlib, 'import_module') as module, \
                                patch.object(Path, 'mkdir') as mkdir:
                            with self.assertRaisesRegex(ValueError, 'actual_six_gib_source_budget'):
                                entry()
                            for effect in (child, command, git, process, module, mkdir):
                                effect.assert_not_called()

    def test_correct_six_gib_accepted_and_legacy_source_declarations_unchanged(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            for explicit, source in ((True, 6 * GIB), (False, GIB), (False, float(6 * GIB))):
                _, path, amendment, profile_path = self.fixture(root, source, explicit=explicit)
                value, _, _ = runner.read_plan(path, amendment)
                self.assertEqual(output_budget_bytes(value), (2 if explicit else 6) * GIB)
                self.assertEqual(value['producer']['source_budget_bytes'], source)
                self.assertEqual(prepare.profile(profile_path)['source_commit'], 'a' * 40)
                self.assertEqual(runner.producer_command(value, root/'never-created-job'),
                    [value['python'], '-B', 'benchmarks/run_managed_soak.py', 'run', '--directory',
                     str(root/'never-created-job'), '--duration', '21600', '--allow-long-run',
                     '--validation-report', value['validation_report']])
            self.assertFalse((root/'never-created-job').exists())


class OutputIntegrationTests(unittest.TestCase):
    def test_read_plan_validates_explicit_value_without_editing_raw_plan(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            for value in (None, 2 * GIB, True, 6 * GIB + 1):
                plan = long_plan(explicit=False)
                if value is not None:
                    plan['observer']['output_budget_bytes'] = value
                raw = json.dumps(plan).encode()
                path, amendment = root / 'plan.json', root / 'amendment.json'
                path.write_bytes(raw)
                amendment.write_text(json.dumps(dict(original_plan_sha256=sha256(raw).hexdigest(),
                    observer_interval_seconds_effective=61)))
                if value is True or value == 6 * GIB + 1:
                    with self.assertRaisesRegex(ValueError, 'budget_bytes_invalid'):
                        runner.read_plan(path, amendment)
                else:
                    actual, _, _ = runner.read_plan(path, amendment)
                    self.assertEqual(output_budget_bytes(actual), 6 * GIB if value is None else value)
                self.assertEqual(path.read_bytes(), raw)

    def test_preflight_and_prepare_reserve_same_default_and_explicit_bytes(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            for explicit in (False, True):
                plan = long_plan(explicit)
                amount = 2 * GIB if explicit else 6 * GIB
                expected = 6 * GIB + amount + GIB + GIB
                evidence = dict(code_commit=plan['source_commit'], tests_run=1413)
                plan['qualification'] = dict(tests_each=1413)
                device = dict(source_readonly=True, devnull_character_device=True, devnull_child_exit=0)
                git = lambda _, *args: '' if args[0] == 'status' else plan['source_commit']
                with patch.object(runner, 'read_plan', return_value=(plan, dict(replay_scope={}), {})), \
                        patch.object(runner, 'git', side_effect=git), \
                        patch.object(runner.subprocess, 'run', side_effect=[SimpleNamespace(returncode=0, stdout=json.dumps(evidence)),
                            SimpleNamespace(returncode=0, stdout=json.dumps(device))]), \
                        patch('shutil.disk_usage', return_value=SimpleNamespace(free=100 * GIB)):
                    result = runner.preflight(SimpleNamespace(plan=root/'unused', amendment=root/'unused2', scratch=root/'fresh'))
                self.assertEqual(result['observer_output_budget_bytes'], amount)
                self.assertEqual(result['conservative_required_free_bytes'], expected)
                path = root / 'plan.json'
                path.write_text(json.dumps(plan))
                value = dict(source_root=plan['source_root'], source_commit=plan['source_commit'],
                    validation_report=str(root/'missing-report'), plan=str(path), long_scratch=str(root/'long'),
                    qualification={}, smoke_scratch=str(root/'smoke'))
                with patch.object(prepare, 'profile', return_value=value), \
                        patch.object(prepare.subprocess, 'check_output', return_value=plan['source_commit']), \
                        patch.object(prepare, 'fingerprint', return_value='synthetic'), \
                        patch.object(prepare, 'commands', return_value={}), \
                        patch.object(prepare, 'cohost_budget', return_value={}) as cohost, \
                        patch.object(prepare.shutil, 'disk_usage', return_value=SimpleNamespace(free=100 * GIB)):
                    result = prepare.prepare(root/'profile')
                self.assertEqual(result['disk']['observer_bytes'], amount)
                self.assertEqual(result['disk']['long_conservative_required_bytes'], expected)
                cohost.assert_called_once_with(expected)

    def test_invoke_budget_before_imports_uses_same_value_and_smoke_clone_limit(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / 'plan.json'
            plan = long_plan()
            path.write_text(json.dumps(plan))
            value = dict(plan=str(path), source_root=plan['source_root'], resource_review={})
            for phase, clone in (('long-preflight', GIB), ('smoke-produce', 256 * 1024**2)):
                with self.subTest(phase=phase), patch.object(prepare, 'profile', return_value=value), \
                        patch.object(prepare, 'authorized'), patch.object(prepare, 'cohost_budget', return_value={}) as cohost, \
                        patch.object(prepare.importlib, 'import_module') as module, \
                        patch.object(prepare.subprocess, 'Popen') as child:
                    with self.assertRaisesRegex(ValueError, 'floor_not_independently_reviewed'):
                        prepare.invoke(path, phase, 'unused')
                    cohost.assert_called_once_with(6 * GIB + 2 * GIB + clone + GIB)
                    module.assert_not_called()
                    child.assert_not_called()

    def exercise_one_collect(self, root, *, explicit=True, measure_error=None, failed_write=False,
                             failed_append=False, legacy_file=False, control_size=2 * GIB + 1):
        """Run supervisor control flow with mocked children; no Popen or SQL."""
        class StopFixture(BaseException):
            pass
        plan = long_plan(explicit)
        control, output = root/'control', root/'observer'
        control.mkdir()
        output.mkdir()
        # Sparse metadata fixture: no GiB of data is written or allocated.
        with (control/'new-control-record').open('wb') as stream:
            stream.truncate(control_size)
        if legacy_file:
            with (output/'timeline.jsonl').open('wb') as stream:
                stream.truncate(6 * GIB + 1)
        if failed_append:
            (output/'timeline.jsonl').write_text('{"synthetic":true,"logical_point":"unknown","alerts":[]}\n')
        producer = Mock()
        producer.birth = '123'
        producer.started_boottime_ns = runner.time.clock_gettime_ns(runner.time.CLOCK_BOOTTIME)
        producer.process.pid = 123456789
        producer.process.poll.return_value = None
        producer.identity.return_value = dict(pid=123456789, birth='123', started_wall_ns=1, started_boottime_ns=1)
        events = []
        producer.terminate_owned.side_effect = lambda: events.append('drain') or True
        registered = dict(observer_freeze_commit='synthetic', selected_cpu=2,
            observer_output_budget_bytes=output_budget_bytes(plan))
        def record(path, value):
            events.append(('write', Path(path).name, value))
            if failed_write or failed_append and Path(path).name == 'sample-classification.jsonl':
                raise OSError('synthetic output full')
        original_measure = runner.measured_output_bytes
        with patch.object(runner, 'Pipes', return_value=producer), \
                patch.object(runner, 'read_plan', return_value=(plan, {}, {})), \
                patch.object(runner, 'git', return_value='synthetic'), \
                patch.object(runner.ro, 'load_json', return_value=registered), \
                patch.object(runner.ro, 'process_identity', return_value={'birth': '123'}), \
                patch.object(runner.ro, 'atomic_json', side_effect=record), \
                patch.object(runner, 'append', side_effect=record), \
                patch.object(runner.os, 'sched_setaffinity'), patch.object(runner.signal, 'signal'), \
                patch.object(runner.time, 'sleep', side_effect=StopFixture), \
                patch.object(runner.Timeline, 'read', return_value=[]) if legacy_file else nullcontext(), \
                patch.object(runner, 'measured_output_bytes', side_effect=measure_error or original_measure):
            with self.assertRaises(OSError if failed_write else StopFixture):
                runner.supervise(SimpleNamespace(scratch=root, plan=root/'unused', amendment=root/'unused2'))
        return events, producer

    def test_explicit_control_exceedance_drains_before_error_log_without_financial_alert(self):
        with TemporaryDirectory() as directory:
            events, producer = self.exercise_one_collect(Path(directory))
        producer.terminate_owned.assert_called_once()
        event = next(item for item in events if isinstance(item, tuple) and item[2].get('code') == 'observer_output_budget_exceeded')
        self.assertLess(events.index('drain'), events.index(event))
        self.assertEqual(event[2]['measured_output_bytes'], 2 * GIB + 1)
        self.assertFalse(event[2]['financial_corruption_inferred'])

    def test_explicit_measurement_unknown_drains_with_typed_technical_record(self):
        with TemporaryDirectory() as directory:
            events, producer = self.exercise_one_collect(Path(directory), measure_error=PermissionError('synthetic denied'))
        producer.terminate_owned.assert_called_once()
        event = next(item for item in events if isinstance(item, tuple) and item[2].get('code') == 'observer_output_budget_measurement_unknown')
        self.assertEqual(event[2]['error_type'], 'PermissionError')
        self.assertIsNone(event[2]['measured_output_bytes'])
        self.assertLess(events.index('drain'), events.index(event))

    def test_explicit_initial_write_failure_still_requests_drain_before_error_log(self):
        with TemporaryDirectory() as directory:
            events, producer = self.exercise_one_collect(Path(directory), failed_write=True)
        producer.terminate_owned.assert_called_once()
        event = next(item for item in events if isinstance(item, tuple) and item[2].get('code') == 'observer_output_write_failed')
        self.assertLess(events.index('drain'), events.index(event))

    def test_missing_field_retains_legacy_three_file_scope_and_does_not_drain_for_control(self):
        with TemporaryDirectory() as directory:
            events, producer = self.exercise_one_collect(Path(directory), explicit=False)
        producer.terminate_owned.assert_not_called()
        self.assertFalse(any(isinstance(item, tuple) and item[2].get('code') == 'observer_output_budget_exceeded' for item in events))

    def test_legacy_three_file_exceedance_preserves_historical_field_without_drain(self):
        with TemporaryDirectory() as directory:
            events, producer = self.exercise_one_collect(Path(directory), explicit=False, legacy_file=True)
        producer.terminate_owned.assert_not_called()
        event = next(item for item in events if isinstance(item, tuple) and item[2].get('code') == 'observer_output_budget_exceeded')
        self.assertEqual(event[2]['measured_known_output_bytes'], 6 * GIB + 1)
        self.assertFalse(event[2]['financial_drain_requested'])
        self.assertNotIn('official_driver_drain_requested', event[2])

    def test_explicit_append_failure_drains_before_technical_error_log(self):
        with TemporaryDirectory() as directory:
            events, producer = self.exercise_one_collect(Path(directory), failed_append=True, control_size=0)
        producer.terminate_owned.assert_called_once()
        event = next(item for item in events if isinstance(item, tuple) and item[2].get('code') == 'observer_output_write_failed')
        self.assertLess(events.index('drain'), events.index(event))

    def test_protected_old_pid_is_rejected_before_identity_or_signal(self):
        for pid in (4471, 8784):
            owned = object.__new__(runner.Pipes)
            owned.process = Mock(pid=pid)
            with patch.object(runner.ro, 'process_identity') as identity:
                with self.assertRaisesRegex(ValueError, 'protected_old_process'):
                    owned.terminate_owned()
                identity.assert_not_called()
            owned.process.send_signal.assert_not_called()


if __name__ == '__main__':
    unittest.main()
