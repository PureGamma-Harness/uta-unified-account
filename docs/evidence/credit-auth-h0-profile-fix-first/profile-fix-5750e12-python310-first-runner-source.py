import sys,pathlib,json,unittest,os,sqlite3,platform
sys.path.insert(0,sys.argv[1]);sys.path.insert(0,str(pathlib.Path(sys.argv[1])/'tests'))
SAFE_CODES={'credit_auth_outcome_unknown','credit_auth_disabled','credit_auth_forbidden','credit_auth_input_invalid','credit_auth_handle_invalid','credit_auth_thread_mismatch','credit_auth_process_mismatch','credit_auth_handle_capacity','credit_auth_reservation_capacity','signing_capacity_exhausted','request_replayed','invalid_signature','idempotency_conflict','grant_identity_conflict','grant_revision_conflict','auth_clock_regressed'}
SAFE_TYPES={'AssertionError','ValueError','TypeError','CreditAuthError','SigningError','StorageError','OperationalError','DatabaseError','IntegrityError','ResourceWarning','OSError','RuntimeError','AttributeError','ImportError'}
class R(unittest.TextTestResult):
 def __init__(self,*args,**kw):super().__init__(*args,**kw);self.records=[]
 def addSuccess(self,t):super().addSuccess(t);self.records.append({'test_id':t.id(),'status':'PASS'})
 def addFailure(self,t,e):super().addFailure(t,e);self.record(t,e,'FAIL')
 def addError(self,t,e):super().addError(t,e);self.record(t,e,'ERROR')
 def record(self,t,e,status):
  typ=e[0].__name__;code=getattr(e[1],'code',None);sql=getattr(e[1],'sqlite_errorcode',None)
  self.records.append({'test_id':t.id(),'status':status,'exception_type':typ if typ in SAFE_TYPES else 'OTHER','error_code':code if code in SAFE_CODES else None,'sqlite_errorcode':sql if type(sql) is int and 0<=sql<=65535 else None})
names=sys.argv[3:] or ['test_credit_auth_h0.CreditAuthH0Tests']
suite=unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromName(n) for n in names)
result=unittest.TextTestRunner(verbosity=2,resultclass=R).run(suite)
report={'python':platform.python_version(),'sqlite':sqlite3.sqlite_version,'affinity':sorted(os.sched_getaffinity(0)),'tests_run':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),'skipped':len(result.skipped),'records':result.records,'passed':result.wasSuccessful(),'financial_database_opened':False,'scope':'H0 fresh private AuthDB only; not production'}
pathlib.Path(sys.argv[2]).write_text(json.dumps(report,indent=2)+'\n')
sys.exit(0 if result.wasSuccessful() else 1)
