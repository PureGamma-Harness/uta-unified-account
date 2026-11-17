"""Read only public-candidate Git blobs, never private files or product imports.

This is a publication/privacy and scope check, not a security vulnerability scan.
Pattern-free output cannot certify absence of arbitrary encoded sensitive data.
"""
import argparse
import ast
from datetime import datetime,timezone
from hashlib import sha256
import json
from pathlib import Path
import re
import subprocess
import time

BASE='909acecd153e2e89dfe2238e3ed3a3d9a3d3c9f0'
TIP='912f2a4e5ed74f7a3fbf892ff0172e4eacc9c45a'
PATTERNS={
 'private_key_pem':rb'-----BEGIN (?:RSA |EC |OPENSSH |ENCRYPTED )?PRIVATE KEY-----',
 'github_token':rb'\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,})\b',
 'aws_access_key':rb'\b(?:AKIA|ASIA)[A-Z0-9]{16}\b',
 'signed_url':rb'https?://[^\s"<>?]+\?(?:[^\s"<>]*&)?(?:X-Amz-Signature|Signature|sig|access_token)=',
}
SENSITIVE_KEYS={'secret','secret_b64','private_key','private_key_pem','x-uta-nonce',
                'x-uta-signature','authorization','password','access_token','body_base64'}


def main():
    p=argparse.ArgumentParser();p.add_argument('--repository',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    assert a.repository.is_absolute() and a.output.is_absolute() and not a.output.exists()
    def git(*parts):return subprocess.check_output(['git',*parts],cwd=a.repository)
    started=datetime.now(timezone.utc).isoformat();mono=time.monotonic_ns()
    commits=git('rev-list','--reverse',BASE+'..'+TIP).decode().splitlines()
    assert len(commits)==13
    versions={};path_commits={};deleted=[]
    for commit in commits:
        for line in git('diff-tree','--no-commit-id','--name-status','-r',commit).decode().splitlines():
            status,path=line.split('\t',1)
            if status=='D':deleted.append({'commit':commit,'path':path});continue
            assert status in ('A','M')
            assert not path.startswith('/') and '..' not in Path(path).parts
            assert path.startswith(('docs/','tests/','uta/'))
            raw=git('rev-parse',commit+':'+path).decode().strip()
            versions[(path,raw)]={'path':path,'git_blob':raw,'first_commit_in_scope':commit}
            path_commits.setdefault(path,[]).append(commit)
    flags=[];sensitive=[];total=0;json_count=0;records=[]
    for (path,blob),record in sorted(versions.items()):
        content=git('cat-file','blob',blob);total+=len(content)
        assert len(content)<=2*1024**2 and total<=10*1024**2
        record.update(bytes=len(content),sha256=sha256(content).hexdigest())
        assert b'\0' not in content
        if Path(path).suffix.lower() in ('.db','.sqlite','.sqlite3','.pem','.key','.p12','.pfx') or path.endswith(('-wal','-shm')):
            flags.append({'path':path,'blob':blob,'category':'prohibited_artifact_path'})
        for category,pattern in PATTERNS.items():
            for match in re.finditer(pattern,content):
                flags.append({'path':path,'blob':blob,'category':category,'line':content[:match.start()].count(b'\n')+1})
        if path.endswith('.json'):
            document=json.loads(content);json_count+=1
            def walk(value,where=''):
                if isinstance(value,dict):
                    for key,item in value.items():
                        loc=where+'/'+key
                        if key.lower() in SENSITIVE_KEYS and isinstance(item,str):
                            sensitive.append({'path':path,'blob':blob,'field':loc,'value_bytes':len(item.encode()),
                                              'value_sha256':sha256(item.encode()).hexdigest()})
                        walk(item,loc)
                elif isinstance(value,list):
                    for index,item in enumerate(value):walk(item,where+'/'+str(index))
            walk(document)
        records.append(record)
    changed=git('diff','--name-only',BASE,TIP).decode().splitlines()
    assert len(changed)==97
    runtime=[name for name in changed if name.startswith('uta/')]
    assert runtime==['uta/credit_auth_h0.py','uta/credit_auth_h0_schema.py','uta/request_signing.py']
    parsed=ast.parse(git('show',TIP+':uta/credit_auth_h0.py'))
    false_dict=next(node.value for node in parsed.body if isinstance(node,ast.Assign)
                    and any(isinstance(t,ast.Name) and t.id=='_FALSE' for t in node.targets))
    false_flags=ast.literal_eval(false_dict)
    assert false_flags=={'financial_authorized':False,'source_delivery_authorized':False,'execution_authorized':False}
    issuer=next(node for node in parsed.body if isinstance(node,ast.ClassDef) and node.name=='CreditHmacIngressV2')
    init=next(node for node in issuer.body if isinstance(node,ast.FunctionDef) and node.name=='__init__')
    defaults={arg.arg:ast.literal_eval(value) for arg,value in zip(init.args.kwonlyargs,init.args.kw_defaults) if value is not None}
    assert defaults['enabled'] is False
    condition=init.body[0];assert isinstance(condition,ast.If)
    assert ast.unparse(condition.test)=='enabled is not True'
    assert isinstance(condition.body[0],ast.Raise)
    assert ast.literal_eval(condition.body[0].exc.args[0])=='credit_auth_disabled'
    assert ast.literal_eval(condition.body[0].exc.args[1])==501
    unchanged={}
    for path in ('uta/durable_gateway.py','uta/durable_cli.py','uta/credit.py','uta/credit_policy.py',
                 'uta/credit_native_v2.py','uta/writer_fence.py','uta/api.py','uta/server.py','uta/service.py'):
        before=git('show',BASE+':'+path);after=git('show',TIP+':'+path);assert before==after
        unchanged[path]=sha256(after).hexdigest()
    public_borrow=git('show',TIP+':uta/credit.py')
    assert b'managed new borrowing requires a supported credit decision capability' in public_borrow
    assert b'managed new borrowing requires its durable credit dispatcher' in public_borrow
    report={'kind':'SCOPED_H0_GIT_PUBLICATION_PRECHECK_NOT_SECURITY_AUDIT','base_commit':BASE,'tip_commit':TIP,
       'started_at':started,'finished_at':datetime.now(timezone.utc).isoformat(),
       'elapsed_ns_before_report_write':time.monotonic_ns()-mono,'history_commits':commits,
       'tip_changed_paths':changed,'history_path_count':len(path_commits),'unique_path_blob_versions':len(records),
       'total_git_blob_bytes_read':total,'json_blob_versions_parsed':json_count,'deleted_paths':deleted,
       'pattern_or_prohibited_artifact_flags':flags,'json_sensitive_string_fields_requiring_review':sensitive,
       'actual_default_enabled':False,'literal_observation_flags':false_flags,
       'runtime_changes':runtime,'unchanged_ingress_finance_paths_sha256':unchanged,
       'history_blob_manifest':records,'checker_sha256':sha256(Path(__file__).read_bytes()).hexdigest(),
       'actual_private_keys_databases_requests_read':False,'product_imported_or_sql_or_tests_run':False,
       'full_repository_or_security_audit':False,'push_or_pr_or_merge_performed':False,'production_approved':False}
    with a.output.open('x') as out:json.dump(report,out,indent=2,sort_keys=True);out.write('\n')
    print(json.dumps({key:report[key] for key in ('base_commit','tip_commit','history_path_count',
       'unique_path_blob_versions','total_git_blob_bytes_read','json_blob_versions_parsed',
       'pattern_or_prohibited_artifact_flags','json_sensitive_string_fields_requiring_review',
       'actual_default_enabled','literal_observation_flags')}))


if __name__=='__main__':main()
