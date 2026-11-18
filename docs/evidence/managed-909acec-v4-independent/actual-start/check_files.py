"""Independent archived start evidence. No live job sampling, SQL or product imports."""
from datetime import datetime,timezone
from fractions import Fraction
from hashlib import sha256
import json
from pathlib import Path
PREP=Path('/workspace/uta-managed-909acec-prepare');ARC=PREP/'evidence/runs/managed-909acec-six-hours-start';V=PREP/'evidence/preparations/managed-909acec-v4'
SOURCE='909acecd153e2e89dfe2238e3ed3a3d9a3d3c9f0';BOOT='6339d4fc-a9e7-4c10-a591-1e70a14322ff';SRC=Path('/workspace/uta-credit-v2-py310-candidate')
checks=[];inputs={}
def need(ok,label):
 if not ok:raise AssertionError(label)
 checks.append(label)
def raw(p):
 b=p.read_bytes();inputs[str(p)]={'bytes':len(b),'sha256':sha256(b).hexdigest()};return b
def h(p):return sha256(raw(p)).hexdigest()
def load(p):return json.loads(raw(p))
pub=load(ARC/'manifest.json')
for name,spec in pub['files'].items():
 b=raw(PREP/name);need(len(b)==spec['bytes'] and sha256(b).hexdigest()==spec['sha256'],'public_manifest:'+Path(name).name)
m=load(ARC/'original-copy-and-private-stream-manifest.json');need(len(m['original_exact_copies'])==28 and len(m['private_closed_streams'])==8,'28_copies_8_raw')
immutable_original_comparisons=0
for item in m['original_exact_copies']:
 need(Path(item['copy']).name==item['copy'],'copy_plain_filename')
 b=raw(ARC/item['copy']);need(len(b)==item['bytes'] and sha256(b).hexdigest()==item['sha256'],'retained_copy:'+item['copy'])
 if '-private/' in item['original_path']:
  need(raw(Path(item['original_path']))==b,'immutable_original_exact:'+item['copy']);immutable_original_comparisons+=1
need(immutable_original_comparisons==16,'16_immutable_originals_12_job_snapshots_not_resampled')
for item in m['private_closed_streams']:
 need('-private/' in item['original_path'],'closed_raw_allowlist')
 b=raw(Path(item['original_path']));need(len(b)==item['bytes'] and sha256(b).hexdigest()==item['sha256'] and item['complete'] is True and item['raw_published'] is False,'raw:'+item['phase']+':'+item['stream'])
