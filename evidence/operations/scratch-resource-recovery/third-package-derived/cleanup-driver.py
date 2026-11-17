from datetime import datetime,timezone
from hashlib import sha256
from pathlib import Path
import json,os,shutil,stat,subprocess
os.sched_setaffinity(0,{3})
roots=[Path('/tmp/uta-release-d421df3-yy2hmth8'),Path('/tmp/uta-release-8b7f544-r6v0zf_q'),Path('/tmp/uta-release-91e4ae4-k1knnpel')]
targets=[r/n for r in roots for n in ('build-source','sdist-unpacked','venv')]
output=Path('/workspace/uta-safe-scratch-cleanup/third-package-derived');output.mkdir(exist_ok=False)
for p in targets:
 assert p.parent in roots and p.name in ('build-source','sdist-unpacked','venv')
 assert p.is_dir() and not p.is_symlink() and p.stat().st_uid==os.getuid()
assert not any(str(t).startswith('/workspace/') for t in targets)
def digest(p):
 h=sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def retained():
 result={}
 for r in roots:
  for base,ds,fs in os.walk(r,followlinks=False):
   ds[:]=[d for d in ds if Path(base,d) not in targets]
   for f in fs:
    p=Path(base,f)
    assert not p.is_symlink(),str(p)
    assert stat.S_ISREG(p.stat().st_mode),str(p)
    result[str(p)]={'bytes':p.stat().st_size,'sha256':digest(p)}
 return result
state={'synthetic':True,'started_at':datetime.now(timezone.utc).isoformat(),'targets':[str(p) for p in targets],'roots':[str(p) for p in roots],'free_before':shutil.disk_usage('/workspace').free,'retained_files':retained(),'reason':'Rebuildable extracted source and installed environments only; original positive/negative archives and all raw evidence retained','rebuild':'Extract original frozen-source.tar and original positive sdist; recreate venv and install the retained original wheel offline; see each original execution driver','no_original_jobs_or_frozen_sources_touched':True,'production_approved':False}
(output/'before.json').write_text(json.dumps(state,indent=2)+'\n')
for p in targets:shutil.rmtree(p)
after=retained();assert after==state['retained_files']
result={'finished_at':datetime.now(timezone.utc).isoformat(),'removed_rebuildable_directories':len(targets),'retained_files_byte_exact':True,'retained_file_count':len(after),'retained_archive_count':sum(p.endswith(('.tar','.gz','.whl','.zip')) for p in after),'all_positive_negative_archives_and_raw_bytes_preserved':True,'free_before':state['free_before'],'free_after':shutil.disk_usage('/workspace').free,'no_original_jobs_or_frozen_sources_touched':True,'production_approved':False}
(output/'after.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
