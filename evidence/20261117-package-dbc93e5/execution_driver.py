"""Fresh pinned build/functional/archive phases; preserve every outcome."""
from datetime import datetime,timezone
from hashlib import sha256
from pathlib import Path
import argparse,json,os,platform,shlex,sqlite3,subprocess,sys,time
COMMIT='dbc93e5d50125e6ab8f1154511a537f8b1a8fa1b'
source=Path('/workspace/uta-combined-freeze-dbc93e5')
root=Path('/workspace/uta-package-dbc93e5')
scripts=Path(__file__).resolve().parent
work=Path('/workspace/uta-package-dbc93e5-work.txt').read_text().strip();work=Path(work)
report=work/'raw';report.mkdir(exist_ok=True)
os.sched_setaffinity(0,{2})
env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1');env.pop('PYTHONPATH',None)
parser=argparse.ArgumentParser();parser.add_argument('phase',choices=['core','zip','strict','v2']);args=parser.parse_args()
metadata={'source_commit':COMMIT,'source_directory':str(source),'work_directory':str(work),'driver_path':str(Path(__file__).resolve()),'driver_sha256':sha256(Path(__file__).read_bytes()).hexdigest(),'driver_cwd':str(Path.cwd()),'phase':args.phase,'python':sys.version,'sqlite':sqlite3.sqlite_version,'platform':platform.platform(),'cohosted':True,'affinity':sorted(os.sched_getaffinity(0)),'cpu_isolation':'per-process CPU2 affinity only; shared host; no cpuset or exclusivity','environment':{'PYTHONPATH':None,'PYTHONDONTWRITEBYTECODE':'1'},'git_archive_format':'tar.gz','production_approved':False}
phasefile=report/('execution.json' if args.phase=='core' else args.phase+'-execution.json')
assert not phasefile.exists(),'retain existing evidence; never rerun same phase'
records=[]
def flush():
 phasefile.write_text(json.dumps({**metadata,'runs':records},indent=2,sort_keys=True)+'\n')
 (report/(args.phase+'-commands.txt')).write_text('Shared-host CPU2 per-process affinity; no exclusive-host claim. PYTHONPATH unset; PYTHONDONTWRITEBYTECODE=1.\n\n'+'\n\n'.join('cwd '+r['cwd']+'\n'+shlex.join(r['argv'])+'\nreturncode='+str(r['returncode']) for r in records)+'\n')
def run(name,argv,cwd,timeout=60):
 argv=[str(x) for x in argv]; started=datetime.now(timezone.utc).isoformat();at=time.monotonic_ns()
 outpath,errpath=report/(name+'.stdout.txt'),report/(name+'.stderr.txt')
 assert not outpath.exists() and not errpath.exists(),'retain existing attempt logs'
 print('BEGIN',name,started,'timeout',timeout,flush=True)
 rec={'name':name,'argv':argv,'cwd':str(cwd),'started_utc':started,'started_monotonic_ns':at,'timeout_seconds':timeout,'expected_returncode':0}
 try:
  with outpath.open('xb') as out,errpath.open('xb') as err:
   p=subprocess.run(argv,cwd=cwd,env=env,stdout=out,stderr=err,timeout=timeout)
  rec['returncode']=p.returncode
 except subprocess.TimeoutExpired:
  rec['returncode']=124;rec['timed_out']=True
 rec.update(finished_utc=datetime.now(timezone.utc).isoformat(),finished_monotonic_ns=time.monotonic_ns())
 rec['seconds']=(rec['finished_monotonic_ns']-at)/1e9
 rec['stdout']={'path':str(outpath),'sha256':sha256(outpath.read_bytes()).hexdigest(),'bytes':outpath.stat().st_size}
 rec['stderr']={'path':str(errpath),'sha256':sha256(errpath.read_bytes()).hexdigest(),'bytes':errpath.stat().st_size}
 records.append(rec);flush();print('END',name,rec['returncode'],round(rec['seconds'],3),flush=True)
 if rec['returncode']:raise SystemExit(rec['returncode'])
 return rec
