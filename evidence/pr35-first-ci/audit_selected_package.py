"""Read one downloaded package pair and its reports; never build/install/import uta."""
import ast
import configparser
from email.parser import BytesParser
from email.policy import compat32
from hashlib import sha1, sha256
import io
import json
import os
from pathlib import Path, PurePosixPath
import stat
import subprocess
import tarfile
import tomllib
import zipfile

ROOT=Path(__file__).resolve().parents[2]
PRIVATE=Path('/workspace/uta-pr35-first-ci-private')
SOURCE='f6ef89b213ac76813ad31687aa4ff825d9d72585'
OUT=Path(__file__).parent
def digest(raw):return sha256(raw).hexdigest()
def new_json(path,value):
    with path.open('x') as f:json.dump(value,f,sort_keys=True,indent=2);f.write('\n')
def safe_zip(path):
    z=zipfile.ZipFile(path);infos=z.infolist()
    assert len(infos)==len({i.filename for i in infos}) and len(infos)<20000
    assert all(not PurePosixPath(i.filename).is_absolute() and '..' not in PurePosixPath(i.filename).parts and not stat.S_ISLNK(i.external_attr>>16) for i in infos)
    assert z.testzip() is None
    return z
def main():
    os.umask(0o077)
    def git(*args):return subprocess.check_output(['git',*args],cwd=ROOT)
    records=git('ls-tree','-rz','--full-tree',SOURCE)
    tracked={}
    for row in records.split(b'\0'):
        if row:
            header,path=row.split(b'\t',1);mode,kind,oid=header.split()
            assert kind==b'blob' and mode in {b'100644',b'100755'}
            tracked[path.decode()]=oid.decode()
    project=tomllib.loads(git('show',SOURCE+':pyproject.toml').decode())
    init=ast.parse(git('show',SOURCE+':uta/__init__.py'))
    versions=[ast.literal_eval(n.value) for n in init.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='__version__' for t in n.targets)]
    assert versions==[project['project']['version']];version=versions[0]
    runtime_paths={p for p in tracked if p.startswith('uta/') and p.endswith(('.py','.html'))}
    # No Python source from the archives is executed. Git calls above are
    # read-only metadata; every operation below is a ZIP/TAR/JSON/AST read.
    public=OUT/'selected-push312-validation';public.mkdir(mode=0o700)
    with safe_zip(PRIVATE/'push312-package-validation.zip') as z:
        for i in z.infolist():
            path=public/i.filename;path.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
            with path.open('xb') as f:f.write(z.read(i))
    report=json.loads((public/'uta-package-artifact-manifest.json').read_bytes())
    installed=json.loads((public/'uta-installed-validation/installed-report.json').read_bytes())
    outer_members=[];archive_paths=[]
    with safe_zip(PRIVATE/'push312-review-package.zip') as z:
        assert len(z.infolist())==2
        for i in z.infolist():
            assert '/' not in i.filename and i.filename.endswith(('.whl','.tar.gz'))
            raw=z.read(i);expected=report['artifacts'][i.filename]
            assert len(raw)==expected['bytes'] and digest(raw)==expected['sha256']
            path=PRIVATE/i.filename
            with path.open('xb') as f:f.write(raw)
            archive_paths.append(path);outer_members.append(dict(name=i.filename,bytes=len(raw),sha256=digest(raw),CRC32=i.CRC))
    wheel=next(p for p in archive_paths if p.name.endswith('.whl'))
    sdist=next(p for p in archive_paths if p.name.endswith('.tar.gz'))
    wheel_runtime={};wheel_git_mismatch=[]
    with safe_zip(wheel) as z:
        names=z.namelist();metadata_names=[n for n in names if n.endswith('.dist-info/METADATA')];assert len(metadata_names)==1
        metadata=BytesParser(policy=compat32).parsebytes(z.read(metadata_names[0]),headersonly=True)
        metadata_versions=metadata.get_all('Version',[])
        entries=z.read(metadata_names[0].removesuffix('METADATA')+'entry_points.txt').decode()
        for name in names:
            if name.startswith('uta/') and name.endswith(('.py','.html')):
                raw=z.read(name);wheel_runtime[name]=digest(raw)
                if name not in tracked or sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()!=tracked[name]:wheel_git_mismatch.append(name)
    parsed=configparser.ConfigParser(interpolation=None);parsed.read_string(entries)
    expected_entries={'uta':'uta.__main__:main','uta-ops':'uta.ops:main','uta-durable':'uta.durable_cli:main'}
    seen=set();members={};source_runtime={};mismatched=[];special={};total=0;prefix=None
    capture={'tests/fixtures/legacy_ad3f5b8_uta.tar.gz','tests/fixtures/legacy_ad3f5b8_provenance.json',
             'evidence/independent-m0-entry-type-provenance/pure-once01/inputs.sha256',
             'evidence/independent-m0-scan-proof/pure-once01/inputs.sha256'}
    with tarfile.open(sdist,mode='r|gz') as archive:
        for item in archive:
            name=PurePosixPath(item.name)
            assert not name.is_absolute() and '..' not in name.parts and (item.isdir() or item.isfile()) and item.name not in seen
            seen.add(item.name)
            if prefix is None:prefix=item.name.split('/')[0]+'/'
            assert item.name==prefix.rstrip('/') or item.name.startswith(prefix)
            if item.isdir():continue
            relative=item.name.removeprefix(prefix);total+=item.size;assert total<=536870912
            body=archive.extractfile(item);h1=sha1(b'blob '+str(item.size).encode()+b'\0');h256=sha256();parts=[]
            while True:
                chunk=body.read(1048576)
                if not chunk:break
                h1.update(chunk);h256.update(chunk)
                if relative in capture:parts.append(chunk)
            members[relative]={'bytes':item.size,'sha256':h256.hexdigest()}
            if relative in tracked and h1.hexdigest()!=tracked[relative]:mismatched.append(relative)
            if relative.startswith('uta/') and relative.endswith(('.py','.html')):source_runtime[relative]=h256.hexdigest()
            if relative in capture:special[relative]=b''.join(parts)
    missing=sorted(set(tracked)-members.keys());fixture=special['tests/fixtures/legacy_ad3f5b8_uta.tar.gz']
    provenance=json.loads(special['tests/fixtures/legacy_ad3f5b8_provenance.json'])
    with tarfile.open(fileobj=io.BytesIO(fixture),mode='r:gz') as legacy:licensed='LICENSE' in legacy.getnames()
    checks=dict(version=len(metadata_versions)==1 and metadata_versions[0]==version,
        wheel_runtime_exact=set(wheel_runtime)==runtime_paths and not wheel_git_mismatch,
        sdist_runtime_exact=set(source_runtime)==runtime_paths and source_runtime==wheel_runtime,
        sdist_required_files_exact=not missing and not mismatched,
        legacy_fixture_pinned=digest(fixture)==provenance['archive_sha256'],legacy_fixture_licensed=licensed,
        entry_points=dict(parsed['console_scripts'])==expected_entries)
    assert all(checks.values()) and checks==report['checks'] and report['passed'] is True and report['source_commit']==SOURCE
    runtime_hash=digest(json.dumps(wheel_runtime,sort_keys=True,separators=(',',':')).encode())
    assert wheel_runtime==report['runtime_files'] and runtime_hash==report['runtime_tree_sha256']
    assert installed['source_commit']==SOURCE and installed['runtime_tree_sha256']==runtime_hash
    assert installed['passed'] is True and installed['isolated'] is True and installed['pythonpath'] is None
    assert installed['expected_tests']==8 and installed['tests']=={'run':8,'failures':0,'errors':0,'skipped':0}
    assert all(c['returncode']==0 for c in installed['commands'])
    record=dict(kind='FIRST_SELECTED_PUSH312_PURE_ARCHIVE_AUDIT',source_commit=SOURCE,
        source_tree='3066c5be3352fb73c8382aedfa153440bfc30cb8',selection_scope='one push Python3.12 review ZIP plus its validation companion, downloaded once each',
        review_artifact_id=14390317989,validation_artifact_id=14390168340,
        outer_ZIP_digest_CRC_and_nested_artifact_SHA_verified=True,archive_members=outer_members,
        independent_seven_checks=checks,provider_report_seven_checks=report['checks'],
        required_Git_blob_paths=len(tracked),sdist_file_members=len(members),sdist_uncompressed_bytes_read=total,
        source_Git_NUL_tree_records_sha256=digest(records),sdist_missing=missing,sdist_Git_blob_mismatches=mismatched,
        runtime_files=len(runtime_paths),runtime_tree_sha256=runtime_hash,
        exact_two_input_manifest_members={p:members[p] for p in sorted(capture) if p.endswith('inputs.sha256')},
        version=version,installed_tests=installed['tests'],installed_isolated=True,installed_PYTHONPATH=None,
        all_recorded_installed_command_exits_zero=True,installed_report_passed=True,
        local_build_install_SQL_native_or_uta_import_executed=False,old_M05_and_general_CI_first_results_unchanged=True,
        registration05_spent=True,production_approved=False,capacity_approved=False,HA_approved=False,next_run_permitted=False)
    new_json(OUT/'selected-package-audit.json',record)
    print(json.dumps({k:record[k] for k in ['source_commit','independent_seven_checks','required_Git_blob_paths','sdist_uncompressed_bytes_read','installed_tests','local_build_install_SQL_native_or_uta_import_executed']},sort_keys=True))
if __name__=='__main__':main()
