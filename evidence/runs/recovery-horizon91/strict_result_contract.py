"""Pure validation of one original-case record. No process, SQL or file actions."""
BASE = '91e4ae40b5e9b884c54026406299df5000c9c100'
TEST_SHA = '389ab057ab0e12fc0eb73d9f990a084c82565e2cb76dd0e8ac8c2fe8325309f6'
ORIGINAL_ASSERTION = 'original bound PID did not exit within the unchanged five-second recovery horizon'


def validate_worker_result(value):
    errors = []
    if type(value) is not dict:
        return {'valid':False,'errors':['record must be a JSON object'],'safe_to_continue':False}
    bool_keys = ('case_passed','was_successful','test_failure_observed',
                 'historical_original_assertion_reproduced','worker_observation_complete',
                 'production_approved')
    count_keys = ('tests_run','failures','errors','skipped','expected_failures','unexpected_successes')
    for key in bool_keys:
        if type(value.get(key)) is not bool:
            errors.append(key+': exact bool required')
    for key in count_keys:
        if type(value.get(key)) is not int or value[key] not in (0,1):
            errors.append(key+': exact non-bool integer 0 or 1 required')
    if value.get('base_source') != BASE or value.get('test_source_sha256') != TEST_SHA:
        errors.append('original source or testcase identity mismatch')
    if type(value.get('logger_failures')) is not list:
        errors.append('logger_failures: exact list required')
    flags=value.get('evidence_flags')
    if type(flags) is not dict:
        errors.append('evidence_flags: exact object required')
    else:
        for key in ('both_observers_joined','fixture_forced_cleanup','fixture_cleanup_error'):
            if type(flags.get(key)) is not bool:
                errors.append('evidence_flags.'+key+': exact bool required')
        for key in ('observer_failures','sampling_failures','logger_failures'):
            if type(flags.get(key)) is not list:
                errors.append('evidence_flags.'+key+': exact list required')
        post=flags.get('observer_post_join')
        if type(post) is not dict or set(post) != {'pidfd','code_stack'}:
            errors.append('exactly two observer post-join records required')
        else:
            for name,state in post.items():
                if type(state) is not dict or type(state.get('is_alive')) is not bool:
                    errors.append(name+': exact post-join bool required');continue
                lifecycle=state.get('lifecycle')
                if type(lifecycle) is not dict or any(type(lifecycle.get(k)) is not bool for k in ('started','ended')) or 'error' not in lifecycle:
                    errors.append(name+': complete lifecycle required')
    stage=value.get('outcome_stage')
    if stage not in ('PASS','ORIGINAL_PID_EXIT_ASSERTION','OTHER_ASSERTION_FAILURE','UNITTEST_ERROR'):
        errors.append('outcome_stage: unknown or missing')
    if errors:
        return {'valid':False,'errors':errors,'safe_to_continue':False}
    if value['tests_run'] != 1 or any(value[k] != 0 for k in ('skipped','expected_failures','unexpected_successes')):
        errors.append('one actual unskipped case required')
    if value['failures']+value['errors']>1:
        errors.append('one case cannot have multiple terminal outcomes')
    passed=value['failures']==0 and value['errors']==0
    if value['case_passed'] is not passed or value['was_successful'] is not passed or value['test_failure_observed'] is not (not passed):
        errors.append('outcome booleans disagree with actual counts')
    historical=value['historical_original_assertion_reproduced']
    expected_stage=('PASS' if passed else 'UNITTEST_ERROR' if value['errors'] else
                    'ORIGINAL_PID_EXIT_ASSERTION' if historical else 'OTHER_ASSERTION_FAILURE')
    if stage != expected_stage or (historical and (value['failures']!=1 or value['errors']!=0)):
        errors.append('historical assertion flag/stage/count mismatch')
    if value['production_approved'] is not False:
        errors.append('diagnosis cannot grant production approval')
    joined=all(state['is_alive'] is False and state['lifecycle']['started'] is True
               and state['lifecycle']['ended'] is True and state['lifecycle']['error'] is None
               for state in flags['observer_post_join'].values())
    if flags['both_observers_joined'] is not joined:
        errors.append('observer aggregate disagrees with actual post-join records')
    if value['logger_failures'] != flags['logger_failures']:
        errors.append('logger flags disagree')
    complete=(joined and flags['observer_failures']==[] and flags['sampling_failures']==[]
              and flags['logger_failures']==[] and flags['fixture_forced_cleanup'] is False
              and flags['fixture_cleanup_error'] is False)
    if value['worker_observation_complete'] is not complete:
        errors.append('worker completeness aggregate disagrees with exact flags')
    return {'valid':not errors,'errors':errors,
            'safe_to_continue':not errors and complete and value['errors']==0,
            'original_case_passed':passed,'outcome_stage':stage}
