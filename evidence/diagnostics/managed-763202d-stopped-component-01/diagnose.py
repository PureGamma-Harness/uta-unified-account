"""One approved stopped diagnostic; original files are filesystem-copy inputs only."""
from contextlib import contextmanager
from datetime import datetime, timezone
from hashlib import sha256
import importlib.util
import json
import os
from pathlib import Path
import re
import resource
import selectors
import signal
import sqlite3
import stat
import subprocess
import sys
import time

sys.dont_write_bytecode = True
os.umask(0o077)
HERE = Path(__file__).resolve().parent
SOURCE = Path('/workspace/uta-managed-observer-runs/763202d-six-hours-20261117/job')
CODE = Path('/workspace/uta-operations-freeze-763202d')
OBSERVER = Path('/workspace/uta-managed-observer')
CLONE = HERE / 'clone'
PYTHON = '/opt/codex/runtimes/codex-primary-runtime/dependencies/python/bin/python'
DATABASES = ('checkpoint.sqlite3', 'managed/router.sqlite3', 'managed/shard-0000.sqlite3')
CAP, HEADROOM, PIPE_CAP = 6 * 1024**3, 1024**3, 4 * 1024**2
FLAGS = dict(continuous_6h_stability_passed=False, continuous_24h_stability_passed=False,
             capacity_10000_per_s_passed=False, production_approved=False,
             financial_final_evidence_eligible=False, strict_receipt_issued=False)


def utc():
    return datetime.now(timezone.utc).isoformat()


def write(name, value):
    with (HERE / name).open('x') as stream:
        json.dump(value, stream, sort_keys=True, indent=2, allow_nan=False)
        stream.write('\n')


def load(path):
    return json.loads(path.read_text())


def proc(pid, expected):
    try:
        fields = Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()
    except FileNotFoundError:
        return dict(pid=pid, birth=None, expected_birth=str(expected), state='missing', known_stopped=True)
    match = fields[19] == str(expected)
    return dict(pid=pid, birth=fields[19], expected_birth=str(expected), state=fields[0],
                known_stopped=not match or fields[0] in {'Z', 'X', 'x'})


def selected():
    paths = set(DATABASES) | {'job.json', 'progress.json', 'bootstrap-plan.json',
        'pending-market.json', 'log-segments.json', 'validation/summary.json',
        'validation/worker-result.json', 'validation/unittest.txt'}
    for name in DATABASES:
        main = SOURCE / name
        for path in main.parent.iterdir():
            if path.name.startswith(main.name + '-'):
                paths.add(path.relative_to(SOURCE).as_posix())
    manifest = load(SOURCE / 'log-segments.json')
    for item in manifest['segments']:
        path = Path(item['file'])
        if path.is_absolute() or len(path.parts) != 2 or path.parts[0] != 'logs' or path.suffix != '.gz':
            raise ValueError('unsafe_log_segment_path')
        paths.add(path.as_posix())
    for path in (SOURCE / 'logs').iterdir():
        if re.fullmatch(r'events-[0-9]{9,}-[0-9]{9,}\.jsonl\.tmp', path.name):
            paths.add(path.relative_to(SOURCE).as_posix())
    for name in ('job.json.tmp', 'progress.json.tmp', 'bootstrap-plan.json.tmp',
                 'pending-market.json.tmp', 'log-segments.json.tmp'):
        if (SOURCE / name).exists():
            paths.add(name)
    return sorted(paths)


def inventory():
    result = {}
    for name in selected():
        path = SOURCE / name
        for parent in path.relative_to(SOURCE).parents:
            if not stat.S_ISDIR((SOURCE / parent).stat(follow_symlinks=False).st_mode):
                raise ValueError('source_parent_not_direct_directory')
        details = path.stat(follow_symlinks=False)
        if not stat.S_ISREG(details.st_mode):
            raise ValueError('source_member_not_direct_regular_file')
        digest = sha256()
        with path.open('rb') as stream:
            for chunk in iter(lambda: stream.read(1024**2), b''):
                digest.update(chunk)
        result[name] = dict(bytes=details.st_size, dev=details.st_dev, ino=details.st_ino,
            mtime_ns=details.st_mtime_ns, mode=stat.S_IMODE(details.st_mode), sha256=digest.hexdigest())
    return result


