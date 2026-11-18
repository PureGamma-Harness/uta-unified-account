"""PREP: six SQL-free actual-AST fake methods; no run without a new root GO."""
import ast
from hashlib import sha256
import os
from pathlib import Path, PurePosixPath
from queue import Empty, Queue
import stat
import sys
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / 'tools/probe_observer_v2_adapters.py').read_bytes()
TREE = ast.parse(SOURCE)
BUDGET = ast.literal_eval(next(node.value for node in TREE.body
    if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == 'BUDGET' for target in node.targets)))


def selected(names, namespace):
    nodes = [node for node in ast.walk(TREE) if isinstance(node, (ast.FunctionDef, ast.ClassDef)) and node.name in names]
    if len(nodes) != len(names): raise AssertionError('exact_selected_source_required')
    exec(compile(ast.Module(body=nodes, type_ignores=[]), '<actual-adapter-selected>', 'exec'), namespace)
    return namespace


class AbsoluteMemoryPath(PurePosixPath):
    def absolute(self):
        if not self.is_absolute(): raise AssertionError('fixture_requires_absolute_lexical_path')
        return self


class FakeOS:
    O_RDONLY, O_RDWR, O_WRONLY = os.O_RDONLY, os.O_RDWR, os.O_WRONLY
    O_CLOEXEC, O_NOFOLLOW, O_CREAT, O_EXCL = os.O_CLOEXEC, os.O_NOFOLLOW, os.O_CREAT, os.O_EXCL
    PathLike, defpath, makedev = os.PathLike, os.defpath, staticmethod(os.makedev)
    def __init__(self):
        device = SimpleNamespace(st_mode=stat.S_IFCHR | 0o666, st_rdev=os.makedev(1, 3), st_dev=5, st_ino=8)
        self.before, self.after = device, device
        self.inheritable, self.opens, self.closes, self.outputs = False, [], [], {}
        self.fail_open, self.fail_fstat, self.reads, self.nonblocking = None, None, {}, []
    def lstat(self, path): return self.before
    def open(self, path, flags, *mode):
        if self.fail_open is not None: raise self.fail_open
        descriptor = 80 + len(self.opens)
        self.opens.append((str(path), flags, mode, descriptor)); self.outputs[descriptor] = bytearray()
        return descriptor
    def fstat(self, descriptor):
        if self.fail_fstat is not None: raise self.fail_fstat
        return self.after
    def get_inheritable(self, descriptor): return self.inheritable
    def geteuid(self): return 1000
    def close(self, descriptor): self.closes.append(descriptor)
    def set_blocking(self, descriptor, blocking): self.nonblocking.append((descriptor, blocking))
    def read(self, descriptor, size): return self.reads[descriptor].pop(0)
    def write(self, descriptor, raw): self.outputs[descriptor].extend(raw); return len(raw)
    def fsync(self, descriptor): pass


def child_api(*, missing_birth=False, fail_spawn=False, fail_open=False):
    fake_os, events = FakeOS(), []
    if fail_open: fake_os.fail_open = OSError('fake_open_failure')
    lifecycle = {'launching': False, 'spawned': 0, 'child': None, 'birth': None,
        'constructor_complete': False, 'identity_binding_matches': False}
    child = SimpleNamespace(pid=321, stdout=SimpleNamespace(), stderr=SimpleNamespace())
    def spawn(argv, **kwargs):
        events.append(('spawn', list(argv), kwargs))
        if fail_spawn: raise OSError('fake_spawn_failure')
        return child
    def identity(pid):
        if lifecycle['child'] is not child: raise AssertionError('creation_not_registered_immediately')
        events.append(('identity', pid))
        return {'birth': None if missing_birth else '1234'}
    namespace = {'os': fake_os, 'command': ['fixed-data-emitter'], 'stdin_fd': 31,
        'control': PurePosixPath('/private/control'), 'lifecycle': lifecycle,
        'namespace': {'process_identity': identity}, 'BUDGET': BUDGET,
        'subprocess': SimpleNamespace(PIPE=-1, DEVNULL=-3, Popen=spawn)}
    selected({'StderrEvidence', 'ChildAPI'}, namespace)
    return namespace['ChildAPI'], lifecycle, child, fake_os, events


