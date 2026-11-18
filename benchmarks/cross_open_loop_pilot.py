"""CODE-only proposal: independent open-loop configured-Cross durable pilot.

New root approval is mandatory. Existing diagnostic tools/plans stay unchanged.
Parent arrival scheduling never waits for a command completion or queue slot.
"""
import argparse
from collections import Counter
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
from queue import Empty, Full, Queue
import stat
import sys
from threading import Event, Lock, Thread
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
PROTECTED = frozenset((4471,8784,122905,122907,123007,123009,310035,310039,310266,310269))


def write_new(path, value):
    raw=(json.dumps(value,sort_keys=True,indent=2,allow_nan=False)+'\n').encode()
    if len(raw)>2*1024*1024:
        raise ValueError('private report exceeds2MiB')
    descriptor=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    try:
        if os.write(descriptor,raw)!=len(raw):raise OSError('short report write')
        os.fsync(descriptor)
    finally:os.close(descriptor)


def source_pins(path, approved):
    raw=Path(path).read_bytes()
    if sha256(raw).hexdigest()!=approved:raise ValueError('source manifest differs')
    manifest=json.loads(raw); observed={}
    for name,pin in manifest['inputs'].items():
        target=ROOT/name; info=target.lstat()
        if not stat.S_ISREG(info.st_mode) or target.resolve()!=target:raise ValueError('source not canonical regular')
        raw=target.read_bytes(); actual={'bytes':len(raw),'sha256':sha256(raw).hexdigest()}
        if actual!=pin:raise ValueError('source digest differs: '+name)
        observed[name]=actual
    return observed


class BoundedStreams:
    """Trusted Python stdout/stderr hard cap, shared per worker; no FD threat proof."""
    used=0
    failed=False
    encoding='utf-8'
    errors='backslashreplace'
    def __init__(self,fd):self.fd=fd
    def write(self,text):
        if type(self).failed:raise OSError('sticky raw writer failure')
        data=text.encode(self.encoding,self.errors)
        if len(data)>16384-512-self.used:
            type(self).failed=True
            raise OSError('sticky raw cap exhausted')
        type(self).used+=len(data)
        if os.write(self.fd,data)!=len(data):
            type(self).failed=True
            raise OSError('sticky short raw write')
        return len(text)
    def flush(self):pass


def worker(settings_path):
    # No UTA/SQLite/authority access until the held-pidfd owner releases stdin.
    if os.getpid() in PROTECTED or sys.stdin.buffer.read(1)!=b'G':return 126
    cfg=json.loads(Path(settings_path).read_bytes())
    before=source_pins(cfg['source_manifest'],cfg['manifest_sha256'])
    from multiprocessing.connection import Connection
    from uta.durable_process import _run_worker, _SignalReceiver
    sys.stdout,sys.stderr=BoundedStreams(1),BoundedStreams(2)
    prefix=Path(cfg['clock_output'])
    clock=lambda:{'monotonic_ns':time.monotonic_ns(),'utc_epoch_ns':time.time_ns(),
        'utc':datetime.now(timezone.utc).isoformat(),'clock':'same-host monotonic_ns and native UTC'}
    write_new(prefix.with_name(prefix.name+'-start.json'),clock())
    try:
        _run_worker(cfg['directory'],cfg['shard'],cfg['settings'],
            _SignalReceiver(Connection(cfg['stop_fd'],writable=False)),
            Connection(cfg['ready_fd'],readable=False),cfg['parent_pid'],
            _SignalReceiver(Connection(cfg['gate_fd'],writable=False)),cfg['nonce'],cfg['coordinator'])
    finally:
        write_new(prefix.with_name(prefix.name+'-end.json'),{'clock':clock(),
            'source_unchanged':before==source_pins(cfg['source_manifest'],cfg['manifest_sha256']),
            'raw_bytes_reserved':BoundedStreams.used,'raw_writer_failed':BoundedStreams.failed})
    return 0


def clock_sample():
    before=time.monotonic_ns(); epoch=time.time_ns(); after=time.monotonic_ns()
    return {'mono_before_ns':before,'utc_epoch_ns':epoch,'mono_after_ns':after}


def budget(root):
    total=0
    for path in Path(root).rglob('*'):
        info=path.lstat()
        if stat.S_ISREG(info.st_mode):total+=info.st_size
        elif not stat.S_ISDIR(info.st_mode):raise RuntimeError('nonregular private scope object')
    if total>64*1024*1024:raise RuntimeError('logical64MiB scope budget exceeded')
    return total  # C writes between application checks are not a kernel quota.