@contextmanager
def read_clone(relative):
    path = CLONE / relative
    if not path.resolve(strict=True).is_relative_to(CLONE.resolve()) or path.is_symlink():
        raise ValueError('clone_only_sqlite_path_required')
    connection = sqlite3.connect(path.as_uri() + '?mode=ro', uri=True, timeout=2, isolation_level=None)
    connection.row_factory = sqlite3.Row
    try:
        connection.execute('PRAGMA query_only=ON')
        def authorize(action, first, second, _db, _source):
            if action in {sqlite3.SQLITE_SELECT, sqlite3.SQLITE_READ, sqlite3.SQLITE_FUNCTION,
                          sqlite3.SQLITE_TRANSACTION, getattr(sqlite3, 'SQLITE_RECURSIVE', 33)}:
                return sqlite3.SQLITE_OK
            if action == sqlite3.SQLITE_PRAGMA and first.lower() in {
                    'query_only', 'quick_check', 'foreign_key_check', 'table_info'} and second is None:
                return sqlite3.SQLITE_OK
            return sqlite3.SQLITE_DENY
        connection.set_authorizer(authorize)
        connection.execute('BEGIN')
        yield connection
    finally:
        connection.close()


def checkpoint():
    with read_clone('checkpoint.sqlite3') as connection:
        rows = list(connection.execute('SELECT sequence,state FROM rounds ORDER BY sequence'))
        states = {r[0]: json.loads(r[1]) for r in connection.execute(
            "SELECT key,value FROM state WHERE key IN ('started_boottime_ns','boot_id','controller_sessions','logs_verified')")}
        head = connection.execute('SELECT sequence,event_hash FROM events ORDER BY sequence DESC LIMIT 1').fetchone()
        unresolved = connection.execute("SELECT COUNT(*) FROM steps WHERE state!='DONE'").fetchone()[0]
        faults = connection.execute("SELECT COUNT(*) FROM faults WHERE state!='DONE'").fetchone()[0]
    if [tuple(r) for r in rows] != [(n, 'DONE') for n in range(1, 514)] or unresolved or faults:
        raise ValueError('clone_not_actual_stable_513_round_boundary')
    baseline = load(HERE / 'original-baseline.json')
    if (states['started_boottime_ns'] != baseline['started_boottime_ns']
            or states['boot_id'] != baseline['boot_id'] or states['controller_sessions'] != 1
            or states['logs_verified'] is not True):
        raise ValueError('original_checkpoint_clock_session_or_log_state_changed')
    return dict(event_head=dict(sequence=head[0], hash=head[1]), completed=513,
                unresolved_steps=unresolved, unresolved_faults=faults, states=states)


def component(stage):
    if stage == 'lease':
        with read_clone('managed/shard-0000.sqlite3') as connection:
            row = connection.execute('SELECT generation,owner_pid,boot_id,expires_ns,observed_ns FROM writer_fence_lease WHERE singleton=1').fetchone()
        if row is None:
            raise ValueError('native_lease_missing')
        lease = dict(row)
        with read_clone('managed/router.sqlite3') as connection:
            owners = [dict(r) for r in connection.execute('SELECT kind,shard,generation,pid,start_ticks,boot_id FROM router_process_owners ORDER BY sequence')]
        identities = [proc(r['pid'], r['start_ticks']) for r in owners if r['pid'] is not None]
        boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
        now = time.clock_gettime_ns(time.CLOCK_BOOTTIME)
        expired = (lease['boot_id'] == boot == load(HERE / 'original-baseline.json')['boot_id']
            and type(lease['expires_ns']) is int and type(lease['observed_ns']) is int
            and 0 <= lease['observed_ns'] <= lease['expires_ns'] <= now
            and all(item['known_stopped'] for item in identities))
        write('lease-result.json', dict(synthetic=True, redacted=True, lease=lease,
            observed_boottime_ns=now, registered_processes=identities,
            native_lease_expired=expired, **FLAGS))
        return 0 if expired else 2
    sys.path.insert(0, str(OBSERVER))
    from tools import managed_observer_finance as finance
    from tools import managed_soak_observer as core
    before = checkpoint()
    with read_clone('managed/shard-0000.sqlite3') as connection:
        result = finance.read_financial(connection, 5400, 513, compare_golden=True)
    after = checkpoint()
    logs = core.verify_logs(CLONE, after['event_head'])
    if before != after:
        raise ValueError('clone_checkpoint_crossed_financial_snapshot')
    write(stage + '-result.json', dict(synthetic=True, redacted=True,
        checkpoint=after, finance=result, logs=logs,
        component_passed=result['golden']['passed'] and not result['retry_alerts'], **FLAGS))
    return 0 if result['golden']['passed'] and not result['retry_alerts'] else 2


