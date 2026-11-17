"""Dispatch-only independent-host M0 draft. PREP is the default.

No product imports, SQL, subprocess or workload occurs by importing this module.
Execute is intentionally gated by an operator manifest, exact source/control
hashes, provider context, different host/boot, local storage and fresh space.
Private authority/request/stream files are never copied to the public directory.
"""
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
from hashlib import sha256, sha1
import argparse
from collections import Counter
import gzip
import importlib.util
import json
import marshal
import math
import os
from pathlib import Path
import platform
import re
import resource
import socket
import stat
import subprocess
import sys
import time

SOURCE = '909acecd153e2e89dfe2238e3ed3a3d9a3d3c9f0'
SOURCE_TREE = 'cee60bc0b5413551030300e065d0dcaac6a7ff55'
APPROVED_BRANCH = 'refs/heads/perf/approved-m0-20261117-03'
REGISTRATION_ID = 'independent-m0-20261117-03'
APPROVAL_PATH = 'config/independent-m0-approved.json'
ONCE_WORKFLOW = '.github/workflows/independent-m0-once.yml'
TRACKED = 5518
CASE_CAP = 32 * 1024**2
AGGREGATE_CAP = 64 * 1024**2
CLEANUP_RESERVE = 32 * 1024**2
ESCROW_CAP = 96 * 1024**2
TOTAL_CAP = AGGREGATE_CAP + ESCROW_CAP + CLEANUP_RESERVE
LEGACY_MIN_FREE = 2 * 1024**3 + CASE_CAP + CLEANUP_RESERVE
MIN_FREE = 2 * 1024**3 + TOTAL_CAP
RECIPIENT_SPKI = 'de01fcb8516224fd3d91f442899d582c4fcaa5aadfac8e91b45f680307ed3ab1'
RECIPIENT_PEM = '3140279eb39d7873fdcbd23fb46b71f987d43a12184087a791c5b2073b5f1fed'
OUTCOMES = {'financial_succeeded', 'business_rejected', 'control_or_market_rejected',
    'local_outstanding_full', 'durable_queue_full', 'enqueue_business_rejected',
    'submission_failed', 'technical_quarantined', 'unknown', 'timeout'}
EVIDENCE_COMMITS = {'local_three':'841b5cc908e7e15e9461c0ecc91a173e2162cada',
    'ci_eight':'85e96b63813e0b993e532f054ef97740e64176cd',
    'package_author':'721e9d02308d900cd39db2a209d0130394f78338',
    'package_peer':'5c98110359f293413ebe561b3cb2f5683ee26863'}

class GateError(Exception):
    pass

def need(value, code):
    if not value:
        raise GateError(code)

def digest(path):
    return sha256(Path(path).read_bytes()).hexdigest()

def numeric(value):
    need(type(value) in (int,float) and math.isfinite(value), 'numeric_type')
    return value

def nonnegative(value):
    need(numeric(value)>=0,'negative_numeric')
    return value

def close_number(actual, expected, code):
    need(math.isclose(numeric(actual),expected,rel_tol=2e-12,abs_tol=1e-12),code)

def integer(value, lower=0, upper=2**63-1):
    need(type(value) is int and lower <= value <= upper, 'integer_domain')
    return value

def strict_json(raw):
    def pairs(items):
        result = {}
        for key,value in items:
            need(key not in result, 'duplicate_json_key')
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=lambda _: (_ for _ in ()).throw(GateError('json_nonfinite')))

def read_json(path, limit=4*1024**2):
    info = Path(path).lstat()
    need(stat.S_ISREG(info.st_mode) and info.st_size <= limit, 'input_file_type_or_size')
    return strict_json(Path(path).read_bytes())

def public_write(root, name, value):
    need(re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_.-]{0,150}', name) is not None, 'public_filename')
    path = root / name
    raw = (json.dumps(value,sort_keys=True,indent=2,allow_nan=False)+'\n').encode()
    need(len(raw) <= 4*1024**2, 'public_record_cap')
    fd = os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW|os.O_CLOEXEC,0o600)
    with os.fdopen(fd,'wb') as stream:
        stream.write(raw);stream.flush();os.fsync(stream.fileno())
    return {'name':name,'bytes':len(raw),'sha256':sha256(raw).hexdigest()}

RESOURCE_SCAN_ATTEMPTS = 3
RESOURCE_SCAN_RETRY_NS = 50_000_000

# D1 is explanatory only: labels never participate in an exemption decision.
DIAGNOSTIC_PHASES=frozenset({'PREFLIGHT','CRYPTO_CAPABILITY','RUNTIME_PROBE','CASE_B','ESCROW_B','CASE_P','ESCROW_P','FINAL_PUBLIC_VERIFY'})
DIAGNOSTIC_SCOPES=frozenset({'PRIVATE_ROOT','PRIVATE_CASE','PUBLIC_ROOT','PUBLIC_CASE','UNKNOWN'})
DIAGNOSTIC_OPERATIONS=frozenset({'ROOT_LSTAT','ENUMERATE_DIRECTORY','ENTRY_LSTAT','VALIDATE_PARENT','VALIDATE_MAIN','RETRY_STABLE_SET','RESOURCE_LIMIT','HEALTH_VALIDATION'})
DIAGNOSTIC_LABELS=frozenset({'UNKNOWN','AUTH_ROUTER_MAIN','AUTH_ROUTER_WAL','AUTH_ROUTER_SHM','AUTH_SHARD_0_MAIN','AUTH_SHARD_0_WAL','AUTH_SHARD_0_SHM','AUTH_SHARD_1_MAIN','AUTH_SHARD_1_WAL','AUTH_SHARD_1_SHM','RUNTIME_PROBE_MAIN','RUNTIME_PROBE_WAL','RUNTIME_PROBE_SHM','AUTH_CREATE_TEMP','ESCROW_CHECKPOINT_PART','ESCROW_CHECKPOINT','ESCROW_STAGED_CIPHER','ESCROW_PUBLIC_CIPHER'})
DIAGNOSTIC_CODES=frozenset({'resource_root_directory','resource_entries_cap','resource_symlink','resource_special','escrow_directory_scope','escrow_file_scope','resource_compartment_cap','resource_missing_non_aux','resource_aux_parent_changed','resource_aux_main_changed','resource_aux_churn_limit','resource_aux_retry_deadline','resource_stable_type_changed','resource_stable_disappeared_during_retry','resource_scan_role','resource_case_name','tree_entries_cap','output_symlink','output_special','case_output_cap','case_metadata_file','diagnostic_file_scope','runner_boot_changed','runner_host_changed','runner_cpu_unavailable','fresh_space','RESOURCE_PERMISSION_ERROR','RESOURCE_OS_ERROR','UNCLASSIFIED_RESOURCE_ERROR'})
_DIAGNOSTIC_CONTEXT=ContextVar('m0_resource_diagnostic_context',default=None)

def _diagnostic_code(error):
    if isinstance(error,GateError) and str(error) in DIAGNOSTIC_CODES:return str(error)
    if isinstance(error,PermissionError):return 'RESOURCE_PERMISSION_ERROR'
    if isinstance(error,OSError):return 'RESOURCE_OS_ERROR'
    return 'UNCLASSIFIED_RESOURCE_ERROR'

def _diagnostic_path(context,path):
    if path is None:return 'UNKNOWN',None,None
    path=Path(path)
    for role,anchor in (('PRIVATE_ROOT',context['private']),('PUBLIC_ROOT',context['public'])):
        try:return role,path.relative_to(anchor).as_posix(),path
        except ValueError:continue
    return 'UNKNOWN',None,path

def _diagnostic_label(role,relative):
    if relative is None:return 'UNKNOWN'
    if role=='PRIVATE_ROOT':
        match=re.fullmatch(r'[BP]/workload/authority/(router|shard-000[01])\.sqlite3(?:-(wal|shm))?',relative)
        if match:
            stem={'router':'AUTH_ROUTER','shard-0000':'AUTH_SHARD_0','shard-0001':'AUTH_SHARD_1'}[match[1]]
            return stem+'_'+(match[2].upper() if match[2] else 'MAIN')
        match=re.fullmatch(r'runtime-probe/private\.sqlite3(?:-(wal|shm))?',relative)
        if match:return 'RUNTIME_PROBE_'+(match[1].upper() if match[1] else 'MAIN')
        if re.fullmatch(r'[BP]/workload/authority/\.uta-create-[a-z0-9_]{8}',relative):return 'AUTH_CREATE_TEMP'
        if re.fullmatch(r'escrow-completed-[BP]\.json\.part',relative):return 'ESCROW_CHECKPOINT_PART'
        if re.fullmatch(r'escrow-completed-[BP]\.json',relative):return 'ESCROW_CHECKPOINT'
        if re.fullmatch(r'escrow-[BP]/(driver|case-owner)\.(stdout|stderr)\.cms',relative):return 'ESCROW_STAGED_CIPHER'
    if role=='PUBLIC_ROOT' and re.fullmatch(r'escrow-[BP]-safe/(driver|case-owner)\.(stdout|stderr)\.cms',relative):return 'ESCROW_PUBLIC_CIPHER'
    return 'UNKNOWN'

def validate_resource_diagnostic(value):
    need(type(value) is dict and set(value)=={'kind','version','phase','scope','operation','errno','catalogue_label','unknown_relative_path_sha256','primary_code'},'diagnostic_fields')
    need(value['kind']=='M0_RESOURCE_DIAGNOSTIC' and type(value['version']) is int and value['version']==1,'diagnostic_version')
    need(all(type(value[key]) is str for key in ('phase','scope','operation','catalogue_label','primary_code')),'diagnostic_enum_type')
    need(value['phase'] in DIAGNOSTIC_PHASES and value['scope'] in DIAGNOSTIC_SCOPES and value['operation'] in DIAGNOSTIC_OPERATIONS,'diagnostic_enum')
    integer(value['errno'],0,4095)
    need(value['catalogue_label'] in DIAGNOSTIC_LABELS and value['primary_code'] in DIAGNOSTIC_CODES,'diagnostic_label_or_code')
    hashed=value['unknown_relative_path_sha256']
    need(hashed is None or type(hashed) is str and re.fullmatch('[0-9a-f]{64}',hashed) is not None,'diagnostic_path_hash')
    need(value['catalogue_label']=='UNKNOWN' or hashed is None,'diagnostic_known_path_hash')
    return True

