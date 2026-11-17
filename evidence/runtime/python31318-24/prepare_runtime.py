"""Prepare one pinned official archive; no install.sh or financial workload."""
from hashlib import sha256
import json
import os
from pathlib import Path, PurePosixPath
import posixpath
import shutil
import subprocess
import tarfile
from datetime import datetime, timezone

ARCHIVE = Path('/tmp/uta-python31318-24-20261117/python-3.13.18-linux-24.04-x64.tar.gz')
PREFIX = ARCHIVE.parent / 'runtime'
HERE = Path(__file__).resolve().parent
EXPECTED = '683005a1465d94d40045f6a1a6eb316885b5f08d3360f7922b44ef58a14a9eed'
assert ARCHIVE.stat().st_size == 102778317
assert sha256(ARCHIVE.read_bytes()).hexdigest() == EXPECTED
assert not PREFIX.exists()
os.umask(0o077)
started = datetime.now(timezone.utc).isoformat()
free_before = shutil.disk_usage(ARCHIVE.parent).free
with tarfile.open(ARCHIVE, 'r:gz') as archive:
    members = archive.getmembers()
    names = set()
    for member in members:
        name = PurePosixPath(member.name)
        assert not name.is_absolute() and '..' not in name.parts
        canonical = str(name)
        assert canonical not in names
        names.add(canonical)
        assert member.isdir() or member.isfile() or member.issym() or member.islnk()
        assert not member.mode & 0o6000
        if member.issym() or member.islnk():
            target = member.linkname
            assert not PurePosixPath(target).is_absolute()
            resolved = posixpath.normpath(posixpath.join(str(name.parent), target) if member.issym() else target)
            assert resolved != '..' and not resolved.startswith('../')
    # Reject any entry nested beneath a link, even if its target is internal.
    links = {str(PurePosixPath(m.name)) for m in members if m.issym() or m.islnk()}
    for member in members:
        assert not any(str(parent) in links for parent in PurePosixPath(member.name).parents)
    PREFIX.mkdir(mode=0o700)
    archive.extractall(PREFIX, filter='data')

python = PREFIX / 'bin/python3.13'
env = {key: value for key, value in os.environ.items() if key not in {'PYTHONPATH', 'PYTHONHOME', 'LD_LIBRARY_PATH'}}
commands = []
def run(label, argv, environment):
    begin = datetime.now(timezone.utc).isoformat()
    result = subprocess.run(argv, env=environment, cwd=PREFIX, capture_output=True, timeout=15)
    (HERE / (label + '.stdout.txt')).write_bytes(result.stdout)
    (HERE / (label + '.stderr.txt')).write_bytes(result.stderr)
    commands.append({'label': label, 'argv': argv, 'started_at': begin,
        'finished_at': datetime.now(timezone.utc).isoformat(), 'exit_code': result.returncode,
        'environment_overrides': {key: environment.get(key) for key in ('PYTHONPATH', 'PYTHONHOME', 'LD_LIBRARY_PATH', 'PYTHONDONTWRITEBYTECODE')}})
    return result

initial = run('initial-version', [str(python), '--version'], env)
working = dict(env, PYTHONDONTWRITEBYTECODE='1')
if initial.returncode:
    working['LD_LIBRARY_PATH'] = str(PREFIX / 'lib')
    second = run('bundled-library-version', [str(python), '--version'], working)
    if second.returncode:
        (HERE/'commands.json').write_text(json.dumps(commands, indent=2)+'\n')
        raise SystemExit('Local bundled-library attempt failed; no global changes or workload')
capability = """import json,os,platform,sqlite3,ssl,subprocess,sys,sysconfig
child=subprocess.run([sys.executable,'--version'],capture_output=True,text=True,timeout=10)
print(json.dumps({'python':sys.version,'executable':sys.executable,'prefix':sys.prefix,'base_prefix':sys.base_prefix,'platform':platform.platform(),'libc':platform.libc_ver(),'sqlite_version':sqlite3.sqlite_version,'sqlite_module_path':sqlite3.__file__,'openssl':ssl.OPENSSL_VERSION,'config_args':sysconfig.get_config_var('CONFIG_ARGS'),'compiler':sysconfig.get_config_var('CC'),'py_enable_shared':sysconfig.get_config_var('Py_ENABLE_SHARED'),'gil_disabled':sysconfig.get_config_var('Py_GIL_DISABLED'),'library':sysconfig.get_config_var('LDLIBRARY'),'libdir':sysconfig.get_config_var('LIBDIR'),'child_version':{'returncode':child.returncode,'stdout':child.stdout,'stderr':child.stderr},'sql_connections_created':False,'financial_workload_executed':False},indent=2))
raise SystemExit(child.returncode)
"""
result = run('capability', [str(python), '-B', '-c', capability], working)
assert result.returncode == 0
value = json.loads(result.stdout)
assert value['python'].startswith('3.13.18 ')
size = sum(path.stat().st_size for path in PREFIX.rglob('*') if path.is_file() and not path.is_symlink())
report = {'started_at': started, 'finished_at': datetime.now(timezone.utc).isoformat(),
    'archive': str(ARCHIVE), 'archive_bytes': ARCHIVE.stat().st_size, 'archive_sha256': EXPECTED,
    'prefix': str(PREFIX), 'member_count': len(members), 'symlink_count': len(links),
    'safe_member_validation': True, 'install_script_executed': False,
    'prefix_logical_regular_bytes': size, 'free_before_extraction': free_before,
    'free_after': shutil.disk_usage(ARCHIVE.parent).free, 'commands': commands,
    'runtime_usable_for_future_separately_authorized_diagnosis': True,
    'same_ci_environment': False, 'same_ci_binary_claimed': False,
    'sql_connections_created': False, 'financial_workload_executed': False,
    'old_jobs_or_existing_runtimes_modified': False, 'production_approved': False}
(HERE / 'preparation-result.json').write_text(json.dumps(report, indent=2)+'\n')
print(json.dumps({'python': value['python'], 'sqlite': value['sqlite_version'],
    'prefix': str(PREFIX), 'local_environment': commands[-1]['environment_overrides'],
    'free_after': report['free_after'], 'same_ci_environment': False}, indent=2))
