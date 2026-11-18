"""One fresh pinned package; explicit config, retained first outcomes and streams."""
from datetime import datetime,timezone
from hashlib import sha256
from pathlib import Path,PurePosixPath
import argparse,json,os,platform,shlex,sqlite3,subprocess,sys,tarfile,time
parser=argparse.ArgumentParser()
parser.add_argument('phase',choices=['core','v2','runtime','zip','strict'])
parser.add_argument('--config',type=Path,required=True)
args=parser.parse_args();config=json.loads(args.config.read_text())
COMMIT=config['source_commit'];source=Path(config['source_directory']).resolve()
work=Path(config['work_directory']).resolve();scripts=Path(config['evidence_directory']).resolve()
assert scripts==Path(__file__).resolve().parent and work.is_dir()
assert work!=source and not work.is_relative_to(source) and source!=scripts
os.sched_setaffinity(0,{2});report=work/'raw';report.mkdir(exist_ok=True)
env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1');env.pop('PYTHONPATH',None)
metadata={'source_commit':COMMIT,'expected_git_tree':config['expected_git_tree'],'source_directory':str(source),'work_directory':str(work),'driver_path':str(Path(__file__).resolve()),'driver_sha256':sha256(Path(__file__).read_bytes()).hexdigest(),'driver_cwd':str(Path.cwd()),'config_path':str(args.config.resolve()),'config_sha256':sha256(args.config.read_bytes()).hexdigest(),'phase':args.phase,'python':sys.version,'interpreter':sys.executable,'sqlite':sqlite3.sqlite_version,'platform':platform.platform(),'cohosted':True,'affinity':sorted(os.sched_getaffinity(0)),'cpu_isolation':'CPU2 per-process affinity on shared host; no cpuset or exclusivity','environment':{'PYTHONPATH':None,'PYTHONDONTWRITEBYTECODE':'1'},'git_archive_format':'tar.gz','prior_functional_or_binary_results_reused':False,'production_approved':False}
phasefile=report/('execution.json' if args.phase=='core' else args.phase+'-execution.json')
assert not phasefile.exists(),'retain existing evidence; never rerun a phase'
records=[]
def flush():
 phasefile.write_text(json.dumps({**metadata,'runs':records},indent=2,sort_keys=True)+'\n')
 (report/(args.phase+'-commands.txt')).write_text('Shared-host CPU2 affinity; PYTHONPATH unset; bytecode writes disabled. First outcomes retained.\n\n'+'\n\n'.join('cwd '+r['cwd']+'\n'+shlex.join(r['argv'])+'\nreturncode='+str(r['returncode']) for r in records)+'\n')
def run(name,argv,cwd,timeout=60,scope='functional'):
 argv=[str(x) for x in argv];started=datetime.now(timezone.utc).isoformat();at=time.monotonic_ns()
 outpath,errpath=report/(name+'.stdout.txt'),report/(name+'.stderr.txt')
 assert not outpath.exists() and not errpath.exists(),'retain existing attempt streams'
 assert scope!='functional' or timeout<=60
 print('BEGIN',name,started,'scope',scope,'timeout',timeout,flush=True)
 rec={'name':name,'argv':argv,'cwd':str(cwd),'scope':scope,'started_utc':started,'started_monotonic_ns':at,'timeout_seconds':timeout,'expected_returncode':0}
 try:
  with outpath.open('xb') as out,errpath.open('xb') as err:
   result=subprocess.run(argv,cwd=cwd,env=env,stdout=out,stderr=err,timeout=timeout)
  rec['returncode']=result.returncode
 except subprocess.TimeoutExpired:
  rec['returncode']=124;rec['timed_out']=True
 rec.update(finished_utc=datetime.now(timezone.utc).isoformat(),finished_monotonic_ns=time.monotonic_ns())
 rec['seconds']=(rec['finished_monotonic_ns']-at)/1e9
 for label,path in (('stdout',outpath),('stderr',errpath)):
  rec[label]={'path':str(path),'sha256':sha256(path.read_bytes()).hexdigest(),'bytes':path.stat().st_size}
 records.append(rec);flush();print('END',name,rec['returncode'],round(rec['seconds'],3),flush=True)
 if rec['returncode']:raise SystemExit(rec['returncode'])
 return rec
def artifact_paths():
 value=json.loads((work/'artifact-paths.json').read_text())
 assert value['source_commit']==COMMIT
 return tuple(Path(value[name]) for name in ('wheel','sdist','unpacked_source'))