def _mark_resource_error(error,scope,operation,path=None):
    context=_DIAGNOSTIC_CONTEXT.get()
    if context is None or hasattr(error,'_m0_resource_origin'):return
    try:
        role,relative,actual=_diagnostic_path(context,path);label=_diagnostic_label(role,relative)
        hashed=None
        if label=='UNKNOWN' and actual is not None:
            raw=os.fsencode(relative if relative is not None else actual)
            hashed=sha256(role.encode()+b'\0'+raw).hexdigest()
        value={'kind':'M0_RESOURCE_DIAGNOSTIC','version':1,'phase':context['phase'],'scope':scope,
            'operation':operation,'errno':error.errno if isinstance(error,OSError) and type(error.errno) is int and 0<=error.errno<=4095 else 0,
            'catalogue_label':label,'unknown_relative_path_sha256':hashed,'primary_code':_diagnostic_code(error)}
        validate_resource_diagnostic(value);error._m0_resource_origin=value
    except BaseException:pass  # Optional annotation must never replace primary.

def _resource_lstat(path,scope,operation):
    try:return path.lstat()
    except BaseException as error:
        _mark_resource_error(error,scope,operation,path);raise

def _resource_need(condition,code,scope,operation,path=None):
    try:need(condition,code)
    except BaseException as error:
        _mark_resource_error(error,scope,operation,path);raise

def _resource_origin(error,context):
    current=error;seen=set()
    while current is not None and id(current) not in seen:
        seen.add(id(current));value=getattr(current,'_m0_resource_origin',None)
        if value is not None:
            result=dict(value,primary_code=_diagnostic_code(error));validate_resource_diagnostic(result);return result
        current=current.__cause__ or current.__context__
    _mark_resource_error(error,'UNKNOWN','RESOURCE_LIMIT' if _diagnostic_code(error) in {'resource_compartment_cap','case_output_cap','tree_entries_cap','resource_entries_cap'} else 'HEALTH_VALIDATION',getattr(error,'filename',None))
    return getattr(error,'_m0_resource_origin',None)

def _diagnostic_cleanup_bytes(private,public):
    # Finite known cleanup slots only; no DB reads and no fallible full rescan.
    paths=[public/f'resource-diagnostic-{phase}.json' for phase in DIAGNOSTIC_PHASES]
    paths += [private/f'resource-diagnostic-incomplete-{phase}.json' for phase in DIAGNOSTIC_PHASES]
    for case in ('B','P'):
        paths += [private/f'escrow-{stem}-{case}.json{suffix}' for stem in ('context','completed') for suffix in ('','.part')]
        paths += [private/f'escrow-owner-{case}.{suffix}' for suffix in ('stdout','stderr','owner.json')]
        paths += [private/f'escrow-{case}'/(stream+'.openssl-private-stderr') for stream in ('driver.stdout','driver.stderr','case-owner.stdout','case-owner.stderr')]
    total=0
    for path in paths:
        try:info=path.lstat()
        except FileNotFoundError:continue
        need(stat.S_ISREG(info.st_mode),'diagnostic_cleanup_file');total+=info.st_size
    return total

def write_resource_diagnostic(private,public,value):
    validate_resource_diagnostic(value)
    raw=(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode();need(len(raw)<=4096,'diagnostic_record_cap')
    info=public.lstat();need(stat.S_ISDIR(info.st_mode) and info.st_uid==os.getuid() and stat.S_IMODE(info.st_mode)&0o077==0,'diagnostic_public_directory')
    need(_diagnostic_cleanup_bytes(private,public)+len(raw)<=CLEANUP_RESERVE,'diagnostic_cleanup_cap')
    path=public/f"resource-diagnostic-{value['phase']}.json"
    incomplete=private/f"resource-diagnostic-incomplete-{value['phase']}.json"
    if incomplete.exists():return 'UNAVAILABLE'
    try:fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW|os.O_CLOEXEC,0o600)
    except FileExistsError:return 'ALREADY_RECORDED'
    try:
        with os.fdopen(fd,'wb') as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())
    except BaseException:
        # Keep a failed prefix privately, never publish it as a valid record.
        try:
            if not incomplete.exists():os.rename(path,incomplete)
        except BaseException:
            # Only this new O_EXCL optional prefix, never an original stream.
            try:path.unlink()
            except BaseException:pass
        raise
    return 'RECORDED'

class ResourceHealthFailure(GateError):
    def __init__(self,primary,status):
        super().__init__(_diagnostic_code(primary));self.primary_error=primary;self.diagnostic_status=status

def resource_health_check(private,public,phase,check,status_sink=None):
    need(phase in DIAGNOSTIC_PHASES,'diagnostic_phase')
    context={'private':private,'public':public,'phase':phase};token=_DIAGNOSTIC_CONTEXT.set(context)
    try:
        try:return check()
        except Exception as primary:
            status='UNAVAILABLE'
            try:
                value=_resource_origin(primary,context)
                if value is not None:status=write_resource_diagnostic(private,public,value)
            except BaseException:pass
            if status_sink is not None:status_sink.setdefault(phase,status)
            raise ResourceHealthFailure(primary,status) from primary
    finally:_DIAGNOSTIC_CONTEXT.reset(token)

def collect_resource_diagnostics(public,records):
    # Optional record I/O must not replace the first health failure. A malformed
    # or unreadable file stays unlisted, so the final allowlist still rejects it.
    status='COMPLETE'
    for phase in sorted(DIAGNOSTIC_PHASES):
        path=public/f'resource-diagnostic-{phase}.json'
        try:
            if path.exists():
                value=read_json(path,4096);validate_resource_diagnostic(value)
                need(value['phase']==phase,'diagnostic_public_name')
                records.append({'name':path.name,'bytes':path.stat().st_size,'sha256':digest(path)})
        except BaseException:status='UNAVAILABLE'
    return status

def _resource_tree_scope(root):
    context=_DIAGNOSTIC_CONTEXT.get()
    if context is None:return 'UNKNOWN'
    if root in {context['private']/'B',context['private']/'P'}:return 'PRIVATE_CASE'
    if root in {context['public']/'case-B-safe',context['public']/'case-P-safe'}:return 'PUBLIC_CASE'
    role,relative,path=_diagnostic_path(context,root)
    return role

def _walk_error(error,scope='UNKNOWN'):
    _mark_resource_error(error,scope,'ENUMERATE_DIRECTORY',error.filename);raise error

def _resource_entries(root, observe, allow_missing_root=False, diagnostic_scope='UNKNOWN'):
    try:info=_resource_lstat(root,diagnostic_scope,'ROOT_LSTAT')
    except FileNotFoundError:
        if allow_missing_root:return
        raise
    _resource_need(stat.S_ISDIR(info.st_mode) and not stat.S_ISLNK(info.st_mode),'resource_root_directory',diagnostic_scope,'ROOT_LSTAT',root)
    observe(root,info)
    for parent,dirs,files in os.walk(root,followlinks=False,onerror=lambda error:_walk_error(error,diagnostic_scope)):
        for name in dirs+files:
            path=Path(parent)/name
            info=_resource_lstat(path,diagnostic_scope,'ENTRY_LSTAT')
            try:charge=observe(path,info)
            except BaseException as error:
                _mark_resource_error(error,diagnostic_scope,'RETRY_STABLE_SET',path);raise
            yield path,info,charge

def _sqlite_aux_location(path, anchors):
    for role,anchor in anchors:
        try:relative=path.relative_to(anchor).as_posix()
        except ValueError:continue
        if role=='private_root':
            patterns=[r'[BP]/workload/authority/shard-[0-9]{4}\.sqlite3-(wal|shm)',r'runtime-probe/private\.sqlite3-(wal|shm)']
        elif role=='private_case':patterns=[r'workload/authority/shard-[0-9]{4}\.sqlite3-(wal|shm)']
        else:raise GateError('resource_scan_role')
        if not any(re.fullmatch(pattern,relative) for pattern in patterns):continue
        return anchor,relative
    return None

def _known_missing_sqlite_aux(error, anchors):
    if error.errno!=2 or not error.filename:return False
    path=Path(error.filename);location=_sqlite_aux_location(path,anchors)
    if location is not None:
        anchor,relative=location
        # A vanished sidecar never excuses missing/replaced main or parents.
        parent=anchor
        for part in Path(relative).parts[:-1]:
            info=_resource_lstat(parent,_resource_tree_scope(anchor),'VALIDATE_PARENT');_resource_need(stat.S_ISDIR(info.st_mode) and not stat.S_ISLNK(info.st_mode),'resource_aux_parent_changed',_resource_tree_scope(anchor),'VALIDATE_PARENT',parent)
            parent=parent/part
        info=_resource_lstat(parent,_resource_tree_scope(anchor),'VALIDATE_PARENT');_resource_need(stat.S_ISDIR(info.st_mode) and not stat.S_ISLNK(info.st_mode),'resource_aux_parent_changed',_resource_tree_scope(anchor),'VALIDATE_PARENT',parent)
        main=Path(str(path)[:-4]);info=_resource_lstat(main,_resource_tree_scope(anchor),'VALIDATE_MAIN')
        _resource_need(stat.S_ISREG(info.st_mode) and not stat.S_ISLNK(info.st_mode),'resource_aux_main_changed',_resource_tree_scope(anchor),'VALIDATE_MAIN',main)
        return True
    return False

def _fresh_resource_scan(scan, anchors):
    started=time.monotonic_ns()
    stable_types={};max_sizes={};current=set()
    def observe(path,info):
        kind=stat.S_IFMT(info.st_mode)
        if _sqlite_aux_location(path,anchors) is None:
            if path in stable_types:need(stable_types[path]==kind,'resource_stable_type_changed')
            stable_types[path]=kind;current.add(path)
        if stat.S_ISREG(info.st_mode):
            max_sizes[path]=max(max_sizes.get(path,0),info.st_size)
            return max_sizes[path]
        return 0
    for attempt in range(RESOURCE_SCAN_ATTEMPTS):
        current=set()
        try:
            value=scan(observe)
            if attempt:
                need(set(stable_types)<=current,'resource_stable_disappeared_during_retry')
                need(time.monotonic_ns()-started<=RESOURCE_SCAN_RETRY_NS,'resource_aux_retry_deadline')
            return value
        except FileNotFoundError as error:
            need(_known_missing_sqlite_aux(error,anchors),'resource_missing_non_aux')
            need(attempt+1<RESOURCE_SCAN_ATTEMPTS,'resource_aux_churn_limit')
            need(time.monotonic_ns()-started<RESOURCE_SCAN_RETRY_NS,'resource_aux_retry_deadline')
    raise GateError('resource_aux_churn_limit')

