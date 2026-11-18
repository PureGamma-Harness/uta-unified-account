"""Test-only cold import proof; no account, database or worker is created."""
from contextlib import contextmanager
from hashlib import sha256
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
from tempfile import TemporaryDirectory

MODES=('controller','escrow','deny_sqlite3','deny_uta')
TARGETS={'controller':'independent_m0_controller.py','escrow':'m0_stream_escrow.py'}
STREAM_CAP=32768
CHILD_CODE=r'''
import sys
events=[]
roots=('sqlite3','_sqlite3','uta')
labels={'sqlite3':'SQLITE3','_sqlite3':'_SQLITE3','uta':'UTA'}
class ForbiddenImport(Exception):pass
def blocked(name):return any(name==root or name.startswith(root+'.') for root in roots)
def reject(name):
    if blocked(name):
        events.append(labels[name.split('.')[0]])
        raise ForbiddenImport('blocked import')
def audit(event,args):
    if event=='import':reject(args[0])
class Finder:
    def find_spec(self,fullname,path=None,target=None):reject(fullname)
sys.addaudithook(audit)
sys.meta_path.insert(0,Finder())
import json
import resource
from hashlib import sha256
from pathlib import Path
import types
mode=sys.argv[1]
result={'kind':'COLD_IMPORT_PROOF','version':1,'mode':mode,'status':'IMPORT_CONTRACT_FAILED',
    'isolated':sys.flags.isolated==1,'no_site':sys.flags.no_site==1,
    'sitecustomize_loaded':'sitecustomize' in sys.modules or 'usercustomize' in sys.modules,
    'guard_events':events,'blocked_cache_count':0,'target_sha256':None}
try:
    _,hard=resource.getrlimit(resource.RLIMIT_FSIZE)
    cap=32768 if hard==resource.RLIM_INFINITY else min(hard,32768)
    resource.setrlimit(resource.RLIMIT_FSIZE,(cap,cap))
    if any(blocked(name) for name in sys.modules):raise ForbiddenImport('blocked cache')
    if not (result['isolated'] and result['no_site'] and not result['sitecustomize_loaded']):raise ValueError('isolation')
    if mode in ('deny_sqlite3','deny_uta'):
        names=('sqlite3','_sqlite3') if mode=='deny_sqlite3' else ('uta',)
        for name in names:
            try:__import__(name)
            except ForbiddenImport:pass
            else:raise AssertionError('guard did not deny')
        result['status']='GUARD_BLOCKED'
    else:
        names={'controller':'independent_m0_controller.py','escrow':'m0_stream_escrow.py'}
        target=Path(sys.argv[2])/'tools'/names[mode]
        raw=target.read_bytes()
        if len(raw)>131072:raise ValueError('target cap')
        result['target_sha256']=sha256(raw).hexdigest()
        module=types.ModuleType('cold_import_target')
        module.__file__=str(target);module.__package__=''
        sys.modules[module.__name__]=module
        exec(compile(raw,'<cold-import-target>','exec'),module.__dict__)
        if events or any(blocked(name) for name in sys.modules):raise ForbiddenImport('blocked cache')
        result['status']='PASS_IMPORT_COLD'
except ForbiddenImport:result['status']='FORBIDDEN_IMPORT'
except BaseException:result['status']='IMPORT_CONTRACT_FAILED'
result['blocked_cache_count']=sum(blocked(name) for name in sys.modules)
result['sitecustomize_loaded']='sitecustomize' in sys.modules or 'usercustomize' in sys.modules
print(json.dumps(result,sort_keys=True))
raise SystemExit(0 if result['status'] in ('PASS_IMPORT_COLD','GUARD_BLOCKED') else 1)
'''

@contextmanager
def _directory(evidence_root,mode):
    if evidence_root is None:
        with TemporaryDirectory(prefix='cold-import-contract-') as directory:yield Path(directory)
    else:
        root=Path(evidence_root);info=root.lstat()
        if not stat.S_ISDIR(info.st_mode) or stat.S_IMODE(info.st_mode)&0o077 or info.st_uid!=os.getuid():raise ValueError('private_evidence_root_required')
        directory=root/mode;directory.mkdir(mode=0o700)
        yield directory

def _stream(path):
    raw=path.read_bytes()
    return raw,{'bytes':len(raw),'sha256':sha256(raw).hexdigest()}

def _need(value):
    if not value:raise ValueError('invalid_proof')

