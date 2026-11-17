"""Copy explicit safe text evidence only; preserve all external binaries/state."""
from datetime import datetime,timezone
from hashlib import sha256
from pathlib import Path
import importlib.metadata,json,os,platform,re,shutil,sqlite3,subprocess,sys
COMMIT='dbc93e5d50125e6ab8f1154511a537f8b1a8fa1b'
SOURCE=Path('/workspace/uta-combined-freeze-dbc93e5')
DEST=Path(__file__).resolve().parent
WORK=Path('/workspace/uta-package-dbc93e5-work.txt').read_text().strip();WORK=Path(WORK)
def identity(path):return {'sha256':sha256(path.read_bytes()).hexdigest(),'bytes':path.stat().st_size}
def read(path):return json.loads(path.read_text())
def main():
 os.sched_setaffinity(0,{2})
 mapping={}
 def add(original,name):
  assert name not in mapping and original.suffix in ('.txt','.json','.py')
  mapping[name]=original
 manifest=read(WORK/'artifact-manifest.json');strict=read(WORK/'strict-control-bindings.json')
 assert manifest['source_commit']==COMMIT and manifest['passed'] is True and strict['passed'] is True
 for phase in ('core','zip','strict','v2'):
  path=WORK/'raw'/('execution.json' if phase=='core' else phase+'-execution.json');data=read(path)
  assert data['source_commit']==COMMIT and all(r['returncode']==0 for r in data['runs'])
  add(path,'raw/'+path.name);add(WORK/'raw'/(phase+'-commands.txt'),'raw/'+phase+'-commands.txt')
  for run in data['runs']:
   for stream in ('stdout','stderr'):
    name=run['name']+'.'+stream+'.txt';add(WORK/'raw'/name,'raw/'+name)
  for stream in ('stdout','stderr'):
   name=phase+'-driver.'+stream+'.txt';add(WORK/name,name)
 add(WORK/'raw/initial-filesystem.json','initial-filesystem.json')
 add(WORK/'raw/tracked-zip-execution.json','tracked-zip-execution.json')
 for name in ('artifact-manifest.json','strict-control-bindings.json','source-proof.json','installed-internal-v2.json'):
  add(WORK/name,name)
 installed=WORK/'external/installed'
 for name in ('installed-report.json','installed-cli-tests.txt'):add(installed/name,'installed/'+name)
 for cmd in ('uta-durable---help','uta-ops---help','uta-demo','uta-acceptance','uta-scenario','uta-durable-init','uta-durable-inspect','uta-durable-status'):
  for stream in ('stdout','stderr'):
   name=cmd+'.'+stream+'.txt';add(installed/name,'installed/'+name)
 for name in ('installed-views-report.json','installed-view-tests.txt'):add(WORK/'external/installed-views'/name,'installed-views/'+name)
 for name in ('controls.json','wheel-report.json','sdist-report.json','wheel.stdout.txt','wheel.stderr.txt','sdist.stdout.txt','sdist.stderr.txt'):
  add(WORK/'runtime-omission-controls'/name,'runtime-omission-controls/'+name)
 zipdata=read(WORK/'tracked-ci-zip-checks/tracked-ci-zips.json')
 add(WORK/'tracked-ci-zip-checks/tracked-ci-zips.json','tracked-ci-zip-checks/tracked-ci-zips.json')
 for index in range(len(zipdata['omission_controls'])):
  for suffix in ('-report.json','.stdout.txt','.stderr.txt'):
   name='zip-'+str(index)+suffix;add(WORK/'tracked-ci-zip-checks'/name,'tracked-ci-zip-checks/'+name)
 forbidden=(rb'-----BEGIN (?:RSA |EC |OPENSSH |ENCRYPTED )?(?:PRIVATE KEY|CERTIFICATE)-----',rb'https?://[^\s\"<>]+[?&](?:sig|signature|token|access_token)=',rb'(?im)^Authorization:\s*(?:Bearer|Basic)\s+\S+')
 copied={}
 for name,original in sorted(mapping.items()):
  data=original.read_bytes();data.decode('utf-8');assert not any(re.search(p,data) for p in forbidden),'private material: '+name
  target=DEST/name;assert not target.exists(),'retain original evidence, no overwrite'
  target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(original,target);assert target.read_bytes()==data
  copied[name]={'original_path':str(original),**identity(target)}
 status=subprocess.check_output(['git','status','--porcelain','--untracked-files=all'],cwd=SOURCE,text=True)
 head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=SOURCE,text=True).strip();assert head==COMMIT and status==''
 stat=os.statvfs(WORK)
 environment={'recorded_utc':datetime.now(timezone.utc).isoformat(),'source_commit':head,'source_status':status,'python':sys.version,'sqlite':sqlite3.sqlite_version,'setuptools':importlib.metadata.version('setuptools'),'wheel':importlib.metadata.version('wheel'),'platform':platform.platform(),'execution_affinity':[2],'cohosted':True,'exclusive_host_or_cpuset':False,'dependency_downloads':0,'source_directory':str(SOURCE),'private_work_directory':str(WORK),'git_archive_format':'tar.gz','build_source_has_git':(WORK/'build-source/.git').exists(),'unpacked_source_has_git':(WORK/'sdist-unpacked/uta_reference_exchange-0.5.0a1/.git').exists(),'free_bytes_after_collection':stat.f_bavail*stat.f_frsize}
 (DEST/'environment.json').write_text(json.dumps(environment,indent=2,sort_keys=True)+'\n')
 archive_paths=[WORK/'frozen-source.tar.gz',*sorted((WORK/'artifacts').iterdir()),WORK/'runtime-omission-controls/missing-failure-diagnostics.whl',WORK/'runtime-omission-controls/missing-failure-diagnostics.tar.gz',*sorted((WORK/'tracked-ci-zip-checks').glob('*-omitted.tar.gz'))]
 assert len(archive_paths)==5+len(zipdata['omission_controls'])
 (DEST/'retained-archive-inventory.json').write_text(json.dumps({'source_commit':COMMIT,'archives':{str(path):identity(path) for path in archive_paths},'archive_count':len(archive_paths),'all_archives_retained':True,'negative_archives_installed':False,'production_approved':False},indent=2,sort_keys=True)+'\n')
 no_git_tests={}
 for name,label,expected in (('sdist-legacy-tests','legacy',7),('sdist-archival-tests','archived_profile',1),('sdist-release-verifier-tests','release_verifier',19),('history-reference','historical_source_contract',10)):
  log=(WORK/'raw'/(name+'.stderr.txt')).read_text()
  counts=re.findall(r'Ran (\d+) tests? in ',log)
  assert counts==[str(expected)] and log.rstrip().endswith('OK'),'unexpected no-Git tests/skips: '+name
  no_git_tests[label]={'run':int(counts[0]),'failures':0,'errors':0,'skipped':0}
 v2=read(WORK/'installed-internal-v2.json');assert v2['passed'] is True
 verdict={'source_commit':COMMIT,'artifacts':manifest['artifacts'],'version':manifest['version'],'tracked_source_files_exact':len(manifest['sdist_required_files']),'dynamic_runtime_files_exact':len(manifest['runtime_files']),'runtime_tree_sha256':manifest['runtime_tree_sha256'],'positive_archive_complete_seven_checks':manifest['checks'],'installed_cli':read(installed/'installed-report.json')['tests'],'installed_console_commands':len(read(installed/'installed-report.json')['commands']),'installed_views':read(WORK/'external/installed-views/installed-views-report.json')['tests'],'no_git_sdist_tests':no_git_tests,'actual_runtime_omission_controls':strict['actual_runtime_omissions'],'actual_tracked_ci_zip_omission_controls':strict['actual_tracked_zip_omissions'],'strict_actual_bytes_complete_seven_checks':strict['passed'],'installed_internal_v2':v2,'package_scope_passed':True,'overall_candidate_status':'NO_GO','overall_candidate_status_basis':'root reported current dbc CI failures; package exercise does not retest current CI','all_loaded_uta_modules_installed':True,'all_available_submodules_actually_imported':False,'all_62_runtime_files_installed_byte_exact':True,'this_report_qualifies_full_QA_or_CI':False,'historical_failures_unchanged':True,'capacity_10000_per_second_qualified':False,'HA_qualified':False,'real_funds_qualified':False,'production_approved':False,'negative_artifacts_installed':False,'private_binary_material_published':False}
 (DEST/'package-verdict.json').write_text(json.dumps(verdict,indent=2,sort_keys=True)+'\n')
 (DEST/'public-allowlist.json').write_text(json.dumps({'source_commit':COMMIT,'copied_files':copied,'copied_original_bytes_unchanged':True,'content_screening_passed':True,'policy':'Explicit text/JSON/Python files only; no recursive private directory copy. All release/negative/CI archives, DBs, auth/TLS material remain external.','production_approved':False},indent=2,sort_keys=True)+'\n')
 print(json.dumps({'copied_files':len(copied),'free_bytes':environment['free_bytes_after_collection'],'package_scope_passed':True}))
if __name__=='__main__':main()