def _tree_bytes_once(root, entries_limit, byte_limit, observe):
    total = entries = 0
    scope=_resource_tree_scope(root)
    for path,info,charge in _resource_entries(root,observe,allow_missing_root=True,diagnostic_scope=scope):
        entries += 1
        _resource_need(entries <= entries_limit, 'tree_entries_cap',scope,'RESOURCE_LIMIT',path)
        _resource_need(not stat.S_ISLNK(info.st_mode), 'output_symlink',scope,'ENTRY_LSTAT',path)
        _resource_need(stat.S_ISREG(info.st_mode) or stat.S_ISDIR(info.st_mode), 'output_special',scope,'ENTRY_LSTAT',path)
        if stat.S_ISREG(info.st_mode):total += charge
        if byte_limit is not None:_resource_need(total<=byte_limit,'case_output_cap',scope,'RESOURCE_LIMIT',path)
    return total

def tree_bytes(root, entries_limit=20000, byte_limit=None, *, sqlite_aux_role=None):
    need(sqlite_aux_role in {None,'private_root','private_case'},'resource_scan_role')
    anchors=() if sqlite_aux_role is None else ((sqlite_aux_role,root),)
    return _fresh_resource_scan(lambda observe:_tree_bytes_once(root,entries_limit,byte_limit,observe),anchors)

def case_bytes(private, public, name):
    need(name in {'B','P'},'resource_case_name')
    total=tree_bytes(private/name,byte_limit=CASE_CAP,sqlite_aux_role='private_case')+tree_bytes(public/f'case-{name}-safe',byte_limit=CASE_CAP)
    for path in private.iterdir():
        if path.name==f'context-{name}.json' or path.name.startswith(f'case-owner-{name}.'):
            info=_resource_lstat(path,'PRIVATE_ROOT','ENTRY_LSTAT');_resource_need(stat.S_ISREG(info.st_mode),'case_metadata_file','PRIVATE_ROOT','ENTRY_LSTAT',path)
            total+=info.st_size
    return total

def _resource_usage_once(private, public, observe):
    """Disjoint logical accounting. Escrow namespace accepts fixed files only."""
    counts={'normal':0,'escrow':0,'cleanup':0};entries=0
    streams=r'(driver|case-owner)\.(stdout|stderr)'
    for root in (private,public):
      scope='PRIVATE_ROOT' if root==private else 'PUBLIC_ROOT'
      for path,info,charge in _resource_entries(root,observe,diagnostic_scope=scope):
        entries+=1;_resource_need(entries<=20000,'resource_entries_cap',scope,'RESOURCE_LIMIT',path)
        _resource_need(not stat.S_ISLNK(info.st_mode),'resource_symlink',scope,'ENTRY_LSTAT',path)
        _resource_need(stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode),'resource_special',scope,'ENTRY_LSTAT',path)
        rel=path.relative_to(root).as_posix()
        if stat.S_ISDIR(info.st_mode):
            if rel.startswith('escrow-'):_resource_need(re.fullmatch(r'escrow-[BP](-eligible|-safe)?',rel) is not None,'escrow_directory_scope',scope,'ENTRY_LSTAT',path)
            continue
        bucket='normal'
        if rel.startswith('resource-diagnostic-'):
            expected={f'resource-diagnostic-{phase}.json' for phase in DIAGNOSTIC_PHASES}
            incomplete={f'resource-diagnostic-incomplete-{phase}.json' for phase in DIAGNOSTIC_PHASES}
            _resource_need(root==public and rel in expected or root==private and rel in incomplete,'diagnostic_file_scope',scope,'ENTRY_LSTAT',path);bucket='cleanup'
        elif rel.startswith('escrow-'):
            if re.fullmatch(r'escrow-[BP](-eligible|-safe)?/'+streams+r'\.cms',rel):bucket='escrow'
            elif re.fullmatch(r'escrow-[BP]/'+streams+r'\.openssl-private-stderr',rel):bucket='cleanup'
            elif re.fullmatch(r'escrow-(context|completed)-[BP]\.json(\.part)?',rel) or re.fullmatch(r'escrow-owner-[BP]\.(stdout|stderr|owner\.json)',rel):bucket='cleanup'
            elif re.fullmatch(r'escrow-[BP]\.json',rel):bucket='escrow'
            else:_resource_need(False,'escrow_file_scope',scope,'ENTRY_LSTAT',path)
        counts[bucket]+=charge
        _resource_need(counts['normal']<=AGGREGATE_CAP and counts['escrow']<=ESCROW_CAP and counts['cleanup']<=CLEANUP_RESERVE and sum(counts.values())<=TOTAL_CAP,'resource_compartment_cap',scope,'RESOURCE_LIMIT',path)
    counts['total']=sum(counts.values())
    need(counts['normal']<=AGGREGATE_CAP and counts['escrow']<=ESCROW_CAP and counts['cleanup']<=CLEANUP_RESERVE and counts['total']<=TOTAL_CAP,'resource_compartment_cap')
    return counts

def resource_usage(private, public):
    # Only private known SQLite sidecars qualify; public/unknown paths do not.
    return _fresh_resource_scan(lambda observe:_resource_usage_once(private,public,observe),(('private_root',private),))

def validate_environment(approval, environment, actual, controller_sha, *, event='workflow_dispatch', event_commit=None):
    need(set(approval) == {'operator_approval_id','control_commit','controller_sha256','workspace_boot_id','workspace_hostname_sha256','workspace_recorded_at','source_commit'}, 'approval_fields')
    need(re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:-]{0,95}',approval['operator_approval_id']) is not None,'approval_id')
    need(re.fullmatch(r'[0-9a-f]{40}',approval['control_commit']) is not None,'control_commit_format')
    need(approval['controller_sha256'] == controller_sha,'controller_hash_changed')
    need(approval['source_commit'] == SOURCE,'workload_source_not_approved')
    need(environment.get('GITHUB_ACTIONS') == 'true' and environment.get('RUNNER_ENVIRONMENT') == 'github-hosted','hosted_runner_context_required')
    need(environment.get('GITHUB_EVENT_NAME') == event,'wrong_event')
    need(environment.get('GITHUB_SHA') == (event_commit or approval['control_commit']),'control_checkout_commit')
    need(environment.get('RUNNER_OS') == 'Linux','linux_required')
    need(environment.get('GITHUB_RUN_ATTEMPT') == '1','first_attempt_only')
    need(re.fullmatch(r'[1-9][0-9]*',environment.get('GITHUB_RUN_ID','')) is not None,'run_identity')
    need(actual['boot_id'] != approval['workspace_boot_id'],'same_boot_as_workspace')
    need(actual['hostname_sha256'] != approval['workspace_hostname_sha256'],'same_host_as_workspace')
    need(re.fullmatch(r'[0-9a-f-]{36}',approval['workspace_boot_id']) is not None,'workspace_boot_format')
    need(re.fullmatch(r'[0-9a-f]{64}',approval['workspace_hostname_sha256']) is not None,'workspace_host_format')
    stamp=datetime.fromisoformat(approval['workspace_recorded_at'])
    need(stamp.tzinfo is not None,'workspace_reference_timezone')
    age=(datetime.now(timezone.utc)-stamp).total_seconds()
    need(0 <= age <= 900,'workspace_reference_expired')
    need(actual['filesystem_type'] not in {'tmpfs','ramfs','nfs','nfs4','cifs','smb3','9p'} and not actual['filesystem_type'].startswith('fuse'),'nonlocal_or_memory_filesystem')
    need(actual['free_bytes'] >= MIN_FREE,'independent_runner_free_space')
    need(actual['network_external_exchange_configured'] is False,'external_exchange_prohibited')
    return True

def validate_dispatch(approval, environment, actual, controller_sha):
    return validate_environment(approval,environment,actual,controller_sha)

def command_spec():
    return {'case_order':[['B',False],['P',True]],'argv_templates':[
        ['PYTHON','WORKLOAD/benchmarks/run_managed_benchmark.py','--output','PRIVATE/B/workload','--duration','10','--rate','20','--accounts','100','--shards','2','--cpu-limit','1','--durable-batches','--financial-batch-size','0','--normal-cache-size','0'],
        ['PYTHON','WORKLOAD/benchmarks/run_managed_benchmark.py','--output','PRIVATE/P/workload','--duration','10','--rate','20','--accounts','100','--shards','2','--cpu-limit','1','--durable-batches','--financial-batch-size','0','--normal-cache-size','0','--profile']],
        'placeholder_resolution':'PYTHON=current recorded executable;WORKLOAD=exact909 checkout;PRIVATE=new exclusive RUNNER_TEMP root; no variable workload flags'}

def budget_spec():
    return {'format':2,'case_bytes':CASE_CAP,'normal_aggregate_bytes':AGGREGATE_CAP,'escrow_bytes':ESCROW_CAP,
        'cleanup_bytes':CLEANUP_RESERVE,'total_logical_bytes':TOTAL_CAP,
        'extra_free_bytes':2*1024**3,'minimum_fresh_free_bytes':MIN_FREE,'case_inner_wall_seconds':50,
        'case_pipeline_watchdog_seconds':56,'grace_seconds':2,'kill_wait_seconds':2,
        'case_complete_outer_max_seconds':60,
        'escrow_separate_postcase_wall_seconds':20,
        'watchdog_scope':'new owned session: source checks, driver, parser, hashes, fsync and staged safe output',
        'physical_os_disk_quota':False}

