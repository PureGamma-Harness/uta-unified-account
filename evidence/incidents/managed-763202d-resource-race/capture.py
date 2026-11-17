"""Read only original public JSON/proc/source metadata; never open SQLite."""
from datetime import datetime, timezone
import gzip
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import time

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
JOB = Path('/workspace/uta-managed-observer-runs/763202d-six-hours-20261117')
OBSERVER = Path('/workspace/uta-managed-observer')
PRODUCER = Path('/workspace/uta-operations-freeze-763202d')
FLAGS = {'continuous_6h_stability_passed', 'continuous_24h_stability_passed',
         'capacity_10000_per_s_passed', 'production_approved'}
PUBLIC_FILES = [
    'control/final-summary.json', 'control/producer-result.json',
    'control/final-before-cold.json', 'control/final-after-cold.json',
    'control/strict-producer-cold-result.json', 'control/live-coverage.json',
    'control/launch.json', 'control/observer-identity.json',
    'control/supervisor-identity.json', 'control/initial-handoff.json',
    'control/supervisor-heartbeat.json', 'observer/watch-cli-identity.json',
    'observer/baseline.json', 'observer/latest.json', 'job/progress.json',
]
SAMPLE_FIELDS = FLAGS | set('active_elapsed_seconds active_rounds alerts completed_rounds '
    'contract_sha256 control_lane driver final_evidence_eligible finance financial_ready format '
    'frozen_commit listener logical_point observation_only observer_is_formal_signoff '
    'original_deadline_boottime_ns original_start_boottime_ns planned_faults planned_rounds '
    'progress_age_seconds redacted sample_wall_ns synthetic unresolved_faults unresolved_steps '
    'worker error_digest error_type'.split())
CLASS_FIELDS = set('coverage_status credited_block fatal_financial_codes financial_golden_state '
    'job_elapsed_seconds planned_fault_inflight_unknown sample_attempt_id sample_wall_ns '
    'technical_read_unknown timing_source'.split())


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def write(name, value):
    (OUT / name).write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def scrub(value):
    if isinstance(value, dict):
        # The allowed files are frozen public projections, never authority/profile dumps.
        assert not any(key.lower() in {'owner_nonce', 'secret', 'hmac_secret', 'private_key',
                                      'authorization', 'password', 'audience'} for key in value)
        return {key: scrub(item) for key, item in value.items()}
    if isinstance(value, list):
        return [scrub(item) for item in value]
    if isinstance(value, str):
        return value.replace(str(JOB), '<ORIGINAL_JOB>')
    return value


def proc(pid, birth):
    try:
        raw = (Path('/proc') / str(pid) / 'stat').read_bytes()
    except FileNotFoundError:
        return dict(pid=pid, expected_birth=birth, state='missing', identity_matches=False,
                    alive=False, known_stopped=True)
    except OSError as error:
        return dict(pid=pid, expected_birth=birth, state='unavailable', error_type=type(error).__name__,
                    alive=False, known_stopped=False)
    fields = raw.decode().rsplit(')', 1)[1].split()
    matches = fields[19] == str(birth)
    return dict(pid=pid, expected_birth=birth, observed_birth=fields[19], state=fields[0],
                parent_pid=int(fields[1]), identity_matches=matches,
                alive=matches and fields[0] not in {'Z', 'X', 'x'},
                known_stopped=not matches or fields[0] in {'Z', 'X', 'x'},
                proc_stat_sha256=sha256(raw).hexdigest())


started = datetime.now(timezone.utc).isoformat()
sources, records, identities = {}, {}, set()
for relative in PUBLIC_FILES:
    path = JOB / relative
    raw = path.read_bytes()
    value = json.loads(raw)
    sources[relative] = dict(sha256=sha256(raw).hexdigest(), bytes=len(raw),
                             mtime_ns=path.stat().st_mtime_ns)
    # Explicit source-path allowlist; core public schema reviewed at frozen ce3045f.
    records[relative] = scrub(value)
    if relative == 'control/launch.json':
        identities.add((value['driver_pid'], value['driver_birth']))
    if relative.endswith('identity.json'):
        identities.add((value['pid'], value['birth']))
    if isinstance(value.get('identity'), dict):
        identities.add((value['identity']['pid'], value['identity']['birth']))
write('original-public-records.json', records)

counts = {}
for relative, allowed, target in [
    ('observer/timeline.jsonl', SAMPLE_FIELDS, 'timeline.public.jsonl.gz'),
    ('control/sample-classification.jsonl', CLASS_FIELDS, 'classification.public.jsonl.gz'),
]:
    digest, count = sha256(), 0
    with (JOB / relative).open('rb') as source, (OUT / target).open('xb') as output:
        with gzip.GzipFile(filename='', fileobj=output, mode='wb', mtime=0) as compressed:
            for line in source:
                digest.update(line)
                row = json.loads(line)
                assert not (set(row) - allowed), 'unreviewed public field'
                for item in [row.get('driver'), row.get('listener'), (row.get('worker') or {}).get('process')]:
                    if item and item.get('birth') is not None:
                        identities.add((item['pid'], item['birth']))
                compressed.write((canonical(scrub(row)) + '\n').encode())
                count += 1
    counts[relative] = count
    path = JOB / relative
    sources[relative] = dict(sha256=digest.hexdigest(), bytes=path.stat().st_size,
                             mtime_ns=path.stat().st_mtime_ns, public_export=target)

source_files = {'producer': (PRODUCER, ['benchmarks/run_managed_soak.py']),
                'observer': (OBSERVER, ['tools/managed_soak_observer.py',
                    'tools/managed_observer_finance.py', 'tools/run_managed_long.py'])}
frozen = {}
for label, (directory, paths) in source_files.items():
    frozen[label] = dict(root=str(directory),
        head=subprocess.check_output(['git', '--no-optional-locks', 'rev-parse', 'HEAD'], cwd=directory, text=True).strip(),
        tracked_clean=not subprocess.check_output(['git', '--no-optional-locks', 'status', '--porcelain', '--untracked-files=no'], cwd=directory),
        sha256={name: sha256((directory / name).read_bytes()).hexdigest() for name in paths})

write('capture-metadata.json', dict(synthetic=True, redacted=True, capture_started_at=started,
    capture_finished_at=datetime.now(timezone.utc).isoformat(), capture_boottime_ns=time.clock_gettime_ns(time.CLOCK_BOOTTIME),
    independent_final_evidence_eligible=False, sql_executed=False, source_records=sources,
    original_jsonl_counts=counts, frozen_sources=frozen,
    process_metadata=[proc(pid, birth) for pid, birth in sorted(identities)],
    sampling_scope='existing separately published JSON and matching proc metadata; not one logical SQLite snapshot',
    **{key: False for key in FLAGS}))
print(json.dumps(dict(public_files=len(records), jsonl_counts=counts, process_identities=len(identities))))
