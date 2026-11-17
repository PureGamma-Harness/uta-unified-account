"""Small synthetic ZIP/TAR/report fixtures; never builds or installs a product."""
from copy import deepcopy
from hashlib import sha256
import io
import json
from pathlib import Path
import tarfile
import zipfile


def facts(path):
    data=path.read_bytes()
    return {'bytes':len(data),'sha256':sha256(data).hexdigest()}


def reference(path):
    return {'path':str(path),'sha256':facts(path)['sha256']}


def save(path,value):
    path.write_text(json.dumps(value)+'\n')
    return reference(path)


def create_package_evidence(root,commit):
    qualified=root/'qualified-source';qualified.mkdir()
    contents={'uta/__init__.py':b'__version__ = "0.5.0a1"\n',
        'uta/failure_diagnostics.py':b'# intended omission fixture\n',
        'tools/run_validation.py':b'# full validation command fixture\n',
        'tools/verify_release_archives.py':b'# synthetic verifier identity; never executed\n',
        'tests/test_durable_cli.py':b'# CLI helper fixture\n',
        'tests/test_durable_views.py':b'# view helper fixture\n',
        'pyproject.toml':b'[project]\nversion = "0.5.0a1"\n',
        'benchmarks/plans/20261117-managed-variants.json':(Path(__file__).resolve().parents[1]/'benchmarks/plans/20261117-managed-variants.json').read_bytes(),
        'evidence/ci-a.zip':b'opaque original CI-A bytes',
        'evidence/ci-b.zip':b'opaque original CI-B bytes'}
    for name,data in contents.items():
        path=qualified/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
    hashes={name:sha256(data).hexdigest() for name,data in contents.items()}
    wheel=root/'fixture-0.5.0a1.whl';sdist=root/'fixture-0.5.0a1.tar.gz'
    with zipfile.ZipFile(wheel,'w') as archive:
        for name,data in contents.items():
            if name.startswith('uta/'):archive.writestr(name,data)
        archive.writestr('fixture.dist-info/METADATA',b'Name: fixture\nVersion: 0.5.0a1\n')
    prefix='fixture-0.5.0a1'
    with tarfile.open(sdist,'w:gz') as archive:
        directory=tarfile.TarInfo(prefix);directory.type=tarfile.DIRTYPE;archive.addfile(directory)
        for name,data in contents.items():
            item=tarfile.TarInfo(prefix+'/'+name);item.size=len(data);archive.addfile(item,io.BytesIO(data))
    artifacts={path.name:facts(path) for path in (wheel,sdist)}
    runtime={name:value for name,value in hashes.items() if name.startswith('uta/')}
    runtime_digest=sha256(json.dumps(runtime,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    checknames=('version','wheel_runtime_exact','sdist_runtime_exact','sdist_required_files_exact','legacy_fixture_pinned','legacy_fixture_licensed','entry_points')
    common={'source_commit':commit,'passed':True,'version':'0.5.0a1','artifacts':artifacts}
    archives=dict(common,sdist_required_files=sorted(hashes),runtime_files=runtime,runtime_tree_sha256=runtime_digest,
        sdist_missing=[],sdist_mismatched=[],checks={name:True for name in checknames},metadata_versions=['0.5.0a1'],
        entry_points='[console_scripts]\nfixture = example:main\n',cli_helper_sha256=hashes['tests/test_durable_cli.py'],
        legacy_fixture_provenance={'scope':'synthetic archive protocol fixture'})
    installed=dict(common,tests={'run':8,'errors':0,'failures':0,'skipped':0},commands=[{'returncode':0}]*8,
        isolated=True,pythonpath=None,runtime_tree_sha256=runtime_digest)
    views=dict(installed,tests={'run':3,'errors':0,'failures':0,'skipped':0})
    verdict=dict(common,no_old_artifacts_or_pass_reused=True,actual_negative_controls=4)
    cases=[];runtime_reports={};zip_reports={};zip_cases=[]
    for label,kind,target in [('wheel','wheel','uta/failure_diagnostics.py'),('sdist','sdist','uta/failure_diagnostics.py'),
                              ('ci-a','sdist','evidence/ci-a.zip'),('ci-b','sdist','evidence/ci-b.zip')]:
        negative=root/(label+'-missing'+('.whl' if kind=='wheel' else '.tar.gz'))
        if kind=='wheel':
            with zipfile.ZipFile(wheel) as original,zipfile.ZipFile(negative,'w') as output:
                for item in original.infolist():
                    if item.filename!=target:output.writestr(item,original.read(item.filename))
        else:
            with tarfile.open(sdist) as original,tarfile.open(negative,'w:gz') as output:
                for item in original.getmembers():
                    if item.name!=prefix+'/'+target:output.addfile(item,original.extractfile(item) if item.isfile() else None)
        false={'wheel_runtime_exact'} if kind=='wheel' else {'sdist_runtime_exact','sdist_required_files_exact'} if target.startswith('uta/') else {'sdist_required_files_exact'}
        report=deepcopy(archives);report.update(passed=False,checks={name:name not in false for name in checknames},
            sdist_missing=[] if kind=='wheel' else [target])
        side=sdist if kind=='wheel' else wheel
        report['artifacts']={side.name:facts(side),negative.name:facts(negative)}
        path=root/(label+'-report.json');report_ref=save(path,report)
        argv=['/fixture/python',str(qualified/'tools/verify_release_archives.py'),'--source',str(qualified),'--commit',commit,
              '--wheel',str(negative if kind=='wheel' else wheel),'--sdist',str(negative if kind=='sdist' else sdist),'--output',str(path)]
        case={'source_commit':commit,'case':label+'_missing_new_failure_diagnostics_is_rejected','removed_member':target,
            'removed_count':1,'negative_archive_sha256':facts(negative)['sha256'],'argv':argv,'returncode':1,
            'passed':True,'checks':report['checks'],'sdist_missing':report['sdist_missing']}
        if target.startswith('uta/'):
            cases.append(case);runtime_reports[kind]=report_ref
        else:
            zip_cases.append(case);zip_reports[target]=report_ref
    controls={'source_commit':commit,'passed':True,'cases':cases}
    zips={'source_commit':commit,'passed':True,'inclusions':[{'tracked_path':name,'sha256':hashes[name]} for name in hashes if name.endswith('.zip')],
          'omission_controls':zip_cases}
    package={name:save(root/('package-'+name+'.json'),data) for name,data in
        [('verdict',verdict),('archives',archives),('installed',installed),('views',views),('runtime_controls',controls),('zip_controls',zips)]}
    package.update(artifact_files={'wheel':reference(wheel),'sdist':reference(sdist)},
        verifier=reference(qualified/'tools/verify_release_archives.py'),runtime_reports=runtime_reports,zip_reports=zip_reports)
    return hashes,package