def validate_once_manifest(value, environment, event, relation):
    expected={'format','kind','execution_authorized','registration_id','branch','control_commit',
        'controller_sha256','workflow_sha256','source_commit','source_tree','command_spec','budgets',
        'workspace_boot_id','workspace_hostname_sha256','workspace_recorded_at','retention_mode',
        'escrow_tool_sha256','recipient_certificate_sha256','recipient_spki_sha256'}
    need(set(value)==expected,'once_manifest_fields')
    need(type(value['format']) is int and value['format']==2 and value['kind']=='ROOT_REVIEWED_ONCE_M0_V2_ESCROW','once_manifest_format')
    need(value['execution_authorized'] is True,'once_not_authorized')
    need(value['registration_id']==REGISTRATION_ID,'registration_id')
    need(value['branch']==environment.get('GITHUB_REF')==event.get('ref')==APPROVED_BRANCH,'exact_once_branch')
    need(environment.get('GITHUB_EVENT_NAME')=='push' and environment.get('GITHUB_RUN_ATTEMPT')=='1','once_first_push_attempt')
    need(event.get('created') is True and event.get('deleted') is False and event.get('forced') is False,'branch_creation_only')
    need(event.get('before')=='0'*40,'not_initial_branch_push')
    need(event.get('after')==environment.get('GITHUB_SHA')==relation['execution_commit'],'event_target_commit')
    need(re.fullmatch(r'[0-9a-f]{40}',value['control_commit']) is not None,'once_control_commit')
    need(relation['parents']==[value['control_commit']],'manifest_commit_single_parent')
    need(relation['changed_paths']==[APPROVAL_PATH] and relation['changed_status']==['A'],'manifest_only_child_commit')
    need(value['source_commit']==SOURCE and value['source_tree']==SOURCE_TREE,'once_source')
    canonical=lambda v:json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False)
    need(canonical(value['command_spec'])==canonical(command_spec()) and canonical(value['budgets'])==canonical(budget_spec()),'once_command_or_budget')
    need(value['retention_mode']=='four_closed_streams_CMS_AES256GCM_RSA_OAEP_SHA256','unimplemented_retention_mode')
    need(value['recipient_certificate_sha256']==RECIPIENT_PEM and value['recipient_spki_sha256']==RECIPIENT_SPKI,'recipient_changed')
    for key in ('controller_sha256','workflow_sha256','escrow_tool_sha256'):
        need(re.fullmatch(r'[0-9a-f]{64}',value[key]) is not None,'once_hash')
    return True

def registration_proof(root, environment):
    def git(*args):return subprocess.check_output(['git',*args],cwd=root)
    need(git('status','--porcelain','--untracked-files=all')==b'','registration_dirty')
    fields=git('rev-list','--parents','-n','1','HEAD').decode().strip().split()
    need(len(fields)==2,'registration_parent_count')
    execution,parent=fields
    changes=[line.split('\t',1) for line in git('diff','--name-status',parent,execution).decode().splitlines()]
    need(all(len(row)==2 for row in changes),'registration_change_shape')
    relation={'execution_commit':execution,'parents':[parent],
        'changed_status':[row[0] for row in changes],'changed_paths':[row[1] for row in changes]}
    manifest_path=root/APPROVAL_PATH;value=read_json(manifest_path,16384)
    event=read_json(Path(environment['GITHUB_EVENT_PATH']))
    validate_once_manifest(value,environment,event,relation)
    controller=git('show',parent+':tools/independent_m0_controller.py')
    workflow=git('show',parent+':'+ONCE_WORKFLOW)
    need(sha256(controller).hexdigest()==value['controller_sha256'],'approved_control_blob')
    need(sha256(workflow).hexdigest()==value['workflow_sha256'],'approved_workflow_blob')
    need(sha256(git('show',parent+':tools/m0_stream_escrow.py')).hexdigest()==value['escrow_tool_sha256'],'approved_escrow_blob')
    need(sha256(git('show',parent+':config/m0-stream-recipient-public.pem')).hexdigest()==RECIPIENT_PEM,'approved_recipient_blob')
    approval={'operator_approval_id':value['registration_id'],'control_commit':parent,
        'controller_sha256':value['controller_sha256'],'workspace_boot_id':value['workspace_boot_id'],
        'workspace_hostname_sha256':value['workspace_hostname_sha256'],'workspace_recorded_at':value['workspace_recorded_at'],
        'source_commit':SOURCE}
    return approval,{'registration_commit':execution,'manifest_sha256':digest(manifest_path),
        'manifest_parent_commit':parent,'manifest_only_child':True,'branch':APPROVED_BRANCH,
        'authorization_source':'explicit root-reviewed push of this manifest-only child; checksums alone do not grant permission'}


def source_snapshot(source):
    def git(*args):return subprocess.check_output(['git',*args],cwd=source)
    need(git('rev-parse','HEAD').decode().strip()==SOURCE,'source_head')
    need(git('rev-parse','HEAD^{tree}').decode().strip()==SOURCE_TREE,'source_tree')
    need(git('status','--porcelain','--untracked-files=all')==b'','source_dirty')
    manifest={}
    for row in git('ls-tree','-rz','--full-tree',SOURCE).split(b'\0'):
        if not row:continue
        header,name=row.split(b'\t',1);mode,kind,oid=header.split();name=name.decode()
        need(kind==b'blob' and mode in {b'100644',b'100755'},'source_entry_kind')
        path=source/name;info=path.lstat();need(stat.S_ISREG(info.st_mode),'source_regular')
        data=path.read_bytes()
        need(sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()==oid.decode(),'source_git_blob')
        manifest[name]={'bytes':len(data),'sha256':sha256(data).hexdigest()}
    need(len(manifest)==TRACKED,'source_file_count')
    return manifest

def load_owned_runner(source):
    path=source/'tools/run_managed_variants.py'
    spec=importlib.util.spec_from_file_location('frozen_independent_owned_runner',path)
    module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module
    spec.loader.exec_module(module)
    return module

def collect_host(private, environment):
    cpu_models=[]
    for line in Path('/proc/cpuinfo').read_text().splitlines():
        if line.startswith('model name'):
            model=line.split(':',1)[1].strip()
            if model not in cpu_models:cpu_models.append(model)
    fs=subprocess.check_output(['findmnt','-n','-o','FSTYPE','--target',str(private)],text=True,timeout=3).strip()
    need(fs and '\n' not in fs,'filesystem_metadata')
    disk=os.statvfs(private)
    cg={}
    for name in ('cpu.max','memory.max','pids.max'):
        path=Path('/sys/fs/cgroup')/name
        cg[name]=path.read_text().strip() if path.exists() else None
    return {'observed_at':datetime.now(timezone.utc).isoformat(),'boot_id':Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
        'hostname_sha256':sha256(socket.gethostname().encode()).hexdigest(),'os_release':Path('/etc/os-release').read_text(),
        'platform':platform.platform(),'python':sys.version,'python_executable_sha256':digest(Path(sys.executable).resolve()),
        'cpu_models':cpu_models,'cpu_count':os.cpu_count(),'cpu_affinity':sorted(os.sched_getaffinity(0)),
        'compiler_version_first_line':subprocess.check_output(['cc','--version'],text=True,timeout=3).splitlines()[0],
        'cgroup_limits':cg,'rlimits':{name:list(resource.getrlimit(getattr(resource,name))) for name in ('RLIMIT_NOFILE','RLIMIT_NPROC','RLIMIT_AS','RLIMIT_CPU','RLIMIT_FSIZE')},
        'filesystem_type':fs,'filesystem_device':os.stat(private).st_dev,'filesystem_free_bytes_kind':'statvfs_f_bavail_times_frsize_not_thin_storage_guarantee',
        'free_bytes':disk.f_bavail*disk.f_frsize,'network_interfaces':sorted(p.name for p in Path('/sys/class/net').iterdir()),
        'network_external_exchange_configured':False,'network_sandbox_enforced':False,
        'workload_transport':'local SDK/file inbox/owned multiprocessing pipes; no REST/TLS/exchange',
        'replication':False,'provider_context':{key:environment.get(key) for key in ('RUNNER_ENVIRONMENT','RUNNER_OS','RUNNER_ARCH','GITHUB_RUN_ID','GITHUB_RUN_ATTEMPT','GITHUB_SHA','GITHUB_EVENT_NAME')}}

@contextmanager
def child_environment(tmp):
    original=dict(os.environ)
    allowed={name:original[name] for name in ('PATH','LANG','LC_ALL','LD_LIBRARY_PATH') if name in original}
    allowed.update(PYTHONDONTWRITEBYTECODE='1',TMPDIR=str(tmp))
    os.environ.clear();os.environ.update(allowed)
    try:yield
    finally:os.environ.clear();os.environ.update(original)

def child_argv(source, output, profile):
    argv=[sys.executable,str(source/'benchmarks/run_managed_benchmark.py'),'--output',str(output),
        '--duration','10','--rate','20','--accounts','100','--shards','2','--cpu-limit','1',
        '--durable-batches','--financial-batch-size','0','--normal-cache-size','0']
    if profile:argv.append('--profile')
    return argv

def numeric_tree(value, depth=0):
    need(depth<=8,'numeric_tree_depth')
    if value is None or type(value) is bool:return value
    if type(value) in (int,float):return numeric(value)
    need(type(value) is dict and len(value)<=100,'numeric_tree_shape')
    result={}
    for key,item in value.items():
        need(type(key) is str and re.fullmatch(r'[A-Za-z0-9_.:-]{1,100}',key) is not None,'numeric_key')
        result[key]=numeric_tree(item,depth+1)
    return result

