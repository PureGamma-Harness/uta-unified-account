"""Read-only immutable Git/docs delivery check, not a security audit or test."""
import argparse
import ast
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess

TIP = 'accce37182a1ce0384c35671f274b0c28841bc1d'
BASE = '909acecd153e2e89dfe2238e3ed3a3d9a3d3c9f0'
SOURCE = '912f2a4e5ed74f7a3fbf892ff0172e4eacc9c45a'
RUNTIME = '5750e12d60dbf7f8414b4e837e076a60c93a23bc'
ANCESTOR = '44da13d0743a3e523b229af5d116d3b1a6bc5f6c'
MAPPING = (
    ('ef60c11f733fce7a0e6296f721fdad35c9212fdf', '8fdf4c5efd4164c6e3dc932408de6035a17791ad'),
    ('db5787b21589af1d8729731ea5535006ee362fa4', 'd46e67781b914f37a0e0445dfc1ccf93d5289878'),
    ('68fa5ff1d56236ca41f93dedeea0b71a7c09ca49', '7f40d9583646b078bbb922b63efd7aec9fea1db5'))
PATTERNS = {
    'private_key_pem': rb'-----BEGIN (?:RSA |EC |OPENSSH |ENCRYPTED )?PRIVATE KEY-----',
    'github_token': rb'\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,})\b',
    'aws_access_key': rb'\b(?:AKIA|ASIA)[A-Z0-9]{16}\b',
    'signed_url': rb'https?://[^\s"<>?]+\?(?:[^\s"<>]*&)?(?:X-Amz-Signature|Signature|sig|access_token)='}
