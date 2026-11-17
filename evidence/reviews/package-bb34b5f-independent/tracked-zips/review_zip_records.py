"""Independent bounded read-only ZIP/JSON provenance review; no SQL/service/test."""
import hashlib, io, json, os, signal, subprocess, tarfile, time, zipfile
from pathlib import Path
os.sched_setaffinity(0,{2})
signal.alarm(10)
t0=time.monotonic()
SOURCE=Path('/workspace/uta-observer-freeze-bb34b5f')
WORK=Path('/tmp/uta-release-bb34b5f-09yvddlh')
OUT=Path('/workspace/uta-bb34-zip-review-output')
COMMIT='bb34b5fb4397f485c04fe440557b24bb28d1cae2'
sha=lambda b: hashlib.sha256(b).hexdigest()
read=lambda p: json.loads(p.read_bytes())
provpath=Path('/workspace/uta-package-bb34b5f/ci-zip-provenance.json')
prov=read(provpath)
indexpath=WORK/'tracked-ci-zip-checks/tracked-ci-zips.json';index=read(indexpath)
manifestpath=WORK/'artifact-manifest.json'
if not manifestpath.exists():
    matches=list(WORK.rglob('artifact-manifest.json'));assert len(matches)==1;manifestpath=matches[0]
manifest=read(manifestpath)
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=SOURCE,text=True).strip()==COMMIT
assert index['source_commit']==manifest['source_commit']==COMMIT
assert index['passed'] is True and index['historical_results_preserved'] is True
assert index['historical_ci_is_current_release_qualification'] is False if 'historical_ci_is_current_release_qualification' in index else True
assert index['positive_artifacts_unchanged'] is True and index['negative_artifacts_installed'] is False
assert index['provenance_sha256']==sha(provpath.read_bytes())
tracked=subprocess.check_output(['git','ls-tree','-r','--name-only',COMMIT],cwd=SOURCE,text=True).splitlines()
zipnames={name for name in tracked if name.endswith('.zip')}
assert zipnames==set(prov)=={x['tracked_path'] for x in index['inclusions']}=={x['removed_member'] for x in index['omission_controls']}
assert len(zipnames)==6
included={x['tracked_path']:x for x in index['inclusions']}
controls={x['removed_member']:x for x in index['omission_controls']}
artifacts=manifest['artifacts']
wheelname=next(name for name in artifacts if name.endswith('.whl'))
sdistname=next(name for name in artifacts if name.endswith('.tar.gz'))
wheel=WORK/'artifacts'/wheelname;sdist=WORK/'artifacts'/sdistname
assert sha(wheel.read_bytes())==artifacts[wheelname]['sha256']
assert sha(sdist.read_bytes())==artifacts[sdistname]['sha256']
current_zip_bytes={}
with tarfile.open(sdist,'r:gz') as archive:
    members=archive.getmembers();prefix=members[0].name.split('/')[0]+'/'
    for item in members:
        rel=item.name.removeprefix(prefix)
        if rel in zipnames:
            assert item.isfile()
            current_zip_bytes[rel]=archive.extractfile(item).read()
