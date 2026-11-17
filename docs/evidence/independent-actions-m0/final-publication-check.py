"""Read-only Git/files publication check; no SQL, product imports or workloads.

Scans every newly reachable blob after public baseline909, including superseded
and deleted versions, and emits exact final diff/runtime62 fingerprints. This
bounded pattern/scope check is not a proof that arbitrary text has no secrets.
"""
from hashlib import sha256
import argparse
import json
from pathlib import Path
import re
import subprocess

SOURCE='909acecd153e2e89dfe2238e3ed3a3d9a3d3c9f0'
RUNTIME_SHA='ec0fa09e2e2e50557300423ddf6983969c9727816288ed79e9de7a17438c5b2b'
PRIVATE=re.compile(rb'-{5}BEGIN (?:RSA |EC |DSA |OPENSSH |ENCRYPTED )?PRIVATE KEY-{5}')
TOKENS=re.compile(rb'(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,}|AKIA[0-9A-Z]{16}|xox[baprs]-[A-Za-z0-9-]{20,})')
SIGNED=re.compile(rb'https?://[^\s"<>]+(?:X-Amz-Signature=|[?&]sig=|[?&]token=)[^\s"<>]+',re.I)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--candidate',required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    def git(*argv):return subprocess.check_output(['git',*argv])
    commit=git('rev-parse',args.candidate+'^{commit}').decode().strip()
    subprocess.run(['git','merge-base','--is-ancestor',SOURCE,commit],check=True)
    source_tree=git('rev-parse',SOURCE+'^{tree}').decode().strip()
    candidate_tree=git('rev-parse',commit+'^{tree}').decode().strip()
    def inventory(ref):
        records={}
        for row in git('ls-tree','-rz','--full-tree',ref).split(b'\0'):
            if row:
                header,path=row.split(b'\t',1);mode,kind,oid=header.split()
                assert kind==b'blob' and mode in (b'100644',b'100755')
                records[path.decode()]={'git_oid':oid.decode(),'mode':mode.decode()}
        return records
    source=inventory(SOURCE);current=inventory(commit)
    object_names={}
    for row in git('rev-list','--objects',SOURCE+'..'+commit).decode().splitlines():
        fields=row.split(' ',1)
        if len(fields)==2:object_names.setdefault(fields[0],[]).append(fields[1])
    assert len(object_names)<=5000
    changed_paths=git('diff','--name-only',SOURCE,commit).decode().splitlines()
    # A newly published path can reuse a blob already present in public909
    # (notably empty stderr). It still needs a current exact-diff hash, while
    # historical scanning correctly covers only genuinely newly reachable data.
    ids=set(object_names)|{current[k]['git_oid'] for k in changed_paths}|{v['git_oid'] for k,v in source.items() if k.startswith('uta/')}|{v['git_oid'] for k,v in current.items() if k.startswith('uta/')}
    hashes={};findings=[];scanned=[];total=0
    batch=subprocess.Popen(['git','cat-file','--batch'],stdin=subprocess.PIPE,stdout=subprocess.PIPE)
    try:
      for oid in sorted(ids):
        batch.stdin.write((oid+'\n').encode());batch.stdin.flush()
        actual,kind,size=batch.stdout.readline().split();size=int(size)
        assert actual.decode()==oid and size<=4*1024**2
        raw=batch.stdout.read(size);assert len(raw)==size and batch.stdout.read(1)==b'\n'
        if kind!=b'blob':continue
        total+=size;assert total<=32*1024**2
        hashes[oid]={'bytes':size,'sha256':sha256(raw).hexdigest()}
        if oid in object_names:
            paths=object_names[oid];entry=dict(git_oid=oid,paths=paths,**hashes[oid]);scanned.append(entry)
            for path in paths:
                suffix=Path(path).suffix.lower()
                if suffix in ('.db','.sqlite','.sqlite3','.zip','.whl','.gz','.prof','.cms','.der','.key') or suffix=='.pem' and path!='config/m0-stream-recipient-public.pem':
                    findings.append({'kind':'forbidden_historical_payload_path','git_oid':oid,'path':path})
            for label,pattern in [('private_key_material',PRIVATE),('credential_token_pattern',TOKENS),('signed_url_pattern',SIGNED)]:
                if pattern.search(raw):findings.append({'kind':label,'git_oid':oid,'paths':paths})
            try:raw.decode('utf-8')
            except UnicodeDecodeError:findings.append({'kind':'non_text_new_history_blob','git_oid':oid,'paths':paths})
    finally:
        batch.stdin.close();assert batch.wait(timeout=10)==0
    runtime={path:hashes[v['git_oid']]['sha256'] for path,v in source.items() if path.startswith('uta/')}
    actual_runtime={path:hashes[v['git_oid']]['sha256'] for path,v in current.items() if path.startswith('uta/')}
    assert len(source)==5518 and len(runtime)==62 and runtime==actual_runtime
    aggregate=sha256(json.dumps(runtime,sort_keys=True,separators=(',',':')).encode()).hexdigest();assert aggregate==RUNTIME_SHA
    changes=[]
    for line in git('diff','--name-status',SOURCE,commit).decode().splitlines():
        status,path=line.split('\t');assert status=='A'
        if not (path.startswith(('docs/','evidence/reviews/')) or path in {
            '.github/workflows/independent-m0.yml','.github/workflows/independent-m0-once.yml',
            'tools/independent_m0_controller.py','tools/m0_stream_escrow.py','tools/test_m0_stream_escrow_fixture.py',
            'tests/test_independent_m0_controller.py','tests/test_independent_m0_integrity.py','tests/test_independent_m0_escrow.py',
            'config/m0-stream-recipient-public.pem','config/m0-stream-recipient-public-metadata.json'}):
            findings.append({'kind':'unexpected_current_public_path','path':path})
        if Path(path).suffix.lower() in ('.db','.sqlite','.sqlite3','.zip','.whl','.gz','.prof','.cms','.der','.key'):
            findings.append({'kind':'forbidden_current_payload_extension','path':path})
        changes.append({'status':status,'path':path,**current[path],**hashes.get(current[path]['git_oid'],{})})
    # Every current change is newly reachable, therefore has been scanned above.
    assert all(v['git_oid'] in hashes for v in changes)
    assert 'config/independent-m0-approved.json' not in current
    code_paths=['tools/independent_m0_controller.py','tools/m0_stream_escrow.py','tools/test_m0_stream_escrow_fixture.py','.github/workflows/independent-m0-once.yml']
    result={'candidate_commit':commit,'candidate_tree':candidate_tree,'source_commit':SOURCE,'source_tree':source_tree,
        'source_runtime_git_tree':git('rev-parse',SOURCE+':uta').decode().strip(),'source_tracked_count':len(source),
        'runtime_file_count':62,'runtime_map_sha256':aggregate,'runtime_files':runtime,
        'runtime_unchanged':True,'code_files':{p:dict(current[p],**hashes[current[p]['git_oid']]) for p in code_paths},
        'new_commits':git('rev-list','--reverse',SOURCE+'..'+commit).decode().splitlines(),
        'scan_scope':'every newly reachable blob after existing public source909, including superseded/deleted variants; excludes preexisting public ancestor history',
        'new_history_blobs':scanned,'scanned_bytes':total,'current_exact_changes':changes,'findings':findings,
        'actual_private_key_files_or_quarantine_plaintext_read':False,'arbitrary_secret_absence_proved':False,
        'manual_scope':'synthetic pure/crypto fixtures, public cert+metadata, selected safe CI excerpt and review evidence; no DB/request/raw keybundle payload',
        'production_approved':False,'actual_M0_or_Actions_authorized':False,'passed':not findings}
    args.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'candidate':commit,'runtime62_unchanged':True,'new_history_blobs':len(scanned),'scanned_bytes':total,'changes':len(changes),'findings':len(findings)}))
    return 0 if not findings else 1

if __name__=='__main__':raise SystemExit(main())
