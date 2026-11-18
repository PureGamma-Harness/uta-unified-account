import datetime,hashlib,json,os,pathlib,re,stat,time
ROOT=pathlib.Path('/workspace/uta-managed-observer-runs/909acec-six-hours-20261117')
OUT=pathlib.Path('/workspace/uta-909-terminal-firstseal-private-20261118')
assert os.sched_getaffinity(0)=={3}
FILES={'progress':'job/progress.json','job':'job/job.json','launch':'control/launch.json','baseline':'observer/baseline.json','producer':'control/producer-result.json','cold':'control/strict-producer-cold-result.json','before':'control/final-before-cold.json','after':'control/final-after-cold.json','final':'control/final-summary.json','coverage':'control/live-coverage.json','collection_errors':'control/collection-errors.jsonl','supervisor_failure':'control/supervisor-failure.json','cold_receipt':'observer/producer-cold-audit-receipt.json','supervisor_identity':'control/supervisor-identity.json','supervisor_heartbeat':'control/supervisor-heartbeat.json','observer_identity':'control/observer-identity.json'}
raws={};records={};inventory={}
def no_duplicates(items):
 result={}
 for key,value in items:
  if key in result:raise ValueError('duplicate-json-key')
  result[key]=value
 return result
def read(label,relative):
 path=ROOT/relative
 try:fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NOATIME)
 except FileNotFoundError:
  inventory[label]={'relative':relative,'state':'MISSING'};return
 with os.fdopen(fd,'rb') as stream:
  before=os.fstat(stream.fileno());assert stat.S_ISREG(before.st_mode) and before.st_size<=67108864
  raw=stream.read(67108865);after=os.fstat(stream.fileno())
  assert len(raw)==before.st_size and (before.st_ino,before.st_size,before.st_mtime_ns,before.st_ctime_ns)==(after.st_ino,after.st_size,after.st_mtime_ns,after.st_ctime_ns)
 inventory[label]={'relative':relative,'state':'OBSERVED','bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),'inode':before.st_ino,'device':before.st_dev,'mtime_ns':before.st_mtime_ns,'ctime_ns':before.st_ctime_ns,'stable_during_read':True}
 if len(raw)<=1048576:
  copy=OUT/'small-originals'/relative;copy.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
  fd=os.open(copy,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
  with os.fdopen(fd,'wb') as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())
 if relative.endswith('.jsonl'):
  records[label]=[json.loads(line,object_pairs_hook=no_duplicates) for line in raw.splitlines() if line]
 else:records[label]=json.loads(raw,object_pairs_hook=no_duplicates)
for label,relative in FILES.items():read(label,relative)
def obj(v,key):
 x=v.get(key) if isinstance(v,dict) else None
 return x if isinstance(x,dict) else {}
def fields(v,keys):return {k:v[k] for k in keys if isinstance(v,dict) and k in v}
def safe_codes(v):
 if not isinstance(v,list):return {'state':'NOT_A_LIST'}
 return {'known_format_codes':[x for x in v if isinstance(x,str) and re.fullmatch('[A-Za-z0-9_]{1,100}',x)],'unexported_items':sum(not(isinstance(x,str) and re.fullmatch('[A-Za-z0-9_]{1,100}',x)) for x in v)}
def reconciliation(v):
 rec=obj(v,'final_reconciliation');finance=obj(v,'finance')
 return {'observer':fields(v,('frozen_commit','contract_sha256','original_start_boottime_ns','original_deadline_boottime_ns','active_elapsed_seconds','planned_rounds','completed_rounds','active_rounds','logical_point','unresolved_steps','unresolved_faults','final_evidence_eligible','financial_ready')),'alerts':safe_codes(v.get('alerts')),'final_reconciliation':fields(rec,('eligible','watermark','independent_reopen_same_watermark','independent_reopen_reconciliation_passed','producer_audit_sha256','observer_is_formal_signoff')),'final_reconciliation_errors':safe_codes(rec.get('errors')),'financial_golden':fields(obj(finance,'golden'),('compared','passed','reason','completed_rounds','remaining_principal_satoshi')),'financial_golden_errors':safe_codes(obj(finance,'golden').get('errors')),'financial_counts':obj(finance,'counts'),'finance_retry_alert_count':len(finance.get('retry_alerts',[])) if isinstance(finance.get('retry_alerts'),list) else None,'log_verification':fields(obj(rec,'logs'),('verified','events','last_hash')),'residuals':fields(obj(finance,'residuals'),('live_orders',)),'position_residual_count':len(obj(finance,'residuals').get('positions',[])) if isinstance(obj(finance,'residuals').get('positions'),list) else None}
public={'synthetic':True,'observation_only':True,'observed_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'boot_id':pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip(),'source_commit_expected':'909acecd153e2e89dfe2238e3ed3a3d9a3d3c9f0','inventory':inventory,'progress':fields(records.get('progress'),('status','elapsed_seconds','planned_rounds','rounds','unresolved_steps','unresolved_faults','fault_signals','logs_verified','final_audit','controller_sessions','verified_tls','error','continuous_6h_stability_passed','continuous_24h_stability_passed','capacity_10000_per_s_passed','production_approved')),'results':{},'final_summary':fields(records.get('final'),('synthetic','status','financial_final_evidence_eligible','official_driver_drain_requested','expected_fault_signals','actual_fault_signals','fault_schedule_complete','overall_engineering_evidence_within_gates','no_automatic_resume_or_next_job','production_approved','capacity_10000_per_s_passed','financial_6h_passed','continuous_6h_stability_passed','continuous_24h_stability_passed')),'collection_errors':safe_codes(obj(records,'final').get('collection_errors')),'historical_financial_alerts':safe_codes(obj(records,'final').get('historical_financial_alert_codes')),'collection_error_events':[],'coverage':fields(records.get('coverage'),('coverage_status','measurement_status','samples_observed','actual_completed_active_seconds','preregistered_duration_seconds','preregistered_interval_seconds','counts','financial_golden_counts','fatal_financial_code_counts','technical_read_unknown_budget','maximum_observed_consecutive_technical_read_unknown')),'coverage_no_go':safe_codes(obj(records,'coverage').get('coverage_no_go_reasons')),'protected_processes':{}}
for label in ('producer','cold','before','after'):
 value=records.get(label,{})
 public['results'][label]={'outer':fields(value,('exit_code','identity','ended_wall_ns','stdout_sha256','stdout_complete','stderr_present','stderr_sha256')),'response_present':isinstance(value.get('response'),dict),'response_status':fields(obj(value,'response'),('status','mode','planned_rounds','rounds','elapsed_seconds','unresolved_steps','unresolved_faults','fault_signals','logs_verified','final_audit','controller_sessions','verified_tls','final_evidence_eligible','producer_cold_audit_passed'))}
 if label in ('before','after'):public['results'][label]['observation']=reconciliation(obj(value,'response'))
for event in records.get('collection_errors',[]):
 public['collection_error_events'].append(fields(event,('synthetic','at_wall_ns','code','action','signal_sent','measured_bytes','budget_bytes','financial_drain_requested','error_type','error_digest','measured_output_bytes','output_budget_bytes')))
for pid,birth in ((310035,'8086947'),(310039,'8086955'),(310266,'8087358'),(310269,'8087359')):
 try:
  row=pathlib.Path(f'/proc/{pid}/stat').read_text().rsplit(')',1)[1].split()
  public['protected_processes'][str(pid)]={'birth':row[19],'expected_birth':birth,'identity_matches':row[19]==birth,'state':row[0],'ppid':int(row[1]),'exit_code_encoded':int(row[49]) if len(row)>49 else None}
 except FileNotFoundError:public['protected_processes'][str(pid)]={'state':'ABSENT','expected_birth':birth}
(OUT/'safe-first-observation.json').write_text(json.dumps(public,sort_keys=True,indent=2,allow_nan=False)+'\n')
print(json.dumps({'status':'READ_ONLY_FIRST_SEAL_FINISHED','records':len(FILES),'source_files_written':False,'sql_executed':False,'raw_timeline_copied':False,'stdout_large_json_printed':False,'observed_at':public['observed_at_utc'],'progress_status':public['progress'].get('status'),'elapsed':public['progress'].get('elapsed_seconds'),'rounds':public['progress'].get('rounds'),'result_exit_codes':{k:v['outer'].get('exit_code') for k,v in public['results'].items()},'final':public['final_summary'],'observer_large_response_present':{k:public['results'][k]['response_present'] for k in ('before','after')},'safe_observation_sha256':hashlib.sha256((OUT/'safe-first-observation.json').read_bytes()).hexdigest()},sort_keys=True))
