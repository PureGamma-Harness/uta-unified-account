"""Six exact retained controller fake tests; not a native pilot invocation."""
import argparse
from hashlib import sha256
from importlib.machinery import ModuleSpec
from importlib.util import module_from_spec,spec_from_file_location
import json
from pathlib import Path
import stat
import sys
from types import ModuleType

ROOT=Path(__file__).resolve().parents[1]
METHODS=(
 'NativeHostGuardContracts.test_protected_ids_reject_before_any_proc_path',
 'NativeHostGuardContracts.test_same_numeric_pid_cannot_alias_different_birth_or_nonce',
 'NativeHostGuardContracts.test_ack_prerequisites_are_typed_true_and_gates_closed',
 'NativeControllerDeltaContracts.test_001_unverified_candidate_is_closed_never_adopted_or_signalled',
 'NativeControllerDeltaContracts.test_002_slow_setup_or_stop_record_cannot_spawn_or_signal_past_deadline',
 'NativeControllerDeltaContracts.test_003_broken_gate_close_is_sticky_but_all_owned_resources_continue')


def pins(path,approved):
    raw=Path(path).read_bytes()
    if sha256(raw).hexdigest()!=approved:raise ValueError('guards6 binding changed')
    manifest=json.loads(raw);observed={}
    for name,expected in manifest['inputs'].items():
        source=ROOT/name;details=source.lstat()
        if not stat.S_ISREG(details.st_mode) or source.resolve()!=source:raise ValueError('nonregular guard source')
        raw=source.read_bytes();value={'bytes':len(raw),'sha256':sha256(raw).hexdigest()}
        if value!=expected:raise ValueError('guards6 source differs: '+name)
        observed[name]=value
    return observed


