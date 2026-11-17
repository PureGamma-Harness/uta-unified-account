from pathlib import Path
import json,sys,threading,time,unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT),str(ROOT/'tests')]
from uta.writer_fence import _TransactionGuard
from test_owned_startup_reference import OwnedStartupReferenceTests
original=_TransactionGuard.before_commit
observed=[]
def delayed(guard):
    if threading.current_thread().name.startswith('Thread'):
        before=time.monotonic_ns()
        threading.Event().wait(.2)
        observed.append({'thread':threading.current_thread().name,'actual_pause_ns':time.monotonic_ns()-before})
    return original(guard)
with patch.object(_TransactionGuard,'before_commit',delayed):
    suite=unittest.TestSuite([OwnedStartupReferenceTests('test_old_inflight_writer_is_drained_before_complete_ro_replay')])
    result=unittest.TextTestRunner(verbosity=2).run(suite)
print(json.dumps({'controlled_real_pause_seconds':.2,'observed':observed,'tests_run':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),'original_functions_called':True,'unique_historical_cause_proven':False}))
raise SystemExit(not result.wasSuccessful())