flush();py=Path(sys.executable);venv=work/'venv/bin/python'
if args.phase=='core':
 for directory in ('artifacts','build-source','external','sdist-unpacked'):(work/directory).mkdir()
 stat=os.statvfs(work);(report/'initial-filesystem.json').write_text(json.dumps({'available_bytes':stat.f_bavail*stat.f_frsize,'recorded_utc':datetime.now(timezone.utc).isoformat()})+'\n')
 run('initial-df',['df','-B1',work],work,scope='identity')
 run('frozen-source-commit',['git','rev-parse','HEAD'],source,scope='identity')
 assert (report/'frozen-source-commit.stdout.txt').read_text().strip()==COMMIT
 run('frozen-source-tree',['git','rev-parse','HEAD^{tree}'],source,scope='identity')
 assert (report/'frozen-source-tree.stdout.txt').read_text().strip()==config['expected_git_tree']
 run('frozen-source-status',['git','status','--short','--untracked-files=all'],source,scope='identity')
 assert (report/'frozen-source-status.stdout.txt').read_text()==''
 run('venv',[py,'-m','venv',work/'venv'],work)
 run('git-archive',['git','archive','--format=tar.gz','--output='+str(work/'frozen-source.tar.gz'),COMMIT],source,scope='archive-only')
 run('extract-git',[py,scripts/'safe_extract.py',work/'frozen-source.tar.gz',work/'build-source'],work,scope='archive-only')
 assert not (work/'build-source/.git').exists()
 run('build',[py,'-c','import setuptools.build_meta as b; print("WHEEL",b.build_wheel('+repr(str(work/'artifacts'))+')); print("SDIST",b.build_sdist('+repr(str(work/'artifacts'))+'))'],work/'build-source',scope='build')
 wheels=list((work/'artifacts').glob('*.whl'));sdists=list((work/'artifacts').glob('*.tar.gz'));assert len(wheels)==len(sdists)==1
 wheel,sdist=wheels[0],sdists[0]
 with tarfile.open(sdist) as archive:
  names=archive.getnames();roots={PurePosixPath(name).parts[0] for name in names}
  assert len(roots)==1 and all(not PurePosixPath(name).is_absolute() and '..' not in PurePosixPath(name).parts for name in names)
 unpacked=work/'sdist-unpacked'/roots.pop()
 (work/'artifact-paths.json').write_text(json.dumps({'source_commit':COMMIT,'wheel':str(wheel),'sdist':str(sdist),'unpacked_source':str(unpacked)},indent=2)+'\n')
 run('verify-archives',[py,source/'tools/verify_release_archives.py','--source',source,'--commit',COMMIT,'--wheel',wheel,'--sdist',sdist,'--output',work/'artifact-manifest.json'],work,timeout=180,scope='archive-only')
 manifest=json.loads((work/'artifact-manifest.json').read_text())
 assert len(manifest['sdist_required_files'])==config['expected_tracked_files'] and len(manifest['runtime_files'])==config['expected_runtime_files']
 assert manifest['runtime_tree_sha256']==config['expected_runtime_tree_sha256']
 run('install',[venv,'-m','pip','install','--no-deps','--no-index',wheel],work/'external')
 run('installed-run',[venv,'-I',source/'tools/validate_installed_release.py','--source',source,'--artifact-manifest',work/'artifact-manifest.json','--output',work/'external/installed'],work/'external')
 run('installed-views-run',[venv,'-I',source/'evidence/20261117-package-13e6924/validate_installed_views.py','--source',source,'--artifact-manifest',work/'artifact-manifest.json','--output',work/'external/installed-views'],work/'external')
 run('extract-sdist',[py,scripts/'safe_extract.py',sdist,work/'sdist-unpacked'],work,scope='archive-only')
 assert not (unpacked/'.git').exists()
 run('sdist-legacy-tests',[venv,'-m','unittest','discover','-s','tests','-p','test_writer_fence_legacy.py','-v'],unpacked)
 run('sdist-archival-tests',[venv,'-c','from pathlib import Path; import sys,unittest; assert not Path(".git").exists(); sys.path.insert(0,"tests"); from test_managed_benchmark import ManagedBenchmarkTests; suite=unittest.TestSuite([ManagedBenchmarkTests("test_archived_real_probe_preserves_all_arrivals_and_known_profile_limits")]); result=unittest.TextTestRunner(verbosity=2).run(suite); raise SystemExit(not result.wasSuccessful())'],unpacked)
 run('sdist-release-verifier-tests',[venv,'-m','unittest','discover','-s','tests','-p','test_release_archives.py','-v'],unpacked)
 run('history-reference',[venv,'-m','unittest','discover','-s','tests','-p','test_capacity_review_data_reference.py','-v'],unpacked)
 run('frozen-source-final-commit',['git','rev-parse','HEAD'],source,scope='identity')
 assert (report/'frozen-source-final-commit.stdout.txt').read_text().strip()==COMMIT
 run('frozen-source-final-status',['git','status','--short','--untracked-files=all'],source,scope='identity')
 assert (report/'frozen-source-final-status.stdout.txt').read_text()==''
elif args.phase=='v2':
 wheel,sdist,unpacked=artifact_paths()
 run('installed-internal-v2',[venv,'-I',scripts/'installed_v2_smoke.py','--unpacked',unpacked,'--private-root',work/'internal-v2-private','--output',work/'installed-internal-v2.json'],work/'external')
elif args.phase=='runtime':
 wheel,sdist,unpacked=artifact_paths()
 run('runtime-negative-controls',[py,source/'evidence/20261117-package-4608ffe/runtime_omission_controls.py','--source',source,'--manifest',work/'artifact-manifest.json','--wheel',wheel,'--sdist',sdist,'--output',work/'runtime-omission-controls'],work,timeout=180,scope='archive-only')
elif args.phase=='zip':
 wheel,sdist,unpacked=artifact_paths()
 rec=run('tracked-zip',[py,source/'evidence/20261117-package-a35fd56/verify_tracked_ci_zips.py','--source',source,'--manifest',work/'artifact-manifest.json','--wheel',wheel,'--sdist',sdist,'--unpacked-source',unpacked,'--provenance',scripts/'ci-zip-provenance.json','--output',work/'tracked-ci-zip-checks'],work,timeout=900,scope='archive-only')
 (report/'tracked-zip-execution.json').write_text(json.dumps(rec,indent=2)+'\n')
elif args.phase=='strict':
 run('strict-control-bindings',[py,scripts/'verify_control_bindings.py','--source',source,'--commit',COMMIT,'--work',work,'--records',scripts,'--provenance',scripts/'ci-zip-provenance.json','--output',work/'strict-control-bindings.json'],work,timeout=180,scope='archive-only read-only inspection')
 run('final-df',['df','-B1',work],work,scope='identity')
print('phase complete',args.phase,flush=True)
