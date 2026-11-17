"""Pure independent malformed-result and outcome controls; no native or SQL."""
from copy import deepcopy
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess

os.sched_setaffinity(0,{3})
ROOT=Path(__file__).resolve().parents[3]
CANDIDATE='7ce60c197a79f25dac887f352d35749386b812f9'
PATH='evidence/runs/recovery-horizon91/strict_result_contract.py'
raw=subprocess.check_output(['git','show',CANDIDATE+':'+PATH],cwd=ROOT)
assert sha256(raw).hexdigest()=='dbd32f4db11bb6449f63839e46595f574065b03026386dc362bc63f518a05c71'
space={};exec(compile(raw,PATH,'exec'),space)
validate=space['validate_worker_result']
base={'base_source':'91e4ae40b5e9b884c54026406299df5000c9c100','test_source_sha256':'389ab057ab0e12fc0eb73d9f990a084c82565e2cb76dd0e8ac8c2fe8325309f6','tests_run':1,'failures':0,'errors':0,'skipped':0,'expected_failures':0,'unexpected_successes':0,'case_passed':True,'was_successful':True,'test_failure_observed':False,'historical_original_assertion_reproduced':False,'worker_observation_complete':True,'production_approved':False,'outcome_stage':'PASS','logger_failures':[],'evidence_flags':{'both_observers_joined':True,'fixture_forced_cleanup':False,'fixture_cleanup_error':False,'observer_failures':[],'sampling_failures':[],'logger_failures':[],'observer_post_join':{name:{'is_alive':False,'lifecycle':{'started':True,'ended':True,'error':None}} for name in ('pidfd','code_stack')}}}
results=[]
def check(name,mutate,valid,safe):
 value=deepcopy(base);mutate(value);actual=validate(value)
 assert actual['valid'] is valid and actual['safe_to_continue'] is safe,(name,actual)
 results.append({'name':name,'valid':actual['valid'],'safe_to_continue':actual['safe_to_continue'],'errors':actual['errors']})
check('literal valid one-case PASS',lambda v:None,True,True)
def ordinary(v):v.update(failures=1,case_passed=False,was_successful=False,test_failure_observed=True,outcome_stage='OTHER_ASSERTION_FAILURE')
check('ordinary assertion fail retained and safe to continue',ordinary,True,True)
def historical(v):ordinary(v);v.update(historical_original_assertion_reproduced=True,outcome_stage='ORIGINAL_PID_EXIT_ASSERTION')
check('historical assertion fail retained and safe to continue',historical,True,True)
def unittest_error(v):v.update(errors=1,case_passed=False,was_successful=False,test_failure_observed=True,outcome_stage='UNITTEST_ERROR')
check('UNITTEST_ERROR valid record but technical stop',unittest_error,True,False)
check('original malformed four-field combination',lambda v:v.update(worker_observation_complete='false',errors=False,tests_run=0,failures=-1,case_passed='false'),False,False)
check('boolean error zero',lambda v:v.update(errors=False),False,False)
check('floating error zero',lambda v:v.update(errors=0.0),False,False)
check('string completion flag',lambda v:v.update(worker_observation_complete='false'),False,False)
for field in ('tests_run','failures','errors','skipped','expected_failures','unexpected_successes'):
 check('boolean count '+field,lambda v,f=field:v.update({f:False}),False,False)
check('no case executed',lambda v:v.update(tests_run=0),False,False)
check('skip is not a completed original case',lambda v:v.update(skipped=1),False,False)
check('missing mandatory field',lambda v:v.pop('was_successful'),False,False)
check('outcome flag does not match counts',lambda v:v.update(case_passed=False),False,False)
check('historical flag impossible for PASS',lambda v:v.update(historical_original_assertion_reproduced=True),False,False)
check('two terminal outcomes for one case',lambda v:v.update(failures=1,errors=1),False,False)
check('production approval forbidden',lambda v:v.update(production_approved=True),False,False)
check('source mismatch',lambda v:v.update(base_source='0'*40),False,False)
check('observer aggregate forged true',lambda v:v['evidence_flags']['observer_post_join']['pidfd'].update(is_alive=True),False,False)
check('observer lifecycle string is not boolean',lambda v:v['evidence_flags']['observer_post_join']['pidfd']['lifecycle'].update(ended='true'),False,False)
check('missing observer record',lambda v:v['evidence_flags']['observer_post_join'].pop('pidfd'),False,False)
def forced(v):v['evidence_flags']['fixture_forced_cleanup']=True;v['worker_observation_complete']=False
check('forced cleanup true is technical stop',forced,True,False)
print(json.dumps({'candidate':CANDIDATE,'contract_sha256':sha256(raw).hexdigest(),'pure_controls':results,'all_controls_passed':True,'ordinary_FAIL_continues_only_with_complete_technical_record':True,'original_four_red_gate_vectors_closed_for_this_validator':True,'does_not_validate_unwritten_controller_or_actual_runtime':True,'native_or_SQL_run':False,'production_approved':False},indent=2))
