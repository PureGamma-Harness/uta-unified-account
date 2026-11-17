"""Read-only pinned-archive/runtime validation. Creates no SQL connection."""
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path, PurePosixPath
import posixpath
import shutil
import subprocess
import tarfile

HERE = Path(__file__).resolve().parent
DIRECTORY = Path('/tmp/uta-python31318-24-20261117')
ARCHIVE = DIRECTORY / 'python-3.13.18-linux-24.04-x64.tar.gz'
PREFIX = DIRECTORY / 'runtime'
EXPECTED = '683005a1465d94d40045f6a1a6eb316885b5f08d3360f7922b44ef58a14a9eed'
assert ARCHIVE.stat().st_size == 102778317
assert sha256(ARCHIVE.read_bytes()).hexdigest() == EXPECTED
assert PREFIX.stat().st_mode & 0o777 == 0o700
assert DIRECTORY.stat().st_mode & 0o777 == 0o700
links = []
with tarfile.open(ARCHIVE, 'r:gz') as archive:
    members = archive.getmembers()
    seen = set()
    for member in members:
        name = PurePosixPath(member.name)
        assert not name.is_absolute() and '..' not in name.parts
        assert str(name) not in seen
        seen.add(str(name))
        assert member.isdir() or member.isfile() or member.issym() or member.islnk()
        assert not member.mode & 0o6000
        if member.issym() or member.islnk():
            assert not PurePosixPath(member.linkname).is_absolute()
            normalized = posixpath.normpath(posixpath.join(str(name.parent), member.linkname) if member.issym() else member.linkname)
            assert normalized != '..' and not normalized.startswith('../')
            links.append({'name': member.name, 'target': member.linkname})
    for relative in ('bin/python3.13', 'lib/libpython3.13.so.1.0'):
        member = archive.getmember('./' + relative)
        expected = sha256(archive.extractfile(member).read()).hexdigest()
        assert sha256((PREFIX / relative).read_bytes()).hexdigest() == expected

environment = {key: value for key, value in os.environ.items()
               if key not in {'PYTHONHOME', 'PYTHONPATH', 'LD_LIBRARY_PATH'}}
environment.update(LD_LIBRARY_PATH=str(PREFIX / 'lib'), PYTHONDONTWRITEBYTECODE='1')
code = """import json,os,platform,sqlite3,ssl,subprocess,sys,sysconfig
from pathlib import Path
child=subprocess.run([sys.executable,'--version'],capture_output=True,text=True,timeout=10)
libraries=sorted({line.split()[-1] for line in Path('/proc/self/maps').read_text().splitlines() if '/' in line and any(name in line for name in ('libpython3.13','libsqlite3','libssl.so','libcrypto.so','ld-linux'))})
result={'python':sys.version,'executable':sys.executable,'prefix':sys.prefix,'base_prefix':sys.base_prefix,'platform':platform.platform(),'libc':platform.libc_ver(),'sqlite_version':sqlite3.sqlite_version,'sqlite_module_path':sqlite3.__file__,'openssl':ssl.OPENSSL_VERSION,'config_args':sysconfig.get_config_var('CONFIG_ARGS'),'compiler':sysconfig.get_config_var('CC'),'py_enable_shared':sysconfig.get_config_var('Py_ENABLE_SHARED'),'gil_disabled':sysconfig.get_config_var('Py_GIL_DISABLED'),'library':sysconfig.get_config_var('LDLIBRARY'),'compiled_libdir':sysconfig.get_config_var('LIBDIR'),'actually_mapped_libraries':libraries,'child_version':{'returncode':child.returncode,'stdout':child.stdout,'stderr':child.stderr},'sql_connections_created':False,'financial_workload_executed':False}
assert result['python'].startswith('3.13.18 ')
assert child.returncode==0 and child.stdout=='Python 3.13.18\\n'
assert str(Path(sys.prefix)/'lib/libpython3.13.so.1.0') in libraries
print(json.dumps(result,indent=2))
"""
started = datetime.now(timezone.utc).isoformat()
result = subprocess.run([str(PREFIX / 'bin/python3.13'), '-B', '-c', code],
                        cwd=PREFIX, env=environment, capture_output=True, timeout=15)
(HERE / 'final-capability.stdout.txt').write_bytes(result.stdout)
(HERE / 'final-capability.stderr.txt').write_bytes(result.stderr)
assert result.returncode == 0, result.stderr.decode()
report = {'started_at': started, 'finished_at': datetime.now(timezone.utc).isoformat(),
          'archive': str(ARCHIVE), 'archive_sha256': EXPECTED, 'archive_bytes': ARCHIVE.stat().st_size,
          'member_count': len(members), 'safe_member_validation': True, 'relative_internal_links': links,
          'exact_extracted_python_and_libpython_member_bytes': True,
          'prefix': str(PREFIX), 'actual_prefix_mode': oct(PREFIX.stat().st_mode & 0o777),
          'environment_overrides': {key: environment.get(key) for key in ('PYTHONPATH','PYTHONHOME','LD_LIBRARY_PATH','PYTHONDONTWRITEBYTECODE')},
          'command': [str(PREFIX / 'bin/python3.13'), '-B', '-c', code], 'returncode': result.returncode,
          'archive_and_prefix_logical_regular_bytes': ARCHIVE.stat().st_size + sum(path.stat().st_size for path in PREFIX.rglob('*') if path.is_file() and not path.is_symlink()),
          'free_after': shutil.disk_usage(DIRECTORY).free, 'install_script_executed': False,
          'runtime_usable_for_future_separately_authorized_diagnosis': True,
          'same_ci_environment': False, 'same_ci_binary_claimed': False,
          'sql_connections_created': False, 'financial_workload_executed': False,
          'existing_runtimes_or_jobs_modified': False, 'production_approved': False}
(HERE / 'preparation-result.json').write_text(json.dumps(report, indent=2)+'\n')
print(json.dumps({'language_version_ready': '3.13.18', 'prefix': str(PREFIX),
                  'requires_ld_library_path': environment['LD_LIBRARY_PATH'],
                  'free_after': report['free_after'], 'same_ci_environment': False}, indent=2))
