"""Archive original a35 CI/local bytes only; no tests, SQL or load are run."""
from datetime import datetime,timezone
from hashlib import sha256
import io,json,os,re,shutil,subprocess,tarfile,zipfile
from pathlib import Path,PurePosixPath

ROOT=Path(__file__).resolve().parents[3]
OUT=Path(__file__).resolve().parent
SOURCE='a35fd56fc98126b3e5cced8a459bd04ca580e537'
MERGE='2959d4dec3941d8898f60d27fee8bd15fbd452e8'
ALL=Path('/workspace/uta-ci-a35-all')
LOCAL=Path('/workspace/uta-capacity-validation/final-a35fd56')
FAIL=Path('/workspace/uta-ci-a35-failures')


def digest(raw):return sha256(raw).hexdigest()
def load(path):return json.loads(path.read_text())
def write_json(path,value):path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value,indent=2)+'\n')
def copy(source,target):
 target.parent.mkdir(parents=True,exist_ok=True)
 assert not target.exists()
 shutil.copyfile(source,target)
 assert source.read_bytes()==target.read_bytes()
def no_secret_urls(raw):
 # Exact raw files remain unmodified. Fail before publishing unexpected payloads.
 assert not re.search(rb'[?&](?:sig|sv)=',raw), 'signed-download URL in selected evidence'
 assert not re.search(rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',raw),'private key payload'

def main():
 assert not (OUT/'index.json').exists()
 catalog=load(ALL/'artifact-catalog.json')
 assert catalog['source_reference']==SOURCE and len(catalog['artifacts'])==14
 no_secret_urls((ALL/'artifact-catalog.json').read_bytes())
 copy(ALL/'artifact-catalog.json',OUT/'artifact-catalog.json')
 tree=subprocess.check_output(['git','rev-parse',SOURCE+'^{tree}'],cwd=ROOT,text=True).strip()
 original=subprocess.check_output(['git','archive','--format=tar',SOURCE],cwd=ROOT)
 with tarfile.open(fileobj=io.BytesIO(original)) as archive:
  source={entry.name:archive.extractfile(entry).read() for entry in archive.getmembers() if entry.isfile()}
 assert len(source)==1961
 runtime={name:digest(raw) for name,raw in source.items() if name.startswith('uta/') and name.endswith(('.py','.html'))}
 assert len(runtime)==51
 runtime_tree=digest(json.dumps(runtime,sort_keys=True,separators=(',',':')).encode())
 remote=json.loads(subprocess.check_output(['gh','api','repos/PureGamma-Harness/uta-unified-account/git/commits/'+MERGE,'--jq','{sha,tree_sha:.tree.sha,parents:[.parents[].sha]}'],cwd=ROOT,text=True))
 assert remote['sha']==MERGE and remote['tree_sha']==tree and SOURCE in remote['parents']
 write_json(OUT/'source-identity.json',{'head_commit':SOURCE,'head_tree':tree,'actual_pr_checkout':remote,'trees_exactly_equal':True,'tracked_paths':1961,'runtime_files':51,'runtime_tree_sha256':runtime_tree,'code_commit_fields_preserved':True})
 jobs={}
 for run in catalog['run_jobs']:
  assert len(run['jobs'])==4
  for job in run['jobs']:
   version=re.fullmatch(r'test \((3\.\d+)\)',job['name'])[1]
   jobs[run['run'],version]=job
 assert len(jobs)==8
 local=[]
 for label in ('python312','python310','python313-sqlite346'):
  base=LOCAL/label;s=load(base/'summary.json');w=load(base/'worker-result.json')
  proof=unit_check(s,w,(base/'unittest.txt').read_bytes(),source,SOURCE)
  assert proof['passed'] and proof['tests_run']==1243
  for name in ('summary.json','worker-result.json','unittest.txt'):
   no_secret_urls((base/name).read_bytes());copy(base/name,OUT/'local'/label/name)
  copy(LOCAL/(label+'-launcher.txt'),OUT/'local'/(label+'-launcher.txt'))
  local.append({'label':label,**proof})
 for name in ('matrix-summary.json','matrix-progress.json'):copy(LOCAL/name,OUT/'local'/name)
 matrix=load(LOCAL/'matrix-summary.json');assert matrix['source_commit']==SOURCE and matrix['all_exit_zero']
 launcher=Path('/workspace/run_uta_final_matrix.py')
 assert digest(launcher.read_bytes())==matrix['launcher_sha256']
 copy(launcher,OUT/'local'/'run_uta_final_matrix.py')
 records=[]
 for item in catalog['artifacts']:
  base=ALL/str(item['run'])/item['name'];z=base/'original-artifact.zip'
  raw=z.read_bytes();assert digest(raw)==item['sha256'] and len(raw)==item['size_in_bytes']
  dest=OUT/'ci'/str(item['run'])/item['name']
  version=item['name'].rsplit('-',1)[1];job=jobs[item['run'],version]
  expected=SOURCE if item['run']==44066483487 else MERGE
  with zipfile.ZipFile(io.BytesIO(raw)) as archive:
   names=archive.namelist();assert len(names)==len(set(names))
   members={}
   for entry in archive.infolist():
    path=PurePosixPath(entry.filename)
    assert not path.is_absolute() and '..' not in path.parts
    assert (entry.external_attr>>16)&0o170000 !=0o120000
    assert not entry.is_dir()
    value=archive.read(entry);no_secret_urls(value)
    members[entry.filename]=value
   if item['name'].startswith('uta-unit-'):
    assert set(names)=={'summary.json','worker-result.json','unittest.txt'}
    s=json.loads(members['summary.json']);w=json.loads(members['worker-result.json'])
    detail=unit_check(s,w,members['unittest.txt'],source,expected)
    assert detail['tests_run']==1243
    assert (job['conclusion']=='success') is detail['passed']
    if not detail['passed']:copy(z,dest/'original-ci-artifact.zip')
   else:
    detail=package_check(members,source,runtime,runtime_tree,expected)
    assert job['conclusion']=='success'
   for name,value in members.items():
    target=dest/name;target.parent.mkdir(parents=True,exist_ok=True);assert not target.exists();target.write_bytes(value)
  records.append({**item,'job_id':job['id'],'job_conclusion':job['conclusion'],'actual_code_commit':expected,'archive_retention':'external original retained; failed unit ZIP also public' if not detail['passed'] else 'external original retained; all original members public','member_sha256':{n:digest(v) for n,v in members.items()},**detail})
  for name in ('retrieval-receipt.json','plugin-retrieval-receipt.json'):
   if (base/name).exists():copy(base/name,OUT/'retrieval'/str(item['id'])/name)
 for original_log in sorted(FAIL.glob('job-*.txt')):
  no_secret_urls(original_log.read_bytes());copy(original_log,OUT/'ci-joblogs'/original_log.name)
 write_json(OUT/'retrieval'/'history.json',{'initial_six_missing_artifacts_reported_by_integration_owner':True,'reported_initial_error':'HTTP403 on expired short-lived file reference; not CI business result','two_failed_unit_zips':'reused exact already-held bytes after catalog SHA comparison; no CI rerun','four_remaining_artifacts':'gh API binary transfer failed with no bytes; sanitized status/digest retained, then fresh plugin reference immediately downloaded exact bytes','signed_urls_saved':False,'test_or_ci_rerun':False})
 copy(Path('/workspace/uta-ci-a35-refresh.py'),OUT/'retrieval'/'gh-refresh-driver.py')
 units=[r for r in records if r['name'].startswith('uta-unit-')]
 packages=[r for r in records if r['name'].startswith('uta-package-')]
 assert len(units)==8 and len(packages)==6
 assert sum(r['passed'] for r in units)==6 and all(r['passed'] for r in packages)
 write_json(OUT/'index.json',{'source_reference':SOURCE,'actual_pr_checkout':MERGE,'source_trees_equal':True,'created_utc':datetime.now(timezone.utc).isoformat(),'local_runs':local,'ci_artifacts':records,'local_full_passes':3,'ci_unit_passes':6,'ci_unit_failures':2,'ci_package_passes':6,'ci_package_absent_due_to_failed_unit_jobs':['push-python3.13','pr-python3.12'],'qualification':'NO_GO','missing_artifacts':[],'original_results_rewritten':False,'new_tests_sql_or_load_executed':False,'production_approved':False,'capacity_10000_per_s_passed':False,'financial_long_stability_qualified':False})
 print(json.dumps({'local_full_passes':3,'ci_unit_passes':6,'ci_unit_failures':2,'ci_package_passes':6,'original_artifacts_checked':14,'qualification':'NO_GO','new_tests_sql_or_load_executed':False}))


def unit_check(s,w,log,source,expected_commit):
 assert s['code_commit']==expected_commit
 assert digest(log)==s['test_log_sha256']
 assert s['source_sha256']==s['source_sha256_after'] and len(s['source_sha256'])==227
 assert all(digest(source[name])==value for name,value in s['source_sha256'].items())
 for key in ('tests_run','failures','errors','skipped','expected_failures','unexpected_successes','unittest_passed'):assert s[key]==w[key]
 assert s['source_unchanged'] and s['tracked_source_clean_before'] and s['tracked_source_clean_after']
 passed=s['unittest_passed'] and s['worker_exit_code']==0
 assert s['passed'] is passed
 headers=re.findall(r'^(?:FAIL|ERROR): .*$',log.decode(),re.M)
 assert len(headers)==s['failures']+s['errors']
 return {key:s[key] for key in ('tests_run','failures','errors','skipped','expected_failures','unexpected_successes','passed','python','sqlite','duration_seconds')}|{'verification_inputs_exact_head':227,'actual_report_commit':s['code_commit'],'raw_test_log_sha256':digest(log),'failure_headers':headers,'resource_warning_lines':len(re.findall(r'^.*ResourceWarning:',log.decode(),re.M)),'gate':'PASS for recorded test scope' if passed else 'NO_GO'}


def package_check(members,source,runtime,runtime_tree,expected):
 names=set(members)
 console=['uta-durable---help','uta-ops---help','uta-demo','uta-acceptance','uta-scenario','uta-durable-init','uta-durable-inspect','uta-durable-status']
 expected_names={'uta-package-artifact-manifest.json','uta-installed-validation/installed-report.json','uta-installed-validation/installed-cli-tests.txt'}|{'uta-installed-validation/'+name+suffix for name in console for suffix in ('.stdout.txt','.stderr.txt')}
 assert names==expected_names and len(names)==19
 p=json.loads(members['uta-package-artifact-manifest.json']);installed=json.loads(members['uta-installed-validation/installed-report.json'])
 assert p['source_commit']==installed['source_commit']==expected
 assert p['passed'] and all(p['checks'].values()) and p['version']=='0.5.0a1'
 assert set(p['sdist_required_files'])==set(source) and len(p['sdist_required_files'])==1961
 assert not p['sdist_missing'] and not p['sdist_mismatched']
 assert p['runtime_files']==runtime and p['runtime_tree_sha256']==runtime_tree
 assert installed['runtime_tree_sha256']==runtime_tree and installed['version']=='0.5.0a1'
 assert installed['passed'] and installed['isolated'] and installed['pythonpath'] is None
 assert installed['tests']=={'run':8,'failures':0,'errors':0,'skipped':0}
 assert len(installed['commands'])==8 and all(row['returncode']==0 for row in installed['commands'])
 assert installed['artifacts']==p['artifacts']
 assert installed['helper_sha256']==installed['copied_helper_sha256']==digest(source['tests/test_durable_cli.py'])
 site=PurePosixPath(installed['installed_site'])
 assert all(PurePosixPath(path).is_relative_to(site) for path in installed['modules'].values())
 assert installed['production_approved'] is False and p['production_approved'] is False
 assert not re.search(r'/(?:auth|signing|credentials|empty-cli-authority)(?:/|\.)|\.(?:sqlite3|pem|key)$','\n'.join(names))
 return {'passed':True,'gate':'PASS for recorded package scope only','reported_tracked_files_exact':1961,'runtime_files_exact_head':51,'runtime_tree_sha256':runtime_tree,'installed_isolated':True,'installed_tests':installed['tests'],'successful_console_commands':8,'original_member_allowlist_exact':19,'authority_auth_tls_state_in_artifact':False,'version':p['version'],'artifact_hashes':p['artifacts']}

if __name__=='__main__':main()
