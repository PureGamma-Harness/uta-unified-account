"""Root's concrete phase authorization recorder. Metadata only; never invokes."""
from pathlib import Path
import argparse, time, os, json, hashlib, importlib.util, subprocess

parser = argparse.ArgumentParser()
parser.add_argument('--stage', required=True)
parser.add_argument('--wait-seconds', type=float, default=75)
parser.add_argument('--capture-when-fresh', action='store_true')
args = parser.parse_args()
assert 0 < args.wait_seconds <= 75
base = Path('/workspace/uta-managed-909acec-prepare')
profile = base / 'benchmarks/profiles/managed-909acec-v2-qualified-conditional.json'
consumer = base / 'evidence/preparations/managed-909acec-v2/consume_guard.py'
profile_sha = '8f48d7835c3b3d3ad53fbebfe955c611ba815adbddfe3281fb008fdd4b99c87a'
assert hashlib.sha256(profile.read_bytes()).hexdigest() == profile_sha
assert hashlib.sha256(consumer.read_bytes()).hexdigest() == 'f31cca779de58db8fedfd31c5f48069483cffa67c803aea6327ee73fcf930602'
spec = importlib.util.spec_from_file_location('root_specific_phase_guard', consumer)
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)
commands = json.loads((base / 'evidence/preparations/managed-909acec-v2/exact-phase-commands.json').read_text())
item = next(row for row in commands['stages'] if row['stage'] == args.stage)
assert guard.command_sha256(item['argv']) == item['command_sha256']
assert commands['profile_sha256'] == profile_sha
start_wall = time.time_ns()
deadline = time.monotonic() + args.wait_seconds
seen_original_latest = set()
while time.monotonic() < deadline:
    if args.capture_when_fresh:
        latest_path = Path('/workspace/uta-soak-runs/formal-20261116T213613Z-88755a9/observer-20261116T221001Z-f96dfd8/latest.json')
        try:
            old_latest = json.loads(latest_path.read_bytes())
            original_time = old_latest.get('observed_ns')
            age = (time.time_ns() - original_time) / 1e9 if type(original_time) is int else -1
            if 0 <= age <= 8 and original_time not in seen_original_latest:
                seen_original_latest.add(original_time)
                capture = base / 'evidence/preparations/managed-909acec-v2/fresh_admission_capture_r2b.py'
                if not capture.exists():
                    capture = Path('/tmp/uta-managed-909-fresh-admission-capture-r2b.py')
                assert hashlib.sha256(capture.read_bytes()).hexdigest() == '57e87ce1bd10863821cbd0392957515da3b4613b2c756c1c986c947217654aa6'
                snapshot_path = Path('/tmp') / f'uta-909-admission-root-{args.stage}-{time.time_ns()}.json'
                capture_command = [str(json.loads(profile.read_bytes())['python']), '-B', str(capture),
                    '--profile-sha256', profile_sha, '--phase', item['phase'],
                    '--command-sha256', item['command_sha256'], '--output', str(snapshot_path)]
                result = subprocess.run(capture_command, capture_output=True, text=True, timeout=15)
                print(json.dumps({'metadata_only_capture_command': capture_command,
                    'exit_code': result.returncode, 'stdout': result.stdout,
                    'stderr_sha256': hashlib.sha256(result.stderr.encode()).hexdigest()}), flush=True)
        except (OSError, ValueError, TypeError, subprocess.TimeoutExpired):
            pass
    for snapshot in sorted(Path('/tmp').glob('uta-909-admission-*.json'), key=lambda p: p.stat().st_mtime_ns, reverse=True):
        try:
            before = snapshot.stat()
            if before.st_mtime_ns < start_wall:
                continue
            raw = snapshot.read_bytes()
            after = snapshot.stat()
            if (before.st_ino, before.st_size, before.st_mtime_ns) != (after.st_ino, after.st_size, after.st_mtime_ns):
                continue
            record = json.loads(raw)
        except (OSError, json.JSONDecodeError):
            continue
        if record.get('phase') != item['phase'] or record.get('phase_command_sha256') != item['command_sha256']:
            continue
        if record.get('status') != 'ADMISSION_METADATA_COMPONENT_PASS_NOT_PHASE_GO':
            continue
        go = {'authorized': True, 'phase': item['phase'], 'stage': args.stage,
            'profile_sha256': profile_sha, 'snapshot_sha256': hashlib.sha256(raw).hexdigest(),
            'command_sha256': item['command_sha256'], 'snapshot_file': str(snapshot),
            'exact_argv': item['argv'], 'record': item['record'],
            'scope': 'ONLY this exact stage once; no other stage or long-run blanket permission',
            'outer_smoke_seconds': 150,
            'root_static_review': 'final909 full3/CI8/package721 peer5c981; b6c fixedv2; capacity204ecc+2ee819e consumer final review'}
        try:
            checked = guard.consume_guard(profile, item['argv'], snapshot, go,
                now_wall_ns=time.time_ns(), now_boottime_ns=time.clock_gettime_ns(time.CLOCK_BOOTTIME),
                current_boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip())
        except ValueError:
            continue
        if checked['remaining_validity_ns'] < 5_000_000_000:
            continue
        go['root_approved_wall_ns'] = time.time_ns()
        go['guard_result'] = checked
        path = Path('/tmp') / f'uta-909-root-go-{item["phase"]}-{go["root_approved_wall_ns"]}.json'
        encoded = (json.dumps(go, sort_keys=True, indent=2) + '\n').encode()
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, 'wb') as stream:
            stream.write(encoded); stream.flush(); os.fsync(stream.fileno())
        print(json.dumps({'specific_phase_go': item['phase'], 'stage': args.stage,
            'go_file': str(path), 'go_sha256': hashlib.sha256(encoded).hexdigest(),
            'snapshot_file': str(snapshot), 'snapshot_sha256': go['snapshot_sha256'],
            'remaining_validity_ns_at_root_check': checked['remaining_validity_ns']}), flush=True)
        raise SystemExit(0)
    time.sleep(.05)
print(json.dumps({'specific_phase_go': False, 'stage': args.stage, 'reason': 'no_new_matching_unexpired_snapshot_before_deadline'}), flush=True)
raise SystemExit(2)