def outer_guard(binding):
    if os.getppid()!=binding['host_pid'] or time.monotonic()>=binding['outer_deadline_monotonic']:
        raise TimeoutError('outer host lost or budget expired; no next operation')
    if (Path(binding['host_root'])/'stop.json').exists():raise RuntimeError('outer first-failure stop')


def cohort(index, directory, binding):
    from decimal import Decimal as D
    from benchmarks.cross_open_loop_model import accounts, workload, percentiles_ns
    from benchmarks.cross_open_loop_checks import require_feed_timing, FEED_START_LATENESS_NS, FEED_COMPLETE_LATENESS_NS
    from benchmarks.pilot_owned_workers import OwnedWorkers
    from uta.durable_process import DurableProcessRouter
    from uta.examples import synthetic_policy
    from uta.market import MarketSnapshot
    from uta.models import AssetSpec, InstrumentSpec
    from uta.service import ServiceError
    outer_guard(binding);directory.mkdir(mode=0o700)
    policy, rules=synthetic_policy()
    def quote(version):
        return MarketSnapshot(version,datetime.now(timezone.utc),
            {'USD':AssetSpec(D(1),D(1)),'BTC':AssetSpec(D(100),D('.8'))},
            {'BTC-PERP':InstrumentSpec(D(100),D('.1'),D('.05'))})
    def bootstrap(router):
        for shard in (0,1):
            outer_guard(binding)
            router.configure_credit_asset_limit(shard,'USD',D(1000))
            router.fund_credit_pool(shard,'pool-funding','USD',D(1000),source_reference=f'synthetic:{index}:pool:{shard}')
        for number,account in enumerate(accounts()):
            outer_guard(binding)
            router.create_account(account)
            router.deposit(account,'deposit-USD','USD',D(100))
            router.deposit(account,'deposit-BTC','BTC',D(1))
            router.configure_credit_limit(account,'USD',D(10))
            router.publish_market(quote(number+1))  # fixed fresh quote before each offline loan, never retry
            router.set_kill_switch(False)
            outer_guard(binding)
            router.borrow(account,'initial-loan','USD',D(1))
            router.set_kill_switch(True)
    outer_guard(binding)
    router=DurableProcessRouter.initialize(directory/'authority',2,{'USD':8,'BTC':8},managed=True,
        bootstrap=bootstrap,product_catalog=policy,portfolio_rules=rules,max_price_age=timedelta(seconds=5),
        reserve_cache_size=0,market_cache_size=0,normal_cache_size=0,queue_capacity=32,cancel_reserve=4,
        market_capacity=4,decision_audit=True,durable_batches=False,lease_seconds=5,poll_interval=.01,
        background_interval=.1,account_batch=4,matches_per_symbol=1,max_attempts=1)
    write_new(directory/'native-config.json',{'config':router._config,'worker_settings':router._settings,
        'account_shards':{a:router.shard_for(a) for a in accounts()},'policy':policy.to_json(),'rules':rules.to_json()})
    # Producer/observer busy waits are bounded separately from unchanged worker settings.
    for shard in (0,1):router._queue(shard).database.timeout=.2
    owners=OwnedWorkers(router,directory/'workers',Path(__file__).resolve(),{**binding,'cohort':index})
    stop=Event(); lock=Lock(); queues=[Queue(16),Queue(16)]; rows=[]; feed=[]; faults=[]; threads=[]
    start=end=0; cleanup=[]; ready=False; all_joined=False
    def fatal(phase,error):
        with lock:faults.append({'phase':phase,'type':type(error).__name__,'code':getattr(error,'code',None),'at_ns':time.monotonic_ns()})
        stop.set()
    def finish(row,receipt):
        now=time.monotonic_ns()
        state=receipt['state']
        if state not in ('SUCCEEDED','REJECTED','QUARANTINED'):return
        unexpected=False
        if state=='SUCCEEDED':
            outcome='accepted_persistent';unexpected=row['expected_business_rejection']
        elif state=='QUARANTINED':outcome='technical_terminal';unexpected=True
        else:
            error=receipt['error']; error=json.loads(error) if isinstance(error,str) else error
            outcome='business_rejected' if error['status']<500 else 'control_market_rejected'
            unexpected=not (row['expected_business_rejection'] and error['code']=='product_rejected' and error['status']==409)
        with lock:
            if row.get('outcome') is not None:return
            row.update(outcome=outcome,observed_completion_ns=now,latency_ns=now-row['planned_ns'],receipt=receipt,
                completed_after_client_deadline=now>row['planned_ns']+10**9)
        if unexpected:fatal('unexpected_terminal',RuntimeError('terminal receipt differs from fixed workload policy'))
    def dispatch(shard):
        while not stop.is_set():
            try:row=queues[shard].get(timeout=.01)
            except Empty:continue
            with lock:row['enqueue_started_ns']=time.monotonic_ns()
            try:
                receipt=router.submit_order(row['account_id'],row['command_id'],row['order_id'],row['symbol'],D(row['quantity']),D(row['limit_price']))
                with lock:row['enqueue_ack_ns']=time.monotonic_ns()
                finish(row,receipt)
            except Exception as error:
                with lock:row['enqueue_exception']={'type':type(error).__name__,'code':getattr(error,'code',None),'status':getattr(error,'status',None)}
                # Query this same CID once before stopping new offering. This is
                # result discovery, never a second command submission.
                try:
                    existing=router.status(row['command_id'],account_id=row['account_id'])
                    if existing is not None:finish(row,existing)
                except Exception as query_error:
                    with lock:row['status_query_failure']={'type':type(query_error).__name__,'code':getattr(query_error,'code',None)}
                fatal('enqueue_unknown_or_technical',error)
            finally:
                with lock:row['enqueue_call_finished_ns']=time.monotonic_ns()
                queues[shard].task_done()
    def collect():
        while not stop.is_set():
            with lock:pending=[r for r in rows if r.get('outcome') is None and r.get('enqueue_started_ns') is not None]
            for row in pending:
                if stop.is_set():break
                now=time.monotonic_ns()
                if now>row['planned_ns']+10**9:
                    with lock:row.setdefault('client_timeout_unknown_at_ns',now)
                try:
                    receipt=router.status(row['command_id'],account_id=row['account_id'])
                    if receipt is not None:finish(row,receipt)
                except Exception as error:
                    with lock:row.setdefault('status_query_failure',{'type':type(error).__name__,'code':getattr(error,'code',None)})
                    fatal('status_query_unknown',error)
            stop.wait(.01)
    def feeder():
        for number,offset in enumerate((2_031_250_000,4_031_250_000),6):
            planned=start+offset
            if stop.wait(max(0,(planned-time.monotonic_ns())/1e9)):return
            row={'version':number,'planned_ns':planned,'started_ns':time.monotonic_ns(),
                 'max_start_lateness_ns':FEED_START_LATENESS_NS,'max_complete_lateness_ns':FEED_COMPLETE_LATENESS_NS}
            try:
                row['quote_build_started_ns']=time.monotonic_ns()
                require_feed_timing(planned,row['quote_build_started_ns'],'before_quote')
                snapshot=quote(number);row['raw_snapshot']=snapshot.to_json();row['sha256']=sha256(snapshot.to_json().encode()).hexdigest()
                row['publish_started_ns']=time.monotonic_ns()
                require_feed_timing(planned,row['publish_started_ns'],'before_publish')
                publication=router.publish_market(snapshot,timeout=.5)
                row.update(published_ns=time.monotonic_ns(),publication=publication)
                require_feed_timing(planned,row['published_ns'],'after_publish')
                if publication['publishing']:raise RuntimeError('incomplete scheduled market publication')
                activation=router.set_kill_switch(False,timeout=.5)
                if activation['halted']:raise RuntimeError('incomplete scheduled activation')
                row.update(completed_ns=time.monotonic_ns(),activation=activation)
                require_feed_timing(planned,row['completed_ns'],'after_activation')
            except Exception as error:
                row['error_type']=type(error).__name__;row['error_detail']=str(error)[:160];fatal('fixed_market_feed',error)
            finally:
                with lock:feed.append(row)
            if stop.is_set():return
    try:
        owners.start(time.monotonic()+12);ready=True
        publication=router.publish_market(quote(5),timeout=1)
        if publication['publishing'] or router.set_kill_switch(False,timeout=1)['halted']:
            raise RuntimeError('initial activation incomplete; no load')
        anchor_start=clock_sample();start=anchor_start['mono_after_ns'];utc_start=anchor_start['utc_epoch_ns'];end=start+6*10**9
        for target,args,name in [(dispatch,(0,),'dispatch-0'),(dispatch,(1,),'dispatch-1'),(collect,(),'collect'),(feeder,(),'fixed-feed')]:
            thread=Thread(target=target,args=args,name=name,daemon=True);threads.append(thread);thread.start()
        for terms in workload(index):
            planned=start+terms.pop('offset_ns')
            if stop.is_set():break
            delay=planned-time.monotonic_ns()
            if delay>0:stop.wait(delay/1e9)
            if stop.is_set():break
            owners.check();budget(directory.parent)
            row={**terms,'planned_ns':planned,'offered_ns':time.monotonic_ns(),'enqueue_started_ns':None,
                 'enqueue_ack_ns':None,'enqueue_call_finished_ns':None,'outcome':None}
            row['shard']=router.shard_for(row['account_id'])
            with lock:rows.append(row)
            try:queues[row['shard']].put_nowait(row)
            except Full:
                with lock:row.update(outcome='local_backpressure',observed_completion_ns=time.monotonic_ns())
        if not stop.is_set():stop.wait(max(0,(end-time.monotonic_ns())/1e9))
        offer_end=time.monotonic_ns();drain_started=offer_end;drain_deadline=end+2*10**9
        while not stop.is_set() and time.monotonic_ns()<drain_deadline:
            owners.check()
            with lock:complete=all(r['outcome'] is not None for r in rows)
            if complete:break
            stop.wait(.01)
        drain_end=time.monotonic_ns();anchor_end=clock_sample();utc_end=anchor_end['utc_epoch_ns']
    except BaseException as error:
        fatal('cohort',error)
        offer_end=drain_started=drain_end=time.monotonic_ns();utc_start=locals().get('utc_start');utc_end=time.time_ns()
    finally:
        stop.set()
        join_deadline=min(time.monotonic()+1,binding['outer_deadline_monotonic']+2)
        for thread in threads:thread.join(timeout=max(0,join_deadline-time.monotonic()))
        all_joined=not any(t.is_alive() for t in threads)
        cleanup=owners.close(deadline=min(time.monotonic()+3,binding['outer_deadline_monotonic']+2))
    with lock:
        rows=json.loads(json.dumps(rows))  # Freeze even an UNKNOWN late producer; no late rewrite of measured observations.
    for row in rows:
        if row['outcome'] is None:row['outcome']='unknown_unresolved' if row['enqueue_started_ns'] is not None else 'local_queue_leftover_not_submitted'
    worker_clocks=[]
    for shard in (0,1):
        clock_path=directory/'workers'/f'worker-{shard}-clock-end.json'
        if clock_path.is_file():
            item=json.loads(clock_path.read_bytes());worker_clocks.append({'shard':shard,**item})
        else:faults.append({'phase':'worker_clock_end','shard':shard,'type':'MISSING'})
    write_new(directory/'arrivals.json',rows)
    write_new(directory/'fixed-feed.json',feed)
    reopened=None
    if all_joined and all(r['reaped'] for r in cleanup):
        try:
            from benchmarks.cross_open_loop_reconcile import reconcile
            reopened=reconcile(router,rows)
        except Exception as error:
            faults.append({'phase':'readonly_reconcile','type':type(error).__name__,'message':str(error)[:256]})
    counts=Counter(r['outcome'] for r in rows)
    quantiles={name:percentiles_ns([r['latency_ns'] for r in rows if r['outcome']==name and 'latency_ns' in r])
               for name in ('accepted_persistent','business_rejected','control_market_rejected','technical_terminal')}
    expected=(counts=={'accepted_persistent':72,'business_rejected':24})
    qualified=(ready and not faults and not owners.cleanup_errors and all_joined and len(rows)==96 and expected and reopened is not None
        and not reopened['pending_original_CIDs'] and not reopened['unobserved_success_CIDs_found_after_stop']
        and len(worker_clocks)==2 and all(c['source_unchanged'] is True and c['raw_writer_failed'] is False for c in worker_clocks)
        and all(r['actual_exit']==0 and r['reaped'] and not r['held_pidfd_kill_used'] and r['cleanup_error'] is None for r in cleanup)
        and not any(r.get('client_timeout_unknown_at_ns') or r.get('completed_after_client_deadline')
            or r.get('enqueue_exception') or r.get('status_query_failure') for r in rows))
    report={'kind':'G3_SINGLE_HOST_CONFIGURED_CROSS_PERSISTENT_ADMISSION_PILOT_NOT_CAPACITY','cohort':index,
        'source_base':'7665253ced0888e8204b9806b63c4163f2cafe42','planned_arrivals':96,'actually_offered':len(rows),
        'not_offered_after_abort':96-len(rows),'outcomes':dict(counts),'observed_completion_quantiles_ns':quantiles,
        'generator_scheduling_lag_ns':percentiles_ns([r['offered_ns']-r['planned_ns'] for r in rows]),
        'client_timeout_unknown_facts':sum('client_timeout_unknown_at_ns' in r for r in rows),
        'completed_after_client_deadline':sum(bool(r.get('completed_after_client_deadline')) for r in rows),
        'observed_terminal_by_offer_end':sum(r.get('observed_completion_ns',2**63-1)<=end for r in rows if 'latency_ns' in r),
        'observed_terminal_by_drain_end':sum(r.get('observed_completion_ns',2**63-1)<=drain_end for r in rows if 'latency_ns' in r),
        'actual_local_leftover_queues': [q.qsize() for q in queues],
        'enqueue_technical_or_unknown_facts':sum('enqueue_exception' in r for r in rows),
        'query_technical_facts':sum('status_query_failure' in r for r in rows),
        'scheduled_start_ns':start,'scheduled_offer_end_ns':end,'actual_offer_end_ns':offer_end,
        'drain_started_ns':drain_started,'drain_end_ns':drain_end,'drain_elapsed_ns':drain_end-drain_started,
        'generator_utc_start_ns':utc_start,'generator_utc_end_ns':utc_end,
        'clock_anchor_start':locals().get('anchor_start'),'clock_anchor_end':locals().get('anchor_end'),
        'utc_minus_monotonic_drift_ns':None if utc_start is None else (utc_end-utc_start)-(drain_end-start),
        'drift_limit':'bracketed local UTC/monotonic samples only, not remote clock synchronization; native default UTC unchanged',
        'logical_scope_bytes_observed':budget(directory.parent),
        'bounded_producer_threads_joined':all_joined,'owned_worker_cleanup':cleanup,'worker_end_clocks':worker_clocks,'faults':faults,'reopened':reopened,
        'pilot_functional_gate_passed':qualified,'official_10000_per_s_1800s_gate_passed':False,'production_approved':False,
        'latency_semantics':'planned arrival to first observed durable terminal receipt, includes generator/queue/enqueue/writer/collector delay; actual COMMIT instant is not separately observed',
        'limits':'same-host cohosted generator+2 writer processes; no network/replication; no mixed matching/liquidation/API capacity',
        'unfinished_producer_observations_frozen':not all_joined}
    write_new(directory/'report.json',report)
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--worker-settings')
    parser.add_argument('--host-start-gate-stdin',action='store_true')
    parser.add_argument('--host-control-dir')
    parser.add_argument('--output')
    parser.add_argument('--source-manifest')
    parser.add_argument('--approved-manifest-sha256')
    args=parser.parse_args()
    if args.worker_settings:
        if any((args.output,args.source_manifest,args.approved_manifest_sha256,args.host_start_gate_stdin,args.host_control_dir)):raise ValueError('worker/parent modes cannot mix')
        return worker(args.worker_settings)
    if not all((args.output,args.source_manifest,args.approved_manifest_sha256,args.host_start_gate_stdin,args.host_control_dir)):
        raise ValueError('frozen gated parent arguments required')
    if sys.stdin.buffer.read(1)!=b'G':return 126  # Before source/authority/UTA/SQLite access.
    host_root=Path(args.host_control_dir)
    host_intent=json.loads((host_root/'intent.json').read_bytes())
    if (type(host_intent['format']) is not int or host_intent['format']!=1 or host_intent['host_root']!=str(host_root) or host_intent['run_root']!=args.output
            or host_intent['manifest_sha256']!=args.approved_manifest_sha256 or host_intent['host_pid']!=os.getppid()
            or type(host_intent['execution_deadline_ns']) is not int or type(host_intent['cleanup_deadline_ns']) is not int
            or host_intent['cleanup_deadline_ns']!=host_intent['execution_deadline_ns']+2_000_000_000 or time.monotonic_ns()>=host_intent['execution_deadline_ns']):
        raise ValueError('outer host identity/budget binding differs')
    if os.getpid() in PROTECTED:raise RuntimeError('protected numeric coordinator ID')
    if not (sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode):raise RuntimeError('-I -S -B required')
    before=source_pins(args.source_manifest,args.approved_manifest_sha256)
    # Cold -I/-S parent: retain a namespace at the bound benchmark directory,
    # so no unbound benchmarks/__init__.py can execute during native helpers.
    from types import ModuleType
    from importlib.machinery import ModuleSpec
    if 'benchmarks' in sys.modules:raise ValueError('unexpected preloaded benchmark namespace')
    retained=ModuleType('benchmarks');retained.__package__='benchmarks';retained.__path__=[str(ROOT/'benchmarks')]
    retained.__spec__=ModuleSpec('benchmarks',loader=None,is_package=True)
    retained.__spec__.submodule_search_locations=list(retained.__path__);sys.modules['benchmarks']=retained
    sys.stdout,sys.stderr=BoundedStreams(1),BoundedStreams(2)
    output=Path(args.output)
    if not output.is_absolute() or output.parent!=Path('/workspace') or output.exists():raise ValueError('new direct workspace private output required')
    os.umask(0o077);output.mkdir(mode=0o700)
    import sqlite3
    executable=Path(sys.executable).resolve(); executable_digest=sha256()
    with executable.open('rb') as stream:
        for block in iter(lambda:stream.read(131072),b''):executable_digest.update(block)
    write_new(output/'intent.json',{'source_pins_before':before,'argv':sys.argv,'metrics':'NOT_OBSERVED before actual execution',
        'source_manifest_sha256':args.approved_manifest_sha256,'private_scope':True,'replication':'none; SQLite local WAL/FULL',
        'clock':time.get_clock_info('monotonic').__dict__,'CPU_affinity_actual':sorted(os.sched_getaffinity(0)),
        'hardware':{'os_logical_cpu_count':os.cpu_count(),'python':sys.version,
            'sqlite_version':sqlite3.sqlite_version,'executable_path':str(executable),'executable_sha256':executable_digest.hexdigest(),
            'physical_storage':'NOT_OBSERVED local filesystem, no proc scan or block-device probe',
            'network':'no external network; lifecycle FD pipes and shared SQLite inbox/control',
            'replication':'NONE; no cross-host or AZ RPO proof'},
        'generator_role':'main thread independent of native writer processes and blocking enqueue dispatcher threads'})
    binding={'path':args.source_manifest,'sha256':args.approved_manifest_sha256,'host_root':str(host_root),
        'host_session':host_intent['session'],'host_pid':host_intent['host_pid'],
        'outer_deadline_monotonic':host_intent['execution_deadline_ns']/10**9,
        'outer_cleanup_deadline_ns':host_intent['cleanup_deadline_ns']}
    reports=[]
    for index in (0,1):
        outer_guard(binding)
        report=cohort(index,output/f'cohort-{index}',binding);reports.append(report)
        if not report['pilot_functional_gate_passed']:break
    after=source_pins(args.source_manifest,args.approved_manifest_sha256)
    if sys.modules.get('benchmarks') is not retained:raise ValueError('retained benchmark namespace changed')
    for name,module in tuple(sys.modules.items()):
        if name.startswith('benchmarks.'):
            path=Path(module.__file__).resolve();relative=str(path.relative_to(ROOT))
            if relative not in before or sha256(path.read_bytes()).hexdigest()!=before[relative]['sha256']:
                raise ValueError('loaded benchmark helper origin not bound: '+name)
    write_new(output/'result.json',{'cohorts_completed':len(reports),'planned_cohorts':2,'source_unchanged':before==after,
        'both_fixed_pilot_functional_gates_passed':len(reports)==2 and all(r['pilot_functional_gate_passed'] for r in reports),
        'official_capacity_or_production_approved':False,'native_writer_function_unchanged':True,
        'parent_raw_bytes_reserved':BoundedStreams.used,'parent_raw_writer_failed':BoundedStreams.failed})
    budget(output)
    return 0 if before==after and len(reports)==2 and all(r['pilot_functional_gate_passed'] for r in reports) else 1


if __name__=='__main__':
    sys.stdout,sys.stderr=BoundedStreams(1),BoundedStreams(2)
    raise SystemExit(main())
