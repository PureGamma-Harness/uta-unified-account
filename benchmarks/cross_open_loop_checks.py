"""Finite pilot link/time guards; pure inputs, no UTA or I/O authority."""
from fractions import Fraction as F
from hashlib import sha256
import json
import math

FEED_START_LATENESS_NS = 15_625_000
FEED_COMPLETE_LATENESS_NS = 31_250_000


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def verify_admission_link(arrival, command, order, decision, expected_reserve):
    """Link original signed terms to the actual row, stored receipt and audit.

    abs(quantity) or a matching aggregate reserve is never an identity proof.
    Audit-after contains the actual complete new live-order row in this slice.
    """
    require(type(order) is dict and type(decision) is dict, 'missing order/decision')
    payload, receipt = json.loads(command['payload']), json.loads(command['result'])
    expected = {key: arrival[key] for key in ('account_id','order_id','symbol','quantity','limit_price')}
    require(command['command_id'] == arrival['command_id'] and command['account_id'] == expected['account_id']
            and command['kind'] == 'SUBMIT_ORDER' and command['state'] == 'SUCCEEDED', 'CID/account/command linkage differs')
    require(set(payload) == set(expected) | {'reduce_only'} and type(payload['reduce_only']) is bool
            and payload['reduce_only'] is False, 'unknown payload or reduce-only differs')
    for name in ('account_id','order_id','symbol'):
        require(type(expected[name]) is str and payload[name] == order[name] == receipt[name] == expected[name],
                'original identity differs: '+name)
    for name in ('quantity','limit_price'):
        require(all(type(source[name]) is str for source in (expected,payload,order,receipt)), 'untyped financial term: '+name)
        require(F(payload[name]) == F(order[name]) == F(receipt[name]) == F(expected[name]), 'signed financial term differs: '+name)
    require(type(order['reduce_only']) is int and order['reduce_only'] == 0
            and type(receipt['reduce_only']) is bool and receipt['reduce_only'] is False, 'stored reduce-only differs')
    require(order['status'] == receipt['status'] == 'OPEN'
            and F(order['filled_quantity']) == F(receipt['filled_quantity']) == 0
            and F(order['fee_notional']) == F(order['charged_fee']) == 0, 'new live-order economic state differs')
    require(type(order['version']) is int and type(receipt['version']) is int and receipt['version'] == order['version']
            and receipt['created_at'] == order['created_at'], 'receipt order version/time differs')
    identity='decision:'+sha256(json.dumps(['ORDER_ACCEPTED',expected['account_id'],expected['order_id']],
                                          sort_keys=True,separators=(',',':')).encode()).hexdigest()
    require(receipt['decision_evidence'] == 'recorded' and order['admission_decision_id'] == receipt['decision_id'] == decision['decision_id'] == identity
            and decision['kind'] == 'ORDER_ACCEPTED' and decision['account_id'] == expected['account_id']
            and decision['business_id'] == expected['order_id'] and decision['post_version'] == order['version']
            and type(decision['pre_version']) is int and type(decision['post_version']) is int
            and 0 <= decision['pre_version'] < decision['post_version']
            and decision['post_version'] == decision['pre_version'] + 1, 'audit business identity/version differs')
    evidence, summary = json.loads(decision['input_payload']), json.loads(decision['summary_payload'])
    operation=evidence['operation']
    require(set(operation) == {'order_id','symbol','quantity','limit_price','reduce_only'}, 'unknown/missing admission operation field')
    require(operation['order_id'] == expected['order_id'] and operation['symbol'] == expected['symbol']
            and type(operation['reduce_only']) is bool and operation['reduce_only'] is False
            and all(type(operation[k]) is str and F(operation[k]) == F(expected[k]) for k in ('quantity','limit_price')),
            'archived operation signed economic terms differ')
    before, after = evidence['before'], evidence['after']
    require(before['version'] == decision['pre_version'] and after['version'] == decision['post_version'], 'audit snapshot versions differ')
    key=expected['account_id'],expected['order_id']
    require(not any((r['account_id'],r['order_id']) == key for r in before['orders']), 'order already in audit before-state')
    matching=[r for r in after['orders'] if (r['account_id'],r['order_id']) == key]
    require(len(matching) == 1 and json.dumps(matching[0],sort_keys=True,separators=(',',':')) == json.dumps(order,sort_keys=True,separators=(',',':')), 'full audit-after order row differs from actual row')
    require(F(receipt['reserved_margin']) == F(summary['reserved_margin']) == expected_reserve,
            'receipt/audit reserve differs from independent oracle')
    for field in ('risk_mode','rule_id','rule_version','catalog_version'):
        require(receipt[field] == summary['risk_after'][field], 'receipt/audit policy reference differs: '+field)
    require(summary['risk_before']['account_version'] == decision['pre_version']
            and summary['risk_after']['account_version'] == decision['post_version']
            and F(summary['risk_after']['open_order_margin'])-F(summary['risk_before']['open_order_margin']) == expected_reserve,
            'audit risk/reservation version delta differs')


def require_feed_timing(planned_ns, actual_ns, phase):
    require(type(planned_ns) is int and type(actual_ns) is int and planned_ns >= 0, 'feed timestamps must be integer ns')
    if phase in ('before_quote','before_publish'):
        limit=FEED_START_LATENESS_NS
    elif phase in ('after_publish','after_activation'):
        limit=FEED_COMPLETE_LATENESS_NS
    else:
        raise ValueError('unknown fixed feed timing phase')
    lateness=actual_ns-planned_ns
    require(0 <= lateness <= limit, 'fixed feed deadline exceeded: '+phase)
    return lateness


def require_gate_budget(now, startup_deadline, outer_deadline=None):
    """Immediately before EACH gate, reject equality and any expired known budget.

    Outer controller remains OPEN. If it later supplies a bound, it is checked
    as well; None is explicitly no outer attestation, never proof of headroom.
    """
    deadlines=[startup_deadline] + ([] if outer_deadline is None else [outer_deadline])
    require(type(now) in (int,float) and math.isfinite(now), 'invalid gate clock')
    require(all(type(d) in (int,float) and math.isfinite(d) for d in deadlines), 'invalid gate deadline')
    require(all(now < d for d in deadlines), 'gate budget exhausted; leave unreleased gate closed')
    return min(deadlines)-now