def project_summary(summary, profile):
    expected={'duration':10,'rate':20,'accounts':100,'shards':2,'normal_cache_size':0,'financial_batch_size':0,'durable_batches':True,'profile':profile}
    for key,value in expected.items():
        need(type(summary['configuration'][key]) is type(value) or type(value) is int and type(summary['configuration'][key]) is float,'configuration_type')
        need(summary['configuration'][key]==value,'configuration_changed')
    need(integer(summary['offered'],200,200)==200,'offered_count')
    outcomes=summary['outcome_counts'];need(set(outcomes)<=OUTCOMES,'unknown_outcome_name')
    need(sum(integer(v,0,200) for v in outcomes.values())==200,'outcomes_not_partition')
    technical=summary['command_technical_diagnostics']
    for key in ('internal_execution_attempts','commands_with_internal_attempts','commands_with_last_error','quarantined_commands','nonterminal_commands','control_commands_not_succeeded'):
        need(type(technical[key]) is int and technical[key]==0,'technical_diagnostic')
    batches=summary['batch_dispatch_diagnostics']
    for key in ('failure_events','unresolved_batches','recovered_batches'):
        need(type(batches[key]) is int and batches[key]==0,'batch_diagnostic')
    need(summary['poll_errors']==[],'poll_error')
    gate=summary['probe_qualification']
    need(gate['passed'] is True and gate['financial_soft_deadline_passed'] is True,'probe_gate')
    check=summary['readonly_reconciliation']
    need(check['reopened_readonly'] is True and integer(check['pending_count'])==0 and integer(check['unobserved_successes_found_on_reopen'])==0,'reconciliation')
    count=summary['counts'];need(set(count)<=OUTCOMES|{'durably_enqueued','enqueue_technical_errors','financial_success_late'},'counts_key')
    need(all(type(v) is int and 0<=v<=200 for v in count.values()),'counts_value')
    need(all(count.get(key,0)==outcomes.get(key,0) for key in OUTCOMES),'summary_outcome_counts_disagree')
    need(all(count.get(key,0)==0 for key in OUTCOMES-{'financial_succeeded','business_rejected','control_or_market_rejected'}),'technical_outcome')
    need(count.get('enqueue_technical_errors',0)==count.get('financial_success_late',0)==0,'technical_or_late_count')
    need(integer(count.get('financial_succeeded',0),0,200)>=100,'financial_success_floor')
    need(10<=integer(count.get('business_rejected',0),0,200)<=30,'business_rejection_mix')
    need(summary['environment']['code_commit']==SOURCE and summary['environment']['working_tree_dirty'] is False,'recorded_source')
    need(integer(summary['environment']['cpu_affinity_count'],1,1)==1,'recorded_affinity')
    need(integer(check['observed_financial_successes'])==integer(check['persistent_successes'])==count['financial_succeeded'],'reopened_success_count')
    need(integer(check['durable_enqueue_acknowledgements_verified'])==count['durably_enqueued'],'reopened_ack_count')
    runtime=summary['actual_runtime'];need(runtime['durable_batches_capability'] is True and runtime['decision_audit_required'] is True,'actual_runtime_capability')
    settings=runtime['router_settings']
    for key,value in {'normal_cache_size':0,'financial_batch_size':0,'account_batch':25,'matches_per_symbol':10,'max_attempts':3,'lease_seconds':5,'poll_interval':.02,'background_interval':.1}.items():
        need(settings[key]==value and type(settings[key]) is not bool,'actual_runtime_setting')
    workers=summary['actual_spawned_worker_inputs'];need(type(workers) is list and len(workers)==2,'actual_worker_count')
    need(len({integer(w['pid'],1) for w in workers})==2,'actual_worker_identity')
    canonical=lambda value:json.dumps(value,sort_keys=True,allow_nan=False)
    need(all(w['pid']!=os.getpid() and canonical(w['received_settings'])==canonical(settings) for w in workers),'actual_worker_settings')
    latency=summary['latency_ms']
    need(set(latency)=={'all','financial_succeeded','enqueue_ack'},'latency_classes')
    need(all(set(v)=={'p50','p95','p99','p99_9'} for v in latency.values()),'latency_keys')
    for group,quantiles in latency.items():
        values=[quantiles[key] for key in ('p50','p95','p99','p99_9')]
        population=200 if group=='all' else count['financial_succeeded'] if group=='financial_succeeded' else count['durably_enqueued']
        if population:
            values=[nonnegative(value) for value in values]
            need(values==sorted(values),'quantile_order')
        else:need(values==[None]*4,'empty_quantiles')
    elapsed=nonnegative(summary['duration_including_terminal_observation_drain'])
    need(elapsed>=10,'elapsed_below_planned_window')
    close_number(summary['drain_seconds'],max(0,elapsed-10),'drain_time_identity')
    nonnegative(summary['startup_seconds_excluded']);nonnegative(summary['close_seconds_excluded'])
    close_number(summary['unique_observed_financial_success_per_s'],count['financial_succeeded']/elapsed,'financial_rate_identity')
    close_number(summary['enqueue_ack_per_s_not_financial_success'],count['durably_enqueued']/elapsed,'enqueue_rate_identity')
    # Explicit projection: no error text, requests, accounts, payload, writer token,
    # key, nonce, signature, profile secrets or raw stream copies are published.
    return {'source_commit':SOURCE,'configuration':expected,'offered':200,'outcome_counts':numeric_tree(outcomes),
        'counts':numeric_tree(count),'latency_ms':numeric_tree(summary['latency_ms']),
        'duration_including_terminal_observation_drain':numeric(summary['duration_including_terminal_observation_drain']),
        'drain_seconds':numeric(summary['drain_seconds']),'close_seconds_excluded':numeric(summary['close_seconds_excluded']),
        'startup_seconds_excluded':numeric(summary['startup_seconds_excluded']),
        'unique_observed_financial_success_per_s':numeric(summary['unique_observed_financial_success_per_s']),
        'enqueue_ack_per_s_not_financial_success':numeric(summary['enqueue_ack_per_s_not_financial_success']),
        'actual_router_settings':numeric_tree(settings),'actual_worker_pids':[w['pid'] for w in workers],
        'probe_gate_passed':True,'read_only_reconciled':True,'confirmed_fills':0,'all_successful_orders_open':True,
        'profile_is_instrumented':profile,'speedup_comparison_authorized':False,'production_approved':False,'capacity_10000_per_s_passed':False}

def project_arrivals(path):
    rows=[];unpacked=0
    # Bound decompressed allocation before JSON decoding, including concatenated
    # gzip members. Never allocate the whole compressed or unpacked stream.
    with gzip.open(path,'rb') as stream:
      while True:
        remaining=8*1024**2-unpacked
        line=stream.readline(min(65537,remaining+1))
        if not line:break
        unpacked+=len(line)
        need(unpacked<=8*1024**2,'arrival_unpacked_cap')
        need(len(rows)<200 and len(line)<=65536,'arrival_count_or_line_cap')
        row=strict_json(line);sequence=integer(row['sequence'],0,199)
        need(row['command_id']==f'bench:{sequence}' and row['order_id']==f'order:{sequence}','synthetic_cid')
        need(row['outcome'] in OUTCOMES,'arrival_outcome')
        safe={'sequence':sequence,'command_id':row['command_id'],'outcome':row['outcome']}
        for key in ('planned_ns','offered_ns','enqueue_started_ns','enqueue_ack_ns','enqueue_call_finished_ns','observed_completion_ns','latency_ns'):
            safe[key]=None if row[key] is None else integer(row[key])
        planned=safe['planned_ns'];offered=safe['offered_ns'];finished=safe['observed_completion_ns']
        need(planned is not None and offered is not None and finished is not None and planned<=offered<=finished,'arrival_clock_order')
        need(safe['latency_ns']==finished-planned,'latency_time_identity')
        start=safe['enqueue_started_ns'];ack=safe['enqueue_ack_ns'];call=safe['enqueue_call_finished_ns']
        if start is not None:need(offered<=start<=finished and call is not None and start<=call<=finished,'enqueue_clock_order')
        else:need(ack is None and call is None,'enqueue_without_start')
        if ack is not None:need(start is not None and start<=ack<=call,'ack_clock_order')
        need(type(row['deadline_exceeded']) is bool and type(row['intended_product_rejection']) is bool,'arrival_boolean')
        safe.update(deadline_exceeded=row['deadline_exceeded'],intended_product_rejection=row['intended_product_rejection'])
        need(row['deadline_exceeded'] is (safe['latency_ns']>1_000_000_000),'deadline_time_identity')
        receipt=row.get('receipt')
        if receipt is not None:
            need(receipt['command_id']==row['command_id'],'receipt_original_cid')
            need(receipt['state'] in {'SUCCEEDED','REJECTED','QUARANTINED','PENDING'},'receipt_state')
            safe.update(receipt_state=receipt['state'],receipt_attempts=integer(receipt['attempts']),receipt_last_error_present=receipt['last_error'] is not None)
        outcome=row['outcome']
        if outcome in {'financial_succeeded','business_rejected','control_or_market_rejected'}:
            need(receipt is not None and ack is not None,'terminal_receipt_missing')
            need(receipt['state']==('SUCCEEDED' if outcome=='financial_succeeded' else 'REJECTED'),'receipt_outcome_identity')
            need(safe['receipt_attempts']==0 and receipt['last_error'] is None,'receipt_technical_diagnostic')
            if outcome=='financial_succeeded':
                need('error' in receipt and receipt['error'] is None,'success_receipt_error')
            else:
                error=receipt.get('error')
                if type(error) is str:
                    try:error=strict_json(error)
                    except (ValueError,TypeError):raise GateError('rejection_error_json') from None
                need(type(error) is dict and set(error)=={'status','code','message'},'rejection_error_shape')
                status=integer(error['status'],100,599)
                need(type(error['code']) is str and 0<len(error['code'])<=256 and type(error['message']) is str and len(error['message'])<=65536,'rejection_error_fields')
                need((status<500) is (outcome=='business_rejected'),'receipt_rejection_classification')
                safe['receipt_error_status']=status
        rows.append(safe)
    need(len(rows)==200 and {r['sequence'] for r in rows}==set(range(200)),'missing_arrivals')
    return rows