profile=load(PREP/'benchmarks/profiles/managed-909acec-v4-long-conditional.json');snapshots=[];phase_summary=[]
for phase in ('long-preflight','long-start'):
 specfile=V/(phase+'-spec.json');spec=load(specfile);root=load(ARC/(phase+'--root--root-approved-phase.json'))
 need(root['authorized'] is True and root['scope']=='ONE_EXACT_LONG_PHASE_NO_NEXT_PHASE' and root['phase']==phase,'root_scope:'+phase)
 need(root['spec_sha256']==h(specfile) and root['runner_sha256']==h(V/'run_one_long_phase.py')=='49c34950c38056be2fdef534a7d252a579fde20bd1d0f5195ec39df0ae527210' and root['profile_sha256']==h(Path(spec['profile_file']))=='9ecd5476c347fbf1d767445f6c73a26fde46b026c7008d9b0f24f36e8801213d','reviewed_three_SHA:'+phase)
 ap=next(ARC.glob(phase+'--*-admission.json'));a=load(ap);gp=next(ARC.glob(phase+'--*-root-delegated-phaseGO.json'));go=load(gp);pop=load(ARC/(phase+'--actual-Popen.json'));ident=pop['identity']
 need(go['authorized'] is True and go['root_phase_delegation_record_sha256']==h(ARC/(phase+'--root--root-approved-phase.json')) and go['root_approved_spec_sha256']==root['spec_sha256'] and go['snapshot_sha256']==h(ap),'phase_GO:'+phase)
 cmdh=sha256(json.dumps(spec['argv'],separators=(',',':')).encode()).hexdigest()
 need(root['command_sha256']==go['command_sha256']==pop['command_sha256']==a['phase_command_sha256']==spec['command_sha256']==cmdh,'actual_command:'+phase)
 need(a['source_commit']==root['source_commit']==SOURCE and a['source_boot']==root['source_boot']==ident['boot']==BOOT and a['phase']==go['phase']==phase,'source_boot_phase:'+phase)
 nw,nb=ident['captured_wall_ns'],ident['captured_boottime_ns'];cw,cb,vw,vb=(a[k] for k in ('captured_wall_ns','captured_boottime_ns','valid_until_wall_ns','valid_until_boottime_ns'))
 need(cw<=nw<vw and cb<=nb<vb and 0<=nw-cw<=15*10**9 and 0<=nb-cb<=15*10**9,'dual_clock_fresh_at_Popen:'+phase)
 po,lo,pm,lm=(a[k] for k in ('original_progress_observed_ns','original_latest_observed_ns','original_progress_mtime_ns','original_latest_mtime_ns'));ph,lh=(Fraction(str(a[k])) for k in ('original_progress_heartbeat_age_seconds','original_latest_heartbeat_age_seconds'))
 need(all(0<t<=cw for t in (po,lo,pm,lm)) and 0<=ph+Fraction(nw-po,10**9)<=15 and 0<=lh+Fraction(nw-lo,10**9)<=30 and 0<=nw-pm<=15*10**9 and 0<=nw-lm<=30*10**9,'original_effective_HB_mtime:'+phase)
 need(a['fresh_free_bytes']>=17448304640 and a['required_free_bytes']==17448304640,'full_combined_floor:'+phase)
 need(a['observer_source_commit']=='f96dfd8d6b1ca6f5ae28ac771c886baf4fdeb30e' and a['observer_interval_seconds']==60 and a['observer_default_post_write_software_threshold_bytes']==64*1024**2 and a['observer_original_no_alerts'] is True and a['conditional_floor_is_hard_quota'] is False and a['allowlisted_observer_cli']=={'--interval':'60'},'old_observer_policy:'+phase)
 for side in ('original_processes_before','original_processes_after'):
  need(all(a[side][str(pid)]['birth']==birth and a[side][str(pid)]['uids']==[1000]*4 and a[side][str(pid)]['state']=='S' for pid,birth in [(4471,'210004'),(8784,'412799')]),'old_identity:'+phase+':'+side)
 closed=load(ARC/(phase+'--closed-private-stream-manifest.json'))
 for stream,row in closed.items():
  need(row['complete'] is True and row['error'] is None and row['bytes']==row['retained_bytes'] and h(Path(row['file']))==row['sha256'],'closed_manifest_connection:'+phase+':'+stream)
 original=Path('/workspace/uta-managed-observer-runs')/('909acec-v4-'+phase+'-private');receipt=load(original/'actual-wrapper.stdout');body=receipt['structured_stdout']
 need(type(receipt['exit_code']) is int and receipt['exit_code']==0 and receipt['stdout_complete'] is True and receipt['stderr_present'] is False and receipt['phase']==phase,'actual_prepare_exit:'+phase)
 need('exit_code' not in body and 'timed_out' not in body,'actual_direct_target_shape:'+phase)
 att=load(ARC/(phase+'--root--root-phase-attestation.json'));out=load(ARC/(phase+'--phase-outcome.json'))
 need(att['runner_exit_code']==0 and att['primary_error'] is None and att['cleanup_secondary_errors']==[] and att['root_watchdog_reason'] is None and att['result']==out and out['status']=='PHASE_RECEIPT_VERIFIED','actual_runner_exit:'+phase)
 first=pop['first_Popen_boottime_ns'];pc=out['post_hash_clock'];end=att['root_post_stream_close_fsync_read_hash_parse_endpoint']
 need(pop['phase_deadline_boottime_ns']==first+75*10**9 and first<=nb<=pc['boottime_ns']<=end['boottime_ns']<pop['phase_deadline_boottime_ns'],'posthash_phase_bound:'+phase)
 need(root['issued_wall_ns']<=pc['wall_ns']<=end['wall_ns']<root['valid_until_wall_ns'] and root['issued_boottime_ns']<=first<=end['boottime_ns']<root['valid_until_boottime_ns'],'root_window:'+phase)
 need(out['next_phase_authorized'] is False and out['repeat_start_allowed'] is False,'no_repeat_or_next:'+phase)
 snapshots.append(h(ap));phase_summary.append({'phase':phase,'snapshot_sha256':h(ap),'post_Popen_remaining_ns':min(vw-nw,vb-nb),'captured_free_bytes':a['fresh_free_bytes'],'margin_bytes':a['fresh_free_bytes']-17448304640,'first_to_phase_post_hash_ns':pc['boottime_ns']-first,'first_to_root_post_hash_ns':end['boottime_ns']-first})
 if phase=='long-start':start_body=body;start_root=root
