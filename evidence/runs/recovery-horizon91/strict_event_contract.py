"""Pure audit of saved original-call events; no runtime/financial-core imports."""
from collections import Counter
import re

def validate_events(events,worker):
    errors=[]
    if type(events) is not list or not events:return {'valid':False,'errors':['nonempty event list required']}
    for row in events:
        if type(row) is not dict or type(row.get('kind')) is not str or type(row.get('thread')) is not str or any(type(row.get(k)) is not int for k in ('monotonic_ns','boottime_ns','utc_ns')):
            return {'valid':False,'errors':['event shape/clocks must have exact types']}
    starts=[r for r in events if r['kind']=='spawn_start'];spawns=[r for r in events if r['kind']=='spawn_return']
    if len(spawns)<2 or Counter(r.get('shard') for r in starts)!=Counter(r.get('shard') for r in spawns):errors.append('original spawn accounting incomplete')
    pids=[]
    for row in spawns:
        identity=row.get('identity')
        if type(row.get('shard')) is not int or row['shard'] not in (0,1) or type(identity) is not dict or type(identity.get('pid')) is not int or identity['pid']<=1 or type(identity.get('start_ticks')) is not str:
            errors.append('original spawn identity invalid');continue
        pids.append(identity['pid'])
    if len(set(pids))!=len(pids):errors.append('duplicate PID cannot substitute a distinct original binding')
    final=[r for r in events if r['kind']=='final_owned_child']
    if len(final)!=len(pids) or {r.get('pid') for r in final}!=set(pids) or any(r.get('pidfd_exited') is not True or type(r.get('exitcode')) is not int for r in final):errors.append('all original bound children need real final pidfd exits')
    status_open={};status_done=set();last_supervisor=None;kill_open=[];kill_done=[]
    for row in events:
        kind=row['kind']
        if kind=='fence_status_start':
            cid=row.get('call_id')
            if type(cid) is not int or cid in status_open:errors.append('status call identity invalid or duplicate')
            else:status_open[cid]=row['thread']
        elif kind in ('fence_status_return','fence_status_error'):
            cid=row.get('call_id')
            if type(cid) is not int or cid not in status_open or cid in status_done or status_open[cid]!=row['thread']:errors.append('status completion has no unique actual call')
            else:status_done.add(cid)
            if row['thread']=='uta-process-supervisor':last_supervisor=row if kind=='fence_status_return' else None
        elif kind=='kill_start':
            kill_open.append((row.get('pid'),row['thread']))
            if row['thread']!='uta-process-supervisor':errors.append('non-supervisor kill is forced cleanup or unclassified; stop')
            if row.get('pid') not in pids:errors.append('kill lacks original spawn binding')
            observed=last_supervisor
            if (observed is None or observed.get('owner_pid')!=row.get('pid') or observed.get('active') is not False
                or type(observed.get('expires_ns')) is not int or type(observed.get('now_ns')) is not int
                or observed['expires_ns']>observed['now_ns']):errors.append('kill lacks original observed expired ownership proof')
        elif kind=='kill_return':kill_done.append((row.get('pid'),row['thread']))
        elif kind in ('observer_lifecycle_error','sampling_unavailable','observation_unavailable','pidfd_open_unavailable'):
            errors.append(kind+': technical unknown')
    if not status_open or set(status_open)!=status_done:errors.append('native status observations missing or unfinished')
    if Counter(kill_open)!=Counter(kill_done):errors.append('kill calls incomplete')
    flags=worker.get('evidence_flags',{})
    for name in ('pidfd','code_stack'):
        begin=[r for r in events if r['kind']=='observer_lifecycle_start' and r.get('observer')==name]
        end=[r for r in events if r['kind']=='observer_lifecycle_end' and r.get('observer')==name]
        post=[r for r in events if r['kind']=='observer_post_join' and r.get('observer')==name]
        if len(begin)!=1 or len(end)!=1 or len(post)!=1:errors.append(name+': missing/duplicate observer lifecycle')
        elif (post[0].get('is_alive') is not False or post[0].get('lifecycle')!=flags.get('observer_post_join',{}).get(name,{}).get('lifecycle')
              or begin[0]['monotonic_ns']>end[0]['monotonic_ns'] or end[0]['monotonic_ns']>post[0]['monotonic_ns']):errors.append(name+': actual observer end/postjoin inconsistency')
    if worker.get('case_passed') is True:
        observations=[r.get('observation') for r in events if r['kind']=='case_observations']
        if len(observations)!=1 or type(observations[0]) is not dict:errors.append('PASS lacks original observation')
        else:
            obs=observations[0];finance=obs.get('finance',{})
            if (finance.get('ledger_and_debt_unchanged') is not True or any(type(finance.get(k)) is not int or finance[k] not in (0,1) for k in ('orders','accepted_events'))):errors.append('PASS lacks original financial assertions')
            digest=obs.get('original_snapshot_sha256')
            if type(digest) is not str or re.fullmatch('[0-9a-f]{64}',digest) is None:errors.append('PASS lacks original snapshot digest')
            publications=[r for r in events if r['kind']=='publication_return' and r.get('version')==2]
            if len(publications)!=1 or type(publications[0].get('receipts')) is not dict or set(publications[0]['receipts'])!={'0','1'}:errors.append('PASS lacks two actual original publication receipts')
            elif type(digest) is str:
                for shard,receipt in publications[0]['receipts'].items():
                    if type(receipt) is not dict or receipt.get('state')!='SUCCEEDED' or receipt.get('command_id')!=f'market:3:{shard}:{digest[:16]}' or type(receipt.get('sequence')) is not int:errors.append('PASS original CID receipt mismatch')
    return {'valid':errors==[],'errors':errors,'spawn_bindings':len(pids),
            'monitor_expiry_kills':len(kill_open),'status_calls':len(status_open)}