flush();py=Path(sys.executable);venv=work/'venv/bin/python'
wheel=work/'artifacts/uta_reference_exchange-0.5.0a1-py3-none-any.whl';sdist=work/'artifacts/uta_reference_exchange-0.5.0a1.tar.gz'
unpacked=work/'sdist-unpacked/uta_reference_exchange-0.5.0a1'
if args.phase=='core':
 for directory in ('artifacts','build-source','external','sdist-unpacked'): (work/directory).mkdir()
 stat=os.statvfs(work);(report/'initial-filesystem.json').write_text(json.dumps({'available_bytes':stat.f_bavail*stat.f_frsize,'recorded_utc':datetime.now(timezone.utc).isoformat()})+'\n')
 run('frozen-source-commit',['git','rev-parse','HEAD'],source)
 assert (report/'frozen-source-commit.stdout.txt').read_text().strip()==COMMIT
 run('frozen-source-status',['git','status','--short'],source)
 assert (report/'frozen-source-status.stdout.txt').read_text()==''
 run('venv',[py,'-m','venv',work/'venv'],work)
 run('git-archive',['git','archive','--format=tar.gz','--output='+str(work/'frozen-source.tar.gz'),COMMIT],source)
 run('extract-git',[py,scripts/'safe_extract.py',work/'frozen-source.tar.gz',work/'build-source'],work)
 assert not (work/'build-source/.git').exists()
 run('build',[py,'-c','import setuptools.build_meta as b; print("WHEEL", b.build_wheel('+repr(str(work/'artifacts'))+')); print("SDIST", b.build_sdist('+repr(str(work/'artifacts'))+'))'],work/'build-source')
 run('verify-archives',[py,source/'tools/verify_release_archives.py','--source',source,'--commit',COMMIT,'--wheel',wheel,'--sdist',sdist,'--output',work/'artifact-manifest.json'],work)
 run('install',[venv,'-m','pip','install','--no-deps','--no-index',wheel],work/'external')
 run('installed-run',[venv,'-I',source/'tools/validate_installed_release.py','--source',source,'--artifact-manifest',work/'artifact-manifest.json','--output',work/'external/installed'],work/'external')
 run('installed-views-run',[venv,'-I',source/'evidence/20261117-package-13e6924/validate_installed_views.py','--source',source,'--artifact-manifest',work/'artifact-manifest.json','--output',work/'external/installed-views'],work/'external')
 run('extract-sdist',[py,scripts/'safe_extract.py',sdist,work/'sdist-unpacked'],work)
 assert not (unpacked/'.git').exists()
 run('sdist-legacy-tests',[venv,'-m','unittest','discover','-s','tests','-p','test_writer_fence_legacy.py','-v'],unpacked)
 run('sdist-archival-tests',[venv,'-c','from pathlib import Path; import sys,unittest; assert not Path(".git").exists(); sys.path.insert(0,"tests"); from test_managed_benchmark import ManagedBenchmarkTests; suite=unittest.TestSuite([ManagedBenchmarkTests("test_archived_real_probe_preserves_all_arrivals_and_known_profile_limits")]); result=unittest.TextTestRunner(verbosity=2).run(suite); raise SystemExit(not result.wasSuccessful())'],unpacked)
 run('sdist-release-verifier-tests',[venv,'-m','unittest','discover','-s','tests','-p','test_release_archives.py','-v'],unpacked)
 run('history-reference',[venv,'-m','unittest','discover','-s','tests','-p','test_capacity_review_data_reference.py','-v'],unpacked)
 run('runtime-negative-controls',[py,source/'evidence/20261117-package-4608ffe/runtime_omission_controls.py','--source',source,'--manifest',work/'artifact-manifest.json','--wheel',wheel,'--sdist',sdist,'--output',work/'runtime-omission-controls'],work)
 run('frozen-source-final-commit',['git','rev-parse','HEAD'],source)
 run('frozen-source-final-status',['git','status','--short'],source)
elif args.phase=='zip':
 rec=run('tracked-zip',[py,source/'evidence/20261117-package-a35fd56/verify_tracked_ci_zips.py','--source',source,'--manifest',work/'artifact-manifest.json','--wheel',wheel,'--sdist',sdist,'--unpacked-source',unpacked,'--provenance',scripts/'ci-zip-provenance.json','--output',work/'tracked-ci-zip-checks'],work,timeout=600)
 (report/'tracked-zip-execution.json').write_text(json.dumps(rec,indent=2)+'\n')
elif args.phase=='strict':
 run('strict-control-bindings',[py,scripts/'verify_control_bindings.py','--source',source,'--work',work,'--records',scripts,'--provenance',scripts/'ci-zip-provenance.json','--output',work/'strict-control-bindings.json'],work)
elif args.phase=='v2':
 run('installed-internal-v2',[venv,'-I',scripts/'installed_v2_smoke.py','--unpacked',unpacked,'--private-root',work/'internal-v2-private','--output',work/'installed-internal-v2.json'],work/'external')
print('phase complete',args.phase,flush=True)
