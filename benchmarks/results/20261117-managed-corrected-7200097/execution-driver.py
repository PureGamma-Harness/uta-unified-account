"""External execution recorder; never modifies the frozen benchmark/source."""
from datetime import datetime, timezone
from hashlib import sha256
import inspect
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

SOURCE = Path('/workspace/uta-durable-final-7200097')
SHA = '7200097ce9f92fa678907bee9a99933f60d65bc3'
SOAK_SOURCE = Path('/workspace/uta-soak-source-88755a9')
JOB = Path('/workspace/uta-soak-runs/formal-20261116T213613Z-88755a9')
OBSERVER = JOB / 'observer-20261116T221001Z-f96dfd8'
OUTPUT = Path('/tmp/uta-managed-corrected-7200097-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
OUTPUT.mkdir()
sys.path.insert(0, str(SOURCE))
from uta.durable_process import DurableProcessRouter
from benchmarks.run_managed_benchmark import Configuration

def now(): return datetime.now(timezone.utc).isoformat()
def save(path, value): path.write_text(json.dumps(value, indent=2) + '\n')
def source_state():
    head = subprocess.check_output(['git','rev-parse','HEAD'], cwd=SOURCE, text=True).strip()
    dirty = subprocess.check_output(['git','--no-optional-locks','status','--porcelain','--untracked-files=no'], cwd=SOURCE, text=True).strip()
    files = sorted((SOURCE/'uta').rglob('*.py')) + [SOURCE/'benchmarks'/name for name in
        ('run_benchmark.py','run_group_benchmark.py','run_managed_benchmark.py')]
    hashes = {str(path.relative_to(SOURCE)):sha256(path.read_bytes()).hexdigest() for path in files}
    if head != SHA or dirty: raise RuntimeError('frozen source changed')
    return {'head':head,'tracked_dirty':dirty,'files_sha256':hashes}
def identity(pid):
    raw = Path('/proc/'+str(pid)+'/stat').read_text()
    fields = raw[raw.rfind(')')+2:].split()
    return {'pid':pid,'birth':fields[19],'state':fields[0],
            'command':Path('/proc/'+str(pid)+'/cmdline').read_bytes().decode().split('\0')[:-1]}
identities = {str(pid):identity(pid) for pid in (4471,8784)}
assert identities['4471']['birth'] == '210004'
def cohost(path):
    at = now()
    call = [sys.executable,str(SOAK_SOURCE/'benchmarks/run_soak.py'),'status','--directory',str(JOB)]
    result = subprocess.run(call,cwd=SOAK_SOURCE,text=True,capture_output=True,timeout=15)
    observation = json.loads(result.stdout) if result.returncode == 0 else None
    observer = json.loads((OBSERVER/'latest.json').read_text())
    processes = {str(pid):identity(pid) for pid in (4471,8784)}
    row = {'observed_utc':at,'producer_status_command':call,'returncode':result.returncode,
           'stderr':result.stderr,'producer':observation,'observer_latest':observer,'processes':processes}
    save(path,row)
    if result.returncode or result.stderr or observation['status'] != 'running':
        raise RuntimeError('cohost producer failed')
    if observation['heartbeat_age_seconds'] > 30 or observation['market_age_seconds'] > 5:
        raise RuntimeError('cohost heartbeat or quote stale')
    if set(observation['counts']) - {'done','active'}:
        raise RuntimeError('cohost unfinished/error rounds')
    if observer['assessment']['alerts'] or (time.time_ns()-observer['observed_ns'])/1e9 > 150:
        raise RuntimeError('cohost observer stale or alerted')
    for pid, value in processes.items():
        if value['state'] in {'Z','X'} or value['birth'] != identities[pid]['birth'] or value['command'] != identities[pid]['command']:
            raise RuntimeError('cohost process changed or exited')
    # Completed-round goldens can differ in the middle of a real round; retain
    # inflight evidence and rely on the observer's explicit assessment above.
    return row

plan_path = SOURCE/'benchmarks/plans/20261117-managed-corrected-baseline.json'
plan_bytes = plan_path.read_bytes()
plan = json.loads(plan_bytes)
(OUTPUT/'preregistered-plan.json').write_bytes(plan_bytes)
initial_source = source_state()
runtime = {name:parameter.default for name,parameter in inspect.signature(DurableProcessRouter).parameters.items()
           if name in ('lease_seconds','poll_interval','background_interval','account_batch','matches_per_symbol','max_attempts')}
assert runtime == dict(lease_seconds=5.,poll_interval=.02,background_interval=.1,account_batch=25,matches_per_symbol=10,max_attempts=3)
manifest = {'plan_id':plan['plan_id'],'plan_sha256':sha256(plan_bytes).hexdigest(),
    'authorization':'integration owner /root explicit GO; exact source7200097; local three runtime916 + eight remote CI916 + package862/installed8 qualified',
    'go_ci_runs':['44025608750','44025613936'],'created_utc':now(),'source':initial_source,
    'driver_sha256':sha256(Path(__file__).read_bytes()).hexdigest(),'interpreter':sys.executable,
    'runtime_defaults':runtime,'cohosted':True,'replication':False,'production_approved':False,
    'capacity_10000_per_s_passed':False,'stability_passed':False,'runs':[],
    'output':str(OUTPUT),'status':'RUNNING'}
save(OUTPUT/'execution-manifest.json',manifest)
print(json.dumps({'event':'cohort_prepared','output':str(OUTPUT),'at':now()}),flush=True)
try:
    for planned in plan['runs']:
        run_id = planned['run_id']
        if source_state() != initial_source: raise RuntimeError('source/hash drift before case')
        if shutil.disk_usage(OUTPUT).free < plan['resource_budget']['minimum_free_disk_bytes']:
            raise RuntimeError('insufficient free storage')
        cohost(OUTPUT/(run_id+'-cohost-before.json'))
        command = [sys.executable,str(SOURCE/'benchmarks/run_managed_benchmark.py'),
            '--output',str(OUTPUT/run_id),'--duration','10','--rate',str(planned['offered_rate_per_second']),
            '--accounts','100','--shards','2','--cpu-limit','2'] + (['--profile'] if planned['profile'] else [])
        record = {'run_id':run_id,'command':command,'started_utc':now(),'started_monotonic_ns':time.monotonic_ns()}
        manifest['runs'].append(record)
        save(OUTPUT/'execution-manifest.json',manifest)
        print(json.dumps({'event':'case_started',**record}),flush=True)
        with (OUTPUT/(run_id+'-stdout.json')).open('x') as stdout, (OUTPUT/(run_id+'-stderr.txt')).open('x') as stderr:
            result = subprocess.run(command,cwd=SOURCE,stdout=stdout,stderr=stderr,timeout=45)
        record.update(finished_utc=now(),finished_monotonic_ns=time.monotonic_ns(),returncode=result.returncode)
        save(OUTPUT/'execution-manifest.json',manifest)
        cohost(OUTPUT/(run_id+'-cohost-after.json'))
        if result.returncode: raise RuntimeError(run_id+' failed; preserved original authority')
        summary = json.loads((OUTPUT/run_id/'summary.json').read_text())
        record.update(counts=summary['counts'],readonly=summary['readonly_reconciliation'],
            rate=summary['unique_observed_financial_success_per_s'],latency_ms=summary['latency_ms'],
            duration_including_drain=summary['duration_including_terminal_observation_drain'])
        expected=Configuration(rate=planned['offered_rate_per_second'],profile=planned['profile']).__dict__
        if summary['configuration'] != expected or summary['offered'] != planned['offered_arrivals']:
            raise RuntimeError('configuration/planned quantity drift')
        if summary['environment']['code_commit'] != SHA or source_state() != initial_source:
            raise RuntimeError('source changed during case')
        bad = ('enqueue_technical_errors','technical_quarantined','result_unknown_at_drain_deadline','not_dispatched_before_drain_deadline','local_not_dispatched_timeout')
        if (summary['poll_errors'] or any(summary['counts'].get(key,0) for key in bad)
                or any(value and ('unknown' in key or 'timeout' in key) for key,value in summary['counts'].items())
                or any('error' in row for row in summary['feed_publications'])
                or summary['readonly_reconciliation']['pending_count']
                or summary['readonly_reconciliation']['unobserved_successes_found_on_reopen']
                or (OUTPUT/(run_id+'-stderr.txt')).stat().st_size):
            raise RuntimeError('I/O/unknown/technical/feed/late-reopen or stderr event; stop remaining cases')
        size=sum(path.stat().st_size for path in (OUTPUT/run_id).rglob('*') if path.is_file())
        if size > plan['resource_budget']['per_case_output_max_bytes']:
            raise RuntimeError('case storage budget exceeded')
        if sum(path.stat().st_size for path in OUTPUT.rglob('*') if path.is_file()) > plan['resource_budget']['cohort_output_max_bytes']:
            raise RuntimeError('cohort storage budget exceeded')
        record['status']='COMPLETED_AND_RECONCILED'
        save(OUTPUT/'execution-manifest.json',manifest)
        print(json.dumps({'event':'case_finished','run_id':run_id,'counts':summary['counts'],'rate':record['rate'],'at':now()}),flush=True)
    manifest.update(status='COMPLETED',finished_utc=now(),source_after=source_state())
except BaseException as error:
    manifest.update(status='STOPPED_ON_ERROR',error={'type':type(error).__name__,'message':str(error)},finished_utc=now())
    save(OUTPUT/'execution-manifest.json',manifest)
    print(json.dumps({'event':'cohort_stopped','error':manifest['error'],'output':str(OUTPUT)}),flush=True)
    raise
save(OUTPUT/'execution-manifest.json',manifest)
print(json.dumps({'event':'cohort_finished','output':str(OUTPUT),'at':now()}),flush=True)
