"""Bounded new D1 publication diff scan; does not rescan old public history."""
from hashlib import sha256
import json
from pathlib import Path
import re
import stat
import subprocess

ROOT=Path(__file__).resolve().parents[3];OUT=Path(__file__).with_name('d1-scope-scan-second.json')
rows=subprocess.check_output(['git','status','--porcelain','--untracked-files=all'],cwd=ROOT).decode().splitlines()
records=[];findings=[];total=0
excluded={str(p.relative_to(ROOT)) for p in (OUT,OUT.with_suffix('.stdout.txt'),OUT.with_suffix('.stderr.txt'))}
for row in rows:
    status,path=row[:2],row[3:]
    if path in excluded:continue
    allowed=path in {'tools/independent_m0_controller.py','.github/workflows/independent-m0.yml',
        '.github/workflows/independent-m0-once.yml','tests/test_independent_m0_diagnostics.py',
        'docs/independent-actions-m0-d1-diagnostic-contract.md'} or path.startswith('docs/evidence/independent-actions-m0/d1-')
    if not allowed:findings.append({'kind':'unexpected_path','path':path})
    entry=ROOT/path;info=entry.lstat();assert stat.S_ISREG(info.st_mode) and info.st_size<=128*1024
    raw=entry.read_bytes();raw.decode('utf8');total+=len(raw)
    if re.search(rb'-{5}BEGIN (?:RSA |EC |DSA |OPENSSH |ENCRYPTED )?PRIVATE KEY-{5}',raw):findings.append({'kind':'private_key_pattern','path':path})
    if re.search(rb'(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,}|AKIA[0-9A-Z]{16})',raw):findings.append({'kind':'credential_pattern','path':path})
    if re.search(rb'https?://[^\s"<>]+(?:X-Amz-Signature=|[?&]sig=|[?&]token=)[^\s"<>]+',raw,re.I):findings.append({'kind':'signed_url_pattern','path':path})
    if entry.suffix not in {'.py','.json','.txt','.patch','.md','.yml'}:findings.append({'kind':'unexpected_extension','path':path})
    records.append({'status':status,'path':path,'bytes':len(raw),'sha256':sha256(raw).hexdigest()})
assert len(records)<=40 and total<=512*1024
assert subprocess.run(['git','diff','--quiet','909acecd153e2e89dfe2238e3ed3a3d9a3d3c9f0','HEAD','--','uta'],cwd=ROOT).returncode==0
value=dict(kind='D1_NEW_DIFF_SCOPE_SCAN',version=1,git_base='ab933bec61d5c4be3e40c1a337f8ce55705ba48d',
    scope='Only currently modified/untracked D1 text files; superseded history previously retained, not rescanned by this helper.',
    records=records,currently_written_outputs_excluded=sorted(excluded),scanned_bytes=total,findings=findings,passed=not findings,
    sensitive_material_absence_proved=False,actual_private_key_or_quarantine_read=False,
    runtime_source_git_unchanged=True,production_approved=False)
with OUT.open('x') as f:json.dump(value,f,indent=2,sort_keys=True);f.write('\n')
print(json.dumps({'files':len(records),'bytes':total,'findings':len(findings),'passed':not findings},sort_keys=True))
raise SystemExit(0 if not findings else 1)