def _empty_result(mode):
    return {'kind':'COLD_IMPORT_RESULT','version':1,'mode':mode,'status':'UNKNOWN',
        'code':'NOT_STARTED','returncode':None,'spawned':False,'killed':False,'child_reaped':False,
        'stdout':None,'stderr':None,'proof':None,'expected_target_sha256':None}

def _stop(process,result):
    result['killed']=True
    try:process.kill()
    except OSError:pass
    try:result['returncode']=process.wait(timeout=1)
    except (OSError,subprocess.TimeoutExpired):result['code']='CHILD_REAP_UNKNOWN'
    result['child_reaped']=process.returncode is not None

def _probe_import(mode,source_root=None,*,evidence_root=None):
    """One owned direct interpreter, 1s execution +1s kill/reap budget.

    Return only fixed codes, validated child fields and closed-stream hashes.
    Raw files are retained only in an explicitly supplied private evidence root.
    This is an import contract for trusted source, not a hostile-code sandbox.
    """
    if mode not in MODES:raise ValueError('unknown_probe_mode')
    root=Path(source_root).resolve() if source_root is not None else Path(__file__).resolve().parents[1]
    expected=sha256((root/'tools'/TARGETS[mode]).read_bytes()).hexdigest() if mode in TARGETS else None
    result=_empty_result(mode);result['expected_target_sha256']=expected
    with _directory(evidence_root,mode) as directory:
        stdout_path=directory/'stdout.bin';stderr_path=directory/'stderr.bin';process=None;cleanup_attempted=False
        with stdout_path.open('xb') as stdout,stderr_path.open('xb') as stderr:
            os.fchmod(stdout.fileno(),0o600);os.fchmod(stderr.fileno(),0o600)
            try:
                environment={k:v for k,v in os.environ.items() if not k.startswith('PYTHON')}
                process=subprocess.Popen([sys.executable,'-I','-S','-c',CHILD_CODE,mode,str(root)],
                    stdin=subprocess.DEVNULL,stdout=stdout,stderr=stderr,close_fds=True,cwd=directory,env=environment)
                result['spawned']=True
                try:result['returncode']=process.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    result['code']='CHILD_TIMEOUT';cleanup_attempted=True;_stop(process,result)
                result['child_reaped']=process.returncode is not None
                if result['code']=='NOT_STARTED':result['code']='CHILD_EXITED'
            except OSError:result['code']='CHILD_OS_ERROR'
            finally:
                if process is not None and not result['child_reaped'] and not cleanup_attempted:_stop(process,result)
        if not result['child_reaped']:return result
        try:raw,out=_stream(stdout_path);errors,err=_stream(stderr_path)
        except OSError:result['code']='CHILD_OUTPUT_IO';return result
        result.update(stdout=out,stderr=err)
        if result['code']!='CHILD_EXITED':return result
        if len(raw)>STREAM_CAP or errors or result['returncode']!=0:result['code']='CHILD_OUTPUT_OR_EXIT';return result
        try:
            def pairs(items):
                value={}
                for key,v in items:
                    if key in value:raise ValueError('duplicate')
                    value[key]=v
                return value
            proof=json.loads(raw,object_pairs_hook=pairs)
            _need(type(proof) is dict and set(proof)=={'kind','version','mode','status','isolated','no_site','sitecustomize_loaded','guard_events','blocked_cache_count','target_sha256'})
            _need(proof['kind']=='COLD_IMPORT_PROOF' and type(proof['version']) is int and proof['version']==1)
            _need(proof['mode']==mode and proof['isolated'] is True and proof['no_site'] is True and proof['sitecustomize_loaded'] is False)
            _need(type(proof['blocked_cache_count']) is int and proof['blocked_cache_count']==0)
            expected_events=[] if mode in TARGETS else ['SQLITE3','_SQLITE3'] if mode=='deny_sqlite3' else ['UTA']
            _need(proof['guard_events']==expected_events and proof['target_sha256']==expected)
            _need(proof['status']==('PASS_IMPORT_COLD' if mode in TARGETS else 'GUARD_BLOCKED'))
            result.update(status='PASS',code='COLD_IMPORT_VERIFIED',proof=proof)
        except (ValueError,UnicodeError,AssertionError,TypeError,KeyError):result['code']='CHILD_PROOF_INVALID'
    return result

def probe_import(mode,source_root=None,*,evidence_root=None):
    if mode not in MODES:
        result=_empty_result('INVALID');result['code']='PROBE_MODE';return result
    try:return _probe_import(mode,source_root,evidence_root=evidence_root)
    except (OSError,ValueError):
        result=_empty_result(mode);result['code']='SOURCE_OR_EVIDENCE_IO';return result
