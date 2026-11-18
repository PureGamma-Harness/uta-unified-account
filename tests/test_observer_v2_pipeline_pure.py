"""New opt-in pipeline fixtures. CODE ONLY until exact-source root GO.

Never import the observer/controller modules or instantiate their native
constructors. Extract only named source definitions into fake dependencies.
"""
import ast
from contextlib import contextmanager
from copy import deepcopy
import copy
from hashlib import sha256
import io
import json
import os
from pathlib import Path
from queue import Empty, Full, Queue
import re
import stat
import sys
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools import managed_observer_report as codec, managed_observer_transport as wire
from tools.managed_observer_coverage import Coverage

FROZEN_COVERAGE = ROOT / 'tests/fixtures/managed_observer_coverage_909.py'
legacy_namespace = {}
exec(compile(ast.parse(FROZEN_COVERAGE.read_bytes()), 'frozen-pure-coverage-909', 'exec'), legacy_namespace)
FrozenCoverage = legacy_namespace['Coverage']

PLAN = {"python": "synthetic-python", "source_root": "synthetic-source", "source_commit": "0" * 40,
    "producer": {"duration_seconds": 1800, "source_budget_bytes": 6 * 1024**3},
    "observer": {"report_format": "compact-v2", "output_budget_bytes": 2 * 1024**3,
        "blocks": 1, "independent_finance_golden_required_each_1800_second_block": 1,
        "technical_read_unknown_budget": 3, "maximum_consecutive_technical_read_unknown": 2,
        "interval_seconds": 60, "max_private_clone_bytes": 6 * 1024**3,
        "clone_headroom_bytes": 1024**3, "max_address_space_bytes": 2 * 1024**3}}


def source(relative):
    return ast.parse((ROOT / relative).read_bytes())


def named(tree, name, kind=ast.FunctionDef):
    return next(node for node in ast.walk(tree) if isinstance(node, kind) and node.name == name)


def extract(relative, names, namespace):
    tree = source(relative)
    nodes = [node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.ClassDef)) and node.name in names]
    assert len(nodes) == len(names)
    exec(compile(ast.Module(body=nodes, type_ignores=[]), relative + "#named-only", "exec"), namespace)
    return namespace


def full(count=3):
    return {"format": 1, "logical_point": "stable_boundary", "active_elapsed_seconds": 60.0,
        "sample_wall_ns": 1, "active_rounds": [], "completed_rounds": count,
        "unresolved_steps": 0, "unresolved_faults": 0, "planned_faults": [], "alerts": [],
        "final_evidence_eligible": False, "finance": {"counts": {"uta_command_inbox": count},
            "command_inbox": [{"sequence": n, "command_id": "synthetic:" + str(n),
                "state": "SUCCEEDED", "kind": "SUBMIT_ORDER", "control_lane": False,
                "attempts": 0, "last_error_present": False, "last_error_code": None}
                for n in range(count)], "retry_alerts": [],
            "watermark": {"format": 2, "sha256": "0" * 64},
            "golden": {"compared": True, "passed": True, "errors": []}}}


class MemoryStore:
    def __init__(self, events=None, budget=10**7):
        self.nodes, self.events, self.budget, self.used = {}, events, budget, 0
    def put(self, identity, raw):
        if self.events is not None: self.events.append("CAS")
        if identity in self.nodes:
            assert self.nodes[identity] == raw
            return
        if self.used + len(raw) > self.budget: raise ValueError("synthetic_CAS_quota")
        self.nodes[identity] = raw
        self.used += len(raw)
    def get(self, identity): return self.nodes[identity]


class Receipts:
    def __init__(self): self.rows = {}
    def get(self, attempt): return self.rows.get(attempt)
    def create(self, attempt, compact):
        assert attempt not in self.rows
        self.rows[attempt] = deepcopy(compact)


