"""Independent retained-file verification: no product import, DB, SQL, or job execution.

Private raw is read only for hashes and allowlisted scalar/aggregate assertions;
only hashes and selected synthetic aggregate facts are emitted.
"""
import hashlib
import json
import math
from collections import Counter, defaultdict
from datetime import datetime, timezone
from fractions import Fraction
from pathlib import Path

PREP = Path('/workspace/uta-managed-909acec-prepare')
BASE = Path('/workspace/uta-managed-observer-runs')
CTRL = BASE / '909acec-smoke-20261117-02-controller-private'
ROOT = BASE / '909acec-smoke-20261117-02-root-private'
ARC = PREP / 'evidence/runs/managed-909acec-smoke-02'
V3 = PREP / 'evidence/preparations/managed-909acec-v3'
SOURCE = '909acecd153e2e89dfe2238e3ed3a3d9a3d3c9f0'
BOOT = '6339d4fc-a9e7-4c10-a591-1e70a14322ff'
PROFILE = '0d4beaafd20dcc1f3f4627db17ad3ea3ec72bb66377da0f7a9e69bfc1cc39850'
ENVELOPE = '17902f4669a81761354a68a7ea23be670b1e2547502c0d4a2eadd44d5cad79aa'
CONTROLLER = 'e88a575ef31f12d60f1c42bfdc86e003b013620488b5ac9b4685a1a1a5a445b3'
APPROVAL = 'a283afbed247cb86204773a5f72b139d16370bb8f3981289dc8fcfceb3e77356'
FIRST = 78289089259839
DEADLINE = FIRST + 150_000_000_000
checks = []
files = {}


def need(ok, label):
    if not ok:
        raise AssertionError(label)
    checks.append(label)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def raw(path):
    data = path.read_bytes()
    files[str(path)] = {'bytes': len(data), 'sha256': sha(data)}
    return data


def load(path):
    return json.loads(raw(path))


def integer(value):
    return type(value) is int


def no_claims(d, label):
    for k in ('production_approved', 'continuous_6h_stability_passed',
              'continuous_24h_stability_passed', 'capacity_10000_per_s_passed'):
        need(d.get(k) is False, label + ':' + k)


env = load(V3 / 'conditional-envelope.json')
need(sha(raw(V3 / 'conditional-envelope.json')) == ENVELOPE, 'exact_envelope')
need(sha(raw(V3 / 'smoke_controller_v3.py')) == CONTROLLER, 'exact_controller')
pf = Path(env['profile_file'])
need(sha(raw(pf)) == PROFILE, 'exact_profile')
p = load(pf)
need(env['source_commit'] == p['source_commit'] == SOURCE, 'exact_product_source')
need(env['maximum_producer_starts'] == 1 and env['outer_seconds'] == 150
     and env['no_long_scope'] is True, 'one_smoke_only_envelope')
approval = load(ROOT / 'root-approved-envelope.json')
need(sha(raw(ROOT / 'root-approved-envelope.json')) == APPROVAL, 'exact_root_approval')
need(approval['authorized'] is True and approval['source_commit'] == SOURCE
     and approval['envelope_sha256'] == ENVELOPE
     and approval['controller_sha256'] == CONTROLLER
     and approval['profile_sha256'] == PROFILE, 'root_exact_three_SHA_delegation')
need(approval['scope'] == 'EXACT_SEVEN_SMOKE_STAGES_ONCE_NO_LONG'
     and approval['maximum_producer_starts'] == 1, 'root_scope_not_blanket')
public_manifest = load(ARC / 'manifest.json')
for filename, spec in public_manifest['files'].items():
    content = raw(PREP / filename)
    need(len(content) == spec['bytes'] and sha(content) == spec['sha256'],
         'public_archive_manifest:' + Path(filename).name)
manifest = load(ARC / 'original-copy-manifest.json')
for item in manifest['public_original_metadata_copies']:
    original = raw(Path(item['original']))
    copied = raw(PREP / item['copy'])
    need(original == copied and len(copied) == item['bytes']
         and sha(copied) == item['sha256'], 'exact_public_copy:' + Path(item['copy']).name)
for item in manifest['private_raw_stream_manifest']:
    b = raw(Path(item['private_original']))
    need(len(b) == item['bytes'] and sha(b) == item['sha256']
         and item['complete'] is True and item['published_raw'] is False,
         'private_raw_retained:' + item['stage'] + ':' + item['stream'])