def bounded_child(label, command, limit):
    command = ['bwrap', '--die-with-parent', '--ro-bind', '/', '/', '--dev', '/dev',
        '--proc', '/proc', '--bind', str(HERE), str(HERE), '--', *command]
    process = subprocess.Popen(command, cwd=CODE, stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, close_fds=True, start_new_session=True)
    birth = Path(f'/proc/{process.pid}/stat').read_text().rsplit(')', 1)[1].split()[19]
    selector, buffers, digests = selectors.DefaultSelector(), {}, {}
    for name, pipe in [('stdout', process.stdout), ('stderr', process.stderr)]:
        selector.register(pipe, selectors.EVENT_READ, name)
        buffers[name], digests[name] = bytearray(), sha256()
    started, deadline = utc(), time.monotonic() + limit
    try:
        while selector.get_map():
            if time.monotonic() >= deadline:
                raise TimeoutError('owned_diagnostic_child_timeout')
            for key, _ in selector.select(.05):
                chunk = os.read(key.fileobj.fileno(), 65536)  # Only this new child's PIPE.
                if not chunk:
                    selector.unregister(key.fileobj)
                    key.fileobj.close()
                    continue
                buffers[key.data].extend(chunk)
                digests[key.data].update(chunk)
                if len(buffers[key.data]) > PIPE_CAP:
                    raise ValueError('owned_diagnostic_child_pipe_cap')
        code = process.wait(timeout=max(.001, deadline-time.monotonic()))
    except BaseException:
        if process.poll() is None and not proc(process.pid, birth)['known_stopped']:
            os.killpg(process.pid, signal.SIGKILL)
        process.wait(timeout=2)
        raise
    finally:
        selector.close()
        for pipe in (process.stdout, process.stderr):
            pipe.close()
    for name, buffer in buffers.items():
        (HERE / (label + '-' + name + '.private.txt')).write_bytes(buffer)
    result = dict(started_at=started, finished_at=utc(), pid=process.pid, birth=birth, exit_code=code,
                  stream_sha256={name: digest.hexdigest() for name, digest in digests.items()})
    write(label + '-child.json', result)
    return result, buffers


