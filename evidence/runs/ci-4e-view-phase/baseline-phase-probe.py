"""Real held-lease startup phase; no financial/market function is patched."""
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import sys
from time import monotonic, sleep

ROOT=Path('/workspace/uta-ci-4e-view-phase')
sys.path[:0]=[str(ROOT),str(ROOT/'tests')]
from test_managed_views_reference import ManagedRouterReadReferenceTests, READER
from uta.writer_fence import WriterFence


def facts(case, publication, phase):
    databases=[]
    for shard in range(2):
        with case.router._database(shard).read_transaction() as connection:
            row=connection.execute('SELECT payload FROM uta_market WHERE singleton=1').fetchone()
            databases.append({'shard':shard,'market_payload':None if row is None else row[0],
                'commands':[dict(item) for item in connection.execute("SELECT command_id,state,result,error FROM uta_command_inbox WHERE kind='PUBLISH_MARKET' ORDER BY sequence")]})
    state=case.router._control._state()
    result={'phase':phase,'observed_utc':datetime.now(timezone.utc).isoformat(),'publication':publication,
        'control':state,'health':case.get('/v2/worker-health'),
        'account':case.get('/v2/accounts/'+case.accounts[0],token=READER),'databases':databases}
    print(json.dumps(result,sort_keys=True),flush=True)
    return result


if __name__=='__main__':
    os.sched_setaffinity(0,{min(os.sched_getaffinity(0))})
    print(json.dumps({'source_commit':'4e59084544b8816e6e50e4caea7c6f60cff43a00','python':sys.version,'cpus':sorted(os.sched_getaffinity(0)),'mode':'synthetic controlled lease-contention; not unique CI causation'}),flush=True)
    case=ManagedRouterReadReferenceTests('test_real_partial_fanout_stale_and_recovery_remain_explicit_through_http')
    case.setUp()
    held={}
    try:
        for shard in range(2):
            fence=WriterFence(case.router._database(shard))
            held[shard]=(fence,fence.acquire('independent:phase-hold-'+str(shard),5))
        case.router.start()
        snapshot=case.market()
        publication=case.router.publish_market(snapshot,timeout=.25)
        initial=facts(case,publication,'partial-before-shard0-initialization')
        assert publication['publishing'] is True
        assert initial['account']['snapshot']['market']['freshness']=='missing'
        assert initial['databases'][0]['market_payload'] is None
        assert initial['health']['financial_ready'] is False
        print(json.dumps({'old_instant_fresh_assertion_would_fail':True,'elapsed_age_seconds':(datetime.now(timezone.utc)-snapshot.observed_at).total_seconds()}),flush=True)
        fence,token=held.pop(0)
        fence.release(token)
        command_id=publication['durable_market_commands']['0']
        deadline=monotonic()+1
        receipt=None
        while monotonic()<deadline:
            receipt=case.router.status(command_id,shard=0)
            if receipt and receipt['state'] in ('SUCCEEDED','REJECTED','QUARANTINED'):
                break
            sleep(.01)
        assert receipt and receipt['state']=='SUCCEEDED', receipt
        publication=case.router.publish_market(snapshot,timeout=.05)
        committed=facts(case,publication,'same-original-market-committed-only-shard0')
        assert committed['account']['snapshot']['market']['freshness']=='fresh_as_of_read'
        assert committed['account']['snapshot']['market']['version']==snapshot.version
        assert committed['account']['snapshot']['market']['payload_digest']==sha256(snapshot.to_json().encode()).hexdigest()
        assert publication['receipts']['1']['state']=='PENDING'
        assert committed['control']['halted'] is True and committed['control']['publishing'] is True
        fence,token=held.pop(1)
        fence.release(token)
        case.activate(snapshot)
        complete=facts(case,None,'same-original-market-full-activation')
        assert complete['health']['financial_ready'] is True
        sleep(max(0,(snapshot.observed_at.timestamp()+2-datetime.now(timezone.utc).timestamp()))+.04)
        stale=facts(case,None,'natural-original-timestamp-expiration')
        assert stale['account']['snapshot']['market']['freshness']=='stale'
        assert stale['health']['workers_alive'] is True and stale['health']['financial_ready'] is False
        case.activate(case.market(2))
        recovered=facts(case,None,'genuine-new-version-recovery')
        assert recovered['account']['snapshot']['market']['version']==2
        assert recovered['health']['financial_ready'] is True
        print(json.dumps({'phase_probe_passed':True,'quote_age_seconds_unchanged':2,'original_observed_at':snapshot.observed_at.isoformat()}),flush=True)
    finally:
        for fence,token in held.values():
            fence.release(token)
        case.doCleanups()