def verify_population(summary, rows):
    """Join complete projected populations; histogram output is a bucket bound.

    Source909 ceil(log1p(ns)/log1p(.001)) has <=0.1% bucket inflation
    plus rounding. Permit two nanoseconds and floating roundoff, not arbitrary
    ordered summary values. Rates use the source's float elapsed denominator.
    """
    need(len(rows)==summary['offered']==200,'population_size')
    counts=Counter(row['outcome'] for row in rows)
    need(all(counts[key]==summary['outcome_counts'].get(key,0)==summary['counts'].get(key,0) for key in OUTCOMES),'cross_file_outcomes')
    ack=sum(row['enqueue_ack_ns'] is not None for row in rows)
    late=sum(row['outcome']=='financial_succeeded' and row['deadline_exceeded'] for row in rows)
    need(ack==summary['counts']['durably_enqueued'] and late==summary['counts'].get('financial_success_late',0),'cross_file_ack_or_late')
    by_sequence=sorted(rows,key=lambda row:row['sequence'])
    origin=by_sequence[0]['planned_ns']
    need(all(row['planned_ns']==origin+row['sequence']*50_000_000 for row in rows),'planned_open_loop_schedule')
    populations={'all':[r['latency_ns'] for r in rows],
        'financial_succeeded':[r['latency_ns'] for r in rows if r['outcome']=='financial_succeeded'],
        'enqueue_ack':[r['enqueue_ack_ns']-r['planned_ns'] for r in rows if r['enqueue_ack_ns'] is not None]}
    for group,values in populations.items():
        values.sort()
        for key,numerator,denominator in [('p50',1,2),('p95',95,100),('p99',99,100),('p99_9',999,1000)]:
            reported=summary['latency_ms'][group][key]
            if not values:need(reported is None,'empty_population_quantile');continue
            rank=max(1,(len(values)*numerator+denominator-1)//denominator)
            exact_ns=values[rank-1];reported_ns=numeric(reported)*1e6
            need(exact_ns-1e-6<=reported_ns<=exact_ns*1.001+2+1e-6,'quantile_bucket_population_bound')
    return True

def verify_timing_footer(summary, rows, footer):
    need(type(footer['timing_contract_version']) is int and footer['timing_contract_version']==1,'timing_contract_version')
    start=integer(footer['started_monotonic_ns']);settled=integer(footer['terminal_observation_finished_monotonic_ns'])
    need(integer(footer['planned_duration_ns'])==10_000_000_000 and footer['setup_and_close_excluded'] is True,'timing_footer_scope')
    need(start==min(row['planned_ns'] for row in rows) and max(row['observed_completion_ns'] for row in rows)<=settled,'footer_clock_population')
    close_number(summary['duration_including_terminal_observation_drain'],max(10,(settled-start)/1e9),'footer_elapsed_identity')
    return True

def profile_semantic(path, source_root=None):
    need(path.stat().st_size<=4*1024**2,'profile_binary_cap')
    with path.open('rb') as stream:
        data=marshal.load(stream);need(stream.read(1)==b'','profile_trailing_bytes')
    need(type(data) is dict and len(data)<=10000,'profile_record_shape')
    result=[];caller_total=0
    allowed_roots=[Path(sys.base_prefix).resolve()]
    if source_root is not None:allowed_roots.append(Path(source_root).resolve())
    def label(key):
        need(type(key) is tuple and len(key)==3,'profile_function_key')
        file,line,name=key
        need(type(file) is str and len(file)<=1024 and '\0' not in file and type(name) is str and len(name)<=256 and '\0' not in name,'profile_label')
        synthetic_file=file=='<string>' or re.fullmatch(r'<frozen [A-Za-z0-9_.]+>',file) is not None
        if file!='~' and not synthetic_file:
            resolved=Path(file).resolve()
            need(any(resolved==root or root in resolved.parents for root in allowed_roots),'profile_private_filename')
        need(re.fullmatch(r'''[A-Za-z0-9_<> .:'"()+-]{1,256}''',name) is not None,'profile_function_label')
        return [file,integer(line),name]
    for key,value in data.items():
        need(type(value) is tuple and len(value)==5,'profile_value')
        primitive,calls,own,cumulative,callers=value
        need(type(callers) is dict and len(callers)<=10000,'profile_callers')
        caller_total+=len(callers);need(caller_total<=50000,'profile_total_callers_cap')
        safe_callers=[]
        for caller,counter in callers.items():
            need(type(counter) is tuple and len(counter)==4,'profile_caller_counter')
            safe_callers.append([label(caller),integer(counter[0]),integer(counter[1]),float(numeric(counter[2])).hex(),float(numeric(counter[3])).hex()])
        result.append({'function':label(key),'primitive_calls':integer(primitive),'calls':integer(calls),
            'internal_seconds_hex':float(numeric(own)).hex(),'cumulative_seconds_hex':float(numeric(cumulative)).hex(),
            'callers':safe_callers,'internal_exceeds_cumulative':own>cumulative})
    return {'format':'complete_cprofile_function_and_caller_counters_no_arguments','raw_binary_bytes':path.stat().st_size,
        'raw_binary_sha256':digest(path),'raw_binary_uploaded':False,'rows':result,
        'overlapping_times_are_not_cpu_percentages':True,'parent_mixed_thread_profile_may_be_anomalous':True}

def verify_public(root):
    need(root.is_absolute() and root.is_dir() and not root.is_symlink(),'public_directory')
    manifest=read_json(root/'manifest.json')
    need(manifest['source_commit']==SOURCE and manifest['private_authorities_requests_keys_nonces_signatures_streams_not_uploaded'] is True,'public_manifest_scope')
    records=manifest['files'];need(type(records) is list and len(records)<=100,'public_file_count')
    names=[]
    for item in records:
        need(set(item)=={'name','bytes','sha256'},'public_manifest_fields')
        name=item['name']
        safe_json=re.fullmatch(r'(case-[BP]-safe/)?[a-zA-Z0-9][a-zA-Z0-9_.-]{0,145}\.json',name)
        safe_cipher=re.fullmatch(r'escrow-[BP]-safe/(driver|case-owner)\.(stdout|stderr)\.cms',name)
        need(safe_json is not None or safe_cipher is not None,'public_filename')
        path=root/name;info=path.lstat()
        need(not path.parent.is_symlink(),'public_parent_symlink')
        need(stat.S_ISREG(info.st_mode) and info.st_size==item['bytes'] and digest(path)==item['sha256'],'public_manifest_mismatch')
        if Path(name).name.startswith('resource-diagnostic-'):
            value=read_json(path,4096);validate_resource_diagnostic(value)
            need(name==f"resource-diagnostic-{value['phase']}.json",'diagnostic_public_name')
        if safe_cipher is not None:
            spec=importlib.util.spec_from_file_location('m0_public_cipher_protocol',Path(__file__).resolve().with_name('m0_stream_escrow.py'))
            module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
            try:module.validate_cms_protocol(path)
            except module.EscrowError:raise GateError('public_cipher_protocol') from None
        names.append(name)
    actual=set()
    for path in root.rglob('*'):
        info=path.lstat()
        need(not stat.S_ISLNK(info.st_mode) and (stat.S_ISREG(info.st_mode) or stat.S_ISDIR(info.st_mode)),'public_special_entry')
        if path.is_dir():need(path.parent==root and path.name in {'case-B-safe','case-P-safe','escrow-B-safe','escrow-P-safe'},'public_directory_shape')
        else:actual.add(path.relative_to(root).as_posix())
    need(len(names)==len(set(names)) and actual==set(names)|{'manifest.json'},'unlisted_public_file')
    return True


def cases_sequence(run_case):
    results=[]
    for name,profile in [('B',False),('P',True)]:
        value=run_case(name,profile)
        results.append(value)
        if value['status']!='PASS':break
    return results

def case_driver(command, source, case):
    """Inherited session is essential: outer watchdog owns every descendant.

    Direct-child wait/terminate/kill never targets a numeric PID learned from a
    file. The outer frozen pidfd owner retains the session leader until cleanup.
    Stream growth is observed by the outer health gate, not an OS disk quota.
    """
    with (case/'driver.stdout').open('xb') as stdout,(case/'driver.stderr').open('xb') as stderr:
        with child_environment(case/'tmp'):
            process=subprocess.Popen(command,cwd=source,stdout=stdout,stderr=stderr,start_new_session=False)
        fields=Path(f'/proc/{process.pid}/stat').read_text().rsplit(')',1)[1].split()
        identity={'pid':process.pid,'birth_ticks':integer(int(fields[19]),1),
            'process_group':int(fields[2]),'session':int(fields[3])}
        need(identity['session']==identity['process_group']==os.getsid(0),'driver_inherited_owned_session')
        try:
            code=process.wait(timeout=50)
        except BaseException:
            process.terminate()
            try:process.wait(timeout=2)
            except subprocess.TimeoutExpired:process.kill();process.wait(timeout=2)
            raise
        need(code==0,'driver_exit_unknown')
    return identity

def case_pipeline(source, case, staged, name, profile, snapshot, cpu_ids):
    """Every potentially expensive case operation executes under outer owner."""
    need(source_snapshot(source)==snapshot,'source_changed_before_case')
    command=child_argv(source,case/'workload',profile)
    driver=case_driver(command,source,case)
    need((case/'driver.stderr').stat().st_size==0,'unclassified_stderr')
    safe=project_summary(read_json(case/'workload/summary.json'),profile)
    arrivals=project_arrivals(case/'workload/arrivals.jsonl.gz')
    verify_population(safe,arrivals)
    verify_timing_footer(safe,arrivals,read_json(case/'workload/measurement-footer.json',4096))
    need(source_snapshot(source)==snapshot,'source_changed_after_case')
    records=[public_write(staged,f'case-{name}.json',safe),public_write(staged,f'arrivals-{name}.json',arrivals)]
    paths=sorted((case/'workload/profiles').glob('*.prof'))
    need(len(paths)==(3 if profile else 0),'actual_profile_file_count')
    if profile:
        need(sum(p.name=='dispatcher-0.prof' for p in paths)==1 and {int(p.name.split('-')[1]) for p in paths if p.name.startswith('worker-')}=={0,1},'profile_pid_topology')
    for path in paths:
        need(re.fullmatch(r'(worker-[0-9]+-pid-[0-9]+|dispatcher-[0-9]+)\.prof',path.name) is not None,'profile_filename')
        records.append(public_write(staged,f'{name}-{path.stem}.json',profile_semantic(path,source)))
    need(tree_bytes(case,sqlite_aux_role='private_case')<=CASE_CAP and tree_bytes(staged)<=CASE_CAP,'case_output_cap')
    # All output bytes, hashes and fsyncs precede this completion record. Staged
    # partial files stay private after UNKNOWN and cannot enter upload manifests.
    return {'case':name,'status':'PASS','profile':profile,'source_commit':SOURCE,
        'actual_driver_pid':driver['pid'],'driver_birth_ticks':driver['birth_ticks'],
        'driver_session':driver['session'],'actual_cpu_ids':cpu_ids,'original_child_argv':command,
        'private_driver_streams':[{'name':p.name,'bytes':p.stat().st_size,'sha256':digest(p)} for p in (case/'driver.stdout',case/'driver.stderr')],
        'files':records,'private_originals_uploaded':False,'production_approved':False,
        'private_raw_retention':'private runner lifetime only; provider teardown is not durable escrow'}

def case_worker(descriptor):
    """Internal child capability: only the approved still-live parent creates it.

    This local mode is not an independent approval interface. Same-user code
    replacement is outside the authority model, exactly as for the root manifest.
    No provider tokens or original requests are passed to the new session.
    """
    descriptor=descriptor.resolve();info=descriptor.lstat()
    need(stat.S_ISREG(info.st_mode) and info.st_uid==os.getuid() and stat.S_IMODE(info.st_mode)==0o600,'case_descriptor_owner')
    value=read_json(descriptor,16384)
    expected={'source','private','public','case','profile','controller_sha256','source_snapshot_sha256',
        'control_commit','parent_pid','parent_birth_ticks','boot_id','hostname_sha256','cpu_ids'}
    need(set(value)==expected,'case_descriptor_fields')
    source=Path(value['source']);private=Path(value['private']);public=Path(value['public'])
    need(private.is_absolute() and public.is_absolute() and private.parent==public.parent==Path(os.environ['RUNNER_TEMP']),'case_runner_temp')
    name=value['case'];need((name,value['profile']) in [('B',False),('P',True)] and type(value['profile']) is bool,'case_fixed_arm')
    need(descriptor==private/f'context-{name}.json' and not private.is_symlink(),'case_descriptor_path')
    need(digest(Path(__file__).resolve())==value['controller_sha256'],'case_control_hash')
    root=Path(__file__).resolve().parents[1]
    need(subprocess.check_output(['git','rev-parse','HEAD'],cwd=root).decode().strip()==value['control_commit'],'case_control_commit')
    need(subprocess.check_output(['git','status','--porcelain','--untracked-files=all'],cwd=root)==b'','case_control_dirty')
    need(Path('/proc/sys/kernel/random/boot_id').read_text().strip()==value['boot_id'] and sha256(socket.gethostname().encode()).hexdigest()==value['hostname_sha256'],'case_host_changed')
    snapshot=source_snapshot(source)
    need(sha256(json.dumps(snapshot,sort_keys=True).encode()).hexdigest()==value['source_snapshot_sha256'],'case_source_snapshot')
    owned=load_owned_runner(source)
    parent=owned.process_identity(integer(value['parent_pid'],1))
    need(os.getppid()==parent['pid'] and parent['birth_ticks']==integer(value['parent_birth_ticks'],1) and parent['state'] not in ('Z','X'),'case_parent_identity')
    need(os.getsid(0)==os.getpgrp()==os.getpid(),'case_owned_session')
    need(type(value['cpu_ids']) is list and len(value['cpu_ids'])==1 and {integer(v) for v in value['cpu_ids']}==os.sched_getaffinity(0),'case_cpu')
    case=private/name;staged=case/'safe-staged'
    case.mkdir(mode=0o700);(case/'tmp').mkdir(mode=0o700);staged.mkdir(mode=0o700)
    result=case_pipeline(source,case,staged,name,value['profile'],snapshot,value['cpu_ids'])
    os.rename(staged,public/f'case-{name}-safe')
    public_write(case,'completed.json',result)
    print(json.dumps({'status':'CASE_STAGED','case':name}))
    return 0

def supervised_case(owned, source, private, public, name, profile, snapshot, approval, actual, cpu_ids, health):
    """Separate frozen owner watches worker, parser, hash and fsync as one case."""
    started=time.monotonic_ns()
    entry={'case':name,'profile':profile,'status':'UNKNOWN','source_commit':SOURCE,'production_approved':False}
    descriptor=private/f'context-{name}.json'
    value={'source':str(source),'private':str(private),'public':str(public),'case':name,'profile':profile,
        'controller_sha256':digest(Path(__file__).resolve()),'control_commit':approval['control_commit'],
        'source_snapshot_sha256':sha256(json.dumps(snapshot,sort_keys=True).encode()).hexdigest(),
        'parent_pid':os.getpid(),'parent_birth_ticks':owned.process_identity(os.getpid())['birth_ticks'],
        'boot_id':actual['boot_id'],'hostname_sha256':actual['hostname_sha256'],'cpu_ids':cpu_ids}
    public_write(private,descriptor.name,value)
    case=private/name
    try:
        # Only RUNNER_TEMP survives in addition to the ordinary clean child env.
        runner_temp=os.environ['RUNNER_TEMP']
        with child_environment(private):
            os.environ['RUNNER_TEMP']=runner_temp
            observed=owned.owned_run([sys.executable,str(Path(__file__).resolve()),'--execute','--case-worker',str(descriptor)],
                source,private/f'case-owner-{name}',cpu_ids=cpu_ids,wall_seconds=56,grace_seconds=2,kill_wait_seconds=2,
                output_cap=65536,protected={os.getpid(),os.getppid()},health_check=lambda:health(case))
        entry['owner_cleanup']={key:observed[key] for key in ('outcome','returncode','watchdog_reason','leader_reaped','stdout_stderr_complete')}
        entry['pipeline_owner_pid']=observed['identity']['pid']
        entry['pipeline_owner_birth_ticks']=observed['identity']['birth_ticks']
        need(observed['outcome']=='EXITED' and observed['returncode']==0 and observed['stdout_stderr_complete'] is True,'whole_case_unknown')
        need((private/f'case-owner-{name}.stderr').stat().st_size==0,'unclassified_case_worker_stderr')
        completed=read_json(case/'completed.json',65536)
        need(completed['case']==name and completed['profile'] is profile and completed['status']=='PASS','case_completion_identity')
        elapsed=time.monotonic_ns()-started
        need(elapsed<=60*10**9,'case_complete_outer_deadline')
        # Worker has completed publication under its independent owner. Only a
        # bounded completion descriptor is collected here, never original data.
        entry.update({key:value for key,value in completed.items() if key!='files'})
        entry.update(complete_outer_monotonic_ns=time.monotonic_ns()-started,
            files=[dict(item,name=f'case-{name}-safe/'+item['name']) for item in completed['files']])
        need(entry['complete_outer_monotonic_ns']<=60*10**9,'case_complete_outer_deadline')
    except BaseException as error:
        entry.update(status='UNKNOWN',error_type=type(error).__name__,error_code=str(error) if isinstance(error,GateError) else 'unclassified_private_failure',complete_outer_monotonic_ns=time.monotonic_ns()-started,private_originals_uploaded=False)
        # Do not publish a partially committed/late case. Retain its original
        # safe staged bytes privately, without deleting or reclassifying them.
        if (public/f'case-{name}-safe').exists():
            os.rename(public/f'case-{name}-safe',case/'safe-quarantined')
        entry.pop('files',None)
    return entry

def escrow_closed_case(owned,source,private,public,name,entry,approval,cpu_ids,health):
    result={'case':name,'status':'UNKNOWN','files':[],'four_closed_streams_retained':False,
        'recipient_spki_sha256':RECIPIENT_SPKI,'all_transitive_native_streams_claimed':False,
        'origin_authenticated_by_recipient_encryption':False}
    try:
        proof=entry.get('owner_cleanup',{})
        need(proof.get('leader_reaped') is True,'closed_case_producers_unproven')
        usage=resource_health_check(private,public,f'ESCROW_{name}',lambda:resource_usage(private,public))
        capture={name:True for name in ('driver.stdout','driver.stderr')}
        capture.update({name:proof.get('stdout_stderr_complete') is True for name in ('case-owner.stdout','case-owner.stderr')})
        value={'format':1,'case':name,'private':str(private),'public':str(public),'control_commit':approval['control_commit'],
            'controller_sha256':digest(Path(__file__).resolve()),'run_id':os.environ['GITHUB_RUN_ID'],'run_attempt':os.environ['GITHUB_RUN_ATTEMPT'],
            'parent_pid':os.getpid(),'parent_birth_ticks':owned.process_identity(os.getpid())['birth_ticks'],
            'closed_producers':True,'capture_complete':capture,'aggregate_existing_bytes':usage['escrow'],'aggregate_cap':ESCROW_CAP,'cleanup_cap':CLEANUP_RESERVE}
        descriptor=private/f'escrow-context-{name}.json';public_write(private,descriptor.name,value)
        runner_temp=os.environ['RUNNER_TEMP'];tool=Path(__file__).resolve().parent/'m0_stream_escrow.py'
        with child_environment(private):
            os.environ['RUNNER_TEMP']=runner_temp
            observed=owned.owned_run([sys.executable,str(tool),'--encrypt-case',str(descriptor)],source,
                private/f'escrow-owner-{name}',cpu_ids=cpu_ids,wall_seconds=20,grace_seconds=2,kill_wait_seconds=2,
                output_cap=65536,protected={os.getpid(),os.getppid()},health_check=health)
        result['owner_cleanup']={key:observed[key] for key in ('outcome','returncode','watchdog_reason','leader_reaped','stdout_stderr_complete')}
        # UNKNOWN/timeout may still have completed earlier exact streams. Collect
        # only journaled+atomically published ciphertext, preserving first error.
        completed=read_json(private/f'escrow-completed-{name}.json',65536)
        need(completed['case']==name and type(completed['files']) is list and len(completed['files'])<=4,'escrow_completion_shape')
        names=set()
        for item in completed['files']:
            need(set(item)=={'name','bytes','sha256','recipient_spki_sha256','algorithm','origin_authenticated_by_recipient_encryption'},'escrow_cipher_record')
            need(re.fullmatch(r'(driver|case-owner)\.(stdout|stderr)\.cms',item['name']) is not None and item['name'] not in names,'escrow_stream_name')
            names.add(item['name']);integer(item['bytes'],1,CASE_CAP+65536)
            need(re.fullmatch(r'[0-9a-f]{64}',item['sha256']) is not None and item['recipient_spki_sha256']==RECIPIENT_SPKI,'escrow_cipher_identity')
            if (public/f'escrow-{name}-safe'/item['name']).is_file():
                result['files'].append({'name':f'escrow-{name}-safe/'+item['name'],'bytes':item['bytes'],'sha256':item['sha256']})
        result['failures']=completed['failures']
        resource_usage(private,public)
        need(observed['outcome']=='EXITED' and observed['returncode']==0 and observed['stdout_stderr_complete'] is True and observed['leader_reaped'] is True,'escrow_owner_unknown')
        need(completed['status']=='PASS' and completed['failures']==[] and len(result['files'])==4,'escrow_incomplete')
        result.update(status='PASS',four_closed_streams_retained=True)
    except BaseException as error:
        result.update(error_type=type(error).__name__,error_code=str(error) if isinstance(error,GateError) else 'unclassified_private_escrow_failure')
    return result

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute',action='store_true')
    parser.add_argument('--case-worker',type=Path,help=argparse.SUPPRESS)
    parser.add_argument('--verify-public',type=Path)
    parser.add_argument('--registration-root',type=Path)
    parser.add_argument('--source',type=Path)
    parser.add_argument('--private',type=Path)
    parser.add_argument('--public',type=Path)
    args=parser.parse_args(argv)
    if args.case_worker is not None:
        need(args.execute and args.verify_public is None and args.registration_root is None and args.source is None and args.private is None and args.public is None,'case_worker_mode')
        return case_worker(args.case_worker)
    if args.verify_public is not None:
        need(not args.execute,'mutually_exclusive_modes')
        verify_public(args.verify_public)
        print(json.dumps({'status':'PUBLIC_ALLOWLIST_VERIFIED'}));return 0
    if not args.execute:
        print(json.dumps({'status':'PREP_ONLY','source_commit':SOURCE,'minimum_fresh_free_bytes':MIN_FREE,'cases':['B','P'],'profile_is_not_speedup_arm':True,'execution_authorized':False}))
        return 0
    registration=None
    if args.registration_root is not None:
        approval,registration=registration_proof(args.registration_root,dict(os.environ))
    else:
        approval_raw=os.environ['M0_APPROVAL_JSON'];need(len(approval_raw)<=4096,'approval_size')
        approval=strict_json(approval_raw)
    need(args.source and args.private and args.public,'execute_paths_required')
    for path in (args.private,args.public):
        need(path.is_absolute() and not path.exists() and path.parent.is_dir(),'exclusive_output_path')
        need(path.parent.resolve()==Path(os.environ['RUNNER_TEMP']).resolve(),'runner_temp_only')
    args.private.mkdir(mode=0o700);args.public.mkdir(mode=0o700)
    records=[];stage='source_preflight';result={'status':'UNKNOWN','source_commit':SOURCE,'cases':[],'production_approved':False,'capacity_10000_per_s_passed':False}
    try:
        snapshot=source_snapshot(args.source)
        control_root=Path(__file__).resolve().parents[1]
        need(subprocess.check_output(['git','rev-parse','HEAD'],cwd=control_root).decode().strip()==approval['control_commit'],'actual_control_checkout_commit')
        need(subprocess.check_output(['git','status','--porcelain','--untracked-files=all'],cwd=control_root)==b'','control_dirty')
        control=Path(__file__).resolve();control_sha=digest(control)
        actual=collect_host(args.private,dict(os.environ))
        if registration is None:
            validate_dispatch(approval,dict(os.environ),actual,control_sha)
        else:
            validate_environment(approval,dict(os.environ),actual,control_sha,event='push',event_commit=registration['registration_commit'])
        records.append(public_write(args.public,'host.json',actual))
        records.append(public_write(args.public,'source-manifest.json',{'source_commit':SOURCE,'source_tree':SOURCE_TREE,'files':snapshot}))
        records.append(public_write(args.public,'control.json',{'control_commit':approval['control_commit'],'controller_sha256':control_sha,'operator_approval_id':approval['operator_approval_id'],'source_commit':SOURCE,'workspace_boot_id':approval['workspace_boot_id'],'workspace_hostname_sha256':approval['workspace_hostname_sha256'],'workspace_recorded_at':approval['workspace_recorded_at'],'source_qualification_evidence_commits':EVIDENCE_COMMITS,'qualification_is_prior_root_attestation_not_reexecuted_here':True,'process_topology':'one supervisor -> owned case-worker -> one driver -> two spawn owners/native; one allowed CPU; separate sequential postcase escrow owner','registration':registration,'budget_spec':budget_spec(),'escrow_tool_sha256':digest(Path(__file__).resolve().with_name('m0_stream_escrow.py'))}))
        owned=load_owned_runner(args.source);cpus=[min(actual['cpu_affinity'])]
        health_phase={'value':'PREFLIGHT'};diagnostic_statuses={}
        def health_conditions(case_root=None):
            need(Path('/proc/sys/kernel/random/boot_id').read_text().strip()==actual['boot_id'],'runner_boot_changed')
            need(sha256(socket.gethostname().encode()).hexdigest()==actual['hostname_sha256'],'runner_host_changed')
            need(set(cpus)<=os.sched_getaffinity(0),'runner_cpu_unavailable')
            free=os.statvfs(args.private);need(free.f_bavail*free.f_frsize>=MIN_FREE,'fresh_space')
            resource_usage(args.private,args.public)
            if case_root:need(case_bytes(args.private,args.public,case_root.name)<=CASE_CAP,'case_output_cap')
        def health(case_root=None):
            return resource_health_check(args.private,args.public,health_phase['value'],lambda:health_conditions(case_root),diagnostic_statuses)
        # Before any financial driver, prove this runner's actual OpenSSL and
        # fixed public recipient support the exact authenticated protocol.
        stage='crypto_capability_probe';crypto_logs=args.private/'crypto-capability'
        health_phase['value']='CRYPTO_CAPABILITY'
        runner_temp=os.environ['RUNNER_TEMP']
        with child_environment(args.private):
            os.environ['RUNNER_TEMP']=runner_temp
            capability=owned.owned_run([sys.executable,str(Path(__file__).resolve().with_name('m0_stream_escrow.py')),
                '--check-public-recipient',str(args.private/'synthetic-crypto-probe')],args.source,crypto_logs,
                cpu_ids=cpus,wall_seconds=10,grace_seconds=2,kill_wait_seconds=2,output_cap=65536,
                protected={os.getpid(),os.getppid()},health_check=health)
        need(capability['outcome']=='EXITED' and capability['returncode']==0 and capability['stdout_stderr_complete'] is True,'crypto_capability_unknown')
        need((args.private/'crypto-capability.stderr').stat().st_size==0,'crypto_capability_stderr')
        crypto=read_json(args.private/'crypto-capability.stdout',65536)
        need(crypto['status']=='PUBLIC_RECIPIENT_CAPABILITY_VERIFIED' and crypto['public_spki_der_sha256']==RECIPIENT_SPKI,'crypto_capability_identity')
        records.append(public_write(args.public,'crypto-capability.json',crypto))
        # Actual WAL/FULL and SQLite compile metadata are collected in an owned
        # isolated child only after execute approval; no product module is used.
        stage='runtime_probe';probe=args.private/'runtime-probe';probe.mkdir(mode=0o700)
        health_phase['value']='RUNTIME_PROBE'
        code="import json,sqlite3,sys; c=sqlite3.connect(sys.argv[1],isolation_level=None,timeout=2); mode=c.execute('PRAGMA journal_mode=WAL').fetchone()[0]; c.execute('PRAGMA synchronous=FULL'); sync=c.execute('PRAGMA synchronous').fetchone()[0]; options=[r[0] for r in c.execute('PRAGMA compile_options')]; c.close(); print(json.dumps({'python':sys.version,'sqlite':sqlite3.sqlite_version,'journal_mode':mode,'synchronous':sync,'compile_options':options,'replication':False}))"
        with child_environment(probe):
            observed=owned.owned_run([sys.executable,'-I','-c',code,str(probe/'private.sqlite3')],args.source,probe/'probe',cpu_ids=cpus,wall_seconds=10,grace_seconds=2,kill_wait_seconds=2,output_cap=65536,protected={os.getpid(),os.getppid()},health_check=health)
        need(observed['outcome']=='EXITED' and observed['returncode']==0,'runtime_probe_unknown')
        runtime=read_json(probe/'probe.stdout',65536)
        need(runtime['journal_mode']=='wal' and runtime['synchronous']==2 and runtime['replication'] is False,'wal_full_required')
        records.append(public_write(args.public,'runtime.json',runtime))
        def run_case(name,profile):
            health_phase['value']=f'CASE_{name}'
            entry=supervised_case(owned,args.source,args.private,args.public,name,profile,snapshot,approval,actual,cpus,health)
            records.extend(entry.pop('files',[]))
            health_phase['value']=f'ESCROW_{name}'
            escrow=escrow_closed_case(owned,args.source,args.private,args.public,name,entry,approval,cpus,health)
            records.extend(escrow.pop('files',[]))
            records.append(public_write(args.public,f'escrow-{name}.json',escrow))
            entry['stream_escrow']=escrow
            if escrow['status']!='PASS':entry.update(case_execution_status=entry['status'],status='UNKNOWN',stop_reason='stream_escrow_not_complete')
            return entry
        stage='cases';result['cases']=cases_sequence(run_case)
        result['status']='PASS_COMPONENT_DIAGNOSTIC_ONLY' if len(result['cases'])==2 and all(c['status']=='PASS' for c in result['cases']) else 'UNKNOWN_OR_NO_GO'
        # Final source replay is global verification, outside each completed
        # case's explicitly reported endpoint, within the job timeout.
        need(source_snapshot(args.source)==snapshot,'source_changed_at_end')
        if len(result['cases'])==1:
            result['cases'].append({'case':'P','profile':True,'status':'NOT_RUN','reason':'first_case_not_passed','production_approved':False})
    except BaseException as error:
        result.update(status='UNKNOWN_OR_NO_GO',stage=stage,error_type=type(error).__name__,error_code=str(error) if isinstance(error,GateError) else 'unclassified_private_failure')
    result.update(no_external_exchange=True,no_network_sandbox_claim=True,private_originals_uploaded=False,
        profile_binary_uploaded=False,private_raw_retention='four closed driver/case-owner streams as authenticated CMS ciphertext; subject to explicit per-case escrow result and provider artifact retention',
        speedup_claim=False,ha_approved=False)
    result['resource_diagnostic_status']={phase:status for phase,status in locals().get('diagnostic_statuses',{}).items()}
    # Diagnostics are their own typed records. Original four stream files and
    # ordering are untouched. Unknown/invalid diagnostic data blocks publication.
    result['resource_diagnostic_collection']=collect_resource_diagnostics(args.public,records)
    records.append(public_write(args.public,'result.json',result))
    public_write(args.public,'manifest.json',{'files':records,'private_authorities_requests_keys_nonces_signatures_streams_not_uploaded':True,'source_commit':SOURCE})
    print(json.dumps({'status':result['status'],'source_commit':SOURCE,'public_records':len(records),'production_approved':False}))
    return 0 if result['status']=='PASS_COMPONENT_DIAGNOSTIC_ONLY' else 1

if __name__=='__main__':
    try:
        code=main()
    except Exception as error:
        print(json.dumps({'status':'UNKNOWN_OR_NO_GO','error_type':type(error).__name__,'error_code':str(error) if isinstance(error,GateError) else 'unclassified_private_failure','production_approved':False}))
        code=1
    raise SystemExit(code)