need(len(set(snapshots))==2,'start_has_new_snapshot_not_preflight_reuse')
need(start_root['spec_sha256']=='934dc15bcf1ec48f482335b0bf79ef9c6b53a65b48f60d1e9a947d770c1702ab' and start_root['independent_review_commit']=='43222eca2bc5c1948fb9ff2de7c07ce772e0838d','exact_reviewed_start_authority')
need(start_body['status']=='SUPERVISOR_STARTED_PENDING_ACTUAL_DRIVER' and start_body['supervisor_pid']==310035 and start_body['supervisor_birth']=='8086947','real_supervisor_start_receipt')
handoff=load(ARC/'actual-start-handoff.json');base=load(ARC/'job--observer--baseline.json');launch=load(ARC/'job--control--launch.json')
need(base['boot_id']==BOOT and base['frozen_commit']==SOURCE and base['driver_pid']==launch['driver_pid']==310039 and base['driver_birth']==launch['driver_birth']=='8086955','actual_original_driver_binding')
start,deadline=base['started_boottime_ns'],base['deadline_boottime_ns']
need(start==80871129103044 and deadline==102471129103044 and deadline-start==21600*10**9 and base['planned_rounds']==5400,'unchanged_authoritative_21600_clock')
need(handoff['actual_clock']['original_start_boottime_ns']==start and handoff['actual_clock']['original_deadline_boottime_ns']==deadline,'handoff_clock_matches_baseline')
need(launch['launched_boottime_ns']<=start and base['duration_seconds']==21600,'active_clock_not_approval_or_wrapper_start')
for name,digest in {**base['source_sha256'],**{str(Path('tools')/k):v for k,v in base['observer_code_sha256'].items()}}.items():
 need(h(SRC/name)==digest,'baseline_source_byte:'+name)