def parent():
    started, started_mono = utc(), time.monotonic()
    pid = os.getpid()
    birth = Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()[19]
    def expired(*_):
        raise TimeoutError('shared_outer_180_seconds')
    signal.signal(signal.SIGALRM, expired)
    signal.alarm(180)
    active = None
    try:
        public = SOURCE.parent / 'control'
        progress, final = load(SOURCE / 'progress.json'), load(public / 'final-summary.json')
        original = load(public / 'producer-result.json')
        baseline = load(SOURCE.parent / 'observer/baseline.json')
        if (progress['status'] != 'paused' or progress['rounds'] != {'DONE': 513}
                or progress['elapsed_seconds'] != 2072.722098933 or progress['controller_sessions'] != 1
                or original['exit_code'] != 2 or final['financial_final_evidence_eligible'] is not False):
            raise ValueError('original_terminal_contract_changed')
        previous = load(Path('/workspace/uta-managed-resource-incident/evidence/incidents/managed-763202d-resource-race/capture-metadata.json'))
        identities = [proc(item['pid'], item['expected_birth']) for item in previous['process_metadata']]
        if len(identities) != 25 or not all(item['known_stopped'] for item in identities):
            raise ValueError('published_original_process_not_stopped')
        if baseline['boot_id'] != Path('/proc/sys/kernel/random/boot_id').read_text().strip():
            raise ValueError('original_boot_changed')
        write('original-baseline.json', baseline)
        write('original-terminal.json', dict(progress=progress, final=final, producer=original,
                                            process_metadata=identities))
        initial = inventory()
        estimate = sum(item['bytes'] for item in initial.values())
        free = os.statvfs(HERE).f_bavail * os.statvfs(HERE).f_frsize
        if estimate > CAP or free < estimate + HEADROOM:
            raise ValueError('copy_budget_unavailable')
        meta = load(SOURCE / 'job.json')
        for name in DATABASES:
            info = initial[name]
            if [info['dev'], info['ino']] != meta['file_identities'][str(SOURCE / name)]:
                raise ValueError('original_main_identity_changed')
        write('source-inventory-before.json', initial)
        write('ready.json', dict(started_at=started, pid=pid, birth=birth, source_selected_files=len(initial),
            source_copy_bytes=estimate, free_bytes=free, cpu=sorted(os.sched_getaffinity(0)), **FLAGS))
        print(json.dumps(load(HERE / 'ready.json')), flush=True)
        while not (HERE / 'start-copy').exists():
            if time.monotonic() - started_mono > 25:
                raise TimeoutError('start_handoff_not_released')
            time.sleep(.05)
        CLONE.mkdir(mode=0o700)
        copied = 0
        for name, expected in initial.items():
            destination = CLONE / name
            destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            digest = sha256()
            with (SOURCE / name).open('rb') as source, destination.open('xb') as output:
                for chunk in iter(lambda: source.read(65536), b''):
                    copied += len(chunk)
                    if copied > CAP:
                        raise ValueError('clone_byte_budget_exceeded')
                    digest.update(chunk)
                    output.write(chunk)
            if digest.hexdigest() != expected['sha256']:
                raise ValueError('copied_source_bytes_changed')
        after_copy = inventory()
        write('source-inventory-after-copy.json', after_copy)
        if after_copy != initial:
            raise ValueError('source_changed_during_copy')
        lease, _ = bounded_child('lease', [PYTHON, '-B', str(Path(__file__).resolve()), 'lease'], 10)
        if lease['exit_code'] != 0 or load(HERE / 'lease-result.json')['native_lease_expired'] is not True:
            raise ValueError('native_lease_expiry_not_proven')
        audit, streams = bounded_child('original-producer-audit', [PYTHON, '-B',
            'benchmarks/run_managed_soak.py', 'audit', '--directory', str(CLONE)], 30)
        refused = (audit['exit_code'] != 0 and not streams['stdout'] and
            b'final audit requires a completed, stopped authority' in streams['stderr'])
        if not refused:
            raise ValueError('unmodified_producer_paused_refusal_not_observed')
        first, _ = bounded_child('finance-before', [PYTHON, '-B', str(Path(__file__).resolve()), 'finance-before'], 45)
        if first['exit_code'] != 0:
            raise ValueError('first_independent_component_not_passed')
        second, _ = bounded_child('finance-after', [PYTHON, '-B', str(Path(__file__).resolve()), 'finance-after'], 45)
        if second['exit_code'] != 0:
            raise ValueError('independent_reopen_component_not_passed')
        a, b = load(HERE / 'finance-before-result.json'), load(HERE / 'finance-after-result.json')
        same = a['checkpoint'] == b['checkpoint'] and a['finance']['watermark'] == b['finance']['watermark']
        if not same:
            raise ValueError('independent_reopen_watermark_changed')
        end_inventory = inventory()
        write('source-inventory-after-diagnostic.json', end_inventory)
        if initial != end_inventory:
            raise ValueError('source_changed_during_diagnostic')
        clone_bytes = sum(path.stat().st_size for path in HERE.rglob('*') if path.is_file())
        if clone_bytes > CAP or os.statvfs(HERE).f_bavail * os.statvfs(HERE).f_frsize < HEADROOM:
            raise ValueError('diagnostic_disk_budget_exceeded')
        result = dict(synthetic=True, redacted=True, component_diagnostic='PASS',
            started_at=started, finished_at=utc(), duration_seconds=time.monotonic()-started_mono,
            pid=pid, birth=birth, copied_bytes=copied, source_inventory_unchanged=True,
            native_lease_expired=True, unmodified_original_audit='REFUSED_PAUSED_EXPECTED',
            independent_reopen_same_watermark=same, checkpoint=b['checkpoint'],
            counts=b['finance']['counts'], golden=b['finance']['golden'], logs=b['logs'],
            residuals=b['finance']['residuals'], gross_debt=b['finance']['gross_debt'],
            retry_alert_count=len(b['finance']['retry_alerts']), watermark=b['finance']['watermark'],
            original_six_hour_gate='NO_GO', original_financial_final_gate='NO_GO', original_coverage_gate='NO_GO',
            full_business_event_reexecution=None, full_risk_reexecution=None, **FLAGS)
        write('public-result.json', result)
        print(json.dumps(result), flush=True)
        return 0
    except BaseException as error:
        result = dict(synthetic=True, redacted=True, component_diagnostic='UNKNOWN_OR_FAILED',
            started_at=started, finished_at=utc(), duration_seconds=time.monotonic()-started_mono,
            pid=pid, birth=birth, error_type=type(error).__name__,
            error_digest=sha256(str(error).encode()).hexdigest(),
            original_six_hour_gate='NO_GO', original_financial_final_gate='NO_GO', original_coverage_gate='NO_GO', **FLAGS)
        write('public-result.json', result)
        print(json.dumps(result), flush=True)
        return 2
    finally:
        signal.alarm(0)


if __name__ == '__main__':
    resource.setrlimit(resource.RLIMIT_AS, (2 * 1024**3, 2 * 1024**3))
    raise SystemExit(component(sys.argv[1]) if len(sys.argv) == 2 else parent())
