"""Read-only original full-suite integrity audit; no SQL/product imports."""
from datetime import datetime,timezone
from decimal import Decimal
import hashlib,json,os,re,subprocess
from pathlib import Path
REF='912f2a4e5ed74f7a3fbf892ff0172e4eacc9c45a'
SOURCE=Path('/workspace/uta-auth-h0-qa-912f2a4')
ROOT=Path('/workspace/uta-auth-h0-full-validation/912f2a4-first')
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def stable(path):
 a=path.stat();raw=path.read_bytes();b=path.stat();assert(a.st_ino,a.st_size,a.st_mtime_ns)==(b.st_ino,b.st_size,b.st_mtime_ns)
 return raw
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=SOURCE,text=True).strip()==REF
admission=json.loads(stable(ROOT/'root-admission.json'))
assert admission['source_commit']==REF and admission['cpu']==4
launcher=Path('/workspace/run_uta_h0_full_matrix_912.py')
assert digest(launcher)==admission['launcher_sha256']
cache={};maps=[];runs=[]
for label in ('python312','python310','python313-sqlite346'):
 summary_path=ROOT/label/'summary.json';worker_path=ROOT/label/'worker-result.json';log=ROOT/label/'unittest.txt'
 s=json.loads(stable(summary_path));w=json.loads(stable(worker_path));p=json.loads(stable(ROOT/(label+'-actual-Popen.json')))
 assert s['code_commit']==REF and s['source_sha256']==s['source_sha256_after']
 assert len(s['source_sha256'])==359
 for name,expected in s['source_sha256'].items():
  if name not in cache:cache[name]=hashlib.sha256(subprocess.check_output(['git','show',REF+':'+name],cwd=SOURCE)).hexdigest()
  assert cache[name]==expected and digest(SOURCE/name)==expected
 maps.append(s['source_sha256'])
 assert s['tests_run']==w['tests_run']==1823
 for key in ('failures','errors','skipped','expected_failures','unexpected_successes'):assert s[key]==w[key]==0
 assert s['passed'] is True and s['unittest_passed'] is True and w['unittest_passed'] is True and s['worker_exit_code']==0
 assert s['tracked_source_clean_before'] is True and s['tracked_source_clean_after'] is True and s['source_unchanged'] is True
 assert digest(log)==s['test_log_sha256']
 trailer=re.findall(rb'Ran (\d+) tests in ([0-9.]+)s\s+OK(?:\s|$)',stable(log))
 assert len(trailer)==1 and int(trailer[0][0])==1823
 normalized=[x for x in p['command'] if x!='-B'];assert normalized==s['command_argv']
 outcome_path=ROOT/(label+'-first-outcome.json');outcome=None
 if outcome_path.exists():
  outcome=json.loads(stable(outcome_path));assert outcome['exit_code']==0 and outcome['watchdog_reason'] is None
  assert outcome['raw_sha256']==digest(ROOT/(label+'-private-launcher.txt'))
  assert outcome['source_input_count']==359 and outcome['result']['tests_run']==1823
 runs.append({'label':label,'inner_started_at':s['started_at'],'inner_finished_at':s['finished_at'],'unit_duration_seconds':s['duration_seconds'],
  'python':s['python'],'sqlite':s['sqlite'],'tests_run':1823,'failures':0,'errors':0,'skipped':0,'inner_summary_passed':True,
  'source_inputs':359,'all_source_inputs_match_original_git_and_current_files':True,
  'summary_sha256':digest(summary_path),'worker_result_sha256':digest(worker_path),'private_unittest_sha256':digest(log),'private_unittest_bytes':log.stat().st_size,
  'private_launcher_sha256':digest(ROOT/(label+'-private-launcher.txt')),'private_launcher_bytes':(ROOT/(label+'-private-launcher.txt')).stat().st_size,
  'actual_Popen':p,'controller_first_outcome_present':outcome is not None,
  'controller_first_outcome_sha256':digest(outcome_path) if outcome else None,
  'controller_outer_monotonic_ns':outcome['outer_monotonic_ns'] if outcome else None,
  'rounded_unittest_trailer_seconds':trailer[0][1].decode()})
assert maps[0]==maps[1]==maps[2]
assert not(ROOT/'python313-sqlite346-first-outcome.json').exists() and not(ROOT/'matrix-summary.json').exists()
proc=Path('/proc/306017');observation={'pid':306017,'present':proc.exists()}
if proc.exists():
 text=(proc/'stat').read_text();fields=text[text.rfind(')')+2:].split()
 observation.update(state=fields[0],ppid=int(fields[1]),birth=fields[19],linux_encoded_exit_status=int(fields[-1]))
 status=(proc/'status').read_text();observation['cpus_allowed_list']=re.search(r'^Cpus_allowed_list:\s*(.*)$',status,re.M)[1]
 assert fields[19]=='8046790'
report={'source_commit':REF,'audited_at':datetime.now(timezone.utc).isoformat(),'runs':runs,'same359_input_map':True,
 'unit_duration_sum_seconds_decimal':str(sum(Decimal(str(r['unit_duration_seconds'])) for r in runs)),
 'outer_controller_complete':False,'third_first_outcome_absent':True,'matrix_summary_absent':True,
 'third_wrapper_exit_observation':observation,'third_wrapper_reaped_by_original_controller_proven':False,
 'cpu_evidence':'original root admission and unchanged launcher set affinity4 before Popen; third extant process metadata observed separately; no invented current CPU sample for gone first/second wrappers',
 'original_launcher_sha256':digest(launcher),'original_files_written':False,'raw_streams_published':False,
 'product_or_sql_imported':False,'rerun':False,'production_approved':False,
 'decision':'THREE_INNER_UNIT_SUMMARIES_PASS_SOURCE_BOUND_CONTROLLER_RECORDING_INCOMPLETE'}
print(json.dumps(report,indent=2))