def controller_namespace(events=None):
    events = [] if events is None else events
    files = {}
    def append(path, value):
        events.append("append:" + str(path))
        files.setdefault(str(path), []).append(deepcopy(value))
    def atomic(path, value):
        events.append("atomic:" + str(path))
        files[str(path)] = deepcopy(value)
    ro = SimpleNamespace(parse=codec.strict_json, FLAGS=codec.FLAGS,
        canonical=lambda value: codec.canonical(value).decode(), atomic_json=atomic)
    namespace = {"copy": copy, "sha256": sha256, "ro": ro, "transport": wire,
        "compact_reports": codec, "Empty": Empty, "Queue": Queue,
        "time": SimpleNamespace(time_ns=lambda: 9, clock_gettime_ns=lambda *_: 9, CLOCK_BOOTTIME=7),
        "append": append, "LINE_CAP": wire.LINE_CAP, "ROOT": Path("synthetic-root"),
        "RESULT_FIELDS": set(full())}
    extract("tools/run_managed_long.py", {"classify_safely", "financial_drain_before_log", "Pipes", "Timeline", "final_once"}, namespace)
    return namespace, events, files


def parent_scope(*, budget=10**7, coverage=None):
    namespace, events, files = controller_namespace()
    store, receipts = MemoryStore(events, budget), Receipts()
    class Producer:
        process = SimpleNamespace(poll=lambda: None)
        def terminate_owned(self): events.append("financial_drain"); return True
        def identity(self): return {"pid": 17, "birth": "23"}
    producer = Producer()
    def write_output(function, *args): return function(*args)
    def resource(code, error=None, measured=None): events.append("resource:" + code)
    namespace.update(coverage_seed=coverage or Coverage(PLAN), producer=producer,
        v2=True, node_store=store, receipts=receipts, output=Path("synthetic-observer"),
        control=Path("synthetic-control"), historical_financial_alerts=set(), collection_errors=[],
        write_output=write_output, resource_no_go=resource, output_budget=2 * 1024**3,
        measured_output_bytes=lambda *_: store.used,
        sample_attempt_id=1)
    process = deepcopy(named(source("tools/run_managed_long.py"), "process_samples"))
    factory = ast.parse("""def make_scope():
    attempt = 0
    drained = False
    last_sample_elapsed = None
    coverage = coverage_seed
    drain_requested_ns = None
""").body[0]
    factory.body.append(process)
    factory.body.extend(ast.parse("return process_samples, lambda: (attempt, coverage, drained)").body)
    exec(compile(ast.fix_missing_locations(ast.Module(body=[factory], type_ignores=[])), "actual-process-samples#fake-scope", "exec"), namespace)
    accept, state = namespace["make_scope"]()
    return SimpleNamespace(accept=accept, state=state, namespace=namespace, events=events,
                           files=files, store=store, receipts=receipts)