class StdinOwnershipPure(unittest.TestCase):
    def test_readonly_exact_device_noninheritable_and_flags(self):
        fake = FakeOS()
        function = selected({'open_readonly_stdin'}, {'os': fake, 'stat': stat})['open_readonly_stdin']
        descriptor = function()
        self.assertEqual(descriptor, 80)
        self.assertEqual(fake.opens, [('/dev/null', os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW, (), 80)])
        self.assertEqual(fake.closes, [])

    def test_bad_node_identity_or_inheritable_rejects_and_closes_only_owned_fd(self):
        for kind in ('symlink', 'regular', 'wrong_rdev', 'changed_inode', 'inheritable', 'fstat_error'):
            with self.subTest(kind=kind):
                fake = FakeOS()
                if kind == 'symlink': fake.before = SimpleNamespace(st_mode=stat.S_IFLNK, st_rdev=0)
                if kind == 'regular': fake.before = SimpleNamespace(st_mode=stat.S_IFREG, st_rdev=0)
                if kind == 'wrong_rdev': fake.before = SimpleNamespace(st_mode=stat.S_IFCHR, st_rdev=os.makedev(1, 5))
                if kind == 'changed_inode':
                    fake.after = SimpleNamespace(st_mode=stat.S_IFCHR, st_rdev=os.makedev(1, 3), st_dev=5, st_ino=9)
                if kind == 'inheritable': fake.inheritable = True
                if kind == 'fstat_error': fake.fail_fstat = OSError('fake_fstat')
                function = selected({'open_readonly_stdin'}, {'os': fake, 'stat': stat})['open_readonly_stdin']
                with self.assertRaises((ValueError, OSError)): function()
                self.assertEqual(fake.closes, [80] if fake.opens else [])
                self.assertLessEqual(len(fake.opens), 1)

    def test_allowlisted_stdin_substitution_registers_before_identity_and_preserves_pipe_args(self):
        api, state, child, fake, events = child_api()
        self.assertIs(api.Popen(['fixed-data-emitter'], stdin=-3, stdout=-1, stderr=-1, close_fds=True), child)
        self.assertEqual(events[0][2]['stdin'], 31)
        self.assertEqual((events[0][2]['stdout'], events[0][2]['stderr']), (-1, -1))
        self.assertEqual(state['birth'], '1234')
        self.assertFalse(state['launching'])
        self.assertEqual(fake.closes, [])
        for argv, stdin in ((['fixed-data-emitter'], -3), (['other'], -3), (['fixed-data-emitter'], 99)):
            with self.assertRaises(RuntimeError): api.Popen(argv, stdin=stdin)
        self.assertEqual(len(events), 2)
        for stdin in (99, None, True):
            fresh, fresh_state, _, fresh_os, _ = child_api()
            with self.assertRaisesRegex(RuntimeError, 'stdin_substitution'):
                fresh.Popen(['fixed-data-emitter'], stdin=stdin)
            self.assertEqual(fresh_state['spawned'], 0)
            self.assertEqual(fresh_os.opens, [])

    def test_open_spawn_and_birth_failure_leave_bounded_registered_state(self):
        for kind in ('open', 'spawn', 'birth'):
            with self.subTest(kind=kind):
                api, state, child, fake, events = child_api(missing_birth=kind == 'birth',
                    fail_spawn=kind == 'spawn', fail_open=kind == 'open')
                with self.assertRaises((ValueError, OSError)):
                    api.Popen(['fixed-data-emitter'], stdin=-3, stdout=-1, stderr=-1)
                self.assertFalse(state['launching'])
                self.assertEqual(state['spawned'], 1)
                self.assertIs(state['child'], child if kind == 'birth' else None)
                self.assertIsNone(state['birth'])
                self.assertEqual(fake.closes, [] if kind == 'open' else [80])
                with self.assertRaises(RuntimeError): api.Popen(['fixed-data-emitter'], stdin=-3)

    def test_partial_constructor_cooperates_preserves_bytes_and_unknown_birth_never_passes(self):
        for stuck in (False, True):
            with self.subTest(stuck=stuck):
                fake, sealed, tick = FakeOS(), {}, [0.0]
                release = SimpleNamespace(created=False, exists=lambda: release.created)
                def seal(path, value):
                    sealed[str(path)] = value
                    if path is release: release.created = True
                class Stream:
                    def __init__(self, descriptor): self.descriptor, self.closed = descriptor, False
                    def fileno(self): return self.descriptor
                    def close(self): self.closed = True
                child = SimpleNamespace(pid=321, stdout=Stream(11), stderr=Stream(12))
                fake.reads = {11: [b'abc', b''], 12: [b'err', b'']}
                child.poll = lambda: None if stuck or not release.created or any(fake.reads.values()) else 0
                def monotonic(): tick[0] += .05; return tick[0]
                def sleep(amount): tick[0] += amount
                threads = [SimpleNamespace(ident=1, is_alive=lambda: False, join=lambda timeout: None) for _ in range(2)] if stuck else []
                pipe = SimpleNamespace(threads=threads, samples=Queue(), results={})
                state = {'child': child, 'birth': '1234' if stuck else None,
                    'constructor_complete': stuck, 'identity_binding_matches': stuck}
                function = selected({'cleanup_owned_adapter'}, {'os': fake, 'time': SimpleNamespace(monotonic=monotonic, sleep=sleep),
                    'Empty': Empty, 'seal': seal, 'BUDGET': BUDGET, 'codec': SimpleNamespace(FLAGS={}),
                    'measured_output_bytes': lambda *_: 0})['cleanup_owned_adapter']
                if stuck:
                    with self.assertRaisesRegex(RuntimeError, 'cleanup_unknown'):
                        function(pipe, state, release, PurePosixPath('/private/control'))
                    self.assertLess(tick[0], 2.5)
                else:
                    result = function(pipe, state, release, PurePosixPath('/private/control'))
                    self.assertFalse(result['birth_identity_established'])
                    self.assertFalse(result['Pipes_constructor_completed'])
                    self.assertEqual(result['constructor_fallback'], {'stdout': {'bytes': 3, 'EOF': True}, 'stderr': {'bytes': 3, 'EOF': True}})
                    self.assertEqual([bytes(item) for item in fake.outputs.values()], [b'abc', b'err'])
                    self.assertTrue(child.stdout.closed and child.stderr.closed)
                    self.assertEqual(fake.nonblocking, [(11, False), (12, False)])

    def test_actual_execute_finally_closes_stdin_and_write_audit_is_not_relaxed(self):
        for fail, close_fail in ((False, False), (True, False), (True, True)):
            with self.subTest(fail=fail, close_fail=close_fail):
                fake = FakeOS()
                original_close = fake.close
                def close(descriptor):
                    original_close(descriptor)
                    if close_fail: raise OSError('fake_close_failure')
                fake.close = close
                class MemoryPath(AbsoluteMemoryPath):
                    def exists(self): return False
                    def is_symlink(self): return False
                    def lstat(self): return SimpleNamespace(st_mode=stat.S_IFDIR | 0o700, st_uid=1000)
                    def mkdir(self, **kwargs): pass
                    def read_bytes(self): return b'fake-source'
                original = RuntimeError('fake_primary')
                def body(*args):
                    if fail: raise original
                    return {'result': 'fake-only'}
                namespace = {'ADAPTER_PARENT': MemoryPath('/private/runs'), 'os': fake, 'stat': stat,
                    'seal': lambda *_: None, 'BUDGET': BUDGET, 'time': SimpleNamespace(time_ns=lambda: 1),
                    'sha256': sha256, 'Path': MemoryPath, 'sys': sys, '__file__': '/fake/probe.py',
                    'open_readonly_stdin': lambda: 31, 'execute_with_stdin': body}
                function = selected({'execute'}, namespace)['execute']
                if fail:
                    with self.assertRaises(RuntimeError) as captured: function(MemoryPath('/private/runs/new'))
                    self.assertIs(captured.exception, original)
                else: self.assertEqual(function(MemoryPath('/private/runs/new')), {'result': 'fake-only'})
                self.assertEqual(fake.closes, [31])
        audit = selected({'audit'}, {'os': FakeOS(), 'Path': AbsoluteMemoryPath,
            'output': PurePosixPath('/private/new'), 'lifecycle': {'launching': False}, 'command': ['fixed']})['audit']
        with self.assertRaisesRegex(RuntimeError, 'write_outside'):
            audit('open', ('/dev/null', None, os.O_RDWR))
        audit('open', ('/private/new/control/new.json', None, os.O_WRONLY | os.O_CREAT))
        constructor_try = next(node for node in ast.walk(next(node for node in TREE.body
            if isinstance(node, ast.FunctionDef) and node.name == 'execute_with_stdin'))
            if isinstance(node, ast.Try) and any(isinstance(item, ast.Expr) and isinstance(item.value, ast.Call)
                and isinstance(item.value.func, ast.Attribute) and item.value.func.attr == '__init__' for item in node.body))
        self.assertTrue(any(isinstance(item, ast.Call) and isinstance(item.func, ast.Name)
            and item.func.id == 'cleanup_owned_adapter' for statement in constructor_try.finalbody for item in ast.walk(statement)))


if __name__ == '__main__':
    def forbid_effect(event, args):
        if event in {'subprocess.Popen', 'os.fork', 'os.posix_spawn', 'os.kill', 'os.killpg',
                     'sqlite3.connect', 'socket.connect', 'socket.bind', 'ctypes.dlopen'}:
            raise RuntimeError('pure_fixture_forbidden_effect:' + event)
        if event == 'open':
            _, mode, flags = args
            if (mode and any(item in mode for item in 'wax+')) or flags & (os.O_WRONLY | os.O_RDWR):
                raise RuntimeError('pure_fixture_forbidden_write')
    sys.addaudithook(forbid_effect)
    unittest.main()