need(len(manifest['public_original_metadata_copies']) == 45
     and len(manifest['private_raw_stream_manifest']) == 16, '45_metadata_16_streams')

responses, receipts, identities, stage_facts = {}, {}, [], []
for entry in env['stages']:
    stage, phase, cmd = entry['stage'], entry['phase'], entry['argv']
    digest = sha(json.dumps(cmd, separators=(',', ':')).encode())
    need(digest == entry['command_sha256'] and cmd[cmd.index('--invoke')+1] == phase
         and cmd[cmd.index('--record')+1] == entry['record']
         and cmd[cmd.index('--profile')+1] == str(pf), stage + ':exact_enumerated_command')
    paths = list(CTRL.glob(stage + '-*-admission.json'))
    need(len(paths) == 1, stage + ':one_snapshot')
    a = load(paths[0]); gofile = paths[0].with_name(paths[0].name.replace('-admission', '-delegated-stageGO'))
    go = load(gofile); popen = load(CTRL / (stage + '-actual-Popen.json'))
    identity = popen['identity']; identities.append((identity['pid'], identity['birth'], stage))
    need(go['authorized'] is True and go['snapshot_sha256'] == sha(raw(paths[0]))
         and go['root_delegation_record_sha256'] == APPROVAL
         and go['root_approved_envelope_sha256'] == ENVELOPE
         and go['profile_sha256'] == PROFILE and go['command_sha256'] == digest
         and go['stage'] == stage and go['phase'] == phase, stage + ':delegated_GO_binding')
    need(a['profile_sha256'] == PROFILE and a['phase_command_sha256'] == digest
         and a['phase'] == phase and a['source_commit'] == SOURCE
         and a['source_boot'] == identity['boot'] == BOOT
         and a['status'] == 'ADMISSION_METADATA_COMPONENT_PASS_NOT_PHASE_GO', stage + ':snapshot_binding')
    cw, cb, vw, vb = (a[k] for k in ('captured_wall_ns', 'captured_boottime_ns',
                                      'valid_until_wall_ns', 'valid_until_boottime_ns'))
    nw, nb = identity['captured_wall_ns'], identity['captured_boottime_ns']
    po, lo, pm, lm = (a[k] for k in ('original_progress_observed_ns', 'original_latest_observed_ns',
                                      'original_progress_mtime_ns', 'original_latest_mtime_ns'))
    ph, lh = (Fraction(str(a[k])) for k in ('original_progress_heartbeat_age_seconds',
                                           'original_latest_heartbeat_age_seconds'))
    need(all(integer(v) and v > 0 for v in (cw, cb, vw, vb, nw, nb, po, lo, pm, lm))
         and cw <= nw < vw and cb <= nb < vb
         and 0 <= nw-cw <= 15*10**9 and 0 <= nb-cb <= 15*10**9,
         stage + ':both_clocks_unexpired_after_Popen')
    pa, la = Fraction(nw-po, 10**9), Fraction(nw-lo, 10**9)
    need(0 <= pa <= 15 and 0 <= la <= 30 and 0 <= ph+pa <= 15 and 0 <= lh+la <= 30
         and 0 <= nw-pm <= 15*10**9 and 0 <= nw-lm <= 30*10**9
         and abs(pm-po) <= 15*10**9 and abs(lm-lo) <= 15*10**9,
         stage + ':original_HB_mtime_recomputed_at_post_Popen')
    need(a['capture_started_wall_ns'] <= cw and all(x <= cw for x in (po,lo,pm,lm)), stage + ':capture_not_future_or_rolled_back')
    need(vb-cb == vw-cw and vw <= cw+15*10**9 and vw <= po+15*10**9
         and vw <= pm+15*10**9 and vw <= lm+30*10**9,
         stage + ':minimum_deadline_bounds')
    need(type(a['fresh_free_bytes']) is int and a['fresh_free_bytes'] >= 17_448_304_640
         and a['required_free_bytes'] == 17_448_304_640, stage + ':full_resource_floor')
    need(a['observer_source_commit'] == 'f96dfd8d6b1ca6f5ae28ac771c886baf4fdeb30e'
         and a['observer_script_sha256'] == '5329bcdb2668eda44635558f4153305306be608cb3803099c61e50dbc26e2efd'
         and a['observer_interval_seconds'] == 60
         and a['observer_default_post_write_software_threshold_bytes'] == 64*1024**2
         and a['observer_original_no_alerts'] is True
         and a['conditional_floor_is_hard_quota'] is False,
         stage + ':old_observer_conditional_policy')
    need(a['allowlisted_observer_cli'] == {'--interval':'60'}
         and a['producer_source_commit'] == '88755a9f2ba3bb672ca5d354b3037796f00c6611', stage + ':old_CLI_and_producer_binding')
    need(a['observer_current_logical_bytes'] + a['all_matching_external_staging_bytes']
         + a['projected_additional_6h_stress_assumption_bytes'] < 256*1024**2
         and a['total_metadata_entries_counted'] <= 20000, stage + ':bounded_metadata_contingency')
    for side in ('original_processes_before', 'original_processes_after'):
        need(all(a[side][str(pid)]['birth'] == birth and a[side][str(pid)]['state'] not in ('Z','X')
                 and a[side][str(pid)]['uids'] == [1000]*4
                 for pid, birth in ((4471, '210004'), (8784, '412799'))), stage + ':' + side)
    need(popen['first_Popen_boottime_ns'] == FIRST and popen['unchanged_controller_deadline_boottime_ns'] == DEADLINE
         and FIRST <= nb < DEADLINE, stage + ':fixed_original_150')
    streams = load(CTRL / (stage + '-raw-stream-manifest.json'))
    for stream in ('stdout', 'stderr'):
        b = raw(CTRL / (stage + '.' + stream)); m = streams[stream]
        need(m['complete'] is True and m['error'] is None and len(b) == m['bytes'] == m['retained_bytes']
             and len(b) <= 4*1024**2 and sha(b) == m['sha256'], stage + ':' + stream + ':complete_raw')
    need(raw(CTRL / (stage+'.stderr')) == b'', stage + ':empty_stderr')
    receipt = load(CTRL / (stage+'.stdout')); expected = 1 if stage == 'strict-negative' else 0
    need(type(receipt['exit_code']) is int and receipt['exit_code'] == expected
         and receipt['stdout_complete'] is True, stage + ':outer_receipt')
    body = receipt['structured_stdout']; no_claims(receipt, stage + ':outer')
    if stage != 'cold':
        need(type(body['exit_code']) is int and body['exit_code'] == expected
             and body['timed_out'] is False, stage + ':nested_receipt')
        response = body['response']
    else:
        need('timed_out' not in body and 'exit_code' not in body, 'cold_actual_direct_shape')
        response = body
    no_claims(body, stage + ':inner'); no_claims(response, stage + ':response')
    responses[stage], receipts[stage] = response, receipt
    stage_facts.append({'stage': stage, 'phase': phase, 'snapshot_sha256': sha(raw(paths[0])),
                        'command_sha256': digest, 'post_Popen_remaining_validity_ns': min(vw-nw, vb-nb),
                        'fresh_free_bytes': a['fresh_free_bytes'],
                        'margin_above_full_floor_bytes': a['fresh_free_bytes']-17_448_304_640})

