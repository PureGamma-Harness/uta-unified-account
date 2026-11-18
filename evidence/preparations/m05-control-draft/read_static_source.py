"""Git/text-only proof of two literal public MANIFEST selectors; no build/import."""
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT=Path(__file__).resolve().parents[3]
SOURCE='9cd87f7d0fbacdfd87a58dbef6ca24713dc3fe95'
CONTROL='933c86803020fccbc11949795cb9c75a2262959d'
BASE='6010e920a168b35fccfc9ef9ee34e030b28b11d9'
PATHS=[
    'evidence/independent-m0-entry-type-provenance/pure-once01/inputs.sha256',
    'evidence/independent-m0-scan-proof/pure-once01/inputs.sha256',
]
def git(*args):return subprocess.check_output(['git',*args],cwd=ROOT)
def sha(raw):return hashlib.sha256(raw).hexdigest()
def main():
    assert git('diff','--name-only',SOURCE+'^',SOURCE).decode().splitlines()==['MANIFEST.in']
    old=git('show',SOURCE+'^:MANIFEST.in');new=git('show',SOURCE+':MANIFEST.in')
    insertion=b''.join(('include '+path+'\n').encode() for path in PATHS)
    assert new==old.replace(b'include config/m0-stream-recipient-public.pem\n',b'include config/m0-stream-recipient-public.pem\n'+insertion,1)
    assets=[]
    for path in PATHS:
        raw=git('show',SOURCE+':'+path)
        assert raw==git('show',CONTROL+':'+path)
        assert all(re.fullmatch(r'[0-9a-f]{64}  (tools|tests)/[A-Za-z0-9_]+\.py',line) for line in raw.decode().splitlines())
        assert new.splitlines().count(('include '+path).encode())==1
        assets.append(dict(path=path,blob_oid=git('rev-parse',SOURCE+':'+path).decode().strip(),
            bytes=len(raw),sha256=sha(raw),selector='include '+path,historical_provenance_bytes_unchanged=True))
    assert git('diff',BASE,SOURCE,'--','uta')==b''
    assert git('diff',CONTROL,SOURCE,'--','tools','tests','.github/workflows','config','uta')==b''
    assert git('ls-tree',SOURCE,'config/independent-m0-approved.json')==b''
    assert git('log','--format=','--name-status','909acecd153e2e89dfe2238e3ed3a3d9a3d3c9f0..'+SOURCE,'--','config/independent-m0-approved.json').strip()==b''
    for actual in ['cad6e2b8e5efbb13da66376f69ce9dca39e522ba','e643661dbafdff76e66c50d20eecc2fdef4bf9e1']:
        assert subprocess.run(['git','merge-base','--is-ancestor',actual,SOURCE],cwd=ROOT,stdout=subprocess.DEVNULL).returncode==1
    result=dict(kind='STATIC_EXACT_PUBLIC_MANIFEST_SELECTION_ONLY',SOURCE=SOURCE,
        source_tree=git('rev-parse',SOURCE+'^{tree}').decode().strip(),
        MANIFEST_blob_oid=git('rev-parse',SOURCE+':MANIFEST.in').decode().strip(),
        MANIFEST_sha256=sha(new),selected_exact_public_blobs=assets,
        original_first_CI_run=44217339023,original_first_CI_head='cad6e2b8e5efbb13da66376f69ce9dca39e522ba',
        original_first_package_failure_preserved=True,original_four_runtime_unit_tests_each=2049,
        original_four_runtime_installed_validation='SKIPPED_AFTER_PACKAGE_FAILURE',
        new_source_package_or_installed_validation='NOT_RUN',
        source_uta_tree=git('rev-parse',SOURCE+':uta').decode().strip(),runtime_zero_diff_to6010=True,
        actual_marker_path_or_true_M_ancestor_absent=True,controller_helper_tests_workflows_config_unchanged_from_safe_C=True,
        historical_input_hash_lines_not_rewritten_as_current_controller_attestation=True,
        SQL_native_service_crypto_or_workload_executed=False,new_CI_or_push_or_PR_created=False,
        registration05_spent=True,next_run_permitted=False)
    print(json.dumps(result,sort_keys=True))
if __name__=='__main__':main()