SENSITIVE = {'secret','secret_b64','private_key','private_key_pem','x-uta-nonce',
             'x-uta-signature','authorization','password','access_token','body_base64'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--repository', type=Path, required=True)
    parser.add_argument('--result', type=Path, required=True)
    args = parser.parse_args()
    def git(*parts):
        return subprocess.check_output(['git', *parts], cwd=args.repository)
    def blob(ref, name):
        return git('show', ref + ':' + name)
    def digest(raw):
        return hashlib.sha256(raw).hexdigest()
    assert git('rev-parse','HEAD').decode().strip() == TIP
    assert git('status','--porcelain') == b''
    assert subprocess.run(['git','merge-base','--is-ancestor',ANCESTOR,TIP],cwd=args.repository).returncode == 0
    runtime_paths = git('ls-tree','-r','--name-only',TIP,'--','uta').decode().splitlines()
    assert len(runtime_paths) == 64
    assert runtime_paths == git('ls-tree','-r','--name-only',SOURCE,'--','uta').decode().splitlines()
    runtime = {}
    for path in runtime_paths:
        raw = blob(TIP,path)
        assert raw == blob(SOURCE,path) == blob(RUNTIME,path)
        runtime[path] = digest(raw)
    tree = ast.parse(blob(TIP,'uta/credit_auth_h0.py'),feature_version=(3,10))
    flags = ast.literal_eval(next(n.value for n in tree.body if isinstance(n,ast.Assign)
        and any(isinstance(t,ast.Name) and t.id == '_FALSE' for t in n.targets)))
    assert flags == {'financial_authorized':False,'source_delivery_authorized':False,'execution_authorized':False}
    issuer = next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name == 'CreditHmacIngressV2')
    init = next(n for n in issuer.body if isinstance(n,ast.FunctionDef) and n.name == '__init__')
    default = {arg.arg:ast.literal_eval(value) for arg,value in zip(init.args.kwonlyargs,init.args.kw_defaults) if value is not None}
    assert default['enabled'] is False and ast.unparse(init.body[0].test) == 'enabled is not True'
    assert [ast.literal_eval(v) for v in init.body[0].body[0].exc.args] == ['credit_auth_disabled',501]
    def changed(commit):
        return [line.split('\t',1) for line in git('diff-tree','--no-commit-id','--name-status','-r',commit).decode().splitlines()]
    maps = []
    for original, picked in MAPPING:
        first, second = changed(original), changed(picked)
        assert first == second and all(status in ('A','M') for status,_ in first)
        for _,path in first:
            assert blob(original,path) == blob(picked,path)
        maps.append({'original':original,'delivery':picked,'patch_path_count':len(first),'all_introduced_blobs_equal':True})
    commits = git('rev-list','--reverse',BASE+'..'+TIP).decode().splitlines()
    versions, forbidden, deleted, sensitive = {}, [], [], []
    for commit in commits:
        for status,path in changed(commit):
            if status == 'D':
                deleted.append({'commit':commit,'path':path})
                continue
            assert status in ('A','M') and path.startswith(('docs/','tests/','uta/'))
            object_id = git('rev-parse',commit+':'+path).decode().strip()
            versions[(path,object_id)] = None
    json_count, total = 0, 0
    for path, object_id in versions:
        raw = git('cat-file','blob',object_id)
        total += len(raw)
        assert len(raw) <= 2*1024**2 and total <= 10*1024**2 and b'\0' not in raw
        versions[(path,object_id)] = digest(raw)
        if Path(path).suffix.lower() in ('.db','.sqlite','.sqlite3','.pem','.key','.p12','.pfx') or path.endswith(('-wal','-shm')):
            forbidden.append({'path':path,'category':'prohibited_artifact_path'})
        if re.fullmatch(r'private-(?:profile|request-\d+)\.json',Path(path).name) or Path(path).suffix.lower() in ('.stdout','.stderr'):
            forbidden.append({'path':path,'category':'private_raw_artifact_path'})
        for category, pattern in PATTERNS.items():
            if re.search(pattern,raw):
                forbidden.append({'path':path,'category':category})
        if path.endswith('.json'):
            json_count += 1
            def walk(value):
                if isinstance(value,dict):
                    for key,item in value.items():
                        if key.lower() in SENSITIVE and isinstance(item,str):
                            sensitive.append({'path':path,'field':key,'string_bytes':len(item.encode())})
                        walk(item)
                elif isinstance(value,list):
                    for item in value:walk(item)
            walk(json.loads(raw))
    note = blob(TIP,'docs/credit-auth-h0-draft-delivery.md').decode()
    assert all(text in note for text in ('recording remains incomplete','PR22 foundation recovery error',
        'separate reliability','new private format2 store','old reader is not authorized to rewrite',
        'Retain the private AuthDB','not full H0/H1'))
    manifest = [{'path':path,'blob':oid,'sha256':value} for (path,oid),value in sorted(versions.items())]
    result = {'decision':'ALLOW_AUTH_ONLY_DEFAULT_OFF_DRAFT_SCOPE_ONLY' if not (forbidden or sensitive or deleted) else 'REVIEW_BLOCKED',
        'reviewed_head':TIP,'head_parent':git('rev-parse',TIP+'^').decode().strip(),'ancestor_P2':ANCESTOR,
        'qualified_inner_source':SOURCE,'runtime_source':RUNTIME,'runtime_file_count':64,
        'all_runtime_blobs_equal_source912_and5750':True,'runtime_manifest_sha256':digest(json.dumps(runtime,sort_keys=True).encode()),
        'default_enabled':False,'disabled_constructor_status':501,'literal_authorization_flags':flags,
        'cherry_patch_mapping':maps,'history_commits_checked':len(commits),'unique_public_path_blob_versions':len(versions),
        'public_bytes_read':total,'json_versions_checked':json_count,'deleted_paths':deleted,
        'defined_artifact_or_pattern_flags':forbidden,'defined_sensitive_JSON_string_fields':sensitive,
        'public_manifest_sha256':digest(json.dumps(manifest,sort_keys=True).encode()),
        'full3_outer_gate':'RECORDING_INCOMPLETE_UNCHANGED','PR22_foundation_gate':'RECOVERY_BLOCKER_NO_GO_UNCHANGED',
        'fresh_auth_format2_only_no_inplace_upgrade':True,'rollback_retain_audit_no_oldreader_rewrite':True,
        'H1_or_recovery_fix_mixed_into_runtime':False,'unmaterialized_runtime_read_via_Git_only':True,
        'defined_pattern_check_not_security_audit':True,'arbitrary_encoded_secret_absence_certified':False,
        'SQL_or_product_import_or_dynamic_test_or_private_data_read':False,'push_PR_merge_or_financial_enablement':False,
        'production_approved':False,'recorded_at':datetime.now(timezone.utc).isoformat(),
        'checker_sha256':digest(Path(__file__).read_bytes())}
    assert not args.result.exists()
    args.result.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