need([e['stage'] for e in env['stages']] == ['produce','startup','normal-live','fault-live','final','cold','strict-negative'], 'seven_ordered_stages')
produce = responses['produce']
need(produce['status'] == 'completed' and produce['rounds'] == {'DONE':15}
     and produce['fault_signals'] == {'worker':3,'parent':1} and produce['unresolved_faults'] == 0
     and produce['unresolved_steps'] == 0 and produce['controller_sessions'] == 1
     and produce['logs_verified'] is True and produce['verified_tls'] is True
     and 60 <= produce['elapsed_seconds'] < 150, 'actual_producer_15_rounds_60_seconds')
normal, fault, final = (responses[s] for s in ('normal-live','fault-live','final'))
normal_projection = load(CTRL/'normal-live-public-projection.json')
fault_projection = load(CTRL/'fault-live-public-projection.json')
need(normal['logical_point'] == 'stable_boundary' and normal['completed_rounds'] == 1
     and normal['finance']['golden']['compared'] is True and normal['finance']['golden']['passed'] is True
     and normal['alerts'] == [] and normal_projection['actual_fault_signals_after'] == {'parent':0,'worker':0}, 'normal_real_stable_golden_before_fault')
w = fault_projection['fault_witness']; proc = normal['worker']['process']
need(w['pidfd_death_observed'] is True and w['pid'] == proc['pid'] and w['birth'] == proc['birth']
     and w['old_generation'] == normal['worker']['generation'] == 1
     and w['boot'] == BOOT and w['uid'] == 1000, 'actual_same_worker_pidfd_death_witness')