identities={(x['pid'],x['birth']) for x in handoff['process_metadata']}
need(identities=={(310035,'8086947'),(310039,'8086955'),(310266,'8087358'),(310269,'8087359')},'four_original_live_recorded_identities')
need(all(x['boot']==BOOT and x['uids']==[1000]*4 and x['state_before'] in 'RSDI' and x['state_after'] in 'RSDI' for x in handoff['process_metadata']),'recorded_PID_birth_boot_UID_states')
watch=next(x for x in handoff['process_metadata'] if x['pid']==310269)
need(watch['--interval']=='61' and watch['--frozen-commit']==SOURCE and watch['--driver-pid']=='310039' and watch['--driver-birth']=='8086955','actual_watch_argv_policy')
need(load(ARC/'job--control--supervisor-identity.json')['pid']==310035 and load(ARC/'job--control--observer-identity.json')['pid']==310266 and load(ARC/'job--observer--watch-cli-identity.json')['pid']==310269,'control_identity_records')
prefix=m['observer_JSONL_prefix'];b=raw(ARC/prefix['copy']);rows=[json.loads(line) for line in b.splitlines()]
need(len(b)==prefix['bytes']==471537 and sha256(b).hexdigest()==prefix['sha256']=='737d0aa3f64dea39f358e0a30a2464866e3ad25eee45dbe382614d7df5c902ab' and len(rows)==prefix['complete_original_rows']==5 and b.endswith(b'\n'),'complete_original_prefix_5_rows_hash')
need([r['logical_point'] for r in rows]==['stable_boundary']*4+['inflight_or_unknown'] and [r['completed_rounds'] for r in rows]==[1,16,31,46,60] and all(r['alerts']==[] for r in rows),'all_original_unknown_rows_preserved')
need(all(r['finance']['golden']['compared'] is True and r['finance']['golden']['passed'] is True for r in rows[:4]),'first_four_recorded_golden_comparisons_pass')
need(all(all(r[k] is False for k in ('continuous_6h_stability_passed','continuous_24h_stability_passed','capacity_10000_per_s_passed','production_approved','final_evidence_eligible')) for r in rows),'sample_future_flags_false')
need(rows[4]['active_rounds']==[61] and rows[4]['finance']['golden']['compared'] is False,'fifth_inflight_not_golden_pass')
need(all(r['original_start_boottime_ns']==start and r['original_deadline_boottime_ns']==deadline and r['planned_rounds']==5400 and r['frozen_commit']==SOURCE for r in rows),'all_samples_same_original_clock_source')
need(all(rows[i]['sample_wall_ns']<rows[i+1]['sample_wall_ns'] for i in range(4)),'retained_sample_order')
coverage=load(ARC/'job--control--live-coverage.json')
need(coverage['samples_observed']==4 and coverage['logical_point_counts']=={'stable_boundary':4} and coverage['financial_golden_counts']['stable_compared_passed']==4 and coverage['coverage_status']=='PENDING' and coverage['counts']['technical_read_unknown_samples']==0,'earlier_coverage_4stable_pending')
need(handoff['snapshots_are_from_different_logical_points'] is True and handoff['financial_comparisons_across_these_snapshots_not_performed'] is True,'no_cross_watermark_financial_comparison')
need(all(handoff[k] is False for k in ('financial_6h_passed','live_coverage_passed','continuous_6h_stability_passed','production_approved','capacity_10000_per_s_passed','new_start_or_resume_authorized_by_this_archive')),'all_final_flags_false')
need(handoff['original_763_and_first01_remain_NO_GO'] is True,'original_NO_GO_unchanged')
anchor=handoff['actual_clock'];mapped_start=[anchor[k]+start-anchor['anchor_boottime_ns'] for k in ('anchor_wall_before_ns','anchor_wall_after_ns')];mapped_end=[x+21600*10**9 for x in mapped_start]
print(json.dumps({'status':'ACTUAL_START_HANDOFF_RETAINED_FILE_SCOPE_ACCEPT_NOT_6H','reviewed_at_utc':datetime.now(timezone.utc).isoformat(),'checks_passed':len(checks),'checks':checks,'input_hashes':inputs,'source_commit':SOURCE,'author_archive_commit':'a9af0622f13a6276bd787296ea0a8d749cab6ce8','phase_bounds':phase_summary,'archived_metadata':28,'immutable_originals_compared':16,'job_metadata_snapshots_hash_verified_without_current_resampling':12,'closed_raw_hashes_verified':8,'recorded_live_identities':sorted([list(x) for x in identities]),'original_active_start_boottime_ns':start,'original_deadline_boottime_ns':deadline,'duration_seconds':21600,'planned_rounds':5400,'start_wall_mapping_ns_interval':mapped_start,'deadline_wall_mapping_ns_interval':mapped_end,'UTC_mapping_is_approximate_handoff_anchor_not_authoritative_clock':True,'archived_prefix_rows':5,'inflight_row_kept':True,'new_live_sample_SQL_or_status_or_signal_or_Popen':False,'financial_6h_passed':False,'live_coverage_passed':False,'production_approved':False,'new_start_or_resume_authorized':False},indent=2,sort_keys=True))
