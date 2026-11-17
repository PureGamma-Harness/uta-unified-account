"""Deterministic original-4608 test-contract failure; actual HTTP and COMMIT."""
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
import types

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
raw = subprocess.check_output(['git', 'show', '4608ffeda0651f8dafd2cd151618a71ed99aa62e:tests/test_gateway_grouped.py'], cwd=ROOT)
module = types.ModuleType('original_grouped_contract')
module.__file__ = str(ROOT / 'tests/test_gateway_grouped.py')
sys.modules[module.__name__] = module
exec(compile(raw, module.__file__, 'exec'), module.__dict__)
case = module.GroupedGatewayTests('test_real_submit_cancel_and_response_loss_retry_preserve_one_business_effect')
case.setUp()
replies, expected_failure = [], None
try:
    entered, release, hold = case.block_admission('order')
    original_request = case.request
    def observed(method, path, payload=None, *, token=module.ALICE):
        response = original_request(method, path, payload, token=token)
        replies.append(response)
        if response[0] == 503 and response[1].get('error', {}).get('code') == 'command_result_unknown':
            assert entered.is_set()
            release.set()
        return response
    case.request = observed
    with hold:
        try:
            case.test_real_submit_cancel_and_response_loss_retry_preserve_one_business_effect()
        except AssertionError as error:
            expected_failure = str(error)
    case.admission.close()
    orders = case.exchange.orders('alice')
    accepted = [event for event in case.exchange.events(limit=1000) if event['event_type'] == 'ORDER_ACCEPTED']
    assert expected_failure and '503 != 201' in expected_failure
    assert replies[0][0] == 503 and replies[0][1]['error']['code'] == 'command_result_unknown'
    assert len(orders) == len(accepted) == 1 and orders[0]['status'] == 'OPEN'
    print(json.dumps({'subject': '4608ffeda0651f8dafd2cd151618a71ed99aa62e',
          'original_test_sha256': sha256(raw).hexdigest(), 'admission_timeout_seconds': .05,
          'controlled_running_pause': True, 'response': replies[0],
          'original_assertion_failure': expected_failure, 'orders': orders,
          'accepted_events': len(accepted), 'test_contract_counterexample_observed': True,
          'original_CI_unique_cause_proven': False, 'production_approved': False}, indent=2))
finally:
    case.doCleanups()
