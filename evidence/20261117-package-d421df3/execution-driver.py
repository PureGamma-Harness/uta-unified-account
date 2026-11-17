from datetime import datetime,timezone
from hashlib import sha256
from pathlib import Path
import json,os,platform,shlex,sqlite3,subprocess,sys,tarfile,time
source=Path('/workspace/uta-observer-freeze-d421df3')
report=Path('/workspace/uta-package-d421df3/raw')
work=Path('/workspace/uta-package-d421df3-work.txt').read_text().strip();work=Path(work)
report.mkdir(parents=True,exist_ok=False)
os.sched_setaffinity(0,{2})
env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1');env.pop('PYTHONPATH',None)
records=[]
def run(name,argv,cwd,allow_failure=False):
 started=datetime.now(timezone.utc).isoformat();at=time.monotonic()
 with (report/(name+'.stdout.txt')).open('wb') as out,(report/(name+'.stderr.txt')).open('wb') as err:
  p=subprocess.run([str(x) for x in argv],cwd=cwd,env=env,stdout=out,stderr=err)
 rec={'name':name,'argv':[str(x) for x in argv],'cwd':str(cwd),'environment':{'PYTHONPATH':None,'PYTHONDONTWRITEBYTECODE':'1'},'affinity':[2],'started_utc':started,'finished_utc':datetime.now(timezone.utc).isoformat(),'seconds':time.monotonic()-at,'returncode':p.returncode,'expected_returncode':0}
 records.append(rec);(report/'execution.json').write_text(json.dumps({'source_commit':'d421df3fc5123e8267f0eecf8bb5efdc37cd0dc6','work_directory':str(work),'cohosted':True,'cpu_isolation':'per-process affinity CPU2 only; no cpuset or exclusive-host guarantee','runs':records},indent=2)+'\n')
 (report/'commands.txt').write_text('All commands inherit per-process affinity CPU2, PYTHONDONTWRITEBYTECODE=1 and unset PYTHONPATH. Source is read only; output is fresh. No host/cpuset isolation.\n\n'+'\n\n'.join('cwd '+r['cwd']+'\n'+shlex.join(r['argv'])+'\nreturncode='+str(r['returncode']) for r in records)+'\n')
 print(name,p.returncode,round(rec['seconds'],3),flush=True)
 if p.returncode and not allow_failure: raise SystemExit(p.returncode)
 return p.returncode
py=Path(sys.executable)
for directory in ('artifacts','build-source','external','sdist-unpacked'): (work/directory).mkdir()
run('frozen-source-commit',['git','rev-parse','HEAD'],source)
run('frozen-source-status',['git','status','--short'],source)
run('venv',[py,'-m','venv',work/'venv'],report)
run('git-archive',['git','archive','--format=tar','--output='+str(work/'frozen-source.tar'),'HEAD'],source)
with tarfile.open(work/'frozen-source.tar') as archive: archive.extractall(work/'build-source')
assert not (work/'build-source/.git').exists()
run('build',[py,'-c','import setuptools.build_meta as b; print("WHEEL", b.build_wheel('+repr(str(work/'artifacts'))+')); print("SDIST", b.build_sdist('+repr(str(work/'artifacts'))+'))'],work/'build-source')
wheel=work/'artifacts/uta_reference_exchange-0.5.0a1-py3-none-any.whl';sdist=work/'artifacts/uta_reference_exchange-0.5.0a1.tar.gz'
run('verify-archives',[py,source/'tools/verify_release_archives.py','--source',source,'--commit','d421df3fc5123e8267f0eecf8bb5efdc37cd0dc6','--wheel',wheel,'--sdist',sdist,'--output',work/'artifact-manifest.json'],report)
venv=work/'venv/bin/python'
run('install',[venv,'-m','pip','install','--no-deps','--no-index',wheel],work/'external')
run('installed-run',[venv,'-I',source/'tools/validate_installed_release.py','--source',source,'--artifact-manifest',work/'artifact-manifest.json','--output',work/'external/installed'],work/'external')
run('installed-views-run',[venv,'-I',source/'evidence/20261117-package-13e6924/validate_installed_views.py','--source',source,'--artifact-manifest',work/'artifact-manifest.json','--output',work/'external/installed-views'],work/'external')
with tarfile.open(sdist) as archive: archive.extractall(work/'sdist-unpacked')
unpacked=work/'sdist-unpacked/uta_reference_exchange-0.5.0a1'
assert not (unpacked/'.git').exists()
run('sdist-legacy-tests',[venv,'-m','unittest','discover','-s','tests','-p','test_writer_fence_legacy.py','-v'],unpacked)
run('sdist-archival-tests',[venv,'-c','from pathlib import Path; import sys,unittest; assert not Path(".git").exists(); sys.path.insert(0,"tests"); from test_managed_benchmark import ManagedBenchmarkTests; suite=unittest.TestSuite([ManagedBenchmarkTests("test_archived_real_probe_preserves_all_arrivals_and_known_profile_limits")]); result=unittest.TextTestRunner(verbosity=2).run(suite); raise SystemExit(not result.wasSuccessful())'],unpacked)
run('sdist-release-verifier-tests',[venv,'-m','unittest','discover','-s','tests','-p','test_release_archives.py','-v'],unpacked)
run('runtime-negative-controls',[py,source/'evidence/20261117-package-4608ffe/runtime_omission_controls.py','--source',source,'--manifest',work/'artifact-manifest.json','--wheel',wheel,'--sdist',sdist,'--output',work/'runtime-omission-controls'],report)
run('frozen-source-final-commit',['git','rev-parse','HEAD'],source)
run('frozen-source-final-status',['git','status','--short'],source)
print('core package checks complete; eight tracked ZIP inclusion/omission checks pending independent provenance registration',flush=True)