need(w['death_wall_ns'] <= fault['sample_wall_ns'] <= w['death_wall_ns'] + 5*10**9
     and fault['logical_point'] == 'inflight_or_unknown' and fault['completed_rounds'] == 4
     and fault['active_rounds'] == [5] and fault['alerts'] == []
     and any(x['kind']=='worker' and x['old_generation']==1 and x['round']==5 for x in fault['planned_faults'])
     and fault_projection['actual_fault_signals_after'] == {'worker':1,'parent':0}, 'fault_death_tied_to_actual_inflight_round5')
need(fault['finance']['golden']['compared'] is False
     and fault['finance']['golden']['reason'] == 'inflight_or_logical_point_unproven', 'fault_not_claimed_stable_financial_golden')
need(final['logical_point'] == 'stable_boundary' and final['completed_rounds'] == 15
     and final['active_rounds'] == [] and final['alerts'] == [] and final['unresolved_faults'] == 0
     and final['finance']['golden']['compared'] is True and final['finance']['golden']['passed'] is True, 'final_real_stable_golden')
need(Counter(x['kind'] for x in final['planned_faults']) == {'worker':3,'parent':1}
     and all(x['state']=='DONE' and x['signal_sent'] is True for x in final['planned_faults']), 'all_four_actual_fault_actions_done')
f = final['finance']; expected_counts = {'ledger_events':81,'ledger_postings':194,'uta_orders':60,'uta_matches':30,'uta_fills':60,
    'partial_cancelled_orders':15,'terminal_account_commands':90,'control_commands':30,'uta_risk_decisions':120}
need(all(f['counts'][k] == v for k,v in expected_counts.items()), 'actual_financial_count_denominators')
need(f['residuals'] == {'live_orders':0,'positions':[]} and f['retry_alerts'] == []
     and all(x['principal_minor']==0 and x['interest_minor']==0 for x in f['gross_debt']), 'final_zero_debt_live_orders_positions')
sums = defaultdict(int)
for row in f['balances']:
    need(type(row['minor_units']) is int, 'balance_exact_integer')
    sums[row['asset']] += row['minor_units']
need(all(x==0 for x in sums.values()), 'recorded_final_balance_snapshot_per_currency_sums_zero')
inbox = f['command_inbox']
need(len(inbox) == 120 and len({x['command_id'] for x in inbox}) == 120
     and len({x['sequence'] for x in inbox}) == 120
     and all(x['state']=='SUCCEEDED' and x['quarantined'] is False and not x['error_present'] for x in inbox), 'recorded_120_unique_terminal_commands')
recon = final['final_reconciliation']; cold = responses['cold']
need(recon['independent_reopen_reconciliation_passed'] is True and recon['independent_reopen_same_watermark'] is True
     and set(recon['errors']) == {'actual_6h_and_5400_rounds_required','producer_actual_active_duration_incomplete','producer_cold_audit_same_watermark_missing'}
     and recon['eligible'] is False, 'short_final_full_reopen_with_exact_long_blockers')
need(cold['short_smoke_cold_audit_passed'] is True and cold['long_run_receipt_issued'] is False
     and cold['producer_audit_scope'] == 'short_smoke_private_complete_clone'
     and cold['watermark_before'] == cold['watermark_after'] == recon['watermark']
     and cold['watermark_before']['financial'] == f['watermark'], 'cold_complete_clone_same_full_watermark')
need(cold == load(ARC/'smoke--short-smoke-cold-audit.json'), 'actual_cold_result_matches_archived_original')
negative = responses['strict-negative']
need(negative['error_type'] == 'ValueError'
     and negative['error_digest'] == sha(b'producer_audit_requires_other_final_checks_passed')
     and negative['final_evidence_eligible'] is False
     and negative['alerts'] == ['producer_cold_audit_failed_closed'], 'strict_expected_digest_and_no_long_receipt')

attestation = load(ROOT/'final-outer-attestation.json')
erratum = load(ROOT/'timing-boundary-erratum.json')
need(erratum['original_attestation_sha256'] == sha(raw(ROOT/'final-outer-attestation.json'))
     and erratum['original_numeric_value_seconds'] == 64.379813724
     and erratum['original_source_and_results_rewritten'] is False, 'append_only_exact_timing_erratum')
