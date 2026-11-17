"""Independent JSON/gzip checks only. No financial module, SQLite or load imports."""
from __future__ import annotations
import ast
from collections import Counter
from copy import deepcopy
from fractions import Fraction
from hashlib import sha256
import gzip
import json
import math
from pathlib import Path
import sys

SOURCE = 'a35fd56fc98126b3e5cced8a459bd04ca580e537'
ROOT = Path(__file__).resolve().parents[3]
ARCHIVE = ROOT / 'docs/evidence/managed-variant-wiring-20261117'
QUANTILES = {'p50': Fraction(1,2), 'p95': Fraction(95,100), 'p99': Fraction(99,100), 'p99_9': Fraction(999,1000)}


def file_digest(path):
    return sha256(path.read_bytes()).hexdigest()


def manifest_check(directory, manifest):
    for name, proof in manifest['files'].items():
        assert not Path(name).is_absolute() and '..' not in Path(name).parts
        path=directory/name
        assert path.is_file(), name
        assert file_digest(path)==proof['sha256'], name
        if 'bytes' in proof: assert path.stat().st_size==proof['bytes'], name
    return len(manifest['files'])


def exact_quantile(values, fraction):
    if not values: return None
    rank=max(1,(len(values)*fraction.numerator+fraction.denominator-1)//fraction.denominator)
    return sorted(values)[rank-1]


def percentile_check(values, reported):
    result={}
    for name, fraction in QUANTILES.items():
        exact=exact_quantile(values, fraction)
        upper=reported[name]
        if exact is None:
            assert upper is None
        else:
            observed=Fraction(str(upper))*1_000_000
            assert exact<=observed, (name,exact,observed)
            # ceil(expm1(ceil(log1p(ns)/log(1.001))*log(1.001)))
            # can add one ns from the final integer ceil.
            assert observed <= Fraction(exact+1)*Fraction(1001,1000)+1
        result[name]={'exact_nanoseconds':exact,'reported_upper_bound_milliseconds':upper}
    return result


def composite_gate(summary):
    """Local diagnostic gate; never a production/capacity authorization."""
    gate=summary['probe_qualification']
    return gate['passed'] is True and gate['financial_soft_deadline_passed'] is True


def observed_technical_gate(summary):
    """Execute only the exact frozen pure gate AST, not its importing module."""
    module=ast.parse((ROOT/'benchmarks/run_managed_benchmark.py').read_text())
    node=next(n for n in module.body if isinstance(n,ast.FunctionDef) and n.name=='probe_qualification')
    namespace={}
    exec(compile(ast.Module(body=[node],type_ignores=[]),'<frozen pure gate>', 'exec'),namespace)
    return namespace['probe_qualification'](summary)


def recompute_case(directory):
    summary=json.loads((directory/'summary.json').read_text())
    window=json.loads((directory/'arrival-window.json').read_text())
    with gzip.open(directory/'arrivals.jsonl.gz','rt') as stream:
        rows=[json.loads(line) for line in stream]
    manifest_files=manifest_check(directory,json.loads((directory/'manifest.json').read_text()))
    config=summary['configuration']
    start=window['planned_start_monotonic_ns']
    offered=int(Fraction(str(config['duration']))*Fraction(str(config['rate'])))
    assert summary['offered']==window['offered']==len(rows)==offered==8
    assert {row['sequence'] for row in rows}==set(range(offered))
    assert len({row['command_id'] for row in rows})==offered
    assert len({row['order_id'] for row in rows})==offered
    outcomes=Counter()
    all_ns=[]; financial_ns=[]; ack_ns=[]
    late=0
    for row in rows:
        expected=start+int(Fraction(row['sequence']*10**9)/Fraction(str(config['rate'])))
        assert row['planned_ns']==expected
        assert row['offered_ns']>=expected
        assert row['enqueue_started_ns']>=row['offered_ns']
        assert row['enqueue_ack_ns']>=row['enqueue_started_ns']
        assert row['enqueue_call_finished_ns']>=row['enqueue_ack_ns']
        assert row['observed_completion_ns']>=row['enqueue_call_finished_ns']
        assert row['latency_ns']==row['observed_completion_ns']-row['planned_ns']
        is_late=row['latency_ns']>Fraction(str(config['timeout_ms']))*10**6
        assert row['deadline_exceeded'] is is_late
        outcomes[row['outcome']]+=1
        all_ns.append(row['latency_ns'])
        ack_ns.append(row['enqueue_ack_ns']-row['planned_ns'])
        if row['outcome']=='financial_succeeded':
            financial_ns.append(row['latency_ns']); late+=is_late
            receipt=row['receipt']; result=json.loads(receipt['result'])
            assert receipt['state']=='SUCCEEDED' and receipt['error'] is None
            assert receipt['command_id']==row['command_id'] and receipt['account_id']==row['account_id']
            assert receipt['attempts']==0 and receipt['last_error'] is None
            assert (result['status'],result['filled_quantity'])==('OPEN','0')
            assert Fraction(result['quantity'])==Fraction(1,1000)
            assert Fraction(result['reserved_margin'])==Fraction(251,25000)
    assert dict(outcomes)==summary['outcome_counts']=={'financial_succeeded':8}
    assert summary['counts']['financial_succeeded']==8
    assert summary['counts']['durably_enqueued']==len(ack_ns)==8
    assert summary['counts']['financial_success_late']==late==0
    elapsed=summary['duration_including_terminal_observation_drain']
    assert elapsed>=config['duration']
    assert Fraction(str(elapsed))*10**9 >= max(row['observed_completion_ns'] for row in rows)-start
    assert math.isclose(summary['drain_seconds'],max(0,elapsed-config['duration']),rel_tol=1e-12,abs_tol=1e-12)
    assert summary['unique_observed_financial_success_per_s']==8/elapsed
    assert summary['enqueue_ack_per_s_not_financial_success']==8/elapsed
    actual=summary['actual_runtime']
    assert actual['router_settings']['normal_cache_size']==config['normal_cache_size']
    assert actual['router_settings']['financial_batch_size']==config['financial_batch_size']
    assert actual['durable_batches_capability'] is config['durable_batches']
    assert actual['decision_audit_required'] is True
    assert actual['financial_batch_soft_budget_seconds']==.005
    assert actual['physical_commit_counts_measured'] is False
    workers=summary['actual_spawned_worker_inputs']
    assert len(workers)==1
    assert workers[0]['received_settings']==actual['router_settings']
    assert workers[0]['pid']==summary['initial_real_pid_and_fence']['workers'][0]['pid']
    environment=summary['environment']
    assert environment['generator_sha256']==file_digest(ROOT/'benchmarks/run_managed_benchmark.py')
    for name,digest in environment['source_sha256'].items():
        assert file_digest(ROOT/'uta'/name)==digest,name
    checks=summary['readonly_reconciliation']
    assert checks['reopened_readonly'] and checks['persistent_successes']==8
    assert checks['pending_count']==checks['unobserved_successes_found_on_reopen']==0
    assert all(shard['confirmed_matches']==0 and shard['durable_batches_capability'] is config['durable_batches'] for shard in checks['shards'])
    batch=summary['batch_dispatch_diagnostics']
    assert batch['unique_executed_commands']<=batch['executed_commands']<=batch['selected_commands']
    assert batch['unique_selected_commands']<=batch['selected_commands']
    assert batch['failure_events']==batch['unresolved_batches']==batch['recovered_batches']==0
    phases=summary['execution_classification']
    assert phases['batch_selected_memberships']==batch['selected_commands']
    assert phases['batch_executed_memberships_including_rejections']==batch['executed_commands']
    assert phases['physical_metadata_and_financial_commit_counts_measured'] is False
    assert composite_gate(summary)
    return {'case':str(directory.relative_to(ARCHIVE)), 'rows':len(rows),'manifest_files':manifest_files,
            'raw_sha256':file_digest(directory/'arrivals.jsonl.gz'),'summary_sha256':file_digest(directory/'summary.json'),
            'configured_rate_not_capacity':config['rate'],'arrival_window_seconds':config['duration'],
            'observed_receipt_denominator_seconds':elapsed,'financial_receipts':len(financial_ns),
            'recomputed_observed_receipt_per_second':len(financial_ns)/elapsed,
            'exact_and_reported_percentiles':{name:percentile_check(values,summary['latency_ms'][name]) for name,values in
                [('all',all_ns),('financial_succeeded',financial_ns),('enqueue_ack',ack_ns)]},
            'latency_group_counts':{'all':len(all_ns),'financial_succeeded':len(financial_ns),'enqueue_ack':len(ack_ns)},
            'exact_max_latency_nanoseconds':{'all':max(all_ns),'financial_succeeded':max(financial_ns),'enqueue_ack':max(ack_ns)},
            'same_factor_comparison':False,'performance_qualification':False,'database_reopened_by_this_check':False}


def main(output):
    outer=json.loads((ARCHIVE/'manifest.json').read_text())
    files=manifest_check(ARCHIVE,outer)
    plan=json.loads((ROOT/'benchmarks/plans/20261117-managed-variants.json').read_text())
    assert plan['execution_authorized'] is False and plan['frozen_commit'] is None
    baseline=plan['baseline']
    assert (baseline['durable_batches'],baseline['financial_batch_size'],baseline['normal_cache_size'])==(True,0,0)
    for variant in plan['variants']:
        assert variant['durable_batches'] is True
        assert sum(variant[key]!=baseline[key] for key in ('financial_batch_size','normal_cache_size'))==1
    cases=[recompute_case(p.parent) for p in sorted((ARCHIVE/'raw').rglob('summary.json'))]
    assert len(cases)==17 and sum(row['rows'] for row in cases)==136
    original=json.loads(next((ARCHIVE/'raw/py312').rglob('summary.json')).read_text())
    late=deepcopy(original); late['counts']['financial_success_late']=1
    late['probe_qualification']=observed_technical_gate(late)
    assert late['probe_qualification']['passed'] is True
    assert late['probe_qualification']['financial_soft_deadline_passed'] is False
    assert composite_gate(late) is False
    inputs=['benchmarks/plans/20261117-managed-variants.json','benchmarks/run_managed_benchmark.py','benchmarks/run_benchmark.py','benchmarks/run_group_benchmark.py','tests/test_managed_variant_wiring.py','tests/test_managed_retry_gate.py','uta/durable_batches.py','uta/durable_process.py']
    result={'source_commit':SOURCE,'review_inputs_sha256':{name:file_digest(ROOT/name) for name in inputs},'outer_manifest_files_checked':files,'raw_cases_checked':len(cases),
            'financial_receipt_rows_checked':sum(row['rows'] for row in cases), 'cases':cases,
            'counterfactual_only_not_a_new_load':{'change':'counts.financial_success_late=1',
                'current_technical_gate':late['probe_qualification'],'composite_diagnostic_gate':False,
                'existing_source_intent':'technical and latency gates are deliberately separate'},
            'blocks_go_without_execution_amendment':True,
            'review_requires':['check technical passed AND financial_soft_deadline_passed','report exact ranks/N/max from raw rows',
                'external bounded watchdog and owned-child cleanup','pin actual source and explicit allowed CPU set','do not infer capacity from offered20/s unsaturated runs'],
            'new_load_executed':False,'database_opened':False,'production_approved':False,'capacity_10000_per_s_passed':False}
    Path(output).write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ('source_commit','outer_manifest_files_checked','raw_cases_checked','financial_receipt_rows_checked','new_load_executed','database_opened','production_approved')}))

if __name__=='__main__':
    main(sys.argv[1])