class ObserverV2PipelinePureTests(unittest.TestCase):
    def test_financial_verifier_and_legacy_classification_body_preserved(self):
        self.assertEqual(sha256(FROZEN_COVERAGE.read_bytes()).hexdigest(),
            '15e4f97c1d3541c2ee076e618b19ce5442f42290b3ffefd63e29985942485699')
        original = source("tests/fixtures/managed_soak_observer_909.py")
        current = source("tools/managed_soak_observer.py")
        for name in ("sample", "final_check", "producer_audit", "original_command_coverage", "publish"):
            self.assertEqual(ast.dump(named(current, name), include_attributes=False),
                             ast.dump(named(original, name), include_attributes=False), name)
        prior = source("tests/fixtures/run_managed_long_909.py")
        candidate = source("tools/run_managed_long.py")
        for name in ("classify_safely", "financial_drain_before_log", "resource_no_go"):
            self.assertEqual(ast.dump(named(prior, name), include_attributes=False),
                             ast.dump(named(candidate, name), include_attributes=False), name)
        old_for = next(node for node in named(prior, "collect").body if isinstance(node, ast.For))
        new_for = deepcopy(next(node for node in named(candidate, "process_samples").body if isinstance(node, ast.For)))
        self.assertEqual(ast.unparse(new_for.body[-1].test), "v2")
        new_for.body.pop()
        self.assertEqual(ast.dump(new_for, include_attributes=False), ast.dump(old_for, include_attributes=False))

    def test_legacy_watch_emission_remains_default_and_v2_suppresses_old_publish(self):
        old = source("tests/fixtures/managed_soak_observer_909.py")
        current = source("tools/managed_soak_observer.py")
        main = deepcopy(named(current, "main"))
        main.body = [node for node in main.body if not (
            isinstance(node, ast.Expr) and any(option in ast.unparse(node) for option in ("--collector-input-v2", "--report-protocol"))) and not (
            isinstance(node, ast.If) and "args.collector_input_v2" in ast.unparse(node.test)) and not (
            isinstance(node, ast.Assign) and ast.unparse(node).startswith("input_sequence ="))]
        for node in ast.walk(main):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "Observer":
                node.keywords = [item for item in node.keywords if item.arg not in {"collector_input_v2", "report_protocol"}]
        loop = next(node for node in main.body if isinstance(node, ast.While))
        wire_branch = next(node for node in loop.body if isinstance(node, ast.If) and ast.unparse(node.test) == "args.collector_input_v2")
        self.assertNotIn("observer.publish", "\n".join(ast.unparse(node) for node in wire_branch.body))
        loop.body[loop.body.index(wire_branch):loop.body.index(wire_branch) + 1] = wire_branch.orelse
        once = next(node for node in loop.body if isinstance(node, ast.If) and ast.unparse(node.test) == "args.once")
        self.assertEqual(ast.unparse(once.body[0].test), "not args.collector_input_v2")
        once.body[0:1] = once.body[0].body
        self.assertEqual(ast.dump(main, include_attributes=False), ast.dump(named(old, "main"), include_attributes=False))
        self.assertEqual(wire.report_format({"observer": {}}), "legacy")
        class SourcePath:
            def __init__(self, name): self.name = str(name).rsplit('/', 1)[-1]
            def with_name(self, name): return SourcePath(name)
            def read_bytes(self): return ('synthetic source:' + self.name).encode()
            def __truediv__(self, name): return SourcePath(name)
            def read_text(self): return 'synthetic-boot'
            def exists(self): return True
        contract = deepcopy(named(current, 'contract'))
        namespace = {'Path': SourcePath, '__file__': 'managed_soak_observer.py', 'sha256': sha256,
                     'validate_metadata': lambda *_: {'source': 'synthetic'}}
        exec(compile(ast.Module(body=[contract], type_ignores=[]), 'actual-contract#fake-source', 'exec'), namespace)
        bound = []
        for emits_wire in (True, True, False):
            observer = SimpleNamespace(driver_pid=17, driver_birth='23', frozen_commit='0' * 40,
                collector_input_v2=emits_wire, report_protocol='compact-v2')
            bound.append(namespace['contract'](observer, {}, {}))
        self.assertEqual(bound[0], bound[1]); self.assertEqual(bound[1], bound[2])
        observer.report_protocol = 'legacy'
        legacy_contract = namespace['contract'](observer, {}, {})
        self.assertNotIn('observer_output_protocol', legacy_contract)
        self.assertEqual(len(legacy_contract['observer_code_sha256']), 2)
        commands = {'ROOT': Path('synthetic-root'), 'transport': wire}
        extract('tools/run_managed_long.py', {'observer_command'}, commands)
        launch = {'driver_pid': 17, 'driver_birth': '23'}
        watch = commands['observer_command'](PLAN, Path('synthetic-scratch'), launch, persistent=False)
        audit = commands['observer_command'](PLAN, Path('synthetic-scratch'), launch, audit=True)
        self.assertIn('--report-protocol', watch); self.assertIn('--collector-input-v2', watch)
        self.assertIn('--report-protocol', audit); self.assertNotIn('--collector-input-v2', audit)
        prior_commands = {'ROOT': Path('synthetic-root')}
        extract('tests/fixtures/run_managed_long_909.py', {'observer_command'}, prior_commands)
        legacy_plan = deepcopy(PLAN); del legacy_plan['observer']['report_format']
        for auditing in (False, True):
            self.assertEqual(commands['observer_command'](legacy_plan, Path('synthetic-scratch'), launch,
                audit=auditing, persistent=False), prior_commands['observer_command'](legacy_plan,
                Path('synthetic-scratch'), launch, audit=auditing, persistent=False))
        # Invoke the actual sample's unchanged baseline compare, with all
        # pre-baseline helpers replaced by immutable fakes and no SQL engine.
        role = SimpleNamespace(driver_pid=17, driver_birth='23', frozen_commit='0' * 40,
            collector_input_v2=True, report_protocol='compact-v2',
            output=SourcePath('observer'), job=SourcePath('job'))
        role.contract = lambda meta, cp: namespace['contract'](role, meta, cp)
        sample_namespace = {'Path': SourcePath,
            'time': SimpleNamespace(time_ns=lambda: 9, clock_gettime_ns=lambda *_: 9, CLOCK_BOOTTIME=7),
            'load_json': lambda path: legacy_contract if path.name == 'baseline.json' else
                {'status': 'running'} if path.name == 'progress.json' else {},
            'process_identity': lambda *_: {'known_stopped': False, 'alive': True},
            'checkpoint': lambda *_args, **_kwargs: {'driver_pid': 17}}
        sample_method = deepcopy(named(current, 'sample'))
        exec(compile(ast.Module(body=[sample_method], type_ignores=[]), 'actual-sample#prebaseline-fakes', 'exec'), sample_namespace)
        with self.assertRaisesRegex(ValueError, 'original_source_start_deadline_or_identity_changed'):
            sample_namespace['sample'](role)

    def test_split_coalesced_frames_sequence_hash_cap_and_EOF(self):
        first, second = wire.input_frame(full(), 1), wire.input_frame(full(), 2)
        for pieces in ((first[:17], first[17:]), (first + second,)):
            buffer, decoder, rows = wire.LineBuffer(), wire.FrameDecoder(), []
            for piece in pieces:
                rows.extend(decoder.decode(line) for line in buffer.feed(piece))
            buffer.finish()
            self.assertEqual(len(rows), 1 if len(pieces) == 2 else 2)
        decoder = wire.FrameDecoder(); decoder.decode(first)
        for bad in (first, wire.input_frame(full(), 3)):
            with self.assertRaises(ValueError): decoder.decode(bad)
        changed = codec.strict_json(first); changed["reference_sha256"] = "f" * 64
        with self.assertRaises(ValueError): wire.FrameDecoder().decode(codec.canonical(changed) + b"\n")
        with self.assertRaises(ValueError): list(wire.LineBuffer(limit=8).feed(b"x" * 8))
        partial = wire.LineBuffer(); list(partial.feed(first[:-1]))
        with self.assertRaises(ValueError): partial.finish()

    def test_raw_queue_bound_and_actual_pipe_reader_use_no_constructor(self):
        namespace, _, _ = controller_namespace()
        pipe = namespace["Pipes"].__new__(namespace["Pipes"])
        pipe.samples, pipe.frame_decoder = Queue(maxsize=wire.QUEUE_FRAMES), wire.FrameDecoder()
        pipe.decode_failed, pipe.stream_error, pipe.discarded_frames = False, None, 0
        pipe.results, pipe.line_buffer = {}, wire.LineBuffer()
        pipe.samples.put_nowait(wire.input_frame(full(), 1)); pipe.samples.put_nowait(wire.input_frame(full(), 2))
        with self.assertRaises(Full): pipe.samples.put_nowait(b"third")
        self.assertEqual(list(pipe.read_samples()), [full(), full()])
        class Refilling:
            def __init__(self):
                self.frames = [wire.input_frame(full(1), 1), wire.input_frame(full(2), 2)]
                self.next = 3
            def get_nowait(self):
                frame = self.frames.pop(0)
                self.frames.append(wire.input_frame(full(self.next), self.next))
                self.next += 1
                return frame
            def qsize(self): return len(self.frames)
        pipe.samples, pipe.frame_decoder = Refilling(), wire.FrameDecoder()
        self.assertEqual([sample['completed_rounds'] for sample in pipe.read_samples()], [1, 2])
        self.assertEqual([sample['completed_rounds'] for sample in pipe.read_samples()], [3, 4])
        self.assertEqual(pipe.samples.qsize(), wire.QUEUE_FRAMES)
        pipe.decode_failed = True
        for discarded in (2, 4):
            with self.assertRaises(ValueError): list(pipe.read_samples())
            self.assertEqual(pipe.discarded_frames, discarded)
            self.assertEqual(pipe.samples.qsize(), wire.QUEUE_FRAMES)
        pipe = namespace['Pipes'].__new__(namespace['Pipes'])
        pipe.samples, pipe.frame_decoder = Queue(maxsize=wire.QUEUE_FRAMES), wire.FrameDecoder()
        pipe.decode_failed, pipe.stream_error, pipe.discarded_frames = False, None, 0
        pipe.line_buffer, pipe.threads = wire.LineBuffer(), []
        pipe.process = SimpleNamespace(poll=lambda: 0, returncode=0)
        pipe.identity = lambda: {'pid': 17, 'birth': '23'}
        pipe.results = {'stdout': {'raw': b'', 'complete': False, 'bytes': 1, 'sha256': '0' * 64},
                        'stderr': {'bytes': 0, 'sha256': '0' * 64}}
        self.assertTrue(pipe.input_state()['frames_complete'])
        self.assertFalse(pipe.input_state()['stdout_fully_retained'])
        result = pipe.result()
        self.assertFalse(result['stdout_complete'])
        self.assertTrue(result['full_input_stream']['stdout_read_to_EOF'])
        self.assertIsNone(result['response'])
        pipe.stream_error = "synthetic incomplete EOF"
        with self.assertRaises(ValueError): list(pipe.read_samples())
        pipe.samples, pipe.stream_error = None, None
        extra = full(); extra['not_in_legacy_projection'] = 'synthetic'
        raw = wire.input_frame(extra, 1)
        pipe.results['stdout'] = {'raw': raw, 'complete': True, 'bytes': len(raw), 'sha256': sha256(raw).hexdigest()}
        final = pipe.result()
        self.assertEqual(final['response'], full())
        self.assertEqual(final['stdout_sha256'], sha256(raw).hexdigest())
        self.assertNotEqual(final['stdout_sha256'], codec.fingerprint(final['response'])['sha256'])

    def test_actual_parent_pipeline_full_first_then_exact_external_reconstruction(self):
        scope = parent_scope()
        value = full(512)
        compact = scope.accept([value])
        self.assertEqual(scope.state()[0], 1)
        self.assertEqual(codec.canonical(codec.restore(compact, scope.store)), codec.canonical(value))
        reference = FrozenCoverage(PLAN).observe(value, job_elapsed_seconds=60, sample_attempt_id=1)
        self.assertEqual({key: compact["coverage_observation"][key] for key in reference}, reference)
        classification = next(i for i, event in enumerate(scope.events) if 'sample-classification' in event)
        self.assertLess(classification, scope.events.index("CAS"))
        self.assertLessEqual(len(codec.canonical(compact)), codec.MAX_REPORT_BYTES)

    def test_known_fatal_drain_precedes_CAS_and_export_UNKNOWN_keeps_classification(self):
        scope, value = parent_scope(budget=0), full()
        value["finance"]["command_inbox"][0]["state"] = "QUARANTINED"
        with self.assertRaisesRegex(ValueError, "synthetic_CAS_quota"): scope.accept([value])
        self.assertLess(scope.events.index("financial_drain"), scope.events.index("CAS"))
        classified = scope.files['synthetic-control/sample-classification.jsonl'][0]
        self.assertIn("terminal_command_failure", classified["fatal_financial_codes"])
        self.assertTrue(any(event.startswith("resource:observer_v2_export_unknown") for event in scope.events))
        self.assertEqual(scope.state()[0], 1)
        self.assertEqual(scope.state()[1].report(60)["samples_observed"], 1)

    def test_classify_safely_rollback_remains_in_actual_shared_path(self):
        class Trip(Coverage):
            def observe(self, sample, **timing):
                result = super().observe(sample, **timing)
                if sample.get('record_origin') != 'supervisor_classification_error_marker':
                    raise ValueError('synthetic after mutation')
                return result
        scope = parent_scope(coverage=Trip(PLAN))
        compact = scope.accept([full()])
        self.assertEqual(scope.state()[1].report(60)["samples_observed"], 1)
        self.assertTrue(compact["coverage_observation"]["technical_read_unknown"])
        self.assertIn('invalid_observer_record_or_classification', scope.namespace['collection_errors'])

    def test_receipt_idempotency_conflict_and_partial_index_UNKNOWN(self):
        compact, receipts, calls = {"synthetic": True, "count": 1}, Receipts(), []
        wire.commit_publication(compact, 1, receipts, lambda _: calls.append('timeline'), lambda _: calls.append('latest'))
        repeated = wire.commit_publication(compact, 1, receipts, lambda _: calls.append('duplicate'), lambda _: calls.append('duplicate'))
        self.assertEqual(calls, ['timeline', 'latest'])
        self.assertEqual(repeated['derived_index_status'], 'UNKNOWN_NOT_RECHECKED')
        with self.assertRaises(ValueError): wire.commit_publication({"synthetic": 1, "count": 1}, 1, receipts, lambda _: None, lambda _: None)
        def failed(_): raise OSError('synthetic index write failure')
        with self.assertRaises(OSError): wire.commit_publication(compact, 2, receipts, failed, lambda _: None)
        self.assertEqual(wire.commit_publication(compact, 2, receipts, lambda _: calls.append('repair'), lambda _: None)['derived_index_status'], 'UNKNOWN_NOT_RECHECKED')
        self.assertNotIn('repair', calls)

    def test_external_timeline_hydrates_before_independent_legacy_coverage(self):
        scope, value = parent_scope(), full()
        compact = scope.accept([value])
        class FakePath:
            def exists(self): return True
            @contextmanager
            def open(self, _): yield io.BytesIO(codec.canonical(compact) + b'\n')
        timeline = scope.namespace['Timeline'](FakePath(), reference_store=scope.store)
        self.assertEqual(timeline.read(), [value])
        fresh = MemoryStore(); fresh.nodes = dict(scope.store.nodes)
        self.assertEqual(codec.restore(compact, fresh), value)
        denied = scope.namespace['Timeline'](FakePath()).read()[0]
        self.assertEqual(denied['record_origin'], 'supervisor_invalid_jsonl_marker')
        independent = FrozenCoverage(PLAN)
        # A new timeline object provides an independent replay from the start.
        restored = scope.namespace['Timeline'](FakePath(), reference_store=scope.store).read()[0]
        expected = FrozenCoverage(PLAN).observe(value, job_elapsed_seconds=60, sample_attempt_id=1)
        self.assertEqual(independent.observe(restored, job_elapsed_seconds=60, sample_attempt_id=1), expected)
        self.assertIsNone(FrozenCoverage(PLAN).observe(denied, job_elapsed_seconds=60, sample_attempt_id=1)['credited_block'])
        key = compact['full_reference']['root']; previous = fresh.nodes.pop(key)
        with self.assertRaises(KeyError): codec.restore(compact, fresh)
        fresh.nodes[key] = previous + b' '
        with self.assertRaises(ValueError): codec.restore(compact, fresh)

    def test_final_once_compact_on_disk_full_in_memory_counted_once(self):
        scope, value = parent_scope(), full()
        result = {'response': value, 'stdout_complete': True, 'exit_code': 0}
        class Child:
            process = SimpleNamespace(wait=lambda **_: 0)
            def __init__(self, *_args, **kwargs): self.wire = kwargs['wire_input']
            def result(self): return result
        namespace = scope.namespace
        namespace.update(Pipes=Child, observer_command=lambda *_args, **_kwargs: ['synthetic-observer'])
        returned = namespace['final_once'](PLAN, Path('synthetic-scratch'), {}, 'final.json',
            publish_full=lambda report: scope.accept([report]))
        self.assertIs(returned['response'], value)
        stored = scope.files['synthetic-scratch/control/final.json']
        self.assertEqual(stored['response_stored_schema'], codec.SCHEMA)
        self.assertEqual(codec.restore(stored['response'], scope.store), value)
        self.assertEqual(scope.state()[0], 1)

    def test_same_actual_metadata_quota_counts_CAS_receipts_and_failure_files(self):
        tree = {'control': {'summary.json': 12}, 'observer': {'timeline.jsonl': 2, 'latest.json': 3,
            'report-v2-nodes': {'node.json': 100}, 'report-v2-publications': {'1.json': 50},
            'v2-export-failure-1.json': 25, 'private-audit': {'private-full-clone-abcdefgh': {'clone.sqlite3': 999}}}}
        values, children = {}, {}
        def visit(path, value):
            is_dir = isinstance(value, dict)
            values[path] = SimpleNamespace(st_mode=(stat.S_IFDIR | 0o700) if is_dir else (stat.S_IFREG | 0o600),
                st_uid=7, st_dev=1, st_ino=len(values) + 1, st_size=0 if is_dir else value)
            if is_dir:
                children[path] = list(value)
                for name, item in value.items(): visit(path + '/' + name, item)
        for path, value in tree.items(): visit(path, value)
        @contextmanager
        def scan(fd): yield [SimpleNamespace(name=name) for name in children[fd]]
        fake_os = SimpleNamespace(scandir=scan,
            open=lambda path, _flags, dir_fd=None: str(path) if dir_fd is None else dir_fd + '/' + str(path),
            stat=lambda name, dir_fd, follow_symlinks: values[dir_fd + '/' + name],
            fstat=lambda fd: values[fd], close=lambda _: None, geteuid=lambda: 7,
            **{name: getattr(os, name) for name in ('O_RDONLY', 'O_DIRECTORY', 'O_NOFOLLOW', 'O_CLOEXEC')})
        namespace = {'os': fake_os, 'stat': stat, 're': re, 'Path': Path, 'GIB': 1024**3,
            'MIN_OUTPUT_BUDGET_BYTES': 1024**3, 'DEFAULT_OUTPUT_BUDGET_BYTES': 6 * 1024**3}
        extract('tools/managed_output_budget.py', {'output_budget_bytes', 'measured_output_bytes'}, namespace)
        self.assertEqual(namespace['output_budget_bytes'](PLAN), 2 * 1024**3)
        self.assertEqual(namespace['measured_output_bytes']('control', 'observer'), 192)

    def test_rehashed_wrong_subtree_count_cannot_reconstruct_a_false_full_report(self):
        scope = parent_scope(); compact = scope.accept([full()])
        publication = codec.strict_json(scope.store.nodes[compact['publication_sha256']])
        reference = codec.strict_json(scope.store.nodes[publication['full_reference']['root']])
        array = reference['value']['finance']['command_inbox'][codec.ARRAY_REF]
        node = codec.strict_json(scope.store.nodes[array['root']]); node['count'] += 1
        def save(value):
            raw = codec.canonical(value); identity = codec.node_hash(raw)
            scope.store.nodes[identity] = raw
            return identity
        array['root'] = save(node)
        publication['full_reference']['root'] = save(reference)
        changed = {**publication, 'publication_sha256': save(publication)}
        with self.assertRaisesRegex(ValueError, 'count_mismatch'):
            codec.restore(changed, scope.store)


if __name__ == '__main__':
    def deny_native(event, args):
        if event in {'sqlite3.connect', 'subprocess.Popen', 'os.fork', 'os.kill', 'os.posix_spawn',
                     'os.link', 'os.remove', 'os.mkdir', 'os.rename', 'fcntl.flock'}:
            raise AssertionError('pipeline pure attempted native effect: ' + event)
        if event == 'open':
            _, mode, flags = args
            if (mode and any(char in mode for char in 'wax+')) or flags & (os.O_WRONLY | os.O_RDWR):
                raise AssertionError('pipeline pure attempted file mutation')
    sys.addaudithook(deny_native)
    unittest.main()