need(raw(ROOT/'timing-boundary-erratum.json') == raw(ARC/'root--timing-boundary-erratum.json'), 'exact_public_erratum_copy')
outer = load(ROOT/'controller.stdout'); provisional = load(CTRL/'outcome-provisional.json')
need(attestation['controller_stdout_sha256'] == sha(raw(ROOT/'controller.stdout'))
     and attestation['controller_stderr_sha256'] == sha(raw(ROOT/'controller.stderr'))
     and raw(ROOT/'controller.stderr') == b'', 'root_closed_raw_hashes')
need(attestation['controller_exit_code'] == 0 and attestation['controller_original_result'] == outer
     and outer['stage_states'] == {s:'PASS' for s in responses}
     and outer['full_smoke_passed'] is True and provisional['full_smoke_passed'] is True, 'actual_controller_exit_and_retained_outcome')
need(Fraction(str(attestation['actual_first_producer_to_closed_streams_and_hashes_seconds'])) == Fraction(64_379_813_724,10**9)
     and Fraction(64_379_813_724,10**9) < 150
     and attestation['actual_outer_150_passed'] is True, 'recorded_root_endpoint_under_fixed_150')
need(attestation['long_authorized'] is False and attestation['production_approved'] is False
     and outer['new_long_authorized'] is False and outer['financial_6h_passed'] is False, 'no_long_or_production_qualification')

# Post-completion metadata only; no signal, status CLI, process creation, or DB.
known = {pid:(birth,role) for pid,birth,role in identities}
for row in load(ARC/'outcome.json')['additional_known_identity_metadata_from_private_original_allowlisted_fields']:
    known.setdefault(row['pid'], (row['expected_birth'], row['role']))
for s in ('startup','normal-live','fault-live','final'):
    r = responses[s]
    for role, obj in [('driver',r['driver']),('listener',r['listener']),('worker',r['worker']['process'])]:
        if obj.get('pid'):
            known.setdefault(obj['pid'], (obj.get('birth'), s+':'+role))
known[load(ROOT/'launcher-started.json')['controller_PID']] = (None,'controller')
proc_facts = []
for pid,(birth,role) in sorted(known.items()):
    need(pid not in (4471,8784), 'cleanup_scope_excludes_protected:' + str(pid))
    path = Path('/proc')/str(pid)/'stat'
    try:
        text = path.read_text(); fields = text[text.rindex(')')+2:].split()
        current_birth, state = fields[19], fields[0]
        need(birth not in (None,'None') and current_birth != str(birth), 'known_original_PID_exited:' + str(pid))
        result = 'PID_REUSED_DIFFERENT_BIRTH'
    except FileNotFoundError:
        result = 'MISSING'
    proc_facts.append({'pid':pid,'expected_birth':birth,'role':role,'observed':result})

result = {'status':'INDEPENDENT_RETAINED_FILES_SMOKE02_NARROW_SCOPE_ACCEPT',
          'reviewed_at_utc':datetime.now(timezone.utc).isoformat(), 'source_commit':SOURCE,
          'controller_preparation_commit':'f2ad840f91a41bc098fedadc3ffc30c590f38bc6',
          'author_actual_archive_commit':'a97483d89fed2d440cc36bdf850be34e179d1cb1',
          'author_timing_addendum_commit':'bf8492534d69a64ad2e859b9423c63473d16eb88',
          'checks_passed':len(checks),'checks':checks,'stages':stage_facts,
          'financial_counts':expected_counts,'recorded_balance_sums_minor':dict(sums),
          'known_process_metadata':proc_facts,'input_hashes':files,
          'timing_boundary':'controller exited; root streams closed/fsynced/read/parsed and first metadata read; root auxiliary hashes and attestation serialization follow endpoint',
          'root_endpoint_seconds_exact':'64379813724/1000000000',
          'SQL_or_product_import_or_job_execution':False,'independent_DB_reexecution':False,
          'all_unobserved_descendant_PIDs_proven':False,
          'financial_6h_passed':False,'capacity_10000_per_s_passed':False,
          'production_approved':False,'new_long_authorized':False,'first_smoke01_remains_NO_GO':True}
print(json.dumps(result,sort_keys=True,indent=2))