def load(name,filename):
    if name in sys.modules:raise ValueError('retained module collision: '+name)
    spec=spec_from_file_location(name,ROOT/'benchmarks'/filename)
    module=module_from_spec(spec);sys.modules[name]=module
    # Execute exactly the pinned source bytes, never an unbound .pyc cache.
    code=compile((ROOT/'benchmarks'/filename).read_bytes(),str(ROOT/'benchmarks'/filename),'exec',dont_inherit=True)
    exec(code,module.__dict__)
    return module


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--scope',choices=('guards6',),required=True)
    parser.add_argument('--binding',required=True);parser.add_argument('--approved-binding-sha256',required=True)
    parser.add_argument('methods',nargs='+');args=parser.parse_args()
    if args.methods!=list(METHODS):raise ValueError('only fixed6 method IDs in frozen order; no discovery')
    if not(sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode):raise ValueError('-I -S -B required')
    before=pins(args.binding,args.approved_binding_sha256)
    if 'benchmarks' in sys.modules:raise ValueError('unknown benchmark namespace already loaded')
    package=ModuleType('benchmarks');package.__package__='benchmarks';package.__path__=[]
    package.__spec__=ModuleSpec('benchmarks',loader=None,is_package=True);package.__spec__.submodule_search_locations=[]
    sys.modules['benchmarks']=package
    control=load('benchmarks._guards6_lookup_guard','native_guards6_lookup_guard.py')
    guard=control.LookupGuard();sys.addaudithook(guard.audit)
    # Real stdlib imports, with source-only reviewed startup. They may create
    # in-memory MainProcess/locks and register atexit; they do not spawn owners.
    import unittest
    import unittest.mock
    import multiprocessing
    import multiprocessing.connection as connection
    import signal
    import socket
    import subprocess
    import threading
    real_connection=connection.Connection
    try:guard.install_apis()
    except BaseException:
        guard.restore();raise
    result=None;success=[];failures=[]
    retained={}
    try:
        for short,filename in [('cross_open_loop_checks','cross_open_loop_checks.py'),
                               ('cross_pilot_native_host','cross_pilot_native_host.py'),
                               ('pilot_owned_workers','pilot_owned_workers.py')]:
            module=load('benchmarks.'+short,filename);retained[short]=module;setattr(package,short,module)
        test=load('benchmarks._guards6_fixed_tests','test_cross_native_host_guards.py')
        host,adapter=retained['cross_pilot_native_host'],retained['pilot_owned_workers']
        real_owned_type=adapter.OwnedWorkers;real_owned_close=adapter.OwnedWorkers.close
        original_functions={(short,name):getattr(retained[short],name) for short,names in {
            'cross_pilot_native_host':('identity','registered_birth_matches','adopt_verified_child','signal_owned_before_deadline','close_stdin_no_flush','cleanup_call'),
            'pilot_owned_workers':('guarded_popen','signal_owned_before_deadline','private_json','close_stdin_no_flush')}.items() for name in names}
        def intact():
            import os
            if sys.modules.get('benchmarks') is not package or package.__path__!=[]:raise ValueError('retained package changed')
            allowed={'benchmarks',control.__name__,test.__name__}|{m.__name__ for m in retained.values()}
            if {n for n in sys.modules if n=='benchmarks' or n.startswith('benchmarks.')}!=allowed:raise ValueError('unbound benchmark import')
            if (test.host is not host or test.adapter is not adapter or adapter.Connection is not real_connection
                or adapter.OwnedWorkers is not real_owned_type or adapter.OwnedWorkers.close is not real_owned_close):
                raise ValueError('test native stdlib/helper reference changed')
            if host.os is not os or adapter.os is not os or host.signal is not signal or adapter.signal is not signal or adapter.subprocess is not subprocess:
                raise ValueError('dangerous lookup module reference differs from fixture patch targets')
            if any(getattr(retained[s],n) is not original for (s,n),original in original_functions.items()):raise ValueError('controller helper identity changed')
            if not guard.identities_intact():raise ValueError('test left a dangerous lookup unguarded/unrestored')
        intact()
        class RecordedResult(unittest.TextTestResult):
            def addSuccess(self,case):super().addSuccess(case);success.append(case.id())
            def addFailure(self,case,error):super().addFailure(case,error);failures.append(case.id())
            def addError(self,case,error):super().addError(case,error);failures.append(case.id())
            def addSubTest(self,case,subtest,error):
                super().addSubTest(case,subtest,error)
                if error is not None:failures.append(subtest.id())
        cases=[]
        for identifier in METHODS:
            classname,method=identifier.split('.')
            kind=getattr(test,classname)
            if not isinstance(kind,type) or not issubclass(kind,unittest.TestCase):raise ValueError('fixed test class changed')
            cases.append(kind(method))
        expected=[case.id() for case in cases]
        result=unittest.TextTestRunner(verbosity=2,failfast=True,resultclass=RecordedResult).run(unittest.TestSuite(cases))
        intact();after=pins(args.binding,args.approved_binding_sha256)
        forbidden=sorted(n for n in sys.modules if n=='uta' or n.startswith('uta.') or n.split('.')[0] in ('sqlite3','_sqlite3'))
        counts={name:len(getattr(result,name)) for name in ('failures','errors','skipped','expectedFailures','unexpectedSuccesses')}
        registry=getattr(sys.modules.get('multiprocessing.process'),'_children',None)
        registry_empty=type(registry) is set and len(registry)==0
        passed=(before==after and result.testsRun==6 and result.wasSuccessful() and success==expected
                and not any(counts.values()) and not guard.attempts and not forbidden and registry_empty)
        print(json.dumps({'event':'FIXED_PURE_SCOPE_RESULT','scope':'guards6','methods':list(METHODS),'expected_IDs':expected,
            'actual_success_IDs':success,'actual_failure_IDs':failures,'tests_run':result.testsRun,'counts':counts,
            'source_pins_unchanged':before==after,'retained_helper_identity_unchanged':True,'forbidden_imports':forbidden,
            'unexpected_unmocked_operation_attempts':guard.attempts,'real_connection_class_retained':adapter.Connection is real_connection,
            'stdlib_modules_imported':[n for n in ('multiprocessing','multiprocessing.connection','subprocess','signal','socket','threading') if n in sys.modules],
            'stdlib_import_semantics':'real multiprocessing creates memory MainProcess/authkey and registers util atexit; these are not OS children/threads/Connections/semaphore resources',
            'in_memory_mp_child_registry_empty':registry_empty,'observation_limit':'finite source and lookup-guard proof; no kernel PID/process/thread enumeration or arbitrary-C sandbox claim',
            'passed':passed},sort_keys=True),flush=True)
        return 0 if passed else 1
    finally:
        guard.restore()  # No test/guard API replacement leaks into stdlib atexit.


if __name__=='__main__':raise SystemExit(main())