assert set(current_zip_bytes)==zipnames
records=[];historical_maps={}
for name in sorted(zipnames):
    blob=(SOURCE/name).read_bytes();inc=included[name];ref=prov[name];control=controls[name]
    assert sha(blob)==ref['sha256']==inc['sha256']
    assert blob==current_zip_bytes[name]
    assert len(blob)==inc['bytes']
    assert inc['historical_ci_is_current_release_qualification'] is False
    with zipfile.ZipFile(io.BytesIO(blob)) as archive:
        infos=archive.infolist();assert {m.filename for m in infos}=={'summary.json','worker-result.json','unittest.txt'} and len(infos)==3
        actual_members=[]
        byname={x['name']:x for x in inc['members']}
        for item in infos:
            content=archive.read(item)
            assert len(content)==byname[item.filename]['bytes'] and sha(content)==byname[item.filename]['sha256']
            actual_members.append({'name':item.filename,'bytes':len(content),'sha256':sha(content)})
        summary=json.loads(archive.read('summary.json'))
        worker=json.loads(archive.read('worker-result.json'))
    assert summary['code_commit']==ref['recorded_code_commit']==inc['historical_ci']['code_commit']
    assert summary['source_sha256']==summary['source_sha256_after']
    assert summary['passed'] is False and worker['unittest_passed'] is False
    assert summary['tests_run']==worker['tests_run']==inc['historical_ci']['tests_run']
    assert summary['failures']==worker['failures']==inc['historical_ci']['failures']
    assert summary['errors']==worker['errors']==inc['historical_ci']['errors']
    commit=ref['reference_commit'];source_map=summary['source_sha256']
    if commit not in historical_maps:
        # One bounded git object batch per historical commit; no checkout or code execution.
        requests=''.join(commit+':'+path+'\n' for path in source_map).encode()
        output=subprocess.check_output(['git','cat-file','--batch'],input=requests,cwd=SOURCE)
        offset=0;result={}
        for path in source_map:
            end=output.index(b'\n',offset);header=output[offset:end].split();assert header[1]==b'blob'
            size=int(header[2]);start=end+1;content=output[start:start+size]
            assert output[start+size:start+size+1]==b'\n'
            result[path]=sha(content);offset=start+size+1
        assert offset==len(output);historical_maps[commit]=result
    assert source_map==historical_maps[commit]
    assert control['removed_count']==1 and control['returncode']==1 and control['passed'] is True
    assert control['sdist_missing']==[name]
    expected={key: key!='sdist_required_files_exact' for key in manifest['checks']}
    assert control['checks']==expected
    args=control['argv'];arg=lambda option:Path(args[args.index(option)+1])
    assert args[args.index('--commit')+1]==COMMIT and arg('--source')==SOURCE
    assert arg('--wheel')==wheel
    report_path=arg('--output');report=read(report_path)
    negative=arg('--sdist')
    assert sha(negative.read_bytes())==control['negative_archive_sha256']
    assert report['source_commit']==COMMIT and report['passed'] is False
    assert report['checks']==expected and report['sdist_missing']==[name] and report['sdist_mismatched']==[]
    assert report['runtime_files']==manifest['runtime_files'] and report['runtime_tree_sha256']==manifest['runtime_tree_sha256']
    assert report['artifacts'][wheelname]==artifacts[wheelname]
    assert report['artifacts'][negative.name]['sha256']==control['negative_archive_sha256']
    assert report['artifacts'][negative.name]['bytes']==negative.stat().st_size
    records.append({'tracked_path':name,'sha256':sha(blob),'bytes':len(blob),'zip_members':actual_members,
        'historical_reference_commit':commit,'historical_source_hash_count':len(source_map),
        'historical_source_hashes_independently_equal_git_blobs':True,
        'historical_result':inc['historical_ci'],'current_release_qualification':False,
        'positive_sdist_member_byte_exact':True,
        'negative_report':str(report_path),'negative_report_sha256':sha(report_path.read_bytes()),
        'negative_archive_sha256':control['negative_archive_sha256'],'checks':expected,
        'negative_sdist_missing':[name],'positive_wheel_artifact_identity_exact':True,
        'negative_runtime_map_equal_positive':True,'negative_raw_report_bindings_exact':True})
result={'source_commit':COMMIT,'passed':True,'scope':'six tracked historical ZIPs and actual omission JSON bindings; no tests/SQL/services/collector rerun',
    'cpu_ids':sorted(os.sched_getaffinity(0)),'wall_seconds':time.monotonic()-t0,
    'independently_checked_source_zip_count':6,'negative_report_count':6,'historical_results_remain_failed':True,
    'historical_sources_are_not_bb34_release_CI':True,
    'negative_tar_full_member_diff_performed':False,
    'inputs':{str(p):{'bytes':p.stat().st_size,'sha256':sha(p.read_bytes())} for p in [provpath,indexpath,manifestpath]},
    'positive_artifact_identity':{name:data for name,data in artifacts.items()},'cases':records}
(OUT/'result.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:result[k] for k in ('passed','source_commit','independently_checked_source_zip_count','negative_report_count','wall_seconds')},indent=2))
