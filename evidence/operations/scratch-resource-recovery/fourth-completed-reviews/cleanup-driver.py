from pathlib import Path
from hashlib import sha256
from datetime import datetime,timezone
import json,os,shutil,subprocess,tarfile,stat
os.sched_setaffinity(0,{3})
repo=Path('/workspace/uta-observer-delivery');plan=json.loads(Path('/workspace/uta-scratch-review-20261117.json').read_bytes())
output=Path('/workspace/uta-safe-scratch-cleanup/fourth-completed-reviews');output.mkdir(exist_ok=False)
def git(*args,cwd=repo):return subprocess.check_output(['git',*args],cwd=cwd,text=True).strip()
def digest(path):
 h=sha256()
 with Path(path).open('rb') as stream:
  for data in iter(lambda:stream.read(1024*1024),b''):h.update(data)
 return h.hexdigest()
def used(paths):
 found=[]
 for proc in Path('/proc').iterdir():
  if not proc.name.isdigit():continue
  for link in [proc/'cwd',proc/'exe']:
   try:value=os.readlink(link)
   except OSError:continue
   if any(value==str(p) or value.startswith(str(p)+'/') for p in paths):found.append((proc.name,str(link),value))
 return found
rows=plan['review_candidates'];targets=[Path(r['absolute_path']) for r in rows]
assert len(targets)==31 and len(set(targets))==31
protected=[Path(p) for p in plan['required_keep_paths']]+[Path('/workspace/uta-ledger-main-schema-gap'),Path('/workspace/uta-ledger-main-fix-acceptance'),Path('/workspace/uta-credit-internal-v2'),repo]
for r,p in zip(rows,targets):
 assert p.is_dir() and not p.is_symlink() and p not in protected
 assert not any(x in str(p) for x in ('freeze','soak-runs','observer-runs'))
 assert git('rev-parse','HEAD',cwd=p)==r['HEAD']==git('rev-parse',r['branch_ref'])
 assert git('rev-parse','HEAD^{tree}',cwd=p)==r['tree']
 assert git('status','--porcelain','--untracked-files=all',cwd=p)==''
 ignored=git('ls-files','--others','--ignored','--exclude-standard',cwd=p).splitlines()
 assert all('__pycache__/' in name or name.endswith('.pyc') for name in ignored),str(p)
assert used(targets)==[]
runtime=plan['conditional_runtime_candidate'];prefix=Path(runtime['absolute_path']);archive=Path(runtime['retained_archive'])
assert prefix==Path('/tmp/uta-python31318-24-20261117/runtime') and prefix.is_dir() and not prefix.is_symlink()
assert digest(archive)==runtime['archive_sha256'] and archive.stat().st_size==runtime['archive_bytes']
assert used([prefix])==[]
member_files=links=0
with tarfile.open(archive,'r:gz') as tar:
 for member in tar:
  relative=Path(member.name)
  assert not relative.is_absolute() and '..' not in relative.parts
  actual=prefix/relative
  if member.isfile():
   stream=tar.extractfile(member);h=sha256()
   for data in iter(lambda:stream.read(1024*1024),b''):h.update(data)
   assert actual.is_file() and not actual.is_symlink() and actual.stat().st_size==member.size and digest(actual)==h.hexdigest(),member.name
   member_files+=1
  elif member.issym():assert actual.is_symlink() and os.readlink(actual)==member.linkname;links+=1
  else:assert member.isdir()
before={'started_at':datetime.now(timezone.utc).isoformat(),'free_before':shutil.disk_usage('/workspace').free,'worktrees':rows,'runtime':runtime,'runtime_regular_files_exact':member_files,'runtime_links_exact':links,'owner_confirmation':'root: all31 completed review trees and B runtime diagnosis done; live sources, jobs and original archives retained; current agents use separate protected trees','no_original_archive_raw_database_or_job_deleted':True,'production_approved':False}
(output/'before.json').write_text(json.dumps(before,indent=2)+'\n')
for r,p in zip(rows,targets):
 assert used([p])==[]
 assert git('status','--porcelain','--untracked-files=all',cwd=p)==''
 subprocess.run(['git','worktree','remove','--force',str(p)],cwd=repo,check=True,stdout=subprocess.DEVNULL)
 assert git('rev-parse',r['branch_ref'])==r['HEAD']
 assert git('rev-parse',r['HEAD']+'^{tree}')==r['tree']
shutil.rmtree(prefix)
assert digest(archive)==runtime['archive_sha256']
after={'finished_at':datetime.now(timezone.utc).isoformat(),'removed_completed_clean_worktrees':len(rows),'all31_named_refs_and_exact_trees_preserved':True,'removed_derived_runtime_prefix':str(prefix),'retained_runtime_archive_sha256':digest(archive),'retained_runtime_archive_byte_exact':True,'free_before':before['free_before'],'free_after':shutil.disk_usage('/workspace').free,'no_job_frozen_source_original_archives_raw_database_auth_or_tls_touched':True,'production_approved':False}
(output/'after.json').write_text(json.dumps(after,indent=2)+'\n');print(json.dumps(after))
