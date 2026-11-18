"""Minimum file/hash/clock admission guard; never starts a phase or samples cohost."""
from hashlib import sha256
import json
import math
from pathlib import Path

SOURCE='909acecd153e2e89dfe2238e3ed3a3d9a3d3c9f0'
BOOT='6339d4fc-a9e7-4c10-a591-1e70a14322ff'


def command_sha256(command):
    return sha256(json.dumps(list(command),separators=(',',':')).encode()).hexdigest()


def consume_guard(profilefile,commandtuple,snapshotfile,root_go,*,now_wall_ns,now_boottime_ns,current_boot):
    """root_go is supplied only after root's explicit approval for this phase.

    A matching profile/hash alone grants no permission. Caller must check this
    immediately before the reviewed frozen invoke, with current wall/boot clocks.
    """
    def need(ok,code):
        if not ok:raise ValueError(code)
    need(type(root_go) is dict and root_go.get('authorized') is True,'specific_phase_root_GO_missing')
    need(type(commandtuple) in (tuple,list) and all(type(x) is str for x in commandtuple),'command_tuple_invalid')
    raw_profile=Path(profilefile).read_bytes();raw_snapshot=Path(snapshotfile).read_bytes()
    need(sha256(raw_profile).hexdigest()==root_go.get('profile_sha256'),'root_GO_profile_hash_mismatch')
    need(sha256(raw_snapshot).hexdigest()==root_go.get('snapshot_sha256'),'root_GO_snapshot_hash_mismatch')
    need(command_sha256(commandtuple)==root_go.get('command_sha256'),'root_GO_command_hash_mismatch')
    p,r=json.loads(raw_profile),json.loads(raw_snapshot)
    need(p.get('source_commit')==r.get('source_commit')==SOURCE,'source_binding_changed')
    need(r.get('status')=='ADMISSION_METADATA_COMPONENT_PASS_NOT_PHASE_GO','admission_not_passed')
    need(r.get('profile_sha256')==root_go['profile_sha256'] and r.get('phase_command_sha256')==root_go['command_sha256']
        and r.get('phase')==root_go.get('phase'),'phase_snapshot_binding_changed')
    def flag(name):
        need(commandtuple.count(name)==1,'command_flag_missing_or_duplicate')
        i=commandtuple.index(name);need(i+1<len(commandtuple),'command_flag_value_missing');return commandtuple[i+1]
    need(list(commandtuple[:3])==[p['python'],'-B',str(Path(p['source_root'])/'tools/prepare_managed_stability.py')]
        and flag('--profile')==str(profilefile) and flag('--invoke')==root_go['phase']
        and flag('--root-go-profile-sha256')==root_go['profile_sha256'],'frozen_wrapper_command_changed')
    need(p['qualification']['status']=='COMPLETE_ALL_GATES_PASSED' and p['qualification'].get('blocked_reason') is None
        and all(p['qualification'].get(k) is True for k in ('all_three_local_passed','all_eight_ci_passed','independent_new_package_passed'))
        and p['resource_review'].get('old_observer_floor_approved') is True,'static_qualification_or_policy_incomplete')
    try:
        cw,cb,vw,vb=(r[k] for k in ('captured_wall_ns','captured_boottime_ns','valid_until_wall_ns','valid_until_boottime_ns'))
        po,lo,pm,lm=(r[k] for k in ('original_progress_observed_ns','original_latest_observed_ns','original_progress_mtime_ns','original_latest_mtime_ns'))
        ph,lh=(r[k] for k in ('original_progress_heartbeat_age_seconds','original_latest_heartbeat_age_seconds'))
    except KeyError:
        raise ValueError('admission_clock_field_missing') from None
    need(all(type(x) is int and 0<x<=2**63-1 for x in (cw,cb,vw,vb,po,lo,pm,lm,now_wall_ns,now_boottime_ns)), 'admission_clock_type_unknown')
    need(current_boot==r.get('source_boot')==BOOT,'boot_changed')
    need(cw<=now_wall_ns<vw and cb<=now_boottime_ns<vb
        and 0<=now_boottime_ns-cb<=15*10**9 and 0<=now_wall_ns-cw<=15*10**9,'admission_expired_or_clock_rolled_back')
    need(all(0<x<=now_wall_ns for x in (po,lo,pm,lm)),'original_timestamp_from_future')
    need(all(type(x) in (int,float) and math.isfinite(x) and x>=0 for x in (ph,lh)),'original_heartbeat_invalid')
    pa,la=(now_wall_ns-po)/1e9,(now_wall_ns-lo)/1e9
    need(0<=pa<=15 and 0<=la<=30 and 0<=(now_wall_ns-pm)/1e9<=15 and 0<=(now_wall_ns-lm)/1e9<=30
        and abs(pm-po)<=15*10**9 and abs(lm-lo)<=15*10**9 and 0<=ph+pa<=15 and 0<=lh+la<=30,'original_heartbeat_or_mtime_stale')
    need(type(r.get('fresh_free_bytes')) is int and r['fresh_free_bytes']>=17_448_304_640,'resource_floor_not_met')
    return {'fresh_admission_check_passed':True,'phase':root_go['phase'],
        'remaining_validity_ns':min(vw-now_wall_ns,vb-now_boottime_ns),
        'phase_execution_performed':False,'guard_is_not_blanket_permission':True}
