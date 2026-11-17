"""No-SQL capability/source preflight, invoked only by an authorized batch."""
import hashlib,json,os,platform,sqlite3,sys,sysconfig,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]

def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def probe(binding):
    reference=json.loads((Path(__file__).parent/'original_source266.json').read_text())
    sources={name:digest(ROOT/name) for name in reference['source_sha256']}
    mapped=sorted({line.split()[-1] for line in Path('/proc/self/maps').read_text().splitlines()
                   if '/' in line and any(term in line for term in ('libpython3.13','libsqlite3','libssl.so','libcrypto.so','ld-linux'))})
    libpython=[name for name in mapped if 'libpython3.13' in name]
    bound_files={key:{'path':value['path'],'sha256':digest(value['path'])}
                 for key,value in binding['files'].items()}
    return {'version_info':list(sys.version_info[:3]),'python':sys.version,
        'executable':str(Path(sys.executable).resolve()),'sqlite':sqlite3.sqlite_version,
        'platform':platform.platform(),'libc':platform.libc_ver(),
        'compiler':platform.python_compiler(),'prefix':sys.prefix,'base_prefix':sys.base_prefix,
        'flags':str(sys.flags),'optimize':sys.flags.optimize,'dont_write_bytecode':sys.dont_write_bytecode,
        'py_enable_shared':sysconfig.get_config_var('Py_ENABLE_SHARED'),
        'mapped_libraries':mapped,'mapped_libpython':libpython,
        'mapped_library_sha256':{name:digest(name) for name in mapped},'bound_files':bound_files,
        'environment':{key:os.environ.get(key) for key in binding['recorded_environment']},
        'affinity':sorted(os.sched_getaffinity(0)),
        'source_members':len(sources),'source_sha256':sources,
        'source_matches_original':sources==reference['source_sha256'],
        'monotonic_ns':time.monotonic_ns(),'boottime_ns':time.clock_gettime_ns(time.CLOCK_BOOTTIME),
        'utc_ns':time.time_ns(),'sql_connections_created':False,'financial_case_started':False}

if __name__=='__main__':
    if len(sys.argv)!=3 or sys.argv[1] not in ('A','B'):
        raise SystemExit('runtime_probe91.py A|B PREREG_JSON')
    config=json.loads(Path(sys.argv[2]).read_text())
    print(json.dumps(probe(config['runtimes'][sys.argv[1]]),indent=2,allow_nan=False))
